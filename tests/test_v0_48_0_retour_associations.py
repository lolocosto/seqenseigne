"""tests/test_v0_48_0_retour_associations.py — v0.48.0

Retour attendu (à faire / à rendre) et délai sur les documents associés à la
progression principale ; « fin du créneau » (échéance fixe, absents compris) ;
conversion en travail à la distribution ; suivi des changements tant que le
document n'est pas distribué ; synthèse Pronote ; routes.

Classe c1 : lundi M1 ; créneau cr1 du 28/09 au 23/10 → séances 28/09, 05/10,
12/10, 19/10 (fin du créneau = 19/10).
"""
from datetime import date, datetime

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt, grille_horaire as gh
from services import calendrier_scolaire as cal
from services import progression_doc as pgd
from services import documents_seance as docs
from services import seance
from services import synthese_seance as sy
from services import travail as tr

ANNEE = "2026-2027"
AUJ = date(2026, 10, 1)
E = ["e1", "e2"]


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
                  "VALUES ('c1', '6EME3', 'N09', ?, 'et')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c1", aujourd_hui=AUJ)
        for eid in E:
            c.execute("INSERT INTO eleves (id, nom, prenom) VALUES (?, ?, 'P')", (eid, eid.upper()))
            c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES (?, 'c1')", (eid,))
    s.ecrire_progression({"niveau": "N09", "annee": ANNEE, "etablissement_id": "et",
                          "creneaux": [{"id": "cr1", "sequence": "S01", "partie_debut": 1,
                                        "partie_fin": 1, "partie": "1re partie", "ordre": 1,
                                        "date_debut": "2026-09-28", "date_fin": "2026-10-23"}]})
    return s


def _prog(st):
    return st.lire_progression_par_triplet("N09", ANNEE, "et")


def _assoc(st, rang, lib, **kw):
    with st._conn() as c:
        return pgd.ajouter(c, prog_kind="principale", prog_ref=_prog(st)["id"],
                           creneau_ref="cr1", rang_seance=rang, doc_source="externe",
                           doc_ref=lib, doc_libelle=lib, **kw)


def test_validation_et_delais():
    assert pgd.delai_en_jours("prochaine", 3) == 1
    assert pgd.delai_en_jours("jours", 3) == 3
    assert pgd.delai_en_jours("semaines", 2) == 14
    assert pgd.delai_en_jours("fin_creneau", 1) == 0
    with pytest.raises(ValueError):
        pgd._valider_retour("autre", "", 1)
    with pytest.raises(ValueError):
        pgd._valider_retour("faire", "mois", 1)
    assert pgd._valider_retour("", "jours", 5) == ("", "", 1)


def test_fiches_de_resume_fin_du_creneau(st):
    _assoc(st, 1, "Fiches de résumé", retour="faire", delai_type="fin_creneau")
    with st._conn() as c:
        p = docs.documents_prevus(c, st, ANNEE, "c1")[0]
        assert p["echeance"] == ("2026-10-19", "M1") and p["retour"] == "faire"
        seance.definir_absence(c, st, ANNEE, "c1", "e2", "2026-09-28", "M1", True)
        nv = docs.pour_seance(c, st, ANNEE, "c1", "2026-09-28", "M1", E)["nouveaux"]
        docs.marquer_distribue(c, nv[0]["id"], "2026-09-28", "M1", True)
        # e2 reçoit les fiches en rattrapage le 05/10 : même échéance (19/10).
        docs.marquer_donne(c, nv[0]["id"], "e2", "2026-10-05", "M1", True)
        v = tr.pour_seance(c, st, ANNEE, "c1", "2026-10-19", "M1", E)
    assert [e["eleve_id"] for e in v["a_verifier"][0]["eleves"]] == ["e1", "e2"]
    with st._conn() as c:
        assert tr.pour_seance(c, st, ANNEE, "c1", "2026-10-12", "M1", E)["a_verifier"] == []


def test_a_rendre_avec_delai_et_synthese(st):
    _assoc(st, 2, "DM 1", retour="rendre", delai_type="semaines", delai_n=1)
    with st._conn() as c:
        nv = docs.pour_seance(c, st, ANNEE, "c1", "2026-10-05", "M1", E)["nouveaux"]
        docs.marquer_distribue(c, nv[0]["id"], "2026-10-05", "M1", True)
        v = tr.pour_seance(c, st, ANNEE, "c1", "2026-10-05", "M1", E)
        assert v["donnes_ici"][0]["echeance_classe"] == ("2026-10-12", "M1")
        assert [r["eleve_id"] for r in tr.pour_seance(c, st, ANNEE, "c1", "2026-10-19",
                                                      "M1", E)["en_retard"]] == E
        s = sy.lire(c, st, ANNEE, "c1", "2026-10-05", "M1")
    assert "Documents distribués : DM 1" in s["contenu"]
    assert s["travail"] == "Pour le 12/10 : DM 1 (à rendre)"


def test_changement_suivi_tant_que_non_distribue(st):
    a = _assoc(st, 1, "Fiche A")
    with st._conn() as c:
        docs.pour_seance(c, st, ANNEE, "c1", "2026-09-28", "M1", E)        # matérialisée
        pgd.modifier_retour(c, a["id"], "faire", "jours", 3)
        nv = docs.pour_seance(c, st, ANNEE, "c1", "2026-09-28", "M1", E)["nouveaux"]
        assert (nv[0]["retour"], nv[0]["delai_jours"]) == ("faire", 3)
        docs.marquer_distribue(c, nv[0]["id"], "2026-09-28", "M1", True)
        pgd.modifier_retour(c, a["id"], "", "", 1)                         # trop tard
        nv = docs.pour_seance(c, st, ANNEE, "c1", "2026-09-28", "M1", E)["nouveaux"]
        assert nv[0]["retour"] == "faire"


def test_routes(client, app, st):
    r = client.post("/api/progression-doc", json={
        "prog_kind": "principale", "prog_ref": "p", "creneau_ref": "cr", "rang_seance": 1,
        "doc_source": "externe", "doc_ref": "x", "retour": "rendre", "delai_type": "jours",
        "delai_n": 4})
    assert r.status_code == 201 and r.get_json()["delai_n"] == 4
    aid = r.get_json()["id"]
    assert client.put(f"/api/progression-doc/{aid}/retour",
                      json={"retour": "faire", "delai_type": "fin_creneau"}).get_json()["delai_type"] == "fin_creneau"
    assert client.put(f"/api/progression-doc/{aid}/retour",
                      json={"retour": "zz"}).status_code == 400
