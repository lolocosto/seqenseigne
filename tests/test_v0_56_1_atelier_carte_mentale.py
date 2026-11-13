"""tests/test_v0_56_1_atelier_carte_mentale.py — v0.56.1

Atelier « Carte mentale » harmonisé sur les autres ateliers (Laurent, 13 novembre 2026,
doc/redemarrage_v0_56_1.md) : l'API suit le contrat d'AtelierEditeur (élément par partie,
GET unitaire, POST de création, PATCH partiel, DELETE, rendu-pdf/info, rendu-pdf,
rendu-tex) pour que l'atelier réutilise la classe commune au lieu de son propre mécanisme.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import cartes_mentales as cm  # noqa: E402
from tests.test_v0_52_2_documents_6e import app_6e  # noqa: E402,F401
from tests.test_v0_55_0_cartes_mentales import CARTE, _carte  # noqa: E402

URL = "/api/v2/livret-sequence/N09/S01/cartes-mentales"


def test_modele_propose_par_le_serveur_est_une_source_acceptee():
    # Une seule source du modèle (auparavant dupliqué dans le JS) ; « + Créer » l'enregistre tel quel.
    assert cm.controler_latex(cm.MODELE) == ([], [])


def test_partie_sans_carte_a_un_identifiant_et_s_ouvre_sur_le_modele(app_6e):
    cl = app_6e.test_client()
    r = cl.get(URL + "/1")
    assert r.status_code == 200
    el = r.get_json()
    assert el["id"] == "1" and el["presente"] is False and el["latex"] == cm.MODELE
    assert el["etat_code"] == "en_cours" and el["modifiable"] is True
    assert cl.get(URL + "/9").status_code == 404


def test_creer_depuis_le_modele_puis_refus_d_une_seconde_creation(app_6e):
    cl = app_6e.test_client()
    r = cl.post(URL, json={"numero": 1})
    assert r.status_code == 201
    assert r.get_json()["presente"] and r.get_json()["id"] == "1"
    assert cl.post(URL, json={"numero": 1}).status_code == 409
    assert cl.post(URL, json={"numero": 9}).status_code == 404
    assert cl.post(URL, json={}).status_code == 400


def test_patch_partiel_garde_les_cles_absentes_pour_valider_sans_renvoyer_la_source(app_6e):
    cl = app_6e.test_client()
    cl.put(URL + "/1", json={"titre": "Nombres", "latex": CARTE})
    r = cl.patch(URL + "/1", json={"etat_code": "valide"})
    assert r.status_code == 200
    el = r.get_json()
    assert el["etat_code"] == "valide" and el["titre"] == "Nombres" and el["latex"] == CARTE.strip()
    # Réponse = élément complet (AtelierEditeur.sauvegarder le reprend comme item actif)
    r = cl.patch(URL + "/1", json={"etat_code": "en_cours", "titre": "N2"})
    assert r.get_json()["titre"] == "N2" and r.get_json()["etat"] == "mise à jour"
    r = cl.patch(URL + "/1", json={"latex": _carte(3)})
    assert r.get_json()["avertissements"]
    assert cl.patch(URL + "/1", json={"latex": "pas une carte"}).status_code == 400


def test_sequence_validee_creation_et_modification_refusees_lecture_possible(app_6e):
    cl = app_6e.test_client()
    cl.put(URL + "/1", json={"titre": "N", "latex": CARTE})
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE sequences_par_niveau SET etat_code = 'valide' WHERE id = 'sn6'")
    assert cl.get(URL + "/1").get_json()["modifiable"] is False
    assert cl.patch(URL + "/1", json={"etat_code": "valide"}).status_code == 409
    assert cl.post(URL, json={"numero": 2}).status_code in (404, 409)
    assert cl.delete(URL + "/1").status_code == 409


def test_rendu_tex_de_la_partie_ou_de_toute_la_sequence(app_6e):
    cl = app_6e.test_client()
    cl.put(URL + "/1", json={"titre": "N", "latex": CARTE})
    r = cl.get(URL + "/1/rendu-tex?version=corrigee")
    assert r.status_code == 200
    tex = r.get_data(as_text=True)
    assert r"\seqVersionComplete" in tex and "Carte mentale --- Partie 1" in tex
    # Même générateur que le document de la séquence (lien depuis « Rendu PDF ») : même .tex.
    livret = cl.get("/api/v2/livret-sequence/N09/S01/rendu-tex?document=cartes_mentales"
                    "&version=corrigee&partie=1").get_data(as_text=True)
    assert tex == livret
    seq = cl.get(URL + "/1/rendu-tex?portee=sequence").get_data(as_text=True)
    assert seq == cl.get("/api/v2/livret-sequence/N09/S01/rendu-tex?document=cartes_mentales"
                         ).get_data(as_text=True)


def test_rendu_d_une_partie_sans_carte_erreur_lisible_et_info_sans_cache(app_6e):
    cl = app_6e.test_client()
    r = cl.post(URL + "/1/rendu-pdf")
    assert r.status_code == 400
    assert r.get_json()["erreurs"][0]["message"].startswith("Aucune carte mentale")
    info = cl.get(URL + "/1/rendu-pdf/info").get_json()
    assert info["cache_valide"] is False


def test_routes_de_l_atelier_classees_atelier_dans_les_profils(app_6e):
    from services import profils
    regles = [r for r in app_6e.url_map.iter_rules() if "cartes-mentales" in r.rule]
    assert len(regles) >= 5
    for r in regles:
        assert profils.categorie(r.endpoint) == "atelier", r.rule
