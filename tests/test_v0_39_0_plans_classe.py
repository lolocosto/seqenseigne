"""tests/test_v0_39_0_plans_classe.py — v0.39.0

Plans de classe hebdomadaires : salles de la semaine (cours en classe
entière), plan vide / saisi / reconduit (libres à confirmer), semaines
passées figées, élèves sortis / arrivés, place disparue d'une version de
salle, validations, aléatoire, étiquettes « Prénom N. », impression PDF.
"""
import random
from datetime import date
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt, grille_horaire as gh, salles as sv
from services import plans_classe as pc
from services import plan_classe_pdf as pdf
from services.plan_salle_tikz import places_depuis_tikz

ANNEE = "2026-2027"
AUJ = date(2026, 10, 1)                 # semaine du 28/09
S40, S41, S42 = "2026-09-28", "2026-10-05", "2026-10-12"
FIXTURE_302 = Path(__file__).parent / "fixtures" / "plan_salle_302.tex"


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


@pytest.fixture
def base(store):
    """Établissement, salle 302 (plan réel), 4EME3 avec 4 élèves, un cours
    en classe entière en 302 et un demi-groupe en 310."""
    with store._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat) VALUES "
                  "('et', 'Collège', 'propose')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('cl', '4EME3', 'N11', ?, 'et')", (ANNEE,))
        s302 = sv.creer(c, "et", "302", AUJ)
        places = places_depuis_tikz(FIXTURE_302.read_text(encoding="utf-8"))
        sv.enregistrer_plan(c, s302["id"], [{**p, "numero": None} for p in places], AUJ)
        s310 = sv.creer(c, "et", "310", AUJ)
        eleves = [("e1", "MARTIN", "Lison"), ("e2", "MOREAU", "Lison"),
                  ("e3", "DIAZ", "Younes"), ("e4", "ALI", "Maëva")]
        for eid, nom, prenom in eleves:
            c.execute("INSERT INTO eleves (id, nom, prenom) VALUES (?,?,?)",
                      (eid, nom, prenom))
            c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES (?, 'cl')",
                      (eid,))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="cl",
                    salle_id=s302["id"], aujourd_hui=AUJ)
        edt.ajouter(c, ANNEE, "mar", "M1", "et", classe_id="cl",
                    groupe="demi_classe_A", salle_id=s310["id"], aujourd_hui=AUJ)
    return {"s302": s302["id"], "s310": s310["id"]}


def P(eid, num, statut="libre", confirme=1):
    return {"eleve_id": eid, "numero": num, "statut": statut, "confirme": confirme}


class TestLecture:
    def test_salles_de_la_semaine_cours_classe_entiere(self, store, base):
        with store._conn() as c:
            assert pc.salles_de_la_semaine(c, "cl", S40) == [
                {"id": base["s302"], "nom": "302"}]

    def test_plan_vide(self, store, base):
        with store._conn() as c:
            p = pc.lire(c, "cl", base["s302"], AUJ, AUJ)
        assert p["source"] == "vide" and p["lundi"] == S40
        assert p["statut_semaine"] == "en_cours" and p["modifiable"]
        assert len(p["places"]) == 33 and len(p["non_places"]) == 4

    def test_etiquettes(self):
        e = [{"nom": "MARTIN", "prenom": "Lison"}, {"nom": "MOREAU", "prenom": "Lison"},
             {"nom": "MARCHAND", "prenom": "Léo"}, {"nom": "MARIN", "prenom": "Leo"},
             {"nom": "DIAZ", "prenom": "Younes"}]
        assert pc.etiquettes(e) == ["Lison Ma.", "Lison Mo.", "Léo Marc.",
                                    "Leo Mari.", "Younes D."]


