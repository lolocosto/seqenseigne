"""tests/test_v0_19_1_19_affectation.py — v0.19.1.19

Affectation des séances : fonction pure (par_seance, par_repartition,
exceptions, validation des valeurs) + persistance (mode, affectations par
créneau, motif, exceptions) + migration des tables.
"""
import sqlite3
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore
from services import affectation as aff


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def _seances():
    return [{"numero": i + 1, "date": d, "edt_creneau_id": e}
            for i, (d, e) in enumerate([
                ("2025-09-08", "lun"), ("2025-09-12", "ven"),
                ("2025-09-15", "lun"), ("2025-09-19", "ven"),
            ])]


def test_tables_creees(store, tmp_path):
    con = sqlite3.connect(tmp_path / "data" / "seqenseigne.db")
    noms = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ("affectation_config", "affectation_seance",
              "regle_repartition", "affectation_exception"):
        assert t in noms


def test_affectation_valide():
    assert aff.affectation_valide("automatisme")
    assert aff.affectation_valide("progression")
    assert aff.affectation_valide("aucun")
    assert aff.affectation_valide("mer:abc123")
    assert not aff.affectation_valide("mer:")
    assert not aff.affectation_valide("bidon")


def test_affecter_par_seance():
    r = aff.affecter(_seances(), "par_seance",
                     affectations_par_edt={"lun": "automatisme",
                                           "ven": "progression"})
    assert [s["affectation"] for s in r] == [
        "automatisme", "progression", "automatisme", "progression"]


def test_affecter_par_repartition_cyclique():
    r = aff.affecter(_seances(), "par_repartition",
                     motif=["automatisme", "automatisme", "progression"])
    # cycle de longueur 3 sur 4 séances : a, a, p, a
    assert [s["affectation"] for s in r] == [
        "automatisme", "automatisme", "progression", "automatisme"]


def test_affecter_exception_force_aucun():
    r = aff.affecter(_seances(), "par_seance",
                     affectations_par_edt={"lun": "automatisme"},
                     exceptions={"2025-09-15"})
    d = {s["date"]: s["affectation"] for s in r}
    assert d["2025-09-08"] == "automatisme"
    assert d["2025-09-15"] == "aucun"


def test_par_seance_defaut_aucun():
    # créneau non affecté => aucun
    r = aff.affecter(_seances(), "par_seance", affectations_par_edt={})
    assert all(s["affectation"] == "aucun" for s in r)


def test_persistance_mode_et_affectations(store):
    with store._conn() as conn:
        assert aff.lire_mode(conn, "cl_x", "2025-2026") == "par_seance"
        aff.definir_mode(conn, "cl_x", "2025-2026", "par_repartition")
        assert aff.lire_mode(conn, "cl_x", "2025-2026") == "par_repartition"
        with pytest.raises(aff.DonneesInvalides):
            aff.definir_mode(conn, "cl_x", "2025-2026", "zzz")
        # affectations : upsert + 'aucun' supprime
        aff.definir_affectations(conn, "cl_x", "2025-2026",
                                 [{"edt_creneau_id": "e1",
                                   "affectation": "automatisme"}])
        assert aff.lire_affectations(conn, "cl_x", "2025-2026") == {
            "e1": "automatisme"}
        aff.definir_affectations(conn, "cl_x", "2025-2026",
                                 [{"edt_creneau_id": "e1",
                                   "affectation": "aucun"}])
        assert aff.lire_affectations(conn, "cl_x", "2025-2026") == {}


def test_persistance_motif_et_exceptions(store):
    with store._conn() as conn:
        aff.definir_motif(conn, "cl_y", "2025-2026",
                          ["automatisme", "progression"])
        assert aff.lire_motif(conn, "cl_y", "2025-2026") == [
            "automatisme", "progression"]
        with pytest.raises(aff.DonneesInvalides):
            aff.definir_motif(conn, "cl_y", "2025-2026", ["bidon"])
        ex = aff.ajouter_exception(conn, "cl_y", "2025-2026", "2025-09-15",
                                   "éval")
        assert aff.dates_exceptions(conn, "cl_y", "2025-2026") == {
            "2025-09-15"}
        aff.supprimer_exception(conn, ex["id"])
        assert aff.dates_exceptions(conn, "cl_y", "2025-2026") == set()
