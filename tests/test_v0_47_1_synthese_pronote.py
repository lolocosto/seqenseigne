"""tests/test_v0_47_1_synthese_pronote.py — v0.47.1

Synthèse pour le cahier de textes Pronote : ligne de mise en route
(automatismes, « Pas de mise en route », rien sans MER), ligne de séquence
(code, nom, partie, n/N), « Cours » à partir des notions / méthodes des
objectifs de la partie, activités dans l'ordre choisi, texte libre, documents
distribués, travail à faire ; éléments déjà faits dans le créneau ;
activités paramétrables ; routes.
"""
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt, grille_horaire as gh
from services import calendrier_scolaire as cal
from services import documents_seance as docs
from services import seance
from services import synthese_seance as sy
from services import travail as tr

ANNEE = "2026-2027"
AUJ = date(2026, 10, 1)


@pytest.fixture
def st(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "vacances", lambda *a, **k: [])
    monkeypatch.setattr(cal, "jours_feries_annee_scolaire", lambda *a: {})
    s = SqliteStore(tmp_path / "data")
    with s._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat, academie) VALUES "
                  "('et', 'C', 'propose', 'Rennes')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id, mer_active, "
                  "mer_mode) VALUES ('c1', '4EME3', 'N11', ?, 'et', 1, 'automatismes')", (ANNEE,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="c1", aujourd_hui=AUJ)
        c.execute("INSERT INTO eleves (id, nom, prenom) VALUES ('e1', 'A', 'P')")
        c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES ('e1', 'c1')")
        # Atelier : S14 partie 1, deux objectifs (notions + méthode).
        c.execute("INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES "
                  "('sn1', 'N11', 'S14')")
        c.execute("INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES "
                  "('pt1', 'sn1', 1)")
        c.execute("INSERT INTO notions (id, titre) VALUES ('no1', 'Algorithme'), "
                  "('no2', 'Variable \\emph{informatique}')")
        c.execute("INSERT INTO methodes (id, titre) VALUES ('me1', 'Lire un script')")
        c.execute("INSERT INTO objectifs (id, partie_id, code, nom, methode_id) VALUES "
                  "('ob1', 'pt1', '01', 'Cours', NULL), ('ob2', 'pt1', '02', 'Lire', 'me1')")
        c.execute("INSERT INTO objectif_notions (objectif_id, notion_id, ordre) VALUES "
                  "('ob1', 'no1', 1), ('ob1', 'no2', 2)")
        sy.migrer(c)
    s.ecrire_progression({"niveau": "N11", "annee": ANNEE, "etablissement_id": "et",
                          "creneaux": [{"id": "cr1", "sequence": "S14", "partie_debut": 1,
                                        "partie_fin": 1, "partie": "1re partie", "ordre": 1,
                                        "date_debut": "2026-10-05", "date_fin": "2026-10-23"}]})
    return s


def _lire(st, jour="2026-10-05"):
    with st._conn() as c:
        return sy.lire(c, st, ANNEE, "c1", jour, "M1")


def test_candidats_et_lignes_de_base(st):
    r = _lire(st)
    assert [n["titre"] for n in r["candidats"]["notions"]] == ["Algorithme", "Variable informatique"]
    assert [m["titre"] for m in r["candidats"]["methodes"]] == ["Lire un script"]
    lignes = r["contenu"].splitlines()
    assert lignes[0].startswith("Mise en route : automatismes (enveloppe")
    assert lignes[1] == "S14 — 1re partie (1/3)"
    assert not r["externe"] and r["travail"] == ""


def test_choix_cours_activites_texte_documents_travail(st):
    with st._conn() as c:
        sy.enregistrer_contenu(c, "c1", "2026-10-05", "M1", {
            "notions": ["no1", "no2"], "methodes": ["me1"],
            "activites": ["Évaluation", "Révisions", "Exercices"],
            "texte_libre": "Programme Scratch : le chat qui danse"})
        d = docs.ajouter_ponctuel(c, ANNEE, "c1", "Autorisation sortie", "sortie",
                                  "2026-10-05", "M1")
        docs.marquer_distribue(c, d["id"], "2026-10-05", "M1", True)
        tr.donner(c, st, ANNEE, "c1", "2026-10-05", "M1", "DM 1", "rendre", delai_jours=7)
        tr.donner(c, st, ANNEE, "c1", "2026-10-05", "M1", "Ex 3 p 12", "faire", delai_jours=1)
    r = _lire(st)
    assert r["contenu"].splitlines()[2:] == [
        "Cours : notions (Algorithme, Variable informatique) et méthode (Lire un script)",
        "Évaluation", "Révisions", "Exercices",
        "Programme Scratch : le chat qui danse",
        "Documents distribués : Autorisation sortie"]
    assert r["travail"].splitlines() == ["Pour le 12/10 : DM 1 (à rendre)",
                                         "Pour le 12/10 : Ex 3 p 12"]


def test_deja_faits_dans_le_creneau(st):
    with st._conn() as c:
        sy.enregistrer_contenu(c, "c1", "2026-10-05", "M1", {"notions": ["no1"]})
    assert _lire(st, "2026-10-12")["deja_faits"] == {"notions": ["no1"], "methodes": []}
    assert _lire(st, "2026-10-05")["deja_faits"] == {"notions": [], "methodes": []}


def test_pas_de_mise_en_route_et_classe_sans_mer(st):
    with st._conn() as c:
        seance.marquer_mer_non_faite(c, st, ANNEE, "c1", "2026-10-05", "M1", True)
    assert _lire(st)["contenu"].splitlines()[0] == "Pas de mise en route"
    with st._conn() as c:
        c.execute("UPDATE classes SET mer_active=0 WHERE id='c1'")
    assert _lire(st)["contenu"].splitlines()[0].startswith("S14")


def test_activites_parametrables(st):
    with st._conn() as c:
        assert [a["libelle"] for a in sy.lister_activites(c)] == list(sy.ACTIVITES_DEFAUT)
        a = sy.ajouter_activite(c, "Travail de groupe")
        with pytest.raises(sy.SyntheseErreur):
            sy.ajouter_activite(c, "révisions")
        sy.modifier_activite(c, a["id"], {"actif": False})
        assert "Travail de groupe" not in [x["libelle"] for x in sy.lister_activites(c)]
        assert "Travail de groupe" in [x["libelle"] for x in sy.lister_activites(c, True)]


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
    base = {"annee": ANNEE, "classe_id": "c1", "date": "2026-10-05", "creneau": "M1"}
    r = client.put("/api/seance/synthese", json={**base, "choix": {
        "activites": ["Correction"], "texte_libre": "Séance libre"}}).get_json()
    assert r["externe"] is True and r["contenu"] == "Correction\nSéance libre"
    assert client.get(f"/api/seance/synthese?annee={ANNEE}&classe_id=c1&date=2026-10-06"
                      f"&creneau=M1").status_code == 404
    assert client.post("/api/activites-seance", json={"libelle": "Oral"}).status_code == 201
    assert len(client.get("/api/activites-seance").get_json()["activites"]) == 5
