"""services/referentiel_validation.py — v0.15.2.8 (partie B1)

Auto-validation des référentiels.

Règle métier (Laurent, v0.15.2.8) :

    Un référentiel passe automatiquement en état `valide` quand
    TOUS les éléments suivants sont vrais :
      - Tous les atomes du niveau (notions, méthodes, exercices,
        fiches de résumé, cartes d'automatisme) sont à `etat_code='valide'`.
      - Toutes les évaluations du niveau sont à `etat_code='valide'`.
      - Tous les documents actifs du référentiel ont été compilés
        avec succès (`compile_ok=1`) et ne sont pas périmés.

    Si l'un quelconque de ces critères devient faux après avoir été
    vrai, le référentiel retombe à `en_cours` à la prochaine lecture
    lazy (sauf s'il a déjà été figé : `fige` est immuable).

Périmètre v0.15.2.8 partie B1 — auto-validation seulement.
La transition `valide → fige` reste manuelle (chantier B2, v0.15.2.9).

Granularité
-----------
Per-document (un seul `compile_date`/`compile_ok` par doc, cf. v0.15.2.6).
Le périmètre des atomes pertinents par type de document est défini dans
`services.peremption_atomes`.

API
---
`evaluer_eligibilite_validation(conn, ref_id) -> dict`
    Évalue les critères et retourne un diagnostic structuré
    (sans toucher à l'état du référentiel).

`maj_etat_lazy(conn, ref_id) -> str`
    Évalue ET applique la transition d'état si applicable.
    Retourne l'état après mise à jour.
    Ne touche jamais aux états terminaux (`fige`, `annule`).
"""
from __future__ import annotations

import sqlite3

from services.peremption_atomes import max_mtime_atomes_pertinents


# États autorisés du référentiel (rappel — cf. services/referentiels.py).
_ETATS_TERMINAUX = {'verrouille', 'utilise', 'annule'}
# v0.15.3 — Trois états terminaux pour `maj_etat_lazy` :
#   verrouille : JSON+PDFs produits, déverrouillable manuellement (pas via lazy)
#   utilise    : associé à ≥1 progression
#   annule     : référentiel concurrent écarté lors du verrouillage d'un autre
# Le lazy ne touche jamais ces 3 états.


# Liste des tables d'atomes à vérifier intégralement pour la validation
# d'un référentiel d'un niveau. C'est l'ensemble des tables d'atomes
# tagué par un `etat_code` et un `niveau`.
_TABLES_ATOMES = ('notions', 'methodes', 'exercices', 'fiches_resume',
                  'cartes_automatisme')


def _niveau_du_referentiel(conn: sqlite3.Connection, ref_id: str) -> str | None:
    row = conn.execute(
        "SELECT niveau FROM referentiel_niveaux WHERE id = ?", (ref_id,)
    ).fetchone()
    if row is None:
        return None
    return row['niveau'] if isinstance(row, sqlite3.Row) else row[0]


def _compter_atomes_non_valides(conn: sqlite3.Connection,
                                  niveau: str) -> dict[str, int]:
    """Pour chaque table d'atomes, compte ceux du niveau dont
    `etat_code != 'valide'`. Retourne un dict {table: count} (count=0
    si table absente / niveau vide)."""
    res: dict[str, int] = {}
    for t in _TABLES_ATOMES:
        try:
            row = conn.execute(
                f"SELECT COUNT(*) FROM {t} "
                f"WHERE niveau = ? AND etat_code != 'valide'",
                (niveau,),
            ).fetchone()
            res[t] = int(row[0]) if row else 0
        except sqlite3.OperationalError:
            # Table absente : pas de blocage
            res[t] = 0
    return res


def _compter_evaluations_non_valides(conn: sqlite3.Connection,
                                       niveau: str) -> int:
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM evaluations "
            "WHERE niveau = ? AND etat_code != 'valide'",
            (niveau,),
        ).fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        return 0


