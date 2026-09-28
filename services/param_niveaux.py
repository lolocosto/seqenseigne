"""services/param_niveaux.py — v0.13.1.

Helpers de lecture du référentiel des niveaux scolaires depuis la BDD
(table `param_niveaux`, créée et amorcée en v0.13.0).

Centralise les fonctions de lecture pour éliminer la duplication
historique entre :
  - `_NOM_COURT_NIVEAU` (hardcoded dans services/livret_sequence.py)
  - `_CYCLE_PAR_NIVEAU` (dupliqué dans livret_sequence.py ET
    livret_plans_de_travail.py)

API publique :
  - `lire_attributs(conn, code) -> dict | None` : tous les attributs
    d'un niveau (cycle_code, annee_dans_cycle, nom_court, nom_long, ordre)
    ou None si le niveau n'existe pas.
  - `lire_cycle(conn, code) -> str` : code du cycle pour un niveau.
    Lève `NiveauInconnu` si le niveau n'existe pas.
  - `lire_nom_court(conn, code) -> str` : nom court (`'5ème'`, `'CM2'`…)
    avec fallback sur le code si le niveau n'existe pas.
  - `lire_nom_court_latex(conn, code) -> str` : nom court en forme
    LaTeX (`'5\\ieme'`, `'CM2'`…). Substitue la table en dur
    `_NOM_COURT_NIVEAU` historique de `livret_sequence.py`.
  - `lister_tous(conn) -> list[dict]` : tous les niveaux, triés par
    ordre. Utile pour les sélecteurs UI.

Toutes les fonctions acceptent une connexion SQLite déjà ouverte
(par l'appelant qui gère sa transaction). Pas de side-effects.

Convention : si `param_niveaux` est vide (cas exceptionnel — par exemple
BDD restaurée depuis un backup antérieur à v0.13.0 sans CSV présent),
les fonctions de lecture lèvent `NiveauInconnu` ou retournent un
fallback robuste, jamais ne plantent.
"""

from __future__ import annotations
import sqlite3


class NiveauInconnu(LookupError):
    """Levée par les helpers stricts (ex. `lire_cycle`) quand le niveau
    demandé n'existe pas dans `param_niveaux`."""

    def __init__(self, niveau: str):
        super().__init__(f"Niveau inconnu dans param_niveaux : {niveau!r}")
        self.niveau = niveau


def lire_attributs(conn: sqlite3.Connection, code: str) -> dict | None:
    """Retourne tous les attributs d'un niveau, ou None si absent.

    Format retourné :
        {
          'code':              'N10',
          'cycle_code':        'C04',
          'annee_dans_cycle':  'anneeun',
          'nom_court':         '5ème',
          'nom_long':          'cinquième',
          'ordre':             4,
        }
    """
    row = conn.execute(
        "SELECT code, cycle_code, annee_dans_cycle, nom_court, nom_long, ordre "
        "FROM param_niveaux WHERE code = ?",
        (code,),
    ).fetchone()
    if row is None:
        return None
    # Compatible avec sqlite3.Row (accès par clé) ET tuple (accès par index)
    if hasattr(row, 'keys'):
        return {k: row[k] for k in row.keys()}
    return {
        'code':             row[0],
        'cycle_code':       row[1],
        'annee_dans_cycle': row[2],
        'nom_court':        row[3],
        'nom_long':         row[4],
        'ordre':            row[5],
    }


def lire_cycle(conn: sqlite3.Connection, code: str) -> str:
    """Retourne le code de cycle ('C03', 'C04', …) d'un niveau.

    Lève `NiveauInconnu` si le niveau n'existe pas. C'est un échec dur
    voulu : un service qui demande le cycle d'un niveau ne doit pas
    continuer avec un cycle invalide ou absent.
    """
    row = conn.execute(
        "SELECT cycle_code FROM param_niveaux WHERE code = ?",
        (code,),
    ).fetchone()
    if row is None:
        raise NiveauInconnu(code)
    # row[0] fonctionne pour Row comme pour tuple
    return row[0]


def lire_nom_court(conn: sqlite3.Connection, code: str) -> str:
    """Retourne le nom court d'un niveau ('5ème', 'CM2', '6ème'…).

    Fallback : si le niveau n'existe pas dans `param_niveaux`,
    retourne le code lui-même (ex. retourne 'N10' au lieu de planter).
    Cohérent avec l'ancien comportement de `_NOM_COURT_NIVEAU.get(code, code)`.
    """
    row = conn.execute(
        "SELECT nom_court FROM param_niveaux WHERE code = ?",
        (code,),
    ).fetchone()
    if row is None:
        return code
    return row[0]


def lire_nom_court_latex(conn: sqlite3.Connection, code: str) -> str:
    """Retourne le nom court d'un niveau **dans sa forme LaTeX**.

    Convertit le nom_court brut de `param_niveaux` en sa forme adaptée à
    l'inclusion directe dans du source TeX généré :
      - 'CM1', 'CM2' → identique (pas de transformation)
      - 'Xème'        → 'X\\ieme'  (ex. '5ème' → '5\\ieme')

    Cette conversion remplace la table en dur `_NOM_COURT_NIVEAU` qui
    était dupliquée dans `services/livret_sequence.py` (v0.13.1).

    Note sur le format de sortie : on produit `'X\\ieme'` (sans `{}`)
    pour rester strictement compatible avec le rendu LaTeX historique
    de `livret_sequence.py`. Le module `livret_plans_de_travail.py`
    utilise quant à lui sa propre table `LIBELLES_NIVEAUX_LATEX` avec
    la forme `'X\\ieme{}'` (avec accolades), qui n'est PAS substituée
    par cette fonction (sujet de cohérence à traiter séparément si
    nécessaire).

    Fallback : si le niveau n'existe pas dans `param_niveaux`, retourne
    le code lui-même (cohérent avec le fallback de `lire_nom_court`).
    """
    import re
    nc = lire_nom_court(conn, code)
    # Pattern strict : la chaîne doit être uniquement "Xème" pour matcher.
    # Cela protège contre une éventuelle forme déjà LaTeX (idempotence).
    m = re.fullmatch(r'(\d+)ème', nc)
    if m:
        return f"{m.group(1)}\\ieme"
    return nc


def lister_tous(conn: sqlite3.Connection) -> list[dict]:
    """Retourne tous les niveaux de `param_niveaux`, triés par `ordre`.

    Utile pour les sélecteurs UI ou les itérations exhaustives.
    Liste vide si la table est vide.
    """
    rows = conn.execute(
        "SELECT code, cycle_code, annee_dans_cycle, nom_court, nom_long, ordre "
        "FROM param_niveaux ORDER BY ordre"
    ).fetchall()
    out: list[dict] = []
    for row in rows:
        if hasattr(row, 'keys'):
            out.append({k: row[k] for k in row.keys()})
        else:
            out.append({
                'code':             row[0],
                'cycle_code':       row[1],
                'annee_dans_cycle': row[2],
                'nom_court':        row[3],
                'nom_long':         row[4],
                'ordre':            row[5],
            })
    return out
