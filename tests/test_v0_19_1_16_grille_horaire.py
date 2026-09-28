"""tests/test_v0_19_1_16_grille_horaire.py — v0.19.1.16

Grille horaire par établissement : migration de la table, peuplement des 8
créneaux par défaut (idempotent), et CRUD du service (création, unicité du
code, modification, suppression, validation des heures).
"""
import sqlite3
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore
from services import grille_horaire as gh


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def _etab(store, eid="et_test", nom="Test"):
    with store._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO etablissements (id, nom, etat) "
                     "VALUES (?,?, 'propose')", (eid, nom))
    return eid


def test_table_creee(store, tmp_path):
    con = sqlite3.connect(tmp_path / "data" / "seqenseigne.db")
    t = con.execute("SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='grille_horaire_creneaux'").fetchone()
    assert t is not None


def test_defauts_8_creneaux():
    d = gh.defauts()
    assert len(d) == 8
    codes = [x["code"] for x in d]
    assert codes == ["M1", "M2", "M3", "M4", "S1", "S2", "S3", "S4"]
    # Horaires Hautes Ourmes vérifiés sur deux bornes
    m1 = d[0]
    assert m1["heure_debut"] == "08:25" and m1["heure_fin"] == "09:20"
    s1 = d[4]
    assert s1["heure_debut"] == "12:55" and s1["heure_fin"] == "13:50"


def test_peupler_defauts_idempotent(store):
    eid = _etab(store)
    with store._conn() as conn:
        n1 = gh.peupler_defauts_si_vide(conn, eid)
        n2 = gh.peupler_defauts_si_vide(conn, eid)  # 2e appel : rien
        items = gh.lister(conn, eid)
    assert n1 == 8
    assert n2 == 0
    assert len(items) == 8


def test_creer_et_unicite(store):
    eid = _etab(store)
    with store._conn() as conn:
        gh.peupler_defauts_si_vide(conn, eid)
        c = gh.creer(conn, eid, "S5", heure_debut="17:05", heure_fin="18:00",
                     demi_journee="S")
        assert c["code"] == "S5" and c["demi_journee"] == "S"
        with pytest.raises(gh.DonneesInvalides):
            gh.creer(conn, eid, "M1")  # doublon


def test_modifier_et_supprimer(store):
    eid = _etab(store)
    with store._conn() as conn:
        gh.peupler_defauts_si_vide(conn, eid)
        s1 = [x for x in gh.lister(conn, eid) if x["code"] == "S1"][0]
        m = gh.modifier(conn, s1["id"], {"heure_fin": "14:25"})
        assert m["heure_fin"] == "14:25"
        gh.supprimer(conn, s1["id"])
        assert all(x["code"] != "S1" for x in gh.lister(conn, eid))
        with pytest.raises(gh.CreneauIntrouvable):
            gh.supprimer(conn, "gh_inexistant")


def test_heure_invalide_rejetee(store):
    eid = _etab(store)
    with store._conn() as conn:
        with pytest.raises(gh.DonneesInvalides):
            gh.creer(conn, eid, "X1", heure_debut="25:00")
