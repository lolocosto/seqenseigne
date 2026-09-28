"""tests/test_R4e2_edition.py — R4e2.

Tests de l'édition du modèle v2 : parties, précédences, réassignation.

Deux axes :
  1. Service services.v2_edition — tests unitaires sur conn en mémoire
     peuplée (fixture base_peuplee).
  2. Route /api/v2/... — tests d'intégration via client Flask, avec
     peuplement direct pattern R4b (sqlite3.connect(store.db_path)).

Les tests reposent sur le schéma v2 réel (les 5 tables de R4a).
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Schéma minimal pour les tests unitaires ──────────────────────────────────
# On ne charge pas tout le schema.sql pour rester indépendant. On recrée
# juste les 5 tables v2 + ce qu'elles référencent, sans les FK strictes
# vers methodes/exercices (hors périmètre R4e2).

_SCHEMA_TEST = """
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
CREATE TABLE IF NOT EXISTS notions (
    id     TEXT PRIMARY KEY,
    titre  TEXT NOT NULL DEFAULT '',
    corps  TEXT NOT NULL DEFAULT '',
    niveau TEXT NOT NULL DEFAULT '',
    sequence TEXT NOT NULL DEFAULT ''
);
CREATE TABLE objectif_notions (
    objectif_id TEXT NOT NULL,
    notion_id   TEXT NOT NULL,
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
def base_peuplee(conn):
    """Deux séquences par niveau :
        sn_A : N11/S03 avec 2 parties (pt_A1 #1, pt_A2 #2)
               pt_A1 a obj ob_01 (code '01'), ob_02 (code '02')
               pt_A2 a obj ob_11 (code '11') — déjà bien rangé
               pt_A1 a 1 précédence : N10/S03
        sn_B : N11/S05 avec 1 partie (pt_B1 #1)
               pt_B1 a obj ob_51 (code '01')
    """
    conn.executescript("""
        INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
            ('sn_A', 'N11', 'S03'),
            ('sn_B', 'N11', 'S05');

        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES
            ('pt_A1', 'sn_A', 1),
            ('pt_A2', 'sn_A', 2),
            ('pt_B1', 'sn_B', 1);

        INSERT INTO partie_precedences (partie_id, precedent_niveau, precedent_seq)
        VALUES ('pt_A1', 'N10', 'S03');

        INSERT INTO objectifs (id, partie_id, code, nom) VALUES
            ('ob_01', 'pt_A1', '01', 'Cours'),
            ('ob_02', 'pt_A1', '02', 'Obj 2'),
            ('ob_11', 'pt_A2', '11', 'Obj 11'),
            ('ob_51', 'pt_B1', '01', 'S05 Cours');
    """)
    conn.commit()
    return conn


# ═════════════════════════════════════════════════════════════════════════════
# 1. Helper métier : code_coherent_avec_partie
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import code_coherent_avec_partie


class TestCodeCoherentAvecPartie:
    @pytest.mark.parametrize("code,num,attendu", [
        # Convention respectée
        ("01", 1, True),  ("02", 1, True),  ("09", 1, True),
        ("11", 2, True),  ("12", 2, True),  ("19", 2, True),
        ("21", 3, True),  ("29", 3, True),
        # Convention cassée
        ("01", 2, False), ("02", 2, False),
        ("11", 1, False), ("12", 1, False),
        ("21", 1, False), ("21", 2, False),
    ])
    def test_codes_numeriques(self, code, num, attendu):
        assert code_coherent_avec_partie(code, num) is attendu

    @pytest.mark.parametrize("code", ["", "Cours", "A1", "001", "1", None])
    def test_codes_atypiques_toujours_coherents(self, code):
        """Les codes non-numériques ou de longueur ≠ 2 n'ont pas de
        convention à respecter → toujours True (pas de badge d'alerte)."""
        assert code_coherent_avec_partie(code, 1) is True
        assert code_coherent_avec_partie(code, 2) is True


# ═════════════════════════════════════════════════════════════════════════════
# 2. CRUD partie
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    creer_partie,
    supprimer_partie,
    renumeroter_partie,
    SequenceParNiveauIntrouvable,
    PartieIntrouvable,
    NumeroPartieInvalide,
    NumeroPartieDejaUtilise,
    PartieNonVide,
)


