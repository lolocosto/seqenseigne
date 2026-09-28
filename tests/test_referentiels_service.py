"""tests/test_referentiels_service.py — Tests service + route référentiels.

Le fichier tests/test_referentiels.py existant teste les accès bas-niveau
du store. Ce fichier complète avec le nouveau service et la nouvelle route.
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services import referentiels as svc


# ── Helpers ────────────────────────────────────────────────────────────────────

def _creer_referentiel(store, niveau: str, version: str, etat: str = "en_cours",
                      description: str = "") -> str:
    """Crée un référentiel minimal dans le store et retourne son id."""
    return store.creer_referentiel({
        "id":          f"{niveau}_v{version}",
        "niveau":      niveau,
        "version":     version,
        "description": description or f"Rentrée {version}",
        "etat":        etat,
        "themes":      [{"code": "A", "nom": "Nombres", "couleur": "bleu"}],
        "sequences":   [],
    })


# ── Service : lister_par_niveau ────────────────────────────────────────────────

def test_lister_par_niveau_tri_descendant(sqlite_store):
    """Les référentiels sont retournés du plus récent au plus ancien."""
    _creer_referentiel(sqlite_store, "N10", "2021")
    _creer_referentiel(sqlite_store, "N10", "2024")
    _creer_referentiel(sqlite_store, "N10", "2022")
    _creer_referentiel(sqlite_store, "N10", "2023")

    refs = svc.lister_par_niveau(sqlite_store, "N10")
    versions = [r["version"] for r in refs]
    assert versions == ["2024", "2023", "2022", "2021"]


def test_lister_par_niveau_filtre_bien(sqlite_store):
    """Un autre niveau ne remonte pas dans la liste."""
    _creer_referentiel(sqlite_store, "N10", "2024")
    _creer_referentiel(sqlite_store, "N11", "2024")
    _creer_referentiel(sqlite_store, "N12", "2024")

    refs = svc.lister_par_niveau(sqlite_store, "N11")
    assert len(refs) == 1
    assert refs[0]["niveau"] == "N11"


def test_lister_par_niveau_vide_sans_correspondance(sqlite_store):
    """Niveau absent → liste vide, pas d'erreur."""
    _creer_referentiel(sqlite_store, "N10", "2024")
    assert svc.lister_par_niveau(sqlite_store, "N09") == []


def test_lister_par_niveau_vide_si_niveau_vide(sqlite_store):
    """Niveau '' → liste vide (garde défensive)."""
    _creer_referentiel(sqlite_store, "N10", "2024")
    assert svc.lister_par_niveau(sqlite_store, "") == []


def test_lister_par_niveau_champs_retournes(sqlite_store):
    """Chaque entrée retourne id, niveau, version, description, etat."""
    _creer_referentiel(sqlite_store, "N10", "2024", description="Rentrée 2024")
    r = svc.lister_par_niveau(sqlite_store, "N10")[0]
    assert r["id"] == "N10_v2024"
    assert r["niveau"] == "N10"
    assert r["version"] == "2024"
    assert r["description"] == "Rentrée 2024"
    assert r["etat"] in ("en_cours", "valide", "verrouille")


# ── Service : recommande ───────────────────────────────────────────────────────

def test_recommande_le_plus_recent(sqlite_store):
    _creer_referentiel(sqlite_store, "N10", "2022")
    _creer_referentiel(sqlite_store, "N10", "2024")
    _creer_referentiel(sqlite_store, "N10", "2023")

    reco = svc.recommande(sqlite_store, "N10")
    assert reco is not None
    assert reco["version"] == "2024"


def test_recommande_none_si_aucun_referentiel(sqlite_store):
    """Cas dégradé : message UI 'aucun référentiel disponible pour N09'."""
    assert svc.recommande(sqlite_store, "N09") is None


# ── Route ──────────────────────────────────────────────────────────────────────

def test_route_referentiels_avec_niveau(client, sqlite_store):
    _creer_referentiel(sqlite_store, "N10", "2023")
    _creer_referentiel(sqlite_store, "N10", "2024")

    r = client.get("/api/referentiels?niveau=N10")
    assert r.status_code == 200
    data = r.get_json()
    assert "referentiels" in data
    # Vérif des versions présentes (tri descendant)
    versions = [ref["version"] for ref in data["referentiels"]]
    assert versions[0] == "2024"
    assert "2023" in versions


def test_route_referentiels_niveau_sans_resultat(client, sqlite_store):
    """Aucun référentiel pour N09 → liste vide, status 200."""
    r = client.get("/api/referentiels?niveau=N09")
    assert r.status_code == 200
    assert r.get_json() == {"referentiels": []}


def test_route_referentiels_sans_niveau(client, sqlite_store):
    """Sans param niveau → retourne tout."""
    _creer_referentiel(sqlite_store, "N10", "2024")
    _creer_referentiel(sqlite_store, "N11", "2024")

    r = client.get("/api/referentiels")
    assert r.status_code == 200
    niveaux = {ref["niveau"] for ref in r.get_json()["referentiels"]}
    assert {"N10", "N11"} <= niveaux
