"""tests/test_v0_32_0_planification_hebdo.py — v0.32.0

Vue « Planification hebdo » : bornes de semaine, détail d'une séance (séquence
principale via la progression réalisée).
"""
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import planification_hebdo as ph


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def test_semaine_bornes_lundi_vendredi():
    # 2026-09-16 est un mercredi -> lundi 14, vendredi 18.
    s = ph.semaine_de("2026-2027", "2026-09-16")
    assert s["lundi"] == "2026-09-14"
    assert s["vendredi"] == "2026-09-18"
    assert len(s["jours"]) == 5


def test_semaine_defaut_sans_lundi():
    s = ph.semaine_de("2026-2027", None)
    # lundi de la semaine du jour, vendredi = lundi + 4.
    lundi = date.fromisoformat(s["lundi"])
    assert lundi.weekday() == 0
    assert (date.fromisoformat(s["vendredi"]) - lundi).days == 4


def test_grille_structure(store):
    with store._conn() as conn:
        g = ph.grille_semaine(conn, store, "2026-2027", "2026-09-14")
    assert "cases" in g and "creneaux" in g
    assert g["lundi"] == "2026-09-14"
    # base vide : pas de classe -> pas de cases (mais structure présente)
    assert isinstance(g["cases"], list)
