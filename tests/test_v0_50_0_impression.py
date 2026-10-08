"""tests/test_v0_50_0_impression.py — v0.50.0

Documents imprimables hors ateliers en HTML + CSS d'impression (sans LaTeX) :
planning des automatismes, planning MER d'une classe, aperçu théorique MER.

Le jeu de données est celui du test de non-régression de la projection
(v0.41.1) : EdT A/B, MER panachées, vacances et fériés fictifs. On vérifie
que la page HTML porte une case par jour des blocs de frise (v0.50.2 : la
comparaison avec l'ancien .tex a disparu avec les routes PDF LaTeX ; le
HTML lui-même est figé dans la capture v0.41.1).
"""
import re

import pytest

from test_v0_41_1_projection_figee import ANNEE, _calendrier_fictif, _donnees


@pytest.fixture
def jeu(app, client, monkeypatch):
    _calendrier_fictif(monkeypatch)
    _donnees(app.json_store)
    return client


def _blocs_attendus(app, module, fonction, *args):
    """Blocs de frise calculés par la route (même source que la page)."""
    import importlib
    m = importlib.import_module(module)
    with app.test_request_context(f"/?annee={ANNEE}"):
        return getattr(m, fonction)(*args)


def _compter(blocs):
    jours = [j for b in blocs if b["type"] == "periode" for j in b["jours"]]
    return jours, sum(1 for b in blocs if b["type"] == "vacances")


def _cases(html):
    return re.findall(r'<span class="case case-(\w+)">', html)


# ── Planning des automatismes ────────────────────────────────────────────────

def test_automatismes_page_a3_et_une_case_par_jour(app, jeu):
    r = jeu.get(f"/impression/classes/cl/planning-automatismes?annee={ANNEE}")
    assert r.status_code == 200
    assert r.mimetype == "text/html"
    html = r.get_data(as_text=True)
    assert "@page { size: A3 landscape; margin: 1cm; }" in html
    assert "impression.css" in html
    assert "Planning des automatismes (Leitner)" in html
    assert "4EME3 — année 2026-2027" in html
    _, blocs = _blocs_attendus(app, "routes.leitner", "_blocs", "cl", ANNEE)
    jours, nb_vac = _compter(blocs)
    cases = _cases(html)
    assert len(cases) == len(jours) > 0
    assert cases == [j["kind"] for j in jours]
    assert html.count('<div class="vacances">') == nb_vac > 0
    # Enveloppes en symboles Unicode : une par enveloppe (légende exclue).
    nb_env = sum(html.count(c) for c in "①②③④")
    legende = 4   # la légende contient ①②③④
    assert nb_env - legende == sum(len(j.get("enveloppes") or [])
                                   for j in jours if j["kind"] == "seance")


def test_automatismes_classe_inconnue_404(jeu):
    r = jeu.get(f"/impression/classes/nope/planning-automatismes?annee={ANNEE}")
    assert r.status_code == 404


def test_nom_de_classe_echappe(app, jeu):
    with app.json_store._conn() as c:
        c.execute("UPDATE classes SET nom='4<b>3 & co' WHERE id='cl'")
    html = jeu.get(f"/impression/classes/cl/planning-automatismes?annee={ANNEE}"
                   ).get_data(as_text=True)
    assert "4&lt;b&gt;3 &amp; co" in html
    assert "4<b>3" not in html


# ── Planning MER d'une classe ────────────────────────────────────────────────

