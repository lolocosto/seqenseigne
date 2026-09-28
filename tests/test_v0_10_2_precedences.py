"""tests/test_v0_10_2_precedences.py — v0.10.2.

Tests pour :
  - Précédences au niveau séquence-niveau (lister/ajouter/retirer)
  - Validation backend stricte des exos R/EA selon la provenance
  - Auto-import des cycles depuis CSV au démarrage
"""

from __future__ import annotations
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Schéma minimal pour les tests unitaires ──────────────────────────────────

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
CREATE TABLE exercices (
    id           TEXT PRIMARY KEY,
    serie        TEXT NOT NULL DEFAULT '',
    titre          TEXT NOT NULL DEFAULT '',
    fichier      TEXT NOT NULL DEFAULT '',
    niveau       TEXT NOT NULL DEFAULT '',
    sequence     TEXT NOT NULL DEFAULT '',
    num          INTEGER,
    serie_code   TEXT NOT NULL DEFAULT '',
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE TABLE objectif_exos (
    objectif_id    TEXT NOT NULL,
    serie          TEXT NOT NULL,
    exercice_id    TEXT NOT NULL,
    ordre          INTEGER NOT NULL DEFAULT 0,
    origin_niveau  TEXT, origin_seq TEXT,
    origin_serie   TEXT, origin_num INTEGER,
    PRIMARY KEY (objectif_id, serie, exercice_id),
    UNIQUE (objectif_id, serie, ordre)
);
CREATE TABLE partie_exos_revision_approche (
    partie_id      TEXT NOT NULL
                   REFERENCES sequence_parties(id) ON DELETE CASCADE,
    type           TEXT NOT NULL,
    exercice_id    TEXT NOT NULL
                   REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre          INTEGER NOT NULL DEFAULT 0,
    origin_niveau  TEXT, origin_seq TEXT,
    origin_serie   TEXT, origin_num INTEGER,
    PRIMARY KEY (partie_id, type, exercice_id),
    UNIQUE (partie_id, type, ordre)
);
CREATE TABLE sequence_par_niveau_precedences (
    sequence_par_niveau_id TEXT NOT NULL
                           REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    precedent_niveau       TEXT NOT NULL,
    precedent_seq          TEXT NOT NULL,
    ordre                  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (sequence_par_niveau_id, precedent_niveau, precedent_seq)
);
CREATE TABLE ui_etat_atelier_sequence (
    sequence_par_niveau_id TEXT PRIMARY KEY,
    objectif_ouvert_id     TEXT,
    derniere_maj           TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE notions (
    id TEXT PRIMARY KEY, titre TEXT, corps TEXT,
    niveau TEXT, sequence TEXT,
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE TABLE objectif_notions (
    objectif_id TEXT, notion_id TEXT, ordre INTEGER,
    PRIMARY KEY (objectif_id, notion_id)
);
CREATE TABLE partie_precedences (
    partie_id TEXT, precedent_niveau TEXT, precedent_seq TEXT,
    PRIMARY KEY (partie_id, precedent_niveau, precedent_seq)
);
CREATE TABLE methodes (
    id TEXT PRIMARY KEY, titre TEXT, niveau TEXT, sequence TEXT, fichier TEXT,
    etat_code TEXT NOT NULL DEFAULT 'en_cours'
);
CREATE TABLE themes (
    id TEXT PRIMARY KEY, code TEXT, nom TEXT, code_couleur TEXT
);
CREATE TABLE sequences_du_cycle (
    id TEXT PRIMARY KEY, code TEXT, nom TEXT, numero INTEGER, theme_id TEXT
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
    """Mini-base pour tests v0.10.2 :
      sn_n11 : N11/S03, 1 partie pt_n11
      sn_n10 : N10/S03, 1 partie (la "n-1" canonique)
      sn_solo: N12/S99 (séquence isolée pour tests précédence vide)

      Exercices :
        ex_ea1 : N11/S03 série EA → utilisable en EA de pt_n11
        ex_ea_autre : N11/S04 série EA → PAS utilisable (autre séquence)
        ex_a_n10 : N10/S03 série A → utilisable en R *si* N10/S03 est précédence
        ex_e_n10 : N10/S03 série E → PAS utilisable en R (mauvaise série)
        ex_a_n10_autre : N10/S05 série A → PAS utilisable en R (hors précédences)
    """
    conn.executescript("""
        INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES
            ('sn_n11', 'N11', 'S03'),
            ('sn_n10', 'N10', 'S03'),
            ('sn_solo', 'N12', 'S99');
        INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES
            ('pt_n11', 'sn_n11', 1),
            ('pt_n10', 'sn_n10', 1);
        INSERT INTO exercices
            (id, serie, titre, fichier, niveau, sequence, num, serie_code) VALUES
            ('ex_ea1',         'approche',   'EA1',      'ea1.tex', 'N11', 'S03', 1, 'AE'),
            ('ex_ea_autre',    'approche',   'EA autre', 'ea2.tex', 'N11', 'S04', 1, 'AE'),
            ('ex_a_n10',       'avancee',    'A n10',    'a1.tex',  'N10', 'S03', 1, 'A'),
            ('ex_e_n10',       'exploration','E n10',    'e1.tex',  'N10', 'S03', 1, 'E'),
            ('ex_a_n10_autre', 'avancee',    'A n10 a',  'a2.tex',  'N10', 'S05', 1, 'A');
    """)
    conn.commit()
    return conn


# ═════════════════════════════════════════════════════════════════════════════
# 1. lister / ajouter / retirer précédence séquence
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    lister_precedences_sequence,
    ajouter_precedence_sequence,
    retirer_precedence_sequence,
    SequenceParNiveauIntrouvable,
    PrecedenceInvalide,
    PrecedenceSeqDejaPresente,
    PrecedenceSeqIntrouvable,
)


class TestPrecedencesSequence:
    def test_lister_vide(self, base):
        assert lister_precedences_sequence(base, "sn_n11") == []

    def test_ajouter_simple(self, base):
        rep = ajouter_precedence_sequence(base, "sn_n11", "N10", "S03")
        assert rep == [
            {"precedent_niveau": "N10", "precedent_seq": "S03", "ordre": 1},
        ]

    def test_ajouter_plusieurs_ordre(self, base):
        ajouter_precedence_sequence(base, "sn_n11", "N10", "S03")
        rep = ajouter_precedence_sequence(base, "sn_n11", "C03", "S05")
        assert [(p["precedent_niveau"], p["precedent_seq"], p["ordre"])
                for p in rep] == [
            ("N10", "S03", 1),
            ("C03", "S05", 2),
        ]

    def test_doublon_409(self, base):
        ajouter_precedence_sequence(base, "sn_n11", "N10", "S03")
        with pytest.raises(PrecedenceSeqDejaPresente):
            ajouter_precedence_sequence(base, "sn_n11", "N10", "S03")

    def test_circulaire_400(self, base):
        with pytest.raises(PrecedenceInvalide):
            ajouter_precedence_sequence(base, "sn_n11", "N11", "S03")

    # ── v0.10.3 — Règle (b) : niveau ≤ niveau courant ─────────────────────

    def test_niveau_meme_autre_sequence_OK(self, base):
        """Règle (b) : N12/S03 → N12/S05 autorisé (même niveau, autre seq)."""
        # On utilise sn_solo (N12/S99). Précédence vers N12/S03 : OK.
        rep = ajouter_precedence_sequence(base, "sn_solo", "N12", "S03")
        assert len(rep) == 1
        assert rep[0]["precedent_niveau"] == "N12"

    def test_niveau_strictement_inferieur_OK(self, base):
        """Règle (b) : N11/S03 → N10/S03 autorisé."""
        rep = ajouter_precedence_sequence(base, "sn_n11", "N10", "S03")
        assert len(rep) == 1

    def test_niveau_superieur_refuse(self, base):
        """Règle (b) : N11/S03 → N12/S03 refusé (niveau supérieur)."""
        with pytest.raises(PrecedenceInvalide) as ei:
            ajouter_precedence_sequence(base, "sn_n11", "N12", "S03")
        assert "supérieur" in str(ei.value).lower() or "supérieur" in str(ei.value)

    def test_niveau_superieur_n10_n11_refuse(self, base):
        """Règle (b) : N10/S03 → N11/S03 refusé."""
        with pytest.raises(PrecedenceInvalide):
            ajouter_precedence_sequence(base, "sn_n10", "N11", "S03")

    def test_niveau_superieur_n10_n12_refuse(self, base):
        """Règle (b) : N10/S03 → N12/S03 refusé."""
        with pytest.raises(PrecedenceInvalide):
            ajouter_precedence_sequence(base, "sn_n10", "N12", "S03")

    def test_cycle_virtuel_C_toujours_autorise(self, base):
        """Règle (b) : C03/* (préfixe non-N) toujours autorisé partout."""
        # Sur N10 : C03 OK
        rep1 = ajouter_precedence_sequence(base, "sn_n10", "C03", "S03")
        assert len(rep1) == 1
        # Sur N11 : C03 OK
        rep2 = ajouter_precedence_sequence(base, "sn_n11", "C03", "S05")
        assert len(rep2) == 1

    def test_champs_vides_400(self, base):
        with pytest.raises(PrecedenceInvalide):
            ajouter_precedence_sequence(base, "sn_n11", "", "S03")
        with pytest.raises(PrecedenceInvalide):
            ajouter_precedence_sequence(base, "sn_n11", "N10", "")

    def test_sequence_inexistante(self, base):
        with pytest.raises(SequenceParNiveauIntrouvable):
            ajouter_precedence_sequence(base, "sn_inc", "N10", "S03")

    def test_retirer(self, base):
        ajouter_precedence_sequence(base, "sn_n11", "N10", "S03")
        ajouter_precedence_sequence(base, "sn_n11", "C03", "S05")
        rep = retirer_precedence_sequence(base, "sn_n11", "N10", "S03")
        assert rep == [
            {"precedent_niveau": "C03", "precedent_seq": "S05", "ordre": 1},
        ]

    def test_retirer_recompacte(self, base):
        ajouter_precedence_sequence(base, "sn_n11", "N10", "S03")
        ajouter_precedence_sequence(base, "sn_n11", "C03", "S05")
        ajouter_precedence_sequence(base, "sn_n11", "C03", "S08")
        # Retirer celle du milieu → ordres 1,2 pour les 2 restantes
        rep = retirer_precedence_sequence(base, "sn_n11", "C03", "S05")
        assert [p["ordre"] for p in rep] == [1, 2]
        # Ordre stable : N10/S03 toujours avant C03/S08
        assert rep[0]["precedent_niveau"] == "N10"
        assert rep[1]["precedent_seq"] == "S08"

    def test_retirer_inexistante_404(self, base):
        with pytest.raises(PrecedenceSeqIntrouvable):
            retirer_precedence_sequence(base, "sn_n11", "N10", "S03")

    def test_indep_entre_sequences(self, base):
        ajouter_precedence_sequence(base, "sn_n11", "N10", "S03")
        assert lister_precedences_sequence(base, "sn_n10") == []
        assert lister_precedences_sequence(base, "sn_solo") == []


# ═════════════════════════════════════════════════════════════════════════════
# 2. Validation backend stricte des exos R/EA
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_edition import (
    ajouter_exo_revision_approche,
    ExoApprocheHorsSequence,
    ExoApprocheMauvaiseSerie,
    ExoRevisionHorsPrecedences,
    ExoRevisionMauvaiseSerie,
)


class TestValidationApproche:
    def test_ea_valide(self, base):
        rep = ajouter_exo_revision_approche(base, "pt_n11", "EA", "ex_ea1")
        assert len(rep["EA"]) == 1
        # Origin remplie automatiquement depuis l'exo
        assert rep["EA"][0]["origin_niveau"] == "N11"
        assert rep["EA"][0]["origin_seq"] == "S03"
        assert rep["EA"][0]["origin_serie"] == "AE"

    def test_ea_hors_sequence(self, base):
        with pytest.raises(ExoApprocheHorsSequence):
            ajouter_exo_revision_approche(base, "pt_n11", "EA", "ex_ea_autre")

    def test_ea_mauvaise_serie(self, base):
        # ex_a_n10_autre : N10/S05 série A → mauvaise série pour EA + hors séquence
        # Mais on teste la mauvaise série en premier (ordre des checks).
        # En pratique ici le check "hors séquence" passe en premier ;
        # créons un exo qui est dans la bonne séquence mais mauvaise série
        base.execute(
            "INSERT INTO exercices (id, serie, titre, fichier, niveau, sequence, "
            "num, serie_code) VALUES "
            "('ex_f_n11', 'fond', 'F1', 'f.tex', 'N11', 'S03', 1, 'F')"
        )
        with pytest.raises(ExoApprocheMauvaiseSerie):
            ajouter_exo_revision_approche(base, "pt_n11", "EA", "ex_f_n11")


class TestValidationRevision:
    def test_r_sans_precedence_refuse(self, base):
        """Pas de précédence déclarée → tout R refusé."""
        with pytest.raises(ExoRevisionHorsPrecedences):
            ajouter_exo_revision_approche(base, "pt_n11", "R", "ex_a_n10")

    def test_r_valide_avec_precedence(self, base):
        ajouter_precedence_sequence(base, "sn_n11", "N10", "S03")
        rep = ajouter_exo_revision_approche(base, "pt_n11", "R", "ex_a_n10")
        assert len(rep["R"]) == 1
        assert rep["R"][0]["origin_niveau"] == "N10"
        assert rep["R"][0]["origin_seq"] == "S03"
        assert rep["R"][0]["origin_serie"] == "A"

    def test_r_mauvaise_serie(self, base):
        ajouter_precedence_sequence(base, "sn_n11", "N10", "S03")
        with pytest.raises(ExoRevisionMauvaiseSerie):
            # ex_e_n10 est série E, pas A
            ajouter_exo_revision_approche(base, "pt_n11", "R", "ex_e_n10")

    def test_r_hors_precedences(self, base):
        ajouter_precedence_sequence(base, "sn_n11", "N10", "S03")
        # ex_a_n10_autre est N10/S05 série A : bonne série mais pas dans
        # les précédences (qui ne contiennent que N10/S03).
        with pytest.raises(ExoRevisionHorsPrecedences):
            ajouter_exo_revision_approche(
                base, "pt_n11", "R", "ex_a_n10_autre",
            )

    def test_r_plusieurs_precedences(self, base):
        ajouter_precedence_sequence(base, "sn_n11", "N10", "S03")
        ajouter_precedence_sequence(base, "sn_n11", "N10", "S05")
        # Maintenant ex_a_n10 (N10/S03) ET ex_a_n10_autre (N10/S05) acceptés
        rep1 = ajouter_exo_revision_approche(base, "pt_n11", "R", "ex_a_n10")
        rep2 = ajouter_exo_revision_approche(
            base, "pt_n11", "R", "ex_a_n10_autre",
        )
        assert len(rep2["R"]) == 2


# ═════════════════════════════════════════════════════════════════════════════
# 3. Auto-import des cycles
# ═════════════════════════════════════════════════════════════════════════════

from services.cycle_auto_import import auto_importer_cycles


class TestAutoImportCycles:
    def _setup_data_dir(self, td: Path, csv_files: dict) -> Path:
        d = td / "data"
        d.mkdir()
        for name, content in csv_files.items():
            (d / name).write_text(content, encoding="utf-8")
        return d

    def _init_minimal_db(self, db_path: Path):
        """Crée le DDL minimal nécessaire à auto_importer_cycles."""
        with sqlite3.connect(db_path) as c:
            c.executescript("""
                CREATE TABLE cycles (
                    code TEXT PRIMARY KEY, nom TEXT, description TEXT
                );
                CREATE TABLE themes (
                    id TEXT PRIMARY KEY,
                    cycle_code TEXT REFERENCES cycles(code) ON DELETE CASCADE,
                    code TEXT, nom TEXT, code_couleur TEXT, description TEXT,
                    ordre INTEGER
                );
                CREATE TABLE sequences_du_cycle (
                    id TEXT PRIMARY KEY,
                    cycle_code TEXT REFERENCES cycles(code) ON DELETE CASCADE,
                    code TEXT, nom TEXT, numero INTEGER, theme_id TEXT
                );
            """)

    def test_csv_absents_pas_d_import(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        db = d / "test.db"
        self._init_minimal_db(db)
        rep = auto_importer_cycles(d, db)
        assert rep["C03"]["importe"] is False
        assert rep["C03"]["raison"] == "csv_absents"
        assert rep["C04"]["importe"] is False

    def test_import_c03_simple(self, tmp_path):
        d = self._setup_data_dir(tmp_path, {
            "C03_themes.csv":
                "Code,Nom,CodeCouleur,Description\n"
                "A,Nombres,nombres,Foo\n"
                "B,Géo,geometrie,Bar\n",
            "C03_sequences.csv":
                "Code,Numero,Nom,Theme\n"
                "S01,1,Nombres entiers,A\n"
                "S02,2,Fractions,A\n",
        })
        db = d / "test.db"
        self._init_minimal_db(db)
        rep = auto_importer_cycles(d, db)
        assert rep["C03"]["importe"] is True
        assert rep["C03"]["rapport"]["themes"]["crees"] == 2
        assert rep["C03"]["rapport"]["sequences"]["crees"] == 2

    def test_idempotence(self, tmp_path):
        d = self._setup_data_dir(tmp_path, {
            "C03_themes.csv": "Code,Nom,CodeCouleur,Description\nA,N,n,\n",
            "C03_sequences.csv": "Code,Numero,Nom,Theme\nS01,1,X,A\n",
        })
        db = d / "test.db"
        self._init_minimal_db(db)
        # Premier import
        rep1 = auto_importer_cycles(d, db)
        assert rep1["C03"]["importe"] is True
        # Deuxième : doit dire deja_en_bdd
        rep2 = auto_importer_cycles(d, db)
        assert rep2["C03"]["importe"] is False
        assert rep2["C03"]["raison"] == "deja_en_bdd"


# ═════════════════════════════════════════════════════════════════════════════
# 4. v2_lecture enrichie : précédences au top-level
# ═════════════════════════════════════════════════════════════════════════════

from services.v2_lecture import lire_sequence_par_niveau


class TestV2LectureEnrichie:
    def test_precedences_au_top_level(self, base):
        ajouter_precedence_sequence(base, "sn_n11", "N10", "S03")
        rep = lire_sequence_par_niveau(base, "N11", "S03")
        assert "precedences" in rep
        assert rep["precedences"] == [
            {"precedent_niveau": "N10", "precedent_seq": "S03", "ordre": 1},
        ]

    def test_precedences_vide_par_defaut(self, base):
        rep = lire_sequence_par_niveau(base, "N12", "S99")
        assert rep["precedences"] == []


# ═════════════════════════════════════════════════════════════════════════════
# 5. Tests d'intégration via routes Flask
# ═════════════════════════════════════════════════════════════════════════════

class TestRoutes:
    @pytest.fixture
    def populated(self, app, sqlite_store):
        import sqlite3 as _sql
        with _sql.connect(sqlite_store.db_path) as c:
            c.execute("PRAGMA foreign_keys = ON")
            c.executescript("""
                INSERT INTO sequences_par_niveau (id, niveau, sequence_code)
                  VALUES ('sn_X', 'N11', 'S03');
                INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                  VALUES ('pt_X', 'sn_X', 1);
                INSERT INTO exercices
                  (id, serie, titre, fichier, niveau, sequence, num, serie_code)
                  VALUES
                  ('ex_ea_X', 'approche', 'EA', 'ea.tex', 'N11', 'S03', 1, 'AE'),
                  ('ex_a_n10', 'avancee', 'A', 'a.tex',  'N10', 'S03', 1, 'A');
            """)
            c.commit()
        return {"sn_id": "sn_X", "pt_id": "pt_X"}

    def test_get_precedences_vide(self, client, populated):
        rep = client.get(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/precedences"
        )
        assert rep.status_code == 200
        assert rep.get_json()["precedences"] == []

    def test_post_precedence(self, client, populated):
        rep = client.post(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/precedences",
            json={"precedent_niveau": "N10", "precedent_seq": "S03"},
        )
        assert rep.status_code == 201
        assert len(rep.get_json()["precedences"]) == 1

    def test_post_precedence_circulaire_400(self, client, populated):
        rep = client.post(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/precedences",
            json={"precedent_niveau": "N11", "precedent_seq": "S03"},
        )
        assert rep.status_code == 400

    def test_post_precedence_doublon_409(self, client, populated):
        client.post(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/precedences",
            json={"precedent_niveau": "N10", "precedent_seq": "S03"},
        )
        rep = client.post(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/precedences",
            json={"precedent_niveau": "N10", "precedent_seq": "S03"},
        )
        assert rep.status_code == 409

    def test_delete_precedence(self, client, populated):
        client.post(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/precedences",
            json={"precedent_niveau": "N10", "precedent_seq": "S03"},
        )
        rep = client.delete(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}"
            f"/precedences/N10/S03",
        )
        assert rep.status_code == 200
        assert rep.get_json()["precedences"] == []

    def test_delete_precedence_inexistante_404(self, client, populated):
        rep = client.delete(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}"
            f"/precedences/N10/S99",
        )
        assert rep.status_code == 404

    def test_ea_valide_via_route(self, client, populated):
        rep = client.post(
            f"/api/v2/parties/{populated['pt_id']}/exos-revision-approche",
            json={"type": "EA", "exercice_id": "ex_ea_X"},
        )
        assert rep.status_code == 201

    def test_r_sans_precedence_409(self, client, populated):
        rep = client.post(
            f"/api/v2/parties/{populated['pt_id']}/exos-revision-approche",
            json={"type": "R", "exercice_id": "ex_a_n10"},
        )
        assert rep.status_code == 409
        assert rep.get_json()["code"] == "exo_revision_hors_precedences"

    def test_r_avec_precedence(self, client, populated):
        # Ajouter la précédence d'abord
        client.post(
            f"/api/v2/sequences-par-niveau/{populated['sn_id']}/precedences",
            json={"precedent_niveau": "N10", "precedent_seq": "S03"},
        )
        rep = client.post(
            f"/api/v2/parties/{populated['pt_id']}/exos-revision-approche",
            json={"type": "R", "exercice_id": "ex_a_n10"},
        )
        assert rep.status_code == 201
