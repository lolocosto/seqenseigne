"""tests/test_R4e3_edition_objectif.py — R4e3.

Tests de l'édition granulaire d'un objectif v2 (code, nom, méthode,
critères) + catalogue de méthodes par séquence.

Deux axes, même pattern que R4e1 / R4e2 :
  1. Service (tests unitaires purs sur sqlite3 en mémoire)
  2. Routes (tests d'intégration via client Flask du conftest global)
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Schéma minimal pour les tests unitaires ──────────────────────────────────
# On réplique les 5 tables v2 + `methodes` (colonnes utilisées par R4e3).

_SCHEMA_TEST = """
CREATE TABLE methodes (
    id             TEXT PRIMARY KEY,
    titre          TEXT NOT NULL DEFAULT '',
    niveau         TEXT NOT NULL DEFAULT '',
    sequence       TEXT NOT NULL DEFAULT '',
    num_methode    INTEGER,
    num_objectif   TEXT NOT NULL DEFAULT '',
    fichier        TEXT NOT NULL DEFAULT '',
    etat_code      TEXT NOT NULL DEFAULT 'en_cours'  -- v0.10.4
);

CREATE TABLE sequences_par_niveau (
    id            TEXT PRIMARY KEY,
    niveau        TEXT NOT NULL,
    sequence_code TEXT NOT NULL,
    parametres    TEXT NOT NULL DEFAULT '',
    UNIQUE (niveau, sequence_code)
);
CREATE TABLE sequence_parties (
    id                     TEXT PRIMARY KEY,
    sequence_par_niveau_id TEXT NOT NULL
                           REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    numero                 INTEGER NOT NULL,
    UNIQUE (sequence_par_niveau_id, numero)
);
CREATE TABLE partie_precedences (
    partie_id        TEXT NOT NULL
                     REFERENCES sequence_parties(id) ON DELETE CASCADE,
    precedent_niveau TEXT NOT NULL,
    precedent_seq    TEXT NOT NULL,
    PRIMARY KEY (partie_id, precedent_niveau, precedent_seq)
);
CREATE TABLE objectifs (
    id         TEXT PRIMARY KEY,
    partie_id  TEXT NOT NULL
               REFERENCES sequence_parties(id) ON DELETE CASCADE,
    code       TEXT NOT NULL,
    nom        TEXT NOT NULL DEFAULT '',
    methode_id TEXT,
    critere_F  TEXT NOT NULL DEFAULT '',
    critere_A  TEXT NOT NULL DEFAULT '',
    critere_E  TEXT NOT NULL DEFAULT '',
    fin_cycle  TEXT NOT NULL DEFAULT 'N',
    UNIQUE (partie_id, code)
);
CREATE TABLE notions (
    id     TEXT PRIMARY KEY,
    titre  TEXT NOT NULL DEFAULT '',
    corps  TEXT NOT NULL DEFAULT '',
    niveau TEXT NOT NULL DEFAULT '',
    sequence TEXT NOT NULL DEFAULT ''
);
CREATE TABLE objectif_notions (
    objectif_id TEXT NOT NULL
                REFERENCES objectifs(id) ON DELETE CASCADE,
    notion_id   TEXT NOT NULL
                REFERENCES notions(id) ON DELETE CASCADE,
    ordre       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (objectif_id, notion_id)
);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(_SCHEMA_TEST)
    yield c
    c.close()


