"""tests/test_v0_15_2_9_figeage.py — v0.15.2.9 (partie B2)

Action de figeage complète : trace JSON + copie PDF + transition d'état.

Couvre :
- Génération de la trace (structure, champs requis, contenu pertinent).
- Refus si non éligible (atomes/évals/docs non valides).
- Refus si état != valide.
- Comportement « concurrence » : confirmation_requise renvoyée sans
  modifier la BDD ni les fichiers.
- En succès : trace.json créé, PDF copiés, état → ('verrouille',) concurrents
  → 'annule'.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.referentiel_figeage import (  # noqa: E402
    verrouiller_complet, generer_trace, copier_pdfs, VERSION_SCHEMA_TRACE,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _conn(store):
    return store._conn()


def _ref(conn, etat='valide', niveau='N10', version='2025_v1'):
    rid = f"ref_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO referentiel_niveaux
        (id, niveau, version, date_debut, date_fin, description, etat)
        VALUES (?, ?, ?, '2025-09-01', '2026-08-31', 'Test', ?)""",
        (rid, niveau, version, etat))
    return rid


def _theme(conn, ref_id, code='T01'):
    conn.execute("""INSERT INTO referentiel_themes
        (referentiel_id, code, nom, couleur)
        VALUES (?, ?, 'Nombres et calculs', 'nombres')""",
        (ref_id, code))


def _seq_referentiel(conn, ref_id, code='S01', numero=1, theme_code='T01'):
    conn.execute("""INSERT INTO referentiel_sequences
        (referentiel_id, code, numero, nom, theme_code)
        VALUES (?, ?, ?, 'Séquence test', ?)""",
        (ref_id, code, numero, theme_code))


def _seq_par_niveau(conn, niveau='N10', sequence_code='S01'):
    sid = f"sn_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO sequences_par_niveau
        (id, niveau, sequence_code, parametres)
        VALUES (?, ?, ?, '')""",
        (sid, niveau, sequence_code))
    return sid


def _partie(conn, sn_id, numero=1, nb_seances=1.5):
    conn.execute("""INSERT INTO sequence_parties
        (id, sequence_par_niveau_id, numero, nb_seances_R_AE)
        VALUES (?, ?, ?, ?)""",
        (f"pt_{uuid.uuid4().hex[:8]}", sn_id, numero, nb_seances))


def _objectif_ref(conn, ref_id, seq_code='S01', code='01'):
    conn.execute("""INSERT INTO referentiel_objectifs
        (referentiel_id, seq_code, code, nom, fin_cycle,
         critere_f, critere_a, critere_e, partie_numero, nb_seances)
        VALUES (?, ?, ?, 'Connaître X', 1, 'cf', 'ca', 'ce', 1, 0.5)""",
        (ref_id, seq_code, code))


def _exo(conn, niveau='N10', sequence='S01', num=1, etat='valide'):
    aid = f"ex_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO exercices
        (id, niveau, sequence, num, serie, titre, enonce, corrige,
         etat_code, mtime)
        VALUES (?, ?, ?, ?, 'F', 'Exo test', '', '', ?,
                '2026-01-01 00:00:00')""",
        (aid, niveau, sequence, num, etat))
    return aid


def _notion(conn, niveau='N10', sequence='S01', num=1, etat='valide'):
    aid = f"no_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO notions
        (id, niveau, sequence, num_connaissance, titre, corps,
         etat_code, mtime)
        VALUES (?, ?, ?, ?, 'Notion test', '', ?,
                '2026-01-01 00:00:00')""",
        (aid, niveau, sequence, num, etat))
    return aid


def _doc(conn, ref_id, type_doc='livret_sequence', *, actif=True,
         compile_ok=1, compile_date='2026-03-01 12:00:00'):
    did = f"d_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO referentiel_documents
        (id, referentiel_id, type_document, options, ordre, mtime,
         compile_ok, compile_date, compile_log, compile_en_cours)
        VALUES (?, ?, ?, ?, 1, '2026-01-01', ?, ?, NULL, 0)""",
        (did, ref_id, type_doc, json.dumps({'actif': actif}),
         compile_ok, compile_date))
    return did


