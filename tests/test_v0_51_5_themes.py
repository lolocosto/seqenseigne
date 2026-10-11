"""tests/test_v0_51_5_themes.py — v0.51.5

Thèmes des référentiels externes (principal et MER) : création (codes A, B…,
couleur), séquences regroupées par thème dans l'ordre des thèmes, déplacement
d'une séquence à l'intérieur de son thème, changement de thème, déplacement
et suppression d'un thème, codes recalculés en conception seulement, alertes,
export JSON, routes et profils.
"""
from datetime import date

import pytest

from app import create_app
from persistence.sqlite_store import SqliteStore
from services import format_referentiel as fmt
from services import referentiel_principal_externe as rpe

ANNEE = "2026-2027"
AUJ = date(2026, 9, 1)
P = "/api/referentiels-principaux-externes"


@pytest.fixture
def st(tmp_path):
    return SqliteStore(tmp_path / "data")


def _vue(c, rid):
    """[(code séquence, nom, code thème)] dans l'ordre."""
    return [(s["code"], s["nom"], s["theme_code"]) for s in rpe.lire(c, rid, AUJ)["sequences"]]


def _themes(c, rid):
    return [(t["code"], t["nom"]) for t in rpe.lister_themes(c, rid)]


def _ref(c, type_ref="principal"):
    rid = rpe.creer(c, "N09", ANNEE, type_ref=type_ref)["id"]
    rpe.ajouter_theme(c, rid, "Nombres et calculs", "nombres")
    rpe.ajouter_theme(c, rid, "Grandeurs et mesures", "grandeurs")
    return rid


def test_creation_des_themes(st):
    with st._conn() as c:
        rid = rpe.creer(c, "N09", ANNEE, type_ref="mer")["id"]
        assert rpe.lire(c, rid, AUJ)["alertes_themes"] == \
            ["Aucun thème : définissez les thèmes du référentiel."]
        a = rpe.ajouter_theme(c, rid, "Nombres et calculs", "nombres")
        b = rpe.ajouter_theme(c, rid, "Espace et géométrie")
        assert (a["code"], a["couleur"], b["code"], b["couleur"]) == ("A", "nombres", "B", "")
        with pytest.raises(rpe.RefExtErreur):
            rpe.ajouter_theme(c, rid, "nombres et calculs")          # doublon
        with pytest.raises(rpe.RefExtErreur):
            rpe.ajouter_theme(c, rid, "Données", "fuchsia")           # couleur inconnue
        with pytest.raises(rpe.RefExtErreur):
            rpe.ajouter_theme(c, rid, " ")
        rpe.modifier_theme(c, rid, "B", {"nom": "Géométrie", "couleur": "geometrie"})
        assert rpe.lire(c, rid, AUJ)["themes"][1]["couleur"] == "geometrie"
        assert rpe.lire(c, rid, AUJ)["alertes_themes"] == []


def test_sequences_regroupees_par_theme(st):
    with st._conn() as c:
        rid = _ref(c)
        assert rpe.ajouter_sequence(c, rid, "Longueurs", "B")["code"] == "S01"
        r = rpe.ajouter_sequence(c, rid, "Entiers", "A")      # se place avant le thème B
        assert r["code"] == "S01" and r["numero"] == 1
        rpe.ajouter_sequence(c, rid, "Fractions", "A")
        rpe.ajouter_sequence(c, rid, "Divers")                 # sans thème : en dernier
        assert _vue(c, rid) == [("S01", "Entiers", "A"), ("S02", "Fractions", "A"),
                                ("S03", "Longueurs", "B"), ("S04", "Divers", None)]
        assert rpe.lire(c, rid, AUJ)["alertes_themes"] == ["S04 « Divers » : sans thème."]
        # Déplacement : à l'intérieur du thème seulement.
        assert rpe.deplacer_sequence(c, rid, "S03", -1, AUJ) == {"recode": False}
        rpe.deplacer_sequence(c, rid, "S02", -1, AUJ)
        assert [x[1] for x in _vue(c, rid)] == ["Fractions", "Entiers", "Longueurs", "Divers"]
        with pytest.raises(rpe.RefExtErreur):
            rpe.ajouter_sequence(c, rid, "X", "Z")


def test_changer_de_theme(st):
    with st._conn() as c:
        rid = _ref(c)
        for nom, th in (("Entiers", "A"), ("Longueurs", "B"), ("Aires", "B")):
            rpe.ajouter_sequence(c, rid, nom, th)
        rpe.ajouter_partie(c, rid, "S03", 0, AUJ)
        rpe.ajouter_objectif(c, rid, "S03", 1, "Calculer une aire", 2)
        # « Aires » (S03) passe en A : fin du thème A.
        assert rpe.affecter_theme(c, rid, "S03", "A", AUJ) == {"code": "S02"}
        assert _vue(c, rid) == [("S01", "Entiers", "A"), ("S02", "Aires", "A"),
                                ("S03", "Longueurs", "B")]
        objs = rpe.lire(c, rid, AUJ)["sequences"][1]["parties"][0]["objectifs"]
        assert objs[0]["nom"] == "Calculer une aire"
        rpe.affecter_theme(c, rid, "S01", None, AUJ)
        assert _vue(c, rid)[-1] == ("S03", "Entiers", None)


