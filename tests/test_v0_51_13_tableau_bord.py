"""tests/test_v0_51_13_tableau_bord.py — v0.51.13

Tableau de bord de l'appli de classe : tuiles Établissements (salles, plan
saisi) et Classes (effectif, plan de classe saisi), routes et profils ;
tuile Journée (données de la planification hebdo du jour) ; écran Échanges
(sous-onglet unique, imports compris) ; compteurs de la base par appli.
Données fictives.
"""
from datetime import date
from pathlib import Path

import pytest

from app import create_app
from services import edt, grille_horaire as gh, salles as sv
from services import plans_classe as pc
from services import tableau_bord as tb
from services.plan_salle_tikz import places_depuis_tikz

ANNEE = "2026-2027"
AUJ = date(2026, 10, 1)
S40 = "2026-09-28"
RACINE = Path(__file__).resolve().parent.parent
FIXTURE_302 = Path(__file__).parent / "fixtures" / "plan_salle_302.tex"


@pytest.fixture
def classe(data_dir):
    app = create_app(data_dir, profil="classe")
    app.config["TESTING"] = True
    st = app.json_store
    with st._conn() as c:
        c.execute("INSERT INTO etablissements (id, nom, etat) VALUES ('et', 'Collège B', 'valide')")
        c.execute("INSERT INTO etablissements (id, nom, etat) VALUES ('ea', 'Collège A', 'valide')")
        gh.peupler_defauts_si_vide(c, "et")
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('cl', '4EME3', 'N11', ?, 'et')", (ANNEE,))
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('c6', '6EME1', 'N09', ?, 'et')", (ANNEE,))
        c.execute("INSERT INTO classes (id, nom, niveau, annee, etablissement_id) "
                  "VALUES ('cx', '5EME2', 'N10', '2025-2026', 'et')")
        s302 = sv.creer(c, "et", "302", AUJ)
        places = places_depuis_tikz(FIXTURE_302.read_text(encoding="utf-8"))
        sv.enregistrer_plan(c, s302["id"], [{**p, "numero": None} for p in places], AUJ)
        s310 = sv.creer(c, "et", "310", AUJ)
        s0 = sv.creer(c, "et", "Ancienne", AUJ)
        for k, (eid, nom) in enumerate([("e1", "MARTIN"), ("e2", "MOREAU"), ("e3", "DIAZ")]):
            c.execute("INSERT INTO eleves (id, nom, prenom) VALUES (?,?,'Fictif')", (eid, nom))
            c.execute("INSERT INTO eleves_classes (eleve_id, classe_id) VALUES (?, 'cl')", (eid,))
        c.execute("INSERT INTO eleves (id, nom, prenom) VALUES ('e9', 'SORTI', 'X')")
        c.execute("INSERT INTO eleves_classes (eleve_id, classe_id, date_sortie) "
                  "VALUES ('e9', 'cl', '2026-09-15')")
        edt.ajouter(c, ANNEE, "lun", "M1", "et", classe_id="cl", salle_id=s302["id"],
                    aujourd_hui=AUJ)
        pc.enregistrer(c, "cl", s302["id"], S40,
                       [{"eleve_id": "e1", "numero": 1, "statut": "libre", "confirme": 1}], AUJ)
    return {"app": app, "s302": s302["id"], "s310": s310["id"], "s0": s0["id"]}


def test_etablissements_et_salles(classe):
    r = classe["app"].test_client().get("/api/tableau-bord/etablissements")
    assert r.status_code == 200
    etabs = r.get_json()["etablissements"]
    assert [e["nom"] for e in etabs] == ["Collège A", "Collège B"]
    assert etabs[0]["salles"] == []
    salles = {s["nom"]: s["plan"] for s in etabs[1]["salles"]}
    assert salles["302"] is True and salles["310"] is False


def test_salle_archivee_absente(classe):
    with classe["app"].json_store._conn() as c:
        c.execute("UPDATE salles SET archivee=1 WHERE id=?", (classe["s0"],))
        noms = [s["nom"] for s in tb.etablissements_et_salles(c, AUJ)[1]["salles"]]
    assert "Ancienne" not in noms


def test_classes_de_l_annee(classe):
    r = classe["app"].test_client().get(f"/api/tableau-bord/classes?annee={ANNEE}")
    assert r.status_code == 200
    d = r.get_json()
    assert d["annee"] == ANNEE
    assert [(c["nom"], c["effectif"], c["plan"]) for c in d["classes"]] == [
        ("4EME3", 3, True), ("6EME1", 0, False)]              # sortie non comptée
    assert d["classes"][0]["etablissement_id"] == "et"


def test_classes_sans_plans_saisis(data_dir):
    """Base sans table de plans de classe (jamais ouverte) : pas d'erreur."""
    app = create_app(data_dir, profil="classe")
    with app.json_store._conn() as c:
        c.execute("DROP TABLE IF EXISTS plan_placements")
        c.execute("DROP TABLE IF EXISTS plans_classe")
    assert app.test_client().get("/api/tableau-bord/classes").status_code == 200


def test_journee_donnees_de_la_planification(classe):
    """La tuile Journée lit la planification hebdo de la semaine du jour."""
    r = classe["app"].test_client().get(f"/api/planification-hebdo?annee={ANNEE}&lundi={S40}")
    d = r.get_json()
    lundi = [c for c in d["cases"] if c["date"] == S40]
    assert [(c["creneau"], c["classe"]) for c in lundi] == [("M1", "4EME3")]


def test_routes_par_profil(data_dir):
    atelier = create_app(data_dir, profil="atelier").test_client()
    assert atelier.get("/api/tableau-bord/classes").status_code == 404
    assert atelier.get("/api/tableau-bord/etablissements").status_code == 404
    complet = create_app(data_dir, profil="complet").test_client()
    assert complet.get("/api/tableau-bord/classes").status_code == 200


def test_ecran_echanges_et_tuiles():
    html = (RACINE / "templates" / "index.html").read_text(encoding="utf-8")
    # Un seul sous-onglet « Échanges », imports à la main compris.
    assert 'id="admin-echanges-btn" data-profils="atelier classe"' in html
    assert "adminSousOnglet('importpub')" not in html and "adminSousOnglet('importusage')" not in html
    i, j = html.index('id="admin-echanges"'), html.index("<!-- /admin-echanges -->")
    bloc = html[i:j]
    for zone in ("ech-publication", "ech-usage", "ech-depot", "ech-instance",
                 'id="admin-importusage" data-profils="atelier"',
                 'id="admin-importpub" data-profils="classe"'):
        assert zone in bloc, zone
    # Tuiles de classe ; « Séances de la semaine » remplacée par Journée.
    for zone in ("tdb-journee", "tdb-classes", "tdb-etabs", "tdb-usage", "tdb-publication"):
        assert f'id="{zone}"' in html
    assert 'id="tdb-seances"' not in html
    assert '<script src="/static/tdb_tuiles.js"></script>' in html
