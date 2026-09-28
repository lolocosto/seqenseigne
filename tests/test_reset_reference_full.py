"""
tests/test_reset_reference_full.py — Test de non-régression pour
`SqliteStore.reset_reference()`.

Contexte
--------
Reproduit le bug rencontré le 23 avril 2026 : la méthode ne vidait pas
toutes les tables filles des atomes (notamment `objectif_exos` qui a
un FK RESTRICT vers `exercices`), ce qui provoquait une
`IntegrityError` dès qu'une vraie base peuplée était réinitialisée.

Stratégie du test : construire une base contenant des données dans
toutes les tables de référence liées aux atomes pédagogiques, puis
appeler `reset_reference` et vérifier :
  1. aucune exception
  2. toutes les tables de référence sont vides
  3. les tables « référentiels stables » (cycles, themes,
     referentiel_*) sont inchangées

Le peuplement se fait ici par SQL direct pour éviter toute dépendance
envers les autres helpers Python, et surtout pour ne tester qu'une
chose : que `reset_reference` vide correctement, indépendamment de
comment les données arrivent en base.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

# v0.7 — Tests adaptés au modèle universel à 2 niveaux
# (atome_sections + atome_section_items remplacent items_texte).

from persistence.sqlite_store import SqliteStore


@pytest.fixture
def store_peuple():
    """
    Crée une base SQLite neuve et y insère une ligne dans les tables
    susceptibles de poser problème au reset. Utilise des insertions
    SQL minimales (seulement les colonnes NOT NULL) pour être
    robuste aux évolutions de schéma.

    Attention : `objectif_exos.objectif_id` référence `objectifs(id)`
    (pas `objectifs(id)`). La chaîne FK est donc :
    `sequences_par_niveau` → `sequence_parties` → `objectifs`
    → `objectif_exos`.
    """
    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteStore(Path(tmp))
        with store._conn() as conn:
            # ── Tables principales (atomes) ──────────────────────────
            conn.execute(
                "INSERT INTO exercices (id, serie) VALUES ('e1', 'fondamental')"
            )
            conn.execute("INSERT INTO notions (id) VALUES ('n1')")
            conn.execute("INSERT INTO methodes (id) VALUES ('m1')")
            # v0.14.6.b.2 — INSERT INTO objectifs (v1) retiré.
            conn.execute(
                "INSERT INTO livrets_de_sequence (id, niveau, sequence) "
                "VALUES ('l1', 'N11', 'S01')"
            )

            # ── Chaîne séquence_parties → objectifs ──────────────
            conn.execute(
                "INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
                "VALUES ('spn1', 'N11', 'S01')"
            )
            conn.execute(
                "INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
                "VALUES ('sp1', 'spn1', 1)"
            )
            conn.execute(
                "INSERT INTO objectifs (id, partie_id, code, methode_id) "
                "VALUES ('o2_1', 'sp1', '02', 'm1')"
            )

            # ── Tables filles (celles qui posaient problème au reset) ─
            # v0.14.6.b.2 — INSERT INTO exercice_objectifs (v1) retiré.
            conn.execute(
                "INSERT INTO objectif_exos "
                "(objectif_id, serie, exercice_id, ordre) "
                "VALUES ('o2_1', 'F', 'e1', 1)"
            )
            # v0.14.6.b.2 — INSERT INTO livret_exercices retiré (table
            # supprimée).
            conn.execute(
                "INSERT INTO livret_revisions "
                "(livret_id, niveau_source, seq_source, serie, num, ordre) "
                "VALUES ('l1', 'N10', 'S01', 'fondamental', 1, 1)"
            )
            conn.execute(
                "INSERT INTO methode_notions (methode_id, notion_id) "
                "VALUES ('m1', 'n1')"
            )
            # v0.7 : modèle universel à 2 niveaux. Une section "Exemples"
            # avec un item, attachée à n1 (notion).
            conn.execute(
                "INSERT INTO atome_sections (id, entite_type, entite_id, "
                "titre, ordre) VALUES "
                "('sec1', 'notion', 'n1', 'Exemples', 0)"
            )
            conn.execute(
                "INSERT INTO atome_section_items (id, section_id, "
                "ordre, corps) VALUES "
                "('it1', 'sec1', 0, 'ex.')"
            )
        yield store


def test_reset_reference_ne_leve_pas_dintegrityerror(store_peuple):
    """Garde-fou : le bug initial était une IntegrityError sur la FK
    RESTRICT entre objectif_exos et exercices. On veut que cela ne se
    reproduise plus."""
    vides = store_peuple.reset_reference()
    assert isinstance(vides, list)
    assert "exercices" in vides
    assert "objectif_exos" in vides


def test_reset_reference_vide_bien_objectif_exos(store_peuple):
    """Test spécifique de la FK qui bloquait : `objectif_exos` doit
    être vidée avant `exercices` pour respecter la contrainte
    RESTRICT."""
    with store_peuple._conn() as conn:
        n_before = conn.execute("SELECT COUNT(*) FROM objectif_exos").fetchone()[0]
    assert n_before == 1

    store_peuple.reset_reference()

    with store_peuple._conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM objectif_exos").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM exercices").fetchone()[0] == 0


def test_reset_reference_vide_toutes_les_tables_regenerees(store_peuple):
    """Toutes les tables d'atomes et leurs tables filles doivent être
    vidées."""
    store_peuple.reset_reference()

    with store_peuple._conn() as conn:
        tables_a_vider = [
            # v0.14.6.b.2 — `objectifs`, `exercice_objectifs` et
            # `livret_exercices` retirées de la liste : tables supprimées.
            "notions", "methodes", "exercices",
            "livrets_de_sequence",
            # v0.7 : items_texte remplacé par atome_sections + atome_section_items.
            "atome_sections", "atome_section_items",
            "methode_notions",
            "objectif_exos", "livret_revisions",
        ]
        for t in tables_a_vider:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            assert n == 0, f"{t} contient encore {n} lignes après reset"


def test_reset_reference_preserve_les_referentiels_stables(store_peuple):
    """Les tables de référentiels (cycles, themes) ne doivent pas être
    vidées : elles sont peuplées par un autre import, indépendant du
    scan des atomes."""
    with store_peuple._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO cycles (code, nom) VALUES ('C04', 'Cycle 4')")
        conn.execute(
            "INSERT OR IGNORE INTO themes "
            "(id, cycle_code, code, nom, code_couleur) "
            "VALUES ('t1', 'C04', 'A', 'Nombres', 'nombres')"
        )

    store_peuple.reset_reference()

    with store_peuple._conn() as conn:
        n_cycles = conn.execute("SELECT COUNT(*) FROM cycles").fetchone()[0]
        n_themes = conn.execute("SELECT COUNT(*) FROM themes").fetchone()[0]
        assert n_cycles >= 1, "cycles a été vidé à tort"
        assert n_themes >= 1, "themes a été vidé à tort"


def test_reset_reference_preserve_classes_et_etablissements(store_peuple):
    """Les tables de suivi (classes, étab.) ne doivent pas être
    touchées par `reset_reference`."""
    with store_peuple._conn() as conn:
        conn.execute("INSERT INTO etablissements (id, nom) VALUES ('et1', 'Test')")
        conn.execute(
            "INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
            "VALUES ('cl1', '4e1', 'N11', '2025-2026', 'et1')"
        )

    store_peuple.reset_reference()

    with store_peuple._conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM etablissements").fetchone()[0] == 1

