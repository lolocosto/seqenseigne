"""tests/test_R4c_renommage_rang_partie.py — Tests du renommage rang_* → partie_*.

Vérifie :
  1. Sur une base fraîche, les colonnes sont bien partie_debut/partie_fin
  2. Sur une base ancienne (avec rang_debut/rang_fin), la migration
     idempotente renomme bien les colonnes en partie_debut/partie_fin
  3. Les données existantes sont préservées lors du renommage
  4. La rétrocompat lors de l'écriture (accepter rang_* en entrée) fonctionne
"""

import sqlite3
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from persistence.sqlite_store import SqliteStore


@pytest.fixture
def base_fraiche(tmp_path):
    """Base SQLite vierge (schéma natif, déjà avec partie_debut/partie_fin)."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return SqliteStore(data_dir)


@pytest.fixture
def base_ancienne_rang(tmp_path):
    """Base créée à la main avec les anciennes colonnes rang_debut/rang_fin."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "seqenseigne.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    # Créer une table creneaux avec l'ancien schéma
    conn.execute("""
        CREATE TABLE progressions (
            id TEXT PRIMARY KEY,
            niveau TEXT,
            annee TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE creneaux (
            id TEXT PRIMARY KEY,
            progression_id TEXT NOT NULL REFERENCES progressions(id),
            seq_code TEXT NOT NULL,
            rang_debut INTEGER NOT NULL DEFAULT 1,
            rang_fin INTEGER NOT NULL DEFAULT 1,
            partie TEXT,
            periode TEXT,
            date_debut TEXT,
            date_fin TEXT,
            revisions TEXT,
            ordre INTEGER NOT NULL DEFAULT 0
        )
    """)
    # Insérer quelques données
    conn.execute(
        "INSERT INTO progressions (id, niveau, annee) "
        "VALUES ('pg_1', 'N11', '2025-2026')"
    )
    conn.execute(
        "INSERT INTO creneaux "
        "(id, progression_id, seq_code, rang_debut, rang_fin, partie, ordre) "
        "VALUES ('cr_1', 'pg_1', 'S01', 1, 2, '1re partie', 1)"
    )
    conn.execute(
        "INSERT INTO creneaux "
        "(id, progression_id, seq_code, rang_debut, rang_fin, ordre) "
        "VALUES ('cr_2', 'pg_1', 'S03', 3, 3, 2)"
    )
    conn.commit()
    conn.close()
    return db_path


class TestSchemaNatif:
    def test_nouvelles_colonnes_presentes(self, base_fraiche):
        conn = sqlite3.connect(str(base_fraiche.db_path))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(creneaux)")}
        conn.close()
        assert "partie_debut" in cols
        assert "partie_fin" in cols

    def test_anciennes_colonnes_absentes(self, base_fraiche):
        conn = sqlite3.connect(str(base_fraiche.db_path))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(creneaux)")}
        conn.close()
        assert "rang_debut" not in cols
        assert "rang_fin" not in cols

    def test_index_sur_partie_debut(self, base_fraiche):
        """L'index idx_creneaux_seq doit porter sur partie_debut, pas rang_debut."""
        conn = sqlite3.connect(str(base_fraiche.db_path))
        # Regarder les colonnes indexées par idx_creneaux_seq
        info = conn.execute(
            "PRAGMA index_info('idx_creneaux_seq')"
        ).fetchall()
        col_names = []
        for r in info:
            col_info = conn.execute(
                "PRAGMA table_info(creneaux)"
            ).fetchall()
            col_names.append(col_info[r[1]][1])
        conn.close()
        assert "partie_debut" in col_names


