"""tests/test_v0_30_0_tableau_bord.py — v0.30.0

Tableau de bord : agrégats des tuiles (atomes en cours par niveau, séances de
la semaine).
"""
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import tableau_bord as tb


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def _ins_notion(conn, id_, niveau, num, etat):
    conn.execute(
        "INSERT INTO notions (id, niveau, sequence, num_connaissance, titre, "
        "corps, ordre_sections, fichier, etat_code) VALUES "
        "(?,?,?,?,?,?,?,?,?)",
        (id_, niveau, "S01", num, "T", "", "", "f_" + id_, etat))


def test_atomes_en_cours_agrege_par_niveau(store):
    with store._conn() as conn:
        _ins_notion(conn, "n1", "N09", "01", "en_cours")
        _ins_notion(conn, "n2", "N09", "02", "valide")
        _ins_notion(conn, "n3", "N11", "01", "en_cours")
        conn.commit()
        data = tb.atomes_en_cours_par_niveau(conn)
    par_niv = {d["niveau"]: d for d in data}
    assert par_niv["N09"]["par_type"]["notion"] == 1  # 1 en cours (n2 validé)
    assert par_niv["N09"]["total"] == 1
    assert par_niv["N09"]["niveau_label"] == "6ème"
    assert par_niv["N11"]["total"] == 1
    # Tri par total décroissant (ici égalité, mais les deux présents).
    assert {"N09", "N11"} <= set(par_niv)


def test_atomes_tous_valides_total_zero(store):
    with store._conn() as conn:
        _ins_notion(conn, "n1", "N09", "01", "valide")
        conn.commit()
        data = tb.atomes_en_cours_par_niveau(conn)
    assert all(d["total"] == 0 for d in data)


def test_seances_semaine_structure(store):
    with store._conn() as conn:
        res = tb.seances_de_la_semaine(conn, store, "2026-2027",
                                       jour_reference=date(2026, 9, 15))
    assert res["lundi"] == "2026-09-14"
    assert res["vendredi"] == "2026-09-18"
    assert [j["jour"] for j in res["jours"]] == ["lun", "mar", "mer", "jeu", "ven"]
