"""tests/test_R4e4b_edition_exos.py — R4e4b.

Tests de l'édition des exos par série d'un objectif v2 :
  - ajout (EA/F/A/E sans origin_*, R avec origin_* obligatoires)
  - retrait avec recompactage dense des ordres
  - réordonnancement strict
  - catalogues d'exos disponibles (par série et pour révision)

Pattern R4e2/R4e3 : tests unitaires sur sqlite3 en mémoire (service)
+ tests d'intégration via client Flask (routes).
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Schéma de test minimal ──────────────────────────────────────────────────
# On reproduit les tables v2 + `exercices`. Le schéma `objectif_exos`
# suit la version R4e4a (pas de colonne `num`, PK (objectif_id, serie,
# exercice_id), UNIQUE (objectif_id, serie, ordre)).

_SCHEMA_TEST = """
CREATE TABLE exercices (
    id         TEXT PRIMARY KEY,
    serie      TEXT NOT NULL,
    titre        TEXT NOT NULL DEFAULT '',
    niveau     TEXT NOT NULL DEFAULT '',
    sequence   TEXT NOT NULL DEFAULT '',
    num        INTEGER,
    serie_code TEXT NOT NULL DEFAULT '',
    fichier    TEXT NOT NULL DEFAULT '',
    etat_code  TEXT NOT NULL DEFAULT 'en_cours'  -- v0.10.4
);

