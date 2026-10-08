"""tests/test_v0_51_0_profils.py — v0.51.0

Profils de lancement (séparation de l'appli en deux outils) :
  - complet (défaut) : tout, comme avant ;
  - atelier : conception des référentiels (LaTeX) ;
  - classe  : suivi des classes (sans LaTeX), structure en lecture seule.
"""
import tempfile
from pathlib import Path

import pytest

from app import create_app
from services import profils

# Blueprints qui compilent du LaTeX ou éditent les atomes : jamais dans le
# profil classe.
BP_COMPILATION = {"rendu_atome", "referentiel_documents_compilation",
                  "livret_sequence", "plans_de_travail", "evaluations",
                  "cartes_automatisme", "fiches_resume", "atomes", "paquet",
                  "v2_edition"}


def _app(profil):
    a = create_app(Path(tempfile.mkdtemp()) / "data", profil=profil)
    a.config["TESTING"] = True
    return a


@pytest.fixture(scope="module")
def apps():
    return {p: _app(p) for p in profils.PROFILS}


# ── Lecture du profil ────────────────────────────────────────────────────────

def test_profil_par_defaut_et_variable(monkeypatch):
    monkeypatch.delenv("SEQ_PROFIL", raising=False)
    assert profils.profil_courant() == "complet"
    monkeypatch.setenv("SEQ_PROFIL", " Classe ")
    assert profils.profil_courant() == "classe"
    assert profils.profil_courant("atelier") == "atelier"
    with pytest.raises(ValueError):
        profils.profil_courant("tout")


def test_classification_complete(apps):
    app = apps["complet"]
    connus = (profils.BP_ATELIER | profils.BP_STRUCTURE | profils.BP_CLASSE
              | profils.BP_COMMUN)
    assert set(app.blueprints) <= connus, set(app.blueprints) - connus
    endpoints = {r.endpoint for r in app.url_map.iter_rules()}
    assert set(profils.ENDPOINTS) <= endpoints, set(profils.ENDPOINTS) - endpoints


def test_profil_complet_inchange(apps):
    """En complet, tous les blueprints sont enregistrés, sans garde."""
    app = apps["complet"]
    assert app.config["SEQ_PROFIL"] == "complet"
    assert set(app.blueprints) == (profils.BP_ATELIER | profils.BP_STRUCTURE
                                   | profils.BP_CLASSE | profils.BP_COMMUN)
    c = app.test_client()
    assert c.get("/api/classes").status_code == 200
    assert c.get("/api/tableau-bord/atomes-en-cours").status_code == 200
    assert c.get("/api/tableau-bord/seances-semaine").status_code == 200
    # L'import de classes historiques existe (400 = paramètres manquants).
    assert c.post("/api/import/historique", json={}).status_code == 400


# ── Profil classe ────────────────────────────────────────────────────────────

def test_classe_sans_compilation(apps):
    app = apps["classe"]
    assert not (set(app.blueprints) & BP_COMPILATION)
    assert not (set(app.blueprints) & (profils.BP_ATELIER - {"admin"}))
    # Les routes de compilation restées dans admin sont refusées.
    c = app.test_client()
    for url in ("/api/admin/compilation-atomes/preview",
                "/api/admin/compilation-atomes/run"):
        r = c.get(url)
        assert r.status_code == 404 and r.get_json()["code"] == "profil"


def test_classe_toutes_les_routes_atelier_refusees(apps):
    """Chaque route enregistrée dans le profil classe est soit autorisée, soit
    refusée par le garde : aucune route de conception n'y est joignable."""
    app = apps["classe"]
    for r in app.url_map.iter_rules():
        for m in r.methods - {"HEAD", "OPTIONS"}:
            ok, code = profils.autorise("classe", r.endpoint, m)
            cat = profils.categorie(r.endpoint)
            if cat in ("atelier", "complet"):
                assert not ok and code == 404, r.endpoint
            if cat == "structure" and m != "GET":
                assert not ok and code == 403, (r.endpoint, m)


def test_classe_structure_en_lecture_seule(apps):
    c = apps["classe"].test_client()
    assert c.get("/api/referentiels?niveau=N11").status_code == 200
    assert c.get("/api/referentiels-principaux-externes?niveau=N11").status_code == 200
    assert c.get("/api/types-documents").status_code == 200
    r = c.post("/api/referentiels/coquille", json={"niveau": "N11"})
    assert r.status_code == 403
    assert r.get_json()["code"] == "profil"
    assert "appli locale" in r.get_json()["error"]
    assert c.post("/api/referentiels-principaux-externes",
                  json={"niveau": "N11"}).status_code == 403
    assert c.post("/api/types-documents", json={"libelle": "X"}).status_code == 403


def test_classe_routes_de_classe_et_communes(apps):
    c = apps["classe"].test_client()
    for url in ("/api/classes", "/api/admin/annees", "/api/referentiel/niveaux",
                "/api/admin/statut", "/api/tableau-bord/seances-semaine",
                "/api/preferences/type_mise_en_route", "/api/annees-scolaires"):
        assert c.get(url).status_code == 200, url
    assert c.get("/api/tableau-bord/atomes-en-cours").status_code == 404
    # Outils de transition : profil complet seulement.
    assert c.post("/api/import/historique", json={}).status_code == 404
    assert c.post("/api/admin/reset/tout").status_code == 404
    assert c.post("/api/admin/reset/reference").status_code == 404


# ── Profil atelier ───────────────────────────────────────────────────────────

def test_atelier_sans_routes_de_classe(apps):
    app = apps["atelier"]
    assert not (set(app.blueprints) & profils.BP_CLASSE)
    c = app.test_client()
    for url in ("/api/classes", "/api/seance?classe_id=x", "/api/edt",
                "/api/tableau-bord/seances-semaine", "/api/admin/etablissements"):
        assert c.get(url).status_code == 404, url
    assert c.post("/api/admin/reset/suivi").status_code == 404
    assert c.post("/api/admin/reset/tout").status_code == 404


def test_atelier_conception_et_communes(apps):
    c = apps["atelier"].test_client()
    for url in ("/api/tableau-bord/atomes-en-cours",
                "/api/tableau-bord/atomes-non-rattaches",
                "/api/referentiels?niveau=N11", "/api/admin/annees",
                "/api/referentiel/niveaux", "/api/admin/statut",
                "/api/types-documents"):
        assert c.get(url).status_code == 200, url
    r = c.post("/api/types-documents", json={"libelle": "Fiche méthode"})
    assert r.status_code in (200, 201)


# ── Page principale ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("profil", profils.PROFILS)
def test_page_porte_le_profil(apps, profil):
    html = apps[profil].test_client().get("/").get_data(as_text=True)
    assert f'<html lang="fr" data-profil="{profil}">' in html
    assert f'window.SEQ_PROFIL = "{profil}";' in html
    assert ('class="logo-profil"' in html) == (profil != "complet")
    # Onglets marqués par profil.
    assert 'data-tab="ateliers" data-profils="atelier"' in html
    assert 'data-tab="planification" data-profils="classe"' in html
    assert 'id="admin-importsuivi-btn" data-profils="complet"' in html
