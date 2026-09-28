"""
tests/test_sqlite_store.py — Tests du SqliteStore.
"""

import pytest

# v0.7 — Tests adaptés au modèle universel à 2 niveaux
# (atome_sections + atome_section_items remplacent items_texte).
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from persistence.sqlite_store import SqliteStore


# ── Fixture locale ────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    return SqliteStore(tmp_path / "data")


# ── Classes ───────────────────────────────────────────────────────────────────

class TestClasses:

    def _classe(self, cid="cl_00000001", nom="4e3", annee="2025-2026",
                etab="Collège Test"):
        return {
            "id": cid, "nom": nom, "niveau": "N11",
            "annee": annee, "etablissement": etab,
            "progression_id": None,
            "eleves": [{"id": f"el_{cid[-4:]}", "nom": "DUPONT", "prenom": "Alice"}],
            "versions_actives": {}, "sequences_verouillees": [],
        }

    def test_lire_vide(self, db):
        assert db.lire_classes() == {"classes": []}

    def test_creer_et_lire(self, db):
        c = self._classe()
        db.ecrire_classes({"classes": [c]})
        result = db.lire_classes()
        assert len(result["classes"]) == 1
        assert result["classes"][0]["id"] == "cl_00000001"
        assert result["classes"][0]["eleves"][0]["nom"] == "DUPONT"

    def test_plusieurs_classes(self, db):
        # Classes différentes : noms ou années différents (contrainte UNIQUE)
        classes = [
            self._classe("cl_00000001", nom="4e3", annee="2025-2026"),
            self._classe("cl_00000002", nom="4e4", annee="2025-2026"),
            self._classe("cl_00000003", nom="4e3", annee="2024-2025"),
        ]
        db.ecrire_classes({"classes": classes})
        result = db.lire_classes()
        assert len(result["classes"]) == 3

    def test_contrainte_unique_nom_annee_etab(self, db):
        """
        Deux classes avec même (nom, annee, etab) : la seconde doit échouer
        au niveau SQL (la contrainte UNIQUE empêche l'écriture).
        """
        import sqlite3
        c1 = self._classe("cl_00000001", nom="4e3", annee="2025-2026")
        c2 = self._classe("cl_00000002", nom="4e3", annee="2025-2026")
        db.ecrire_classes({"classes": [c1]})
        with pytest.raises(sqlite3.IntegrityError):
            db.ecrire_classes({"classes": [c1, c2]})

    def test_ecrire_remplace_tout(self, db):
        db.ecrire_classes({"classes": [self._classe("cl_a", nom="4e3")]})
        db.ecrire_classes({"classes": [self._classe("cl_b", nom="5e1")]})
        result = db.lire_classes()
        ids = [c["id"] for c in result["classes"]]
        assert "cl_a" not in ids
        assert "cl_b" in ids

    def test_versions_actives_preservees(self, db):
        c = self._classe()
        c["versions_actives"] = {"N11_S01": "2025-09-01"}
        db.ecrire_classes({"classes": [c]})
        result = db.lire_classes()
        assert result["classes"][0]["versions_actives"] == {"N11_S01": "2025-09-01"}

    def test_sequences_verouillees_preservees(self, db):
        c = self._classe()
        c["sequences_verouillees"] = ["N11_S01", "N11_S02"]
        db.ecrire_classes({"classes": [c]})
        result = db.lire_classes()
        assert "N11_S01" in result["classes"][0]["sequences_verouillees"]


# ── Suivi ─────────────────────────────────────────────────────────────────────

