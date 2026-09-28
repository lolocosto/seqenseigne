"""tests/test_v0_32_5_progression_doc.py — v0.32.5

Association de documents à la progression (au niveau) : CRUD + documents
disponibles pour une séquence (sources interne principale + externe).
"""
import pytest

from persistence.sqlite_store import SqliteStore
from services import progression_doc as pd


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def test_migration_table_presente(store):
    with store._conn() as conn:
        t = conn.execute(
            "SELECT name FROM sqlite_master WHERE name='progression_doc'"
        ).fetchone()
    assert t is not None


def test_crud_association(store):
    with store._conn() as conn:
        a = pd.ajouter(conn, prog_kind="principale", prog_ref="p1",
                       creneau_ref="c1", rang_seance=1, doc_source="interne",
                       doc_ref="livret_sequence|N11/S05", doc_libelle="L S05")
        assert a["rang_seance"] == 1
        assert pd.lister(conn, "principale", "p1") == [a] or \
            len(pd.lister(conn, "principale", "p1")) == 1
        # filtre par créneau
        assert len(pd.lister(conn, "principale", "p1", "c1")) == 1
        assert len(pd.lister(conn, "principale", "p1", "c2")) == 0
        pd.supprimer(conn, a["id"])
        assert pd.lister(conn, "principale", "p1") == []


def test_validation_prog_kind(store):
    with store._conn() as conn:
        with pytest.raises(ValueError):
            pd.ajouter(conn, prog_kind="xxx", prog_ref="p", creneau_ref="c",
                       rang_seance=1, doc_source="interne", doc_ref="x")
        with pytest.raises(ValueError):
            pd.ajouter(conn, prog_kind="mer", prog_ref="p", creneau_ref="c",
                       rang_seance=1, doc_source="xxx", doc_ref="x")


def test_ordre_incremente(store):
    with store._conn() as conn:
        a1 = pd.ajouter(conn, prog_kind="mer", prog_ref="p", creneau_ref="c",
                        rang_seance=1, doc_source="externe", doc_ref="d1")
        a2 = pd.ajouter(conn, prog_kind="mer", prog_ref="p", creneau_ref="c",
                        rang_seance=1, doc_source="externe", doc_ref="d2")
    assert a1["ordre"] == 0 and a2["ordre"] == 1
