"""
tests/test_peuplement_schema.py — Tests de la migration de schéma
v0.6.3e (script peuplement_01_migrer_schema).

Vérifie que les ALTER TABLE et CREATE TABLE produisent bien le schéma
attendu, et que le script est idempotent.
"""

import sqlite3
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.peuplement_01_migrer_schema import (
    migrer,
    SCHEMA_VERSION_ATTENDUE,
    COLONNES_A_AJOUTER,
    TABLES_A_CREER,
)
from persistence.sqlite_store import SqliteStore


@pytest.fixture
def base_pre_v063e(tmp_path):
    """
    Crée une base SQLite simulant une base d'AVANT v0.6.3e, c'est-à-dire
    sans les colonnes ni la table livret_revisions. Utile pour tester
    que la migration 01 les ajoute correctement sur une base existante.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "seqenseigne.db"

    # Créer directement les tables anciennes (schéma minimal pré-v0.6.3e)
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE notions ("
                 "id TEXT PRIMARY KEY, titre TEXT, corps TEXT, ordre_sections TEXT)")
    conn.execute("CREATE TABLE methodes ("
                 "id TEXT PRIMARY KEY, titre TEXT, corps TEXT, "
                 "fin_cycle TEXT, ordre_sections TEXT)")
    conn.execute("CREATE TABLE objectifs ("
                 "id TEXT PRIMARY KEY, methode_id TEXT, code TEXT, "
                 "critere_F TEXT, critere_A TEXT, critere_E TEXT)")
    conn.execute("CREATE TABLE exercices ("
                 "id TEXT PRIMARY KEY, serie TEXT, nom TEXT, "
                 "variables TEXT, enonce TEXT, corrige TEXT)")
    conn.execute("CREATE TABLE livrets_de_sequence ("
                 "id TEXT PRIMARY KEY, niveau TEXT, sequence TEXT, contenu TEXT)")
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def base_initialisee(tmp_path):
    """
    Crée une base SQLite via SqliteStore (schéma déjà à jour v0.6.3e).
    Utile pour tester l'idempotence : la migration 01 ne doit rien faire.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    store = SqliteStore(data_dir)
    db_path = data_dir / "seqenseigne.db"
    # Remettre user_version à 0 pour simuler une base qui n'a pas encore été
    # marquée v0.6.3e (schéma présent, compteur à poser).
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    conn.close()
    return db_path


# ── Tests de la première migration ────────────────────────────────────────────

class TestMigrationInitiale:
    """Première exécution : toutes les colonnes et tables doivent être créées.
    On part d'une base simulant une installation pré-v0.6.3e."""

    def test_migration_reussit(self, base_pre_v063e):
        rapport = migrer(base_pre_v063e)
        assert rapport["version_avant"] == 0
        assert rapport["version_apres"] == SCHEMA_VERSION_ATTENDUE

    def test_colonnes_ajoutees_dans_exercices(self, base_pre_v063e):
        migrer(base_pre_v063e)
        conn = sqlite3.connect(str(base_pre_v063e))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(exercices)")}
        conn.close()
        for col, _ in COLONNES_A_AJOUTER["exercices"]:
            assert col in cols, f"Colonne {col} manquante dans exercices"

    def test_colonnes_ajoutees_dans_notions(self, base_pre_v063e):
        migrer(base_pre_v063e)
        conn = sqlite3.connect(str(base_pre_v063e))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(notions)")}
        conn.close()
        for col, _ in COLONNES_A_AJOUTER["notions"]:
            assert col in cols, f"Colonne {col} manquante dans notions"

    def test_colonnes_ajoutees_dans_methodes(self, base_pre_v063e):
        migrer(base_pre_v063e)
        conn = sqlite3.connect(str(base_pre_v063e))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(methodes)")}
        conn.close()
        for col, _ in COLONNES_A_AJOUTER["methodes"]:
            assert col in cols, f"Colonne {col} manquante dans methodes"

    # v0.14.6.b.2 — test_colonnes_ajoutees_dans_objectifs supprimé : la
    # table `objectifs` (v1) n'existe plus.

    def test_table_livret_revisions_creee(self, base_pre_v063e):
        migrer(base_pre_v063e)
        conn = sqlite3.connect(str(base_pre_v063e))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        conn.close()
        assert "livret_revisions" in tables

    def test_index_crees(self, base_pre_v063e):
        rapport = migrer(base_pre_v063e)
        # v0.14.6.b.2 — Compteur passé de 7 à 6 : idx_objectifs_niv_seq
        # retiré (table supprimée).
        assert rapport["index_crees"] == 6

    def test_index_sur_exercices_niv_seq(self, base_pre_v063e):
        migrer(base_pre_v063e)
        conn = sqlite3.connect(str(base_pre_v063e))
        idx = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )}
        conn.close()
        assert "idx_exercices_niv_seq" in idx
        # v0.14.6.b.2 — assertion sur idx_objectifs_niv_seq retirée
        # (table supprimée).


# ── Idempotence ───────────────────────────────────────────────────────────────

class TestIdempotence:
    """Relancer le script ne doit rien modifier."""

    def test_schema_initial_deja_a_jour(self, base_initialisee):
        """Sur une base créée via SqliteStore (schéma v0.6.3e natif),
        la migration 01 ne doit ajouter aucune colonne ni table."""
        rapport = migrer(base_initialisee)
        # Les ALTER TABLE ne font rien car les colonnes existent déjà
        assert rapport["colonnes_ajoutees"] == {}
        assert rapport["tables_creees"] == []
        assert rapport["version_apres"] == SCHEMA_VERSION_ATTENDUE

    def test_deuxieme_passage_ne_modifie_rien(self, base_pre_v063e):
        """Sur une base pré-v0.6.3e : premier passage migre, deuxième ne fait rien."""
        r1 = migrer(base_pre_v063e)
        r2 = migrer(base_pre_v063e)
        # Premier passage : tout à créer
        assert r1["colonnes_ajoutees"]
        assert r1["tables_creees"]
        # Deuxième passage : rien à créer
        assert r2["colonnes_ajoutees"] == {}
        assert r2["tables_creees"] == []
        assert r2["version_avant"] == SCHEMA_VERSION_ATTENDUE
        assert r2["version_apres"] == SCHEMA_VERSION_ATTENDUE

    def test_donnees_preservees(self, base_pre_v063e):
        """Les données d'une base pré-v0.6.3e sont préservées par la migration."""
        conn = sqlite3.connect(str(base_pre_v063e))
        # Injecter une notion avant migration (4 colonnes, schéma ancien)
        conn.execute("INSERT INTO notions VALUES (?,?,?,?)",
                     ("n_abc", "Titre test", "Corps test", "ER"))
        conn.commit()
        conn.close()
        migrer(base_pre_v063e)
        conn = sqlite3.connect(str(base_pre_v063e))
        r = conn.execute("SELECT id, titre FROM notions WHERE id='n_abc'").fetchone()
        conn.close()
        assert r == ("n_abc", "Titre test")


# ── Cas limites ───────────────────────────────────────────────────────────────

class TestCasLimites:
    def test_base_inexistante_leve_erreur(self, tmp_path):
        chemin_inexistant = tmp_path / "inexistante.db"
        with pytest.raises(FileNotFoundError):
            migrer(chemin_inexistant)
