#!/usr/bin/env python3
"""scripts/migrer_v0_13_5_2.py — v0.13.5.2.1

Migration ponctuelle (idempotente) : ajoute le support des évaluations.

Périmètre
---------
1. Ajoute la colonne `mtime DATETIME` aux tables d'atomes existantes :
   notions, methodes, exercices, fiches_resume.
   Pour les enregistrements existants, mtime est initialisé à
   CURRENT_TIMESTAMP au moment de la migration.

2. Ajoute la colonne `type_format TEXT NOT NULL DEFAULT 'standard'` à
   la table exercices. Valeurs prévues : 'standard' (défaut), 'qcm'.

3. Crée les tables `evaluations` et `evaluation_exercices` si absentes.

Note importante
---------------
Ces migrations sont aussi appliquées **automatiquement** au démarrage
de l'application (cf. SqliteStore._migrer_schema_post_ddl). Ce script
sert :
  - à diagnostiquer (mode dry-run sans modifier la BDD)
  - à appliquer la migration sur une BDD hors de l'appli

Sécurités
---------
- **Dry-run par défaut** : affiche ce qui serait modifié.
- Avec `--apply`, demande confirmation interactive (OUI) sauf si
  `--yes` est passé.
- **Idempotence** : si la migration a déjà été appliquée, no-op.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


# ── Détection des modifications nécessaires ─────────────────────────────────


def _colonnes(conn: sqlite3.Connection, table: str) -> set[str]:
    """Retourne le set des noms de colonnes d'une table.
    Set vide si la table n'existe pas."""
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {r["name"] for r in rows}
    except sqlite3.OperationalError:
        return set()


