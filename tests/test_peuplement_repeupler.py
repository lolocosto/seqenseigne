"""
tests/test_peuplement_repeupler.py — Tests du repeuplement des tables
relationnelles.

v0.15.5 : le wrapper CLI `scripts/peuplement_02_repeupler.py` (orphelin) a
été supprimé. Ces tests ne l'utilisaient pas : ils ciblent directement les
méthodes `ecrire_*` du SqliteStore, qui restent en service.

Couvre les méthodes `ecrire_*` du SqliteStore :
  - ecrire_objectifs (crée les objectifs depuis referentiel_objectifs)
  - ecrire_notions (ajout niveau/sequence/num_connaissance/fichier)
  - ecrire_methodes (ajout métadonnées + liaison objectif)
  - ecrire_exercices (ajout métadonnées + résolution objectifs_codes)
  - ecrire_livrets_importes (peuple livret_exercices + livret_revisions)
"""

import pytest

# v0.7 — Tests adaptés au modèle universel à 2 niveaux
# (atome_sections + atome_section_items remplacent items_texte).
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from persistence.sqlite_store import SqliteStore
from scripts.peuplement_01_migrer_schema import migrer


@pytest.fixture
def store_migre(tmp_path):
    """Store SQLite avec schéma v0.6.3e appliqué."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    store = SqliteStore(data_dir)
    migrer(data_dir / "seqenseigne.db")
    return store


@pytest.fixture
def store_avec_referentiel(store_migre):
    """Store avec un référentiel verrouillé contenant 3 objectifs."""
    store_migre.creer_referentiel({
        "id":          "N10_v2024",
        "niveau":      "N10",
        "version":     "2024",
        "description": "Test",
        "etat":        "verrouille",
        "themes":      [{"code": "A", "nom": "Nombres", "couleur": "blue"}],
        "sequences":   [
            {
                "code": "S01", "numero": 1,
                "nom": "Représentations", "theme_code": "A",
                "objectifs": [
                    {
                        "code": "01", "nom": "Connaître le cours",
                        "fin_cycle": False,
                        "critere_f": "", "critere_a": "", "critere_e": "",
                    },
                    {
                        "code": "02", "nom": "Utiliser les fractions",
                        "fin_cycle": False,
                        "critere_f": "F", "critere_a": "A", "critere_e": "E",
                    },
                    {
                        "code": "03", "nom": "Calculer avec des fractions",
                        "fin_cycle": True,
                        "critere_f": "cF", "critere_a": "cA", "critere_e": "cE",
                    },
                ],
            },
        ],
    })
    return store_migre


# ── Tests ecrire_objectifs ────────────────────────────────────────────────────

class TestEcrireObjectifs:
    def test_cree_objectifs_depuis_referentiel(self, store_avec_referentiel):
        rapport = store_avec_referentiel.ecrire_objectifs()
        assert rapport["objectifs_crees"] == 3
        assert rapport["referentiels_traites"] == 1

    def test_objectifs_ont_metadonnees(self, store_avec_referentiel):
        # v0.14.6.b.1 — ecrire_objectifs écrit désormais dans objectifs.
        # On reconstitue (niveau, sequence_code) via JOIN partie →
        # sequence_par_niveau pour vérifier l'équivalent fonctionnel.
        store_avec_referentiel.ecrire_objectifs()
        import sqlite3
        conn = sqlite3.connect(str(store_avec_referentiel.db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT sn.niveau AS niveau, sn.sequence_code AS sequence, "
            "       ov2.code AS code, ov2.nom AS nom "
            "FROM objectifs ov2 "
            "JOIN sequence_parties      p  ON p.id  = ov2.partie_id "
            "JOIN sequences_par_niveau  sn ON sn.id = p.sequence_par_niveau_id "
            "ORDER BY ov2.code"
        ).fetchall()
        conn.close()
        assert len(rows) == 3
        assert rows[0]["niveau"] == "N10"
        assert rows[0]["sequence"] == "S01"
        assert rows[0]["code"] == "01"
        assert rows[0]["nom"] == "Connaître le cours"
        assert rows[1]["code"] == "02"
        assert rows[1]["nom"] == "Utiliser les fractions"

    def test_criteres_recopies(self, store_avec_referentiel):
        # v0.14.6.b.1 — Lecture v2.
        store_avec_referentiel.ecrire_objectifs()
        import sqlite3
        conn = sqlite3.connect(str(store_avec_referentiel.db_path))
        conn.row_factory = sqlite3.Row
        r = conn.execute(
            "SELECT critere_F, critere_A, critere_E "
            "FROM objectifs WHERE code='02'"
        ).fetchone()
        conn.close()
        assert r["critere_F"] == "F"
        assert r["critere_A"] == "A"
        assert r["critere_E"] == "E"

    def test_idempotent_upsert(self, store_avec_referentiel):
        """Deux runs consécutifs ne doublent pas les objectifs."""
        # v0.14.6.b.1 — COUNT sur v2.
        store_avec_referentiel.ecrire_objectifs()
        import sqlite3
        conn = sqlite3.connect(str(store_avec_referentiel.db_path))
        n1 = conn.execute("SELECT COUNT(*) FROM objectifs").fetchone()[0]
        conn.close()

        rapport2 = store_avec_referentiel.ecrire_objectifs()
        conn = sqlite3.connect(str(store_avec_referentiel.db_path))
        n2 = conn.execute("SELECT COUNT(*) FROM objectifs").fetchone()[0]
        conn.close()
        assert n1 == n2 == 3
        # Au 2e passage, tout est mis à jour (pas créé)
        assert rapport2["objectifs_maj"] == 3
        assert rapport2["objectifs_crees"] == 0

    def test_preserve_methode_id_existante(self, store_avec_referentiel):
        """Si un objectif a été lié à une méthode, le 2e run d'ecrire_objectifs
        ne doit PAS effacer cette liaison.
        v0.14.6.b.1 — Manipulation sur objectifs.
        """
        store_avec_referentiel.ecrire_objectifs()
        import sqlite3
        conn = sqlite3.connect(str(store_avec_referentiel.db_path))
        # Simuler une méthode liée à l'objectif 02
        conn.execute("INSERT INTO methodes (id, titre) VALUES ('m_test', 'Test')")
        obj_id = conn.execute(
            "SELECT ov2.id FROM objectifs ov2 "
            "JOIN sequence_parties      p  ON p.id  = ov2.partie_id "
            "JOIN sequences_par_niveau  sn ON sn.id = p.sequence_par_niveau_id "
            "WHERE ov2.code='02' AND sn.niveau='N10'"
        ).fetchone()[0]
        conn.execute(
            "UPDATE objectifs SET methode_id='m_test' WHERE id=?",
            (obj_id,)
        )
        conn.commit()
        conn.close()

        store_avec_referentiel.ecrire_objectifs()
        conn = sqlite3.connect(str(store_avec_referentiel.db_path))
        r = conn.execute(
            "SELECT methode_id FROM objectifs WHERE id=?", (obj_id,)
        ).fetchone()
        conn.close()
        assert r[0] == "m_test"  # toujours liée

    # v0.14.6.b.1 — test_preserve_liaisons_n_n_moins_1 SUPPRIMÉ.
    # Il vérifiait la préservation des colonnes `est_nouveau` et
    # `obj_precedent_id` à travers un 2e run d'ecrire_objectifs.
    # Ces colonnes n'existent pas dans `objectifs` (décision validée
    # avec Laurent : remplacées par le mécanisme des précédences
    # inter-parties en v2). Le test n'a donc plus de cible. Voir
    # appli/doc/redemarrage_v0_14_6_b1.md pour le détail de la décision.


# ── Tests ecrire_notions ──────────────────────────────────────────────────────

class TestEcrireNotions:
    def test_metadonnees_conservees(self, store_migre):
        store_migre.ecrire_notions([
            {
                "id":               "n_abc",
                "titre":            "Proportion",
                "corps":            "Une proportion est ...",
                "ordreExRem":       True,
                "exemples":         [],
                "remarques":        [],
                "niveau":           "N10",
                "sequence":         "S01",
                "num_connaissance": "01",
                "fichier":          "N10_S01_Notion_01.tex",
            }
        ])
        import sqlite3
        conn = sqlite3.connect(str(store_migre.db_path))
        conn.row_factory = sqlite3.Row
        r = conn.execute(
            "SELECT niveau, sequence, num_connaissance, fichier "
            "FROM notions WHERE id='n_abc'"
        ).fetchone()
        conn.close()
        assert r["niveau"] == "N10"
        assert r["sequence"] == "S01"
        assert r["num_connaissance"] == "01"
        assert r["fichier"] == "N10_S01_Notion_01.tex"


# ── Tests ecrire_methodes ─────────────────────────────────────────────────────

class TestEcrireMethodes:
    def test_metadonnees_conservees(self, store_avec_referentiel):
        store_avec_referentiel.ecrire_objectifs()
        store_avec_referentiel.ecrire_methodes([
            {
                "id":           "m_abc",
                "titre":        "Test méthode",
                "corps":        "Corps",
                "niveau":       "N10",
                "sequence":     "S01",
                "num_methode":  "1",
                "num_objectif": "02",
                "fichier":      "N10_S01_Methode_01.tex",
                "criteres":     {"2": "F2", "3": "A2", "4": "E2"},
            }
        ])
        import sqlite3
        conn = sqlite3.connect(str(store_avec_referentiel.db_path))
        conn.row_factory = sqlite3.Row
        r = conn.execute(
            "SELECT niveau, sequence, num_methode, num_objectif, fichier "
            "FROM methodes WHERE id='m_abc'"
        ).fetchone()
        conn.close()
        assert r["niveau"] == "N10"
        assert r["sequence"] == "S01"
        assert r["num_methode"] == 1
        assert r["num_objectif"] == "02"
        assert r["fichier"] == "N10_S01_Methode_01.tex"

    def test_lie_objectif_existant(self, store_avec_referentiel):
        """Une méthode avec num_objectif='02' doit lier l'objectif '02' du
        même (niveau, sequence)."""
        store_avec_referentiel.ecrire_objectifs()
        store_avec_referentiel.ecrire_methodes([
            {
                "id":           "m_abc",
                "titre":        "Test",
                "niveau":       "N10",
                "sequence":     "S01",
                "num_methode":  "1",
                "num_objectif": "02",
                "fichier":      "test.tex",
                "criteres":     {"2": "F_new", "3": "A_new", "4": "E_new"},
            }
        ])
        import sqlite3
        conn = sqlite3.connect(str(store_avec_referentiel.db_path))
        conn.row_factory = sqlite3.Row
        # v0.14.6.b.1 — Reconstruction niveau/sequence via JOIN v2.
        r = conn.execute(
            "SELECT ov2.methode_id, ov2.critere_F "
            "FROM objectifs ov2 "
            "JOIN sequence_parties      p  ON p.id  = ov2.partie_id "
            "JOIN sequences_par_niveau  sn ON sn.id = p.sequence_par_niveau_id "
            "WHERE sn.niveau='N10' AND sn.sequence_code='S01' AND ov2.code='02'"
        ).fetchone()
        conn.close()
        assert r["methode_id"] == "m_abc"
        # Les critères de la méthode remplacent ceux du référentiel
        assert r["critere_F"] == "F_new"

    def test_methode_sans_referentiel_ne_cree_pas_objectif(self, store_migre):
        """Décision du chantier C1 : une méthode sans objectif correspondant
        dans le référentiel n'en crée pas un.
        v0.14.6.b.1 — Le cas legacy v1 a été supprimé (cf.
        ecrire_methodes : plus de création d'objectif orphelin). Le
        comportement est désormais strictement v2.
        """
        store_migre.ecrire_methodes([
            {
                "id": "m_orphan", "titre": "Orpheline",
                "niveau": "N10", "sequence": "S99",
                "num_methode": "1", "num_objectif": "02",
                "fichier": "test.tex",
                "criteres": {"2": "F", "3": "A", "4": "E"},
            }
        ])
        import sqlite3
        conn = sqlite3.connect(str(store_migre.db_path))
        # v0.14.6.b.1 — COUNT via v2 + JOIN partie.
        n = conn.execute(
            "SELECT COUNT(*) FROM objectifs ov2 "
            "JOIN sequence_parties      p  ON p.id  = ov2.partie_id "
            "JOIN sequences_par_niveau  sn ON sn.id = p.sequence_par_niveau_id "
            "WHERE sn.sequence_code='S99'"
        ).fetchone()[0]
        conn.close()
        assert n == 0, "Aucun objectif ne doit être créé sans referentiel"


# ── Tests ecrire_exercices ────────────────────────────────────────────────────

class TestEcrireExercices:
    def test_metadonnees_conservees(self, store_avec_referentiel):
        store_avec_referentiel.ecrire_objectifs()
        store_avec_referentiel.ecrire_exercices([
            {
                "id":              "ex_abc",
                "serie":           "fondamental",
                "serie_code":      "F",
                "niveau":          "N10",
                "sequence":        "S01",
                "num":             "3",
                "fichier":         "N10S01F03.tex",
                "nom":             "",
                "variables":       "",
                "enonce":          "Énoncé",
                "corrige":         "Corrigé",
                "objectifs_codes": ["02"],
            }
        ])
        import sqlite3
        conn = sqlite3.connect(str(store_avec_referentiel.db_path))
        conn.row_factory = sqlite3.Row
        r = conn.execute(
            "SELECT niveau, sequence, num, serie_code, fichier "
            "FROM exercices WHERE id='ex_abc'"
        ).fetchone()
        conn.close()
        assert r["niveau"] == "N10"
        assert r["sequence"] == "S01"
        assert r["num"] == 3
        assert r["serie_code"] == "F"
        assert r["fichier"] == "N10S01F03.tex"

    # v0.14.6.b.2 — test_liaison_exercice_objectifs et
    # test_objectifs_codes_inconnu_ignore supprimés : la table
    # `exercice_objectifs` (v1) n'existe plus.


# ── Tests ecrire_livrets_importes ─────────────────────────────────────────────

