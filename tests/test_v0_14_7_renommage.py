"""Tests v0.14.7 + v0.15.0.1 — Table `objectifs` (modèle unique).

v0.14.7 a clos le chantier de suppression de la table v1 par le renommage
de `objectifs_v2` → `objectifs`. v0.15.0.1 a remplacé le script de
renommage manuel par une migration automatique au démarrage de SqliteStore
(suite à un cas où le renommage manuel n'avait pas été lancé avant le
premier démarrage post-déploiement, laissant la table active `objectifs`
vide).

Ces tests valident :
1. Sur une base fraîche, la table `objectifs` existe (et `objectifs_v2`
   n'existe pas).
2. Les FK qui pointaient vers `objectifs_v2` pointent maintenant vers
   `objectifs`.
3. L'index `idx_objectifs_partie` est présent (renommé depuis
   `idx_objectifs_v2_partie`).
4. La migration auto v0.15.0.1 reconcilie les données quand
   `objectifs_v2` est peuplée et `objectifs` vide. Elle est idempotente
   et silencieuse sur une BDD propre.
5. Plusieurs scripts historiques de migration v1→v2 ont disparu, y
   compris `scripts/renommer_objectifs_v2.py` (supprimé en v0.15.0.1).
6. Les chaînes principales (atomes, fiches, livret de séquence)
   fonctionnent toujours sur le nouveau nom.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def store_migre(tmp_path):
    """Store SQLite avec schéma post-v0.14.7 appliqué."""
    from persistence.sqlite_store import SqliteStore
    from scripts.peuplement_01_migrer_schema import migrer

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    store = SqliteStore(data_dir)
    migrer(data_dir / "seqenseigne.db")
    return store


# ── 1. Table `objectifs` présente, `objectifs_v2` absente ────────────

class TestNomDeTable:
    """v0.14.7 — La table porte désormais le nom `objectifs` (sans
    suffixe `_v2`).
    """

    def test_objectifs_presente(self, store_migre):
        with store_migre._conn() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='objectifs'"
            ).fetchone()
        assert row is not None

    def test_objectifs_v2_absente(self, store_migre):
        with store_migre._conn() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='objectifs_v2'"
            ).fetchone()
        assert row is None

    def test_colonnes_attendues(self, store_migre):
        """La structure de la table est celle de l'ex-`objectifs_v2`."""
        with store_migre._conn() as conn:
            cols = {r["name"] for r in conn.execute(
                "PRAGMA table_info(objectifs)"
            ).fetchall()}
        attendues = {"id", "partie_id", "code", "nom", "methode_id",
                     "critere_F", "critere_A", "critere_E"}
        for col in attendues:
            assert col in cols, f"Colonne {col} manquante"


# ── 2. Index renommé ──────────────────────────────────────────────────

class TestIndex:
    """v0.14.7 — L'index `idx_objectifs_v2_partie` est devenu
    `idx_objectifs_partie`.
    """

    def test_index_nouveau_nom_present(self, store_migre):
        with store_migre._conn() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name='idx_objectifs_partie'"
            ).fetchone()
        assert row is not None

    def test_index_ancien_nom_absent(self, store_migre):
        with store_migre._conn() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name='idx_objectifs_v2_partie'"
            ).fetchone()
        assert row is None


# ── 3. FK pointent vers le nouveau nom ────────────────────────────────

class TestForeignKeys:
    """v0.14.7 — Toutes les FK qui référençaient `objectifs_v2(id)`
    pointent désormais vers `objectifs(id)`.
    """

    @pytest.mark.parametrize("table_source", [
        "objectif_notions",
        "objectif_cartes",
        "objectif_exos",
        "fiches_resume",
    ])
    def test_fk_pointe_vers_objectifs(self, store_migre, table_source):
        with store_migre._conn() as conn:
            fks = list(conn.execute(
                f"PRAGMA foreign_key_list({table_source})"
            ).fetchall())
        # On cherche une FK qui pointe vers `objectifs`
        cibles = {r["table"] for r in fks}
        assert "objectifs" in cibles, (
            f"{table_source} doit avoir une FK vers `objectifs` ; "
            f"trouvé : {cibles}"
        )
        # Et aucune FK ne pointe vers `objectifs_v2`
        assert "objectifs_v2" not in cibles, (
            f"{table_source} a encore une FK vers `objectifs_v2` !"
        )


# ── 4. Cascade fonctionne sur le nouveau nom ─────────────────────────