def _table_existe(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def calculer_modifications(conn: sqlite3.Connection) -> dict:
    """Détermine la liste des modifications à appliquer.

    Retourne un dict structuré :
      {
        "mtime_a_ajouter":     ["notions", ...],
        "type_format_a_ajouter": True | False,
        "evaluations_a_creer":   True | False,
        "evaluation_exercices_a_creer": True | False,
      }
    """
    res = {
        "mtime_a_ajouter":              [],
        "type_format_a_ajouter":        False,
        "evaluations_a_creer":          False,
        "evaluation_exercices_a_creer": False,
    }
    for table in ("notions", "methodes", "exercices", "fiches_resume"):
        cols = _colonnes(conn, table)
        if cols and "mtime" not in cols:
            res["mtime_a_ajouter"].append(table)
    cols_e = _colonnes(conn, "exercices")
    if cols_e and "type_format" not in cols_e:
        res["type_format_a_ajouter"] = True
    if not _table_existe(conn, "evaluations"):
        res["evaluations_a_creer"] = True
    if not _table_existe(conn, "evaluation_exercices"):
        res["evaluation_exercices_a_creer"] = True
    return res


def afficher_plan(modifications: dict) -> None:
    """Affiche le plan en ligne."""
    rien_a_faire = (
        not modifications["mtime_a_ajouter"]
        and not modifications["type_format_a_ajouter"]
        and not modifications["evaluations_a_creer"]
        and not modifications["evaluation_exercices_a_creer"]
    )
    if rien_a_faire:
        print("Aucune modification à appliquer (BDD déjà à jour v0.13.5.2).")
        return

    print("Plan de migration v0.13.5.2 :")
    print()

    if modifications["mtime_a_ajouter"]:
        print("  Ajout colonne mtime :")
        for t in modifications["mtime_a_ajouter"]:
            print(f"    - {t}")
        print("    (les enregistrements existants reçoivent CURRENT_TIMESTAMP)")
        print()

    if modifications["type_format_a_ajouter"]:
        print("  Ajout colonne type_format sur exercices :")
        print("    - default 'standard' pour les exercices existants")
        print()

    if modifications["evaluations_a_creer"]:
        print("  Création table evaluations")

    if modifications["evaluation_exercices_a_creer"]:
        print("  Création table evaluation_exercices")
    print()


# ── Application ──────────────────────────────────────────────────────────────


def appliquer(conn: sqlite3.Connection, modifications: dict) -> int:
    """Applique les modifications. Retourne le nombre d'opérations effectuées."""
    n = 0
    # 1) Ajout mtime aux tables d'atomes
    for table in modifications["mtime_a_ajouter"]:
        # SQLite n'autorise pas DEFAULT CURRENT_TIMESTAMP sur ADD COLUMN.
        # On ajoute en deux temps : nullable, puis UPDATE.
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN mtime DATETIME"
        )
        conn.execute(
            f"UPDATE {table} SET mtime = CURRENT_TIMESTAMP "
            f"WHERE mtime IS NULL"
        )
        n += 1

    # 2) Ajout type_format sur exercices
    if modifications["type_format_a_ajouter"]:
        conn.execute(
            "ALTER TABLE exercices ADD COLUMN type_format TEXT "
            "NOT NULL DEFAULT 'standard'"
        )
        n += 1

    # 3) Création des tables si absentes
    if modifications["evaluations_a_creer"]:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id                          TEXT PRIMARY KEY,
                niveau                      TEXT NOT NULL,
                numero                      INTEGER NOT NULL,
                ordre                       INTEGER NOT NULL,
                titre                       TEXT NOT NULL DEFAULT '',
                mode_notation               TEXT NOT NULL DEFAULT 'note',
                afficher_bareme_dans_exos   INTEGER NOT NULL DEFAULT 1,
                item_langue_francaise       TEXT NOT NULL DEFAULT '',
                etat_code                   TEXT NOT NULL DEFAULT 'en_cours',
                mtime                       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (niveau, numero),
                CHECK  (mode_notation IN ('note', 'criteres', 'note_criteres', 'aucun')),
                CHECK  (etat_code IN ('en_cours', 'valide')),
                CHECK  (afficher_bareme_dans_exos IN (0, 1))
            );
            CREATE INDEX IF NOT EXISTS idx_evaluations_niveau_ordre
                ON evaluations (niveau, ordre);
        """)
        n += 1

    if modifications["evaluation_exercices_a_creer"]:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS evaluation_exercices (
                evaluation_id      TEXT NOT NULL
                                   REFERENCES evaluations(id) ON DELETE CASCADE,
                exercice_id        TEXT NOT NULL
                                   REFERENCES exercices(id) ON DELETE RESTRICT,
                ordre              INTEGER NOT NULL,
                bareme_points      REAL,
                bareme_qcm_ok      REAL,
                bareme_qcm_partiel REAL,
                bareme_qcm_ko      REAL,
                PRIMARY KEY (evaluation_id, exercice_id),
                UNIQUE      (evaluation_id, ordre)
            );
            CREATE INDEX IF NOT EXISTS idx_evaluation_exercices_eval
                ON evaluation_exercices (evaluation_id, ordre);
        """)
        n += 1

    conn.commit()
    return n


def confirmer_interactif() -> bool:
    """Demande confirmation interactive. Accepte uniquement 'OUI'."""
    rep = input("Appliquer les modifications ? Tapez OUI pour confirmer : ")
    return rep.strip() == "OUI"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migration v0.13.5.2 : support des évaluations.",
    )
    parser.add_argument(
        "--db",
        default="data/seqenseigne.db",
        help="Chemin vers la base SQLite (défaut : data/seqenseigne.db)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Appliquer réellement les modifications (sinon : dry-run)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Sauter la confirmation interactive (pour batch / tests)",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERREUR : base introuvable : {db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        modifications = calculer_modifications(conn)
        afficher_plan(modifications)

        rien_a_faire = (
            not modifications["mtime_a_ajouter"]
            and not modifications["type_format_a_ajouter"]
            and not modifications["evaluations_a_creer"]
            and not modifications["evaluation_exercices_a_creer"]
        )
        if rien_a_faire:
            return 0

        if not args.apply:
            print("Mode dry-run (aucune modification appliquée).")
            print("Relancer avec --apply pour appliquer.")
            return 0

        if not args.yes and not confirmer_interactif():
            print("Abandon.")
            return 1

        n = appliquer(conn, modifications)
        print(f"\nOK : {n} opération(s) appliquée(s).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
