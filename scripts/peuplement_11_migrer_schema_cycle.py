"""
scripts/peuplement_11_migrer_schema_cycle.py — R1.

Ajoute à une base existante :
  - table cycles
  - table themes (FK vers cycles)
  - table sequences_du_cycle (FK vers cycles et themes)

Idempotent : si les tables existent, ne fait rien.

Contrairement aux scripts C1, ce script ne touche PAS aux tables existantes
(referentiel_themes, referentiel_sequences continuent de vivre leur vie).
Le démantèlement de ces tables interviendra dans un chantier ultérieur (R4).

Usage :
    cd appli
    ..\\outils\\python\\python.exe scripts\\peuplement_11_migrer_schema_cycle.py
"""

from __future__ import annotations
import sys
import sqlite3
from pathlib import Path


# ── DDL idempotent pour R1 ───────────────────────────────────────────────────

DDL_R1 = """
CREATE TABLE IF NOT EXISTS cycles (
    code        TEXT PRIMARY KEY,
    nom         TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS themes (
    id           TEXT PRIMARY KEY,
    cycle_code   TEXT NOT NULL REFERENCES cycles(code) ON DELETE CASCADE,
    code         TEXT NOT NULL,
    nom          TEXT NOT NULL,
    code_couleur TEXT NOT NULL DEFAULT '',
    description  TEXT NOT NULL DEFAULT '',
    ordre        INTEGER NOT NULL DEFAULT 0,
    UNIQUE (cycle_code, nom),
    UNIQUE (cycle_code, code)
);
CREATE INDEX IF NOT EXISTS idx_themes_cycle ON themes (cycle_code, ordre);

CREATE TABLE IF NOT EXISTS sequences_du_cycle (
    id          TEXT PRIMARY KEY,
    cycle_code  TEXT NOT NULL REFERENCES cycles(code) ON DELETE CASCADE,
    code        TEXT NOT NULL,
    numero      INTEGER NOT NULL,
    nom         TEXT NOT NULL,
    theme_id    TEXT REFERENCES themes(id) ON DELETE SET NULL,
    UNIQUE (cycle_code, code),
    UNIQUE (cycle_code, numero)
);
CREATE INDEX IF NOT EXISTS idx_sequences_cycle ON sequences_du_cycle (cycle_code, numero);
CREATE INDEX IF NOT EXISTS idx_sequences_theme ON sequences_du_cycle (theme_id);
"""


def _tables_existantes(conn: sqlite3.Connection) -> set[str]:
    return {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


def migrer(db_path: Path) -> dict:
    """
    Applique la migration R1. Retourne un rapport.
    Idempotent.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Base introuvable : {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        avant = _tables_existantes(conn)
        cibles = {"cycles", "themes", "sequences_du_cycle"}
        a_creer = cibles - avant

        conn.executescript(DDL_R1)
        conn.commit()

        apres = _tables_existantes(conn)
        cibles_presentes = cibles & apres
    finally:
        conn.close()

    return {
        "tables_creees":   sorted(a_creer),
        "tables_presentes": sorted(cibles_presentes),
        "ok":              cibles.issubset(apres),
    }


def main() -> int:
    racine = Path(__file__).parent.parent
    db_path = racine / "data" / "seqenseigne.db"

    if not db_path.exists():
        print(f"ERREUR : base introuvable à {db_path}")
        return 1

    print(f"Migration de schéma R1 sur : {db_path}")
    try:
        rapport = migrer(db_path)
    except Exception as e:
        print(f"ERREUR : {e}")
        import traceback; traceback.print_exc()
        return 2

    print("=" * 60)
    print("Migration R1 — terminée")
    print("=" * 60)
    if rapport["tables_creees"]:
        print("Tables créées : " + ", ".join(rapport["tables_creees"]))
    else:
        print("Aucune nouvelle table à créer (schéma déjà à jour).")
    print("Tables cible présentes : " + ", ".join(rapport["tables_presentes"]))
    return 0 if rapport["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
