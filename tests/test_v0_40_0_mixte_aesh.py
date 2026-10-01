"""tests/test_v0_40_0_mixte_aesh.py — v0.40.0

Sexe des élèves (normalisation, import Pronote qui complète les élèves
existants sans lire les colonnes sensibles, saisie manuelle), voisinage des
places (même îlot + côté commun, jamais la diagonale), aléatoire mixte,
places réservées AESH (validation, reconduction, besoin de la semaine,
aléatoire qui ne les touche pas, impression).

Le CSV d'import est SYNTHÉTIQUE : jamais de vraie liste d'élèves dans le dépôt.
"""
import random
from datetime import date
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore
from services import edt, grille_horaire as gh, salles as sv
from services import eleves_sexe
from services import plans_classe as pc
from services import plan_classe_pdf as pdf
from services.plan_salle_tikz import places_depuis_tikz

ANNEE = "2026-2027"
AUJ = date(2026, 10, 1)
S40, S41 = "2026-09-28", "2026-10-05"
FIXTURE_302 = Path(__file__).parent / "fixtures" / "plan_salle_302.tex"


@pytest.fixture
def store(tmp_path):
    return SqliteStore(tmp_path / "data")


@pytest.fixture
def base(store):
    with store._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat) VALUES ('et', 'C', 'propose')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('cl', '4EME3', 'N11', ?, 'et')", (ANNEE,))
        s = sv.creer(c, "et", "302", AUJ)
        places = places_depuis_tikz(FIXTURE_302.read_text(encoding="utf-8"))
        sv.enregistrer_plan(c, s["id"], [{**p, "numero": None} for p in places], AUJ)
        for i, sexe in enumerate("MFMFMF"):
            c.execute("INSERT INTO eleves (id, nom, prenom, sexe) VALUES (?,?,?,?)",
                      (f"e{i}", f"NOM{i}", f"P{i}", sexe))
            c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES (?, 'cl')",
                      (f"e{i}",))
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="cl", salle_id=s["id"],
                    nb_aesh=1, aujourd_hui=AUJ)
        edt.ajouter(c, ANNEE, "ven", "M1", "et", classe_id="cl", salle_id=s["id"],
                    nb_aesh=2, aujourd_hui=AUJ)
    return s["id"]


def P(eid, num, statut="libre"):
    return {"eleve_id": eid, "numero": num, "statut": statut, "confirme": 1}


# ── Sexe ─────────────────────────────────────────────────────────────────────

def test_normaliser():
    assert [eleves_sexe.normaliser(v) for v in ("M", "f", " F ", "", None, "Masculin")] \
        == ["M", "F", "F", "", "", "M"]
    with pytest.raises(eleves_sexe.SexeErreur):
        eleves_sexe.normaliser("X")


def test_migration_colonne_sexe(store):
    with store._conn() as c:
        assert "sexe" in {r[1] for r in c.execute("PRAGMA table_info(eleves)")}


def test_import_complete_les_existants_sans_colonnes_sensibles(client, app):
    from services import annees_scolaires
    an = annees_scolaires.courante()
    r = client.post("/api/classes", json={"nom": "4EME9", "annee": an})
    cid = r.get_json()["id"]
    assert client.post(f"/api/classes/{cid}/eleves",
                       json={"nom": "DUPONT", "prenom": "Léa"}).status_code == 200
    csv = ("Numero,Nom,Prenom,DateNaissance,PrenomUsage,Sexe,Classe de rattachement,"
           "Projet d'accompagnement\n"
           "1,DUPONT ,Léa,01/01/2013,,F,4EME9,PAI fictif\n"
           "2,MARTIN,Noé,02/02/2013,,M,4EME9,\n"
           "3,DURAND,Sam,03/03/2013,,?,4EME9,\n")
    res = client.post(f"/api/classes/{cid}/eleves/import", json={"csv": csv}).get_json()
    assert res["ajouts"] == 2 and res["ignores"] == 1
    assert res["sexes_mis_a_jour"] == 2
    sexes = {e["nom"]: e["sexe"] for e in res["eleves"]}
    assert sexes == {"DUPONT": "F", "MARTIN": "M", "DURAND": ""}
    with app.json_store._conn() as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(eleves)")}
    assert not cols & {"date_naissance", "datenaissance", "projet", "pai"}
    eid = next(e["id"] for e in res["eleves"] if e["nom"] == "DURAND")
    assert client.put(f"/api/eleves/{eid}/sexe", json={"sexe": "M"}).get_json()["sexe"] == "M"
    assert client.put(f"/api/eleves/{eid}/sexe", json={"sexe": "Z"}).status_code == 400


# ── Voisinage ────────────────────────────────────────────────────────────────

