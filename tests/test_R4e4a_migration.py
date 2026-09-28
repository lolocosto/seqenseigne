"""tests/test_R4e4a_migration.py — R4e4a.

Tests de la migration de schéma `objectif_exos` :
  - num         → origin_num (renommage, valeurs préservées)
  - PK          : (objectif_id, serie, num) → (objectif_id, serie, exercice_id)
  - nouveau     : UNIQUE (objectif_id, serie, ordre)
  - `ordre` recalculé par ROW_NUMBER() pour garantir l'unicité, même si
    les données anciennes avaient des collisions

Contrat de la migration (dans sqlite_store._migrer_schema()) :
  - Sur base fraîche (schema.sql à jour) : table créée directement au
    bon format, la branche de migration ne s'exécute pas
  - Sur base ancienne (colonne `num` présente, `origin_num` absente) :
    CREATE _new + INSERT SELECT + DROP + RENAME
  - Idempotente : relancer ne fait rien
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from persistence.sqlite_store import SqliteStore


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def base_fraiche(tmp_path):
    """Base SQLite vierge, créée via SqliteStore → schema.sql récent."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return SqliteStore(data_dir)


def _creer_base_ancienne(db_path: Path) -> None:
    """Crée une base avec le schéma à jour (via SqliteStore), puis
    réécrit la table `objectif_exos` avec l'ancien schéma (colonne `num`,
    PK et UNIQUE anciennes) et y insère des données représentatives.

    Cela reproduit fidèlement l'état d'une base Laurent avant R4e4a :
    toutes les autres tables sont en version moderne, seule
    `objectif_exos` porte l'ancien format.
    """
    # Étape 1 : base créée via schema.sql moderne (en passant par SqliteStore
    # on bénéficie du pipeline complet mais avec une DB vierge → la
    # migration R4e4a ne se déclenche pas car il n'y a pas encore de
    # colonne `num`).
    data_dir = db_path.parent
    SqliteStore(data_dir)

    # Étape 2 : on écrase la table objectif_exos pour simuler l'ancien état.
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")  # pour pouvoir DROP
    conn.executescript("""
        DROP INDEX IF EXISTS idx_objectif_exos_exo;
        DROP TABLE objectif_exos;

        CREATE TABLE objectif_exos (
            objectif_id    TEXT NOT NULL REFERENCES objectifs(id) ON DELETE CASCADE,
            serie          TEXT NOT NULL,
            num            INTEGER NOT NULL,
            exercice_id    TEXT NOT NULL REFERENCES exercices(id) ON DELETE RESTRICT,
            ordre          INTEGER NOT NULL DEFAULT 0,
            origin_niveau  TEXT, origin_seq TEXT, origin_serie TEXT,
            PRIMARY KEY (objectif_id, serie, num),
            UNIQUE (objectif_id, serie, exercice_id)
        );
        CREATE INDEX idx_objectif_exos_exo ON objectif_exos (exercice_id);
    """)
    # Pour insérer, il faut que les objectifs et exercices référencés existent.
    # On crée une séquence + partie + objectifs + exercices minimaux.
    # Les colonnes de ces tables étant pilotées par schema.sql (à jour), on
    # doit fournir tout ce que les NOT NULL impliquent. On découvre les
    # colonnes via PRAGMA pour rester robuste au schéma réel.

    conn.execute(
        "INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
        "VALUES ('sn_anc', 'N11', 'S03')"
    )
    conn.execute(
        "INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
        "VALUES ('pt_anc', 'sn_anc', 1)"
    )
    conn.executemany(
        "INSERT INTO objectifs (id, partie_id, code) VALUES (?, ?, ?)",
        [("ob_1", "pt_anc", "01"), ("ob_2", "pt_anc", "02")],
    )
    # Colonnes de `exercices` — on lit dynamiquement pour s'adapter au schéma
    ex_cols = {r[1] for r in conn.execute("PRAGMA table_info(exercices)").fetchall()}
    # Colonnes obligatoires supposées : id ; colonnes NOT NULL habituelles : niveau, sequence, serie_code, num, nom, fichier
    for exid, num_ex in [("ex_1", 1), ("ex_2", 2), ("ex_3", 3),
                          ("ex_4", 4), ("ex_5", 5), ("ex_6", 6)]:
        champs = ["id"]
        vals = [exid]
        # Champs textuels : on ne définit que ceux qui existent réellement
        for c in ("niveau", "sequence", "serie_code", "nom", "fichier"):
            if c in ex_cols:
                champs.append(c)
                vals.append("N11" if c == "niveau"
                            else "S03" if c == "sequence"
                            else "F" if c == "serie_code"
                            else f"Exo {exid}" if c == "nom"
                            else f"{exid}.tex")
        # `serie` est la colonne NOT NULL à nom long ('fondamental', 'avancé'...)
        if "serie" in ex_cols:
            champs.append("serie")
            vals.append("fondamental")
        if "num" in ex_cols:
            champs.append("num")
            vals.append(num_ex)
        placeholders = ", ".join("?" * len(champs))
        conn.execute(
            f"INSERT INTO exercices ({', '.join(champs)}) VALUES ({placeholders})",
            vals,
        )

    # Les données d'objectif_exos (ancien format)
    conn.executescript("""
        INSERT INTO objectif_exos
            (objectif_id, serie, num, exercice_id, ordre) VALUES
            ('ob_1', 'F', 1, 'ex_1', 1),
            ('ob_1', 'F', 2, 'ex_2', 2),
            ('ob_1', 'F', 3, 'ex_3', 3);

        INSERT INTO objectif_exos
            (objectif_id, serie, num, exercice_id, ordre,
             origin_niveau, origin_seq, origin_serie) VALUES
            ('ob_1', 'R', 5, 'ex_4', 1, 'N10', 'S01', 'F');

        INSERT INTO objectif_exos
            (objectif_id, serie, num, exercice_id, ordre) VALUES
            ('ob_2', 'F', 1, 'ex_5', 5),
            ('ob_2', 'F', 2, 'ex_6', 5);
    """)
    conn.commit()
    conn.close()