CREATE TABLE sequences_par_niveau (
    id            TEXT PRIMARY KEY,
    niveau        TEXT NOT NULL,
    sequence_code TEXT NOT NULL,
    UNIQUE (niveau, sequence_code)
);
CREATE TABLE sequence_parties (
    id                     TEXT PRIMARY KEY,
    sequence_par_niveau_id TEXT NOT NULL
                           REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    numero                 INTEGER NOT NULL,
    UNIQUE (sequence_par_niveau_id, numero)
);
CREATE TABLE objectifs (
    id         TEXT PRIMARY KEY,
    partie_id  TEXT NOT NULL REFERENCES sequence_parties(id) ON DELETE CASCADE,
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

CREATE TABLE objectif_exos (
    objectif_id    TEXT NOT NULL REFERENCES objectifs(id) ON DELETE CASCADE,
    serie          TEXT NOT NULL,
    exercice_id    TEXT NOT NULL REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre          INTEGER NOT NULL DEFAULT 0,
    origin_niveau  TEXT,
    origin_seq     TEXT,
    origin_serie   TEXT,
    origin_num     INTEGER,
    PRIMARY KEY (objectif_id, serie, exercice_id),
    UNIQUE       (objectif_id, serie, ordre)
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
    """Peuplement standard :
      - Une séquence sn_A N11/S03 avec partie pt_1 et objectif ob_1 (code 01)
      - Une séquence sn_B N10/S01 (utilisée comme origin pour la série R)
      - Plusieurs exos dans N11/S03 (F, A, E, AE) et N10/S01 (F, A)
      - L'objectif ob_1 a déjà 3 exos F : ex_F1 (ordre 1), ex_F2 (ordre 2),
        ex_F3 (ordre 3), un exo A (ex_A1 ordre 1), et un exo R (ex_R_orig
        venu de N10/S01/F avec origin_num 7).
    """
    conn.executescript("""
        INSERT INTO exercices (id, serie, titre, niveau, sequence, num, serie_code, fichier) VALUES
            ('ex_F1',      'fondamental',   'F1',  'N11', 'S03', 1, 'F',  'N11S03F01.tex'),
            ('ex_F2',      'fondamental',   'F2',  'N11', 'S03', 2, 'F',  'N11S03F02.tex'),
            ('ex_F3',      'fondamental',   'F3',  'N11', 'S03', 3, 'F',  'N11S03F03.tex'),
            ('ex_F4_libre','fondamental',   'F4',  'N11', 'S03', 4, 'F',  'N11S03F04.tex'),
            ('ex_A1',      'avancé',        'A1',  'N11', 'S03', 1, 'A',  'N11S03A01.tex'),
            ('ex_A2_libre','avancé',        'A2',  'N11', 'S03', 2, 'A',  'N11S03A02.tex'),
            ('ex_E1_libre','exploration',   'E1',  'N11', 'S03', 1, 'E',  'N11S03E01.tex'),
            ('ex_EA1_libre','approche',     'AE1', 'N11', 'S03', 1, 'AE', 'N11S03AE01.tex'),
            ('ex_R_orig',  'fondamental',   'R0',  'N10', 'S01', 7, 'F',  'N10S01F07.tex'),
            ('ex_R_autre', 'avancé',        'R1',  'N10', 'S01', 2, 'A',  'N10S01A02.tex');

        INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
            ('sn_A', 'N11', 'S03');
        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES
            ('pt_1', 'sn_A', 1);
        INSERT INTO objectifs (id, partie_id, code, nom) VALUES
            ('ob_1', 'pt_1', '01', 'Objectif test');

        INSERT INTO objectif_exos
            (objectif_id, serie, exercice_id, ordre,
             origin_niveau, origin_seq, origin_serie, origin_num) VALUES
            ('ob_1', 'F', 'ex_F1', 1, NULL, NULL, NULL, 1),
            ('ob_1', 'F', 'ex_F2', 2, NULL, NULL, NULL, 2),
            ('ob_1', 'F', 'ex_F3', 3, NULL, NULL, NULL, 3),
            ('ob_1', 'A', 'ex_A1', 1, NULL, NULL, NULL, 1),
            ('ob_1', 'R', 'ex_R_orig', 1, 'N10', 'S01', 'F', 7);
    """)
    conn.commit()
    return conn


# ═════════════════════════════════════════════════════════════════════════════
# 1. ajouter_exo_a_objectif
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    ajouter_exo_a_objectif,
    SerieInvalide,
    OriginInvalide,
    ExoDejaPresent,
    ExerciceIntrouvable,
    ObjectifIntrouvable,
)


class TestAjouterExo:
    def test_ajout_normal_F(self, base):
        """Ajout d'un ex_F4_libre en série F : ordre = 4 (max+1)."""
        rep = ajouter_exo_a_objectif(base, "ob_1", "F", "ex_F4_libre")
        exos = rep["exos"]
        assert len(exos) == 4
        assert [e["exercice_id"] for e in exos] == ["ex_F1", "ex_F2", "ex_F3", "ex_F4_libre"]
        assert [e["ordre"] for e in exos] == [1, 2, 3, 4]
        # origin_* non renseignés pour série F
        nouvel_exo = exos[3]
        assert nouvel_exo["origin_niveau"] is None
        assert nouvel_exo["origin_seq"] is None
        # origin_num reprend exercices.num de l'exo
        assert nouvel_exo["origin_num"] == 4

    def test_ajout_serie_vide(self, base):
        """Ajouter un premier exo en série E (aucun exo préexistant) → ordre = 1."""
        rep = ajouter_exo_a_objectif(base, "ob_1", "E", "ex_E1_libre")
        assert len(rep["exos"]) == 1
        assert rep["exos"][0]["ordre"] == 1

    def test_ajout_serie_AE(self, base):
        """Série AE (approche) fonctionne comme F/A/E."""
        rep = ajouter_exo_a_objectif(base, "ob_1", "AE", "ex_EA1_libre")
        assert len(rep["exos"]) == 1
        assert rep["serie"] == "AE"

    def test_ajout_serie_R_refuse(self, base):
        """v0.11.2 — La série R a été retirée. Toute tentative d'ajout en
        série R doit être rejetée par la validation (SerieInvalide)."""
        with pytest.raises(SerieInvalide):
            ajouter_exo_a_objectif(
                base, "ob_1", "R", "ex_R_autre",
                origin_niveau="N10", origin_seq="S01", origin_serie="A",
            )

    def test_ajout_F_avec_origin_refuse(self, base):
        """Série F avec origin_* → 400 (pas pertinent)."""
        with pytest.raises(OriginInvalide) as ei:
            ajouter_exo_a_objectif(
                base, "ob_1", "F", "ex_F4_libre",
                origin_niveau="N10", origin_seq="S01", origin_serie="F",
            )
        assert ei.value.code == "origin_invalide"

    def test_ajout_exo_deja_present_refuse(self, base):
        """ex_F1 est déjà en F → 409."""
        with pytest.raises(ExoDejaPresent) as ei:
            ajouter_exo_a_objectif(base, "ob_1", "F", "ex_F1")
        assert ei.value.code == "exo_deja_present"

    def test_meme_exo_dans_differentes_series_autorise(self, base):
        """ex_F1 est en F. On doit pouvoir l'ajouter en EA, A ou E.
        v0.11.2 — la série R n'est plus une cible possible."""
        rep = ajouter_exo_a_objectif(base, "ob_1", "AE", "ex_F1")
        ex_ids_AE = [e["exercice_id"] for e in rep["exos"]]
        assert "ex_F1" in ex_ids_AE

    @pytest.mark.parametrize("serie_invalide", ["", "X", "f", "FA", None, 42])
    def test_serie_invalide(self, base, serie_invalide):
        with pytest.raises(SerieInvalide):
            ajouter_exo_a_objectif(base, "ob_1", serie_invalide, "ex_F4_libre")

    def test_objectif_introuvable(self, base):
        with pytest.raises(ObjectifIntrouvable):
            ajouter_exo_a_objectif(base, "ob_xxx", "F", "ex_F4_libre")

    def test_exercice_introuvable(self, base):
        with pytest.raises(ExerciceIntrouvable):
            ajouter_exo_a_objectif(base, "ob_1", "F", "ex_xxx")


# ═════════════════════════════════════════════════════════════════════════════
# 2. retirer_exo_de_objectif
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    retirer_exo_de_objectif,
    ExoIntrouvableDansObjectif,
)