class TestSuivi:

    def test_lire_vide(self, db):
        assert db.lire_suivi() == {}

    def test_ecrire_et_lire(self, db):
        data = {"4E3": {"S01": {"e01": {"F": [1, 2], "A": [1]}}}}
        db.ecrire_suivi(data)
        result = db.lire_suivi()
        assert result["4E3"]["S01"]["e01"]["F"] == [1, 2]
        assert result["4E3"]["S01"]["e01"]["A"] == [1]

    def test_cocher_exercice(self, db):
        db.cocher_exercice("4E3", "S01", "e01", "F", 1, True)
        db.cocher_exercice("4E3", "S01", "e01", "F", 2, True)
        result = db.lire_suivi_classe("4E3")
        assert 1 in result["S01"]["e01"]["F"]
        assert 2 in result["S01"]["e01"]["F"]

    def test_decocher_exercice(self, db):
        db.cocher_exercice("4E3", "S01", "e01", "F", 1, True)
        db.cocher_exercice("4E3", "S01", "e01", "F", 1, False)
        result = db.lire_suivi_classe("4E3")
        assert 1 not in result.get("S01", {}).get("e01", {}).get("F", [])

    def test_lire_suivi_classe(self, db):
        data = {
            "4E3": {"S01": {"e01": {"F": [1]}}},
            "4E4": {"S01": {"e02": {"F": [2]}}},
        }
        db.ecrire_suivi(data)
        result = db.lire_suivi_classe("4E3")
        assert "S01" in result
        assert "4E4" not in result

    def test_ecrire_remplace_tout(self, db):
        db.ecrire_suivi({"4E3": {"S01": {"e01": {"F": [1]}}}})
        db.ecrire_suivi({"4E4": {"S01": {"e02": {"F": [2]}}}})
        result = db.lire_suivi()
        assert "4E3" not in result
        assert "4E4" in result


# ── Niveaux ───────────────────────────────────────────────────────────────────

class TestNiveaux:

    def _setup(self, db):
        """Progression avec créneaux partie_debut/partie_fin pour tester les niveaux."""
        import sqlite3 as _sqlite3
        pid = "N11-2025-2026"
        # Progression en premier (FK progression_id)
        db.ecrire_progression({
            "id": pid, "niveau": "N11", "annee": "2025-2026",
            "etablissement": "", "source": "test",
            "creneaux": [
                {"id": "cr1", "sequence": "S01", "partie_debut": 1, "partie_fin": 1,
                 "partie": None, "periode": "Sem1",
                 "date_debut": None, "date_fin": None, "ordre": 1},
                {"id": "cr2", "sequence": "S01", "partie_debut": 2, "partie_fin": 2,
                 "partie": None, "periode": "Sem2",
                 "date_debut": None, "date_fin": None, "ordre": 2},
            ],
        })
        db.ecrire_classes({"classes": [{
            "id": "4E3", "nom": "4e3", "niveau": "N11",
            "annee": "2025-2026", "etablissement": "", "progression_id": pid,
            "eleves": [{"id": "e01", "nom": "A", "prenom": "B"},
                       {"id": "e02", "nom": "C", "prenom": "D"}],
            "versions_actives": {}, "sequences_verouillees": [],
        }]})
        # v0.14.6.b.2 — INSERT préalables dans `objectifs` (v1) retirés.
        # La colonne `niveaux.objectif_id` ayant été supprimée, plus
        # besoin de pré-créer les objectifs ; `niveaux` n'a plus de FK
        # vers eux.

    def test_lire_vide(self, db):
        assert db.lire_niveaux() == {}

    def test_ecrire_et_lire(self, db):
        self._setup(db)
        data = {"4E3": {"S01": {"e01": {"01": "3"}}}}
        db.ecrire_niveaux(data)
        result = db.lire_niveaux()
        assert result["4E3"]["S01"]["e01"]["01"] == "3"

    def test_set_niveau(self, db):
        self._setup(db)
        db.set_niveau("4E3", "S01", "e01", "01", "4")
        result = db.lire_niveaux_classe("4E3")
        assert result["S01"]["e01"]["01"] == "4"

    def test_set_niveau_ecrase(self, db):
        self._setup(db)
        db.set_niveau("4E3", "S01", "e01", "01", "3")
        db.set_niveau("4E3", "S01", "e01", "01", "4")
        result = db.lire_niveaux_classe("4E3")
        assert result["S01"]["e01"]["01"] == "4"

    def test_lire_niveaux_classe(self, db):
        self._setup(db)
        db.set_niveau("4E3", "S01", "e01", "01", "3")
        result = db.lire_niveaux_classe("4E3")
        assert "S01" in result and "e01" in result["S01"]

    def test_code_0_stocke(self, db):
        self._setup(db)
        db.set_niveau("4E3", "S01", "e01", "13", "0")
        result = db.lire_niveaux_classe("4E3")
        assert result["S01"]["e01"]["13"] == "0"


