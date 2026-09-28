"""tests/test_progression_rechercher.py — Tests recherche par triplet.

Couvre :
  - SqliteStore.lire_progression_par_triplet
  - route GET /api/progression/<niveau>/rechercher
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _creer_progression(store, niveau: str, annee: str,
                      etablissement_nom: str = "Collège Test") -> dict:
    """
    Crée une progression via ecrire_progression (qui crée l'établissement au
    passage si absent), puis retourne le dict enrichi (inclut etablissement_id).
    """
    prog = {
        "niveau":        niveau,
        "annee":         annee,
        "etablissement": etablissement_nom,
        "source":        "manuel",
        "etat":          "en_cours",
        "creneaux":      [],
    }
    store.ecrire_progression(prog)
    return prog  # ecrire_progression a rempli id + etablissement_id


# ── Méthode store ──────────────────────────────────────────────────────────────

def test_lire_progression_par_triplet_trouve(sqlite_store):
    prog = _creer_progression(sqlite_store, "N10", "2025-2026", "Collège A")
    etab_id = prog["etablissement_id"]

    result = sqlite_store.lire_progression_par_triplet("N10", "2025-2026", etab_id)
    assert result is not None
    assert result["niveau"] == "N10"
    assert result["annee"] == "2025-2026"
    assert result["etablissement_id"] == etab_id


def test_lire_progression_par_triplet_none_si_annee_inconnue(sqlite_store):
    prog = _creer_progression(sqlite_store, "N10", "2025-2026", "Collège A")
    result = sqlite_store.lire_progression_par_triplet(
        "N10", "2099-2100", prog["etablissement_id"]
    )
    assert result is None


def test_lire_progression_par_triplet_none_si_etablissement_inconnu(sqlite_store):
    _creer_progression(sqlite_store, "N10", "2025-2026", "Collège A")
    result = sqlite_store.lire_progression_par_triplet(
        "N10", "2025-2026", "et_inexistant"
    )
    assert result is None


def test_lire_progression_par_triplet_discrimine_niveau(sqlite_store):
    """Même année + même établissement mais niveau différent → introuvable."""
    prog_n10 = _creer_progression(sqlite_store, "N10", "2025-2026", "Collège A")
    etab_id = prog_n10["etablissement_id"]

    result = sqlite_store.lire_progression_par_triplet(
        "N11", "2025-2026", etab_id
    )
    assert result is None


def test_lire_progression_par_triplet_deux_etablissements(sqlite_store):
    """Deux établissements, même niveau+année → chacun sa progression."""
    prog_a = _creer_progression(sqlite_store, "N10", "2025-2026", "Collège A")
    prog_b = _creer_progression(sqlite_store, "N10", "2025-2026", "Collège B")

    r_a = sqlite_store.lire_progression_par_triplet(
        "N10", "2025-2026", prog_a["etablissement_id"]
    )
    r_b = sqlite_store.lire_progression_par_triplet(
        "N10", "2025-2026", prog_b["etablissement_id"]
    )
    assert r_a is not None and r_b is not None
    assert r_a["etablissement_id"] != r_b["etablissement_id"]


# ── Route ──────────────────────────────────────────────────────────────────────

def test_route_rechercher_cas_nominal(client, sqlite_store):
    prog = _creer_progression(sqlite_store, "N11", "2025-2026", "Collège X")
    etab_id = prog["etablissement_id"]

    r = client.get(
        f"/api/progression/N11/rechercher?annee=2025-2026&etablissement_id={etab_id}"
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["trouve"] is True
    assert data["progression"]["annee"] == "2025-2026"
    assert data["progression"]["niveau"] == "N11"


def test_route_rechercher_zero_resultat(client, sqlite_store):
    """Aucune progression pour ce triplet → 200 avec trouve:false."""
    # On crée une progression sur un autre triplet pour ne pas partir d'une base vide
    _creer_progression(sqlite_store, "N10", "2025-2026", "Collège X")

    r = client.get(
        "/api/progression/N11/rechercher"
        "?annee=2099-2100&etablissement_id=et_xxx"
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["trouve"] is False
    assert data["triplet"]["niveau"] == "N11"
    assert data["triplet"]["annee"] == "2099-2100"


def test_route_rechercher_400_si_annee_manquante(client):
    r = client.get(
        "/api/progression/N10/rechercher?etablissement_id=et_abc"
    )
    assert r.status_code == 400


def test_route_rechercher_400_si_etablissement_manquant(client):
    r = client.get(
        "/api/progression/N10/rechercher?annee=2025-2026"
    )
    assert r.status_code == 400


def test_route_rechercher_400_si_parametres_vides(client):
    r = client.get("/api/progression/N10/rechercher?annee=&etablissement_id=")
    assert r.status_code == 400


def test_route_rechercher_discrimine_niveau(client, sqlite_store):
    """Même (année, établissement) mais niveau différent → trouve:false."""
    prog = _creer_progression(sqlite_store, "N10", "2025-2026", "Collège X")
    etab_id = prog["etablissement_id"]

    r = client.get(
        f"/api/progression/N11/rechercher?annee=2025-2026&etablissement_id={etab_id}"
    )
    assert r.status_code == 200
    assert r.get_json()["trouve"] is False
