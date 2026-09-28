"""tests/test_v0_13_6_4_documents_publiables.py — v0.13.6.4

Tests du catalogue des documents publiables d'un référentiel.

Couvre :
  1. Présence de la table `referentiel_documents` après init du store
  2. Initialisation par défaut : 9 types insérés, idempotent
  3. Tous les défauts sont bien-formés (clés, types, énumérés)
  4. Lister documents : auto-initialise si vide
  5. Maj options : validation des clés et valeurs
  6. Cascade : suppression d'un référentiel supprime ses documents
  7. Routes GET et PUT (intégration via client Flask)
"""
from __future__ import annotations

from pathlib import Path
import sys
import json
import sqlite3
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import referentiel_documents as svc  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────


def _conn(store):
    return store._conn()


def _creer_referentiel_minimal(conn: sqlite3.Connection,
                               niveau: str = 'N10') -> str:
    """Crée un référentiel minimal en BDD, retourne son id."""
    ref_id = f"ref_test_{uuid.uuid4().hex[:8]}"
    conn.execute("""
        INSERT INTO referentiel_niveaux
            (id, niveau, version, date_debut, date_fin, description, etat)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ref_id, niveau, '2025_test', '2025-09-01', '2026-08-31',
          'Test', 'en_cours'))
    conn.commit()
    return ref_id


# ── 1. Schéma ────────────────────────────────────────────────────────────────


def test_table_referentiel_documents_existe(sqlite_store):
    """Après init du store, la table referentiel_documents doit exister."""
    with _conn(sqlite_store) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='referentiel_documents'"
        ).fetchone()
        assert row is not None, "Table referentiel_documents absente"


def test_index_referentiel_id_existe(sqlite_store):
    with _conn(sqlite_store) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_referentiel_documents_referentiel_id'"
        ).fetchone()
        assert row is not None, "Index manquant"


# ── 2. Catalogue des défauts ─────────────────────────────────────────────────


def test_neuf_types_definis():
    assert len(svc.TYPES_DOCUMENT) == 9


def test_chaque_type_a_defauts_bienformes():
    """Chaque type a un dict de défauts contenant au moins la clé `actif`."""
    for type_doc in svc.TYPES_DOCUMENT:
        defaut = svc.OPTIONS_PAR_DEFAUT[type_doc]
        assert isinstance(defaut, dict), f"{type_doc} : défaut non-dict"
        assert 'actif' in defaut, f"{type_doc} : clé `actif` manquante"
        assert defaut['actif'] is False, (
            f"{type_doc} : actif par défaut doit être False"
        )


def test_enumes_valides():
    """Les valeurs par défaut des champs énumérés sont dans la liste autorisée."""
    for type_doc, defaut in svc.OPTIONS_PAR_DEFAUT.items():
        for cle, val in defaut.items():
            if cle in svc.ENUMS:
                assert val in svc.ENUMS[cle], (
                    f"{type_doc}.{cle} : défaut {val!r} hors énum "
                    f"{svc.ENUMS[cle]}"
                )


def test_ordre_couvre_tous_les_types():
    """`ORDRE_AFFICHAGE` est défini pour les 9 types, sans doublon."""
    assert set(svc.ORDRE_AFFICHAGE.keys()) == set(svc.TYPES_DOCUMENT)
    valeurs = list(svc.ORDRE_AFFICHAGE.values())
    assert len(valeurs) == len(set(valeurs)), "Doublons dans ORDRE_AFFICHAGE"


# ── 3. Initialisation ────────────────────────────────────────────────────────


def test_initialisation_insere_9_documents(sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        svc.initialiser_documents_defaut(conn, ref_id)
        n = conn.execute(
            "SELECT COUNT(*) FROM referentiel_documents WHERE referentiel_id = ?",
            (ref_id,),
        ).fetchone()[0]
    assert n == 9


def test_initialisation_idempotente(sqlite_store):
    """Lancer 2 fois `initialiser_documents_defaut` ne crée pas de doublons."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        svc.initialiser_documents_defaut(conn, ref_id)
        svc.initialiser_documents_defaut(conn, ref_id)  # 2e passe
        n = conn.execute(
            "SELECT COUNT(*) FROM referentiel_documents WHERE referentiel_id = ?",
            (ref_id,),
        ).fetchone()[0]
    assert n == 9


def test_initialisation_options_actif_false(sqlite_store):
    """Tous les documents initialisés ont actif=False."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        svc.initialiser_documents_defaut(conn, ref_id)
        rows = conn.execute(
            "SELECT type_document, options FROM referentiel_documents "
            "WHERE referentiel_id = ?",
            (ref_id,),
        ).fetchall()
    for r in rows:
        opts = json.loads(r['options'])
        assert opts.get('actif') is False, (
            f"{r['type_document']} : actif != False à l'init"
        )


# ── 4. Lister ────────────────────────────────────────────────────────────────


def test_lister_auto_initialise_si_vide(sqlite_store):
    """Premier accès à lister_documents → 9 entrées créées automatiquement."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        # Pas d'init manuelle : on appelle directement lister
        docs = svc.lister_documents(conn, ref_id)
    assert len(docs) == 9
    types = {d['type_document'] for d in docs}
    assert types == set(svc.TYPES_DOCUMENT)


def test_lister_renvoie_options_fusionnees(sqlite_store):
    """Les options renvoyées incluent les défauts (fusion JSON stocké + défauts)."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc.lister_documents(conn, ref_id)
    livret_seq = next(d for d in docs
                      if d['type_document'] == 'livret_sequence')
    # Le défaut contient ~9 clés, on vérifie quelques-unes
    assert livret_seq['options']['actif'] is False
    assert livret_seq['options']['inclure_enonces_serie_a'] is True
    assert livret_seq['options']['inclure_fiches_resume_en_fin'] == 'non'


def test_lister_tri_par_ordre(sqlite_store):
    """Les documents sont retournés dans l'ordre d'affichage."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc.lister_documents(conn, ref_id)
    ordres = [d['ordre'] for d in docs]
    assert ordres == sorted(ordres)
    # Premier = livret_sequence (ORDRE_AFFICHAGE[0])
    assert docs[0]['type_document'] == 'livret_sequence'


def test_lister_isolation_par_referentiel(sqlite_store):
    """Les documents d'un référentiel ne fuient pas vers un autre."""
    with _conn(sqlite_store) as conn:
        ref_a = _creer_referentiel_minimal(conn, 'N10')
        ref_b = _creer_referentiel_minimal(conn, 'N11')
        # Activer un document sur A
        docs_a = svc.lister_documents(conn, ref_a)
        livret_a = next(d for d in docs_a
                        if d['type_document'] == 'livret_sequence')
        svc.maj_options(conn, livret_a['id'], {'actif': True})

        docs_b = svc.lister_documents(conn, ref_b)
        livret_b = next(d for d in docs_b
                        if d['type_document'] == 'livret_sequence')
        assert livret_b['options']['actif'] is False, (
            "Activation sur A a fui sur B"
        )


# ── 5. Maj options ───────────────────────────────────────────────────────────


def test_maj_options_active(sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc.lister_documents(conn, ref_id)
        livret = next(d for d in docs
                      if d['type_document'] == 'livret_sequence')
        out = svc.maj_options(conn, livret['id'], {'actif': True})
    assert out['options']['actif'] is True
    # Les autres options restent à leur défaut
    assert out['options']['inclure_enonces_serie_a'] is True


def test_maj_options_partielle_preserve_existant(sqlite_store):
    """Une maj partielle ne touche que les clés fournies."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc.lister_documents(conn, ref_id)
        livret = next(d for d in docs
                      if d['type_document'] == 'livret_sequence')
        # Active d'abord
        svc.maj_options(conn, livret['id'], {'actif': True})
        # Puis modifie juste une option
        out = svc.maj_options(conn, livret['id'],
                              {'inclure_corriges_serie_a': True})
    assert out['options']['actif'] is True  # préservé
    assert out['options']['inclure_corriges_serie_a'] is True  # modifié


def test_maj_options_cle_inconnue_rejetee(sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc.lister_documents(conn, ref_id)
        livret_plans = next(d for d in docs
                            if d['type_document'] == 'livret_plans')
        with pytest.raises(svc.DocumentErreur) as ei:
            # livret_plans n'a que `actif`
            svc.maj_options(conn, livret_plans['id'],
                            {'inclure_cours': True})
    assert ei.value.code == 'options_invalides'
    assert 'inclure_cours' in str(ei.value.details)


def test_maj_options_type_invalide_rejete(sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc.lister_documents(conn, ref_id)
        livret = next(d for d in docs
                      if d['type_document'] == 'livret_sequence')
        with pytest.raises(svc.DocumentErreur) as ei:
            # `actif` attend bool, on passe une string
            svc.maj_options(conn, livret['id'], {'actif': 'oui'})
    assert ei.value.code == 'options_invalides'


def test_maj_options_enum_invalide_rejete(sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc.lister_documents(conn, ref_id)
        livret = next(d for d in docs
                      if d['type_document'] == 'livret_sequence')
        with pytest.raises(svc.DocumentErreur) as ei:
            svc.maj_options(
                conn, livret['id'],
                {'inclure_fiches_resume_en_fin': 'wat'},
            )
    assert ei.value.code == 'options_invalides'


def test_livret_sequence_a_option_contenu(sqlite_store):
    """v0.13.6.4 — Le livret_sequence a une option 'contenu' (radio).

    Valeur par défaut : 'cours_et_exercices'. Valeurs autorisées :
    'cours_seul', 'exercices_seul', 'cours_et_exercices'.
    """
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc.lister_documents(conn, ref_id)
        livret = next(d for d in docs
                      if d['type_document'] == 'livret_sequence')
    assert livret['options']['contenu'] == 'cours_et_exercices'


def test_maj_contenu_livret_sequence(sqlite_store):
    """Bascule contenu vers cours_seul, puis exercices_seul."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        docs = svc.lister_documents(conn, ref_id)
        livret = next(d for d in docs
                      if d['type_document'] == 'livret_sequence')

        out = svc.maj_options(conn, livret['id'],
                              {'contenu': 'cours_seul'})
        assert out['options']['contenu'] == 'cours_seul'

        out = svc.maj_options(conn, livret['id'],
                              {'contenu': 'exercices_seul'})
        assert out['options']['contenu'] == 'exercices_seul'

        # Valeur hors enum rejetée
        with pytest.raises(svc.DocumentErreur) as ei:
            svc.maj_options(conn, livret['id'],
                            {'contenu': 'autre_chose'})
        assert ei.value.code == 'options_invalides'


def test_maj_options_doc_introuvable(sqlite_store):
    with _conn(sqlite_store) as conn:
        with pytest.raises(svc.DocumentIntrouvable):
            svc.maj_options(conn, 'rd_inexistant', {'actif': True})


# ── 6. Cascade ───────────────────────────────────────────────────────────────


def test_cascade_suppression_referentiel(sqlite_store):
    """Supprimer un référentiel supprime ses documents."""
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
        svc.initialiser_documents_defaut(conn, ref_id)
        n_avant = conn.execute(
            "SELECT COUNT(*) FROM referentiel_documents "
            "WHERE referentiel_id = ?",
            (ref_id,),
        ).fetchone()[0]
        assert n_avant == 9

        conn.execute("DELETE FROM referentiel_niveaux WHERE id = ?",
                     (ref_id,))
        conn.commit()

        n_apres = conn.execute(
            "SELECT COUNT(*) FROM referentiel_documents "
            "WHERE referentiel_id = ?",
            (ref_id,),
        ).fetchone()[0]
    assert n_apres == 0, "Cascade FK n'a pas fonctionné"


# ── 7. Routes (intégration Flask) ────────────────────────────────────────────


def test_route_get_documents(client, sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)

    resp = client.get(f'/api/referentiels/{ref_id}/documents')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'documents' in data
    assert len(data['documents']) == 9
    # Tous démarrent inactifs
    assert all(d['options']['actif'] is False for d in data['documents'])


def test_route_get_documents_referentiel_inconnu(client):
    resp = client.get('/api/referentiels/ref_inexistant/documents')
    assert resp.status_code == 404


def test_route_put_documents(client, sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
    # Init et récup d'un doc
    resp = client.get(f'/api/referentiels/{ref_id}/documents')
    livret = next(d for d in resp.get_json()['documents']
                  if d['type_document'] == 'livret_sequence')

    resp = client.put(
        f"/api/referentiels/{ref_id}/documents/{livret['id']}",
        json={'options': {'actif': True}},
    )
    assert resp.status_code == 200
    out = resp.get_json()['document']
    assert out['options']['actif'] is True


def test_route_put_options_invalides(client, sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
    resp = client.get(f'/api/referentiels/{ref_id}/documents')
    livret = next(d for d in resp.get_json()['documents']
                  if d['type_document'] == 'livret_plans')

    resp = client.put(
        f"/api/referentiels/{ref_id}/documents/{livret['id']}",
        json={'options': {'cle_qui_nexiste_pas': True}},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['error'] == 'options_invalides'


def test_route_put_document_d_un_autre_referentiel(client, sqlite_store):
    """PUT sur un doc qui n'appartient pas au référentiel → 404."""
    with _conn(sqlite_store) as conn:
        ref_a = _creer_referentiel_minimal(conn, 'N10')
        ref_b = _creer_referentiel_minimal(conn, 'N11')
    # On récupère un doc de B et on tente de l'éditer via l'URL de A
    resp = client.get(f'/api/referentiels/{ref_b}/documents')
    livret_b = resp.get_json()['documents'][0]
    resp = client.put(
        f"/api/referentiels/{ref_a}/documents/{livret_b['id']}",
        json={'options': {'actif': True}},
    )
    assert resp.status_code == 404


def test_route_put_body_invalide(client, sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _creer_referentiel_minimal(conn)
    resp = client.get(f'/api/referentiels/{ref_id}/documents')
    livret = resp.get_json()['documents'][0]

    # body sans 'options'
    resp = client.put(
        f"/api/referentiels/{ref_id}/documents/{livret['id']}",
        json={'autre_truc': 42},
    )
    assert resp.status_code == 400