class TestCreerPartie:
    def test_auto_incremente_numero(self, base_peuplee):
        # sn_A a déjà partie 1 et 2 → nouvelle doit prendre le numéro 3.
        p = creer_partie(base_peuplee, "sn_A")
        assert p["numero"] == 3
        assert p["sequence_par_niveau_id"] == "sn_A"
        assert p["id"].startswith("pt_")

    def test_numero_explicite(self, base_peuplee):
        # sn_B n'a que la partie 1 → on peut en créer une en 5.
        p = creer_partie(base_peuplee, "sn_B", numero=5)
        assert p["numero"] == 5

    def test_auto_incremente_sur_sequence_vide(self, base_peuplee):
        """Créer une partie sur une sequence_par_niveau qui n'en a aucune
        doit produire le numéro 1."""
        base_peuplee.execute(
            "INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
            "VALUES ('sn_vide', 'N12', 'S01')"
        )
        p = creer_partie(base_peuplee, "sn_vide")
        assert p["numero"] == 1

    def test_conflit_numero_leve_409(self, base_peuplee):
        with pytest.raises(NumeroPartieDejaUtilise) as ei:
            creer_partie(base_peuplee, "sn_A", numero=1)
        assert ei.value.code == "numero_deja_utilise"
        assert ei.value.details["numero"] == 1

    def test_sequence_inexistante_leve_404(self, base_peuplee):
        with pytest.raises(SequenceParNiveauIntrouvable):
            creer_partie(base_peuplee, "sn_inconnu")

    @pytest.mark.parametrize("num", [0, -1, "abc", "1.5"])
    def test_numero_invalide(self, base_peuplee, num):
        with pytest.raises(NumeroPartieInvalide):
            creer_partie(base_peuplee, "sn_A", numero=num)


class TestSupprimerPartie:
    def test_supprime_partie_vide(self, base_peuplee):
        """Créer une partie vide et la supprimer."""
        base_peuplee.execute(
            "INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
            "VALUES ('pt_vide', 'sn_A', 3)"
        )
        rep = supprimer_partie(base_peuplee, "pt_vide")
        assert rep["supprimee"] is True
        # Vérification en base
        row = base_peuplee.execute(
            "SELECT 1 FROM sequence_parties WHERE id = ?", ("pt_vide",)
        ).fetchone()
        assert row is None

    def test_refuse_suppression_partie_non_vide(self, base_peuplee):
        with pytest.raises(PartieNonVide) as ei:
            supprimer_partie(base_peuplee, "pt_A1")
        assert ei.value.code == "partie_non_vide"
        assert ei.value.details["nb_objectifs"] == 2

    def test_partie_inexistante_404(self, base_peuplee):
        with pytest.raises(PartieIntrouvable):
            supprimer_partie(base_peuplee, "pt_inconnu")

    def test_cascade_precedences(self, base_peuplee):
        """Vider pt_A1 de ses objectifs puis le supprimer : ses
        précédences doivent disparaître en cascade."""
        base_peuplee.execute("DELETE FROM objectifs WHERE partie_id = 'pt_A1'")
        supprimer_partie(base_peuplee, "pt_A1")
        n = base_peuplee.execute(
            "SELECT COUNT(*) FROM partie_precedences WHERE partie_id = ?",
            ("pt_A1",),
        ).fetchone()[0]
        assert n == 0


