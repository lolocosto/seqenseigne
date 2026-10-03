"""tests/test_v0_44_0_documents.py — v0.44.0

Documents de début de séance : documents prévus (progression principale)
placés sur leur séance, report d'un document non distribué, document ajouté à
la volée (cette séance ou la suivante), distribution, absents redevables,
rattrapage (« donné »), suivi qui ne remonte pas avant son ouverture.

Classe c1 : un cours le lundi M1. Semaine de rentrée ignorée → 14/09 = 1re
séance ; séances : 14/09, 21/09, 28/09, 05/10, 12/10, 19/10…
"""
from datetime import date, datetime

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt, grille_horaire as gh
from services import calendrier_scolaire as cal
from services import progression_doc as pgd
from services import documents_seance as docs
from services import seance

ANNEE = "2026-2027"
AUJ = date(2026, 10, 1)
T = datetime(2026, 10, 5, 9, 0)


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
    st = SqliteStore(tmp_path / "data")
    with st._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'C', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('c1', '6EME3', 'N09', ?, 'et')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c1", aujourd_hui=AUJ)
        for eid, nom in (("e1", "ALI"), ("e2", "BEN"), ("e3", "COL")):
            c.execute("INSERT INTO eleves (id, nom, prenom) VALUES (?,?,'X')", (eid, nom))
            c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES (?, 'c1')", (eid,))
    st.ecrire_progression({
        "niveau": "N09", "annee": ANNEE, "etablissement_id": "et",
        "creneaux": [{"id": "cr1", "sequence": "S01", "partie_debut": 1, "partie_fin": 1,
                      "partie": "1re partie", "ordre": 1,
                      "date_debut": "2026-09-28", "date_fin": "2026-10-23"}]})
    prog = st.lire_progression_par_triplet("N09", ANNEE, "et")
    with st._conn() as c:
        # Rang 1 = 28/09 ; rang 2 = 05/10 ; rang 3 = 12/10.
        pgd.ajouter(c, prog_kind="principale", prog_ref=prog["id"], creneau_ref="cr1",
                    rang_seance=2, doc_source="externe", doc_ref="fiche", doc_libelle="Fiche 1")
        pgd.ajouter(c, prog_kind="principale", prog_ref=prog["id"], creneau_ref="cr1",
                    rang_seance=3, doc_source="externe", doc_ref="ex", doc_libelle="Exercices")
        pgd.ajouter(c, prog_kind="principale", prog_ref=prog["id"], creneau_ref="cr1",
                    rang_seance=1, doc_source="externe", doc_ref="old", doc_libelle="Ancien")
    return st


def _lire(store, jour):
    with store._conn() as c:
        return seance.lire(c, store, ANNEE, "c1", jour, "M1", T)


def _nouveaux(store, jour):
    return [(d["libelle"], d["distribue"], d["reporte"])
            for d in _lire(store, jour)["documents"]["nouveaux"]]


def test_documents_prevus_places_sur_leur_seance(store):
    with store._conn() as c:
        p = {x["libelle"]: x["date"] for x in docs.documents_prevus(c, store, ANNEE, "c1")}
    assert p == {"Ancien": "2026-09-28", "Fiche 1": "2026-10-05", "Exercices": "2026-10-12"}


def test_suivi_ouvert_ne_remonte_pas_le_passe(store):
    # Première ouverture au 05/10 : « Ancien » (28/09) n'apparaît pas.
    assert _nouveaux(store, "2026-10-05") == [("Fiche 1", False, False)]


def test_distribution_report_et_rattrapage(store):
    lu = _lire(store, "2026-10-05")
    fiche = lu["documents"]["nouveaux"][0]["id"]
    with store._conn() as c:
        seance.definir_absence(c, store, ANNEE, "c1", "e2", "2026-10-05", "M1", True)
        docs.marquer_distribue(c, fiche, "2026-10-05", "M1", True)
    assert _nouveaux(store, "2026-10-05") == [("Fiche 1", True, False)]
    # 12/10 : « Exercices » nouveau ; e2, présent, doit la fiche.
    l12 = _lire(store, "2026-10-12")
    assert [(d["libelle"], d["reporte"]) for d in l12["documents"]["nouveaux"]] == [("Exercices", False)]
    assert [(r["eleve_id"], [d["libelle"] for d in r["documents"]])
            for r in l12["documents"]["a_rattraper"]] == [("e2", ["Fiche 1"])]
    # « Exercices » non distribué le 12/10 → reporté le 19/10.
    assert _nouveaux(store, "2026-10-19") == [("Exercices", False, True)]
    # Donné à e2 le 12/10 : coché le 12/10, disparu ensuite.
    with store._conn() as c:
        docs.marquer_donne(c, fiche, "e2", "2026-10-12", "M1", True)
    r12 = _lire(store, "2026-10-12")["documents"]["a_rattraper"]
    assert r12 == [{"eleve_id": "e2", "documents": [{**r12[0]["documents"][0], "donne": True}]}]
    assert _lire(store, "2026-10-19")["documents"]["a_rattraper"] == []