class TestSaisie:
    def test_enregistrer_puis_relire(self, store, base):
        with store._conn() as c:
            p = pc.enregistrer(c, "cl", base["s302"], S40,
                               [P("e1", 1), P("e3", 5, "impose")], AUJ)
        assert p["source"] == "saisi"
        assert {(x["eleve_id"], x["numero"], x["statut"]) for x in p["placements"]} == {
            ("e1", 1, "libre"), ("e3", 5, "impose")}
        assert sorted(p["non_places"]) == ["e2", "e4"]

    def test_validations(self, store, base):
        with store._conn() as c:
            for mauvais in ([P("e1", 1), P("e2", 1)], [P("e1", 1), P("e1", 2)],
                            [P("e1", 99)], [P("zz", 1)], [P("e1", 1, "autre")]):
                with pytest.raises(pc.PlanErreur):
                    pc.enregistrer(c, "cl", base["s302"], S40, mauvais, AUJ)

    def test_semaine_passee_figee(self, store, base):
        with store._conn() as c:
            with pytest.raises(pc.SemaineFigee):
                pc.enregistrer(c, "cl", base["s302"], "2026-09-21", [], AUJ)
            assert pc.lire(c, "cl", base["s302"], "2026-09-21", AUJ)["modifiable"] is False

    def test_reconduction_libres_a_confirmer(self, store, base):
        with store._conn() as c:
            pc.enregistrer(c, "cl", base["s302"], S40,
                           [P("e1", 1), P("e3", 5, "impose")], AUJ)
            r = pc.lire(c, "cl", base["s302"], S42, AUJ)
            assert r["source"] == "reconduit" and r["reconduit_de"] == S40
            conf = {x["eleve_id"]: x["confirme"] for x in r["placements"]}
            assert conf == {"e1": 0, "e3": 1}
            # Rien n'est écrit tant qu'on ne modifie pas.
            assert c.execute("SELECT COUNT(*) FROM plans_classe").fetchone()[0] == 1
            # Confirmer crée le plan de la semaine.
            pc.enregistrer(c, "cl", base["s302"], S42,
                           [P("e1", 1), P("e3", 5, "impose")], AUJ)
            assert pc.lire(c, "cl", base["s302"], S42, AUJ)["source"] == "saisi"
            # La semaine 41 reste reconduite depuis la 40.
            assert pc.lire(c, "cl", base["s302"], S41, AUJ)["reconduit_de"] == S40
            # Réinitialiser la 42 : retour à la reconduction.
            assert pc.reinitialiser(c, "cl", base["s302"], S42, AUJ)["source"] == "reconduit"

    def test_reconduction_par_salle(self, store, base):
        with store._conn() as c:
            pc.enregistrer(c, "cl", base["s302"], S40, [P("e1", 1)], AUJ)
            assert pc.lire(c, "cl", base["s310"], S41, AUJ)["source"] == "vide"

    def test_eleve_sorti_et_arrive(self, store, base):
        with store._conn() as c:
            pc.enregistrer(c, "cl", base["s302"], S40, [P("e1", 1), P("e2", 2)], AUJ)
            c.execute("UPDATE eleves_classes SET date_sortie='2026-10-03' WHERE eleve_id='e2'")
            c.execute("INSERT INTO eleves (id, nom, prenom) VALUES ('e5', 'NEUF', 'Ana')")
            c.execute("INSERT INTO eleves_classes (eleve_id, classe_id, date_entree) "
                      "VALUES ('e5', 'cl', '2026-10-06')")
            r40 = pc.lire(c, "cl", base["s302"], S40, AUJ)
            r41 = pc.lire(c, "cl", base["s302"], S41, AUJ)
        assert "e5" not in r40["non_places"]
        assert [x["eleve_id"] for x in r41["placements"]] == ["e1"]
        assert "e5" in r41["non_places"] and "e2" not in r41["non_places"]
        assert r41["avertissements"] == []

    def test_place_disparue_dans_une_version_de_salle(self, store, base):
        with store._conn() as c:
            pc.enregistrer(c, "cl", base["s302"], S40, [P("e1", 1), P("e3", 33)], AUJ)
            # La salle est utilisée (EdT) : nouvelle version sans la place 33.
            plan = sv.lire_plan(c, base["s302"], AUJ)
            sv.enregistrer_plan(c, base["s302"],
                                [p for p in plan["places"] if p["numero"] != 33],
                                AUJ, date_effet=S41)
            r = pc.lire(c, "cl", base["s302"], S41, AUJ)
        assert [x["eleve_id"] for x in r["placements"]] == ["e1"]
        assert "e3" in r["non_places"] and "place 33" in r["avertissements"][0]