def test_voisins_meme_ilot_cote_commun():
    places = [{"numero": 1, "x": 0, "y": 0, "angle": 0, "ilot": "i1"},
              {"numero": 2, "x": 60, "y": 0, "angle": 0, "ilot": "i1"},
              {"numero": 3, "x": 0, "y": 40, "angle": 0, "ilot": "i1"},
              {"numero": 4, "x": 60, "y": 40, "angle": 0, "ilot": "i1"},
              {"numero": 5, "x": 120, "y": 0, "angle": 0, "ilot": ""}]
    assert pc.voisins(places) == [[1, 2], [1, 3], [2, 4], [3, 4]]   # ni 1-4 ni 2-5


def test_voisins_de_la_302():
    places = places_depuis_tikz(FIXTURE_302.read_text(encoding="utf-8"))
    v = pc.voisins(places)
    assert len(v) == 31 and [1, 2] in v and [3, 4] in v and [3, 6] not in v


# ── Aléatoire mixte ──────────────────────────────────────────────────────────

def test_aleatoire_mixte_damier_optimal():
    paires = [[1, 2], [1, 3], [2, 4], [3, 4]]
    sexes = {"a": "M", "b": "M", "c": "F", "d": "F"}
    for graine in range(5):
        r = pc.aleatoire_mixte([], [1, 2, 3, 4], sexes, paires,
                               random.Random(graine), essais=1, ameliorations=200)
        assert pc.score_mixite(r, paires, sexes) == 4
        assert {p["statut"] for p in r} == {"impose"}


def test_aleatoire_mixte_garde_imposes_et_reservations():
    paires = [[1, 2], [2, 3], [3, 4]]
    sexes = {"a": "M", "b": "M", "c": "F"}
    r = pc.aleatoire_mixte([P("a", 4, "impose")], [1, 2, 3, 4, 5], sexes, paires,
                           random.Random(1), reservees=[5])
    par = {p["eleve_id"]: p["numero"] for p in r}
    assert par["a"] == 4 and 5 not in par.values()
    assert pc.score_mixite(r, paires, sexes) == 2          # c entre a et b


def test_aleatoire_pur_ne_touche_pas_les_reservations():
    r = pc.aleatoire([], [1, 2, 3], ["a", "b", "c"], random.Random(3), reservees=[2])
    assert sorted(p["numero"] for p in r) == [1, 3]


# ── AESH ─────────────────────────────────────────────────────────────────────

class TestAesh:
    def test_besoin_de_la_semaine_et_avertissement(self, store, base):
        with store._conn() as c:
            p = pc.lire(c, "cl", base, S40, AUJ)
        assert p["aesh"]["besoin"] == 2 and len(p["aesh"]["seances"]) == 2
        assert p["reservations"] == []
        assert any("AESH : 2 places" in a for a in p["avertissements"])

    def test_reserver_reconduire_et_valider(self, store, base):
        with store._conn() as c:
            p = pc.enregistrer(c, "cl", base, S40, [P("e0", 1)], AUJ, reservations=[2, 3])
            assert p["reservations"] == [2, 3]
            assert not any("AESH" in a for a in p["avertissements"])
            # Placements seuls : les réservations sont conservées.
            p = pc.enregistrer(c, "cl", base, S40, [P("e0", 4)], AUJ)
            assert p["reservations"] == [2, 3]
            # Reconduites la semaine suivante.
            assert pc.lire(c, "cl", base, S41, AUJ)["reservations"] == [2, 3]
            with pytest.raises(pc.PlanErreur):     # réservée ET occupée
                pc.enregistrer(c, "cl", base, S40, [P("e0", 2)], AUJ, reservations=[2])
            with pytest.raises(pc.PlanErreur):
                pc.enregistrer(c, "cl", base, S40, [], AUJ, reservations=[99])
            # Réinitialiser supprime aussi les réservations de la semaine.
            pc.reinitialiser(c, "cl", base, S40, AUJ)
            assert pc.lire(c, "cl", base, S40, AUJ)["reservations"] == []

    def test_route_aleatoire_mixte(self, store, base):
        # Service + route : appel direct de la logique de route via le service.
        with store._conn() as c:
            pc.enregistrer(c, "cl", base, S40, [], AUJ, reservations=[1])
            p = pc.lire(c, "cl", base, S40, AUJ)
            r = pc.aleatoire_mixte(p["placements"], [x["numero"] for x in p["places"]],
                                   {e["id"]: e["sexe"] for e in p["eleves"]},
                                   p["voisins"], random.Random(0),
                                   reservees=p["reservations"])
            assert len(r) == 6 and 1 not in {x["numero"] for x in r}
            # 3 garçons, 3 filles : 3 paires mixtes au moins sont atteignables.
            assert pc.score_mixite(r, p["voisins"], {e["id"]: e["sexe"] for e in p["eleves"]}) >= 3

    def test_pdf_affiche_aesh(self, store, base):
        with store._conn() as c:
            pc.enregistrer(c, "cl", base, S40, [P("e0", 1)], AUJ, reservations=[2])
            t = pdf.page_tikz(pc.lire(c, "cl", base, S40, AUJ))
        assert "{AESH}" in t