class TestCascadeFonctionne:
    """v0.14.7 — Sanity : insérer dans objectifs, créer des liaisons
    dans objectif_exos, puis supprimer l'objectif → la cascade ON
    DELETE doit toujours fonctionner.
    """

    def test_cascade_objectif_exos(self, store_migre):
        with store_migre._conn() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            # Pile complète : sn → partie → objectif
            conn.execute(
                "INSERT INTO sequences_par_niveau "
                "(id, niveau, sequence_code) VALUES ('sn1', 'N10', 'S01')"
            )
            conn.execute(
                "INSERT INTO sequence_parties "
                "(id, sequence_par_niveau_id, numero) "
                "VALUES ('pt1', 'sn1', 1)"
            )
            conn.execute(
                "INSERT INTO objectifs "
                "(id, partie_id, code, nom) "
                "VALUES ('ob1', 'pt1', '02', 'Obj test')"
            )
            conn.execute(
                "INSERT INTO exercices "
                "(id, serie, serie_code, niveau, sequence, num, fichier) "
                "VALUES ('ex1', 'F', 'F', 'N10', 'S01', 1, 'x.tex')"
            )
            conn.execute(
                "INSERT INTO objectif_exos "
                "(objectif_id, serie, exercice_id, ordre) "
                "VALUES ('ob1', 'F', 'ex1', 1)"
            )
            conn.commit()

            # CASCADE : supprimer l'objectif doit supprimer la liaison
            conn.execute("DELETE FROM objectifs WHERE id='ob1'")
            conn.commit()
            n = conn.execute(
                "SELECT COUNT(*) FROM objectif_exos WHERE objectif_id='ob1'"
            ).fetchone()[0]
        assert n == 0, "CASCADE ON DELETE doit fonctionner sur `objectifs`"


# ── 5. Migration auto v0.15.0.1 (remplace l'ancien script v0.14.7) ───

class TestMigrationReconciliationV0_15_0_1:
    """v0.15.0.1 — Migration auto de réconciliation `objectifs ← objectifs_v2`.

    Contexte : en v0.14.7, le renommage devait être effectué par le script
    `scripts/renommer_objectifs_v2.py` lancé manuellement avant le premier
    démarrage post-déploiement. Si l'utilisateur lançait `lancer.bat`
    d'abord, le `CREATE TABLE IF NOT EXISTS objectifs` de schema.sql créait
    une table `objectifs` vide à côté de `objectifs_v2` peuplée (cas
    rencontré chez le mainteneur fin mai 2026). Le script de renommage
    refusait ensuite de tourner (conflit table de destination existante),
    laissant l'utilisateur avec une table active vide.

    v0.15.0.1 ajoute une migration au démarrage de SqliteStore qui :
      - Détecte le cas (objectifs_v2 peuplée + objectifs vide)
      - Copie les données via INSERT OR IGNORE
      - Imprime un message d'information

    Le script v0.14.7 `renommer_objectifs_v2.py` est supprimé : la
    migration auto le remplace pour tous les cas pratiques.
    """

    # v0.51.13 — La réconciliation est retirée : objectifs_v2 (et
    # items_texte) sont des résidus retirés au démarrage, contenu sauvegardé.

    def test_residus_retires_avec_sauvegarde(self, tmp_path):
        import json
        from persistence.sqlite_store import SqliteStore

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        SqliteStore(data_dir)
        db_path = data_dir / "seqenseigne.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE objectifs_v2 (id TEXT PRIMARY KEY, partie_id TEXT, code TEXT);
            INSERT INTO objectifs_v2 VALUES ('ob1', 'pt', '02');
            CREATE TABLE items_texte (id TEXT PRIMARY KEY, categorie TEXT, texte TEXT);
            INSERT INTO items_texte VALUES ('it1', 'exemple', 'Un exemple');
        """)
        conn.commit()
        conn.close()
        SqliteStore(data_dir)                       # redémarrage : retrait
        conn = sqlite3.connect(str(db_path))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert not ({"objectifs_v2", "items_texte"} & tables) and "objectifs" in tables
        sauv = list((data_dir / "sauvegardes").glob("retrait_residus_*.json"))
        assert len(sauv) == 1
        contenu = json.loads(sauv[0].read_text(encoding="utf-8"))["tables"]
        assert contenu["objectifs_v2"][0]["id"] == "ob1"
        assert contenu["items_texte"][0]["texte"] == "Un exemple"
        SqliteStore(data_dir)                       # idempotent
        assert len(list((data_dir / "sauvegardes").glob("retrait_residus_*.json"))) == 1

    def test_residu_reference_par_une_cle_garde(self, tmp_path):
        from persistence.sqlite_store import SqliteStore

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        SqliteStore(data_dir)
        db_path = data_dir / "seqenseigne.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE objectifs_v2 (id TEXT PRIMARY KEY);
            CREATE TABLE lien_v2 (x TEXT REFERENCES objectifs_v2(id));
        """)
        conn.commit()
        conn.close()
        SqliteStore(data_dir)
        conn = sqlite3.connect(str(db_path))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "objectifs_v2" in tables

    def test_pas_de_migration_si_objectifs_v2_absente(self, tmp_path):
        """Sur une BDD fraîche (post-v0.14.7 propre), objectifs_v2 n'existe
        pas et la migration est silencieuse. Aucune erreur ne doit être levée.
        """
        from persistence.sqlite_store import SqliteStore

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        # Création + ré-instanciation doivent toutes deux fonctionner
        SqliteStore(data_dir)
        SqliteStore(data_dir)

        db_path = data_dir / "seqenseigne.db"
        conn = sqlite3.connect(str(db_path))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        conn.close()
        assert "objectifs" in tables
        assert "objectifs_v2" not in tables, (
            "Sur BDD fraîche, le schema.sql ne crée pas objectifs_v2"
        )

    def test_script_renommer_supprime(self):
        """v0.15.0.1 — Le script `renommer_objectifs_v2.py` a été supprimé,
        sa fonction étant désormais portée par la migration auto.
        """
        appli = Path(__file__).resolve().parent.parent
        script = appli / "scripts" / "renommer_objectifs_v2.py"
        assert not script.exists(), (
            "v0.15.0.1 a supprimé scripts/renommer_objectifs_v2.py"
        )


