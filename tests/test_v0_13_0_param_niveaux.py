"""tests/test_v0_13_0_param_niveaux.py — v0.13.0.

Tests du chantier 1/3 série v0.13 « Référentiel de niveau ».

Ce fichier couvre :
  - Le DDL de la nouvelle table `param_niveaux` (colonnes, types,
    contraintes, FK, index).
  - Le peuplement initial automatique depuis `data/param_niveaux.csv`
    quand la table est vide à l'init.
  - L'idempotence : ré-initialiser SqliteStore ne duplique pas et
    n'écrase pas les données présentes.
  - La robustesse : CSV absent → table vide (pas de crash) ; CSV mal
    formé → ligne sautée silencieusement.
  - Le respect du principe « la BDD est maître après amorçage » :
    si la table est déjà peuplée, le CSV n'est pas relu (les
    modifications BDD ne sont jamais écrasées).

Cette livraison ne consomme PAS encore la table dans les services
(ce sera v0.13.1). Seul le peuplement et le DDL sont testés ici.
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from persistence.sqlite_store import SqliteStore


_CSV_VALIDE = (
    "Code,CodeCycle,AnneeDansCycle,NomCourt,NomLong\r\n"
    "N07,C03,anneeun,CM1,cours moyen (1ère année)\r\n"
    "N08,C03,anneedeux,CM2,cours moyen (2nde année)\r\n"
    "N09,C03,anneetrois,6ème,sixième\r\n"
    "N10,C04,anneeun,5ème,cinquième\r\n"
    "N11,C04,anneedeux,4ème,quatrième\r\n"
    "N12,C04,anneetrois,3ème,troisième\r\n"
)


@pytest.fixture
def data_dir_avec_csv(tmp_path: Path) -> Path:
    """Répertoire data temporaire avec param_niveaux.csv valide.

    SqliteStore.__init__ crée la BDD à `data_dir / seqenseigne.db`,
    applique le DDL, et amorce param_niveaux depuis le CSV s'il existe.
    """
    d = tmp_path / "data"
    d.mkdir()
    (d / "param_niveaux.csv").write_text(_CSV_VALIDE, encoding="utf-8")
    return d


@pytest.fixture
def data_dir_sans_csv(tmp_path: Path) -> Path:
    """Répertoire data sans param_niveaux.csv (cas dégradé)."""
    d = tmp_path / "data"
    d.mkdir()
    return d


# ═════════════════════════════════════════════════════════════════════════════
# 1. Schéma : la table existe et a la structure attendue
# ═════════════════════════════════════════════════════════════════════════════

class TestSchema:

    def test_table_param_niveaux_existe(self, data_dir_avec_csv):
        SqliteStore(data_dir_avec_csv)
        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            r = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='param_niveaux'"
            ).fetchone()
        assert r is not None

    def test_colonnes_param_niveaux(self, data_dir_avec_csv):
        """Le schéma doit avoir exactement les 6 colonnes attendues,
        avec les bons types et les bonnes contraintes NOT NULL."""
        SqliteStore(data_dir_avec_csv)
        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            cols = {r[1]: dict(zip(
                ["cid", "name", "type", "notnull", "dflt_value", "pk"],
                r,
            )) for r in conn.execute("PRAGMA table_info(param_niveaux)")}

        assert set(cols.keys()) == {
            "code", "cycle_code", "annee_dans_cycle",
            "nom_court", "nom_long", "ordre",
        }
        # PRIMARY KEY sur code
        assert cols["code"]["pk"] == 1
        # NOT NULL sur les colonnes obligatoires
        assert cols["cycle_code"]["notnull"] == 1
        assert cols["annee_dans_cycle"]["notnull"] == 1
        assert cols["nom_court"]["notnull"] == 1
        # nom_long : NOT NULL avec DEFAULT '' (peut rester optionnel à la
        # saisie via le DEFAULT)
        assert cols["nom_long"]["notnull"] == 1
        # ordre : INTEGER NOT NULL DEFAULT 0
        assert cols["ordre"]["type"] == "INTEGER"
        assert cols["ordre"]["notnull"] == 1

    def test_fk_cycle_code_actif(self, data_dir_avec_csv):
        """La FK vers cycles(code) doit être déclarée et active."""
        SqliteStore(data_dir_avec_csv)
        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            fks = list(conn.execute("PRAGMA foreign_key_list(param_niveaux)"))
        assert len(fks) == 1
        # fks[0] = (id, seq, table, from, to, on_update, on_delete, match)
        assert fks[0][2] == "cycles"      # référence cycles
        assert fks[0][3] == "cycle_code"  # depuis param_niveaux.cycle_code
        assert fks[0][4] == "code"        # vers cycles.code

    def test_index_idx_param_niveaux_cycle(self, data_dir_avec_csv):
        SqliteStore(data_dir_avec_csv)
        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            indexes = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND tbl_name='param_niveaux'"
            )]
        assert "idx_param_niveaux_cycle" in indexes


# ═════════════════════════════════════════════════════════════════════════════
# 2. Peuplement initial depuis CSV
# ═════════════════════════════════════════════════════════════════════════════

class TestPeuplementInitial:

    def test_amorcage_complet_depuis_csv(self, data_dir_avec_csv):
        """Au premier démarrage avec table vide + CSV présent, les 6
        niveaux sont insérés."""
        SqliteStore(data_dir_avec_csv)
        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            conn.row_factory = sqlite3.Row
            rows = list(conn.execute(
                "SELECT * FROM param_niveaux ORDER BY ordre"
            ))
        codes = [r["code"] for r in rows]
        assert codes == ["N07", "N08", "N09", "N10", "N11", "N12"]

    def test_attributs_correctement_mappes(self, data_dir_avec_csv):
        """Vérification spécifique sur N10 (5ème) et N12 (3ème)."""
        SqliteStore(data_dir_avec_csv)
        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            conn.row_factory = sqlite3.Row
            n10 = dict(conn.execute(
                "SELECT * FROM param_niveaux WHERE code = 'N10'"
            ).fetchone())
            n12 = dict(conn.execute(
                "SELECT * FROM param_niveaux WHERE code = 'N12'"
            ).fetchone())

        assert n10["cycle_code"] == "C04"
        assert n10["annee_dans_cycle"] == "anneeun"
        assert n10["nom_court"] == "5ème"
        assert n10["nom_long"] == "cinquième"
        assert n10["ordre"] == 4

        assert n12["cycle_code"] == "C04"
        assert n12["annee_dans_cycle"] == "anneetrois"
        assert n12["nom_court"] == "3ème"
        assert n12["nom_long"] == "troisième"
        assert n12["ordre"] == 6

    def test_ordre_derive_de_la_position_csv(self, data_dir_avec_csv):
        """Le champ `ordre` doit refléter la position du niveau dans le
        CSV (1-indexé)."""
        SqliteStore(data_dir_avec_csv)
        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            conn.row_factory = sqlite3.Row
            rows = list(conn.execute(
                "SELECT code, ordre FROM param_niveaux ORDER BY ordre"
            ))
        ordres = [(r["code"], r["ordre"]) for r in rows]
        assert ordres == [
            ("N07", 1), ("N08", 2), ("N09", 3),
            ("N10", 4), ("N11", 5), ("N12", 6),
        ]


# ═════════════════════════════════════════════════════════════════════════════
# 3. Idempotence : ré-init ne duplique ni n'écrase
# ═════════════════════════════════════════════════════════════════════════════

class TestIdempotence:

    def test_re_init_ne_duplique_pas(self, data_dir_avec_csv):
        """Démarrer SqliteStore deux fois ne doit pas créer de doublons."""
        SqliteStore(data_dir_avec_csv)
        SqliteStore(data_dir_avec_csv)  # 2e fois
        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            n = conn.execute("SELECT COUNT(*) FROM param_niveaux").fetchone()[0]
        assert n == 6

    def test_modifications_bdd_preservees_par_re_init(self, data_dir_avec_csv):
        """Si on modifie la table en BDD (simule une édition manuelle),
        une ré-init ne doit PAS écraser ces modifs depuis le CSV.
        Principe : la BDD est maître après amorçage."""
        SqliteStore(data_dir_avec_csv)
        # Modification simulée : changer le nom_long de N10
        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            conn.execute(
                "UPDATE param_niveaux SET nom_long = ? WHERE code = ?",
                ("CINQUIÈME MODIFIÉ", "N10"),
            )
            conn.commit()

        # Re-init
        SqliteStore(data_dir_avec_csv)

        # La modification doit être préservée
        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            r = conn.execute(
                "SELECT nom_long FROM param_niveaux WHERE code = 'N10'"
            ).fetchone()
        assert r[0] == "CINQUIÈME MODIFIÉ"

    def test_suppressions_bdd_preservees_par_re_init(self, data_dir_avec_csv):
        """Si on supprime des lignes en BDD, une ré-init ne doit PAS les
        ré-importer depuis le CSV (la table n'est plus vide ⇒ pas
        d'amorçage)."""
        SqliteStore(data_dir_avec_csv)
        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            conn.execute("DELETE FROM param_niveaux WHERE code IN ('N07', 'N08')")
            conn.commit()

        SqliteStore(data_dir_avec_csv)

        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            codes = sorted(r[0] for r in conn.execute(
                "SELECT code FROM param_niveaux"
            ))
        # Les 2 lignes supprimées ne sont pas revenues
        assert codes == ["N09", "N10", "N11", "N12"]


# ═════════════════════════════════════════════════════════════════════════════
# 4. Robustesse : CSV absent, malformé, vide
# ═════════════════════════════════════════════════════════════════════════════

class TestRobustesse:

    def test_csv_absent_table_vide_pas_de_crash(self, data_dir_sans_csv):
        """Si le CSV est absent, la table doit être créée mais vide
        (pas de crash au démarrage)."""
        SqliteStore(data_dir_sans_csv)
        with sqlite3.connect(data_dir_sans_csv / "seqenseigne.db") as conn:
            n = conn.execute("SELECT COUNT(*) FROM param_niveaux").fetchone()[0]
        assert n == 0

    def test_csv_vide_table_vide_pas_de_crash(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        (d / "param_niveaux.csv").write_text("", encoding="utf-8")
        SqliteStore(d)
        with sqlite3.connect(d / "seqenseigne.db") as conn:
            n = conn.execute("SELECT COUNT(*) FROM param_niveaux").fetchone()[0]
        assert n == 0

    def test_csv_avec_seulement_header_pas_de_crash(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        (d / "param_niveaux.csv").write_text(
            "Code,CodeCycle,AnneeDansCycle,NomCourt,NomLong\r\n",
            encoding="utf-8",
        )
        SqliteStore(d)
        with sqlite3.connect(d / "seqenseigne.db") as conn:
            n = conn.execute("SELECT COUNT(*) FROM param_niveaux").fetchone()[0]
        assert n == 0

    def test_csv_ligne_malformee_sautee(self, tmp_path):
        """Une ligne avec Code vide doit être ignorée silencieusement
        (pas de crash, pas d'exception au démarrage)."""
        d = tmp_path / "data"
        d.mkdir()
        contenu = (
            "Code,CodeCycle,AnneeDansCycle,NomCourt,NomLong\r\n"
            ",C04,anneeun,5ème,cinquième\r\n"          # Code vide → sauté
            "N11,C04,anneedeux,4ème,quatrième\r\n"     # OK
            ",,,,\r\n"                                  # Tous vides → sauté
        )
        (d / "param_niveaux.csv").write_text(contenu, encoding="utf-8")
        SqliteStore(d)
        with sqlite3.connect(d / "seqenseigne.db") as conn:
            codes = [r[0] for r in conn.execute(
                "SELECT code FROM param_niveaux"
            )]
        assert codes == ["N11"]

    def test_csv_avec_bom_utf8(self, tmp_path):
        """CSV exporté depuis Excel a souvent un BOM UTF-8 — doit être
        géré (utilisation de utf-8-sig à la lecture)."""
        d = tmp_path / "data"
        d.mkdir()
        contenu_avec_bom = "\ufeff" + _CSV_VALIDE
        (d / "param_niveaux.csv").write_text(contenu_avec_bom, encoding="utf-8")
        SqliteStore(d)
        with sqlite3.connect(d / "seqenseigne.db") as conn:
            n = conn.execute("SELECT COUNT(*) FROM param_niveaux").fetchone()[0]
        assert n == 6


# ═════════════════════════════════════════════════════════════════════════════
# 5. Cohérence avec cycles existants (FK active)
# ═════════════════════════════════════════════════════════════════════════════

class TestCoherenceCycles:

    def test_les_cycles_referencees_existent(self, data_dir_avec_csv):
        """Tous les cycle_code des niveaux doivent référencer un cycle
        existant en BDD (sinon la FK aurait échoué à l'INSERT)."""
        SqliteStore(data_dir_avec_csv)
        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cycles_referencees = {r[0] for r in conn.execute(
                "SELECT DISTINCT cycle_code FROM param_niveaux"
            )}
            cycles_existants = {r[0] for r in conn.execute(
                "SELECT code FROM cycles"
            )}
        # Les cycles utilisés par les niveaux doivent tous exister
        assert cycles_referencees.issubset(cycles_existants)

    def test_fk_active_empeche_cycle_inexistant(self, data_dir_avec_csv):
        """Tentative d'INSERT avec cycle_code inexistant : doit échouer
        avec IntegrityError quand FK est ON."""
        SqliteStore(data_dir_avec_csv)
        with sqlite3.connect(data_dir_avec_csv / "seqenseigne.db") as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO param_niveaux "
                    "(code, cycle_code, annee_dans_cycle, nom_court, "
                    " nom_long, ordre) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    ("N99", "C99_INEXISTANT", "an", "X", "x", 99),
                )


# ═════════════════════════════════════════════════════════════════════════════
# 6. Cohérence avec data/param_niveaux.csv réel (smoke test)
# ═════════════════════════════════════════════════════════════════════════════

class TestCsvReel:
    """Sanity check sur le CSV réel livré dans data/. Si quelqu'un
    modifie le CSV en cassant le format, ce test le signale."""

    def test_csv_reel_se_charge_sans_erreur(self, tmp_path):
        """Le CSV livré dans appli/data/ doit pouvoir être chargé."""
        racine = Path(__file__).resolve().parent.parent
        csv_reel = racine / "data" / "param_niveaux.csv"
        if not csv_reel.exists():
            pytest.skip("data/param_niveaux.csv absent dans l'environnement de test")

        d = tmp_path / "data"
        d.mkdir()
        # Copier le CSV réel
        (d / "param_niveaux.csv").write_bytes(csv_reel.read_bytes())

        SqliteStore(d)
        with sqlite3.connect(d / "seqenseigne.db") as conn:
            conn.row_factory = sqlite3.Row
            rows = list(conn.execute(
                "SELECT code, cycle_code FROM param_niveaux ORDER BY ordre"
            ))

        # Au minimum : les 6 niveaux N07..N12, N10/N11/N12 → C04
        codes = [r["code"] for r in rows]
        assert "N10" in codes and "N11" in codes and "N12" in codes
        n10 = next(r for r in rows if r["code"] == "N10")
        assert n10["cycle_code"] == "C04"