class TestSuppression:

    def _preparer(self, db):
        db.ecrire_classes({"classes": [{
            "id": "4E3", "nom": "4e3", "niveau": "N11",
            "annee": "2025-2026", "etablissement": "Test",
            "progression_id": "", "eleves": [
                {"id": "e01", "nom": "A", "prenom": "B"},
                {"id": "e02", "nom": "C", "prenom": "D"},
            ],
            "versions_actives": {}, "sequences_verouillees": [],
        }]})
        # Pas de créneaux/objectifs ici → on teste juste la suppression structurelle

    def test_supprimer_classe(self, db):
        self._preparer(db)
        db.supprimer_donnees_classe("4E3")
        assert db.lire_classes() == {"classes": []}

    def test_supprimer_eleve(self, db):
        self._preparer(db)
        db.supprimer_donnees_eleve("4E3", "e01")
        # e01 retiré de la classe, e02 toujours là
        classes = db.lire_classes()
        eleves_ids = [e["id"] for e in classes["classes"][0]["eleves"]]
        assert "e01" not in eleves_ids
        assert "e02" in eleves_ids

    def test_supprimer_classe_nettoie_eleves_orphelins(self, db):
        """
        Supprimer une classe doit aussi supprimer les élèves qui n'étaient
        rattachés qu'à cette classe (pas d'orphelins dans la table globale).
        """
        self._preparer(db)
        # Avant : 2 élèves
        with db._conn() as conn:
            n_eleves = conn.execute("SELECT COUNT(*) FROM eleves").fetchone()[0]
            assert n_eleves == 2
        db.supprimer_donnees_classe("4E3")
        with db._conn() as conn:
            n_eleves = conn.execute("SELECT COUNT(*) FROM eleves").fetchone()[0]
            assert n_eleves == 0, "Les élèves orphelins doivent être supprimés"

    def test_supprimer_classe_preserve_eleves_rattaches_ailleurs(self, db):
        """
        Si un élève est rattaché à 2 classes et qu'on supprime l'une des deux,
        l'élève doit rester dans la base.
        """
        db.ecrire_classes({"classes": [
            {"id": "4E3", "nom": "4e3", "niveau": "N11",
             "annee": "2025-2026", "etablissement": "T",
             "progression_id": "",
             "eleves": [{"id": "e_shared", "nom": "X", "prenom": "Y"}],
             "versions_actives": {}, "sequences_verouillees": []},
            {"id": "4E4", "nom": "4e4", "niveau": "N11",
             "annee": "2025-2026", "etablissement": "T",
             "progression_id": "",
             "eleves": [{"id": "e_shared", "nom": "X", "prenom": "Y"}],
             "versions_actives": {}, "sequences_verouillees": []},
        ]})
        db.supprimer_donnees_classe("4E3")
        with db._conn() as conn:
            # e_shared est toujours dans eleves (car 4E4 le référence encore)
            row = conn.execute(
                "SELECT id FROM eleves WHERE id='e_shared'"
            ).fetchone()
            assert row is not None


# ── Versions ──────────────────────────────────────────────────────────────────

