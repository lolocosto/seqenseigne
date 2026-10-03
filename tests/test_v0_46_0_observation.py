"""tests/test_v0_46_0_observation.py — v0.46.0

Observation en séance : occurrences par élève et observable, compteurs
valoriser / sanctionner, élève absent refusé, observable hors de la liste
effective de l'élève refusé (masqué, individuel non attribué), suppression,
« annuler la dernière », renommage reflété, routes.
"""
from datetime import date, datetime

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt, grille_horaire as gh
from services import calendrier_scolaire as cal
from services import observables as ob
from services import observation as ov
from services import seance

ANNEE = "2026-2027"
AUJ = date(2026, 10, 1)
J, C = "2026-10-05", "M1"


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
    st = SqliteStore(tmp_path / "data")
    with st._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'C', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('c1', '4EME3', 'N11', ?, 'et')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c1", aujourd_hui=AUJ)
        for eid in ("e1", "e2"):
            c.execute("INSERT INTO eleves (id, nom, prenom) VALUES (?, 'N', 'P')", (eid,))
            c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES (?, 'c1')", (eid,))
        o = {"part": ob.creer(c, "N11", "valoriser", "Participation")["id"],
             "bav": ob.creer(c, "N11", "sanctionner", "Bavardage")["id"],
             "tel": ob.creer(c, "N11", "sanctionner", "Téléphone")["id"]}
        ob.ajouter_exception(c, o["bav"], "e2")                 # masqué pour e2
        ob.modifier(c, o["tel"], {"portee": "individuel"})
        ob.ajouter_exception(c, o["tel"], "e1")                 # attribué à e1
    return st, o


def _aj(c, st, eid, oid):
    return ov.ajouter(c, st, ANNEE, "c1", eid, J, C, oid, datetime(2026, 10, 5, 8, 40))


def test_occurrences_et_compteurs(ctx):
    st, o = ctx
    with st._conn() as c:
        _aj(c, st, "e1", o["part"])
        _aj(c, st, "e1", o["part"])
        _aj(c, st, "e1", o["bav"])
        r = _aj(c, st, "e1", o["tel"])
    assert r["compteurs"] == {"e1": {"valoriser": 2, "sanctionner": 2}}
    assert [x["libelle"] for x in r["occurrences"]] == ["Participation", "Participation",
                                                        "Bavardage", "Téléphone"]


def test_refus_hors_liste_effective_et_absent(ctx):
    st, o = ctx
    with st._conn() as c:
        with pytest.raises(ov.ObservationErreur):
            _aj(c, st, "e2", o["bav"])              # masqué pour e2
        with pytest.raises(ov.ObservationErreur):
            _aj(c, st, "e2", o["tel"])              # individuel non attribué
        seance.definir_absence(c, st, ANNEE, "c1", "e2", J, C, True)
        with pytest.raises(ov.ObservationErreur):
            _aj(c, st, "e2", o["part"])             # absent
        with pytest.raises(ov.ObservationErreur):
            ov.ajouter(c, st, ANNEE, "c1", "e1", "2026-10-06", C, o["part"])   # pas de séance


def test_supprimer_et_annuler_derniere(ctx):
    st, o = ctx
    with st._conn() as c:
        r = _aj(c, st, "e1", o["part"])
        _aj(c, st, "e2", o["part"])
        _aj(c, st, "e1", o["bav"])
        r = ov.annuler_derniere(c, "c1", J, C, "e1")
        assert r["compteurs"]["e1"] == {"valoriser": 1, "sanctionner": 0}
        r = ov.supprimer(c, r["occurrences"][0]["id"])
        assert "e1" not in r["compteurs"] and r["compteurs"]["e2"]["valoriser"] == 1
        with pytest.raises(ov.ObservationErreur):
            ov.supprimer(c, "zz")
        assert ov.annuler_derniere(c, "c1", J, C, "e1")["compteurs"] == {"e2": {"valoriser": 1, "sanctionner": 0}}


def test_renommage_reflete(ctx):
    st, o = ctx
    with st._conn() as c:
        _aj(c, st, "e1", o["part"])
        ob.modifier(c, o["part"], {"libelle": "Participation orale"})
        assert ov.lire(c, "c1", J, C)["occurrences"][0]["libelle"] == "Participation orale"


def test_routes(client, app, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
    with app.json_store._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'C', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('c1', '4EME3', 'N11', ?, 'et')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c1", aujourd_hui=AUJ)
        c.execute("INSERT INTO eleves (id, nom, prenom) VALUES ('e1', 'N', 'P')")
        c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES ('e1', 'c1')")
        oid = ob.creer(c, "N11", "valoriser", "Participation")["id"]
    base = {"annee": ANNEE, "classe_id": "c1", "date": J, "creneau": C}
    l = client.get(f"/api/observation/liste?classe_id=c1&eleve_id=e1&date={J}").get_json()
    assert [x["libelle"] for x in l["valoriser"]] == ["Participation"]
    r = client.post("/api/observation", json={**base, "eleve_id": "e1", "observable_id": oid})
    assert r.status_code == 201 and r.get_json()["compteurs"]["e1"]["valoriser"] == 1
    occ = r.get_json()["occurrences"][0]["id"]
    assert client.get(f"/api/observation?classe_id=c1&date={J}&creneau={C}").get_json()["niveau"] == "N11"
    assert client.delete(f"/api/observation/{occ}").get_json()["compteurs"] == {}
    assert client.post("/api/observation/annuler-derniere",
                       json={**base, "eleve_id": "e1"}).status_code == 200
    assert client.post("/api/observation", json={**base, "eleve_id": "e1",
                                                 "observable_id": "zz"}).status_code == 400
