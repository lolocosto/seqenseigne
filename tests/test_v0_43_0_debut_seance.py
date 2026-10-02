"""tests/test_v0_43_0_debut_seance.py — v0.43.0

Début de séance : séance en cours / prochaine / dernière d'après l'heure,
séances du jour, mise en route (Leitner, MER progression), plan de classe de
la semaine ou liste alphabétique, absences (clic, annulation, validations).
"""
from datetime import date, datetime

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt, grille_horaire as gh, salles as sv, indisponibilites as ind
from services import calendrier_scolaire as cal
from services import plans_classe as pc
from services import seance

ANNEE = "2026-2027"
AUJ = date(2026, 10, 1)
# Lundi 05/10/2026, semaine A (07/09 = B, 14/09 = A … 05/10 = A).
LUN = date(2026, 10, 5)


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
    return SqliteStore(tmp_path / "data")


@pytest.fixture
def base(store):
    with store._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'C', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        for cid, nom in (("c1", "4EME3"), ("c2", "6EME8")):
            c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id, "
                      "mer_active, mer_mode) VALUES (?,?,'N11',?,'et',1,'automatismes')",
                      (cid, nom, ANNEE))
        s = sv.creer(c, "et", "302", AUJ)
        sv.enregistrer_plan(c, s["id"], [{"x": 0, "y": 0}, {"x": 60, "y": 0}], AUJ)
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c1", salle_id=s["id"], aujourd_hui=AUJ)
        edt.ajouter(c, ANNEE, "lun", "M3", "et", classe_id="c2", aujourd_hui=AUJ)
        for eid, nom, pr in (("e1", "ZOLA", "Ana"), ("e2", "ABEL", "Léo")):
            c.execute("INSERT INTO eleves (id, nom, prenom) VALUES (?,?,?)", (eid, nom, pr))
            c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES (?, 'c1')", (eid,))
    return s["id"]


def _t(h, m, jour=LUN):
    return datetime(jour.year, jour.month, jour.day, h, m)


class TestSeanceEnCours:
    def test_en_cours_puis_prochaine_puis_derniere(self, store, base):
        with store._conn() as c:
            s = seance.seance_en_cours(c, store, ANNEE, _t(8, 40))
            assert (s["classe_id"], s["creneau"], s["statut"]) == ("c1", "M1", "en_cours")
            s = seance.seance_en_cours(c, store, ANNEE, _t(9, 50))
            assert (s["classe_id"], s["statut"]) == ("c2", "a_venir")
            s = seance.seance_en_cours(c, store, ANNEE, _t(7, 0))
            assert (s["creneau"], s["statut"]) == ("M1", "a_venir")
            s = seance.seance_en_cours(c, store, ANNEE, _t(17, 0))
            assert (s["classe_id"], s["statut"]) == ("c2", "terminee")

    def test_par_classe_et_jour_sans_cours(self, store, base):
        with store._conn() as c:
            s = seance.seance_en_cours(c, store, ANNEE, _t(8, 40), classe_id="c2")
            assert s["classe_id"] == "c2" and s["statut"] == "a_venir"
            assert seance.seance_en_cours(c, store, ANNEE, _t(8, 40, date(2026, 10, 6))) is None

    def test_indisponibilite_ecartee(self, store, base):
        with store._conn() as c:
            ind.creer(c, ANNEE, "et", type="journees", date_debut="2026-10-05")
            assert seance.seance_en_cours(c, store, ANNEE, _t(8, 40)) is None


class TestLecture:
    def test_mise_en_route_et_liste_sans_plan(self, store, base):
        with store._conn() as c:
            r = seance.lire(c, store, ANNEE, "c1", "2026-10-05", "M1", _t(8, 40))
        assert r["seance"]["statut"] == "en_cours"
        assert r["mise_en_route"]["type"] == "mer_auto"
        assert r["mise_en_route"]["rang"] >= 1 and r["mise_en_route"]["enveloppes"]
        assert r["plan"] is None                                  # aucun élève placé
        assert [e["nom"] for e in r["eleves"]] == ["ABEL", "ZOLA"]  # alphabétique
        assert r["absents"] == [] and len(r["seances_du_jour"]) == 1

    def test_plan_de_la_semaine(self, store, base):
        with store._conn() as c:
            pc.enregistrer(c, "c1", base, "2026-10-05",
                           [{"eleve_id": "e1", "numero": 1, "statut": "libre"}], AUJ)
            r = seance.lire(c, store, ANNEE, "c1", "2026-10-05", "M1", _t(8, 40))
        assert r["plan"]["salle"]["nom"] == "302" and len(r["plan"]["placements"]) == 1

    def test_seance_inexistante(self, store, base):
        with store._conn() as c:
            with pytest.raises(seance.SeanceErreur):
                seance.lire(c, store, ANNEE, "c1", "2026-10-06", "M1", _t(8, 40))


class TestAbsences:
    def test_basculer(self, store, base):
        with store._conn() as c:
            assert seance.definir_absence(c, store, ANNEE, "c1", "e1", "2026-10-05",
                                          "M1", True) == ["e1"]
            seance.definir_absence(c, store, ANNEE, "c1", "e1", "2026-10-05", "M1", True)
            assert seance.absents(c, "c1", "2026-10-05", "M1") == ["e1"]   # idempotent
            assert seance.definir_absence(c, store, ANNEE, "c1", "e1", "2026-10-05",
                                          "M1", False) == []

    def test_validations(self, store, base):
        with store._conn() as c:
            with pytest.raises(seance.SeanceErreur):
                seance.definir_absence(c, store, ANNEE, "c1", "zz", "2026-10-05", "M1", True)
            with pytest.raises(seance.SeanceErreur):
                seance.definir_absence(c, store, ANNEE, "c1", "e1", "2026-10-06", "M1", True)


def test_routes(client, app, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
    from routes import seance as rs
    monkeypatch.setattr(rs, "_maintenant", lambda: _t(8, 40))
    with app.json_store._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'C', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('c1', '4EME3', 'N11', ?, 'et')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c1", aujourd_hui=AUJ)
        c.execute("INSERT INTO eleves (id, nom, prenom) VALUES ('e1', 'Z', 'A')")
        c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES ('e1', 'c1')")
    s = client.get(f"/api/seance/en-cours?annee={ANNEE}").get_json()["seance"]
    assert s["classe_id"] == "c1" and s["statut"] == "en_cours"
    q = f"annee={ANNEE}&classe_id=c1&date=2026-10-05&creneau=M1"
    assert client.get("/api/seance?" + q).get_json()["mise_en_route"]["type"] is None
    r = client.put("/api/seance/absence", json={"annee": ANNEE, "classe_id": "c1",
                   "eleve_id": "e1", "date": "2026-10-05", "creneau": "M1", "absent": True})
    assert r.get_json()["absents"] == ["e1"]
    assert client.get("/api/seance?annee=2026-2027&classe_id=c1&date=2026-10-06"
                      "&creneau=M1").status_code == 404