class TestVersions:

    def test_lire_vide(self, db):
        assert db.lire_versions() == {}

    def test_upsert_et_lire(self, db):
        db.upsert_version("N11", "S01", "2025-09-01", "Rentrée",
                          "2025-09-01", {"objectifs": []})
        result = db.lire_versions()
        assert "N11" in result
        assert "S01" in result["N11"]
        assert result["N11"]["S01"][0]["tag"] == "2025-09-01"

    def test_plusieurs_versions(self, db):
        db.upsert_version("N11", "S01", "2025-09-01", "v1", "2025-09-01", {})
        db.upsert_version("N11", "S01", "2025-10-01", "v2", "2025-10-01", {})
        result = db.lire_versions()
        assert len(result["N11"]["S01"]) == 2

    def test_supprimer_version(self, db):
        db.upsert_version("N11", "S01", "2025-09-01", "v1", "2025-09-01", {})
        db.supprimer_version("N11", "S01", "2025-09-01")
        result = db.lire_versions()
        assert not result.get("N11", {}).get("S01", [])

    def _classe_test(self, db):
        db.ecrire_classes({"classes": [{
            "id": "4E3", "nom": "4e3", "niveau": "N11", "annee": "2025-2026",
            "etablissement": "", "progression_id": "", "eleves": [],
            "versions_actives": {}, "sequences_verouillees": [],
        }]})

    def test_version_utilisee(self, db):
        self._classe_test(db)
        db.upsert_version("N11", "S01", "v1", "", "", {})
        db.set_version_active("4E3", "N11", "S01", "v1")
        assert db.version_utilisee("N11", "S01", "v1") is True
        assert db.version_utilisee("N11", "S01", "v2") is False

    def test_verrouiller(self, db):
        self._classe_test(db)
        db.set_version_active("4E3", "N11", "S01", "v1")
        assert db.est_verrouille("4E3", "N11", "S01") is False
        db.verrouiller("4E3", "N11", "S01")
        assert db.est_verrouille("4E3", "N11", "S01") is True

    def test_ecrire_lire_versions_complet(self, db):
        data = {"N11": {"S01": [
            {"tag": "v1", "label": "Test", "date": "2025-09-01", "objectifs": []}
        ]}}
        db.ecrire_versions(data)
        result = db.lire_versions()
        assert result["N11"]["S01"][0]["label"] == "Test"


# ── Atomes pédagogiques ───────────────────────────────────────────────────────