def _statut_documents_du_referentiel(conn: sqlite3.Connection,
                                       ref_id: str) -> dict[str, int]:
    """Pour les documents ACTIFS du référentiel, compte :
      - documents non compilés (compile_ok != 1 ou compile_date NULL)
      - documents périmés (atome pertinent modifié après compile_date)
    Un document inactif (options.actif=False) est ignoré : il ne bloque
    pas la validation.
    """
    rows = conn.execute("""
        SELECT id, type_document, options, compile_ok, compile_date,
               compile_en_cours, referentiel_id
          FROM referentiel_documents
         WHERE referentiel_id = ?
    """, (ref_id,)).fetchall()

    niveau = _niveau_du_referentiel(conn, ref_id)
    non_compiles = 0
    perimes = 0

    import json
    for r in rows:
        try:
            options = json.loads(r['options'] or '{}')
        except (json.JSONDecodeError, TypeError):
            options = {}
        if not options.get('actif', False):
            continue   # documents inactifs : pas de blocage

        if not r['compile_ok'] or not r['compile_date']:
            non_compiles += 1
            continue

        # Documents compilés : vérifier péremption par atome pertinent
        if niveau:
            max_mtime = max_mtime_atomes_pertinents(
                conn, r['type_document'], niveau
            )
            if max_mtime is not None and max_mtime > r['compile_date']:
                perimes += 1

    return {'non_compiles': non_compiles, 'perimes': perimes}


def evaluer_eligibilite_validation(conn: sqlite3.Connection,
                                     ref_id: str) -> dict:
    """Évalue si le référentiel est éligible à `valide`.

    Ne modifie PAS l'état du référentiel : c'est purement un calcul.

    Returns
    -------
    dict
        Structure :
          {
            'eligible':         bool,
            'raisons':          [str],   # vide si éligible
            'details': {
                'atomes_non_valides': {'notions': N, 'methodes': N, ...},
                'evaluations_non_valides': N,
                'documents_non_compiles': N,
                'documents_perimes': N,
            },
            'etat_courant':     str,     # état actuel du référentiel
            'niveau':           str,
          }
    """
    row = conn.execute(
        "SELECT id, niveau, etat FROM referentiel_niveaux WHERE id = ?",
        (ref_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Référentiel introuvable : {ref_id}")
    niveau = row['niveau']
    etat = row['etat']

    atomes = _compter_atomes_non_valides(conn, niveau)
    evals = _compter_evaluations_non_valides(conn, niveau)
    docs = _statut_documents_du_referentiel(conn, ref_id)

    raisons: list[str] = []
    for table, n in atomes.items():
        if n > 0:
            # Libellé lisible pour l'UI : « 3 notions non validées »
            libelle = {
                'notions': 'notions',
                'methodes': 'méthodes',
                'exercices': 'exercices',
                'fiches_resume': 'fiches de résumé',
                'cartes_automatisme': "cartes d'automatisme",
            }.get(table, table)
            raisons.append(f"{n} {libelle} non validé(e)s")
    if evals > 0:
        raisons.append(f"{evals} évaluation(s) non validée(s)")
    if docs['non_compiles'] > 0:
        raisons.append(f"{docs['non_compiles']} document(s) non compilé(s)")
    if docs['perimes'] > 0:
        raisons.append(f"{docs['perimes']} document(s) périmé(s)")

    eligible = (len(raisons) == 0)

    return {
        'eligible':     eligible,
        'raisons':      raisons,
        'details': {
            'atomes_non_valides':      atomes,
            'evaluations_non_valides': evals,
            'documents_non_compiles':  docs['non_compiles'],
            'documents_perimes':       docs['perimes'],
        },
        'etat_courant': etat,
        'niveau':       niveau,
    }


def maj_etat_lazy(conn: sqlite3.Connection, ref_id: str) -> str:
    """Met à jour l'état du référentiel selon l'éligibilité actuelle
    (mode lazy : à appeler à la lecture du référentiel ou sur demande
    explicite via un endpoint).

    Transitions appliquées :
      - en_cours + éligible  → valide
      - valide   + non éligible → en_cours (revient en arrière si quelque
                                  chose a changé : nouveau document, atome
                                  modifié, etc.)
      - verrouille, utilise, annule → JAMAIS modifiés (états terminaux,
                                  cf. _ETATS_TERMINAUX).

    Retourne l'état après mise à jour.

    Lève ValueError si le référentiel est introuvable.
    """
    row = conn.execute(
        "SELECT etat FROM referentiel_niveaux WHERE id = ?", (ref_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Référentiel introuvable : {ref_id}")
    etat = row['etat']

    # États terminaux : on ne touche jamais.
    if etat in _ETATS_TERMINAUX:
        return etat

    elig = evaluer_eligibilite_validation(conn, ref_id)
    nouveau = etat
    if etat == 'en_cours' and elig['eligible']:
        nouveau = 'valide'
    elif etat == 'valide' and not elig['eligible']:
        nouveau = 'en_cours'

    if nouveau != etat:
        conn.execute(
            "UPDATE referentiel_niveaux SET etat = ? WHERE id = ?",
            (nouveau, ref_id),
        )
        conn.commit()
    return nouveau
