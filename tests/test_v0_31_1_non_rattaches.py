"""tests/test_v0_31_1_non_rattaches.py — v0.31.1

Tuile « Éléments non rattachés » : comptage par niveau/type des atomes non liés
à un objectif.
"""
import pytest

from persistence.sqlite_store import SqliteStore
from services import tableau_bord as tb


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def _ins_notion(conn, id_, niveau, num):
    conn.execute(
        "INSERT INTO notions (id, niveau, sequence, num_connaissance, titre, "
        "corps, ordre_sections, fichier, etat_code) VALUES "
        "(?,?,?,?,?,?,?,?,?)",
        (id_, niveau, "S01", num, "T", "", "", "f_" + id_, "valide"))


def test_comptage_non_rattaches(store):
    with store._conn() as conn:
        # 2 notions N09, aucune rattachée (pas de lien objectif_notions).
        _ins_notion(conn, "n1", "N09", "01")
        _ins_notion(conn, "n2", "N09", "02")
        conn.commit()
        data = tb.atomes_non_rattaches_par_niveau(conn)
    par_niv = {d["niveau"]: d for d in data}
    assert "N09" in par_niv
    assert par_niv["N09"]["par_type"].get("notion") == 2
    assert par_niv["N09"]["total"] >= 2
    assert par_niv["N09"]["niveau_label"] == "6ème"


def test_tout_rattache_absent(store):
    # Base vide : aucun niveau ne remonte (aucun atome non rattaché).
    with store._conn() as conn:
        data = tb.atomes_non_rattaches_par_niveau(conn)
    assert all(d["total"] > 0 for d in data)  # jamais de total 0 dans le retour
