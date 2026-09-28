"""tests/test_v0_15_2_8_validation_referentiel.py — v0.15.2.8 (partie B1)

Auto-validation des référentiels : un référentiel passe automatiquement
en `valide` quand tous ses atomes, ses évaluations et ses documents
sont valides/compilés/non périmés. Et revient à `en_cours` si l'un
quelconque de ces critères devient faux (lazy).

Règles testées :

1. `evaluer_eligibilite_validation` retourne `eligible=True` quand TOUS
   les critères sont OK (atomes valides, évals valides, docs compilés
   et non périmés).
2. Chaque critère individuel produit une raison de non-éligibilité
   identifiable et incrémente le bon compteur dans `details`.
3. `maj_etat_lazy` applique les transitions :
   - `en_cours + eligible → valide`
   - `valide + non eligible → en_cours`
4. `maj_etat_lazy` NE TOUCHE PAS aux états terminaux :
   - `fige` reste `fige`
   - `annule` reste `annule`
5. Les documents inactifs (options.actif=False) ne bloquent PAS la
   validation (un document non actif est ignoré).
6. Le lazy auto est branché sur `lister_par_niveau` : si un référentiel
   devient éligible, sa lecture le bascule en `valide`.

L'auto-validation est un calcul dérivé, pas une donnée stockée :
le test verrouille la décision (libellés des raisons, structure du
diagnostic) pour qu'un changement futur soit conscient.
"""
from __future__ import annotations

from pathlib import Path
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.referentiel_validation import (  # noqa: E402
    evaluer_eligibilite_validation,
    maj_etat_lazy,
)


def _conn(store):
    return store._conn()


# Helpers pour créer un fixture minimal