@pytest.fixture
def base(conn):
    """Structure commune : 1 séquence sn_A (N11/S03) avec 2 parties :
        pt_A1 (#1) : ob_01 (code '01', sans méthode) + ob_02 (code '02',
                     lié à me_m1)
        pt_A2 (#2) : ob_11 (code '11', lié à me_m2)
    Méthodes de la séquence : me_m1, me_m2. Méthode d'une autre séquence
    (N11/S05) : me_autre (pour tester le filtre du catalogue).
    """
    conn.executescript("""
        INSERT INTO methodes (id, titre, niveau, sequence, num_methode) VALUES
            ('me_m1',    'Simplifier une fraction', 'N11', 'S03', 1),
            ('me_m2',    'Additionner des fractions','N11', 'S03', 2),
            ('me_autre', 'Méthode d''une autre séquence', 'N11', 'S05', 1);

        INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
            ('sn_A', 'N11', 'S03');

        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES
            ('pt_A1', 'sn_A', 1),
            ('pt_A2', 'sn_A', 2);

        INSERT INTO objectifs (id, partie_id, code, nom, methode_id,
                                  critere_F, critere_A, critere_E) VALUES
            ('ob_01', 'pt_A1', '01', 'Cours',     NULL,    'Notes', 'Fiches', 'Oral'),
            ('ob_02', 'pt_A1', '02', 'Simplifier','me_m1', 'cF 02', 'cA 02', 'cE 02'),
            ('ob_11', 'pt_A2', '11', 'Additionner','me_m2','cF 11', 'cA 11', 'cE 11');
    """)
    conn.commit()
    return conn


# ═════════════════════════════════════════════════════════════════════════════
# 1. modifier_code_objectif
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    modifier_code_objectif,
    CodeObjectifInvalide,
    CodeObjectifDejaUtilise,
    ObjectifIntrouvable,
)


class TestModifierCodeObjectif:
    def test_renomme_code(self, base):
        rep = modifier_code_objectif(base, "ob_11", "05")
        assert rep["code"] == "05"
        # Persistance
        row = base.execute(
            "SELECT code FROM objectifs WHERE id = ?", ("ob_11",)
        ).fetchone()
        assert row["code"] == "05"

    def test_retour_inclut_code_coherent(self, base):
        """Renommer ob_11 (était en partie 2, code 11 → cohérent)
        en '01' : code 01 dans partie 2 → incohérent."""
        rep = modifier_code_objectif(base, "ob_11", "01")
        # Attention : '01' est déjà porté par ob_01 dans pt_A1, mais ob_11
        # est dans pt_A2 donc pas de conflit (UNIQUE par partie).
        assert rep["code"] == "01"
        assert rep["code_coherent"] is False  # '01' en partie 2 = incohérent

    def test_idempotent_meme_code(self, base):
        """Renommer avec le code actuel : no-op, pas d'erreur."""
        rep = modifier_code_objectif(base, "ob_02", "02")
        assert rep["code"] == "02"

    def test_conflit_dans_meme_partie(self, base):
        """ob_02 ne peut pas prendre '01' (déjà porté par ob_01 dans pt_A1)."""
        with pytest.raises(CodeObjectifDejaUtilise) as ei:
            modifier_code_objectif(base, "ob_02", "01")
        assert ei.value.code == "code_objectif_deja_utilise"
        assert ei.value.details["code_demande"] == "01"

    def test_pas_de_conflit_autre_partie(self, base):
        """Un code peut être réutilisé s'il est dans une autre partie :
        on renomme ob_11 (pt_A2) en '01', même si ob_01 (pt_A1) a '01'."""
        rep = modifier_code_objectif(base, "ob_11", "01")
        assert rep["code"] == "01"

    def test_code_strip(self, base):
        """Espaces en début/fin sont retirés."""
        rep = modifier_code_objectif(base, "ob_11", "  05  ")
        assert rep["code"] == "05"

    @pytest.mark.parametrize("code_invalide", [
        "",         # vide
        "   ",      # espaces seuls
        "12345",    # trop long
        "A B",      # espace interne
        "A\tB",     # tab interne
        123,        # pas str
        None,
    ])
    def test_codes_invalides(self, base, code_invalide):
        with pytest.raises(CodeObjectifInvalide):
            modifier_code_objectif(base, "ob_02", code_invalide)

    def test_objectif_inexistant_404(self, base):
        with pytest.raises(ObjectifIntrouvable):
            modifier_code_objectif(base, "ob_xxx", "99")

    def test_accepte_codes_alphanumeriques(self, base):
        """Codes 'Cours', 'A1'... sont tolérés (tests non-numériques)."""
        rep = modifier_code_objectif(base, "ob_02", "A1")
        assert rep["code"] == "A1"
        assert rep["code_coherent"] is True  # non-applicable → True


