"""tests/test_v0_30_2_toutes_sequences.py — v0.30.2

Mode « toutes les séquences » des ateliers d'atomes : lister_atomes_sequence
avec séquence vide renvoie tous les atomes du niveau, chacun portant sa
séquence ; une séquence précise garde le comportement historique.
"""
import pytest

from persistence.sqlite_store import SqliteStore
from services.atomes_liste import lister_atomes_sequence


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def _ins_notion(conn, id_, niveau, seq, num, etat="en_cours"):
    conn.execute(
        "INSERT INTO notions (id, niveau, sequence, num_connaissance, titre, "
        "corps, ordre_sections, fichier, etat_code) VALUES (?,?,?,?,?,?,?,?,?)",
        (id_, niveau, seq, num, "T", "", "", "f_" + id_, etat))


def test_une_sequence(store):
    with store._conn() as conn:
        _ins_notion(conn, "n1", "N09", "S01", "01")
        _ins_notion(conn, "n2", "N09", "S02", "01")
        conn.commit()
        r = lister_atomes_sequence(conn, "notion", "N09", "S01")
    assert len(r) == 1
    assert r[0]["sequence"] == "S01"


def test_toutes_sequences(store):
    with store._conn() as conn:
        _ins_notion(conn, "n1", "N09", "S01", "01")
        _ins_notion(conn, "n2", "N09", "S02", "01")
        _ins_notion(conn, "n3", "N11", "S01", "01")  # autre niveau, exclu
        conn.commit()
        r = lister_atomes_sequence(conn, "notion", "N09", "")
    assert len(r) == 2                       # les 2 séquences du niveau N09
    seqs = {a["sequence"] for a in r}
    assert seqs == {"S01", "S02"}            # chaque atome porte sa séquence


def test_niveau_obligatoire(store):
    with store._conn() as conn:
        with pytest.raises(ValueError):
            lister_atomes_sequence(conn, "notion", "", "")
