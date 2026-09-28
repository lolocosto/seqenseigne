"""tests/test_v0_15_2_6_peremption_atomes.py — v0.15.2.6

Péremption ciblée par type de document : chaque type a sa liste de
tables d'atomes pertinentes ; modifier un atome non-pertinent ne périme
plus le document.

Décisions actées avec Laurent et protégées par tests nommés ici :
- Un test exhaustif vérifie que TOUS les TYPES_DOCUMENT figurent dans le
  mapping ATOMES_PAR_TYPE_DOCUMENT. Garde-fou si un nouveau type est
  ajouté sans mapping.
- Le mapping spécifique pour chaque type est verrouillé.
- livret_plans : aucune table d'atomes (la dépendance à l'assemblage est
  hors scope de cette version).
- Comportement bout en bout : modifier un atome pertinent → 'perime' ;
  modifier un atome non-pertinent → 'ok'.
"""
from __future__ import annotations

from pathlib import Path
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import referentiel_documents_compilation as svc_cmp  # noqa: E402
from services.peremption_atomes import (  # noqa: E402
    ATOMES_PAR_TYPE_DOCUMENT,
    tables_atomes_pertinentes,
    max_mtime_atomes_pertinents,
)
from services.referentiel_documents import TYPES_DOCUMENT  # noqa: E402


# ── Mapping : exhaustivité et contenu ──────────────────────────────────────


def test_mapping_couvre_tous_les_types_document():
    """Garde-fou : tous les TYPES_DOCUMENT doivent figurer dans le
    mapping ATOMES_PAR_TYPE_DOCUMENT. Si un nouveau type est ajouté à
    TYPES_DOCUMENT sans mise à jour de ce mapping, ce test échoue et
    indique le manquant.
    """
    manquants = set(TYPES_DOCUMENT) - set(ATOMES_PAR_TYPE_DOCUMENT.keys())
    surplus  = set(ATOMES_PAR_TYPE_DOCUMENT.keys()) - set(TYPES_DOCUMENT)
    assert manquants == set(), (
        f"Types absents du mapping ATOMES_PAR_TYPE_DOCUMENT : {manquants}. "
        "Ajouter une entrée dans services/peremption_atomes.py."
    )
    assert surplus == set(), (
        f"Types fantômes dans ATOMES_PAR_TYPE_DOCUMENT (pas dans "
        f"TYPES_DOCUMENT) : {surplus}."
    )


def test_mapping_decisions_laurent_v0_15_2_6():
    """Décisions actées avec Laurent (cf. docstring du module). Ce test
    verrouille les choix pour qu'un changement ultérieur soit conscient.
    """
    attendu = {
        'livret_sequence':        ['notions', 'methodes', 'exercices'],
        'livret_exercices':       ['exercices'],
        'livret_cours':           ['notions', 'methodes'],
        'livret_fiches':          ['fiches_resume'],
        'livret_plans':           [],
        'livret_corriges':        ['exercices'],
        'evaluation':             ['exercices'],
        'livret_cartes_recap':    ['cartes_automatisme'],
        'livret_cartes_planches': ['cartes_automatisme'],
    }
    assert ATOMES_PAR_TYPE_DOCUMENT == attendu


def test_livret_plans_jamais_perime_par_atome():
    """livret_plans dépend de l'assemblage de séquence, pas des atomes.
    `tables_atomes_pertinentes` doit renvoyer une liste vide.
    """
    assert tables_atomes_pertinentes('livret_plans') == []


def test_type_inconnu_fallback_large():
    """Un type non mappé doit retomber sur le fallback large (tous les
    atomes du niveau) — mieux vaut sur-périmer qu'ignorer.
    """
    tables = tables_atomes_pertinentes('type_inexistant_42')
    # On vérifie la composition sans imposer l'ordre exact
    assert set(tables) == {
        'notions', 'methodes', 'exercices', 'fiches_resume',
        'cartes_automatisme',
    }


# ── max_mtime_atomes_pertinents : comportement BDD ─────────────────────────


def _conn(store):
    return store._conn()