# ═════════════════════════════════════════════════════════════════════════════
# 2. modifier_nom_objectif
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import modifier_nom_objectif


class TestModifierNomObjectif:
    def test_change_nom(self, base):
        rep = modifier_nom_objectif(base, "ob_02", "Nouveau nom")
        assert rep["nom"] == "Nouveau nom"
        row = base.execute(
            "SELECT nom FROM objectifs WHERE id = ?", ("ob_02",)
        ).fetchone()
        assert row["nom"] == "Nouveau nom"

    def test_nom_vide_accepte(self, base):
        """Chaîne vide acceptée — objectif hérité sans intitulé propre."""
        rep = modifier_nom_objectif(base, "ob_02", "")
        assert rep["nom"] == ""

    def test_nom_strip(self, base):
        rep = modifier_nom_objectif(base, "ob_02", "  Nom avec espaces  ")
        assert rep["nom"] == "Nom avec espaces"

    def test_nom_non_string(self, base):
        """None ou type non-string → chaîne vide (tolérance)."""
        rep = modifier_nom_objectif(base, "ob_02", None)
        assert rep["nom"] == ""
        rep = modifier_nom_objectif(base, "ob_02", 42)
        assert rep["nom"] == ""

    def test_objectif_inexistant_404(self, base):
        with pytest.raises(ObjectifIntrouvable):
            modifier_nom_objectif(base, "ob_xxx", "peu importe")


# ═════════════════════════════════════════════════════════════════════════════
# 3. modifier_methode_objectif
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import modifier_methode_objectif, MethodeIntrouvable


class TestModifierMethodeObjectif:
    def test_attache_methode(self, base):
        """v0.10.7 — me_m1 est déjà lié à ob_02 (cf. fixture). On doit
        d'abord détacher me_m1 de ob_02 avant de pouvoir l'attacher à
        ob_01 (cardinalité 1-1 méthode → objectif)."""
        modifier_methode_objectif(base, "ob_02", None)  # détacher
        rep = modifier_methode_objectif(base, "ob_01", "me_m1")
        assert rep["methode_id"] == "me_m1"
        assert rep["methode_titre"] == "Simplifier une fraction"

    def test_change_methode(self, base):
        """v0.10.7 — ob_02 avait me_m1, on passe à me_m2 — mais me_m2
        est déjà lié à ob_11. Il faut donc d'abord détacher me_m2 de
        ob_11."""
        modifier_methode_objectif(base, "ob_11", None)  # libérer me_m2
        rep = modifier_methode_objectif(base, "ob_02", "me_m2")
        assert rep["methode_id"] == "me_m2"
        assert rep["methode_titre"] == "Additionner des fractions"

    @pytest.mark.parametrize("valeur", [None, ""])
    def test_detache_methode(self, base, valeur):
        """None ou chaîne vide → methode_id devient NULL en base."""
        rep = modifier_methode_objectif(base, "ob_02", valeur)
        assert rep["methode_id"] is None
        assert rep["methode_titre"] is None

    def test_methode_inexistante_404(self, base):
        with pytest.raises(MethodeIntrouvable):
            modifier_methode_objectif(base, "ob_02", "me_xxx")

    def test_objectif_inexistant_404(self, base):
        with pytest.raises(ObjectifIntrouvable):
            modifier_methode_objectif(base, "ob_xxx", "me_m1")

    def test_refuse_methode_hors_sequence(self, base):
        """v0.10.7 — Une méthode ne peut être liée qu'à un objectif de
        sa séquence d'origine. me_autre est de N11/S05 ; ob_02 est de
        N11/S03 → refus."""
        from services.v2_edition import MethodeHorsSequence
        with pytest.raises(MethodeHorsSequence):
            modifier_methode_objectif(base, "ob_02", "me_autre")

    def test_refuse_methode_deja_liee(self, base):
        """v0.10.7 — me_m2 est déjà liée à ob_11 ; tentative de la
        rattacher à ob_02 → refus avec MethodeDejaLiee."""
        from services.v2_edition import MethodeDejaLiee
        with pytest.raises(MethodeDejaLiee):
            modifier_methode_objectif(base, "ob_02", "me_m2")

    def test_idempotent_meme_objectif(self, base):
        """v0.10.7 — Réattacher la même méthode au même objectif est
        idempotent (no-op silencieux, pas d'erreur)."""
        # ob_02 a déjà me_m1 (fixture)
        rep = modifier_methode_objectif(base, "ob_02", "me_m1")
        assert rep["methode_id"] == "me_m1"