class TestMigrationDepuisBaseAncienne:
    def test_migration_renomme_colonnes(self, base_ancienne_rang):
        """Après passage du SqliteStore, les colonnes sont renommées."""
        data_dir = base_ancienne_rang.parent
        # SqliteStore applique la migration au démarrage
        store = SqliteStore(data_dir)
        conn = sqlite3.connect(str(store.db_path))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(creneaux)")}
        conn.close()
        assert "partie_debut" in cols
        assert "partie_fin" in cols
        assert "rang_debut" not in cols
        assert "rang_fin" not in cols

    def test_donnees_preservees(self, base_ancienne_rang):
        """Les valeurs numériques sont conservées lors du rename."""
        data_dir = base_ancienne_rang.parent
        store = SqliteStore(data_dir)
        conn = sqlite3.connect(str(store.db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, partie_debut, partie_fin FROM creneaux ORDER BY id"
        ).fetchall()
        conn.close()
        assert len(rows) == 2
        assert rows[0]["id"] == "cr_1"
        assert rows[0]["partie_debut"] == 1
        assert rows[0]["partie_fin"] == 2
        assert rows[1]["id"] == "cr_2"
        assert rows[1]["partie_debut"] == 3
        assert rows[1]["partie_fin"] == 3

    def test_migration_idempotente(self, base_ancienne_rang):
        """Relancer SqliteStore sur une base déjà migrée ne casse rien."""
        data_dir = base_ancienne_rang.parent
        SqliteStore(data_dir)  # première migration
        SqliteStore(data_dir)  # deuxième "migration" (no-op)
        SqliteStore(data_dir)  # troisième (no-op aussi)

        conn = sqlite3.connect(str(data_dir / "seqenseigne.db"))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(creneaux)")}
        n = conn.execute("SELECT COUNT(*) FROM creneaux").fetchone()[0]
        conn.close()
        assert "partie_debut" in cols
        assert "partie_fin" in cols
        assert n == 2


class TestRetrocompatEcriture:
    """
    Les anciennes clés rang_debut / rang_fin sont acceptées en entrée
    (pour ne pas casser un cache navigateur avec l'ancien JS).
    """
    def test_ecrire_progression_accepte_anciennes_cles(self, base_fraiche):
        progression = {
            "niveau": "N11",
            "annee":  "2025-2026",
            "creneaux": [
                {
                    "id": "cr_rc1",
                    "sequence": "S01",
                    "rang_debut": 1,      # ancienne clé
                    "rang_fin":   2,      # ancienne clé
                    "partie":     "Test",
                    "ordre":      1,
                }
            ]
        }
        base_fraiche.ecrire_progression(progression)

        conn = sqlite3.connect(str(base_fraiche.db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT partie_debut, partie_fin "
            "FROM creneaux WHERE id = 'cr_rc1'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["partie_debut"] == 1
        assert row["partie_fin"] == 2

    def test_ecrire_progression_nouvelles_cles(self, base_fraiche):
        progression = {
            "niveau": "N11",
            "annee":  "2025-2026",
            "creneaux": [
                {
                    "id": "cr_rc2",
                    "sequence": "S03",
                    "partie_debut": 1,    # nouvelle clé
                    "partie_fin":   3,
                    "ordre":        1,
                }
            ]
        }
        base_fraiche.ecrire_progression(progression)

        conn = sqlite3.connect(str(base_fraiche.db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT partie_debut, partie_fin "
            "FROM creneaux WHERE id = 'cr_rc2'"
        ).fetchone()
        conn.close()
        assert row["partie_debut"] == 1
        assert row["partie_fin"] == 3

    def test_lire_progression_retourne_nouvelles_cles(self, base_fraiche):
        """lire_progression doit retourner les clés partie_debut/partie_fin
        (pas rang_debut/rang_fin)."""
        progression = {
            "niveau": "N11",
            "annee":  "2025-2026",
            "creneaux": [{
                "id": "cr_rc3", "sequence": "S07",
                "partie_debut": 2, "partie_fin": 2, "ordre": 1,
            }]
        }
        base_fraiche.ecrire_progression(progression)
        prog = base_fraiche.lire_progression("N11", "2025-2026")
        assert len(prog["creneaux"]) == 1
        cr = prog["creneaux"][0]
        assert "partie_debut" in cr
        assert "partie_fin" in cr
        assert cr["partie_debut"] == 2
        assert cr["partie_fin"] == 2
        # Les anciennes clés ne doivent PAS être dans le retour
        assert "rang_debut" not in cr
        assert "rang_fin" not in cr