def _set_mtime(conn, table, niveau, mtime):
    """Insère un atome stub avec mtime explicite. Les schémas diffèrent
    selon les tables : on insère le minimum requis pour chaque.
    """
    if table == 'notions':
        conn.execute("""INSERT INTO notions
            (id, niveau, sequence, num_connaissance, titre, corps,
             etat_code, mtime)
            VALUES (?, ?, 'S01', 1, 'T', '', 'valide', ?)""",
            (f"n_{uuid.uuid4().hex[:8]}", niveau, mtime))
    elif table == 'methodes':
        conn.execute("""INSERT INTO methodes
            (id, niveau, sequence, num_methode, titre, corps,
             etat_code, mtime)
            VALUES (?, ?, 'S01', 1, 'T', '', 'valide', ?)""",
            (f"m_{uuid.uuid4().hex[:8]}", niveau, mtime))
    elif table == 'exercices':
        conn.execute("""INSERT INTO exercices
            (id, niveau, sequence, num, serie, titre, enonce, corrige,
             etat_code, mtime)
            VALUES (?, ?, 'S01', 1, 'F', 'T', '', '', 'valide', ?)""",
            (f"e_{uuid.uuid4().hex[:8]}", niveau, mtime))
    elif table == 'fiches_resume':
        conn.execute("""INSERT INTO fiches_resume
            (id, niveau, sequence, num_fiche, titre, etat_code, mtime)
            VALUES (?, ?, 'S01', 1, 'T', 'valide', ?)""",
            (f"f_{uuid.uuid4().hex[:8]}", niveau, mtime))
    elif table == 'cartes_automatisme':
        conn.execute("""INSERT INTO cartes_automatisme
            (id, niveau, sequence, num, type_pedago, type_tech, titre,
             lien_type, lien_id, recto, verso, variables,
             etat_code, ordre, mtime)
            VALUES (?, ?, 'S01', 1, 'definition', 'fixe', 'T', NULL, NULL,
                    '', '', '', 'valide', 0, ?)""",
            (f"c_{uuid.uuid4().hex[:8]}", niveau, mtime))


def test_max_mtime_ignore_atomes_non_pertinents(sqlite_store):
    """Pour livret_cartes_recap, seules les cartes comptent. Une notion
    plus récente que toutes les cartes ne doit PAS apparaître dans le
    max(mtime) renvoyé.
    """
    with _conn(sqlite_store) as conn:
        _set_mtime(conn, 'cartes_automatisme', 'N10', '2025-01-01 00:00:00')
        _set_mtime(conn, 'notions',            'N10', '2026-12-31 23:59:59')
        conn.commit()
        m = max_mtime_atomes_pertinents(conn, 'livret_cartes_recap', 'N10')
    # On doit obtenir la date de la carte, pas celle de la notion
    assert m == '2025-01-01 00:00:00'


def test_max_mtime_combine_plusieurs_tables_pertinentes(sqlite_store):
    """livret_sequence couvre notions+methodes+exercices : le max doit
    prendre en compte les trois.
    """
    with _conn(sqlite_store) as conn:
        _set_mtime(conn, 'notions',   'N10', '2025-01-01 00:00:00')
        _set_mtime(conn, 'methodes',  'N10', '2026-05-15 12:00:00')
        _set_mtime(conn, 'exercices', 'N10', '2025-12-25 00:00:00')
        conn.commit()
        m = max_mtime_atomes_pertinents(conn, 'livret_sequence', 'N10')
    assert m == '2026-05-15 12:00:00'  # le plus récent des trois


def test_max_mtime_livret_plans_renvoie_none(sqlite_store):
    """livret_plans : aucune table pertinente → None, même si plein
    d'atomes ont été modifiés.
    """
    with _conn(sqlite_store) as conn:
        _set_mtime(conn, 'notions',            'N10', '2026-01-01 00:00:00')
        _set_mtime(conn, 'exercices',          'N10', '2026-02-01 00:00:00')
        _set_mtime(conn, 'cartes_automatisme', 'N10', '2026-03-01 00:00:00')
        conn.commit()
        m = max_mtime_atomes_pertinents(conn, 'livret_plans', 'N10')
    assert m is None


def test_max_mtime_niveau_vide_renvoie_none(sqlite_store):
    """Aucun atome au niveau → None (pas une exception)."""
    with _conn(sqlite_store) as conn:
        m = max_mtime_atomes_pertinents(conn, 'livret_sequence', 'N09')
    assert m is None


def test_max_mtime_filtre_par_niveau(sqlite_store):
    """Une carte au N11 ne doit pas influencer le max pour N10."""
    with _conn(sqlite_store) as conn:
        _set_mtime(conn, 'cartes_automatisme', 'N10', '2025-01-01 00:00:00')
        _set_mtime(conn, 'cartes_automatisme', 'N11', '2026-12-31 23:59:59')
        conn.commit()
        m = max_mtime_atomes_pertinents(conn, 'livret_cartes_recap', 'N10')
    assert m == '2025-01-01 00:00:00'


# ── etat_effectif_document : intégration bout-en-bout ──────────────────────


