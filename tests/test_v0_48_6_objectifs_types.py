"""tests/test_v0_48_6_objectifs_types.py — v0.48.6

Objectifs typés des référentiels principaux externes : « connaissance »
(un seul par partie, toujours en 1re position, nom et critères pré-remplis
depuis les préférences) et « capacité ».
"""
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import referentiel_principal_externe as rpe

AUJ = date(2026, 9, 1)


@pytest.fixture
def ref(tmp_path):
    st = SqliteStore(tmp_path / "data")
    with st._conn() as c:
        rid = rpe.creer(c, "N11", "2026-2027")["id"]
        rpe.ajouter_sequence(c, rid, "Nombres")
        rpe.ajouter_partie(c, rid, "S01", 4, AUJ)
    return st, rid


def _objs(c, rid):
    s = rpe.lire(c, rid, AUJ)["sequences"][0]
    return [(o["code"], o["type_obj"], o["nom"]) for p in s["parties"] for o in p["objectifs"]]


def test_connaissance_en_tete_et_unique(ref):
    st, rid = ref
    with st._conn() as c:
        rpe.ajouter_objectif(c, rid, "S01", 1, "Comparer", 1)
        rpe.ajouter_objectif(c, rid, "S01", 1, "Connaître le cours", 1, type_obj="connaissance",
                             criteres={"f": "noté", "a": "complété", "e": "à l'oral"})
        assert _objs(c, rid) == [("01", "connaissance", "Connaître le cours"),
                                 ("02", "capacite", "Comparer")]
        with pytest.raises(rpe.RefExtErreur):
            rpe.ajouter_objectif(c, rid, "S01", 1, "Encore", 1, type_obj="connaissance")
        with pytest.raises(rpe.RefExtErreur):
            rpe.ajouter_objectif(c, rid, "S01", 1, "X", 1, type_obj="autre")
        rpe.ajouter_objectif(c, rid, "S01", 1, "Ranger", 1)
        rpe.deplacer_objectif(c, rid, "S01", "02", -1, AUJ)      # ne passe pas devant
        assert _objs(c, rid)[0][1] == "connaissance"
        rpe.deplacer_objectif(c, rid, "S01", "03", -1, AUJ)      # entre capacités : OK
        assert [o[2] for o in _objs(c, rid)] == ["Connaître le cours", "Ranger", "Comparer"]
        o = rpe.lire(c, rid, AUJ)["sequences"][0]["parties"][0]["objectifs"][0]
        assert (o["critere_f"], o["critere_a"], o["critere_e"]) == ("noté", "complété", "à l'oral")


def test_route_preremplit_la_connaissance(client):
    P = "/api/referentiels-principaux-externes"
    rid = client.post(P, json={"niveau": "N11", "annee": "2026-2027"}).get_json()["id"]
    client.post(f"{P}/{rid}/sequences", json={"nom": "Nombres"})
    client.post(f"{P}/{rid}/sequences/S01/parties", json={"nb_seances": 4})
    r = client.post(f"{P}/{rid}/sequences/S01/parties/1/objectifs", json={"type_obj": "connaissance"})
    assert r.status_code == 201
    o = client.get(f"{P}/{rid}").get_json()["sequences"][0]["parties"][0]["objectifs"][0]
    assert o["type_obj"] == "connaissance" and o["nom"].startswith("Connaître")
    assert o["critere_a"]                                    # critère pré-rempli