def _ref(conn, etat='en_cours', niveau='N10'):
    ref_id = f"ref_{uuid.uuid4().hex[:8]}"
    conn.execute("""
        INSERT INTO referentiel_niveaux
            (id, niveau, version, date_debut, date_fin, description, etat)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ref_id, niveau, '2025_test', '2025-09-01', '2026-08-31',
          'Test', etat))
    return ref_id


def _atome(conn, table, niveau, *, etat='valide'):
    """Insère un atome stub. Schéma adapté à chaque table."""
    aid = f"a_{uuid.uuid4().hex[:8]}"
    if table == 'notions':
        conn.execute("""INSERT INTO notions
            (id, niveau, sequence, num_connaissance, titre, corps, etat_code, mtime)
            VALUES (?, ?, 'S01', 1, 'T', '', ?, '2026-01-01 00:00:00')""",
            (aid, niveau, etat))
    elif table == 'methodes':
        conn.execute("""INSERT INTO methodes
            (id, niveau, sequence, num_methode, titre, corps, etat_code, mtime)
            VALUES (?, ?, 'S01', 1, 'T', '', ?, '2026-01-01 00:00:00')""",
            (aid, niveau, etat))
    elif table == 'exercices':
        conn.execute("""INSERT INTO exercices
            (id, niveau, sequence, num, serie, titre, enonce, corrige, etat_code, mtime)
            VALUES (?, ?, 'S01', 1, 'F', 'T', '', '', ?, '2026-01-01 00:00:00')""",
            (aid, niveau, etat))
    elif table == 'fiches_resume':
        conn.execute("""INSERT INTO fiches_resume
            (id, niveau, sequence, num_fiche, titre, etat_code, mtime)
            VALUES (?, ?, 'S01', 1, 'T', ?, '2026-01-01 00:00:00')""",
            (aid, niveau, etat))
    elif table == 'cartes_automatisme':
        conn.execute("""INSERT INTO cartes_automatisme
            (id, niveau, sequence, num, type_pedago, type_tech, titre,
             lien_type, lien_id, recto, verso, variables, etat_code, ordre, mtime)
            VALUES (?, ?, 'S01', 1, 'definition', 'fixe', 'T', NULL, NULL,
                    '', '', '', ?, 0, '2026-01-01 00:00:00')""",
            (aid, niveau, etat))
    return aid


def _evaluation(conn, niveau, *, etat='valide'):
    eid = f"ev_{uuid.uuid4().hex[:8]}"
    conn.execute("""INSERT INTO evaluations
        (id, niveau, numero, ordre, titre, mode_notation,
         afficher_bareme_dans_exos, item_langue_francaise, etat_code, mtime)
        VALUES (?, ?, 1, 1, 'Eval', 'note', 1, 0, ?, '2026-01-01 00:00:00')""",
        (eid, niveau, etat))
    return eid


def _document(conn, ref_id, type_doc, *, actif=True, compile_ok=1,
              compile_date='2026-03-01 12:00:00'):
    did = f"d_{uuid.uuid4().hex[:8]}"
    import json
    conn.execute("""INSERT INTO referentiel_documents
        (id, referentiel_id, type_document, options, ordre, mtime,
         compile_ok, compile_date, compile_log, compile_en_cours)
        VALUES (?, ?, ?, ?, 1, '2026-01-01 00:00:00', ?, ?, NULL, 0)""",
        (did, ref_id, type_doc, json.dumps({'actif': actif}),
         compile_ok, compile_date))
    return did


# ── Eligibilité OK ────────────────────────────────────────────────────────


def test_ref_sans_atome_sans_doc_sans_eval_est_eligible(sqlite_store):
    """Cas trivial : référentiel vide → éligible (rien à valider).
    Sécurité : on ne casse pas les setups initiaux où tout est vide.
    """
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn)
        conn.commit()
        diag = evaluer_eligibilite_validation(conn, ref_id)
    assert diag['eligible'] is True
    assert diag['raisons'] == []


def test_ref_tout_valide_est_eligible(sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn)
        _atome(conn, 'notions',   'N10', etat='valide')
        _atome(conn, 'exercices', 'N10', etat='valide')
        _evaluation(conn, 'N10', etat='valide')
        _document(conn, ref_id, 'livret_sequence',
                  compile_ok=1, compile_date='2026-03-01 12:00:00')
        conn.commit()
        diag = evaluer_eligibilite_validation(conn, ref_id)
    assert diag['eligible'] is True
    assert diag['raisons'] == []


# ── Eligibilité KO — chaque critère individuellement ───────────────────────


def test_atome_non_valide_bloque(sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn)
        _atome(conn, 'exercices', 'N10', etat='en_cours')  # NON valide
        conn.commit()
        diag = evaluer_eligibilite_validation(conn, ref_id)
    assert diag['eligible'] is False
    assert diag['details']['atomes_non_valides']['exercices'] == 1
    # Le libellé humain doit être présent et identifiable
    assert any('exercice' in r for r in diag['raisons'])


def test_chaque_table_atome_a_son_compteur(sqlite_store):
    """Les 5 tables d'atomes ont chacune leur compteur dans details."""
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn)
        _atome(conn, 'notions',            'N10', etat='en_cours')
        _atome(conn, 'methodes',           'N10', etat='en_cours')
        _atome(conn, 'exercices',          'N10', etat='en_cours')
        _atome(conn, 'fiches_resume',      'N10', etat='en_cours')
        _atome(conn, 'cartes_automatisme', 'N10', etat='en_cours')
        conn.commit()
        diag = evaluer_eligibilite_validation(conn, ref_id)
    a = diag['details']['atomes_non_valides']
    assert a['notions'] == 1
    assert a['methodes'] == 1
    assert a['exercices'] == 1
    assert a['fiches_resume'] == 1
    assert a['cartes_automatisme'] == 1
    assert diag['eligible'] is False


def test_evaluation_non_valide_bloque(sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn)
        _evaluation(conn, 'N10', etat='en_cours')
        conn.commit()
        diag = evaluer_eligibilite_validation(conn, ref_id)
    assert diag['eligible'] is False
    assert diag['details']['evaluations_non_valides'] == 1
    assert any('évaluation' in r for r in diag['raisons'])


def test_document_non_compile_bloque(sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn)
        _document(conn, ref_id, 'livret_sequence',
                  actif=True, compile_ok=0, compile_date=None)
        conn.commit()
        diag = evaluer_eligibilite_validation(conn, ref_id)
    assert diag['eligible'] is False
    assert diag['details']['documents_non_compiles'] == 1