# ═════════════════════════════════════════════════════════════════════════════
# 4. modifier_criteres_objectif
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import modifier_criteres_objectif


class TestModifierCriteresObjectif:
    def test_change_un_seul_critere(self, base):
        """On ne met à jour que critere_F, les autres doivent rester."""
        rep = modifier_criteres_objectif(base, "ob_02", critere_F="nouveau F")
        assert rep["critere_F"] == "nouveau F"
        assert rep["critere_A"] == "cA 02"  # inchangé
        assert rep["critere_E"] == "cE 02"  # inchangé

    def test_change_tous_les_criteres(self, base):
        rep = modifier_criteres_objectif(
            base, "ob_02",
            critere_F="F nouveau",
            critere_A="A nouveau",
            critere_E="E nouveau",
        )
        assert rep["critere_F"] == "F nouveau"
        assert rep["critere_A"] == "A nouveau"
        assert rep["critere_E"] == "E nouveau"

    def test_effacer_critere_avec_chaine_vide(self, base):
        """Passer "" efface explicitement. None = ne pas modifier."""
        rep = modifier_criteres_objectif(base, "ob_02", critere_A="")
        assert rep["critere_A"] == ""
        assert rep["critere_F"] == "cF 02"  # inchangé

    def test_aucun_parametre_noop(self, base):
        """Tous les critères à None → pas d'update, retour silencieux."""
        rep = modifier_criteres_objectif(base, "ob_02")
        assert rep["critere_F"] == "cF 02"
        assert rep["critere_A"] == "cA 02"
        assert rep["critere_E"] == "cE 02"

    def test_accepte_latex(self, base):
        """Pas de validation de syntaxe LaTeX, accepte tout."""
        latex = r"$\frac{a}{b} = \frac{1}{2}$"
        rep = modifier_criteres_objectif(base, "ob_02", critere_F=latex)
        assert rep["critere_F"] == latex

    def test_objectif_inexistant_404(self, base):
        with pytest.raises(ObjectifIntrouvable):
            modifier_criteres_objectif(base, "ob_xxx", critere_F="x")


# ═════════════════════════════════════════════════════════════════════════════
# 5. lister_methodes_de_sequence
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import lister_methodes_de_sequence


class TestListerMethodesDeSequence:
    def test_liste_methodes_de_la_sequence(self, base):
        meths = lister_methodes_de_sequence(base, "N11", "S03")
        ids = [m["id"] for m in meths]
        assert "me_m1" in ids
        assert "me_m2" in ids
        assert "me_autre" not in ids   # autre séquence → exclue

    def test_filtre_par_niveau(self, base):
        """Rien sur N12."""
        meths = lister_methodes_de_sequence(base, "N12", "S03")
        assert meths == []

    def test_filtre_par_sequence(self, base):
        """me_autre est dans S05, pas S03."""
        meths = lister_methodes_de_sequence(base, "N11", "S05")
        ids = [m["id"] for m in meths]
        assert ids == ["me_autre"]

    def test_ordre_par_num_methode(self, base):
        """me_m1 (num 1) avant me_m2 (num 2)."""
        meths = lister_methodes_de_sequence(base, "N11", "S03")
        assert [m["id"] for m in meths] == ["me_m1", "me_m2"]

    def test_sequence_inconnue_liste_vide(self, base):
        """Pas d'erreur, juste une liste vide."""
        meths = lister_methodes_de_sequence(base, "N11", "S99")
        assert meths == []


