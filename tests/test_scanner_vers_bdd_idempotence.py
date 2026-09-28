"""
tests/test_scanner_vers_bdd_idempotence.py — Tests de non-régression
pour deux bugs rencontrés après déploiement v0.6.3 + nettoyage_6 :

Bug #1 (import partiel)
-----------------------
Avant ce test : `lire_notions` ne renvoyait pas le champ `fichier`.
Résultat : la déduplication dans `scanner_vers_bdd` ne marchait pas
pour les notions — chaque réimport considérait toutes les notions
comme « nouvelles » et les ré-insérait à côté des anciennes via le
DELETE+INSERT complet. Il fallait enchaîner 6-7 imports pour
converger (et encore, avec des IDs incohérents).

Bug #2 (parties v2 vides)
-------------------------
Après un `reset_reference` + import : la table `objectifs` (legacy)
est vidée mais `referentiel_objectifs` ne l'est pas. `scanner_vers_bdd`
n'appelait pas `ecrire_objectifs()` pour réhydrater les objectifs
depuis les référentiels. Du coup :
  - `peupler_v2_depuis_base` ne trouve aucun objectif legacy →
    crée une partie 1 vide, pas de liaison aux méthodes
  - L'atelier Séquence affiche « partie vide »

Ce test construit un SqliteStore truqué (monkey-patch sur
`ecrire_objectifs`) pour vérifier que la méthode est bien appelée
par `scanner_vers_bdd`.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore


@pytest.fixture
def store():
    """SqliteStore sur une base temporaire vide."""
    with tempfile.TemporaryDirectory() as tmp:
        yield SqliteStore(Path(tmp))


# ─────────────────────────────────────────────────────────────────────────────
# Bug #1 : déduplication par `fichier` stable à travers les réimports
# ─────────────────────────────────────────────────────────────────────────────

class TestLireNotionsRenvoieFichier:
    """
    `lire_notions` doit renvoyer les métadonnées de scan (niveau,
    sequence, num_connaissance, fichier) en plus des champs
    classiques. Sans cela, la déduplication par `fichier` dans
    `scanner_vers_bdd` ne fonctionne pas.
    """

    def test_fichier_est_dans_le_dict(self, store):
        store.ecrire_notions([{
            "id": "uuid1", "titre": "T",
            "niveau": "N11", "sequence": "S01",
            "num_connaissance": "01", "fichier": "N11_S01_Notion_01.tex",
        }])
        lues = store.lire_notions()
        assert len(lues) == 1
        assert lues[0]["fichier"] == "N11_S01_Notion_01.tex"
        assert lues[0]["niveau"] == "N11"
        assert lues[0]["sequence"] == "S01"
        assert lues[0]["num_connaissance"] == "01"

    def test_champs_vides_par_defaut(self, store):
        """Si le scanner n'a pas fourni les métadonnées, on renvoie
        des chaînes vides plutôt que None (évite les erreurs de clé
        côté consommateur)."""
        store.ecrire_notions([{"id": "u", "titre": "T"}])
        lues = store.lire_notions()
        assert lues[0]["fichier"] == ""
        assert lues[0]["niveau"] == ""


class TestScannerVersBddDedup:
    """
    Vérifie que `scanner_vers_bdd` est idempotent quand on le rappelle
    avec les mêmes fichiers source (même si les UUID des atomes
    changent à chaque scan).
    """

    def test_notions_dedup_sur_plusieurs_imports(self, store):
        from importers.scanner_latex import scanner_vers_bdd

        class CsvNull:
            def lire_param_niveaux(self):    return {}
            def lire_c03_sequences(self):    return {}
            def lire_c04_sequences(self):    return {}
            def lire_c03_themes(self):       return {}
            def lire_c04_themes(self):       return {}
            def lire_c03_connaissances(self): return {}
            def lire_c04_connaissances(self): return {}
            def lire_c03_objectifs(self):     return {}
            def lire_c04_objectifs(self):     return {}

        def _data(ids):
            return {
                "niveau": "",
                "notions": [
                    {"id": ids[0], "titre": "T1", "niveau": "N11",
                     "sequence": "S01", "num_connaissance": "01",
                     "fichier": "A.tex"},
                    {"id": ids[1], "titre": "T2", "niveau": "N11",
                     "sequence": "S01", "num_connaissance": "02",
                     "fichier": "B.tex"},
                ],
                "methodes": [], "exercices": [], "livrets": [], "erreurs": [],
            }

        # 1er import
        r1 = scanner_vers_bdd(_data(["u1", "u2"]), store, CsvNull())
        assert r1["notions"] == {"total": 2, "nouvelles": 2}
        assert len(store.lire_notions()) == 2

        # 2e import avec de nouveaux UUID (comme le scanner le fait réellement)
        r2 = scanner_vers_bdd(_data(["new1", "new2"]), store, CsvNull())
        assert r2["notions"]["nouvelles"] == 0
        assert len(store.lire_notions()) == 2

        # 3e import : pareil, toujours stable
        r3 = scanner_vers_bdd(_data(["v1", "v2"]), store, CsvNull())
        assert r3["notions"]["nouvelles"] == 0
        assert len(store.lire_notions()) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Bug #2 : ecrire_objectifs est bien appelé par scanner_vers_bdd
# ─────────────────────────────────────────────────────────────────────────────

class TestScannerVersBddAppelleEcrireObjectifs:
    """
    `scanner_vers_bdd` doit appeler `ecrire_objectifs()` pour
    réhydrater la table legacy `objectifs` depuis `referentiel_objectifs`.
    Sans ce pont, un `reset_reference` suivi d'un scan laisse
    `objectifs` vide, et `peupler_v2_depuis_base` crée des parties vides.
    """

    def test_ecrire_objectifs_est_appele(self, store):
        from importers.scanner_latex import scanner_vers_bdd

        class CsvNull:
            def lire_param_niveaux(self):    return {}
            def lire_c03_sequences(self):    return {}
            def lire_c04_sequences(self):    return {}
            def lire_c03_themes(self):       return {}
            def lire_c04_themes(self):       return {}
            def lire_c03_connaissances(self): return {}
            def lire_c04_connaissances(self): return {}
            def lire_c03_objectifs(self):     return {}
            def lire_c04_objectifs(self):     return {}

        # On instrumente ecrire_objectifs pour compter les appels
        appels = []
        original = store.ecrire_objectifs
        def wrapper(*a, **kw):
            appels.append((a, kw))
            return original(*a, **kw)
        store.ecrire_objectifs = wrapper

        data = {
            "niveau": "", "notions": [], "methodes": [],
            "exercices": [], "livrets": [], "erreurs": [],
        }
        scanner_vers_bdd(data, store, CsvNull())

        assert len(appels) == 1, (
            "ecrire_objectifs doit être appelé exactement une fois par "
            "scanner_vers_bdd pour réhydrater les objectifs legacy "
            "depuis referentiel_objectifs"
        )

    def test_ecrire_objectifs_en_erreur_ne_bloque_pas_limport(self, store):
        """
        Si la réhydratation échoue (par ex. FK cassées), le scan ne
        doit pas planter — l'erreur est loggée dans `erreurs` et les
        atomes sont persistés.
        """
        from importers.scanner_latex import scanner_vers_bdd

        class CsvNull:
            def lire_param_niveaux(self):    return {}
            def lire_c03_sequences(self):    return {}
            def lire_c04_sequences(self):    return {}
            def lire_c03_themes(self):       return {}
            def lire_c04_themes(self):       return {}
            def lire_c03_connaissances(self): return {}
            def lire_c04_connaissances(self): return {}
            def lire_c03_objectifs(self):     return {}
            def lire_c04_objectifs(self):     return {}

        # Faire planter ecrire_objectifs
        def boom(*a, **kw): raise RuntimeError("simulated failure")
        store.ecrire_objectifs = boom

        data = {
            "niveau": "",
            "notions": [{"id": "u", "titre": "T", "niveau": "N11",
                         "sequence": "S01", "num_connaissance": "01",
                         "fichier": "A.tex"}],
            "methodes": [], "exercices": [], "livrets": [], "erreurs": [],
        }
        # L'import ne doit pas lever
        resume = scanner_vers_bdd(data, store, CsvNull())
        assert resume["notions"]["nouvelles"] == 1
        # L'erreur est reportée dans `erreurs`
        assert any("ecrire_objectifs" in e for e in resume["erreurs"])
