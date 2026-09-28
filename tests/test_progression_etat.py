"""
tests/test_progression_etat.py — Tests du verrouillage et des états de progression.

Couvre :
- La fonction `verrouiller_progression` (idempotente, transition auto)
- `changer_etat_progression` (en_cours ↔ valide, refus sur valeurs invalides)
- Le verrouillage auto quand une évaluation est saisie via /api/niveaux/set
"""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from persistence.sqlite_store import SqliteStore
from persistence.ids import nouveau_id_classe, nouveau_id_eleve


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path)


class TestVerrouillerProgression:

    def test_verrouiller_passe_a_verrouille(self, store):
        from services import etablissements as svc
        svc.creer(store, nom="Collège X")
        store.ecrire_progression({
            "niveau": "N11", "annee": "2025-2026", "etablissement": "Collège X",
            "etat": "en_cours", "creneaux": [],
        })
        progs = store.lister_progressions("N11")
        pid = progs[0]["id"]

        store.verrouiller_progression(pid)
        prog = store.lire_progression_par_id(pid)
        assert prog["etat"] == "verrouille"

    def test_verrouiller_idempotent(self, store):
        from services import etablissements as svc
        svc.creer(store, nom="Collège X")
        store.ecrire_progression({
            "niveau": "N11", "annee": "2025-2026", "etablissement": "Collège X",
            "etat": "verrouille", "creneaux": [],
        })
        pid = store.lister_progressions("N11")[0]["id"]
        # Deuxième verrouillage : pas d'erreur, toujours verrouillé
        store.verrouiller_progression(pid)
        assert store.lire_progression_par_id(pid)["etat"] == "verrouille"


class TestChangerEtatProgression:

    def _prog_id(self, store, etat="en_cours"):
        from services import etablissements as svc
        svc.creer(store, nom="Collège X")
        store.ecrire_progression({
            "niveau": "N11", "annee": "2025-2026", "etablissement": "Collège X",
            "etat": etat, "creneaux": [],
        })
        return store.lister_progressions("N11")[0]["id"]

    def test_en_cours_vers_valide(self, store):
        pid = self._prog_id(store, "en_cours")
        store.changer_etat_progression(pid, "valide")
        assert store.lire_progression_par_id(pid)["etat"] == "valide"

    def test_valide_vers_en_cours(self, store):
        pid = self._prog_id(store, "valide")
        store.changer_etat_progression(pid, "en_cours")
        assert store.lire_progression_par_id(pid)["etat"] == "en_cours"

    def test_refuse_etat_invalide(self, store):
        pid = self._prog_id(store)
        with pytest.raises(ValueError, match="Etat invalide"):
            store.changer_etat_progression(pid, "bidon")


class TestVerrouillageAutoViaNiveauxSet:
    """Vérifie que saisir une évaluation verrouille la progression via la route."""

    def test_saisie_niveau_verrouille_la_progression(self, tmp_path):
        # Setup : une classe liée à une progression en_cours
        from services import etablissements as svc_e
        store = SqliteStore(tmp_path)
        svc_e.creer(store, nom="Collège X")

        cid = nouveau_id_classe()
        eid = nouveau_id_eleve()
        store.ecrire_classes({"classes": [{
            "id": cid, "nom": "4e3", "niveau": "N11", "annee": "2025-2026",
            "etablissement": "Collège X",
            "eleves": [{"id": eid, "nom": "DUPONT", "prenom": "Alice"}],
        }]})
        store.ecrire_progression({
            "niveau": "N11", "annee": "2025-2026", "etablissement": "Collège X",
            "etat": "en_cours", "creneaux": [],
        })

        # Appeler la route /api/niveaux/set via le client Flask
        from app import create_app
        app = create_app(data_dir=tmp_path)
        client = app.test_client()

        r = client.post('/api/niveaux/set', json={
            "classe": cid, "seq": "S01", "eleve_id": eid,
            "obj_code": "01", "niveau": "3",
        })
        assert r.status_code == 200

        # La progression doit maintenant être verrouillée
        prog = store.lire_progression(niveau="N11", annee="2025-2026",
                                       etablissement="Collège X")
        assert prog["etat"] == "verrouille"