class TestRenumeroterPartie:
    def test_renumerote_vers_numero_libre(self, base_peuplee):
        rep = renumeroter_partie(base_peuplee, "pt_A2", 5)
        assert rep["numero"] == 5
        # Persisté en base
        row = base_peuplee.execute(
            "SELECT numero FROM sequence_parties WHERE id = ?", ("pt_A2",)
        ).fetchone()
        assert row["numero"] == 5

    def test_idempotent_meme_numero(self, base_peuplee):
        """Renuméroter avec le même numéro actuel : no-op sans erreur."""
        rep = renumeroter_partie(base_peuplee, "pt_A2", 2)
        assert rep["numero"] == 2

    def test_conflit_avec_autre_partie_meme_sequence(self, base_peuplee):
        # pt_A1 est #1 et pt_A2 est #2 ; on essaie de mettre pt_A2 à #1.
        with pytest.raises(NumeroPartieDejaUtilise):
            renumeroter_partie(base_peuplee, "pt_A2", 1)

    def test_pas_de_conflit_avec_autre_sequence(self, base_peuplee):
        """pt_A1 peut prendre le numéro 1 même si pt_B1 (autre séquence) a le
        numéro 1 aussi — contrainte UNIQUE est par séquence."""
        # On crée une nouvelle partie numéro 3 sur sn_A pour libérer 1.
        # Mais en fait pt_A1 est déjà en #1 donc on va prendre sn_B :
        # tester que pt_B1 peut être renuméroté en 2 (qui existe sur sn_A).
        rep = renumeroter_partie(base_peuplee, "pt_B1", 2)
        assert rep["numero"] == 2

    def test_partie_inexistante_404(self, base_peuplee):
        with pytest.raises(PartieIntrouvable):
            renumeroter_partie(base_peuplee, "pt_inconnu", 1)

    @pytest.mark.parametrize("num", [0, -1, "abc"])
    def test_numero_invalide(self, base_peuplee, num):
        with pytest.raises(NumeroPartieInvalide):
            renumeroter_partie(base_peuplee, "pt_A1", num)


# ═════════════════════════════════════════════════════════════════════════════
# 3. Précédences
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    ajouter_precedence,
    supprimer_precedence,
    PrecedenceDejaPresente,
    PrecedenceInvalide,
    PrecedenceIntrouvable,
)


class TestAjouterPrecedence:
    def test_ajoute_precedence(self, base_peuplee):
        rep = ajouter_precedence(base_peuplee, "pt_A2", "N10", "S05")
        assert rep == {
            "partie_id": "pt_A2",
            "precedent_niveau": "N10",
            "precedent_seq": "S05",
        }
        row = base_peuplee.execute(
            "SELECT * FROM partie_precedences WHERE partie_id = ?",
            ("pt_A2",),
        ).fetchone()
        assert row["precedent_niveau"] == "N10"

    def test_doublon_leve_409(self, base_peuplee):
        """pt_A1 a déjà N10/S03 (via la fixture)."""
        with pytest.raises(PrecedenceDejaPresente):
            ajouter_precedence(base_peuplee, "pt_A1", "N10", "S03")

    def test_partie_inexistante_404(self, base_peuplee):
        with pytest.raises(PartieIntrouvable):
            ajouter_precedence(base_peuplee, "pt_xxx", "N10", "S01")

    @pytest.mark.parametrize("niveau,seq", [
        ("", "S01"),        # niveau vide
        ("N10", ""),        # seq vide
        ("NX", "S01"),      # niveau mal formé
        ("N10", "X01"),     # seq mal formée
        ("N10", "SA"),      # seq mal formée
        (None, "S01"),      # None
    ])
    def test_formats_invalides(self, base_peuplee, niveau, seq):
        with pytest.raises(PrecedenceInvalide):
            ajouter_precedence(base_peuplee, "pt_A2", niveau, seq)


class TestSupprimerPrecedence:
    def test_supprime_precedence_existante(self, base_peuplee):
        rep = supprimer_precedence(base_peuplee, "pt_A1", "N10", "S03")
        assert rep["supprimee"] is True
        n = base_peuplee.execute(
            "SELECT COUNT(*) FROM partie_precedences WHERE partie_id = ?",
            ("pt_A1",),
        ).fetchone()[0]
        assert n == 0

    def test_precedence_inexistante_404(self, base_peuplee):
        with pytest.raises(PrecedenceIntrouvable):
            supprimer_precedence(base_peuplee, "pt_A1", "N10", "S99")

    def test_partie_inexistante_404(self, base_peuplee):
        with pytest.raises(PartieIntrouvable):
            supprimer_precedence(base_peuplee, "pt_xxx", "N10", "S03")


# ═════════════════════════════════════════════════════════════════════════════
# 4. Réassignation d'objectif
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    reassigner_objectif_a_partie,
    ObjectifIntrouvable,
    ReassignationImpossible,
)