def _lister_cibles_factice(conn, doc_id, ref_id, type_doc):
    """Factice : retourne 1 cible avec nom_fichier conventionnel."""
    return [{
        'cible_id':    f"{ref_id}/cible0",
        'libelle':     f"{type_doc} (cible 0)",
        'nom_fichier': f"{type_doc}.pdf",
    }]


# ── Génération de la trace ────────────────────────────────────────────────


def test_trace_structure_minimale(sqlite_store):
    """La trace contient les sections principales et la version du schéma."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    assert trace['version_schema'] == VERSION_SCHEMA_TRACE
    assert 'date_figeage' in trace
    assert trace['referentiel']['id'] == rid
    assert trace['referentiel']['niveau'] == 'N10'
    # Sections présentes même vides
    for k in ('themes', 'sequences', 'evaluations', 'documents'):
        assert k in trace


def test_trace_contient_themes_du_referentiel(sqlite_store):
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _theme(conn, rid, code='T01')
        _theme(conn, rid, code='T02')
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    codes = [t['code'] for t in trace['themes']]
    assert codes == ['T01', 'T02']


def test_trace_contient_sequence_avec_parties_objectifs_atomes(sqlite_store):
    """Test bout-en-bout : une séquence complète avec parties pédagogiques,
    objectifs DANS chaque partie (v0.15.2.11) et atomes liés aux objectifs.
    """
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _theme(conn, rid, 'T01')
        _seq_referentiel(conn, rid, 'S01', 1, 'T01')
        sn = _seq_par_niveau(conn, 'N10', 'S01')
        # On insère les parties et on récupère leurs ids
        import uuid as _uu
        pid1 = f"pt_{_uu.uuid4().hex[:8]}"
        pid2 = f"pt_{_uu.uuid4().hex[:8]}"
        conn.execute("""INSERT INTO sequence_parties
            (id, sequence_par_niveau_id, numero, nb_seances_R_AE)
            VALUES (?, ?, 1, 1.5), (?, ?, 2, 2.0)""",
            (pid1, sn, pid2, sn))
        # Un objectif "Cours" (01) dans la partie 1, sans méthode/exo
        conn.execute("""INSERT INTO objectifs
            (id, partie_id, code, nom, methode_id, fin_cycle, nb_seances)
            VALUES ('obj_01', ?, '01', 'Connaître…', NULL, 1, 0.5)""",
            (pid1,))
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    assert len(trace['sequences']) == 1
    seq = trace['sequences'][0]
    assert seq['code'] == 'S01'
    assert [p['numero'] for p in seq['parties']] == [1, 2]
    # Objectifs sous parties (v0.15.2.11)
    p1 = seq['parties'][0]
    assert 'objectifs' in p1
    assert len(p1['objectifs']) == 1
    obj01 = p1['objectifs'][0]
    assert obj01['code'] == '01'
    # v0.15.2.12 — Objectif "Cours" (code 01) : pas de methodes/notions/exercices,
    # mais porte la liste agrégée des fiches_resume de la partie.
    assert 'methodes'  not in obj01
    assert 'notions'   not in obj01
    assert 'exercices' not in obj01
    assert 'fiches_resume' in obj01


def test_trace_documents_inclut_actifs_compiles_seulement(sqlite_store):
    """Documents inactifs et non compilés sont EXCLUS de la trace."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _doc(conn, rid, 'livret_sequence', actif=True,  compile_ok=1)
        _doc(conn, rid, 'livret_fiches',   actif=False, compile_ok=1)
        _doc(conn, rid, 'livret_corriges', actif=True,  compile_ok=0)
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    types = [d['type_document'] for d in trace['documents']]
    assert types == ['livret_sequence']


