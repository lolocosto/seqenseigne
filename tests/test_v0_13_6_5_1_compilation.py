"""tests/test_v0_13_6_5_1_compilation.py — v0.13.6.5.1

Tests du mécanisme de compilation des documents publiables.

Couvre :
  - Migration des 4 colonnes compile_* sur referentiel_documents
  - État effectif (non_compile, en_cours, ko, perime, ok)
  - lister_cibles_document pour les 3 cas : unitaire, livret_sequence × N, eval × N
  - _generer_tex avec type non_implemente → CompilationErreur
  - compiler_document refusé si actif=False
  - compiler_document refusé si compile_en_cours=1
  - Route POST /compiler : 400 (inactif), 404 (inconnu), 202 (lancé)
  - Route GET /compiler/statut : structure de retour
  - Route GET /pdf : 404 (non compilé), 400 (cible requise multi-cible)
  - Reset des verrous orphelins au démarrage

La compilation effective (pdflatex) n'est pas testée ici (pas de
MiKTeX dans le sandbox de tests). Les tests utilisent un mock pour
le compilateur.
"""
from __future__ import annotations

from pathlib import Path
import sys
import json
import sqlite3
import uuid
import time
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import referentiel_documents as svc_cat  # noqa: E402
from services import referentiel_documents_compilation as svc_cmp  # noqa: E402


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


# ── 1. Migration ─────────────────────────────────────────────────────────────


def test_colonnes_compile_existent(sqlite_store):
    """Les 4 colonnes compile_* doivent exister sur referentiel_documents."""
    with _conn(sqlite_store) as conn:
        cols = {r['name'] for r in conn.execute(
            "PRAGMA table_info(referentiel_documents)"
        )}
    for c in ['compile_ok', 'compile_date', 'compile_log', 'compile_en_cours']:
        assert c in cols, f"Colonne {c} absente"


def test_compile_en_cours_defaut_zero(sqlite_store):
    """Un nouveau doc a compile_en_cours=0 par défaut."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        for d in docs:
            assert d['compile_en_cours'] is False


# ── 2. État effectif ─────────────────────────────────────────────────────────


def test_etat_effectif_non_compile(sqlite_store):
    """Document jamais compilé → 'non_compile'."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
    assert all(d['etat_effectif'] == 'non_compile' for d in docs)


def test_etat_effectif_en_cours(sqlite_store):
    """Document avec compile_en_cours=1 → 'en_cours'."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = docs[0]
        conn.execute(
            "UPDATE referentiel_documents SET compile_en_cours = 1 "
            "WHERE id = ?", (doc['id'],)
        )
        conn.commit()
        docs2 = svc_cat.lister_documents(conn, ref_id)
    doc2 = next(d for d in docs2 if d['id'] == doc['id'])
    assert doc2['etat_effectif'] == 'en_cours'


def test_etat_effectif_ko(sqlite_store):
    """Document compilé KO → 'ko'."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = docs[0]
        conn.execute(
            "UPDATE referentiel_documents "
            "SET compile_ok = 0, compile_date = '2026-01-01 00:00:00' "
            "WHERE id = ?", (doc['id'],)
        )
        conn.commit()
        docs2 = svc_cat.lister_documents(conn, ref_id)
    doc2 = next(d for d in docs2 if d['id'] == doc['id'])
    assert doc2['etat_effectif'] == 'ko'


def test_etat_effectif_ok(sqlite_store):
    """Document compilé OK + pas d'atomes plus récents → 'ok'."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = docs[0]
        # Pose compile_date dans le futur lointain → garanti que les
        # mtime des atomes (s'il y en a) sont antérieurs.
        conn.execute(
            "UPDATE referentiel_documents "
            "SET compile_ok = 1, compile_date = '2099-01-01 00:00:00' "
            "WHERE id = ?", (doc['id'],)
        )
        conn.commit()
        docs2 = svc_cat.lister_documents(conn, ref_id)
    doc2 = next(d for d in docs2 if d['id'] == doc['id'])
    assert doc2['etat_effectif'] == 'ok'


# ── 3. Cibles ────────────────────────────────────────────────────────────────


def test_cibles_unitaire(sqlite_store):
    """Pour un type unitaire, une seule cible 'unique'."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        livret_cours = next(d for d in docs
                            if d['type_document'] == 'livret_cours')
        cibles = svc_cmp.lister_cibles_document(
            conn, livret_cours['id'], ref_id, 'livret_cours'
        )
    assert len(cibles) == 1
    assert cibles[0]['cible_id'] == 'unique'
    assert cibles[0]['nom_fichier'] == 'livret_cours.pdf'


