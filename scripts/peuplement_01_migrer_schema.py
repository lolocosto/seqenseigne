"""
scripts/peuplement_01_migrer_schema.py — Migration de schéma pour le patch C1.

Ajoute les colonnes manquantes aux tables d'atomes pédagogiques et crée
la nouvelle table `livret_revisions`. Idempotent : peut être relancé
sans effet si le schéma est déjà à jour.

Usage :
    cd appli
    ..\\outils\\python\\python.exe scripts\\peuplement_01_migrer_schema.py

Affiche un rapport détaillé des modifications effectuées.
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path


SCHEMA_VERSION_ATTENDUE = 3  # incrémenter à chaque évolution majeure du schéma


# Colonnes à ajouter par table, avec leur définition SQL.
# Format : {table: [(colonne, def_sql), ...]}
COLONNES_A_AJOUTER: dict[str, list[tuple[str, str]]] = {
    "exercices": [
        ("niveau",     "TEXT NOT NULL DEFAULT ''"),
        ("sequence",   "TEXT NOT NULL DEFAULT ''"),
        ("num",        "INTEGER"),
        ("serie_code", "TEXT NOT NULL DEFAULT ''"),
        ("fichier",    "TEXT NOT NULL DEFAULT ''"),
    ],
    "notions": [
        ("niveau",           "TEXT NOT NULL DEFAULT ''"),
        ("sequence",         "TEXT NOT NULL DEFAULT ''"),
        ("num_connaissance", "TEXT NOT NULL DEFAULT ''"),
        ("fichier",          "TEXT NOT NULL DEFAULT ''"),
    ],
    "methodes": [
        ("niveau",       "TEXT NOT NULL DEFAULT ''"),
        ("sequence",     "TEXT NOT NULL DEFAULT ''"),
        ("num_methode",  "INTEGER"),
        ("num_objectif", "TEXT NOT NULL DEFAULT ''"),
        ("fichier",      "TEXT NOT NULL DEFAULT ''"),
    ],
    # v0.14.6.b.2 — Entrée "objectifs" retirée : la table `objectifs` (v1)
    # a été supprimée définitivement. Sur les bases anciennes, le script
    # `scripts/supprimer_v1.py` se charge de faire les DROP TABLE.
}

# Nouvelles tables à créer (idempotent via IF NOT EXISTS)
TABLES_A_CREER: list[tuple[str, str]] = [
    ("livret_revisions", """
        CREATE TABLE IF NOT EXISTS livret_revisions (
            livret_id     TEXT NOT NULL REFERENCES livrets_de_sequence(id) ON DELETE CASCADE,
            niveau_source TEXT NOT NULL,
            seq_source    TEXT NOT NULL,
            serie         TEXT NOT NULL,
            num           INTEGER NOT NULL,
            ordre         INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (livret_id, niveau_source, seq_source, serie, num)
        )
    """),
]

# Index à créer (idempotent via IF NOT EXISTS)
INDEX_A_CREER: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_exercices_niv_seq ON exercices(niveau, sequence, num)",
    "CREATE INDEX IF NOT EXISTS idx_exercices_fichier ON exercices(fichier)",
    "CREATE INDEX IF NOT EXISTS idx_methodes_niv_seq  ON methodes(niveau, sequence)",
    "CREATE INDEX IF NOT EXISTS idx_methodes_fichier  ON methodes(fichier)",
    "CREATE INDEX IF NOT EXISTS idx_notions_niv_seq   ON notions(niveau, sequence)",
    "CREATE INDEX IF NOT EXISTS idx_notions_fichier   ON notions(fichier)",
    # v0.14.6.b.2 — Index `idx_objectifs_niv_seq` retiré (table supprimée).
]


def _colonnes_existantes(conn: sqlite3.Connection, table: str) -> set[str]:
    """Retourne l'ensemble des noms de colonnes d'une table."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def _tables_existantes(conn: sqlite3.Connection) -> set[str]:
    """Retourne l'ensemble des noms de tables de la base."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def migrer(db_path: Path) -> dict:
    """
    Applique la migration de schéma sur la base `db_path`.
    Retourne un rapport dict des modifications effectuées.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Base introuvable : {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rapport: dict = {
        "colonnes_ajoutees": {},
        "tables_creees":     [],
        "index_crees":       0,
        "version_avant":     None,
        "version_apres":     None,
    }

    try:
        # Version actuelle du schéma (user_version est une valeur entière libre
        # que l'on utilise ici comme compteur de migrations appliquées)
        rapport["version_avant"] = conn.execute("PRAGMA user_version").fetchone()[0]

        tables_existantes = _tables_existantes(conn)

        # 1. Ajouter les colonnes manquantes
        for table, colonnes in COLONNES_A_AJOUTER.items():
            if table not in tables_existantes:
                print(f"  ⚠ Table {table} absente, colonnes non ajoutées")
                continue
            existantes = _colonnes_existantes(conn, table)
            ajoutees_cette_table = []
            for col, definition in colonnes:
                if col in existantes:
                    continue
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
                ajoutees_cette_table.append(col)
            if ajoutees_cette_table:
                rapport["colonnes_ajoutees"][table] = ajoutees_cette_table

        # 2. Créer les nouvelles tables
        for nom_table, ddl in TABLES_A_CREER:
            if nom_table not in tables_existantes:
                conn.execute(ddl)
                rapport["tables_creees"].append(nom_table)

        # 3. Créer les index
        for ddl_index in INDEX_A_CREER:
            conn.execute(ddl_index)
            rapport["index_crees"] += 1

        # 4. Marquer la version
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION_ATTENDUE}")
        rapport["version_apres"] = SCHEMA_VERSION_ATTENDUE

        conn.commit()

    finally:
        conn.close()

    return rapport


def _imprimer_rapport(rapport: dict) -> None:
    print()
    print("=" * 60)
    print("Migration de schéma v0.6.3e — terminée")
    print("=" * 60)
    print(f"Version du schéma : {rapport['version_avant']} → {rapport['version_apres']}")
    print()
    if rapport["colonnes_ajoutees"]:
        print("Colonnes ajoutées :")
        for table, cols in rapport["colonnes_ajoutees"].items():
            print(f"  {table:12s} : {', '.join(cols)}")
    else:
        print("Aucune colonne à ajouter (schéma déjà à jour).")
    print()
    if rapport["tables_creees"]:
        print(f"Nouvelles tables : {', '.join(rapport['tables_creees'])}")
    else:
        print("Aucune nouvelle table à créer.")
    print()
    print(f"Index vérifiés/créés : {rapport['index_crees']}")
    print()


def main() -> int:
    racine = Path(__file__).parent.parent  # scripts/.. = appli/
    db_path = racine / "data" / "seqenseigne.db"

    if not db_path.exists():
        print(f"ERREUR : base introuvable à {db_path}")
        print("Lancer l'application au moins une fois pour créer la base.")
        return 1

    print(f"Migration de schéma sur : {db_path}")
    try:
        rapport = migrer(db_path)
    except Exception as e:
        print(f"ERREUR : {e}")
        return 2

    _imprimer_rapport(rapport)
    return 0


if __name__ == "__main__":
    sys.exit(main())