class TestRetirerExo:
    def test_retrait_au_milieu_recompacte(self, base):
        """Retirer ex_F2 (ordre 2) : ex_F3 passe de 3 à 2."""
        rep = retirer_exo_de_objectif(base, "ob_1", "F", "ex_F2")
        exos = rep["exos"]
        assert len(exos) == 2
        assert [e["exercice_id"] for e in exos] == ["ex_F1", "ex_F3"]
        assert [e["ordre"] for e in exos] == [1, 2]  # dense

    def test_retrait_premier(self, base):
        """Retirer ex_F1 (ordre 1) : F2 → 1, F3 → 2."""
        rep = retirer_exo_de_objectif(base, "ob_1", "F", "ex_F1")
        exos = rep["exos"]
        assert [e["exercice_id"] for e in exos] == ["ex_F2", "ex_F3"]
        assert [e["ordre"] for e in exos] == [1, 2]

    def test_retrait_dernier(self, base):
        """Retirer ex_F3 (dernier) : les autres restent à 1, 2."""
        rep = retirer_exo_de_objectif(base, "ob_1", "F", "ex_F3")
        exos = rep["exos"]
        assert [e["exercice_id"] for e in exos] == ["ex_F1", "ex_F2"]
        assert [e["ordre"] for e in exos] == [1, 2]

    def test_retrait_dernier_exo_de_serie(self, base):
        """Retirer ex_A1 (seul exo A) → liste vide."""
        rep = retirer_exo_de_objectif(base, "ob_1", "A", "ex_A1")
        assert rep["exos"] == []

    def test_retrait_exo_absent_de_serie_F(self, base):
        """ex_A1 est en A, pas en F → 404."""
        with pytest.raises(ExoIntrouvableDansObjectif):
            retirer_exo_de_objectif(base, "ob_1", "F", "ex_A1")

    def test_retrait_exo_jamais_present(self, base):
        with pytest.raises(ExoIntrouvableDansObjectif):
            retirer_exo_de_objectif(base, "ob_1", "F", "ex_F4_libre")

    def test_retrait_objectif_inexistant(self, base):
        with pytest.raises(ObjectifIntrouvable):
            retirer_exo_de_objectif(base, "ob_xxx", "F", "ex_F1")

    def test_retrait_autres_series_intactes(self, base):
        """Retirer ex_F2 ne touche pas aux séries A et R."""
        retirer_exo_de_objectif(base, "ob_1", "F", "ex_F2")
        n_A = base.execute(
            "SELECT COUNT(*) FROM objectif_exos WHERE objectif_id='ob_1' AND serie='A'"
        ).fetchone()[0]
        n_R = base.execute(
            "SELECT COUNT(*) FROM objectif_exos WHERE objectif_id='ob_1' AND serie='R'"
        ).fetchone()[0]
        assert n_A == 1
        assert n_R == 1


