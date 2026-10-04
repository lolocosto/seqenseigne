"""tests/test_v0_47_0_travail.py — v0.47.0

Travail à faire / à rendre et documents à rapporter : échéance individuelle
(délai compté depuis la remise effective, rattrapage compris), vérification
« à faire » (non fait, à rattraper), « à rendre » suivi jusqu'au dernier
rendu ou à la clôture, retards, document marqué « à rapporter », routes.

Classe c1 : un cours le lundi M1 → séances 05/10, 12/10, 19/10, 26/10…
"""
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt, grille_horaire as gh
from services import calendrier_scolaire as cal
from services import documents_seance as docs
from services import seance
from services import travail as tr

ANNEE = "2026-2027"
AUJ = date(2026, 10, 1)
E = ["e1", "e2", "e3"]


@pytest.fixture
def st(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
    s = SqliteStore(tmp_path / "data")
    with s._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'C', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('c1', '4EME3', 'N11', ?, 'et')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c1", aujourd_hui=AUJ)
        for eid in E:
            c.execute("INSERT INTO eleves (id, nom, prenom) VALUES (?, ?, 'P')", (eid, eid.upper()))
            c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES (?, 'c1')", (eid,))
    return s


def _vue(st, jour):
    with st._conn() as c:
        return tr.pour_seance(c, st, ANNEE, "c1", jour, "M1", E)


def test_premiere_seance_apres():
    s = [("2026-10-05", "M1"), ("2026-10-12", "M1"), ("2026-10-19", "M1")]
    assert tr.premiere_seance_apres(s, "2026-10-05", 1, ("2026-10-05", "M1")) == ("2026-10-12", "M1")
    assert tr.premiere_seance_apres(s, "2026-10-05", 8, ("2026-10-05", "M1")) == ("2026-10-19", "M1")
    assert tr.premiere_seance_apres(s, "2026-10-19", 1, ("2026-10-19", "M1")) is None


def test_a_rendre_echeance_individuelle_et_retards(st):
    with st._conn() as c:
        seance.definir_absence(c, st, ANNEE, "c1", "e2", "2026-10-05", "M1", True)
        t = tr.donner(c, st, ANNEE, "c1", "2026-10-05", "M1", "DM 1", "rendre", delai_jours=7)
    v = _vue(st, "2026-10-05")
    assert v["donnes_ici"][0]["echeance_classe"] == ("2026-10-12", "M1")
    assert [e["eleve_id"] for e in v["a_ramasser"][0]["eleves"]] == ["e1", "e3"]   # e2 absent
    # Le travail n'est pas listé dans les « nouveaux documents ».
    with st._conn() as c:
        nv = docs.pour_seance(c, st, ANNEE, "c1", "2026-10-05", "M1", E)["nouveaux"]
        assert all(d["origine"] != "travail" for d in nv)
        # e2 le reçoit le 12/10 par le rattrapage du début de séance.
        r12 = docs.pour_seance(c, st, ANNEE, "c1", "2026-10-12", "M1", E)["a_rattraper"]
        assert r12[0]["eleve_id"] == "e2" and r12[0]["documents"][0]["retour"] == "rendre"
        docs.marquer_donne(c, t["id"], "e2", "2026-10-12", "M1", True)
        tr.marquer_rendu(c, t["id"], "e3", "2026-10-06" if False else "2026-10-12", "M1", True)
    v19 = _vue(st, "2026-10-19")
    ech = {e["eleve_id"]: (e["echeance"], e["en_retard"]) for e in v19["a_ramasser"][0]["eleves"]}
    assert ech == {"e1": (("2026-10-12", "M1"), True), "e2": (("2026-10-19", "M1"), False)}
    assert [r["eleve_id"] for r in v19["en_retard"]] == ["e1"]
    assert [r["eleve_id"] for r in _vue(st, "2026-10-26")["en_retard"]] == ["e1", "e2"]
    with st._conn() as c:
        tr.marquer_rendu(c, t["id"], "e1", "2026-10-19", "M1", True)
        tr.marquer_rendu(c, t["id"], "e2", "2026-10-19", "M1", True)
    assert _vue(st, "2026-10-26")["a_ramasser"] == []          # tout rendu
    assert _vue(st, "2026-10-26")["en_retard"] == []


def test_cloture(st):
    with st._conn() as c:
        t = tr.donner(c, st, ANNEE, "c1", "2026-10-05", "M1", "Exposé", "rendre", delai_jours=7)
        tr.clore(c, t["id"], True)
    assert _vue(st, "2026-10-19")["a_ramasser"] == [] and _vue(st, "2026-10-19")["en_retard"] == []


def test_a_faire_non_fait_et_rattrapage(st):
    with st._conn() as c:
        t = tr.donner(c, st, ANNEE, "c1", "2026-10-05", "M1", "Ex 12 p 40", "faire", delai_jours=1)
        seance.definir_absence(c, st, ANNEE, "c1", "e3", "2026-10-12", "M1", True)
    v12 = _vue(st, "2026-10-12")
    assert [e["eleve_id"] for e in v12["a_verifier"][0]["eleves"]] == ["e1", "e2"]   # e3 absent
    with st._conn() as c:
        tr.marquer_non_fait(c, st, ANNEE, t["id"], "e1", "2026-10-12", "M1", True, a_rattraper=True)
        tr.marquer_non_fait(c, st, ANNEE, t["id"], "e2", "2026-10-12", "M1", True)
    v12 = _vue(st, "2026-10-12")
    el = {e["eleve_id"]: e for e in v12["a_verifier"][0]["eleves"]}
    assert el["e1"]["non_fait"] and el["e1"]["a_rattraper"] and el["e2"]["non_fait"]
    v19 = _vue(st, "2026-10-19")
    assert [(e["eleve_id"], e["rattrapage"]) for e in v19["a_verifier"][0]["eleves"]] == [("e1", True)]
    assert v19["en_retard"] == []
    # Décocher « non fait » retire aussi le rattrapage.
    with st._conn() as c:
        tr.marquer_non_fait(c, st, ANNEE, t["id"], "e1", "2026-10-12", "M1", False)
    assert _vue(st, "2026-10-19")["a_verifier"] == []


def test_document_a_rapporter(st):
    with st._conn() as c:
        d = docs.ajouter_ponctuel(c, ANNEE, "c1", "Autorisation sortie", "sortie",
                                  "2026-10-05", "M1")
        docs.marquer_distribue(c, d["id"], "2026-10-05", "M1", True)
        tr.definir_retour(c, d["id"], "rapporter", 7)
    v = _vue(st, "2026-10-12")
    assert v["a_ramasser"][0]["retour"] == "rapporter" and len(v["a_ramasser"][0]["eleves"]) == 3
    assert [r["eleve_id"] for r in _vue(st, "2026-10-19")["en_retard"]] == E
    with st._conn() as c:
        tr.definir_retour(c, d["id"], "", 0)
    assert _vue(st, "2026-10-19")["a_ramasser"] == []


def test_validations(st):
    with st._conn() as c:
        with pytest.raises(tr.TravailErreur):
            tr.donner(c, st, ANNEE, "c1", "2026-10-05", "M1", " ", "rendre")
        with pytest.raises(tr.TravailErreur):
            tr.donner(c, st, ANNEE, "c1", "2026-10-05", "M1", "X", "autre")
        with pytest.raises(tr.TravailErreur):
            tr.donner(c, st, ANNEE, "c1", "2026-10-05", "M1", "X", "rendre",
                      echeance=("2026-10-06", "M1"))
        t = tr.donner(c, st, ANNEE, "c1", "2026-10-05", "M1", "X", "rendre",
                      echeance=("2026-10-19", "M1"))
        assert t["delai_jours"] == 14
        with pytest.raises(tr.TravailErreur):
            tr.marquer_non_fait(c, st, ANNEE, t["id"], "e1", "2026-10-19", "M1", True)
        tr.supprimer_travail(c, t["id"])
        with pytest.raises(tr.TravailErreur):
            tr.clore(c, t["id"], True)


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
        c.execute("INSERT INTO eleves (id, nom, prenom) VALUES ('e1', 'A', 'P')")
        c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES ('e1', 'c1')")
    base = {"annee": ANNEE, "classe_id": "c1", "date": "2026-10-05", "creneau": "M1"}
    r = client.post("/api/travail", json={**base, "libelle": "DM", "retour": "rendre",
                                          "delai_jours": 7})
    assert r.status_code == 201
    tid = r.get_json()["id"]
    q = f"annee={ANNEE}&classe_id=c1&date=2026-10-19&creneau=M1"
    assert client.get("/api/travail?" + q).get_json()["en_retard"][0]["eleve_id"] == "e1"
    assert client.put(f"/api/travail/{tid}/rendu", json={**base, "date": "2026-10-19",
                      "eleve_id": "e1", "rendu": True}).status_code == 200
    assert client.get("/api/travail?" + q).get_json()["en_retard"] == []
    assert client.put(f"/api/travail/{tid}/clos", json={"clos": True}).status_code == 200
    assert client.delete(f"/api/travail/{tid}").status_code == 200
    assert client.get(f"/api/travail?annee={ANNEE}&classe_id=c1&date=2026-10-06&creneau=M1").status_code == 404
