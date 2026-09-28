"""tests/test_v0_22_0_leitner.py — v0.22.0

Ordonnancement Leitner : cadence des enveloppes (1..4) et planning ; migration
des colonnes mer_active/mer_mode.
"""
import sqlite3
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore
from services import leitner


def test_cadence_enveloppes():
    # enveloppe 1 chaque séance ; 2 une sur 2 ; 3 une sur 4 ; 4 une sur 8
    assert leitner.enveloppes_a_reviser(1) == [1]
    assert leitner.enveloppes_a_reviser(2) == [1, 2]
    assert leitner.enveloppes_a_reviser(3) == [1]
    assert leitner.enveloppes_a_reviser(4) == [1, 2, 3]
    assert leitner.enveloppes_a_reviser(8) == [1, 2, 3, 4]
    assert leitner.enveloppes_a_reviser(16) == [1, 2, 3, 4]
    assert leitner.enveloppes_a_reviser(0) == []


def test_quatre_enveloppes():
    assert leitner.NB_ENVELOPPES == 4
    # jamais d'enveloppe 5 ni 0
    for n in range(1, 40):
        env = leitner.enveloppes_a_reviser(n)
        assert all(1 <= e <= 4 for e in env)


def test_planning_enrichit():
    seances = [{"numero": 1, "date": "2026-09-07"},
               {"numero": 8, "date": "2026-09-25"}]
    p = leitner.planning(seances)
    assert p[0]["enveloppes"] == [1]
    assert p[1]["enveloppes"] == [1, 2, 3, 4]
    # non destructif : la source garde ses champs, on ajoute enveloppes
    assert p[0]["date"] == "2026-09-07"


def test_migration_colonnes_mer(tmp_path):
    SqliteStore(tmp_path / "data")
    con = sqlite3.connect(tmp_path / "data" / "seqenseigne.db")
    cols = {r[1] for r in con.execute("PRAGMA table_info(classes)")}
    assert "mer_active" in cols
    assert "mer_mode" in cols
