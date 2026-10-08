"""tests/test_v0_50_1_impression_plans.py — v0.50.1

Plans de classe imprimables en HTML + SVG (sans LaTeX) : même contenu que
l'ancien rendu TikZ (retiré en v0.50.2) — places, noms,
gras / italique, numéros, AESH, non placés —, une page A4 par plan.

Jeu de données : celui de tests/test_v0_39_0_plans_classe.py (salle 302
réelle, 33 places, 4 élèves fictifs).
"""
from datetime import date

from services import plans_classe as pc
from services import salles as sv, edt, grille_horaire as gh
from services.impression import plan_svg

from test_v0_39_0_plans_classe import AUJ, S40, P, store, base  # noqa: F401


def _places(page, classe=None):
    return [p for p in page["places"] if classe is None or p["classe"] == classe]


def test_plan_sans_eleve_place_numeros_seuls(store, base):
    with store._conn() as c:
        page = plan_svg(pc.lire(c, "cl", base["s302"], S40, AUJ))
    assert page["titre"] == "Plan de la salle 302 — 4EME3 — semaine du 28/09/2026"
    assert len(page["places"]) == 33 == len(_places(page, "num"))
    assert not page["avec_noms"] and page["non_places"] == []
    # Tient dans la page A4 (17 × 21 cm utiles), proportions conservées.
    assert page["largeur_cm"] <= 17.0 and page["hauteur_cm"] <= 21.0
    _, _, vw, vh = map(float, page["viewbox"].split())
    assert abs(page["largeur_cm"] / page["hauteur_cm"] - vw / vh) < 0.01


def test_plan_avec_noms_styles_et_non_places(store, base):
    with store._conn() as c:
        pc.enregistrer(c, "cl", base["s302"], S40,
                       [P("e1", 1, "impose"), P("e4", 2, confirme=0)], AUJ)
        page = plan_svg(pc.lire(c, "cl", base["s302"], S40, AUJ))
    assert page["avec_noms"]
    imp, = _places(page, "impose")
    conf, = _places(page, "a-confirmer")
    assert "Lison" in " ".join(l["texte"] for l in imp["lignes"])
    assert "Maëva" in " ".join(l["texte"] for l in conf["lignes"])
    assert len(_places(page, "num-gris")) == 31
    assert any("Younes" in n for n in page["non_places"])


def test_place_aesh(store, base):
    with store._conn() as c:
        pc.enregistrer(c, "cl", base["s302"], S40, [P("e1", 1)], AUJ, reservations=[2])
        page = plan_svg(pc.lire(c, "cl", base["s302"], S40, AUJ))
    aesh, = _places(page, "aesh")
    assert aesh["lignes"][0]["texte"] == "AESH"


def test_rotation_et_nom_long_compresse():
    plan = {"salle": {"nom": "S"}, "classe": {"nom": "C"}, "lundi": "2026-09-28",
            "places": [{"numero": 1, "x": 0, "y": 0, "angle": 30},
                       {"numero": 2, "x": 100, "y": 0, "angle": 0}],
            "eleves": [{"id": "a", "etiquette": "Marie-Bénédicte DE LA FONTAINE-DUVAL"}],
            "placements": [{"eleve_id": "a", "numero": 1, "statut": "libre", "confirme": 1}],
            "non_places": [], "reservations": []}
    page = plan_svg(plan)
    p1, p2 = page["places"]
    assert p1["angle"] == 30 and p2["angle"] == 0
    assert [l["texte"] for l in p1["lignes"]] == ["Marie-Bénédicte", "DE LA FONTAINE-DUVAL"]
    assert p1["lignes"][1]["longueur"] is not None      # compressée
    assert p2["lignes"][0]["longueur"] is None          # « 2 » tient


def test_salle_sans_place():
    page = plan_svg({"salle": {"nom": "S"}, "classe": {"nom": "C"},
                     "lundi": "2026-09-28", "places": []})
    assert page["vide"]


# ── Route et gabarit ─────────────────────────────────────────────────────────

def _jeu_route(app):
    from services import annees_scolaires
    an, auj = annees_scolaires.courante(), date.today()
    with app.json_store._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat) VALUES ('et', 'Collège', 'propose')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('cl', '4<A> & co', 'N11', ?, 'et')", (an,))
        s = sv.creer(c, "et", "302", auj)
        sv.enregistrer_plan(c, s["id"], [{"x": 0, "y": 0}, {"x": 60, "y": 0, "angle": 15}], auj)
        vide = sv.creer(c, "et", "310", auj)
        for eid in ("e1", "e2", "e3"):
            c.execute("INSERT INTO eleves (id, nom, prenom) VALUES (?, 'N', ?)", (eid, eid))
            c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES (?, 'cl')", (eid,))
        edt.ajouter(c, an, "lun", "M1", "et", classe_id="cl", salle_id=s["id"], aujourd_hui=auj)
    return s["id"], vide["id"]


def test_route_une_classe(client, app):
    sid, _ = _jeu_route(app)
    client.put("/api/plans-classe", json={"classe_id": "cl", "salle_id": sid,
                                          "placements": [P("e1", 1, "impose")]})
    r = client.get(f"/impression/plans-classe?classe_id=cl&salle_id={sid}")
    assert r.status_code == 200 and r.mimetype == "text/html"
    html = r.get_data(as_text=True)
    assert "@page { size: A4 portrait; margin: 1.5cm; }" in html
    assert html.count("<svg") == 1 and html.count('<section class="plan-page">') == 1
    assert "4&lt;A&gt; &amp; co" in html and "4<A>" not in html
    assert 'class="place impose"' in html and ">e1</text>" in html
    assert 'transform="rotate(15.0 60.0 0.0)"' in html
    assert "<b>Non placés :</b>" in html
    assert "Tableau" in html


def test_route_plans_de_la_salle(client, app):
    sid, vide = _jeu_route(app)
    html = client.get(f"/impression/plans-classe?salle_id={sid}").get_data(as_text=True)
    assert html.count('<section class="plan-page">') == 1
    html = client.get(f"/impression/plans-classe?salle_id={vide}").get_data(as_text=True)
    assert "Aucun plan de classe pour cette salle cette semaine." in html


def test_route_classe_inconnue(client, app):
    sid, _ = _jeu_route(app)
    assert client.get(f"/impression/plans-classe?classe_id=zz&salle_id={sid}"
                      ).status_code == 404