# ═════════════════════════════════════════════════════════════════════════════
# 6. Tests d'intégration des routes
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def client_edition(app):
    """Peuple la base SqliteStore de l'app Flask avec la même structure
    que la fixture `base` ci-dessus (+ suffixe '_rt' sur les IDs)."""
    import sqlite3 as _sq3
    store = app.json_store
    db = _sq3.connect(str(store.db_path))
    try:
        db.executemany(
            "INSERT INTO methodes (id, titre, niveau, sequence, num_methode) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                ("me_m1_rt",    "Simplifier une fraction",  "N11", "S03", 1),
                ("me_m2_rt",    "Additionner des fractions","N11", "S03", 2),
                ("me_autre_rt", "Autre",                    "N11", "S05", 1),
            ],
        )
        db.execute(
            "INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
            "VALUES ('sn_A_rt', 'N11', 'S03')"
        )
        db.executemany(
            "INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
            "VALUES (?, ?, ?)",
            [("pt_A1_rt", "sn_A_rt", 1), ("pt_A2_rt", "sn_A_rt", 2)],
        )
        db.executemany(
            "INSERT INTO objectifs (id, partie_id, code, nom, methode_id, "
            "critere_F, critere_A, critere_E) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("ob_01_rt", "pt_A1_rt", "01", "Cours", None,
                 "Notes", "Fiches", "Oral"),
                ("ob_02_rt", "pt_A1_rt", "02", "Simplifier", "me_m1_rt",
                 "cF 02", "cA 02", "cE 02"),
                ("ob_11_rt", "pt_A2_rt", "11", "Additionner", "me_m2_rt",
                 "cF 11", "cA 11", "cE 11"),
            ],
        )
        db.commit()
    finally:
        db.close()
    return app.test_client()


# --- code ---

def test_route_modifier_code_succes(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_11_rt/code", json={"code": "05"}
    )
    assert rep.status_code == 200
    assert rep.get_json()["code"] == "05"


def test_route_modifier_code_conflit(client_edition):
    """ob_02_rt ne peut pas prendre '01' (déjà pris dans pt_A1_rt)."""
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_02_rt/code", json={"code": "01"}
    )
    assert rep.status_code == 409
    assert rep.get_json()["code"] == "code_objectif_deja_utilise"


def test_route_modifier_code_invalide(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_11_rt/code", json={"code": ""}
    )
    assert rep.status_code == 400
    assert rep.get_json()["code"] == "code_objectif_invalide"


def test_route_modifier_code_sans_champ(client_edition):
    rep = client_edition.patch("/api/v2/objectifs/ob_11_rt/code", json={})
    assert rep.status_code == 400
    assert rep.get_json()["code"] == "code_objectif_invalide"


def test_route_modifier_code_objectif_inexistant(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_xxx/code", json={"code": "99"}
    )
    assert rep.status_code == 404


# --- nom ---

def test_route_modifier_nom_succes(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_02_rt/nom",
        json={"nom": "Nouveau titre"},
    )
    assert rep.status_code == 200
    assert rep.get_json()["nom"] == "Nouveau titre"


def test_route_modifier_nom_vide(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_02_rt/nom", json={"nom": ""}
    )
    assert rep.status_code == 200
    assert rep.get_json()["nom"] == ""


# --- méthode ---

def test_route_attache_methode(client_edition):
    """v0.10.7 — me_m1_rt est déjà liée à ob_02_rt (fixture). On
    détache d'abord puis on rattache à ob_01_rt."""
    detach = client_edition.patch(
        "/api/v2/objectifs/ob_02_rt/methode", json={"methode_id": None}
    )
    assert detach.status_code == 200
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_01_rt/methode",
        json={"methode_id": "me_m1_rt"},
    )
    assert rep.status_code == 200
    data = rep.get_json()
    assert data["methode_id"] == "me_m1_rt"
    assert data["methode_titre"] == "Simplifier une fraction"


def test_route_detache_methode_null(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_02_rt/methode",
        json={"methode_id": None},
    )
    assert rep.status_code == 200
    data = rep.get_json()
    assert data["methode_id"] is None


def test_route_methode_inexistante_404(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_02_rt/methode",
        json={"methode_id": "me_xxx"},
    )
    assert rep.status_code == 404
    assert rep.get_json()["code"] == "methode_introuvable"


# --- critères ---