# ═════════════════════════════════════════════════════════════════════════════
# 3. reordonner_exos
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import reordonner_exos, ReordonnancementInvalide


class TestReordonnerExos:
    def test_inversion_simple(self, base):
        """Échanger F1 et F2."""
        rep = reordonner_exos(base, "ob_1", "F", ["ex_F2", "ex_F1", "ex_F3"])
        assert [e["exercice_id"] for e in rep["exos"]] == ["ex_F2", "ex_F1", "ex_F3"]
        assert [e["ordre"] for e in rep["exos"]] == [1, 2, 3]

    def test_renversement_complet(self, base):
        rep = reordonner_exos(base, "ob_1", "F", ["ex_F3", "ex_F2", "ex_F1"])
        assert [e["exercice_id"] for e in rep["exos"]] == ["ex_F3", "ex_F2", "ex_F1"]

    def test_ordre_identique_noop(self, base):
        """Liste identique à l'existant → pas d'erreur, ordres inchangés."""
        rep = reordonner_exos(base, "ob_1", "F", ["ex_F1", "ex_F2", "ex_F3"])
        assert [e["ordre"] for e in rep["exos"]] == [1, 2, 3]

    def test_liste_incomplete_refuse(self, base):
        with pytest.raises(ReordonnancementInvalide) as ei:
            reordonner_exos(base, "ob_1", "F", ["ex_F1", "ex_F2"])
        assert ei.value.code == "reordonnancement_invalide"
        assert "ex_F3" in ei.value.details["manquants"]

    def test_liste_avec_exo_inconnu_refuse(self, base):
        with pytest.raises(ReordonnancementInvalide) as ei:
            reordonner_exos(
                base, "ob_1", "F",
                ["ex_F1", "ex_F2", "ex_F3", "ex_F4_libre"],
            )
        assert "ex_F4_libre" in ei.value.details["inconnus"]

    def test_liste_avec_doublon_refuse(self, base):
        with pytest.raises(ReordonnancementInvalide):
            reordonner_exos(base, "ob_1", "F", ["ex_F1", "ex_F1", "ex_F3"])

    def test_liste_non_liste_refuse(self, base):
        with pytest.raises(ReordonnancementInvalide):
            reordonner_exos(base, "ob_1", "F", "ex_F1,ex_F2")

    def test_liste_vide_serie_non_vide_refuse(self, base):
        """Passer [] alors que F contient 3 exos → refusé."""
        with pytest.raises(ReordonnancementInvalide):
            reordonner_exos(base, "ob_1", "F", [])

    def test_liste_vide_serie_vide_ok(self, base):
        """Passer [] sur une série qui est vide → no-op silencieux."""
        rep = reordonner_exos(base, "ob_1", "E", [])
        assert rep["exos"] == []

    def test_ne_touche_pas_aux_autres_series(self, base):
        """Réordonner F ne doit pas toucher A ou R."""
        reordonner_exos(base, "ob_1", "F", ["ex_F3", "ex_F2", "ex_F1"])
        rep_A = base.execute(
            "SELECT exercice_id, ordre FROM objectif_exos "
            "WHERE objectif_id='ob_1' AND serie='A'"
        ).fetchall()
        assert [(r["exercice_id"], r["ordre"]) for r in rep_A] == [("ex_A1", 1)]

    def test_objectif_inexistant(self, base):
        with pytest.raises(ObjectifIntrouvable):
            reordonner_exos(base, "ob_xxx", "F", ["ex_F1"])


# ═════════════════════════════════════════════════════════════════════════════
# 4. lister_exos_disponibles (séries EA/F/A/E)
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import lister_exos_disponibles


