"""tests/test_v0_21_0_indisponibilites.py — v0.21.0

Indisponibilités : migration de la table, fonction pure de filtrage (types
seances/journees, portées moi/classes), intégration dans projeter (décalage),
et persistance (CRUD + validations).
"""
import sqlite3
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore
from services import indisponibilites as ind
from services.projection_seances import projeter


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


GRILLE = [
    {"code": "M1", "ordre": 10, "heure_debut": "08:25", "heure_fin": "09:20"},
    {"code": "S1", "ordre": 50, "heure_debut": "12:55", "heure_fin": "13:50"},
    {"code": "S2", "ordre": 60, "heure_debut": "13:55", "heure_fin": "14:50"},
    {"code": "S3", "ordre": 70, "heure_debut": "15:05", "heure_fin": "16:00"},
]
VAC = [{"start_date": "2025-08-01", "end_date": "2025-09-01"}]


def test_table_creee(store, tmp_path):
    con = sqlite3.connect(tmp_path / "data" / "seqenseigne.db")
    t = con.execute("SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='indisponibilites'").fetchone()
    assert t is not None


def test_concerne_journees_et_portee_moi():
    ordre = {g["code"]: g["ordre"] for g in GRILLE}
    ind_j = {"type": "journees", "date_debut": "2025-09-09",
             "date_fin": "2025-09-11", "portee": "moi", "classes_ids": []}
    s = {"date": "2025-09-10", "creneau_code": "M1"}
    assert ind.concerne_seance(ind_j, s, "cA", ordre)
    s2 = {"date": "2025-09-12", "creneau_code": "M1"}
    assert not ind.concerne_seance(ind_j, s2, "cA", ordre)


def test_concerne_seances_plage_creneaux():
    ordre = {g["code"]: g["ordre"] for g in GRILLE}
    ind_s = {"type": "seances", "date_debut": "2025-09-08",
             "date_fin": "2025-09-08", "creneau_debut": "S1",
             "creneau_fin": "S3", "portee": "moi", "classes_ids": []}
    # S2 est dans [S1, S3] ce jour → concerné
    assert ind.concerne_seance(ind_s, {"date": "2025-09-08",
                                       "creneau_code": "S2"}, "cA", ordre)
    # M1 est avant S1 → non concerné
    assert not ind.concerne_seance(ind_s, {"date": "2025-09-08",
                                           "creneau_code": "M1"}, "cA", ordre)
    # autre jour → non concerné
    assert not ind.concerne_seance(ind_s, {"date": "2025-09-15",
                                           "creneau_code": "S2"}, "cA", ordre)


def test_portee_classes():
    ordre = {g["code"]: g["ordre"] for g in GRILLE}
    ind_c = {"type": "journees", "date_debut": "2025-09-10",
             "date_fin": "2025-09-10", "portee": "classes",
             "classes_ids": ["cB"]}
    s = {"date": "2025-09-10", "creneau_code": "M1"}
    assert not ind.concerne_seance(ind_c, s, "cA", ordre)  # cA non listée
    assert ind.concerne_seance(ind_c, s, "cB", ordre)      # cB listée


def test_projection_retire_et_decale():
    edt = [{"jour": "mar", "creneau_code": "M1", "semaine": "AB", "id": "e1"},
           {"jour": "jeu", "creneau_code": "S2", "semaine": "AB", "id": "e2"}]
    s0 = projeter("2025-2026", edt, GRILLE, VAC, {}, date_min="2025-09-01")
    n0 = len(s0)
    # indispo journées couvrant le 1er mardi et jeudi projetés
    indispos = [{"type": "journees", "date_debut": "2025-09-09",
                 "date_fin": "2025-09-11", "portee": "moi", "classes_ids": []}]
    s1 = projeter("2025-2026", edt, GRILLE, VAC, {}, date_min="2025-09-01",
                  indisponibilites=indispos, classe_id="cA")
    assert len(s1) == n0 - 2  # 2 séances retirées
    # numérotation continue sans trou
    assert [s["numero"] for s in s1] == list(range(1, len(s1) + 1))
    # aucune séance restante dans la période d'indispo
    assert not any("2025-09-09" <= s["date"] <= "2025-09-11" for s in s1)


def test_crud_et_validations(store):
    with store._conn() as conn:
        conn.execute("INSERT OR IGNORE INTO etablissements (id, nom, etat) "
                     "VALUES ('etX','Test','propose')")
        it = ind.creer(conn, "2025-2026", "etX", type="journees",
                       date_debut="2025-09-22", motif="Sortie")
        assert it["date_fin"] == "2025-09-22"  # fin = début par défaut
        # type seances sans créneaux → invalide
        with pytest.raises(ind.DonneesInvalides):
            ind.creer(conn, "2025-2026", "etX", type="seances",
                      date_debut="2025-09-11")
        # portée classes sans classe → invalide
        with pytest.raises(ind.DonneesInvalides):
            ind.creer(conn, "2025-2026", "etX", type="journees",
                      date_debut="2025-10-01", portee="classes")
        lst = ind.lister(conn, "2025-2026", etablissement_id="etX")
        assert len(lst) == 1
        ind.supprimer(conn, it["id"])
        assert ind.lister(conn, "2025-2026", etablissement_id="etX") == []
