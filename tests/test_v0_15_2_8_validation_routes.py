"""tests/test_v0_15_2_8_validation_routes.py — v0.15.2.8 (partie B1)

Routes API de l'auto-validation :
  GET  /api/referentiels/<ref_id>/eligibilite_validation
  POST /api/referentiels/<ref_id>/revalider

Et branchement lazy automatique sur GET /api/referentiels?niveau=...
"""
from __future__ import annotations

from pathlib import Path
import sys
import uuid
import json

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def _store_de(app):
    return app.json_store


def _ref(conn, etat='en_cours', niveau='N10'):
    rid = f"ref_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO referentiel_niveaux
        (id, niveau, version, date_debut, date_fin, description, etat)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (rid, niveau, '2025_test', '2025-09-01', '2026-08-31',
         'Test', etat))
    return rid


def _atome_exo(conn, niveau, *, etat='valide'):
    aid = f"a_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO exercices
        (id, niveau, sequence, num, serie, titre, enonce, corrige,
         etat_code, mtime)
        VALUES (?, ?, 'S01', 1, 'F', 'T', '', '', ?, '2026-01-01 00:00:00')""",
        (aid, niveau, etat))


# ── GET /eligibilite_validation ─────────────────────────────────────────────


def test_get_eligibilite_inconnu_renvoie_404(client):
    rep = client.get("/api/referentiels/ref_inexistant/eligibilite_validation")
    assert rep.status_code == 404


def test_get_eligibilite_referentiel_vide_est_eligible(client, app):
    with _store_de(app)._conn() as conn:
        rid = _ref(conn)
        conn.commit()
    rep = client.get(f"/api/referentiels/{rid}/eligibilite_validation")
    assert rep.status_code == 200
    data = rep.get_json()
    assert data['eligible'] is True
    assert data['raisons'] == []
    assert data['etat_courant'] == 'en_cours'
    assert data['niveau'] == 'N10'


def test_get_eligibilite_atome_non_valide_donne_raison(client, app):
    with _store_de(app)._conn() as conn:
        rid = _ref(conn)
        _atome_exo(conn, 'N10', etat='en_cours')
        conn.commit()
    rep = client.get(f"/api/referentiels/{rid}/eligibilite_validation")
    data = rep.get_json()
    assert data['eligible'] is False
    assert any('exercice' in r for r in data['raisons'])
    assert data['details']['atomes_non_valides']['exercices'] == 1


def test_get_eligibilite_ne_modifie_pas_l_etat(client, app):
    """GET = lecture pure. Même éligible, l'état ne change pas."""
    with _store_de(app)._conn() as conn:
        rid = _ref(conn, etat='en_cours')
        conn.commit()
    rep = client.get(f"/api/referentiels/{rid}/eligibilite_validation")
    assert rep.get_json()['eligible'] is True
    # État inchangé
    with _store_de(app)._conn() as conn:
        row = conn.execute(
            "SELECT etat FROM referentiel_niveaux WHERE id=?", (rid,)
        ).fetchone()
    assert row['etat'] == 'en_cours'


# ── POST /revalider ─────────────────────────────────────────────────────────


def test_post_revalider_inconnu_renvoie_404(client):
    rep = client.post("/api/referentiels/ref_inexistant/revalider")
    assert rep.status_code == 404


def test_post_revalider_applique_la_transition(client, app):
    with _store_de(app)._conn() as conn:
        rid = _ref(conn, etat='en_cours')
        conn.commit()
    rep = client.post(f"/api/referentiels/{rid}/revalider")
    assert rep.status_code == 200
    data = rep.get_json()
    assert data['etat'] == 'valide'
    assert data['diagnostic']['eligible'] is True
    # Persisté en BDD
    with _store_de(app)._conn() as conn:
        row = conn.execute(
            "SELECT etat FROM referentiel_niveaux WHERE id=?", (rid,)
        ).fetchone()
    assert row['etat'] == 'valide'


def test_post_revalider_ne_touche_pas_fige(client, app):
    with _store_de(app)._conn() as conn:
        rid = _ref(conn, etat='verrouille')
        _atome_exo(conn, 'N10', etat='en_cours')  # non éligible
        conn.commit()
    rep = client.post(f"/api/referentiels/{rid}/revalider")
    assert rep.status_code == 200
    assert rep.get_json()['etat'] == 'verrouille'


# ── Lazy auto sur GET /api/referentiels?niveau=N10 ──────────────────────────


def test_lister_referentiels_applique_lazy(client, app):
    """Effet bout-en-bout : un référentiel `en_cours` éligible doit
    apparaître `valide` après simple GET (lazy automatique)."""
    with _store_de(app)._conn() as conn:
        rid = _ref(conn, etat='en_cours')
        conn.commit()
    rep = client.get("/api/referentiels?niveau=N10")
    assert rep.status_code == 200
    payload = rep.get_json()
    refs = payload['referentiels']
    cible = next((r for r in refs if r['id'] == rid), None)
    assert cible is not None
    # Le simple GET a basculé l'état
    assert cible['etat'] == 'valide'