class TestAleatoire:
    def test_garde_les_imposes_et_impose_les_autres(self):
        res = pc.aleatoire([P("e1", 3, "impose"), P("e2", 4)], [1, 2, 3, 4, 5],
                           ["e1", "e2", "e3"], random.Random(7))
        par = {p["eleve_id"]: p for p in res}
        assert par["e1"]["numero"] == 3
        assert {p["statut"] for p in res} == {"impose"}
        assert len({p["numero"] for p in res}) == 3 and set(par) == {"e1", "e2", "e3"}

    def test_plus_d_eleves_que_de_places(self):
        res = pc.aleatoire([], [1, 2], ["a", "b", "c"], random.Random(1))
        assert len(res) == 2


class TestPdf:
    def test_page_avec_noms_et_page_numeros(self, store, base):
        with store._conn() as c:
            vide = pc.lire(c, "cl", base["s302"], S40, AUJ)
            pc.enregistrer(c, "cl", base["s302"], S40,
                           [P("e1", 1, "impose"), P("e4", 2, confirme=0)], AUJ)
            plein = pc.lire(c, "cl", base["s302"], S40, AUJ)
        t_vide, t_plein = pdf.page_tikz(vide), pdf.page_tikz(plein)
        assert "Lison" not in t_vide and "{33}" in t_vide
        assert "\\textbf{Lison" in t_plein and "\\textit{Maëva" in t_plein
        assert "Non placés" in t_plein and "Younes" in t_plein

    def test_echappement(self):
        assert pdf.echapper("A&B_%#") == r"A\&B\_\%\#"

    def test_plans_de_la_salle(self, store, base):
        with store._conn() as c:
            plans = pc.plans_de_la_salle(c, base["s302"], S40, AUJ)
            assert [p["classe"]["nom"] for p in plans] == ["4EME3"]
            assert pc.plans_de_la_salle(c, base["s310"], S40, AUJ) == []

    def test_compilation_reelle(self, store, base):
        import shutil
        if not shutil.which("pdflatex"):
            pytest.skip("pdflatex absent")
        with store._conn() as c:
            pc.enregistrer(c, "cl", base["s302"], S40, [P("e1", 1), P("e4", 2)], AUJ)
            plans = pc.plans_de_la_salle(c, base["s302"], S40, AUJ)
        octets = pdf.compiler(pdf.document(plans), shutil.which("pdflatex"))
        assert octets[:4] == b"%PDF"


class TestRoutes:
    def test_parcours(self, client, app):
        from services import annees_scolaires
        an = annees_scolaires.courante()
        auj = date.today()
        with app.json_store._conn() as c:
            c.execute("INSERT INTO etablissements (id, nom, etat) VALUES "
                      "('et', 'Collège', 'propose')")
            gh.peupler_defauts_si_vide(c, "et")
            c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                      "VALUES ('cl', '4EME3', 'N11', ?, 'et')", (an,))
            s = sv.creer(c, "et", "302", auj)
            sv.enregistrer_plan(c, s["id"], [{"x": 0, "y": 0}, {"x": 60, "y": 0}], auj)
            for eid in ("e1", "e2", "e3"):
                c.execute("INSERT INTO eleves (id, nom, prenom) VALUES (?, 'N', ?)",
                          (eid, eid))
                c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) "
                          "VALUES (?, 'cl')", (eid,))
            edt.ajouter(c, an, "lun", "M1", "et", classe_id="cl", salle_id=s["id"],
                        aujourd_hui=auj)
        sid = s["id"]
        r = client.get("/api/plans-classe/salles?classe_id=cl").get_json()
        assert [x["nom"] for x in r["salles"]] == ["302"]
        q = f"classe_id=cl&salle_id={sid}"
        assert client.get("/api/plans-classe?" + q).get_json()["source"] == "vide"
        r = client.put("/api/plans-classe", json={"classe_id": "cl", "salle_id": sid,
                                                  "placements": [P("e1", 1)]})
        assert r.status_code == 200 and r.get_json()["source"] == "saisi"
        r = client.post("/api/plans-classe/aleatoire",
                        json={"classe_id": "cl", "salle_id": sid}).get_json()
        assert len(r["placements"]) == 2 and len(r["non_places"]) == 1
        assert client.delete("/api/plans-classe?" + q).get_json()["source"] == "vide"
        assert client.get("/api/plans-classe?classe_id=zz&salle_id=" + sid).status_code == 404
