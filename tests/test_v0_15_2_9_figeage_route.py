"""tests/test_v0_15_2_9_figeage_route.py — v0.15.2.9 (partie B2)

Route POST /api/referentiels/<id>/figer après v0.15.2.9 — appelle
`verrouiller_complet` avec :
- vérification éligibilité,
- génération trace,
- copie PDF,
- transition d'état.

Comportements protégés :
- Référentiel introuvable → 404.
- État != 'valide' → 409.
- Non éligible (atome en_cours) → 409 avec message explicite.
- Cas nominal : 200 + fige + trace écrite sur disque.
- Cas concurrents avec force_confirme=False → 200 + confirmation_requise.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def _store(app):
    return app.json_store


def _ref(conn, etat='valide', niveau='N10', version='2025_v1'):
    rid = f"ref_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO referentiel_niveaux
        (id, niveau, version, date_debut, date_fin, description, etat)
        VALUES (?, ?, ?, '2025-09-01', '2026-08-31', 'Test', ?)""",
        (rid, niveau, version, etat))
    return rid


def _exo(conn, niveau='N10', sequence='S01', num=1, etat='valide'):
    conn.execute("""INSERT INTO exercices
        (id, niveau, sequence, num, serie, titre, enonce, corrige,
         etat_code, mtime)
        VALUES (?, ?, ?, ?, 'F', 'T', '', '', ?, '2026-01-01 00:00:00')""",
        (f"e_{uuid.uuid4().hex[:8]}", niveau, sequence, num, etat))


def test_figer_introuvable_renvoie_404(client):
    rep = client.post("/api/referentiels/inexistant/figer",
                       json={'force_confirme': True})
    assert rep.status_code == 404


def test_figer_non_valide_renvoie_409(client, app):
    """Référentiel en_cours → 409 avec message."""
    with _store(app)._conn() as conn:
        rid = _ref(conn, etat='en_cours')
        conn.commit()
    rep = client.post(f"/api/referentiels/{rid}/figer",
                       json={'force_confirme': True})
    assert rep.status_code == 409


def test_figer_non_eligible_renvoie_409(client, app):
    """Référentiel valide MAIS avec un exo en_cours → non éligible → 409."""
    with _store(app)._conn() as conn:
        rid = _ref(conn, etat='valide')
        _exo(conn, etat='en_cours')
        conn.commit()
    rep = client.post(f"/api/referentiels/{rid}/figer",
                       json={'force_confirme': True})
    assert rep.status_code == 409
    msg = rep.get_json().get('error', '')
    assert 'éligible' in msg or 'eligible' in msg


def test_figer_succes_change_etat_et_ecrit_trace(client, app):
    """Cas nominal : transition + fichier trace.json présent sur disque."""
    with _store(app)._conn() as conn:
        rid = _ref(conn, etat='valide')
        conn.commit()
    rep = client.post(f"/api/referentiels/{rid}/figer",
                       json={'force_confirme': True})
    assert rep.status_code == 200
    data = rep.get_json()
    assert data['confirmation_requise'] is False
    assert data['ref']['etat'] == 'verrouille'

    # Trace sur disque
    chemin_trace = Path(data['verrouille']['trace'])
    assert chemin_trace.is_file()
    trace = json.loads(chemin_trace.read_text(encoding='utf-8'))
    assert trace['referentiel']['id'] == rid
    assert trace['version_schema'] == 2   # v0.15.2.11


def test_figer_concurrent_sans_force_confirme_renvoie_confirmation(
        client, app):
    """Concurrent présent + force_confirme par défaut (False) →
    confirmation_requise=True, aucune modif BDD ni disque."""
    with _store(app)._conn() as conn:
        _ref(conn, etat='valide', niveau='N10', version='2025_v0')  # concurrent
        rid = _ref(conn, etat='valide', niveau='N10', version='2025_v1')
        conn.commit()
    rep = client.post(f"/api/referentiels/{rid}/figer", json={})
    assert rep.status_code == 200
    data = rep.get_json()
    assert data['confirmation_requise'] is True
    # Référentiel cible toujours 'valide'
    with _store(app)._conn() as conn:
        row = conn.execute(
            "SELECT etat FROM referentiel_niveaux WHERE id=?", (rid,)
        ).fetchone()
    assert row['etat'] == 'valide'