def test_route_modifier_critere_F_seulement(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_02_rt/criteres",
        json={"critere_F": "F nouveau"},
    )
    assert rep.status_code == 200
    data = rep.get_json()
    assert data["critere_F"] == "F nouveau"
    assert data["critere_A"] == "cA 02"  # inchangé


def test_route_modifier_tous_criteres(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_02_rt/criteres",
        json={
            "critere_F": "F total",
            "critere_A": "A total",
            "critere_E": "E total",
        },
    )
    assert rep.status_code == 200
    data = rep.get_json()
    assert data["critere_F"] == "F total"
    assert data["critere_A"] == "A total"
    assert data["critere_E"] == "E total"


def test_route_modifier_criteres_objectif_inexistant(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_xxx/criteres",
        json={"critere_F": "x"},
    )
    assert rep.status_code == 404


# --- catalogue méthodes ---

def test_route_lister_methodes_ok(client_edition):
    rep = client_edition.get("/api/v2/methodes?niveau=N11&sequence=S03")
    assert rep.status_code == 200
    data = rep.get_json()
    ids = [m["id"] for m in data["methodes"]]
    assert "me_m1_rt" in ids
    assert "me_m2_rt" in ids
    assert "me_autre_rt" not in ids


def test_route_lister_methodes_sans_params(client_edition):
    rep = client_edition.get("/api/v2/methodes")
    assert rep.status_code == 400
    assert rep.get_json()["code"] == "parametres_manquants"


def test_route_lister_methodes_sequence_inconnue(client_edition):
    rep = client_edition.get("/api/v2/methodes?niveau=N12&sequence=S99")
    assert rep.status_code == 200
    assert rep.get_json()["methodes"] == []


# --- Vérif que les nouvelles routes acceptent bien seulement PATCH/GET ---

def test_routes_objectif_methodes_httpverb():
    """Les routes d'édition d'objectif sont strictement PATCH, le
    catalogue est strictement GET."""
    from flask import Flask
    from routes.v2_edition import bp_v2_edition

    app = Flask(__name__)
    app.register_blueprint(bp_v2_edition)
    rules = {r.endpoint.split(".")[-1]: r.methods for r in app.url_map.iter_rules()
             if r.endpoint.startswith("v2_edition.")}

    for endpoint in (
        "api_modifier_code_objectif",
        "api_modifier_nom_objectif",
        "api_modifier_methode_objectif",
        "api_modifier_criteres_objectif",
    ):
        assert "PATCH" in rules[endpoint]
        assert "POST"  not in rules[endpoint]
        assert "PUT"   not in rules[endpoint]

    assert "GET"   in rules["api_lister_methodes_de_sequence"]
    assert "PATCH" not in rules["api_lister_methodes_de_sequence"]


# ═════════════════════════════════════════════════════════════════════════════
# v0.6.4 — fin_cycle et notions associées
# ═════════════════════════════════════════════════════════════════════════════
#
# La propriété "fin de cycle 4" et la liste des notions associées étaient
# historiquement attachées à la méthode (table `methodes`, table `methode_notions`),
# mais sémantiquement elles décrivent l'OBJECTIF (compétence du programme officiel).
# v0.6.4 les déplace sur `objectifs` : nouvelle colonne `fin_cycle` et nouvelle
# table `objectif_notions`.

from services.v2_edition import (
    modifier_fin_cycle_objectif,
    ajouter_notion_objectif,
    retirer_notion_objectif,
)