def test_absent_encore_non_liste(store):
    lu = _lire(store, "2026-10-05")
    fiche = lu["documents"]["nouveaux"][0]["id"]
    with store._conn() as c:
        seance.definir_absence(c, store, ANNEE, "c1", "e2", "2026-10-05", "M1", True)
        docs.marquer_distribue(c, fiche, "2026-10-05", "M1", True)
        seance.definir_absence(c, store, ANNEE, "c1", "e2", "2026-10-12", "M1", True)
    assert _lire(store, "2026-10-12")["documents"]["a_rattraper"] == []
    assert _lire(store, "2026-10-19")["documents"]["a_rattraper"][0]["eleve_id"] == "e2"


def test_ponctuel_pour_la_prochaine_seance(client, app, monkeypatch, store):
    # Via le service : ajout pour la séance suivante (12/10), visible le 12/10.
    with store._conn() as c:
        suiv = seance.seance_suivante(c, store, ANNEE, "c1", "2026-10-05", "M1")
        assert suiv["date"] == "2026-10-12"
        d = docs.ajouter_ponctuel(c, ANNEE, "c1", "Autorisation de sortie", "sortie",
                                  suiv["date"], suiv["creneau"])
        with pytest.raises(docs.DocumentErreur):     # pas encore sa séance
            docs.marquer_distribue(c, d["id"], "2026-10-05", "M1", True)
    assert ("Autorisation de sortie", False, False) not in _nouveaux(store, "2026-10-05")
    assert ("Autorisation de sortie", False, False) in _nouveaux(store, "2026-10-12")
    with store._conn() as c:
        docs.supprimer_ponctuel(c, d["id"])
    assert ("Autorisation de sortie", False, False) not in _nouveaux(store, "2026-10-12")


def test_validations(store):
    with store._conn() as c:
        with pytest.raises(docs.DocumentErreur):
            docs.ajouter_ponctuel(c, ANNEE, "c1", "  ", "sortie", "2026-10-05", "M1")
        with pytest.raises(docs.DocumentErreur):
            docs.ajouter_ponctuel(c, ANNEE, "c1", "X", "autre", "2026-10-05", "M1")
        with pytest.raises(docs.DocumentErreur):
            docs.marquer_distribue(c, "absent", "2026-10-05", "M1", True)
    lu = _lire(store, "2026-10-05")
    with store._conn() as c:
        with pytest.raises(docs.DocumentErreur):          # un prévu ne se supprime pas
            docs.supprimer_ponctuel(c, lu["documents"]["nouveaux"][0]["id"])


def test_routes(client, app, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
    from routes import seance as rs
    monkeypatch.setattr(rs, "_maintenant", lambda: T)
    with app.json_store._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'C', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('c1', '6EME3', 'N09', ?, 'et')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c1", aujourd_hui=AUJ)
    base = {"annee": ANNEE, "classe_id": "c1", "date": "2026-10-05", "creneau": "M1"}
    r = client.post("/api/seance/document", json={**base, "libelle": "Mot PP",
                                                  "categorie": "administratif", "pour": "prochaine"})
    assert r.status_code == 201 and r.get_json()["cible_date"] == "2026-10-12"
    did = r.get_json()["id"]
    assert client.put(f"/api/seance/document/{did}/distribue",
                      json={**base, "distribue": True}).status_code == 400
    l = client.get(f"/api/seance?annee={ANNEE}&classe_id=c1&date=2026-10-12&creneau=M1").get_json()
    assert l["documents"]["nouveaux"][0]["libelle"] == "Mot PP"
    assert client.put(f"/api/seance/document/{did}/distribue", json={
        **base, "date": "2026-10-12", "distribue": True}).status_code == 200
    assert client.delete(f"/api/seance/document/{did}").status_code == 200