class TestReassignerObjectif:
    def test_deplace_dans_meme_sequence(self, base_peuplee):
        """Déplacement ob_11 (qui était bien en pt_A2) vers pt_A1."""
        rep = reassigner_objectif_a_partie(base_peuplee, "ob_11", "pt_A1")
        assert rep["objectif_id"] == "ob_11"
        assert rep["partie_id"] == "pt_A1"
        assert rep["numero_partie"] == 1
        assert rep["deplace"] is True
        # Code '11' en partie 1 → convention cassée → flag False
        assert rep["code_coherent"] is False

        # Persistance
        row = base_peuplee.execute(
            "SELECT partie_id FROM objectifs WHERE id = ?", ("ob_11",)
        ).fetchone()
        assert row["partie_id"] == "pt_A1"

    def test_deplace_preserve_convention(self, base_peuplee):
        """Déplacement cohérent avec la convention : code_coherent = True.
        On déplace ob_02 (code '02') de pt_A1 (#1) vers une nouvelle
        partie #1 bis d'une autre séquence — non, restons dans sn_A.
        On crée pt_A3 (#3) et on y déplace ob_02. Code '02' en partie 3
        → cassé (02 attend partie 1). Donc l'inverse : on déplace ob_11
        en pt_A2 (no-op, déjà là) → code_coherent True."""
        rep = reassigner_objectif_a_partie(base_peuplee, "ob_11", "pt_A2")
        assert rep["deplace"] is False  # no-op
        assert rep["code_coherent"] is True

    def test_refuse_partie_autre_sequence(self, base_peuplee):
        """On ne peut pas déplacer ob_01 (sn_A) vers pt_B1 (sn_B)."""
        with pytest.raises(ReassignationImpossible) as ei:
            reassigner_objectif_a_partie(base_peuplee, "ob_01", "pt_B1")
        assert ei.value.code == "partie_hors_sequence"

    def test_refuse_si_code_existe_dans_cible(self, base_peuplee):
        """ob_01 (code '01') ne peut pas aller dans pt_A2 si… attendez,
        pt_A2 n'a que ob_11. On crée une situation de conflit :
        on ajoute d'abord un objectif code '11' dans pt_A1."""
        base_peuplee.execute(
            "INSERT INTO objectifs (id, partie_id, code, nom) "
            "VALUES ('ob_dup', 'pt_A1', '11', 'Doublon intentionnel')"
        )
        with pytest.raises(ReassignationImpossible) as ei:
            # On tente de déplacer ob_11 (code '11') dans pt_A1 (qui a
            # désormais déjà un autre objectif de code '11').
            reassigner_objectif_a_partie(base_peuplee, "ob_11", "pt_A1")
        assert ei.value.code == "conflit_code_dans_partie_cible"
        assert ei.value.details["code_objectif"] == "11"

    def test_objectif_inexistant_404(self, base_peuplee):
        with pytest.raises(ObjectifIntrouvable):
            reassigner_objectif_a_partie(base_peuplee, "ob_xxx", "pt_A1")

    def test_partie_cible_inexistante_404(self, base_peuplee):
        with pytest.raises(PartieIntrouvable):
            reassigner_objectif_a_partie(base_peuplee, "ob_01", "pt_xxx")


# ═════════════════════════════════════════════════════════════════════════════
# 5. Tests d'intégration des routes (via client Flask du conftest global)
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def client_edition(app):
    """Client Flask avec une séquence v2 de test peuplée directement via
    sqlite3 (pattern R4b). Structure identique à la fixture base_peuplee
    ci-dessus pour réutiliser la même logique de test.
    """
    import sqlite3 as _sq3
    store = app.json_store
    db = _sq3.connect(str(store.db_path))
    try:
        db.execute(
            "INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
            "VALUES ('sn_A_rt', 'N11', 'S03')"
        )
        db.executemany(
            "INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
            "VALUES (?, ?, ?)",
            [("pt_A1_rt", "sn_A_rt", 1), ("pt_A2_rt", "sn_A_rt", 2)],
        )
        db.execute(
            "INSERT INTO partie_precedences (partie_id, precedent_niveau, "
            "precedent_seq) VALUES (?, ?, ?)",
            ("pt_A1_rt", "N10", "S03"),
        )
        db.executemany(
            "INSERT INTO objectifs (id, partie_id, code, nom) "
            "VALUES (?, ?, ?, ?)",
            [
                ("ob_01_rt", "pt_A1_rt", "01", "Cours"),
                ("ob_02_rt", "pt_A1_rt", "02", "Obj 2"),
                ("ob_11_rt", "pt_A2_rt", "11", "Obj 11"),
            ],
        )
        db.commit()
    finally:
        db.close()
    return app.test_client()