def test_deplacer_et_supprimer_un_theme(st):
    with st._conn() as c:
        rid = _ref(c)
        rpe.ajouter_sequence(c, rid, "Entiers", "A")
        rpe.ajouter_sequence(c, rid, "Longueurs", "B")
        assert rpe.deplacer_theme(c, rid, "B", -1) == {"recode": True}
        # Le thème et ses séquences passent en tête ; codes recalculés.
        assert _themes(c, rid) == [("A", "Grandeurs et mesures"), ("B", "Nombres et calculs")]
        assert _vue(c, rid) == [("S01", "Longueurs", "A"), ("S02", "Entiers", "B")]
        rpe.supprimer_theme(c, rid, "A")
        assert _themes(c, rid) == [("A", "Nombres et calculs")]
        assert _vue(c, rid) == [("S01", "Entiers", "A"), ("S02", "Longueurs", None)]
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []


def test_codes_conserves_hors_conception(st):
    with st._conn() as c:
        rid = _ref(c)
        rpe.ajouter_sequence(c, rid, "Entiers", "A")
        rpe.ajouter_sequence(c, rid, "Longueurs", "B")
        c.execute("INSERT INTO etablissements (id, nom, etat) VALUES ('et', 'C', 'propose')")
    st.ecrire_progression({"niveau": "N09", "annee": ANNEE, "etablissement_id": "et",
                           "referentiel_id": rid, "creneaux": []})
    with st._conn() as c:
        assert rpe.deplacer_theme(c, rid, "B", -1) == {"recode": False}
        assert _themes(c, rid) == [("B", "Grandeurs et mesures"), ("A", "Nombres et calculs")]
        assert _vue(c, rid) == [("S02", "Longueurs", "B"), ("S01", "Entiers", "A")]
        assert rpe.ajouter_theme(c, rid, "Géométrie")["code"] == "C"


def test_export_json(st):
    with st._conn() as c:
        rid = _ref(c, type_ref="mer")
        rpe.ajouter_sequence(c, rid, "Tables", "A")
        rpe.ajouter_sequence(c, rid, "Conversions", "B")
        rpe.deplacer_theme(c, rid, "B", -1)
        doc = fmt.construire(c, rid)
    th = doc["structure"]["themes"]
    assert [(t["code"], t["nom"], t["couleur"], t["ordre"]) for t in th] == \
        [("A", "Grandeurs et mesures", "grandeurs", 1), ("B", "Nombres et calculs", "nombres", 2)]
    assert [(s["code"], s["theme"]) for s in doc["structure"]["decoupage"]] == \
        [("M01", "A"), ("M02", "B")]
    assert fmt.valider(doc) == []


def test_routes_et_profils(data_dir):
    app = create_app(data_dir, profil="atelier")
    app.config["TESTING"] = True
    cl = app.test_client()
    rid = cl.post(P, json={"niveau": "N09", "annee": ANNEE}).get_json()["id"]
    assert cl.post(f"{P}/{rid}/themes", json={"nom": "Nombres", "couleur": "nombres"}).status_code == 201
    assert cl.post(f"{P}/{rid}/themes", json={"nom": "Géométrie"}).get_json()["code"] == "B"
    assert cl.post(f"{P}/{rid}/sequences", json={"nom": "Symétrie", "theme_code": "B"}).status_code == 201
    assert cl.post(f"{P}/{rid}/sequences", json={"nom": "Entiers", "theme_code": "A"}).get_json()["code"] == "S01"
    assert cl.put(f"{P}/{rid}/themes/B", json={"couleur": "geometrie"}).status_code == 200
    assert cl.put(f"{P}/{rid}/sequences/S02/theme", json={"theme_code": "A"}).get_json() == {"code": "S02"}
    assert cl.post(f"{P}/{rid}/themes/B/deplacer", json={"sens": -1}).status_code == 200
    assert cl.delete(f"{P}/{rid}/themes/A").status_code == 200
    l = cl.get(f"{P}/{rid}").get_json()
    assert [t["nom"] for t in l["themes"]] == ["Nombres"]
    assert len(l["couleurs_themes"]) >= 5
    assert cl.put(f"{P}/{rid}/themes/Z", json={"nom": "x"}).status_code == 404
    classe = create_app(data_dir, profil="classe")
    assert classe.test_client().post(f"{P}/{rid}/themes", json={"nom": "X"}).status_code == 403


from test_v0_51_3_import_paquet import apps, _importer, _paquet  # noqa: E402,F401


def test_import_cote_classe(apps):
    atelier, classe = apps
    with atelier.json_store._conn() as c:
        rid = _ref(c)
        rpe.ajouter_sequence(c, rid, "Entiers", "A")
        rpe.ajouter_sequence(c, rid, "Longueurs", "B")
        rpe.deplacer_theme(c, rid, "B", -1)
    res = _importer(classe, _paquet(atelier, [rid]))
    assert res["referentiels"][0]["importe"]
    with classe.json_store._conn() as c:
        assert [(t["code"], t["nom"], t["ordre"]) for t in rpe.lister_themes(c, rid)] == \
            [("A", "Grandeurs et mesures", 1), ("B", "Nombres et calculs", 2)]
        assert _vue(c, rid) == [("S01", "Longueurs", "A"), ("S02", "Entiers", "B")]
