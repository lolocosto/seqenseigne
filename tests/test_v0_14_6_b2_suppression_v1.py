"""Tests v0.14.6.b.2 — Suppression effective des tables v1.

Cette livraison supprime définitivement les 3 tables v1 résiduelles
(`objectifs`, `exercice_objectifs`, `livret_exercices`), ainsi que la
colonne `niveaux.objectif_id` (FK orpheline vers `objectifs(id)`).

Elle supprime également les fichiers de code et de tests devenus
inutiles :

  Code de prod :
    - services/scanner_vers_v2.py
    - services/edition_progression.py (stub depuis b.1)
    - importers/scanner_plan_de_travail.py
    - routes/peuplement_v2.py
    - scripts/peuplement_03_deduire_liaisons.py
    - scripts/peuplement_04_appliquer_liaisons.py
    - scripts/peuplement_05_plans_de_travail.py
    - scripts/peuplement_06_resoudre_liaisons_interactif.py
    - scripts/peuplement_13_v2_depuis_base.py
    - scripts/peuplement_15_fin_cycle_vers_objectifs.py

  Tests :
    - test_R4b_routes.py
    - test_R4b_scanner_vers_v2.py
    - test_R4e1fix_premier_chiffre.py
    - test_peuplement_15_fin_cycle.py
    - test_peuplement_liaisons.py
    - test_peuplement_plans_de_travail.py

Ces tests valident l'état final : tables absentes, fichiers absents,
chaînes de code nettoyées.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def store_migre(tmp_path):
    """Store SQLite avec schéma post-b.2 appliqué."""
    from persistence.sqlite_store import SqliteStore
    from scripts.peuplement_01_migrer_schema import migrer

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    store = SqliteStore(data_dir)
    migrer(data_dir / "seqenseigne.db")
    return store


# ── 1. Tables v1 absentes du schéma ──────────────────────────────────

class TestTablesV1Absentes:
    """v0.14.6.b.2 — Sur une base fraîche, les 3 tables v1
    (`exercice_objectifs`, `livret_exercices`, et l'ancienne table
    `objectifs` v1 désormais entièrement supprimée) ne doivent plus
    apparaître dans le schéma.

    v0.14.7 — La table `objectifs_v2` a été renommée en `objectifs`.
    L'assertion "`objectifs` est absente" n'a donc plus de sens : la
    table existe sous ce nom (c'est l'ex-`objectifs_v2`). Les tests
    correspondants vivent maintenant dans `test_v0_14_7_renommage.py`.
    """

    def test_exercice_objectifs_absente(self, store_migre):
        with store_migre._conn() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='exercice_objectifs'"
            ).fetchone()
        assert row is None

    def test_livret_exercices_absente(self, store_migre):
        with store_migre._conn() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='livret_exercices'"
            ).fetchone()
        assert row is None

    # v0.14.7 — test_objectifs_absente et test_objectifs_v2_present
    # remplacés par les tests équivalents dans test_v0_14_7_renommage.py.


# ── 2. Colonne niveaux.objectif_id retirée ────────────────────────────

class TestColonneObjectifIdRetiree:
    """v0.14.6.b.2 — La colonne `niveaux.objectif_id` était une FK
    orpheline vers `objectifs(id)`. Sa suppression est nécessaire pour
    que les INSERT dans `niveaux` continuent à fonctionner après le DROP
    de `objectifs` (PRAGMA foreign_keys=ON).
    """

    def test_colonne_absente(self, store_migre):
        with store_migre._conn() as conn:
            cols = {r["name"] for r in conn.execute(
                "PRAGMA table_info(niveaux)"
            ).fetchall()}
        assert "objectif_id" not in cols

    def test_colonnes_attendues_presentes(self, store_migre):
        """Les autres colonnes de `niveaux` sont préservées."""
        with store_migre._conn() as conn:
            cols = {r["name"] for r in conn.execute(
                "PRAGMA table_info(niveaux)"
            ).fetchall()}
        attendues = {"classe_id", "seq_code", "eleve_id", "obj_code",
                     "creneau_id", "niveau_code"}
        for col in attendues:
            assert col in cols, f"Colonne {col} manquante"


# ── 3. INSERT dans niveaux fonctionne après DROP ─────────────────────

class TestInsertNiveauxApresDrop:
    """v0.14.6.b.2 — Régression : sans cette suppression de colonne,
    un INSERT dans `niveaux` aurait planté avec `no such table: objectifs`
    sur une base post-DROP (sous PRAGMA foreign_keys=ON).
    """

    def test_insert_avec_foreign_keys_on(self, store_migre):
        with store_migre._conn() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            # Pas besoin d'un objectif préalable (la FK n'existe plus).
            conn.execute(
                "INSERT INTO niveaux "
                "(classe_id, seq_code, eleve_id, obj_code, niveau_code) "
                "VALUES ('cl1', 'S01', 'e1', '02', '3')"
            )
            conn.commit()
            n = conn.execute(
                "SELECT COUNT(*) FROM niveaux WHERE classe_id='cl1'"
            ).fetchone()[0]
        assert n == 1


# ── 4. Fichiers de code supprimés ─────────────────────────────────────

class TestFichiersCodeSupprimes:
    """v0.14.6.b.2 — Les fichiers liés à la chaîne v1 ont disparu."""

    APPLI = Path(__file__).resolve().parent.parent

    @pytest.mark.parametrize("chemin", [
        "services/scanner_vers_v2.py",
        "services/edition_progression.py",
        "importers/scanner_plan_de_travail.py",
        "routes/peuplement_v2.py",
        "scripts/peuplement_03_deduire_liaisons.py",
        "scripts/peuplement_04_appliquer_liaisons.py",
        "scripts/peuplement_05_plans_de_travail.py",
        "scripts/peuplement_06_resoudre_liaisons_interactif.py",
        "scripts/peuplement_13_v2_depuis_base.py",
        "scripts/peuplement_15_fin_cycle_vers_objectifs.py",
    ])
    def test_fichier_absent(self, chemin):
        assert not (self.APPLI / chemin).exists(), (
            f"Le fichier {chemin} doit avoir été supprimé en v0.14.6.b.2"
        )


# ── 5. Imports inopérants ─────────────────────────────────────────────

class TestImportsInoperants:
    """v0.14.6.b.2 — Les imports des modules supprimés doivent échouer
    nettement (et non lever silencieusement avec un module incomplet).
    """

    def test_scanner_vers_v2_non_importable(self):
        with pytest.raises(ImportError):
            from services import scanner_vers_v2  # noqa: F401

    def test_edition_progression_non_importable(self):
        with pytest.raises(ImportError):
            from services import edition_progression  # noqa: F401

    def test_scanner_plan_de_travail_non_importable(self):
        with pytest.raises(ImportError):
            from importers import scanner_plan_de_travail  # noqa: F401


# ── 6. Routes /api/admin/v2/* supprimées ──────────────────────────────

class TestRoutesPeuplementV2Supprimees:
    """v0.14.6.b.2 — Les endpoints POST /api/admin/v2/peupler et
    GET /api/admin/v2/statistiques ont été retirés (blueprint
    `bp_peuplement_v2` désenregistré dans app.py).
    """

    @pytest.fixture
    def client(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        for f in ["notions.json", "methodes.json", "exercices.json",
                  "livrets_importes.json"]:
            (data_dir / f).write_text(
                '{"' + f.replace('.json', '').replace('importes', 's') + '": []}',
                encoding="utf-8"
            )
        from app import create_app
        app = create_app(data_dir=data_dir)
        app.config["TESTING"] = True
        return app.test_client()

    def test_post_peupler_renvoie_404(self, client):
        r = client.post("/api/admin/v2/peupler", json={})
        assert r.status_code == 404

    def test_get_statistiques_renvoie_404(self, client):
        r = client.get("/api/admin/v2/statistiques")
        assert r.status_code == 404


# ── 7. scanner_latex ne tente plus l'étape v2 ─────────────────────────

class TestScannerLatexSansEtapeV2:
    """v0.14.6.b.2 — L'étape 4 (peuplement v2) a été retirée de
    `scanner_vers_bdd`. Le rapport ne contient plus la clé 'v2'.
    """

    def test_pas_de_helper_peupler_v2(self):
        from importers import scanner_latex
        # Le helper interne _peupler_v2 a été retiré
        assert not hasattr(scanner_latex, "_peupler_v2"), (
            "Le helper interne `_peupler_v2` doit avoir disparu de "
            "importers/scanner_latex.py"
        )


# ── 8. Script supprimer_v1.py ──────────────────────────────────────────
#
# v0.15.5 — La classe `TestScriptSupprimerV1` a été retirée en même temps
# que `scripts/supprimer_v1.py`. Ce script one-shot avait fini son office :
# la table `exercice_objectifs` et les autres structures v1 sont supprimées
# du schéma ET de la BDD de production depuis v0.14.6.b.2. Les tests
# `TestTablesV1Absentes` / `TestColonneObjectifIdRetiree` ci-dessus
# continuent de vérifier l'absence des structures v1 via `peuplement_01`,
# sans dépendre du script supprimé.