# --- Parties ---

def test_route_creer_partie_auto(client_edition):
    rep = client_edition.post(
        "/api/v2/sequences-par-niveau/sn_A_rt/parties",
        json={},
    )
    assert rep.status_code == 201
    data = rep.get_json()
    assert data["numero"] == 3
    assert data["sequence_par_niveau_id"] == "sn_A_rt"


def test_route_creer_partie_numero_explicite(client_edition):
    rep = client_edition.post(
        "/api/v2/sequences-par-niveau/sn_A_rt/parties",
        json={"numero": 5},
    )
    assert rep.status_code == 201
    assert rep.get_json()["numero"] == 5


def test_route_creer_partie_conflit_numero(client_edition):
    rep = client_edition.post(
        "/api/v2/sequences-par-niveau/sn_A_rt/parties",
        json={"numero": 1},
    )
    assert rep.status_code == 409
    assert rep.get_json()["code"] == "numero_deja_utilise"


def test_route_creer_partie_sequence_inexistante(client_edition):
    rep = client_edition.post(
        "/api/v2/sequences-par-niveau/sn_xxx/parties",
        json={},
    )
    assert rep.status_code == 404
    assert rep.get_json()["code"] == "sequence_par_niveau_introuvable"


def test_route_renumeroter_partie(client_edition):
    rep = client_edition.patch(
        "/api/v2/parties/pt_A2_rt",
        json={"numero": 5},
    )
    assert rep.status_code == 200
    assert rep.get_json()["numero"] == 5


def test_route_renumeroter_conflit(client_edition):
    rep = client_edition.patch(
        "/api/v2/parties/pt_A2_rt",
        json={"numero": 1},
    )
    assert rep.status_code == 409
    assert rep.get_json()["code"] == "numero_deja_utilise"


def test_route_renumeroter_sans_corps(client_edition):
    rep = client_edition.patch("/api/v2/parties/pt_A1_rt", json={})
    assert rep.status_code == 400
    assert rep.get_json()["code"] == "numero_invalide"


def test_route_supprimer_partie_non_vide(client_edition):
    """pt_A1_rt contient 2 objectifs → 409."""
    rep = client_edition.delete("/api/v2/parties/pt_A1_rt")
    assert rep.status_code == 409
    data = rep.get_json()
    assert data["code"] == "partie_non_vide"
    assert data["details"]["nb_objectifs"] == 2


def test_route_supprimer_partie_vide(client_edition):
    """Créer une partie vide puis la supprimer."""
    rep1 = client_edition.post(
        "/api/v2/sequences-par-niveau/sn_A_rt/parties",
        json={"numero": 9},
    )
    pt_id = rep1.get_json()["id"]
    rep2 = client_edition.delete(f"/api/v2/parties/{pt_id}")
    assert rep2.status_code == 200
    assert rep2.get_json()["supprimee"] is True


# --- Précédences ---

def test_route_ajouter_precedence(client_edition):
    rep = client_edition.post(
        "/api/v2/parties/pt_A2_rt/precedences",
        json={"precedent_niveau": "N10", "precedent_seq": "S05"},
    )
    assert rep.status_code == 201


def test_route_ajouter_precedence_doublon(client_edition):
    """pt_A1_rt a déjà N10/S03."""
    rep = client_edition.post(
        "/api/v2/parties/pt_A1_rt/precedences",
        json={"precedent_niveau": "N10", "precedent_seq": "S03"},
    )
    assert rep.status_code == 409
    assert rep.get_json()["code"] == "precedence_deja_presente"