class TestAtomes:

    def test_notions_round_trip(self, db):
        # v0.7 : modèle universel à 2 niveaux. La clé legacy `exemples`
        # n'existe plus côté API ; on passe directement `sections`.
        notions = [{"id": "abc123", "titre": "Proportion.", "corps": "Def.",
                    "sections": [
                        {"titre": "Exemples", "items": ["ex1"]},
                    ]}]
        db.ecrire_notions(notions)
        result = db.lire_notions()
        assert len(result) == 1
        assert result[0]["titre"] == "Proportion."
        # Le round-trip doit préserver le format sections.
        assert result[0]["sections"] == [
            {"titre": "Exemples", "items": ["ex1"]},
        ]

    def test_methodes_round_trip(self, db):
        # v0.7 : sections au lieu de exemples/remarques.
        # v0.14.6.b.1 — Le cas legacy (méthode sans métadonnées qui
        # créait un objectif orphelin v1) a été supprimé. Pour valider
        # le round-trip des critères, on utilise désormais le cas nominal :
        # créer un objectif v2 préexistant (via la pile partie →
        # sequence_par_niveau) puis y lier la méthode par
        # (niveau, sequence, num_objectif).
        import sqlite3
        # Créer la notion référencée avant la méthode.
        db.ecrire_notions([{"id": "abc123", "titre": "Notion test", "corps": "",
                            "sections": []}])
        # Créer la pile partie → sequence_par_niveau + l'objectif v2 cible.
        with sqlite3.connect(str(db.db_path)) as conn:
            conn.execute(
                "INSERT INTO sequences_par_niveau "
                "(id, niveau, sequence_code) VALUES ('sn_test', 'N10', 'S01')"
            )
            conn.execute(
                "INSERT INTO sequence_parties "
                "(id, sequence_par_niveau_id, numero) "
                "VALUES ('pt_test', 'sn_test', 1)"
            )
            conn.execute(
                "INSERT INTO objectifs "
                "(id, partie_id, code, nom) "
                "VALUES ('ov2_02', 'pt_test', '02', 'Objectif cible')"
            )
            conn.commit()

        methodes = [{"id": "m01", "titre": "Calculer un %.", "corps": "",
                     "sections": [],
                     "notions": ["abc123"], "finCycle": "O",
                     # v0.14.6.b.1 — métadonnées nécessaires pour que
                     # ecrire_methodes lie la méthode à l'objectif v2.
                     "niveau": "N10", "sequence": "S01",
                     "num_methode": "1", "num_objectif": "02",
                     "criteres": {"2": "crit F", "3": "crit A", "4": "crit E"}}]
        db.ecrire_methodes(methodes)
        result = db.lire_methodes()
        assert result[0]["finCycle"] == "O"
        assert result[0]["criteres"]["2"] == "crit F"
        assert result[0]["notions"] == ["abc123"]
        assert result[0]["sections"] == []

    def test_exercices_round_trip(self, db):
        exercices = [{"id": "e01", "serie": "fondamental", "nom": "Exo 1",
                      "objectifs": [], "enonce": "Calculer…", "corrige": "= 42"}]
        db.ecrire_exercices(exercices)
        result = db.lire_exercices()
        assert result[0]["serie"] == "fondamental"
        assert result[0]["corrige"] == "= 42"

    def test_ecrire_vide_efface(self, db):
        db.ecrire_notions([{"id": "x", "titre": "T", "corps": "",
                            "sections": []}])
        db.ecrire_notions([])
        assert db.lire_notions() == []


# ── Multi-années ──────────────────────────────────────────────────────────────

class TestMultiAnnees:

    def _classes(self, db):
        db.ecrire_classes({"classes": [
            {"id": "4E3_25", "nom": "4e3", "niveau": "N11", "annee": "2025-2026",
             "etablissement": "Collège A", "progression_id": "",
             "eleves": [], "versions_actives": {}, "sequences_verouillees": []},
            {"id": "4E3_24", "nom": "4e3", "niveau": "N11", "annee": "2024-2025",
             "etablissement": "Collège A", "progression_id": "",
             "eleves": [], "versions_actives": {}, "sequences_verouillees": []},
            {"id": "4E4_25", "nom": "4e4", "niveau": "N11", "annee": "2025-2026",
             "etablissement": "Collège B", "progression_id": "",
             "eleves": [], "versions_actives": {}, "sequences_verouillees": []},
        ]})

    def test_annees_disponibles(self, db):
        self._classes(db)
        annees = db.lire_annees_disponibles()
        assert "2025-2026" in annees
        assert "2024-2025" in annees
        # Plus récente en premier
        assert annees.index("2025-2026") < annees.index("2024-2025")

    def test_etablissements_disponibles(self, db):
        self._classes(db)
        etabs = db.lire_etablissements_disponibles()
        assert "Collège A" in etabs
        assert "Collège B" in etabs

    def test_classes_par_annee(self, db):
        self._classes(db)
        result = db.lire_classes_par_annee("2025-2026")
        ids = [c["id"] for c in result["classes"]]
        assert "4E3_25" in ids
        assert "4E4_25" in ids
        assert "4E3_24" not in ids

    def test_classes_par_annee_etab(self, db):
        self._classes(db)
        result = db.lire_classes_par_annee_etab("2025-2026", "Collège A")
        ids = [c["id"] for c in result["classes"]]
        assert "4E3_25" in ids
        assert "4E4_25" not in ids  # Collège B

    def test_niveaux_filtres_par_annee(self, db):
        self._classes(db)
        # Sans progressions/créneaux, on teste le filtre via lire_classes
        result_25 = db.lire_classes_par_annee("2025-2026")
        result_24 = db.lire_classes_par_annee("2024-2025")
        ids_25 = [c["id"] for c in result_25["classes"]]
        ids_24 = [c["id"] for c in result_24["classes"]]
        assert "4E3_25" in ids_25
        assert "4E3_24" not in ids_25
        assert "4E3_24" in ids_24


