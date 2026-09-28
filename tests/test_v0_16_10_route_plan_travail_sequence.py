"""tests/test_v0_16_10_route_plan_travail_sequence.py — v0.16.10

Régression : le bouton « Compiler le plan de travail » de l'onglet Rendu PDF
de l'atelier d'assemblage appelait POST /api/plans-de-travail/<niveau>/<seq>/pdf,
route supprimée en v0.15.1 → 404. v0.16.10 réintroduit la route en portée
séquence.

On vérifie ici la couche HTTP (route enregistrée + codes de réponse), pas la
compilation PDF (qui exige pdflatex, absent de l'environnement de test). La
génération du .tex, elle, est testable.
"""

import sqlite3
import sys
import tempfile
import shutil
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app


@pytest.fixture
def client(tmp_path):
    # On copie la vraie base applicative : le plan de travail dépend des
    # données de référence (param_niveaux → cycle, sequences_du_cycle, themes)
    # qu'une base vierge n'a pas. Si elle est absente (CI sans données), on
    # peuple le minimum nécessaire.
    src = Path(__file__).parent.parent / 'data' / 'seqenseigne.db'
    if src.exists():
        shutil.copy(src, tmp_path / 'seqenseigne.db')
    app = create_app(tmp_path)
    if not src.exists():
        # Base vierge : poser param_niveaux + un cycle minimal pour N10.
        with app.json_store._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO cycles (code, nom) VALUES ('C04', 'Cycle 4')"
            )
            conn.execute(
                "INSERT OR IGNORE INTO param_niveaux (niveau, cycle_code, nom_court) "
                "VALUES ('N10', 'C04', '5e')"
            )
    return app.test_client(), app


def _une_sequence_peuplee(app):
    """Retourne (niveau, sequence_code) d'une séquence ayant au moins une
    partie, ou None si la base n'en contient pas."""
    with app.json_store._conn() as conn:
        row = conn.execute(
            "SELECT sn.niveau, sn.sequence_code "
            "FROM sequences_par_niveau sn "
            "JOIN sequence_parties p ON p.sequence_par_niveau_id = sn.id "
            "LIMIT 1"
        ).fetchone()
        return (row[0], row[1]) if row else None


class TestRoutePlanTravailSequence:
    def test_route_pdf_enregistree(self, client):
        _, app = client
        rules = [str(r) for r in app.url_map.iter_rules()
                 if 'plans-de-travail' in str(r)]
        assert any('/pdf' in r for r in rules), \
            "La route /api/plans-de-travail/<niveau>/<seq>/pdf doit exister"
        assert any('/tex' in r for r in rules)

    def test_niveau_invalide_400(self, client):
        c, _ = client
        r = c.post('/api/plans-de-travail/N99/S01/tex')
        assert r.status_code == 400

    def test_sequence_inconnue_404(self, client):
        # Niveau valide, séquence garantie absente (S99) → 404 métier.
        c, _ = client
        r = c.post('/api/plans-de-travail/N10/S99/tex')
        assert r.status_code == 404
        assert r.get_json().get('error') == 'sequence_introuvable'

    def test_tex_genere_si_sequence_peuplee(self, client):
        c, app = client
        cible = _une_sequence_peuplee(app)
        if cible is None:
            pytest.skip("Aucune séquence peuplée dans la base de test.")
        niveau, seq = cible
        r = c.post(f'/api/plans-de-travail/{niveau}/{seq}/tex')
        assert r.status_code == 200
        assert r.mimetype == 'text/plain'
        assert 'documentclass' in r.get_data(as_text=True)

    def test_get_aussi_supporte(self, client):
        c, app = client
        cible = _une_sequence_peuplee(app)
        if cible is None:
            pytest.skip("Aucune séquence peuplée dans la base de test.")
        niveau, seq = cible
        r = c.get(f'/api/plans-de-travail/{niveau}/{seq}/tex')
        assert r.status_code == 200