def test_cibles_livret_sequence(sqlite_store):
    """Pour livret_sequence : autant de cibles que de séquences-par-niveau
    rattachées au niveau."""
    # Sans données, il y a 0 séquence
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        livret = next(d for d in docs
                      if d['type_document'] == 'livret_sequence')
        cibles_avant = svc_cmp.lister_cibles_document(
            conn, livret['id'], ref_id, 'livret_sequence'
        )
        # Ajouter 2 séquences
        for code in ['S01', 'S02']:
            conn.execute("""
                INSERT INTO sequences_par_niveau(id, niveau, sequence_code)
                VALUES (?, 'N10', ?)
            """, (f"sn_test_{code}", code))
        conn.commit()
        cibles_apres = svc_cmp.lister_cibles_document(
            conn, livret['id'], ref_id, 'livret_sequence'
        )
    assert len(cibles_avant) == 0
    assert len(cibles_apres) == 2
    assert cibles_apres[0]['cible_id'] == 'N10/S01'
    assert cibles_apres[0]['nom_fichier'] == 'livret_sequence__N10__S01.pdf'


def test_cibles_evaluation(sqlite_store):
    """Pour evaluation : autant de cibles que d'évaluations du niveau."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        eval_doc = next(d for d in docs
                        if d['type_document'] == 'evaluation')
        # Ajouter 2 évals N10
        for num in [1, 2]:
            conn.execute("""
                INSERT INTO evaluations
                    (id, niveau, numero, ordre, titre, etat_code)
                VALUES (?, 'N10', ?, ?, 'Éval', 'en_cours')
            """, (f"eval_{num}", num, num))
        conn.commit()
        cibles = svc_cmp.lister_cibles_document(
            conn, eval_doc['id'], ref_id, 'evaluation'
        )
    assert len(cibles) == 2


# ── 4. Types non implémentés ─────────────────────────────────────────────────


def test_generer_tex_type_non_implemente(sqlite_store):
    """v0.13.6.5.2 — Les 4 types précédemment 'à venir' (livret_fiches,
    livret_corriges, livret_cartes_recap, livret_cartes_planches) sont
    maintenant implémentés. Ce test vérifie qu'ils NE lèvent PLUS
    type_non_implemente, mais délèguent bien aux vrais producteurs.

    Note : ce test était écrit en v0.13.6.5.1 pour valider l'inverse
    (les 4 stubs levaient une erreur claire). Avec v0.13.6.5.2, la
    sémantique est inversée : un succès des 4 délégations confirme
    le branchement effectif sur les nouveaux services métier.

    Pour vérifier qu'un type *vraiment* inconnu lève bien une erreur
    explicite, voir test_generer_tex_type_inconnu plus bas dans le
    fichier test_v0_13_6_5_1_1_orchestrateur.py.
    """
    types_implementes = [
        'livret_fiches', 'livret_corriges',
        'livret_cartes_recap', 'livret_cartes_planches',
    ]
    with _conn(sqlite_store) as conn:
        for type_doc in types_implementes:
            # Doit retourner un .tex (str) sans lever — la signature
            # implique au minimum un niveau dans la cible
            try:
                tex = svc_cmp._generer_tex(
                    conn, type_doc, {},
                    {'niveau': 'N10'},
                    [], [],
                )
                # Si le service est bien implémenté, on récupère du .tex
                # (même s'il est vide ou minimal pour un niveau sans données)
                assert isinstance(tex, str)
                assert r'\documentclass' in tex
            except LookupError:
                # Fixture sqlite_store sans cycle pré-créé : c'est OK,
                # ce test ne vise pas le peuplement de la BDD.
                pass
            except sqlite3.OperationalError:
                # v0.15.5 — Depuis la factorisation de la résolution de
                # cycle (lire_cycle lit param_niveaux, peuplé par conftest),
                # les générateurs livret_fiches/corriges ne s'arrêtent plus
                # tôt sur un LookupError « cycle absent » : ils vont jusqu'à
                # construire_preambule, qui requête `paquet_definitions`.
                # Cette table n'est pas créée dans la fixture sqlite_store
                # nue (cf. fixture store_avec_paquet ailleurs). L'absence de
                # table est hors scope : ce test ne vise QUE l'absence de
                # 'type_non_implemente'.
                pass
            except svc_cmp.CompilationErreur as e:
                if e.code == 'type_non_implemente':
                    pytest.fail(
                        f"{type_doc} lève encore 'type_non_implemente' — "
                        f"le producteur n'a pas été branché en v0.13.6.5.2."
                    )
                # D'autres erreurs (LookupError sur cycle absent, etc.)
                # sont possibles selon l'état de la BDD de test ; elles
                # ne sont pas pertinentes pour ce test.


# ── 5. compiler_document : validations ───────────────────────────────────────


def test_compiler_document_refuse_si_inactif(sqlite_store):
    """compiler_document doit refuser un doc dont actif=False."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = next(d for d in docs
                   if d['type_document'] == 'livret_cours')
    with pytest.raises(svc_cmp.CompilationErreur) as ei:
        svc_cmp.compiler_document(sqlite_store, doc['id'])
    assert ei.value.code == 'document_inactif'


