"""tests/test_v0_15_2_2_3_erreur_copie_pdf.py — v0.15.2.2.3

Test du bugfix « toast rouge sans détail » sur l'atelier référentiel.

Symptôme d'origine : quand la compilation d'un document réussit
(PDF produit) mais que la copie du PDF vers son nom métier échoue,
l'exception était avalée silencieusement (`ok_global=False` sans message).
L'UI affichait un toast rouge sans aucune erreur détaillée, et le résumé
de cible indiquait `ok=True` (incohérent).

Le correctif :
  - capture le message d'exception de la copie
  - l'injecte dans `premieres_erreurs` de la cible
  - marque la cible comme `ok=False` (cohérence avec `ok_global`)
  - logge l'erreur côté serveur
"""
from __future__ import annotations

from pathlib import Path
import json
import uuid
from unittest.mock import patch

import pytest

from services import referentiel_documents as svc_cat
from services import referentiel_documents_compilation as svc_cmp
from services import orchestrateur_compilation as orch
from services.orchestrateur_compilation import ResultatOrchestration


def _conn(store):
    return store._conn()


def _creer_referentiel_minimal(conn, niveau='N10'):
    ref_id = f"ref_test_{uuid.uuid4().hex[:8]}"
    conn.execute("""
        INSERT INTO referentiel_niveaux
            (id, niveau, version, date_debut, date_fin, description, etat)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ref_id, niveau, '2025_test', '2025-09-01', '2026-08-31',
          'Test', 'en_cours'))
    conn.commit()
    return ref_id


def _activer_doc_cours(store, ref_id):
    """Active un document de type unitaire (livret_cours) et renvoie son id."""
    with _conn(store) as conn:
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = next(d for d in docs if d['type_document'] == 'livret_cours')
        svc_cat.maj_options(conn, doc['id'], {'actif': True})
        conn.commit()
    return doc['id']


def test_erreur_copie_pdf_remontee_dans_premieres_erreurs(sqlite_store, tmp_path):
    """v0.15.2.2.3 — Si la copie du PDF au nom métier échoue, le message
    d'erreur doit apparaître dans premieres_erreurs et la cible doit être
    marquée ok=False (plus de « toast rouge sans détail »).
    """
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
    doc_id = _activer_doc_cours(sqlite_store, ref_id)

    # PDF d'artefact bidon (existe, lisible)
    faux_pdf = tmp_path / 'unique.pdf'
    faux_pdf.write_bytes(b'%PDF-1.5 fake')

    # Mock orch.compiler : compilation réussie avec chemin_pdf valide
    def fake_compiler(**kwargs):
        return ResultatOrchestration(
            ok=True,
            pdf_bytes=b'%PDF-1.5 fake',
            log_complet='Output written on atome.pdf (1 page).',
            tex_source='\\documentclass{article}\\begin{document}x\\end{document}',
            erreurs=[],
            duree_ms=1234,
            type_echec=None,
            chemin_pdf=faux_pdf,
        )

    # On force l'échec de la copie : write_bytes lève une PermissionError
    # (simule un fichier verrouillé par un viewer PDF ou l'antivirus).
    orig_write_bytes = Path.write_bytes

    def fake_write_bytes(self, data):
        if self.name.endswith('.pdf') and 'referentiels' in str(self):
            raise PermissionError("fichier verrouillé (simulation)")
        return orig_write_bytes(self, data)

    with patch.object(orch, 'compiler', side_effect=fake_compiler):
        with patch.object(Path, 'write_bytes', fake_write_bytes):
            resultat = svc_cmp.compiler_document(sqlite_store, doc_id)

    # ok_global doit être False
    assert resultat['compile_ok'] is False

    # Le log JSON doit contenir l'erreur de copie avec un message exploitable
    log = json.loads(resultat['log_json'])
    cibles = log['cibles']
    assert len(cibles) == 1
    cible = cibles[0]
    # La cible est marquée ko (cohérence)
    assert cible['ok'] is False
    # type_echec = copie_pdf
    assert cible['type_echec'] == 'copie_pdf'
    # Le message d'erreur est présent et mentionne la copie
    assert cible['nb_erreurs'] >= 1
    messages = [e['message'] for e in cible['premieres_erreurs']]
    assert any('copie' in m.lower() for m in messages), (
        f"Le message d'erreur de copie doit être remonté. Messages : {messages}"
    )
    assert any('PermissionError' in m or 'verrouillé' in m for m in messages), (
        f"Le type/détail de l'exception doit être visible. Messages : {messages}"
    )


def test_compilation_reussie_sans_erreur_copie(sqlite_store, tmp_path):
    """v0.15.2.2.3 — Cas nominal : compilation OK + copie OK → ok_global=True,
    cible ok=True, aucune erreur.
    """
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
    doc_id = _activer_doc_cours(sqlite_store, ref_id)

    faux_pdf = tmp_path / 'unique.pdf'
    faux_pdf.write_bytes(b'%PDF-1.5 fake')

    def fake_compiler(**kwargs):
        return ResultatOrchestration(
            ok=True,
            pdf_bytes=b'%PDF-1.5 fake',
            log_complet='Output written on atome.pdf (1 page).',
            tex_source='x',
            erreurs=[],
            duree_ms=100,
            type_echec=None,
            chemin_pdf=faux_pdf,
        )

    with patch.object(orch, 'compiler', side_effect=fake_compiler):
        resultat = svc_cmp.compiler_document(sqlite_store, doc_id)

    assert resultat['compile_ok'] is True
    log = json.loads(resultat['log_json'])
    cible = log['cibles'][0]
    assert cible['ok'] is True
    assert cible['type_echec'] is None
    assert cible['nb_erreurs'] == 0


def test_compilation_ok_mais_chemin_pdf_absent(sqlite_store, tmp_path):
    """v0.15.2.2.3 — Cas où res.ok=True mais chemin_pdf=None (échec
    d'écriture d'artefact côté orchestrateur). Doit être signalé
    explicitement, pas silencieusement.
    """
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
    doc_id = _activer_doc_cours(sqlite_store, ref_id)

    def fake_compiler(**kwargs):
        return ResultatOrchestration(
            ok=True,
            pdf_bytes=b'%PDF-1.5 fake',
            log_complet='Output written.',
            tex_source='x',
            erreurs=[],
            duree_ms=100,
            type_echec=None,
            chemin_pdf=None,  # ← pas de PDF d'artefact
        )

    with patch.object(orch, 'compiler', side_effect=fake_compiler):
        resultat = svc_cmp.compiler_document(sqlite_store, doc_id)

    assert resultat['compile_ok'] is False
    log = json.loads(resultat['log_json'])
    cible = log['cibles'][0]
    assert cible['ok'] is False
    messages = [e['message'] for e in cible['premieres_erreurs']]
    assert any('artefact' in m.lower() or 'aucun pdf' in m.lower()
               for m in messages), (
        f"L'absence de PDF d'artefact doit être signalée. Messages : {messages}"
    )