@pytest.fixture
def base_ancienne(tmp_path):
    """Simule une base créée avant R4e4a. On prépare d'abord les tables
    à la main, PUIS on instancie SqliteStore → la migration s'applique."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "seqenseigne.db"
    _creer_base_ancienne(db_path)
    # Instancier SqliteStore déclenche _init_db → _migrer_schema → migration
    store = SqliteStore(data_dir)
    return store


# ═════════════════════════════════════════════════════════════════════════════
# 1. Base fraîche — schéma correct d'emblée
# ═════════════════════════════════════════════════════════════════════════════

class TestBaseFraiche:
    def test_origin_num_present(self, base_fraiche):
        with base_fraiche._conn() as conn:
            cols = {r["name"] for r in conn.execute(
                "PRAGMA table_info(objectif_exos)"
            ).fetchall()}
        assert "origin_num" in cols
        assert "num" not in cols

    def test_pk_sur_exercice_id(self, base_fraiche):
        """La PK doit être (objectif_id, serie, exercice_id)."""
        with base_fraiche._conn() as conn:
            rows = conn.execute(
                "PRAGMA table_info(objectif_exos)"
            ).fetchall()
        pk_cols = [r["name"] for r in rows if r["pk"] > 0]
        # SQLite retourne les colonnes PK dans l'ordre déclaré, avec pk=1,2,3...
        pk_cols_tries = sorted(rows, key=lambda r: r["pk"])
        pk_ordonnees = [r["name"] for r in pk_cols_tries if r["pk"] > 0]
        assert pk_ordonnees == ["objectif_id", "serie", "exercice_id"]

    def test_contrainte_unique_ordre(self, tmp_path):
        """UNIQUE(objectif_id, serie, ordre) doit être active sur base fraîche.

        On construit une base avec un peu de peuplement (pattern repris
        de la fixture base_ancienne) puis on teste la contrainte sur
        objectif_exos directement.
        """
        # On réutilise la même mécanique : créer une base fraîche,
        # peupler séquence/partie/objectif/exercices, puis tester.
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        store = SqliteStore(data_dir)

        db_path = data_dir / "seqenseigne.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
            "VALUES ('sn_t', 'N11', 'S03')"
        )
        conn.execute(
            "INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
            "VALUES ('pt_t', 'sn_t', 1)"
        )
        conn.execute(
            "INSERT INTO objectifs (id, partie_id, code) "
            "VALUES ('ob_t', 'pt_t', 't')"
        )
        # Pour exercices, on lit les colonnes NOT NULL dynamiquement
        ex_cols = {r[1] for r in conn.execute("PRAGMA table_info(exercices)").fetchall()}
        for exid in ("ex_t1", "ex_t2"):
            champs = ["id"]
            vals = [exid]
            for c, default in [("niveau", "N11"), ("sequence", "S03"),
                               ("serie_code", "F"), ("nom", ""), ("fichier", ""),
                               ("serie", "fondamental")]:
                if c in ex_cols:
                    champs.append(c)
                    vals.append(default)
            if "num" in ex_cols:
                champs.append("num")
                vals.append(1)
            placeholders = ", ".join("?" * len(champs))
            conn.execute(
                f"INSERT INTO exercices ({', '.join(champs)}) "
                f"VALUES ({placeholders})",
                vals,
            )
        conn.commit()

        # 1re insertion OK
        conn.execute(
            "INSERT INTO objectif_exos "
            "(objectif_id, serie, exercice_id, ordre) "
            "VALUES ('ob_t', 'F', 'ex_t1', 1)"
        )
        # 2e avec même (obj, série, ordre) mais exo différent : doit échouer
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO objectif_exos "
                "(objectif_id, serie, exercice_id, ordre) "
                "VALUES ('ob_t', 'F', 'ex_t2', 1)"
            )
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# 2. Base ancienne — migration appliquée
# ═════════════════════════════════════════════════════════════════════════════

class TestMigrationDepuisBaseAncienne:
    def test_colonnes_apres_migration(self, base_ancienne):
        with base_ancienne._conn() as conn:
            cols = {r["name"] for r in conn.execute(
                "PRAGMA table_info(objectif_exos)"
            ).fetchall()}
        assert "origin_num" in cols
        assert "num" not in cols

    def test_donnees_preservees(self, base_ancienne):
        """Les anciennes valeurs de `num` doivent se retrouver dans
        `origin_num`."""
        with base_ancienne._conn() as conn:
            rows = conn.execute(
                "SELECT objectif_id, serie, exercice_id, origin_num "
                "FROM objectif_exos "
                "WHERE objectif_id = 'ob_1' "
                "ORDER BY serie, ordre"
            ).fetchall()
        vus = {(r["serie"], r["exercice_id"]): r["origin_num"] for r in rows}
        # F : ex_1 avait num=1, ex_2 avait num=2, ex_3 avait num=3
        assert vus[("F", "ex_1")] == 1
        assert vus[("F", "ex_2")] == 2
        assert vus[("F", "ex_3")] == 3
        # R : ex_4 avait num=5 (numéro dans la série d'origine N10/S01/F)
        assert vus[("R", "ex_4")] == 5

    def test_origin_fields_preserves(self, base_ancienne):
        with base_ancienne._conn() as conn:
            row = conn.execute(
                "SELECT origin_niveau, origin_seq, origin_serie "
                "FROM objectif_exos WHERE exercice_id = 'ex_4'"
            ).fetchone()
        assert row["origin_niveau"] == "N10"
        assert row["origin_seq"] == "S01"
        assert row["origin_serie"] == "F"

    def test_collision_ordre_resolue(self, base_ancienne):
        """obj_2/F avait deux exos avec ordre=5 dans l'ancienne base.
        Après migration, ils doivent avoir des ordres différents, dense
        (1, 2 à partir de 1)."""
        with base_ancienne._conn() as conn:
            rows = conn.execute(
                "SELECT exercice_id, ordre FROM objectif_exos "
                "WHERE objectif_id = 'ob_2' AND serie = 'F' "
                "ORDER BY ordre"
            ).fetchall()
        ordres = [r["ordre"] for r in rows]
        assert ordres == [1, 2]  # dense

    def test_contrainte_unique_ordre_active(self, base_ancienne):
        """Tenter d'insérer un doublon d'ordre après migration doit échouer."""
        with base_ancienne._conn() as conn:
            # ob_1 série F a les ordres 1, 2, 3 → tenter d'insérer à 2
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO objectif_exos "
                    "(objectif_id, serie, exercice_id, ordre) "
                    "VALUES ('ob_1', 'F', 'ex_5', 2)"
                )

    def test_contrainte_pk_active(self, base_ancienne):
        """Tenter d'insérer le même (obj, série, exo) deux fois doit échouer."""
        with base_ancienne._conn() as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO objectif_exos "
                    "(objectif_id, serie, exercice_id, ordre) "
                    "VALUES ('ob_1', 'F', 'ex_1', 99)"
                )


# ═════════════════════════════════════════════════════════════════════════════
# 3. Idempotence
# ═════════════════════════════════════════════════════════════════════════════

class TestIdempotence:
    def test_relance_init_db_ne_change_rien(self, base_ancienne, tmp_path):
        """Après une 1re migration, réinstancier SqliteStore sur le même
        dossier ne doit pas refaire la migration (pas d'erreur, données
        inchangées)."""
        # 1re passe déjà faite dans la fixture. On vérifie le nombre de lignes.
        with base_ancienne._conn() as conn:
            n1 = conn.execute("SELECT COUNT(*) FROM objectif_exos").fetchone()[0]

        # 2e instanciation sur la même base
        store2 = SqliteStore(base_ancienne.data_dir)
        with store2._conn() as conn:
            n2 = conn.execute("SELECT COUNT(*) FROM objectif_exos").fetchone()[0]
            cols = {r["name"] for r in conn.execute(
                "PRAGMA table_info(objectif_exos)"
            ).fetchall()}

        assert n1 == n2
        assert "origin_num" in cols
        assert "num" not in cols