class TestListerExosDisponibles:
    def test_F_filtre_par_serie_code(self, base):
        """Liste F de N11/S03 : tous les exos serie_code='F' NON déjà dans ob_1/F."""
        exos = lister_exos_disponibles(base, "N11", "S03", "F", objectif_id="ob_1")
        ids = [e["id"] for e in exos]
        # ex_F1/F2/F3 sont déjà dans ob_1/F → exclus
        # ex_F4_libre est dispo
        assert "ex_F4_libre" in ids
        assert "ex_F1" not in ids
        # ex_A1, ex_E1_libre, etc. : serie_code ≠ F → exclus
        assert "ex_A1" not in ids
        assert "ex_E1_libre" not in ids

    def test_F_sans_objectif_retourne_tous(self, base):
        """Sans objectif_id, on retourne tous les exos compatibles."""
        exos = lister_exos_disponibles(base, "N11", "S03", "F")
        ids = {e["id"] for e in exos}
        assert ids == {"ex_F1", "ex_F2", "ex_F3", "ex_F4_libre"}

    def test_AE_serie_code_AE(self, base):
        """Série AE (approche) : filtre serie_code='AE' dans exercices."""
        exos = lister_exos_disponibles(base, "N11", "S03", "AE")
        assert [e["id"] for e in exos] == ["ex_EA1_libre"]

    def test_A_filtre_correct(self, base):
        exos = lister_exos_disponibles(base, "N11", "S03", "A", objectif_id="ob_1")
        # ex_A1 est déjà dans ob_1/A → exclu ; ex_A2_libre dispo
        ids = [e["id"] for e in exos]
        assert ids == ["ex_A2_libre"]

    def test_R_rejetee(self, base):
        """v0.11.2 — La série R a été retirée. Tout appel avec serie='R'
        est désormais rejeté par _valider_serie (SerieInvalide). Avant,
        la fonction retournait silencieusement [] pour 'R'."""
        with pytest.raises(SerieInvalide):
            lister_exos_disponibles(base, "N11", "S03", "R")

    def test_serie_invalide(self, base):
        with pytest.raises(SerieInvalide):
            lister_exos_disponibles(base, "N11", "S03", "X")

    def test_niveau_sequence_inconnus(self, base):
        """Pas d'erreur, juste liste vide."""
        exos = lister_exos_disponibles(base, "N99", "S99", "F")
        assert exos == []

    def test_metadonnees_retournees(self, base):
        """Vérifie les champs retournés pour chaque exo."""
        exos = lister_exos_disponibles(base, "N11", "S03", "F")
        assert exos
        e0 = exos[0]
        # v0.10.4 — etat_code ajouté pour le badge dans la sidebar
        assert set(e0.keys()) == {"id", "titre", "fichier", "niveau",
                                   "sequence", "num", "serie_code",
                                   "etat_code"}


# ═════════════════════════════════════════════════════════════════════════════
# 5. lister_exos_disponibles_pour_revision (série R)
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import lister_exos_disponibles_pour_revision


class TestListerExosPourRevision:
    def test_retourne_tous_les_exos_de_origin(self, base):
        """(N10, S01) → ex_R_orig (F) + ex_R_autre (A)."""
        exos = lister_exos_disponibles_pour_revision(base, "N10", "S01")
        ids = {e["id"] for e in exos}
        assert ids == {"ex_R_orig", "ex_R_autre"}

    def test_tri_par_serie_code(self, base):
        """ex_R_autre (A) doit venir avant ex_R_orig (F) alphabétiquement."""
        exos = lister_exos_disponibles_pour_revision(base, "N10", "S01")
        serie_codes = [e["serie_code"] for e in exos]
        assert serie_codes == sorted(serie_codes)

    def test_origin_inconnu_retourne_vide(self, base):
        exos = lister_exos_disponibles_pour_revision(base, "N99", "S99")
        assert exos == []

    def test_ne_filtre_pas_les_exos_deja_utilises(self, base):
        """ex_R_orig est déjà en série R de ob_1. La fonction le retourne
        quand même (le filtrage se fait côté UI appelante)."""
        exos = lister_exos_disponibles_pour_revision(base, "N10", "S01")
        ids = {e["id"] for e in exos}
        assert "ex_R_orig" in ids


