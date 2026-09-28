"""services/peremption_atomes.py — v0.15.2.6

Mapping `type_document → tables d'atomes` qui périment ce document.

Contexte
--------
Avant v0.15.2.6, `etat_effectif_document` marquait un document `perime`
si N'IMPORTE QUEL atome du niveau avait été modifié après `compile_date`
(notions, méthodes, exercices, fiches_resume, cartes_automatisme tous
confondus). Conséquence : modifier une notion périmait le livret de
cartes alors que les cartes n'avaient pas bougé.

Cette version cible chaque type de document sur ses tables d'atomes
réellement pertinentes.

Granularité
-----------
La péremption reste **par document** (un seul `compile_date` par doc en
BDD). Les documents multi-cibles (livret_sequence, livret_cartes_planches,
evaluation, livret_corriges) sont périmés si l'un quelconque de leurs
atomes pertinents du niveau a changé après leur compile_date — on ne
distingue pas cible par cible.

Décisions actées avec Laurent (v0.15.2.6) :
- livret_sequence       → notions, méthodes, exercices
- livret_exercices      → exercices (niveau global)
- livret_cours          → notions, méthodes (niveau global)
- livret_fiches         → fiches_resume
- livret_plans          → aucun atome (assemblage de séquence uniquement,
                          hors scope atomes — sera câblé quand l'atelier
                          assemblage exposera ses propres mtimes)
- livret_corriges       → exercices
- evaluation            → exercices (assemblage d'évaluation également
                          hors scope atomes pour cette version)
- livret_cartes_recap   → cartes_automatisme
- livret_cartes_planches→ cartes_automatisme

Le mapping est un **dict en dur** (décision archi, pas donnée
configurable). Un test nommé énumère TOUS les TYPES_DOCUMENT et vérifie
leur présence : si un nouveau type est ajouté à TYPES_DOCUMENT sans
être mappé ici, le test échoue.
"""
from __future__ import annotations

import sqlite3


# Mapping type_document → liste de tables d'atomes.
# Liste vide = jamais périmé par les atomes (cas livret_plans).
# Filtrage SQL : toujours `WHERE niveau = ?` (péremption par document,
# pas par cible — cf. docstring du module).
ATOMES_PAR_TYPE_DOCUMENT: dict[str, list[str]] = {
    'livret_sequence':        ['notions', 'methodes', 'exercices'],
    'livret_exercices':       ['exercices'],
    'livret_cours':           ['notions', 'methodes'],
    'livret_fiches':          ['fiches_resume'],
    'livret_plans':           [],   # assemblage uniquement (hors scope atomes)
    'livret_corriges':        ['exercices'],
    'evaluation':             ['exercices'],
    'livret_cartes_recap':    ['cartes_automatisme'],
    'livret_cartes_planches': ['cartes_automatisme'],
}


# Fallback conservateur si un type inconnu apparaît : on retombe sur
# l'ancien comportement (tous les atomes du niveau). C'est volontaire :
# mieux vaut sur-périmer (et donc recompiler) qu'ignorer un changement
# pertinent. Le test nommé garantit qu'aucun type connu ne tombe sur
# ce fallback.
_FALLBACK_TOUS_ATOMES: list[str] = [
    'notions', 'methodes', 'exercices', 'fiches_resume', 'cartes_automatisme'
]


def tables_atomes_pertinentes(type_document: str) -> list[str]:
    """Tables d'atomes dont le mtime périme un document de ce type.

    Liste vide = le document n'est jamais périmé par un changement
    d'atome (ex. livret_plans).
    Type inconnu = fallback large (tous les atomes du niveau), pour
    rester correct si quelqu'un ajoute un type sans mettre à jour le
    mapping. Un test nommé empêche normalement ce cas.
    """
    if type_document in ATOMES_PAR_TYPE_DOCUMENT:
        return list(ATOMES_PAR_TYPE_DOCUMENT[type_document])
    return list(_FALLBACK_TOUS_ATOMES)


def max_mtime_atomes_pertinents(conn: sqlite3.Connection,
                                 type_document: str,
                                 niveau: str) -> str | None:
    """Max(mtime) des atomes pertinents pour ce type de document, au
    niveau donné.

    Renvoie None si :
      - aucune table d'atomes n'est pertinente pour ce type
        (ex. livret_plans) — le document n'est alors jamais périmé par
        un changement d'atome ;
      - aucun atome existant n'a de mtime (niveau vide).

    Les colonnes mtime sont stockées en chaîne ISO "YYYY-MM-DD HH:MM:SS"
    en UTC : la comparaison string fonctionne tant que tous les mtime
    sont à ce format (ce qui est le cas dans toute l'app).
    """
    tables = tables_atomes_pertinentes(type_document)
    if not tables:
        return None
    maxima: list[str] = []
    for t in tables:
        try:
            row = conn.execute(
                f"SELECT MAX(mtime) FROM {t} WHERE niveau = ?",
                (niveau,),
            ).fetchone()
            if row and row[0]:
                maxima.append(row[0])
        except sqlite3.OperationalError:
            # Table absente (rétrocompat tests minimalistes) : on ignore.
            continue
    return max(maxima) if maxima else None
