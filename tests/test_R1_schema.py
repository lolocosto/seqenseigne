"""tests/test_R1_schema.py — Tests du schéma R1.

Vérifie que les tables cycles, themes, sequences_du_cycle sont bien
créées, que leurs contraintes fonctionnent, et que le script de
migration est idempotent.
"""

import sqlite3
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.peuplement_11_migrer_schema_cycle import migrer
from persistence.sqlite_store import SqliteStore


@pytest.fixture
def base_fraiche(tmp_path):
    """Base SQLite vierge (schéma natif complet, dont les tables R1)."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return SqliteStore(data_dir)


@pytest.fixture
def base_ancienne(tmp_path):
    """
    Base SQLite dont on a volontairement supprimé les tables R1,
    pour tester le script de migration en situation réelle.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    store = SqliteStore(data_dir)
    conn = sqlite3.connect(str(store.db_path))
    # Nettoyer les tables R1 dans l'ordre FK-safe
    for t in ["sequences_du_cycle", "themes", "cycles"]:
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.commit()
    conn.close()
    return store


class TestSchemaNatif:
    """Tables R1 présentes dès la création de la base."""

    def test_table_cycles_existe(self, base_fraiche):
        conn = sqlite3.connect(str(base_fraiche.db_path))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        conn.close()
        assert "cycles" in tables

    def test_table_themes_existe(self, base_fraiche):
        conn = sqlite3.connect(str(base_fraiche.db_path))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        conn.close()
        assert "themes" in tables

    def test_table_sequences_du_cycle_existe(self, base_fraiche):
        conn = sqlite3.connect(str(base_fraiche.db_path))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        conn.close()
        assert "sequences_du_cycle" in tables

    def test_colonnes_themes(self, base_fraiche):
        conn = sqlite3.connect(str(base_fraiche.db_path))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(themes)")}
        conn.close()
        assert cols == {
            "id", "cycle_code", "code", "nom", "code_couleur",
            "description", "ordre",
        }

    def test_colonnes_sequences_du_cycle(self, base_fraiche):
        conn = sqlite3.connect(str(base_fraiche.db_path))
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(sequences_du_cycle)"
        )}
        conn.close()
        assert cols == {
            "id", "cycle_code", "code", "numero", "nom", "theme_id",
        }


class TestContraintes:
    """Unicité et FK des tables R1."""

    def _prepare(self, store):
        conn = sqlite3.connect(str(store.db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("INSERT INTO cycles (code, nom) VALUES ('C04', 'Cycle 4')")
        conn.commit()
        return conn

    def test_cycle_code_primary_key(self, base_fraiche):
        conn = self._prepare(base_fraiche)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO cycles (code, nom) VALUES ('C04', 'Duplicate')")
        conn.close()

    def test_theme_unique_code_par_cycle(self, base_fraiche):
        conn = self._prepare(base_fraiche)
        conn.execute(
            "INSERT INTO themes (id, cycle_code, code, nom) "
            "VALUES ('th_1', 'C04', 'A', 'Nombres')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO themes (id, cycle_code, code, nom) "
                "VALUES ('th_2', 'C04', 'A', 'Autre')"
            )
        conn.close()

    def test_theme_unique_nom_par_cycle(self, base_fraiche):
        conn = self._prepare(base_fraiche)
        conn.execute(
            "INSERT INTO themes (id, cycle_code, code, nom) "
            "VALUES ('th_1', 'C04', 'A', 'Nombres')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO themes (id, cycle_code, code, nom) "
                "VALUES ('th_2', 'C04', 'B', 'Nombres')"
            )
        conn.close()

    def test_theme_fk_cycle(self, base_fraiche):
        conn = sqlite3.connect(str(base_fraiche.db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO themes (id, cycle_code, code, nom) "
                "VALUES ('th_1', 'C99', 'A', 'Nombres')"
            )
        conn.close()

    def test_sequence_unique_code_par_cycle(self, base_fraiche):
        conn = self._prepare(base_fraiche)
        conn.execute(
            "INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom) "
            "VALUES ('sc_1', 'C04', 'S01', 1, 'Repr.')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom) "
                "VALUES ('sc_2', 'C04', 'S01', 2, 'Duplicate')"
            )
        conn.close()

    def test_sequence_unique_numero_par_cycle(self, base_fraiche):
        conn = self._prepare(base_fraiche)
        conn.execute(
            "INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom) "
            "VALUES ('sc_1', 'C04', 'S01', 1, 'Repr.')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom) "
                "VALUES ('sc_2', 'C04', 'S02', 1, 'Duplicate numero')"
            )
        conn.close()

    def test_sequence_theme_set_null_on_delete(self, base_fraiche):
        conn = self._prepare(base_fraiche)
        conn.execute(
            "INSERT INTO themes (id, cycle_code, code, nom) "
            "VALUES ('th_1', 'C04', 'A', 'Nombres')"
        )
        conn.execute(
            "INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id) "
            "VALUES ('sc_1', 'C04', 'S01', 1, 'Repr.', 'th_1')"
        )
        conn.execute("DELETE FROM themes WHERE id = 'th_1'")
        theme_id = conn.execute(
            "SELECT theme_id FROM sequences_du_cycle WHERE id = 'sc_1'"
        ).fetchone()[0]
        conn.close()
        assert theme_id is None

    def test_theme_cascade_on_cycle_delete(self, base_fraiche):
        """Supprimer un cycle supprime ses thèmes en cascade."""
        conn = self._prepare(base_fraiche)
        conn.execute(
            "INSERT INTO themes (id, cycle_code, code, nom) "
            "VALUES ('th_1', 'C04', 'A', 'Nombres')"
        )
        conn.execute("DELETE FROM cycles WHERE code = 'C04'")
        n = conn.execute("SELECT COUNT(*) FROM themes").fetchone()[0]
        conn.close()
        assert n == 0


class TestMigration:
    """Le script de migration crée les tables sur une base ancienne."""

    def test_base_ancienne_sans_tables_r1(self, base_ancienne):
        conn = sqlite3.connect(str(base_ancienne.db_path))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        conn.close()
        assert "cycles" not in tables
        assert "themes" not in tables
        assert "sequences_du_cycle" not in tables

    def test_migration_cree_tables(self, base_ancienne):
        rapport = migrer(base_ancienne.db_path)
        assert set(rapport["tables_creees"]) == {
            "cycles", "themes", "sequences_du_cycle"
        }
        assert rapport["ok"] is True

        conn = sqlite3.connect(str(base_ancienne.db_path))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        conn.close()
        assert {"cycles", "themes", "sequences_du_cycle"}.issubset(tables)

    def test_migration_idempotente(self, base_ancienne):
        r1 = migrer(base_ancienne.db_path)
        r2 = migrer(base_ancienne.db_path)
        assert r1["ok"] is True
        assert r2["ok"] is True
        # 2e run : rien à créer
        assert r2["tables_creees"] == []

    def test_migration_sur_base_neuve_no_op(self, base_fraiche):
        """La base native a déjà les tables : migration = no-op."""
        rapport = migrer(base_fraiche.db_path)
        assert rapport["tables_creees"] == []
        assert rapport["ok"] is True
