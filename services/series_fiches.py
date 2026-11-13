r"""services/series_fiches.py — v0.56.0

Séries d'exercices du modèle « Fiches de résumé par objectif » (6e), décisions de
Laurent du 13 novembre 2026 (doc/redemarrage_v0_56_0.md) :

1. SERIES — les séries F, A, E s'appellent « Entraînement », « Approfondissement »,
   « Expertise » et leurs codes **affichés** sont EN06, AP05, EX02 (documents et
   interface). Les **codes internes restent F, A, E** (base, lots, référentiels, format
   d'échange, empreintes) : seul l'affichage change. AE, EV, TP, AC, AT, MR et le cycle 4
   (modèle Notions et méthodes) ne changent pas.
2. MENTION — chaque exercice d'une série F, A ou E porte une mention : O (obligatoire, par
   défaut) ou F (facultatif : il fait travailler la même procédure qu'une remédiation R
   placée juste avant). La remédiation garde son statut R. Colonne `exercices.mention`
   (migration idempotente `migrer`, défaut 'O').
"""

from __future__ import annotations

import re
import sqlite3

# ── 1. Codes et titres affichés ──────────────────────────────────────────────

CODES_AFFICHES = {"F": "EN", "A": "AP", "E": "EX"}
TITRES = {"F": "Entraînement", "A": "Approfondissement", "E": "Expertise"}
_CODE = re.compile(r"^(F|A|E)(\d+)$")


def prefixe_affiche(serie_code: str) -> str:
    """'F' → 'EN', 'A' → 'AP', 'E' → 'EX' ; toute autre série inchangée."""
    return CODES_AFFICHES.get(serie_code or "", serie_code or "")


def code_affiche(serie_code: str, num) -> str:
    """Code d'un exercice dans les documents du modèle Fiches (« EN06 »)."""
    p = prefixe_affiche(serie_code)
    try:
        return f"{p}{int(num):02d}"
    except (TypeError, ValueError):
        return f"{p}{num if num is not None else ''}"


def code_interne_vers_affiche(code: str) -> str:
    """« F06 » → « EN06 » ; « AE01 », « EV03 »… inchangés."""
    m = _CODE.match(code or "")
    return f"{CODES_AFFICHES[m.group(1)]}{m.group(2)}" if m else (code or "")


# ── 2. Mention O / F ─────────────────────────────────────────────────────────

MENTIONS = ("O", "F")
MENTION_DEFAUT = "O"
SERIES_AVEC_MENTION = ("F", "A", "E")
LIBELLES_MENTIONS = {"O": "obligatoire", "F": "facultatif"}
LEGENDE = "O~: obligatoire --- R~: remédiation --- F~: facultatif"


class MentionInvalide(ValueError):
    pass


def migrer(conn: sqlite3.Connection) -> bool:
    """Ajoute `exercices.mention` (TEXT NOT NULL DEFAULT 'O') si elle manque.
    Idempotent ; retourne True si la colonne vient d'être ajoutée."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(exercices)")}
    if not cols or "mention" in cols:
        return False
    conn.execute("ALTER TABLE exercices ADD COLUMN mention TEXT NOT NULL DEFAULT 'O'")
    return True


def colonne_presente(conn: sqlite3.Connection) -> bool:
    return "mention" in {r[1] for r in conn.execute("PRAGMA table_info(exercices)")}


def sql_colonne(conn: sqlite3.Connection, alias: str = "") -> str:
    """Fragment SELECT `, mention` ; 'O' sur une base sans la colonne."""
    p = f"{alias}." if alias else ""
    return f", {p}mention" if colonne_presente(conn) else ", 'O' AS mention"


def valider(valeur) -> str:
    """'O' pour None / '' ; MentionInvalide hors de O, F."""
    v = (valeur or "").strip().upper() if isinstance(valeur, str) or valeur is None else valeur
    v = v or MENTION_DEFAUT
    if v not in MENTIONS:
        raise MentionInvalide(f"mention doit être O (obligatoire) ou F (facultatif) "
                              f"(reçu {valeur!r})")
    return v


def lire(ex) -> str:
    """Mention d'un dict / Row ('O' si absente ou vide)."""
    if isinstance(ex, sqlite3.Row):
        v = ex["mention"] if "mention" in ex.keys() else ""
    elif isinstance(ex, dict):
        v = ex.get("mention")
    else:
        v = getattr(ex, "mention", "")
    return v if v in MENTIONS else MENTION_DEFAUT
