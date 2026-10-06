"""services/referentiel_documents.py — v0.13.6.4

Catalogue des documents publiables d'un référentiel niveau.

Modèle métier
-------------

Chaque référentiel a une liste de 9 entrées (une par type de document
PDF qu'il pourra produire). Chacune porte :
  - un booléen `actif` (dans `options`) pour décider de la publication
  - des options spécifiques au type (séries d'exos incluses, version
    des fiches résumé, etc.)

Cardinalité : 1 entrée par (referentiel_id, type_document). Tout ou
rien sur les séquences et évaluations (l'enseignant n'arbitre pas
séquence-par-séquence ni éval-par-éval).

Initialisation
--------------

`initialiser_documents_defaut(conn, referentiel_id)` est idempotent :
INSERT OR IGNORE sur chacun des 9 types. Appelable à la création du
référentiel ou au 1er accès à l'onglet "Documents à publier".

Validation
----------

`maj_options(conn, doc_id, options)` accepte un dict d'options
*partiel* (PATCH-like) ; il fusionne avec les options actuelles et
valide :
  - clés autorisées seulement (selon type)
  - types respectés (bool, str)
  - valeurs des champs énumérés respectées
Toute clé inconnue ou valeur invalide → DocumentErreur.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any


# ── Catalogue des 9 types et leurs options par défaut ───────────────────────

TYPES_DOCUMENT = (
    'livret_sequence',
    'livret_exercices',
    'livret_cours',
    'livret_fiches',
    'livret_plans',
    'livret_corriges',
    'evaluation',
    'livret_cartes_recap',
    'livret_cartes_planches',
)

# Ordre stable d'affichage dans l'UI (1..9).
ORDRE_AFFICHAGE = {t: i + 1 for i, t in enumerate(TYPES_DOCUMENT)}

# Valeurs autorisées pour les champs énumérés (radios).
ENUMS = {
    'inclure_fiches_resume_en_fin': ('non', 'completes', 'a_completer'),
    'version_fiches':               ('completes', 'a_completer'),
    # v0.48.1 — Découpage du livret de fiches de résumé.
    'decoupage_fiches':             ('annuel', 'par_sequence', 'les_deux'),
    'contenu':                      ('cours_seul', 'exercices_seul',
                                     'cours_et_exercices'),
}

OPTIONS_PAR_DEFAUT: dict[str, dict[str, Any]] = {
    'livret_sequence': {
        'actif': False,
        'contenu': 'cours_et_exercices',  # 'cours_seul' | 'exercices_seul' | 'cours_et_exercices'
        'inclure_plan_travail_en_tete': False,
        'inclure_fiches_resume_en_fin': 'non',
        'inclure_enonces_serie_a': True,
        'inclure_corriges_serie_r_ae': True,
        'inclure_corriges_serie_f': True,
        'inclure_corriges_serie_a': False,
        'inclure_corriges_serie_e': False,
        'inclure_corriges_remediation': False,
    },
    'livret_exercices': {
        'actif': False,
        'enonces_r_ae': True,
        'enonces_f': True,
        'enonces_a': True,
        'enonces_e': True,
        'enonces_remediation': True,
        'corriges_r_ae': True,
        'corriges_f': True,
        'corriges_a': False,
        'corriges_e': False,
        'corriges_remediation': False,
    },
    'livret_cours': {
        'actif': False,
        'inclure_fiches_resume_en_fin': 'non',
    },
    'livret_fiches': {
        'actif': False,
        'version_fiches': 'completes',
        'decoupage_fiches': 'annuel',   # v0.48.1 : 'annuel' | 'par_sequence' | 'les_deux'
    },
    'livret_plans': {
        'actif': False,
    },
    'livret_corriges': {
        'actif': False,
        'inclure_serie_r_ae': True,
        'inclure_serie_f': True,
        'inclure_serie_a': False,
        'inclure_serie_e': False,
    },
    'evaluation': {
        'actif': False,
    },
    'livret_cartes_recap': {
        'actif': False,
    },
    'livret_cartes_planches': {
        'actif': False,
    },
}

# Sanity : les 9 types ont leurs défauts définis.
assert set(OPTIONS_PAR_DEFAUT.keys()) == set(TYPES_DOCUMENT), \
    "OPTIONS_PAR_DEFAUT incomplet"


# ── Erreurs métier ──────────────────────────────────────────────────────────

class DocumentErreur(Exception):
    """Erreur métier dans la manipulation d'un document publiable."""
    def __init__(self, message: str, code: str = 'document_erreur',
                 details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class DocumentIntrouvable(DocumentErreur):
    def __init__(self, doc_id: str):
        super().__init__(f"Document publiable introuvable : {doc_id}",
                         code='document_introuvable')


# ── API publique ────────────────────────────────────────────────────────────


def lister_documents(conn: sqlite3.Connection, referentiel_id: str,
                     data_dir=None) -> list[dict]:
    """Liste les documents publiables d'un référentiel.

    Idempotence : si le référentiel n'a aucun document déclaré, on
    initialise les 9 par défaut (cas premier accès à l'onglet).

    Retourne une liste de dicts : `{id, type_document, options (dict
    Python), ordre, mtime, referentiel_id, compile_ok, compile_date,
    compile_log, compile_en_cours, etat_effectif}`. Triée par `ordre`
    croissant.

    v0.13.6.5.1 : ajout des colonnes compile_* et du champ calculé
    `etat_effectif` (cf. services.referentiel_documents_compilation).
    """
    rows = conn.execute("""
        SELECT id, referentiel_id, type_document, options, ordre, mtime,
               compile_ok, compile_date, compile_log, compile_en_cours
          FROM referentiel_documents
         WHERE referentiel_id = ?
         ORDER BY ordre, type_document
    """, (referentiel_id,)).fetchall()

    if not rows:
        # Initialisation auto et relecture.
        initialiser_documents_defaut(conn, referentiel_id)
        rows = conn.execute("""
            SELECT id, referentiel_id, type_document, options, ordre, mtime,
                   compile_ok, compile_date, compile_log, compile_en_cours
              FROM referentiel_documents
             WHERE referentiel_id = ?
             ORDER BY ordre, type_document
        """, (referentiel_id,)).fetchall()

    # Import tardif pour éviter une dépendance circulaire à l'import
    # du module (referentiel_documents_compilation importe ce module).
    from services.referentiel_documents_compilation import (
        etat_effectif_document,
    )

    out = []
    for r in rows:
        try:
            opts = json.loads(r['options']) if r['options'] else {}
        except (TypeError, json.JSONDecodeError):
            opts = {}
        defaut = OPTIONS_PAR_DEFAUT.get(r['type_document'], {})
        doc = {
            'id':                r['id'],
            'referentiel_id':    r['referentiel_id'],
            'type_document':     r['type_document'],
            'options':           {**defaut, **opts},
            'ordre':             r['ordre'],
            'mtime':             r['mtime'],
            'compile_ok':        r['compile_ok'],
            'compile_date':      r['compile_date'],
            'compile_log':       r['compile_log'],
            'compile_en_cours':  bool(r['compile_en_cours']) if r['compile_en_cours'] is not None else False,
        }
        doc['etat_effectif'] = etat_effectif_document(conn, doc, data_dir)
        out.append(doc)
    return out


def initialiser_documents_defaut(conn: sqlite3.Connection,
                                 referentiel_id: str) -> None:
    """Insère les 9 entrées par défaut pour ce référentiel.

    Idempotent : INSERT OR IGNORE sur (referentiel_id, type_document).
    Appelable en toute sécurité à plusieurs reprises.
    """
    for type_doc in TYPES_DOCUMENT:
        opts = OPTIONS_PAR_DEFAUT[type_doc]
        conn.execute("""
            INSERT OR IGNORE INTO referentiel_documents
                (id, referentiel_id, type_document, options, ordre)
            VALUES (?, ?, ?, ?, ?)
        """, (
            f"rd_{uuid.uuid4().hex[:12]}",
            referentiel_id,
            type_doc,
            json.dumps(opts, ensure_ascii=False),
            ORDRE_AFFICHAGE[type_doc],
        ))
    conn.commit()


def maj_options(conn: sqlite3.Connection, doc_id: str,
                options_partielles: dict) -> dict:
    """Met à jour les options d'un document publiable (PATCH-like).

    `options_partielles` est fusionné avec les options actuelles ;
    seules les clés autorisées pour le type sont acceptées. Valeurs
    énumérées vérifiées.

    Retourne le document complet (avec ses options fusionnées avec les
    défauts) ou lève DocumentErreur si validation échoue.
    """
    row = conn.execute("""
        SELECT id, referentiel_id, type_document, options, ordre, mtime
          FROM referentiel_documents WHERE id = ?
    """, (doc_id,)).fetchone()
    if row is None:
        raise DocumentIntrouvable(doc_id)

    type_doc = row['type_document']
    try:
        opts_courantes = json.loads(row['options']) if row['options'] else {}
    except (TypeError, json.JSONDecodeError):
        opts_courantes = {}

    nouvelles = _valider_options(type_doc, options_partielles)
    fusionne = {**opts_courantes, **nouvelles}

    conn.execute("""
        UPDATE referentiel_documents
           SET options = ?, mtime = CURRENT_TIMESTAMP
         WHERE id = ?
    """, (json.dumps(fusionne, ensure_ascii=False), doc_id))
    conn.commit()

    defaut = OPTIONS_PAR_DEFAUT.get(type_doc, {})
    return {
        'id':            row['id'],
        'type_document': type_doc,
        'options':       {**defaut, **fusionne},
        'ordre':         row['ordre'],
    }


# ── Validation ──────────────────────────────────────────────────────────────

def _valider_options(type_document: str, options: dict) -> dict:
    """Valide un dict d'options *partiel* pour un type donné.

    - Clés autorisées : celles présentes dans `OPTIONS_PAR_DEFAUT[type]`.
    - Types : conserve le type du défaut (bool → bool, str → str).
    - Pour les clés énumérées (`ENUMS`), valeur dans la liste autorisée.
    """
    if type_document not in OPTIONS_PAR_DEFAUT:
        raise DocumentErreur(
            f"Type de document inconnu : {type_document!r}",
            code='type_inconnu',
        )
    autorisees = OPTIONS_PAR_DEFAUT[type_document]
    if not isinstance(options, dict):
        raise DocumentErreur("Options doit être un objet/dict",
                             code='options_non_dict')

    erreurs = []
    sortie = {}
    for cle, val in options.items():
        if cle not in autorisees:
            erreurs.append(f"clé inconnue pour {type_document!r} : {cle!r}")
            continue
        attendu = type(autorisees[cle])
        if attendu is bool:
            if not isinstance(val, bool):
                erreurs.append(f"{cle!r} attend bool, reçu {type(val).__name__}")
                continue
        elif attendu is str:
            if not isinstance(val, str):
                erreurs.append(f"{cle!r} attend str, reçu {type(val).__name__}")
                continue
            if cle in ENUMS and val not in ENUMS[cle]:
                erreurs.append(
                    f"{cle!r} : valeur {val!r} non autorisée "
                    f"(attendu : {', '.join(ENUMS[cle])})"
                )
                continue
        else:
            erreurs.append(f"{cle!r} : type interne inattendu")
            continue
        sortie[cle] = val

    if erreurs:
        raise DocumentErreur(
            "Options invalides",
            code='options_invalides',
            details={'erreurs': erreurs},
        )
    return sortie