def test_trace_documents_chemin_pdf_relatif(sqlite_store):
    """Le chemin PDF dans la trace est relatif au dossier `_fige`."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn)
        _doc(conn, rid, 'livret_sequence', actif=True, compile_ok=1)
        conn.commit()
        trace = generer_trace(conn, rid, _lister_cibles_factice)
    chemin = trace['documents'][0]['cibles'][0]['chemin_pdf']
    assert chemin == 'pdfs/livret_sequence.pdf'
    assert not chemin.startswith('/'), \
        "Le chemin doit être relatif (dossier _fige déplaçable)."


# ── Copie des PDF ─────────────────────────────────────────────────────────


def test_copier_pdfs_copie_les_actifs(sqlite_store, tmp_path):
    """Si le PDF source existe, il est copié dans `pdfs/`."""
    # Setup fichiers
    src = tmp_path / 'src'
    src.mkdir()
    (src / 'livret_sequence.pdf').write_bytes(b'%PDF-1.7 fake content')
    cible = tmp_path / 'fige'
    trace = {'documents': [{
        'type_document': 'livret_sequence',
        'cibles': [{'nom_fichier': 'livret_sequence.pdf'}],
    }]}
    rapport = copier_pdfs(trace, src, cible)
    assert len(rapport['copies']) == 1
    assert rapport['echecs'] == []
    assert (cible / 'pdfs' / 'livret_sequence.pdf').read_bytes() \
        == b'%PDF-1.7 fake content'


def test_copier_pdfs_pdf_source_absent_remontee_echec(tmp_path):
    """PDF source manquant → entrée dans `echecs`, pas d'exception."""
    src = tmp_path / 'src'
    src.mkdir()
    cible = tmp_path / 'fige'
    trace = {'documents': [{
        'type_document': 'livret_sequence',
        'cibles': [{'nom_fichier': 'manquant.pdf'}],
    }]}
    rapport = copier_pdfs(trace, src, cible)
    assert rapport['copies'] == []
    assert len(rapport['echecs']) == 1
    assert 'manquant.pdf' in rapport['echecs'][0]['nom_fichier']


# ── verrouiller_complet — flux complet ──────────────────────────────────────────


def test_verrouiller_complet_non_eligible_leve(sqlite_store, tmp_path):
    """Si un atome est en_cours, le figeage est refusé."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn, etat='valide')
        _exo(conn, 'N10', 'S01', num=1, etat='en_cours')   # non valide
        conn.commit()
        with pytest.raises(ValueError) as excinfo:
            verrouiller_complet(conn, rid, tmp_path, _lister_cibles_factice,
                          force_confirme=True)
    assert 'non éligible' in str(excinfo.value)


def test_verrouiller_complet_etat_non_valide_leve(sqlite_store, tmp_path):
    """Si état != 'valide', refus."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn, etat='en_cours')  # pas valide
        conn.commit()
        with pytest.raises(ValueError):
            verrouiller_complet(conn, rid, tmp_path, _lister_cibles_factice,
                          force_confirme=True)


def test_verrouiller_complet_succes_creee_trace_et_change_etat(sqlite_store,
                                                           tmp_path):
    """Cas nominal : trace écrite, état passe à ('verrouille',) date_debut posée."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn, etat='valide')
        _theme(conn, rid, 'T01')
        _seq_referentiel(conn, rid, 'S01', 1, 'T01')
        conn.commit()
        res = verrouiller_complet(conn, rid, tmp_path, _lister_cibles_factice,
                            force_confirme=True)
    assert res['confirmation_requise'] is False
    assert res['ref']['etat'] == 'verrouille'
    assert (tmp_path / '_verrouille' / 'trace.json').is_file()
    # État réellement persisté
    with _conn(sqlite_store) as conn:
        row = conn.execute(
            "SELECT etat FROM referentiel_niveaux WHERE id=?", (rid,)
        ).fetchone()
    assert row['etat'] == 'verrouille'


def test_verrouiller_complet_trace_ecrite_en_utf8(sqlite_store, tmp_path):
    """La trace contient les accents tels quels (UTF-8, pas \\uXXXX)."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn, etat='valide')
        # description avec accents
        conn.execute(
            "UPDATE referentiel_niveaux SET description=? WHERE id=?",
            ("Référentiel d'évaluation", rid)
        )
        conn.commit()
        verrouiller_complet(conn, rid, tmp_path, _lister_cibles_factice,
                      force_confirme=True)
    contenu = (tmp_path / '_verrouille' / 'trace.json').read_text(encoding='utf-8')
    assert "Référentiel" in contenu
    assert "évaluation" in contenu
    assert "\\u00e9" not in contenu  # pas d'échappement Unicode


