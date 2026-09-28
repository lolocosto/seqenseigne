"""tests/test_v0_26_0_progression_mer.py — v0.26.0

Progressions de MER à la séance : migration, projection pure (consommation des
séances par partie), CRUD (référentiel, pose/retrait/déplacement de parties,
doublon interdit).
"""
import sqlite3
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore
from services import progression_mer as pm
from services import referentiel_externe as rx


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def test_tables_creees(store, tmp_path):
    con = sqlite3.connect(tmp_path / "data" / "seqenseigne.db")
    noms = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name LIKE 'progression_mer%'")}
    assert {"progression_mer", "progression_mer_partie"} <= noms


def test_projeter_consomme_seances_dans_l_ordre():
    seances = [{"numero": i, "date": f"2026-09-{i:02d}"} for i in range(1, 13)]
    parties = [
        {"id": "a", "libelle": "Tables", "nb_seances": 6, "sequence_nom": "CM"},
        {"id": "b", "libelle": "Compléments", "nb_seances": 4, "sequence_nom": "CM"},
    ]
    r = pm.projeter_mer(seances, parties)
    # séances 1-6 = Tables, 7-10 = Compléments, 11-12 = épuisé
    assert [s["mer_libelle"] for s in r[:6]] == ["Tables"] * 6
    assert [s["mer_libelle"] for s in r[6:10]] == ["Compléments"] * 4
    assert r[10]["mer_partie_id"] is None and r[11]["mer_partie_id"] is None
    # rangs corrects
    assert r[0]["mer_rang_partie"] == 1 and r[5]["mer_rang_partie"] == 6
    assert r[6]["mer_rang_partie"] == 1


def test_projeter_liste_vide():
    seances = [{"numero": 1, "date": "2026-09-01"}]
    r = pm.projeter_mer(seances, [])
    assert r[0]["mer_partie_id"] is None


def _ref_mer_avec_parties(conn):
    ref = rx.creer(conn, niveau="N09", nom="MER")
    seq = rx.ajouter_sequence(conn, ref["id"], code="MER1", nom="Calcul mental")
    p1 = rx.ajouter_partie(conn, seq["id"], libelle="Tables", nb_seances=6)
    p2 = rx.ajouter_partie(conn, seq["id"], libelle="Compléments", nb_seances=4)
    return ref, p1["id"], p2["id"]


def test_crud_progression_et_ordre(store):
    with store._conn() as conn:
        ref, p1, p2 = _ref_mer_avec_parties(conn)
        prog = pm.creer_ou_lire(conn, "cl_x", "2026-2027")
        assert prog["etat"] == "en_cours"
        pm.definir_referentiel(conn, prog["id"], ref["id"], "externe")
        # poser 2 parties
        pm.poser_partie(conn, prog["id"], p1)
        pm.poser_partie(conn, prog["id"], p2)
        d = pm._lire(conn, prog["id"])
        assert [x["libelle"] for x in d["parties"]] == ["Tables", "Compléments"]
        # doublon interdit
        with pytest.raises(pm.DonneesInvalides):
            pm.poser_partie(conn, prog["id"], p1)
        # déplacer Compléments en tête
        pose_comp = d["parties"][1]["id"]
        d2 = pm.deplacer_partie(conn, pose_comp, -1)
        assert [x["libelle"] for x in d2["parties"]] == ["Compléments", "Tables"]
        # retirer une partie
        pm.retirer_partie(conn, d2["parties"][0]["id"])
        d3 = pm._lire(conn, prog["id"])
        assert [x["libelle"] for x in d3["parties"]] == ["Tables"]


def test_changer_referentiel_purge_parties(store):
    with store._conn() as conn:
        ref, p1, p2 = _ref_mer_avec_parties(conn)
        prog = pm.creer_ou_lire(conn, "cl_y", "2026-2027")
        pm.definir_referentiel(conn, prog["id"], ref["id"], "externe")
        pm.poser_partie(conn, prog["id"], p1)
        # autre référentiel → purge
        ref2 = rx.creer(conn, niveau="N09", nom="MER2")
        d = pm.definir_referentiel(conn, prog["id"], ref2["id"], "externe")
        assert d["parties"] == []
