"""
tests/test_sequences_par_classe.py — Tests de la v0.6.1 :
- /api/classes/<cid>/sequences lit depuis le référentiel rattaché
- Fallback sur le YAML si pas de référentiel
- Bascule auto du référentiel vers 'verrouille' dès saisie d'une évaluation
"""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def _creer_referentiel_minimal(db, ref_id="N11_v2024", niveau="N11", etat="valide"):
    """Crée un référentiel minimal en base."""
    db.creer_referentiel({
        "id":          ref_id,
        "niveau":      niveau,
        "version":     ref_id.split("_v")[-1],
        "description": "Test",
        "etat":        etat,
        "themes": [{"code": "A", "nom": "Nombres et Calculs", "couleur": ""}],
        "sequences": [
            {
                "code": "S01", "numero": 1, "nom": "Représentations d'un nombre",
                "theme_code": "A",
                "objectifs": [
                    {"code": "01", "nom": "Connaître le cours", "fin_cycle": True},
                    {"code": "05", "nom": "Libellé d'époque 05", "fin_cycle": False},
                    {"code": "06", "nom": "Libellé d'époque 06", "fin_cycle": True},
                ],
            },
        ],
    })


def _creer_progression_et_classe(db, ref_id, cid="4E3", niveau="N11"):
    """Crée une progression liée au référentiel et une classe pointant dessus."""
    prog_id = f"{niveau}-2024-2025-TEST"
    db.ecrire_progression({
        "id": prog_id, "niveau": niveau, "annee": "2024-2025",
        "etablissement": "Test", "source": "sequencesdb",
        "referentiel_id": ref_id,
        "creneaux": [],
    })
    classes = db.lire_classes().get("classes", [])
    classes.append({
        "id": cid, "nom": cid, "niveau": niveau, "annee": "2024-2025",
        "etablissement": "Test", "progression_id": prog_id,
        "eleves": [{"id": "e_abc", "nom": "Chailloux", "prenom": "Romane"}],
        "versions_actives": {}, "sequences_verouillees": [],
    })
    db.ecrire_classes({"classes": classes})
    return prog_id


# ── Route /api/classes/<cid>/sequences ───────────────────────────────────────

class TestRouteSequencesParClasse:

    def test_retourne_depuis_referentiel_quand_dispo(self, client, app):
        """Si la classe pointe vers un référentiel, ses objectifs sont utilisés."""
        db = app.json_store
        _creer_referentiel_minimal(db, etat="valide")
        _creer_progression_et_classe(db, "N11_v2024")

        r = client.get("/api/classes/4E3/sequences")
        assert r.status_code == 200
        d = r.get_json()

        assert d["source"] == "referentiel"
        assert d["referentiel_id"] == "N11_v2024"
        assert len(d["sequences"]) == 1
        seq = d["sequences"][0]
        assert seq["code"] == "S01"
        # Les codes d'objectifs sont ceux du référentiel, pas ceux du YAML courant
        codes = [o["code"] for o in seq["objectifs"]]
        assert "05" in codes
        assert "06" in codes
        # Le nom d'époque est bien présent (pas remappé)
        noms = {o["code"]: o["nom"] for o in seq["objectifs"]}
        assert noms["05"] == "Libellé d'époque 05"

    def test_fallback_yaml_si_pas_de_referentiel(self, client, app):
        """Une classe sans referentiel_id fallback sur le YAML (comportement legacy)."""
        db = app.json_store
        # Classe sans progression associée
        db.ecrire_classes({"classes": [{
            "id": "X1", "nom": "x1", "niveau": "N11", "annee": "2024-2025",
            "etablissement": "", "progression_id": "",
            "eleves": [], "versions_actives": {}, "sequences_verouillees": [],
        }]})

        r = client.get("/api/classes/X1/sequences")
        assert r.status_code == 200
        d = r.get_json()
        assert d["source"] == "yaml"
        assert d["referentiel_id"] is None
        # Les séquences peuvent être vides si aucun YAML n'est peuplé ;
        # l'important est que la route ne plante pas.

    def test_classe_inconnue_retourne_404(self, client):
        r = client.get("/api/classes/INCONNU/sequences")
        assert r.status_code == 404


# ── Bascule auto lors de la saisie d'une évaluation ──────────────────────────

class TestBasculeAutoVerrouille:

    def test_set_niveau_verrouille_referentiel_valide(self, client, app):
        """
        Un référentiel en état 'valide' bascule auto en 'verrouille' dès la
        première saisie d'un niveau pour une classe qui l'utilise.
        """
        db = app.json_store
        _creer_referentiel_minimal(db, etat="valide")
        _creer_progression_et_classe(db, "N11_v2024")

        assert db.lire_referentiel("N11_v2024")["etat"] == "valide"

        # Saisir un niveau pour un élève
        r = client.post("/api/niveaux/set", json={
            "classe": "4E3", "seq": "S01", "eleve_id": "e_abc",
            "obj_code": "05", "niveau": "3",  # 3 = Avancé
        })
        assert r.status_code == 200

        # Le référentiel doit maintenant être verrouillé
        assert db.lire_referentiel("N11_v2024")["etat"] == "verrouille"

    def test_set_niveau_reste_verrouille_si_deja_verrouille(self, client, app):
        """Idempotence : pas de régression d'état."""
        db = app.json_store
        _creer_referentiel_minimal(db, etat="verrouille")
        _creer_progression_et_classe(db, "N11_v2024")

        client.post("/api/niveaux/set", json={
            "classe": "4E3", "seq": "S01", "eleve_id": "e_abc",
            "obj_code": "05", "niveau": "3",
        })
        assert db.lire_referentiel("N11_v2024")["etat"] == "verrouille"

    def test_set_niveau_sans_referentiel_ne_plante_pas(self, client, app):
        """Une classe sans référentiel (legacy) doit toujours fonctionner."""
        db = app.json_store
        db.ecrire_classes({"classes": [{
            "id": "X1", "nom": "x1", "niveau": "N11", "annee": "2024-2025",
            "etablissement": "", "progression_id": "",
            "eleves": [{"id": "e_abc", "nom": "Test", "prenom": "T"}],
            "versions_actives": {}, "sequences_verouillees": [],
        }]})

        r = client.post("/api/niveaux/set", json={
            "classe": "X1", "seq": "S01", "eleve_id": "e_abc",
            "obj_code": "01", "niveau": "3",
        })
        assert r.status_code == 200  # pas d'erreur