# ── Réinitialisation ──────────────────────────────────────────────────────────

class TestReset:

    def test_reset_reference(self, db):
        db.ecrire_notions([{"id": "x", "titre": "T", "corps": "",
                            "exemples": [], "remarques": [], "ordreExRem": True}])
        db.reset_reference()
        assert db.lire_notions() == []

    def test_reset_suivi(self, db):
        db.ecrire_classes({"classes": [{
            "id": "4E3", "nom": "4e3", "niveau": "N11", "annee": "2025-2026",
            "etablissement": "", "progression_id": "", "eleves": [],
            "versions_actives": {}, "sequences_verouillees": [],
        }]})
        db.reset_suivi()
        assert db.lire_classes() == {"classes": []}
        assert db.lire_niveaux() == {}

    def test_reset_suivi_vide_progressions_et_creneaux(self, db):
        """
        Option A : "Vider le suivi" doit tout nettoyer côté classes (classes,
        élèves, progressions, créneaux, suivi, niveaux), mais PAS toucher aux
        référentiels (partagés, immuables).
        """
        # Créer un référentiel qui doit survivre
        db.creer_referentiel({
            "id": "N11_v2024-2025", "niveau": "N11", "version": "2024-2025",
            "verrouille": True,
            "themes": [{"code": "A", "nom": "Nombres et Calculs"}],
            "sequences": [{"code": "S01", "numero": 1, "nom": "Test",
                          "theme_code": "A", "objectifs": [
                              {"code": "01", "nom": "Cours"}
                          ]}],
        })
        # Créer une progression avec un créneau
        db.ecrire_progression({
            "id": "N11-2024-2025-TEST",
            "niveau": "N11", "annee": "2024-2025", "etablissement": "Test",
            "source": "sequencesdb",
            "referentiel_id": "N11_v2024-2025",
            "creneaux": [{
                "id": "cr1", "sequence": "S01", "partie_debut": 1, "partie_fin": 1,
                "periode": "Sem1", "ordre": 1,
            }],
        })
        # Créer une classe + élève + niveau saisi
        db.ecrire_classes({"classes": [{
            "id": "4E3", "nom": "4e3", "niveau": "N11", "annee": "2024-2025",
            "etablissement": "Test", "progression_id": "N11-2024-2025-TEST",
            "eleves": [{"id": "e_abc", "nom": "Dupont", "prenom": "Alice"}],
            "versions_actives": {}, "sequences_verouillees": [],
        }]})
        db.ecrire_niveaux({"4E3": {"S01": {"e_abc": {"01": "A"}}}})

        # Sanity check : tout est bien en base
        with db._conn() as conn:
            assert conn.execute("SELECT COUNT(*) FROM progressions").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM creneaux").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM eleves").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM niveaux").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM referentiel_niveaux").fetchone()[0] == 1

        # Vider le suivi
        db.reset_suivi()

        # Tout le suivi doit être parti
        with db._conn() as conn:
            assert conn.execute("SELECT COUNT(*) FROM progressions").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM creneaux").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM eleves").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM niveaux").fetchone()[0] == 0
            # Le référentiel survit
            assert conn.execute("SELECT COUNT(*) FROM referentiel_niveaux").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM referentiel_objectifs").fetchone()[0] == 1

