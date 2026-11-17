"""services/fiches_cycle4.py — v0.59.0

Référentiel de 4e au modèle « Fiches de résumé par objectif », cartes
d'automatisme dans la progression principale (`doc/redemarrage_v0_59_0.md`,
décisions D1 à D6 ; besoins `col4/besoins_appli_fiches_4e.md`, version 1).

Ce module porte les quatre ajouts de schéma (migration idempotente, appelée
au démarrage par `persistence/sqlite_store.py` et par les outils) et leurs
lectures :

  - `referentiel_niveaux.cartes_automatisme` (0/1, défaut 0) — option
    « cartes d'automatisme » du modèle Fiches (D4), choisie à la création,
    figée au verrouillage comme le modèle. Avec l'option, la validation du
    référentiel compte les cartes **rattachées aux objectifs** du périmètre
    (lien `objectif_cartes`), et elles seules ;
  - `cartes_automatisme.niveau_creation` ('' par défaut) — niveau où la
    notion de la carte est un objectif (N11 : carte de 4e ; N10 : automatisme
    de 5e écrit en 4e avant le référentiel de 5e). Gardé pour le document de
    rituels de la v0.60 (D3) avec l'objectif (et donc la partie) ;
  - `sequences_par_niveau.titre_court` ('' par défaut) — titre de la
    séquence propre au niveau dans les documents (D5), repli sur le nom du
    cycle ;
  - table `archivages_structure` — marque d'archivage de la structure de
    2025 d'un niveau du cycle 4 (D1, `outils/archiver_structure_niveau.py`) :
    l'import des lots d'un niveau autre que la 6e la réclame.

Aucune ligne existante ne change : colonnes à valeur par défaut neutre, table
vide. Les tables d'instantané `referentiel_*` ne sont jamais touchées.
"""
from __future__ import annotations

import sqlite3

DDL_ARCHIVAGES = """
CREATE TABLE IF NOT EXISTS archivages_structure (
    niveau     TEXT PRIMARY KEY,
    fait_le    TEXT NOT NULL,
    journal    TEXT NOT NULL DEFAULT '',
    resume     TEXT NOT NULL DEFAULT ''
)"""


def _cols(conn, table: str) -> set:
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def migrer(conn) -> list[str]:
    """Ajouts idempotents ; retourne la liste de ce qui vient d'être ajouté."""
    faits = []
    for table, col, ddl in (
            ("referentiel_niveaux", "cartes_automatisme", "INTEGER NOT NULL DEFAULT 0"),
            ("cartes_automatisme", "niveau_creation", "TEXT NOT NULL DEFAULT ''"),
            ("sequences_par_niveau", "titre_court", "TEXT NOT NULL DEFAULT ''")):
        cols = _cols(conn, table)
        if cols and col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            faits.append(f"{table}.{col}")
    existe = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                          "name='archivages_structure'").fetchone()
    if existe is None:
        conn.execute(DDL_ARCHIVAGES)
        faits.append("archivages_structure")
    return faits


# ── D4 — Option « cartes d'automatisme » du modèle Fiches ───────────────────

def option_cartes(conn, ref_id: str) -> bool:
    """L'option est-elle posée sur ce référentiel ? (False si colonne absente)."""
    if not ref_id or "cartes_automatisme" not in _cols(conn, "referentiel_niveaux"):
        return False
    r = conn.execute("SELECT cartes_automatisme FROM referentiel_niveaux WHERE id = ?",
                     (ref_id,)).fetchone()
    return bool(r and r[0])


def poser_option_cartes(conn, ref_id: str, valeur: bool) -> bool:
    """À la création seulement (l'appelant le garantit). Retourne la valeur posée."""
    migrer(conn)
    conn.execute("UPDATE referentiel_niveaux SET cartes_automatisme = ? WHERE id = ?",
                 (1 if valeur else 0, ref_id))
    return bool(valeur)


def _filtre_principal(alias: str) -> str:
    return (f" AND COALESCE({alias}.sequence_code, '') NOT LIKE 'X%'"
            f" AND COALESCE({alias}.sequence_code, '') NOT GLOB 'M[0-9][0-9]'")


def cartes_rattachees(conn, niveau: str) -> list[dict]:
    """Cartes rattachées (objectif_cartes) à un objectif du périmètre du
    principal du niveau (séquences-niveaux hors archives Xnn et mises en
    route Mnn), une fois chacune : {id, sequence, num, titre, etat_code,
    niveau_creation, objectifs: ['A1-02', …]}."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                        "name='objectif_cartes'").fetchone():
        return []
    nc = "c.niveau_creation" if "niveau_creation" in _cols(conn, "cartes_automatisme") \
        else "''"
    out: dict = {}
    for r in conn.execute(
            f"SELECT c.id, c.sequence, c.num, c.titre, c.etat_code, {nc} AS nc, "
            "sn.sequence_code AS seq_obj, o.code AS code_obj "
            "FROM objectif_cartes oc JOIN cartes_automatisme c ON c.id = oc.carte_id "
            "JOIN objectifs o ON o.id = oc.objectif_id "
            "JOIN sequence_parties p ON p.id = o.partie_id "
            "JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id "
            "WHERE sn.niveau = ?" + _filtre_principal("sn")
            + " ORDER BY sn.sequence_code, o.code, oc.ordre, c.num", (niveau,)):
        d = out.setdefault(r[0], {"id": r[0], "sequence": r[1], "num": r[2], "titre": r[3],
                                  "etat_code": r[4], "niveau_creation": r[5] or "",
                                  "objectifs": []})
        d["objectifs"].append(f"{r[6]}-{r[7]}")
    return list(out.values())


def compter_cartes_rattachees(conn, niveau: str) -> dict:
    """{"total": n, "non_valides": n} des cartes rattachées du périmètre."""
    cs = cartes_rattachees(conn, niveau)
    return {"total": len(cs), "non_valides": sum(1 for c in cs if c["etat_code"] != "valide")}


# ── D5 — Titre court de la séquence-niveau ──────────────────────────────────

def titre_court(conn, niveau: str, sequence_code: str) -> str:
    if "titre_court" not in _cols(conn, "sequences_par_niveau"):
        return ""
    r = conn.execute("SELECT titre_court FROM sequences_par_niveau WHERE niveau = ? AND "
                     "sequence_code = ?", (niveau, sequence_code)).fetchone()
    return ((r[0] if r else "") or "").strip()


# ── D1 — Marque d'archivage de la structure de 2025 ─────────────────────────

def archivage(conn, niveau: str) -> dict | None:
    """{niveau, fait_le, journal, resume} si la structure de 2025 du niveau a
    été archivée (outils/archiver_structure_niveau.py), sinon None."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                        "name='archivages_structure'").fetchone():
        return None
    r = conn.execute("SELECT niveau, fait_le, journal, resume FROM archivages_structure "
                     "WHERE niveau = ?", (niveau,)).fetchone()
    return dict(zip(("niveau", "fait_le", "journal", "resume"), r)) if r else None