class TestModifierFinCycleObjectif:
    """Service modifier_fin_cycle_objectif : bascule O/N et accepte
    plusieurs formats d'entrée (booléen, 'O', 'OUI', etc.)."""

    def test_marquer_fin_cycle_par_chaine_O(self, base):
        rep = modifier_fin_cycle_objectif(base, "ob_02", "O")
        assert rep["fin_cycle"] == "O"
        # Vérifier l'état persistant
        row = base.execute(
            "SELECT fin_cycle FROM objectifs WHERE id = 'ob_02'"
        ).fetchone()
        assert row[0] == "O"

    def test_marquer_fin_cycle_par_booleen(self, base):
        rep = modifier_fin_cycle_objectif(base, "ob_02", True)
        assert rep["fin_cycle"] == "O"

    def test_demarquer_fin_cycle(self, base):
        # D'abord marquer
        modifier_fin_cycle_objectif(base, "ob_02", True)
        # Puis démarquer
        rep = modifier_fin_cycle_objectif(base, "ob_02", False)
        assert rep["fin_cycle"] == "N"

    def test_valeurs_diverses_acceptees(self, base):
        """'oui', 'OUI', 'true', '1' → 'O' ; tout autre → 'N'."""
        for entree, attendu in [
            ("oui", "O"),
            ("OUI", "O"),
            ("true", "O"),
            ("1", "O"),
            ("non", "N"),
            ("0", "N"),
            ("", "N"),
            (None, "N"),
        ]:
            rep = modifier_fin_cycle_objectif(base, "ob_02", entree)
            assert rep["fin_cycle"] == attendu, (
                f"Entrée {entree!r} → attendu {attendu!r}, reçu {rep['fin_cycle']!r}"
            )

    def test_objectif_inexistant_leve(self, base):
        from services.v2_edition import ObjectifIntrouvable
        with pytest.raises(ObjectifIntrouvable):
            modifier_fin_cycle_objectif(base, "ob_zzzzz", "O")


class TestNotionsObjectif:
    """Service ajouter_notion_objectif / retirer_notion_objectif et leur
    intégration dans le retour standard de l'objectif."""

    @pytest.fixture
    def base_avec_notions(self, base):
        """Ajoute 3 notions à la base de test, prêtes à être associées."""
        base.executemany(
            "INSERT INTO notions (id, titre) VALUES (?, ?)",
            [
                ("no_n1", "Notion 1 — Définition de fraction"),
                ("no_n2", "Notion 2 — Simplification"),
                ("no_n3", "Notion 3 — Quotient"),
            ],
        )
        return base

    def test_ajouter_premiere_notion(self, base_avec_notions):
        rep = ajouter_notion_objectif(base_avec_notions, "ob_02", "no_n1")
        assert len(rep["notions"]) == 1
        assert rep["notions"][0]["id"] == "no_n1"
        assert rep["notions"][0]["titre"] == "Notion 1 — Définition de fraction"

    def test_ajouter_plusieurs_notions_ordre_preserve(self, base_avec_notions):
        """L'ordre d'insertion détermine l'ordre `ordre`. Le retour est
        trié par `ordre`, donc l'ordre d'insertion."""
        ajouter_notion_objectif(base_avec_notions, "ob_02", "no_n3")
        ajouter_notion_objectif(base_avec_notions, "ob_02", "no_n1")
        rep = ajouter_notion_objectif(base_avec_notions, "ob_02", "no_n2")
        ids = [n["id"] for n in rep["notions"]]
        assert ids == ["no_n3", "no_n1", "no_n2"]

    def test_ajouter_notion_idempotent(self, base_avec_notions):
        """Ajouter 2 fois la même notion ne crée pas de doublon."""
        ajouter_notion_objectif(base_avec_notions, "ob_02", "no_n1")
        rep = ajouter_notion_objectif(base_avec_notions, "ob_02", "no_n1")
        assert len(rep["notions"]) == 1

    def test_ajouter_notion_inexistante_leve(self, base_avec_notions):
        from services.v2_edition import V2EditionErreur
        with pytest.raises(V2EditionErreur):
            ajouter_notion_objectif(base_avec_notions, "ob_02", "no_zzz")

    def test_ajouter_objectif_inexistant_leve(self, base_avec_notions):
        from services.v2_edition import ObjectifIntrouvable
        with pytest.raises(ObjectifIntrouvable):
            ajouter_notion_objectif(base_avec_notions, "ob_zzz", "no_n1")

    def test_retirer_notion_existante(self, base_avec_notions):
        ajouter_notion_objectif(base_avec_notions, "ob_02", "no_n1")
        ajouter_notion_objectif(base_avec_notions, "ob_02", "no_n2")
        rep = retirer_notion_objectif(base_avec_notions, "ob_02", "no_n1")
        ids = [n["id"] for n in rep["notions"]]
        assert ids == ["no_n2"]

    def test_retirer_notion_jamais_ajoutee_idempotent(self, base_avec_notions):
        """Retirer une association inexistante : pas d'erreur, no-op."""
        rep = retirer_notion_objectif(base_avec_notions, "ob_02", "no_n1")
        assert rep["notions"] == []