# ═════════════════════════════════════════════════════════════════════════════
# 6. Tests d'intégration des routes
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def client_exos(app):
    """Peuple la base via SqliteStore (schema.sql complet) + seed R4e4b."""
    import sqlite3 as _sq3
    store = app.json_store
    db = _sq3.connect(str(store.db_path))
    try:
        db.execute("PRAGMA foreign_keys = ON")

        # Colonnes `exercices` lues dynamiquement (le schéma Laurent a
        # des colonnes supplémentaires qu'on doit renseigner)
        ex_cols = {r[1] for r in db.execute("PRAGMA table_info(exercices)").fetchall()}

        def insert_exercice(exid, serie_long, serie_code, titre, num):
            champs = ["id"]
            vals = [exid]
            mapping = {
                "serie":      serie_long, "serie_code": serie_code,
                "titre":      titre,      "niveau":     "N11",
                "sequence":   "S03",      "fichier":    f"{exid}.tex",
                "num":        num,
            }
            for c, v in mapping.items():
                if c in ex_cols:
                    champs.append(c)
                    vals.append(v)
            db.execute(
                f"INSERT INTO exercices ({', '.join(champs)}) "
                f"VALUES ({', '.join('?' * len(champs))})",
                vals,
            )

        insert_exercice("ex_F1_rt", "fondamental", "F",  "F1", 1)
        insert_exercice("ex_F2_rt", "fondamental", "F",  "F2", 2)
        insert_exercice("ex_F4_rt", "fondamental", "F",  "F4", 4)
        insert_exercice("ex_A1_rt", "avancé",      "A",  "A1", 1)

        # Un exo en N10/S01 pour les révisions
        db.execute(
            f"INSERT INTO exercices "
            f"({', '.join(c for c in ['id','serie','serie_code','titre','niveau','sequence','fichier','num'] if c in ex_cols)}) "
            f"VALUES ({', '.join('?' * len([c for c in ['id','serie','serie_code','titre','niveau','sequence','fichier','num'] if c in ex_cols]))})",
            [v for c, v in [("id","ex_R_rt"),("serie","fondamental"),("serie_code","F"),
                             ("titre","R0"),("niveau","N10"),("sequence","S01"),
                             ("fichier","N10S01F07.tex"),("num",7)]
             if c in ex_cols],
        )

        db.execute(
            "INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
            "VALUES ('sn_A_rt', 'N11', 'S03')"
        )
        db.execute(
            "INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
            "VALUES ('pt_1_rt', 'sn_A_rt', 1)"
        )
        db.execute(
            "INSERT INTO objectifs (id, partie_id, code, nom) "
            "VALUES ('ob_1_rt', 'pt_1_rt', '01', 'Test')"
        )
        db.executemany(
            "INSERT INTO objectif_exos "
            "(objectif_id, serie, exercice_id, ordre, "
            " origin_niveau, origin_seq, origin_serie, origin_num) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("ob_1_rt", "F", "ex_F1_rt", 1, None, None, None, 1),
                ("ob_1_rt", "F", "ex_F2_rt", 2, None, None, None, 2),
                ("ob_1_rt", "A", "ex_A1_rt", 1, None, None, None, 1),
            ],
        )
        db.commit()
    finally:
        db.close()
    return app.test_client()


def test_route_ajouter_exo_F(client_exos):
    rep = client_exos.post(
        "/api/v2/objectifs/ob_1_rt/exos",
        json={"serie": "F", "exercice_id": "ex_F4_rt"},
    )
    assert rep.status_code == 201
    data = rep.get_json()
    assert data["serie"] == "F"
    assert len(data["exos"]) == 3
    assert [e["ordre"] for e in data["exos"]] == [1, 2, 3]


def test_route_ajouter_exo_serie_R_refuse(client_exos):
    """v0.11.2 — Tout POST avec serie='R' doit être rejeté par la route
    (status 400, code 'serie_invalide')."""
    rep = client_exos.post(
        "/api/v2/objectifs/ob_1_rt/exos",
        json={
            "serie": "R", "exercice_id": "ex_R_rt",
            "origin_niveau": "N10", "origin_seq": "S01", "origin_serie": "F",
        },
    )
    assert rep.status_code == 400
    assert rep.get_json()["code"] == "serie_invalide"