# ── 6. Scripts historiques supprimés ──────────────────────────────────

class TestScriptsHistoriquesSupprimes:
    """v0.14.7 — Plusieurs scripts historiques liés au chantier de
    migration v1→v2 ont été retirés car leur raison d'être disparaît
    avec la table v1.
    """

    APPLI = Path(__file__).resolve().parent.parent

    @pytest.mark.parametrize("chemin", [
        "scripts/audit_v1_v2.py",
        "scripts/migrer_v1_vers_v2.py",
        "scripts/migrer_methodes_objectifs.py",
        "scripts/peuplement_12_migrer_schema_sequences.py",
    ])
    def test_script_absent(self, chemin):
        assert not (self.APPLI / chemin).exists(), (
            f"Le script {chemin} doit avoir été supprimé en v0.14.7"
        )


# ── 7. Chaînes principales fonctionnent sur le nouveau nom ───────────

class TestChainesPrincipales:
    """v0.14.7 — Sanity de bout en bout : on peut créer un objectif,
    une méthode, une fiche, et les lier ensemble en utilisant
    uniquement le nouveau nom `objectifs`.
    """

    def test_creer_objectif_et_lire(self, store_migre):
        """Création + lecture via `objectifs`."""
        with store_migre._conn() as conn:
            conn.execute(
                "INSERT INTO sequences_par_niveau "
                "(id, niveau, sequence_code) VALUES ('sn1', 'N10', 'S01')"
            )
            conn.execute(
                "INSERT INTO sequence_parties "
                "(id, sequence_par_niveau_id, numero) "
                "VALUES ('pt1', 'sn1', 1)"
            )
            conn.execute(
                "INSERT INTO objectifs "
                "(id, partie_id, code, nom) "
                "VALUES ('ob1', 'pt1', '02', 'Mon objectif')"
            )
            conn.commit()

            row = conn.execute(
                "SELECT id, code, nom FROM objectifs WHERE code='02'"
            ).fetchone()
        assert row is not None
        assert row["nom"] == "Mon objectif"

    def test_join_objectif_partie_sequence(self, store_migre):
        """Le JOIN typique partie → objectif → sequence_par_niveau
        fonctionne sur le nouveau nom.
        """
        with store_migre._conn() as conn:
            conn.execute(
                "INSERT INTO sequences_par_niveau "
                "(id, niveau, sequence_code) VALUES ('sn1', 'N10', 'S01')"
            )
            conn.execute(
                "INSERT INTO sequence_parties "
                "(id, sequence_par_niveau_id, numero) "
                "VALUES ('pt1', 'sn1', 1)"
            )
            conn.execute(
                "INSERT INTO objectifs "
                "(id, partie_id, code, nom) "
                "VALUES ('ob1', 'pt1', '02', 'Obj')"
            )
            conn.commit()

            # JOIN canonique
            row = conn.execute(
                "SELECT sn.niveau AS niveau, sn.sequence_code AS sequence, "
                "       ov.code AS code, ov.nom AS nom "
                "FROM objectifs ov "
                "JOIN sequence_parties      p  ON p.id  = ov.partie_id "
                "JOIN sequences_par_niveau  sn ON sn.id = p.sequence_par_niveau_id "
                "WHERE ov.code='02'"
            ).fetchone()
        assert row is not None
        assert row["niveau"] == "N10"
        assert row["sequence"] == "S01"
        assert row["code"] == "02"
        assert row["nom"] == "Obj"
