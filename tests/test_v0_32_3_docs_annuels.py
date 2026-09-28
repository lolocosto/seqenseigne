"""tests/test_v0_32_3_docs_annuels.py — v0.32.3

Documents annuels des référentiels externes (rattachés au référentiel, pas à
une partie).
"""
import pytest

from persistence.sqlite_store import SqliteStore
from services import referentiel_externe as rx


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def test_ajouter_et_lister_doc_annuel(store, tmp_path):
    with store._conn() as conn:
        ref = rx.creer(conn, niveau="N09", nom="MER 6e")
        d = rx.ajouter_doc_annuel(conn, ref["id"], nom_fichier="recap.pdf",
                                  contenu=b"%PDF", mime="application/pdf",
                                  data_dir=tmp_path / "data")
        assert d["affichable"] is True
        annuels = rx.lister_docs_annuels(conn, ref["id"])
        assert len(annuels) == 1
        assert annuels[0]["nom_fichier"] == "recap.pdf"
        # exposé dans lire()
        full = rx.lire(conn, ref["id"])
        assert len(full["docs_annuels"]) == 1
        # pas rattaché à une partie
        assert full["sequences"] == []
        # fichier écrit
        assert (tmp_path / "data" / annuels[0]["chemin"]).exists()


def test_supprimer_referentiel_supprime_docs_annuels(store, tmp_path):
    with store._conn() as conn:
        ref = rx.creer(conn, niveau="N09", nom="X")
        rx.ajouter_doc_annuel(conn, ref["id"], nom_fichier="a.pdf",
                              contenu=b"%PDF", mime="application/pdf",
                              data_dir=tmp_path / "data")
        rx.supprimer(conn, ref["id"], data_dir=tmp_path / "data")
        # plus aucun doc annuel
        annuels = conn.execute(
            "SELECT COUNT(*) FROM referentiel_externe_doc WHERE ref_ext_id=?",
            (ref["id"],)).fetchone()[0]
        assert annuels == 0