def test_planning_mer_page_a3_et_une_case_par_jour(app, jeu):
    r = jeu.get(f"/impression/classes/cl/planning-mer?annee={ANNEE}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "@page { size: A3 landscape; margin: 1cm; }" in html
    assert "Planning de progression MER" in html
    assert 'class="frise frise-mer"' in html
    d = _blocs_attendus(app, "routes.progression_mer", "_planning_mer_classe",
                        "cl", ANNEE)
    jours, nb_vac = _compter(d["blocs"])
    assert _cases(html) == [j["kind"] for j in jours] and jours
    assert html.count('<div class="vacances">') == nb_vac > 0


def test_planning_mer_classe_inconnue_404(jeu):
    assert jeu.get(f"/impression/classes/nope/planning-mer?annee={ANNEE}"
                   ).status_code == 404


# ── Aperçu théorique ─────────────────────────────────────────────────────────

def test_lignes_theoriques_plages_enchainees():
    from services.impression import lignes_theoriques
    lignes, total = lignes_theoriques([
        {"libelle": "Fractions", "sequence_code": "M01", "nb_seances": 3},
        {"libelle": "Calcul mental", "sequence_nom": "Nombres", "nb_seances": 1},
        {"libelle": "Vide", "nb_seances": 0},
    ])
    assert total == 4
    assert [l["plage"] for l in lignes] == ["séances 1–3", "séances 4", "—"]
    assert lignes[0]["sequence"] == "M01" and lignes[1]["sequence"] == "Nombres"


def _prog_id(app):
    from services import progression_mer as pm
    with app.json_store._conn() as c:
        return pm.creer_ou_lire(c, "N11", ANNEE)["id"]


def test_theorique_sans_partie(app, jeu):
    pid = _prog_id(app)
    r = jeu.get(f"/impression/progression-mer/{pid}/planning-theorique?annee={ANNEE}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "@page { size: A4 portrait; margin: 2cm; }" in html
    assert "Aucune partie posée." in html
    assert "Total : 0 séance(s)" in html


def test_theorique_avec_parties(app, jeu, monkeypatch):
    from routes import progression_mer as rpm
    pid = _prog_id(app)
    vrai = rpm.svc._lire

    def _lire(conn, prog_id):
        p = vrai(conn, prog_id)
        p["parties"] = [{"libelle": "Fractions & co", "sequence_code": "M01",
                         "nb_seances": 3},
                        {"libelle": "Calcul", "sequence_code": "M02",
                         "nb_seances": 2}]
        return p
    monkeypatch.setattr(rpm.svc, "_lire", _lire)
    html = jeu.get(f"/impression/progression-mer/{pid}/planning-theorique"
                   f"?annee={ANNEE}").get_data(as_text=True)
    assert "Total : 5 séance(s)" in html
    assert "<b>Fractions &amp; co</b>" in html
    assert "séances 4–5" in html


def test_theorique_inconnue_404(jeu):
    assert jeu.get("/impression/progression-mer/nope/planning-theorique"
                   ).status_code == 404


# ── Gabarits seuls (blocs synthétiques) ──────────────────────────────────────

BLOCS = [
    {"type": "periode", "jours": [
        {"jour_court": "lun 07/09", "creneau_code": "M1", "kind": "seance",
         "enveloppes": [1, 3], "mer_libelle": "Fractions", "mer_rang": 2, "mer_nb": 3},
        {"jour_court": "mer 11/11", "kind": "ferie"},
        {"jour_court": "jeu 03/12", "kind": "indispo"},
        {"jour_court": "ven 04/12", "kind": "seance", "enveloppes": [],
         "epuise": True},
    ]},
    {"type": "vacances", "nom": "Vacances de Noël"},
]


def _rendre(app, gabarit, **kw):
    from flask import render_template
    with app.test_request_context("/"):
        return render_template(gabarit, annee=ANNEE, **kw)


def test_gabarit_automatismes_cases(app):
    html = _rendre(app, "impression/planning_automatismes.html",
                   classe_nom="6A", blocs=BLOCS)
    assert _cases(html) == ["seance", "ferie", "indispo", "seance"]
    assert '<span class="enveloppes">① ③</span>' in html
    assert '<span class="enveloppes">--</span>' in html
    assert '<span class="ferie">férié</span>' in html
    assert '<span class="indispo">∅</span>' in html
    assert "lun 07/09 <b>M1</b>" in html
    assert '<div class="vacances">Vacances de Noël</div>' in html


def test_gabarit_mer_cases(app):
    html = _rendre(app, "impression/planning_mer.html", classe_nom="6A",
                   ref_nom="M2026_6A", blocs=BLOCS)
    assert '<span class="mer-libelle">Fractions</span>' in html
    assert '<span class="mer-rang">(2/3)</span>' in html
    assert "réf. M2026_6A" in html
    # Progression épuisée : tiret.
    assert html.count('<span class="ferie">--</span>') == 1