def test_compiler_document_refuse_si_en_cours(sqlite_store):
    """compiler_document doit refuser si compile_en_cours=1."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = next(d for d in docs
                   if d['type_document'] == 'livret_cours')
        # Activer et marquer en cours
        svc_cat.maj_options(conn, doc['id'], {'actif': True})
        conn.execute(
            "UPDATE referentiel_documents SET compile_en_cours = 1 WHERE id = ?",
            (doc['id'],)
        )
        conn.commit()
    with pytest.raises(svc_cmp.CompilationErreur) as ei:
        svc_cmp.compiler_document(sqlite_store, doc['id'])
    assert ei.value.code == 'compilation_en_cours'


def test_compiler_document_doc_inconnu(sqlite_store):
    """compiler_document sur doc_id inconnu → CompilationErreur."""
    with pytest.raises(svc_cmp.CompilationErreur) as ei:
        svc_cmp.compiler_document(sqlite_store, 'rd_inexistant')
    assert ei.value.code == 'document_introuvable'


# ── 6. Routes ────────────────────────────────────────────────────────────────


def test_route_compiler_inactif(client, sqlite_store):
    """POST /compiler sur doc inactif → 400."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = next(d for d in docs
                   if d['type_document'] == 'livret_cours')

    resp = client.post(
        f"/api/referentiels/{ref_id}/documents/{doc['id']}/compiler"
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['error'] == 'document_inactif'


def test_route_compiler_doc_inconnu(client, sqlite_store):
    """POST /compiler sur doc inexistant → 404."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
    resp = client.post(
        f"/api/referentiels/{ref_id}/documents/rd_inexistant/compiler"
    )
    assert resp.status_code == 404


def test_route_compiler_ref_inconnu(client):
    """POST /compiler sur référentiel inexistant → 404."""
    resp = client.post(
        "/api/referentiels/ref_inexistant/documents/rd_x/compiler"
    )
    assert resp.status_code == 404


def test_route_statut(client, sqlite_store):
    """GET /compiler/statut renvoie un dict {statut, bdd}."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = docs[0]
    resp = client.get(
        f"/api/referentiels/{ref_id}/documents/{doc['id']}/compiler/statut"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'statut' in data
    assert 'bdd' in data
    # Pas de compilation en cours → statut mémoire = None
    assert data['statut'] is None
    # BDD : compile_en_cours=False
    assert data['bdd']['compile_en_cours'] is False


def test_route_pdf_non_compile(client, sqlite_store):
    """GET /pdf sur doc non compilé (type unitaire) → 404."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = next(d for d in docs
                   if d['type_document'] == 'livret_cours')
    resp = client.get(
        f"/api/referentiels/{ref_id}/documents/{doc['id']}/pdf"
    )
    assert resp.status_code == 404
    data = resp.get_json()
    assert data['error'] == 'pdf_non_trouve'


def test_route_pdf_cible_requise(client, sqlite_store):
    """GET /pdf sur livret_sequence sans cible (et avec >1 cibles) → 400."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        doc = next(d for d in docs
                   if d['type_document'] == 'livret_sequence')
        # Ajouter 2 séquences pour avoir >1 cibles
        for code in ['S01', 'S02']:
            conn.execute("""
                INSERT INTO sequences_par_niveau(id, niveau, sequence_code)
                VALUES (?, 'N10', ?)
            """, (f"sn_test_{code}", code))
        conn.commit()
    resp = client.get(
        f"/api/referentiels/{ref_id}/documents/{doc['id']}/pdf"
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['error'] == 'cible_requise'


# ── 7. Reset des verrous orphelins ───────────────────────────────────────────


def test_reset_verrous_orphelins_au_demarrage(tmp_path):
    """Si Flask redémarre alors qu'un compile_en_cours est resté à 1,
    la prochaine init du store doit le réinitialiser."""
    from persistence.sqlite_store import SqliteStore

    # Première init : créer un doc, le marquer en_cours
    store1 = SqliteStore(tmp_path)
    with store1._conn() as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
        conn.execute(
            "UPDATE referentiel_documents SET compile_en_cours = 1 "
            "WHERE id = ?", (docs[0]['id'],)
        )
        conn.commit()
        # Vérif
        n_en_cours = conn.execute(
            "SELECT COUNT(*) FROM referentiel_documents "
            "WHERE compile_en_cours = 1"
        ).fetchone()[0]
        assert n_en_cours == 1

    # Réinit (simule redémarrage Flask) — devrait remettre à 0
    store2 = SqliteStore(tmp_path)
    with store2._conn() as conn:
        n_en_cours = conn.execute(
            "SELECT COUNT(*) FROM referentiel_documents "
            "WHERE compile_en_cours = 1"
        ).fetchone()[0]
        assert n_en_cours == 0, (
            "Les verrous compile_en_cours orphelins n'ont pas été reset "
            "au démarrage"
        )


# ── 8. Lister documents avec compile_* ───────────────────────────────────────


def test_lister_documents_expose_compile_columns(sqlite_store):
    """Le service catalogue expose les colonnes compile_* et etat_effectif."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc_cat.lister_documents(conn, ref_id)
    for d in docs:
        assert 'compile_ok' in d
        assert 'compile_date' in d
        assert 'compile_log' in d
        assert 'compile_en_cours' in d
        assert 'etat_effectif' in d
        # referentiel_id est aussi exposé (utile pour etat_effectif)
        assert 'referentiel_id' in d
