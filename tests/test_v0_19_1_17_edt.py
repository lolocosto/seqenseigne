"""tests/test_v0_19_1_17_edt.py — v0.19.1.17

Emploi du temps de l'enseignant : migration, CRUD, validations (jour/semaine/
usage, créneau présent dans la grille, unicité), comptage des séances/semaine
dérivé (AB compte pour A et B ; seul classe_entiere est compté), et garde de
cohérence (un créneau de grille référencé par l'EDT ne peut être supprimé).
"""
import sqlite3
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt
from services import grille_horaire as gh


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def _etab(store, eid="et_test"):
    with store._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO etablissements (id, nom, etat) "
                     "VALUES (?,?, 'propose')", (eid, "Test"))
        gh.peupler_defauts_si_vide(conn, eid)
    return eid


def test_table_creee(store, tmp_path):
    con = sqlite3.connect(tmp_path / "data" / "seqenseigne.db")
    t = con.execute("SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='edt_creneaux'").fetchone()
    assert t is not None


def test_ajout_et_validations(store):
    eid = _etab(store)
    with store._conn() as conn:
        c = edt.ajouter(conn, "2025-2026", "lun", "M1", eid)
        assert c["semaine"] == "AB" and c["usage"] == "cours" and c["groupe"] == "classe_entiere"
        # jour invalide
        with pytest.raises(edt.DonneesInvalides):
            edt.ajouter(conn, "2025-2026", "xxx", "M1", eid)
        # semaine invalide
        with pytest.raises(edt.DonneesInvalides):
            edt.ajouter(conn, "2025-2026", "mar", "M2", eid, semaine="C")
        # usage invalide
        with pytest.raises(edt.DonneesInvalides):
            edt.ajouter(conn, "2025-2026", "mar", "M2", eid, usage="zzz")
        # créneau hors grille
        with pytest.raises(edt.DonneesInvalides):
            edt.ajouter(conn, "2025-2026", "mar", "Z9", eid)
        # doublon
        with pytest.raises(edt.DonneesInvalides):
            edt.ajouter(conn, "2025-2026", "lun", "M1", eid)


def test_comptage_seances_AB(store):
    eid = _etab(store)
    with store._conn() as conn:
        cid = "cl_x"
        edt.ajouter(conn, "2025-2026", "lun", "M1", eid, semaine="AB",
                    classe_id=cid, usage="cours")
        edt.ajouter(conn, "2025-2026", "mar", "M1", eid, semaine="A",
                    classe_id=cid, usage="cours")
        edt.ajouter(conn, "2025-2026", "jeu", "M3", eid, semaine="AB",
                    classe_id=cid, usage="vie_de_classe")  # non compté
        compte = edt.compter_seances(conn, cid, "2025-2026")
    # AB (1) + A (1) => A=2 ; AB (1) => B=1 ; le 'autre' n'est pas compté
    assert compte == {"A": 2, "B": 1}


def test_usage_non_compte_exclu(store):
    eid = _etab(store)
    with store._conn() as conn:
        cid = "cl_y"
        edt.ajouter(conn, "2025-2026", "lun", "M1", eid, semaine="AB",
                    classe_id=cid, groupe="demi_classe_A", usage="cours")
        compte = edt.compter_seances(conn, cid, "2025-2026")
    assert compte == {"A": 0, "B": 0}  # demi_classe pas encore comptée


def test_grille_protegee_si_referencee(store):
    eid = _etab(store)
    with store._conn() as conn:
        edt.ajouter(conn, "2025-2026", "lun", "M1", eid)
        m1 = [x for x in gh.lister(conn, eid) if x["code"] == "M1"][0]
        with pytest.raises(gh.DonneesInvalides):
            gh.supprimer(conn, m1["id"])
        # un créneau non référencé se supprime normalement
        s4 = [x for x in gh.lister(conn, eid) if x["code"] == "S4"][0]
        gh.supprimer(conn, s4["id"])
        assert all(x["code"] != "S4" for x in gh.lister(conn, eid))


def test_modifier_et_supprimer(store):
    eid = _etab(store)
    with store._conn() as conn:
        c = edt.ajouter(conn, "2025-2026", "ven", "S1", eid, semaine="A")
        m = edt.modifier(conn, c["id"], {"usage": "autre", "libelle": "Vie de classe"})
        assert m["usage"] == "autre" and m["libelle"] == "Vie de classe"
        edt.supprimer(conn, c["id"])
        with pytest.raises(edt.CreneauEdtIntrouvable):
            edt.supprimer(conn, c["id"])


def test_coherence_AB_vs_A_B(store):
    """Un créneau ne peut mélanger 'AB' (toutes semaines) et 'A'/'B'."""
    eid = _etab(store)
    with store._conn() as conn:
        edt.ajouter(conn, "2025-2026", "lun", "M1", eid, semaine="AB")
        # AB déjà là → ajouter A doit échouer
        with pytest.raises(edt.DonneesInvalides):
            edt.ajouter(conn, "2025-2026", "lun", "M1", eid, semaine="A")
        # sur un autre créneau : A puis B OK, puis AB refusé
        edt.ajouter(conn, "2025-2026", "mar", "M2", eid, semaine="A")
        edt.ajouter(conn, "2025-2026", "mar", "M2", eid, semaine="B")
        with pytest.raises(edt.DonneesInvalides):
            edt.ajouter(conn, "2025-2026", "mar", "M2", eid, semaine="AB")
