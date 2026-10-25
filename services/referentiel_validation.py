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


# v0.52.4 (M3) — Atomes que le modèle « Fiches de résumé par objectif »
# (gabarit `sixieme`) ne publie pas : ils ne bloquent pas sa validation.
_TABLES_HORS_MODELE_FICHES = ('notions', 'methodes', 'cartes_automatisme')


def _filtre_perimetre_sql(type_ref: str) -> str:
    """v0.54.0 (RI1) — filtre SQL sur la colonne `sequence` d'une table
    d'atomes : principal = ni archives `Xnn` ni mises en route `Mnn` (v0.52.4,
    v0.53.0) ; mise en route = les `Mnn` seulement."""
    if (type_ref or "principal") == "mer":
        return " AND COALESCE(sequence, '') GLOB 'M[0-9][0-9]'"
    return (" AND COALESCE(sequence, '') NOT LIKE 'X%'"
            " AND COALESCE(sequence, '') NOT GLOB 'M[0-9][0-9]'")


def compter_atomes_perimetre(conn: sqlite3.Connection, niveau: str,
                             gabarit: str = 'cycle4',
                             type_ref: str = 'principal') -> dict:
    """{"non_valides": {table: n}, "total": {table: n}} des atomes du
    périmètre du référentiel (RI1) ; modèle « Fiches » : notions, méthodes et
    cartes ne comptent pas (M3)."""
    from services.gabarits_documents import est_modele_fiches
    fiches = est_modele_fiches(gabarit)
    non_valides: dict[str, int] = {}
    total: dict[str, int] = {}
    for t in _TABLES_ATOMES:
        if fiches and t in _TABLES_HORS_MODELE_FICHES:
            non_valides[t] = total[t] = 0
            continue
        try:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
            filtre = _filtre_perimetre_sql(type_ref) if "sequence" in cols else ""
            row = conn.execute(
                f"SELECT COUNT(*), SUM(CASE WHEN etat_code != 'valide' THEN 1 ELSE 0 END) "
                f"FROM {t} WHERE niveau = ?" + filtre, (niveau,)).fetchone()
            total[t] = int(row[0] or 0) if row else 0
            non_valides[t] = int(row[1] or 0) if row else 0
        except sqlite3.OperationalError:
            # Table absente : pas de blocage
            non_valides[t] = total[t] = 0
    return {"non_valides": non_valides, "total": total}


def _compter_atomes_non_valides(conn: sqlite3.Connection,
                                  niveau: str,
                                  gabarit: str = 'cycle4',
                                  type_ref: str = 'principal') -> dict[str, int]:
    """Pour chaque table d'atomes, compte ceux du niveau dont
    `etat_code != 'valide'`. Retourne un dict {table: count} (count=0
    si table absente / niveau vide).

    v0.52.4 (M3) :
      - les archives `Xnn` (anciens exercices de 6e, v0.52.0 D1) ne sont
        jamais comptées, quel que soit le modèle (le cycle 4 n'en a pas) ;
      - modèle « Fiches de résumé par objectif » : notions, méthodes et
        cartes d'automatisme ne sont pas comptées (0).
    v0.53.0 (MR7) — ni les mises en route Mnn ; v0.54.0 (RI1) — un
    référentiel de mise en route ne compte que ses `Mnn`."""
    return compter_atomes_perimetre(conn, niveau, gabarit, type_ref)["non_valides"]


def _compter_evaluations_non_valides(conn: sqlite3.Connection,
                                       niveau: str,
                                       type_ref: str | None = None) -> int:
    """v0.54.0 (RI1) — `type_ref` donné : évaluations du périmètre seulement
    (principal : sans les tests courts des mises en route ; mise en route :
    ses tests courts). Sans `type_ref` : toutes celles du niveau (avant)."""
    try:
        if type_ref is not None:
            from services.referentiels_internes import evaluations_du_perimetre
            return sum(1 for e in evaluations_du_perimetre(conn, niveau, type_ref)
                       if e["etat_code"] != "valide")
        row = conn.execute(
            "SELECT COUNT(*) FROM evaluations "
            "WHERE niveau = ? AND etat_code != 'valide'",
            (niveau,),
        ).fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        return 0


def sequences_non_validees(conn: sqlite3.Connection, niveau: str,
                           type_ref: str) -> list[str]:
    """v0.54.0 (RI5) — codes des séquences du périmètre qui ne sont pas
    « validées » dans l'atelier (sequences_par_niveau.etat_code). Le passage à
    « validée » contrôle la séquence : F et A, critères et fiche par objectif
    au principal (M2), MR6 pour une mise en route."""
    try:
        from services.referentiels_internes import sequences_du_perimetre
        return [s["code"] for s in sequences_du_perimetre(conn, niveau, type_ref)
                if s["etat_code"] != "valide"]
    except sqlite3.OperationalError:
        return []


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
    # v0.52.4 (D2) — Seuls les types du gabarit du référentiel comptent : un
    # document actif de l'autre modèle (resté en base après un changement de
    # modèle, G5) ne bloque pas la validation.
    from services.gabarits_documents import types_du_referentiel
    du_gabarit = set(types_du_referentiel(conn, ref_id))
    rows = [r for r in rows if r['type_document'] in du_gabarit]

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

    from services.gabarits_documents import gabarit_du_referentiel, est_modele_fiches
    from services.referentiels_internes import type_du_referentiel
    gabarit = gabarit_du_referentiel(conn, ref_id)
    type_ref = type_du_referentiel(conn, ref_id)
    atomes = _compter_atomes_non_valides(conn, niveau, gabarit, type_ref)
    # v0.54.0 (RI1) — évaluations du périmètre : les tests courts des mises
    # en route ne bloquent plus le principal (et inversement).
    evals = _compter_evaluations_non_valides(conn, niveau, type_ref)
    docs = _statut_documents_du_referentiel(conn, ref_id)
    # v0.54.0 (RI5) — modèle « Fiches » : chaque séquence du périmètre doit
    # être validée dans l'atelier (contrôle de la séquence). « Notions et
    # méthodes » : inchangé (les séquences ne sont pas exigées).
    seq_nv = (sequences_non_validees(conn, niveau, type_ref)
              if est_modele_fiches(gabarit) else [])

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
    if seq_nv:
        raisons.append(f"{len(seq_nv)} séquence(s) non validée(s) dans l'atelier : "
                       + ", ".join(seq_nv))
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
            'sequences_non_validees':  seq_nv,                 # v0.54.0 (RI5)
        },
        'type_ref':     type_ref,                              # v0.54.0
        'gabarit':      gabarit,
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