def _doc_de_base(referentiel_id, type_document, compile_date):
    return {
        'id':                 f"doc_{uuid.uuid4().hex[:8]}",
        'referentiel_id':     referentiel_id,
        'type_document':      type_document,
        'options':            {'actif': True},
        'compile_en_cours':   False,
        'compile_ok':         1,
        'compile_date':       compile_date,
        'compile_log':        None,
    }


def _ref_minimal(conn, niveau='N10'):
    ref_id = f"ref_{uuid.uuid4().hex[:8]}"
    conn.execute("""
        INSERT INTO referentiel_niveaux
            (id, niveau, version, date_debut, date_fin, description, etat)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ref_id, niveau, '2025_test', '2025-09-01', '2026-08-31',
          'Test', 'en_cours'))
    return ref_id


def test_etat_modif_atome_non_pertinent_reste_ok(sqlite_store):
    """Scénario clé : un livret de cartes compilé HIER, une notion
    modifiée AUJOURD'HUI. Avant v0.15.2.6 : 'perime'. Après : 'ok'.
    """
    with _conn(sqlite_store) as conn:
        ref_id = _ref_minimal(conn)
        # Compile la veille
        doc = _doc_de_base(ref_id, 'livret_cartes_recap',
                           '2026-01-01 00:00:00')
        # Notion modifiée le lendemain (hors scope)
        _set_mtime(conn, 'notions', 'N10', '2026-01-02 00:00:00')
        conn.commit()
        etat = svc_cmp.etat_effectif_document(conn, doc)
    assert etat == 'ok'


def test_etat_modif_atome_pertinent_passe_a_perime(sqlite_store):
    """Inverse : une carte modifiée APRÈS la compile périme bien le
    livret de cartes (cas légitime de péremption).
    """
    with _conn(sqlite_store) as conn:
        ref_id = _ref_minimal(conn)
        doc = _doc_de_base(ref_id, 'livret_cartes_recap',
                           '2026-01-01 00:00:00')
        _set_mtime(conn, 'cartes_automatisme', 'N10',
                   '2026-01-02 00:00:00')
        conn.commit()
        etat = svc_cmp.etat_effectif_document(conn, doc)
    assert etat == 'perime'


def test_etat_livret_plans_modif_atome_reste_ok(sqlite_store):
    """livret_plans : MÊME une modif d'exercice (pertinent pour d'autres
    types) ne le périme pas, car son mapping est vide.
    """
    with _conn(sqlite_store) as conn:
        ref_id = _ref_minimal(conn)
        doc = _doc_de_base(ref_id, 'livret_plans',
                           '2026-01-01 00:00:00')
        _set_mtime(conn, 'exercices', 'N10', '2026-06-15 00:00:00')
        conn.commit()
        etat = svc_cmp.etat_effectif_document(conn, doc)
    assert etat == 'ok'


def test_etat_livret_sequence_modif_notion_passe_a_perime(sqlite_store):
    """livret_sequence inclut notions : une notion plus récente le périme."""
    with _conn(sqlite_store) as conn:
        ref_id = _ref_minimal(conn)
        doc = _doc_de_base(ref_id, 'livret_sequence',
                           '2026-01-01 00:00:00')
        _set_mtime(conn, 'notions', 'N10', '2026-02-01 00:00:00')
        conn.commit()
        etat = svc_cmp.etat_effectif_document(conn, doc)
    assert etat == 'perime'


def test_etat_evaluation_modif_notion_reste_ok(sqlite_store):
    """evaluation = exercices SEULEMENT (cf. décision Laurent v0.15.2.6).
    Une notion modifiée ne périme pas l'évaluation.
    """
    with _conn(sqlite_store) as conn:
        ref_id = _ref_minimal(conn)
        doc = _doc_de_base(ref_id, 'evaluation',
                           '2026-01-01 00:00:00')
        _set_mtime(conn, 'notions', 'N10', '2026-06-01 00:00:00')
        conn.commit()
        etat = svc_cmp.etat_effectif_document(conn, doc)
    assert etat == 'ok'


def test_etat_evaluation_modif_exercice_passe_a_perime(sqlite_store):
    """evaluation est bien périmée par un exercice plus récent."""
    with _conn(sqlite_store) as conn:
        ref_id = _ref_minimal(conn)
        doc = _doc_de_base(ref_id, 'evaluation',
                           '2026-01-01 00:00:00')
        _set_mtime(conn, 'exercices', 'N10', '2026-06-01 00:00:00')
        conn.commit()
        etat = svc_cmp.etat_effectif_document(conn, doc)
    assert etat == 'perime'
