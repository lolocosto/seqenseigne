"""tests/test_v0_48_4_harmonisation_referentiels.py — v0.48.4

Nom calculé et type (principal / MER) pour tous les référentiels :
nom_calcule (interne, externe, lettre), création interne avec type, filtre
`type` de /api/referentiels (la progression principale ne voit pas les MER),
nom calculé des référentiels externes de MER (+ description).
"""
import pytest

from services import referentiel_principal_externe as rpe
from services import referentiel_externe as rx
from services import referentiels as refs


def test_nom_calcule():
    assert rpe.nom_calcule({"niveau": "N11", "version": "2025", "source": "interne"}) \
        == "4e — 2025-2026 — Principal"
    assert rpe.nom_calcule({"niveau": "N09", "version": "2026b", "type_ref": "mer"}) \
        == "6e — 2026-2027 — MER b"
    assert rpe.nom_calcule({"niveau": "N12", "version": "X2026c", "source": "externe",
                            "annee": "2026-2027"}) == "3e — 2026-2027 — Principal c"


def test_creation_interne_avec_type(app, client):
    r = client.post("/api/referentiels/coquille", json={"niveau": "N11", "type_ref": "mer"})
    assert r.status_code in (200, 201)
    l = client.get("/api/referentiels?niveau=N11").get_json()["referentiels"]
    assert l[0]["type_ref"] == "mer" and l[0]["nom"].endswith("MER")
    with app.json_store._conn() as c:
        with pytest.raises(ValueError):
            refs.creer_coquille(c, "N11", type_ref="autre")


def test_progression_ne_voit_que_les_principaux(app, client):
    with app.json_store._conn() as c:
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, type_ref) VALUES "
                  "('2026_N11', 'N11', '2026', 'verrouille', 'principal'), "
                  "('2026_N11b', 'N11', '2026b', 'verrouille', 'mer')")
        rpe.creer(c, "N11", "2026-2027")
    l = client.get("/api/referentiels?niveau=N11&etats=verrouille,utilise&externes=1"
                   "&type=principal").get_json()["referentiels"]
    assert [x["id"] for x in l] == ["2026_N11", "X2026_N11"]
    l = client.get("/api/referentiels?niveau=N11&type=mer").get_json()["referentiels"]
    assert [x["id"] for x in l] == ["2026_N11b"]


def test_mer_externe_nom_calcule(app):
    with app.json_store._conn() as c:
        a = rx.creer(c, niveau="N09", annee="2026-2027", description="Calcul mental")
        b = rx.creer(c, niveau="N09", annee="2026-2027")
        assert a["nom"] == "6e — 2026-2027 — MER" and a["description"] == "Calcul mental"
        assert b["nom"] == "6e — 2026-2027 — MER b"
        assert rx.creer(c, niveau="N09", annee="2026-2027", nom="Ancien nom")["nom"] == "Ancien nom"