# ── Routes : fin_cycle et notions ────────────────────────────────────────────

@pytest.fixture
def client_avec_notions(client_edition, app):
    """Ajoute des notions à la fixture client_edition pour tester les routes
    POST/DELETE notions."""
    import sqlite3 as _sq3
    db = _sq3.connect(str(app.json_store.db_path))
    try:
        db.executemany(
            "INSERT INTO notions (id, titre) VALUES (?, ?)",
            [
                ("no_a", "Notion A"),
                ("no_b", "Notion B"),
            ],
        )
        db.commit()
    finally:
        db.close()
    return client_edition


def test_route_fin_cycle_marquer(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_02_rt/fin-cycle",
        json={"fin_cycle": "O"},
    )
    assert rep.status_code == 200
    assert rep.get_json()["fin_cycle"] == "O"


def test_route_fin_cycle_demarquer(client_edition):
    # Marquer puis démarquer
    client_edition.patch(
        "/api/v2/objectifs/ob_02_rt/fin-cycle", json={"fin_cycle": "O"}
    )
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_02_rt/fin-cycle", json={"fin_cycle": "N"}
    )
    assert rep.status_code == 200
    assert rep.get_json()["fin_cycle"] == "N"


def test_route_fin_cycle_payload_invalide(client_edition):
    """Body sans 'fin_cycle' : 400."""
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_02_rt/fin-cycle", json={}
    )
    assert rep.status_code == 400
    assert "fin_cycle" in rep.get_json()["error"].lower()


def test_route_fin_cycle_objectif_inexistant(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_zzz/fin-cycle", json={"fin_cycle": "O"}
    )
    assert rep.status_code == 404


def test_route_ajouter_notion(client_avec_notions):
    rep = client_avec_notions.post(
        "/api/v2/objectifs/ob_02_rt/notions",
        json={"notion_id": "no_a"},
    )
    assert rep.status_code == 201
    notions = rep.get_json()["notions"]
    assert len(notions) == 1
    assert notions[0]["id"] == "no_a"


def test_route_ajouter_notion_payload_invalide(client_avec_notions):
    rep = client_avec_notions.post(
        "/api/v2/objectifs/ob_02_rt/notions", json={}
    )
    assert rep.status_code == 400


def test_route_ajouter_notion_inexistante(client_avec_notions):
    rep = client_avec_notions.post(
        "/api/v2/objectifs/ob_02_rt/notions",
        json={"notion_id": "no_zzzz"},
    )
    assert rep.status_code == 404


def test_route_retirer_notion(client_avec_notions):
    # Ajouter puis retirer
    client_avec_notions.post(
        "/api/v2/objectifs/ob_02_rt/notions", json={"notion_id": "no_a"}
    )
    rep = client_avec_notions.delete(
        "/api/v2/objectifs/ob_02_rt/notions/no_a"
    )
    assert rep.status_code == 200
    assert rep.get_json()["notions"] == []


def test_route_retirer_notion_jamais_ajoutee_idempotent(client_avec_notions):
    """DELETE sur une association qui n'existait pas : 200, pas 404."""
    rep = client_avec_notions.delete(
        "/api/v2/objectifs/ob_02_rt/notions/no_a"
    )
    assert rep.status_code == 200


def test_route_methodes_pas_PATCH(client_avec_notions):
    """Les nouvelles routes sont bien sur les bons verbes HTTP."""
    rules = {r.endpoint: r.methods for r in client_avec_notions.application.url_map.iter_rules()}
    assert "PATCH" in rules["v2_edition.api_modifier_fin_cycle_objectif"]
    assert "POST"  in rules["v2_edition.api_ajouter_notion_objectif"]
    assert "DELETE" in rules["v2_edition.api_retirer_notion_objectif"]