def test_document_perime_bloque(sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn)
        # Doc compilé le 1er mars
        _document(conn, ref_id, 'livret_sequence',
                  actif=True, compile_ok=1,
                  compile_date='2026-03-01 12:00:00')
        # Atome pertinent modifié le 15 mars (= après compile_date)
        conn.execute("""UPDATE notions SET mtime='2026-03-15 00:00:00'
            WHERE niveau='N10'""")
        # Au cas où il n'y en aurait pas, on en crée un
        _atome(conn, 'notions', 'N10', etat='valide')
        conn.execute("""UPDATE notions SET mtime='2026-03-15 00:00:00'
            WHERE niveau='N10'""")
        conn.commit()
        diag = evaluer_eligibilite_validation(conn, ref_id)
    assert diag['eligible'] is False
    assert diag['details']['documents_perimes'] == 1


def test_document_inactif_n_est_pas_bloquant(sqlite_store):
    """Un document inactif (options.actif=False) est ignoré : il ne
    bloque pas la validation, même non compilé."""
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn)
        _document(conn, ref_id, 'livret_sequence',
                  actif=False, compile_ok=0, compile_date=None)
        conn.commit()
        diag = evaluer_eligibilite_validation(conn, ref_id)
    assert diag['eligible'] is True
    assert diag['details']['documents_non_compiles'] == 0


# ── Transitions d'état (lazy) ──────────────────────────────────────────────


def test_lazy_en_cours_devient_valide_quand_eligible(sqlite_store):
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn, etat='en_cours')
        # Rien à valider : éligible
        conn.commit()
        nouvel = maj_etat_lazy(conn, ref_id)
    assert nouvel == 'valide'


def test_lazy_valide_retombe_a_en_cours_si_non_eligible(sqlite_store):
    """Cas important : un référentiel `valide` doit retomber à `en_cours`
    si un atome est ajouté en `en_cours` (typiquement : Laurent ajoute
    un nouvel exercice qu'il n'a pas encore validé).
    """
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn, etat='valide')
        _atome(conn, 'exercices', 'N10', etat='en_cours')
        conn.commit()
        nouvel = maj_etat_lazy(conn, ref_id)
    assert nouvel == 'en_cours'


def test_lazy_ne_touche_pas_verrouille(sqlite_store):
    """v0.15.3 — État terminal : pas de retour en arrière, même si non
    éligible. (Anciennement nommé test_lazy_ne_touche_pas_fige avant
    la fusion fige+verrouille.)"""
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn, etat='verrouille')
        _atome(conn, 'exercices', 'N10', etat='en_cours')
        conn.commit()
        nouvel = maj_etat_lazy(conn, ref_id)
    assert nouvel == 'verrouille'


def test_lazy_ne_touche_pas_annule(sqlite_store):
    """État terminal : annule reste annule."""
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn, etat='annule')
        conn.commit()
        nouvel = maj_etat_lazy(conn, ref_id)
    assert nouvel == 'annule'


def test_lazy_reste_en_cours_si_non_eligible(sqlite_store):
    """Si on ajoute un atome non valide à un référentiel en_cours,
    il reste en_cours (pas de transition prématurée vers valide)."""
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn, etat='en_cours')
        _atome(conn, 'notions', 'N10', etat='en_cours')
        conn.commit()
        nouvel = maj_etat_lazy(conn, ref_id)
    assert nouvel == 'en_cours'


def test_lazy_persiste_etat_en_bdd(sqlite_store):
    """La transition est commitée : une relecture renvoie le nouvel état."""
    with _conn(sqlite_store) as conn:
        ref_id = _ref(conn, etat='en_cours')
        conn.commit()
        maj_etat_lazy(conn, ref_id)
    with _conn(sqlite_store) as conn:
        row = conn.execute(
            "SELECT etat FROM referentiel_niveaux WHERE id=?", (ref_id,)
        ).fetchone()
    assert row['etat'] == 'valide'


def test_lazy_referentiel_inconnu_leve_value_error(sqlite_store):
    with _conn(sqlite_store) as conn:
        with pytest.raises(ValueError):
            maj_etat_lazy(conn, 'ref_inexistant_xyz')