def test_verrouiller_complet_pdfs_copies(sqlite_store, tmp_path):
    """Le PDF actif est copié dans `_fige/pdfs/`."""
    # Préparer un PDF source dans le dossier "référentiel"
    pdf_src = tmp_path / 'livret_sequence.pdf'
    pdf_src.write_bytes(b'%PDF-1.7 contenu test')

    with _conn(sqlite_store) as conn:
        rid = _ref(conn, etat='valide')
        _doc(conn, rid, 'livret_sequence', actif=True, compile_ok=1)
        conn.commit()
        res = verrouiller_complet(conn, rid, tmp_path, _lister_cibles_factice,
                            force_confirme=True)
    assert res['verrouille']['nb_pdfs_copies'] == 1
    assert (tmp_path / '_verrouille' / 'pdfs' / 'livret_sequence.pdf').is_file()


def test_verrouiller_complet_pdf_absent_reporte_dans_echecs(sqlite_store, tmp_path):
    """PDF déclaré actif mais fichier source absent → echec listé, le
    figeage continue (transition d'état appliquée quand même)."""
    with _conn(sqlite_store) as conn:
        rid = _ref(conn, etat='valide')
        _doc(conn, rid, 'livret_sequence', actif=True, compile_ok=1)
        conn.commit()
        # Pas de PDF physique posé : la copie échouera
        res = verrouiller_complet(conn, rid, tmp_path, _lister_cibles_factice,
                            force_confirme=True)
    assert res['ref']['etat'] == 'verrouille'   # transition appliquée
    assert len(res['verrouille']['echecs_copie']) == 1


def test_verrouiller_complet_concurrents_force_confirme_false_renvoie_confirmation(
        sqlite_store, tmp_path):
    """Concurrent éligible présent + force_confirme=False : la fonction
    ne touche RIEN (BDD ET disque) et renvoie confirmation_requise=True."""
    with _conn(sqlite_store) as conn:
        # Concurrent : même niveau+année, suffixe antérieur
        rid_concurrent = _ref(conn, etat='valide', niveau='N10',
                                version='2025_v0')
        rid = _ref(conn, etat='valide', niveau='N10', version='2025_v1')
        conn.commit()
        res = verrouiller_complet(conn, rid, tmp_path, _lister_cibles_factice,
                            force_confirme=False)
    assert res['confirmation_requise'] is True
    # Le dossier _fige n'a PAS été créé
    assert not (tmp_path / '_verrouille').exists()
    # États inchangés
    with _conn(sqlite_store) as conn:
        for r_id, attendu in [(rid, 'valide'),
                                (rid_concurrent, 'valide')]:
            row = conn.execute(
                "SELECT etat FROM referentiel_niveaux WHERE id=?", (r_id,)
            ).fetchone()
            assert row['etat'] == attendu


def test_verrouiller_complet_concurrents_force_confirme_true_annule_concurrents(
        sqlite_store, tmp_path):
    """force_confirme=True : concurrents passent à 'annule', cible à 'fige'."""
    with _conn(sqlite_store) as conn:
        rid_concurrent = _ref(conn, etat='valide', niveau='N10',
                                version='2025_v0')
        rid = _ref(conn, etat='valide', niveau='N10', version='2025_v1')
        conn.commit()
        res = verrouiller_complet(conn, rid, tmp_path, _lister_cibles_factice,
                            force_confirme=True)
    assert res['ref']['etat'] == 'verrouille'
    assert len(res['concurrents_annules']) == 1
    with _conn(sqlite_store) as conn:
        row = conn.execute(
            "SELECT etat FROM referentiel_niveaux WHERE id=?",
            (rid_concurrent,)
        ).fetchone()
    assert row['etat'] == 'annule'