def test_route_ajouter_exo_F_avec_origin_400(client_exos):
    rep = client_exos.post(
        "/api/v2/objectifs/ob_1_rt/exos",
        json={"serie": "F", "exercice_id": "ex_F4_rt",
              "origin_niveau": "N10", "origin_seq": "S01", "origin_serie": "F"},
    )
    assert rep.status_code == 400


def test_route_ajouter_exo_deja_present_409(client_exos):
    rep = client_exos.post(
        "/api/v2/objectifs/ob_1_rt/exos",
        json={"serie": "F", "exercice_id": "ex_F1_rt"},
    )
    assert rep.status_code == 409
    assert rep.get_json()["code"] == "exo_deja_present"


def test_route_ajouter_exercice_inexistant_404(client_exos):
    rep = client_exos.post(
        "/api/v2/objectifs/ob_1_rt/exos",
        json={"serie": "F", "exercice_id": "ex_xxx"},
    )
    assert rep.status_code == 404


def test_route_ajouter_sans_exercice_id_400(client_exos):
    rep = client_exos.post(
        "/api/v2/objectifs/ob_1_rt/exos",
        json={"serie": "F"},
    )
    assert rep.status_code == 400


def test_route_retirer_exo(client_exos):
    rep = client_exos.delete(
        "/api/v2/objectifs/ob_1_rt/exos/F/ex_F1_rt",
    )
    assert rep.status_code == 200
    data = rep.get_json()
    assert len(data["exos"]) == 1
    # Recompactage : ex_F2 passe en ordre 1
    assert data["exos"][0]["exercice_id"] == "ex_F2_rt"
    assert data["exos"][0]["ordre"] == 1


def test_route_retirer_exo_absent_404(client_exos):
    rep = client_exos.delete(
        "/api/v2/objectifs/ob_1_rt/exos/F/ex_xxx",
    )
    assert rep.status_code == 404


def test_route_reordonner(client_exos):
    rep = client_exos.patch(
        "/api/v2/objectifs/ob_1_rt/exos/F/ordre",
        json={"exercice_ids": ["ex_F2_rt", "ex_F1_rt"]},
    )
    assert rep.status_code == 200
    data = rep.get_json()
    assert [e["exercice_id"] for e in data["exos"]] == ["ex_F2_rt", "ex_F1_rt"]


def test_route_reordonner_liste_invalide(client_exos):
    rep = client_exos.patch(
        "/api/v2/objectifs/ob_1_rt/exos/F/ordre",
        json={"exercice_ids": ["ex_F1_rt"]},
    )
    assert rep.status_code == 400


def test_route_reordonner_sans_champ(client_exos):
    rep = client_exos.patch(
        "/api/v2/objectifs/ob_1_rt/exos/F/ordre",
        json={},
    )
    assert rep.status_code == 400


def test_route_exos_disponibles(client_exos):
    rep = client_exos.get(
        "/api/v2/exos-disponibles"
        "?niveau=N11&sequence=S03&serie_cible=F&objectif_id=ob_1_rt"
    )
    assert rep.status_code == 200
    data = rep.get_json()
    ids = [e["id"] for e in data["exos"]]
    assert "ex_F4_rt" in ids
    assert "ex_F1_rt" not in ids  # déjà dans ob_1_rt


def test_route_exos_disponibles_params_manquants(client_exos):
    rep = client_exos.get("/api/v2/exos-disponibles?niveau=N11")
    assert rep.status_code == 400


def test_route_exos_disponibles_serie_invalide(client_exos):
    rep = client_exos.get(
        "/api/v2/exos-disponibles?niveau=N11&sequence=S03&serie_cible=X"
    )
    assert rep.status_code == 400


def test_route_exos_revision(client_exos):
    rep = client_exos.get(
        "/api/v2/exos-disponibles-revision?niveau=N10&sequence=S01"
    )
    assert rep.status_code == 200
    ids = [e["id"] for e in rep.get_json()["exos"]]
    assert "ex_R_rt" in ids


def test_route_exos_revision_params_manquants(client_exos):
    rep = client_exos.get("/api/v2/exos-disponibles-revision")
    assert rep.status_code == 400
