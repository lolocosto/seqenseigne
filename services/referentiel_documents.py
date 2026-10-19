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
# v0.52.1 — C'est le gabarit « cycle4 » de services/gabarits_documents.py
# (mêmes clés, mêmes options) ; ne renommer aucune clé : les chaînes
# « type|cible » sont enregistrées côté classe.

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

    v0.52.1 — Seuls les types du **gabarit** du référentiel sont listés
    (services/gabarits_documents.py : `cycle4` = les 9 types historiques,
    `sixieme` = les documents de 6e). Les lignes d'un autre gabarit restent en
    base (options conservées si l'on revient en arrière) mais ne sont ni
    listées, ni compilées, ni proposées côté classe.

    Idempotence : si le référentiel n'a aucun document de son gabarit, on
    initialise ceux de ce gabarit (cas premier accès à l'onglet, ou gabarit
    qui vient de changer).

    Retourne une liste de dicts : `{id, type_document, options (dict
    Python), ordre, mtime, referentiel_id, compile_ok, compile_date,
    compile_log, compile_en_cours, etat_effectif}`. Triée par `ordre`
    croissant. Les types hors cycle 4 portent aussi `libelle`,
    `description` et `champs` (interface générique de l'onglet).

    v0.13.6.5.1 : ajout des colonnes compile_* et du champ calculé
    `etat_effectif` (cf. services.referentiel_documents_compilation).
    """
    from services import gabarits_documents as gd
    gabarit = gd.gabarit_du_referentiel(conn, referentiel_id)
    types_gabarit = gd.types(gabarit)

    def _lire():
        return [r for r in conn.execute("""
            SELECT id, referentiel_id, type_document, options, ordre, mtime,
                   compile_ok, compile_date, compile_log, compile_en_cours
              FROM referentiel_documents
             WHERE referentiel_id = ?
             ORDER BY ordre, type_document
        """, (referentiel_id,)).fetchall() if r['type_document'] in types_gabarit]

    rows = _lire()
    if not rows:
        # Initialisation auto et relecture.
        initialiser_documents_defaut(conn, referentiel_id)
        rows = _lire()

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
        t = gd.type_document(r['type_document'])
        defaut = t.options if t is not None else {}
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
        if r['type_document'] not in TYPES_DOCUMENT:
            doc.update(gd.description_interface(r['type_document']))
        doc['etat_effectif'] = etat_effectif_document(conn, doc, data_dir)
        out.append(doc)
    return out


def initialiser_documents_defaut(conn: sqlite3.Connection,
                                 referentiel_id: str) -> None:
    """Insère les entrées par défaut du gabarit de ce référentiel (les 9
    types historiques pour le gabarit `cycle4`).

    Idempotent : INSERT OR IGNORE sur (referentiel_id, type_document).
    Appelable en toute sécurité à plusieurs reprises.
    """
    from services import gabarits_documents as gd
    gabarit = gd.gabarit_du_referentiel(conn, referentiel_id)
    for i, t in enumerate(gd.catalogue(gabarit), start=1):
        conn.execute("""
            INSERT OR IGNORE INTO referentiel_documents
                (id, referentiel_id, type_document, options, ordre)
            VALUES (?, ?, ?, ?, ?)
        """, (
            f"rd_{uuid.uuid4().hex[:12]}",
            referentiel_id,
            t.cle,
            json.dumps(t.options_par_defaut(), ensure_ascii=False),
            i,
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

    from services import gabarits_documents as gd
    t = gd.type_document(type_doc)
    defaut = t.options if t is not None else {}
    doc = {
        'id':            row['id'],
        'type_document': type_doc,
        'options':       {**defaut, **fusionne},
        'ordre':         row['ordre'],
    }
    if type_doc not in TYPES_DOCUMENT:
        doc.update(gd.description_interface(type_doc))
    return doc


# ── Validation ──────────────────────────────────────────────────────────────

def _valider_options(type_document: str, options: dict) -> dict:
    """Valide un dict d'options *partiel* pour un type donné.

    - Clés autorisées : celles présentes dans les options par défaut du type.
    - Types : conserve le type du défaut (bool → bool, str → str).
    - Pour les clés énumérées, valeur dans la liste autorisée.

    v0.52.1 — Délègue au catalogue des gabarits
    (services/gabarits_documents.valider_options) : les 9 types du cycle 4
    y ont exactement les options et valeurs ci-dessus (OPTIONS_PAR_DEFAUT,
    ENUMS) ; les types de 6e y ont les leurs.
    """
    from services import gabarits_documents as gd
    return gd.valider_options(type_document, options)