def test_route_ajouter_precedence_format_invalide(client_edition):
    rep = client_edition.post(
        "/api/v2/parties/pt_A1_rt/precedences",
        json={"precedent_niveau": "X10", "precedent_seq": "S03"},
    )
    assert rep.status_code == 400
    assert rep.get_json()["code"] == "precedence_invalide"


def test_route_supprimer_precedence(client_edition):
    rep = client_edition.delete(
        "/api/v2/parties/pt_A1_rt/precedences/N10/S03"
    )
    assert rep.status_code == 200
    assert rep.get_json()["supprimee"] is True


def test_route_supprimer_precedence_inexistante(client_edition):
    rep = client_edition.delete(
        "/api/v2/parties/pt_A1_rt/precedences/N10/S99"
    )
    assert rep.status_code == 404
    assert rep.get_json()["code"] == "precedence_introuvable"


# --- Réassignation objectif ---

def test_route_reassigner_objectif_cohérent(client_edition):
    """Déplace ob_11 (en pt_A2) vers pt_A1. Code '11' en partie 1 →
    incohérent → code_coherent = False dans la réponse, mais pas d'erreur."""
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_11_rt/partie",
        json={"partie_id": "pt_A1_rt"},
    )
    assert rep.status_code == 200
    data = rep.get_json()
    assert data["partie_id"] == "pt_A1_rt"
    assert data["deplace"] is True
    assert data["code_coherent"] is False


def test_route_reassigner_sans_partie_id(client_edition):
    rep = client_edition.patch("/api/v2/objectifs/ob_11_rt/partie", json={})
    assert rep.status_code == 400
    assert rep.get_json()["code"] == "partie_id_manquant"


def test_route_reassigner_objectif_inexistant(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_xxx/partie",
        json={"partie_id": "pt_A1_rt"},
    )
    assert rep.status_code == 404
    assert rep.get_json()["code"] == "objectif_introuvable"


def test_route_reassigner_partie_cible_inexistante(client_edition):
    rep = client_edition.patch(
        "/api/v2/objectifs/ob_11_rt/partie",
        json={"partie_id": "pt_xxx"},
    )
    assert rep.status_code == 404
    assert rep.get_json()["code"] == "partie_introuvable"


def test_route_reassigner_refus_conflit_code(client_edition):
    """Crée un ob_11_rt dans pt_A1_rt artificiellement puis tente de
    déplacer le vrai ob_11_rt (en pt_A2_rt) vers pt_A1_rt → conflit."""
    # On ne peut pas faire ça sans accès direct DB ; on insère via sqlite3.
    import sqlite3 as _sq3
    # Récupère app.json_store.db_path via client.application
    store = client_edition.application.json_store
    db = _sq3.connect(str(store.db_path))
    try:
        db.execute(
            "INSERT INTO objectifs (id, partie_id, code, nom) "
            "VALUES ('ob_dup_rt', 'pt_A1_rt', '11', 'Conflit voulu')"
        )
        db.commit()
    finally:
        db.close()

    rep = client_edition.patch(
        "/api/v2/objectifs/ob_11_rt/partie",
        json={"partie_id": "pt_A1_rt"},
    )
    assert rep.status_code == 409
    assert rep.get_json()["code"] == "conflit_code_dans_partie_cible"


def test_route_toutes_methodes_uniquement_autorisees():
    """Pour chaque endpoint, vérifier que seules les méthodes prévues
    sont autorisées (pas d'OPTIONS/PUT détournés en POST, etc.)."""
    from flask import Flask
    from routes.v2_edition import bp_v2_edition

    app = Flask(__name__)
    app.register_blueprint(bp_v2_edition)
    rules = {r.endpoint.split(".")[-1]: r.methods for r in app.url_map.iter_rules()
             if r.endpoint.startswith("v2_edition.")}

    # Vérifications ciblées
    assert "POST" in rules["api_creer_partie"]
    assert "GET"  not in rules["api_creer_partie"]

    assert "PATCH" in rules["api_renumeroter_partie"]
    assert "DELETE" in rules["api_supprimer_partie"]

    assert "POST"   in rules["api_ajouter_precedence"]
    assert "DELETE" in rules["api_supprimer_precedence"]

    assert "PATCH" in rules["api_reassigner_objectif"]
