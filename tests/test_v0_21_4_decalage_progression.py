"""tests/test_v0_21_4_decalage_progression.py — v0.27.2

Décalages de progression par « semaines neutralisées » (algorithme §9 de
doc/spec_decalage_semaines_neutralisees.md). Un décalage neutralise des
semaines de cours ; les créneaux les enjambent (comme les vacances).
"""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore
from services import decalage_progression as dp


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


def _lundis(debut_iso, n):
    cur = date.fromisoformat(debut_iso)
    return [(cur + timedelta(days=7 * i)).isoformat() for i in range(n)]


# Calendrier de test : lundis à partir du 07/09/2026, vacances Toussaint sur
# les semaines du 19/10 et 26/10.
LUNDIS = _lundis("2026-09-07", 16)
_VAC = {"2026-10-19", "2026-10-26"}
def est_vac(l): return l in _VAC


def test_table_creee(store, tmp_path):
    con = sqlite3.connect(tmp_path / "data" / "seqenseigne.db")
    t = con.execute("SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='decalage_progression'").fetchone()
    assert t is not None


def test_cas_A_enjambement_et_cumul():
    """S03 couvre les semaines du 07 et du 14 ; décalages +1 au 11/09
    (neutralise sem 07) et +1 au 22/09 (neutralise sem 21). Attendu : S03 sur
    les semaines du 14 et du 28 (le 21 est transparent)."""
    creneaux = [{"seq_code": "S03", "date_debut": "2026-09-07",
                 "date_fin": "2026-09-18"}]
    dec = [{"a_partir_de": "2026-09-11", "nb_semaines": 1},
           {"a_partir_de": "2026-09-22", "nb_semaines": 1}]
    r = dp.appliquer_decalages(creneaux, dec, LUNDIS, est_vac)
    assert r[0]["date_debut"] == "2026-09-14"   # semaine du 14
    assert r[0]["date_fin"] == "2026-10-02"     # vendredi de la semaine du 28


def test_cas_B_creneau_apres_saute_les_vacances():
    """S05 sur la semaine du 12/10 ; décalage +1 au 22/09 (neutralise sem 21).
    S05 poussé d'une semaine de cours → semaine du 02/11 (saut Toussaint)."""
    creneaux = [{"seq_code": "S05", "date_debut": "2026-10-12",
                 "date_fin": "2026-10-16"}]
    dec = [{"a_partir_de": "2026-09-22", "nb_semaines": 1}]
    r = dp.appliquer_decalages(creneaux, dec, LUNDIS, est_vac)
    assert r[0]["date_debut"] == "2026-11-02"


def test_cas_C_creneau_avant_inchange():
    creneaux = [{"seq_code": "S01", "date_debut": "2026-09-07",
                 "date_fin": "2026-09-11"}]
    dec = [{"a_partir_de": "2026-09-22", "nb_semaines": 1}]
    r = dp.appliquer_decalages(creneaux, dec, LUNDIS, est_vac)
    assert r[0]["date_debut"] == "2026-09-07"
    assert r[0]["date_fin"] == "2026-09-11"


def test_union_semaines_neutralisees():
    """Deux décalages qui neutralisent la même semaine → union (une fois)."""
    dec = [{"a_partir_de": "2026-09-22", "nb_semaines": 1},
           {"a_partir_de": "2026-09-21", "nb_semaines": 1}]
    N = dp.semaines_neutralisees(dec, LUNDIS, est_vac)
    assert N == {"2026-09-21"}  # même semaine, comptée une fois


def test_sans_decalage_retourne_copie():
    creneaux = [{"seq_code": "S01", "date_debut": "2026-09-07",
                 "date_fin": "2026-09-11"}]
    r = dp.appliquer_decalages(creneaux, [], LUNDIS, est_vac)
    assert r == [dict(c) for c in creneaux]
    assert r[0] is not creneaux[0]
