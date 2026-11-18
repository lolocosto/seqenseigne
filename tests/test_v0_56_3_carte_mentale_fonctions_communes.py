"""tests/test_v0_56_3_carte_mentale_fonctions_communes.py — v0.56.3

Demande de Laurent (13 novembre 2026, 17 h 03), doc/redemarrage_v0_56_3.md :
« mettre en place la multisélection pour valider plusieurs éléments en une seule
fois » dans l'atelier Carte mentale, et y reprendre toutes les fonctionnalités
communes des ateliers atomiques.

Côté serveur :
  - la validation groupée est une suite de PATCH {etat_code} sur la route de
    chaque partie (même route que « Valider ») ; la séquence validée refuse (409) ;
  - une partie SANS carte refuse explicitement un changement d'état seul (409
    `carte_absente`) au lieu de tenter de créer une carte vide ;
  - la Recherche (outil commun des atomes) couvre les cartes mentales ; le rendu
    par lot (ORDRE_TYPES) n'est pas touché.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_v0_52_2_documents_6e import app_6e  # noqa: E402,F401
from tests.test_v0_55_0_cartes_mentales import CARTE  # noqa: E402

URL = "/api/v2/livret-sequence/N09/S01/cartes-mentales"


@pytest.fixture
def cl3(app_6e):
    """S01 avec trois parties : cartes en cours aux parties 1 et 2, rien à la 3."""
    with app_6e.json_store._conn() as c:
        c.execute("INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) "
                  "VALUES ('p62', 'sn6', 2), ('p63', 'sn6', 3)")
        c.commit()
    cl = app_6e.test_client()
    for n in (1, 2):
        assert cl.post(URL, json={"numero": n}).status_code == 201
        assert cl.patch(f"{URL}/{n}", json={"titre": f"C{n}", "latex": CARTE}).status_code == 200
    return cl


def _etats(cl):
    return {p["numero"]: (p["carte"] or {}).get("etat_code") for p in cl.get(URL).get_json()["parties"]}


def test_validation_groupee_un_patch_etat_par_partie_valide_plusieurs_cartes(cl3):
    for n in (1, 2):
        r = cl3.patch(f"{URL}/{n}", json={"etat_code": "valide"})
        assert r.status_code == 200 and r.get_json()["etat_code"] == "valide"
    assert _etats(cl3) == {1: "valide", 2: "valide", 3: None}
    # Le contenu n'est pas touché par un changement d'état seul.
    assert cl3.get(f"{URL}/1").get_json()["titre"] == "C1"
    # Repasser en cours en groupe : même route.
    assert cl3.patch(f"{URL}/2", json={"etat_code": "en_cours"}).status_code == 200
    assert _etats(cl3)[2] == "en_cours"


def test_partie_sans_carte_refuse_un_changement_d_etat_seul_sans_creer_de_carte(cl3):
    r = cl3.patch(f"{URL}/3", json={"etat_code": "valide"})
    assert r.status_code == 409
    assert r.get_json()["error"] == "carte_absente"
    assert "pas de carte mentale" in r.get_json()["message"]
    assert _etats(cl3)[3] is None
    # L'enregistrement d'une carte (titre + source) reste possible sur cette partie.
    assert cl3.patch(f"{URL}/3", json={"titre": "C3", "latex": CARTE}).status_code == 200
    assert _etats(cl3)[3] == "en_cours"


def test_sequence_validee_refuse_la_validation_groupee(cl3, app_6e):
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE sequences_par_niveau SET etat_code = 'valide' WHERE id = 'sn6'")
        c.commit()
    for n in (1, 2):
        r = cl3.patch(f"{URL}/{n}", json={"etat_code": "valide"})
        assert r.status_code == 409 and r.get_json()["error"] == "sequence_validee"
    assert _etats(cl3) == {1: "en_cours", 2: "en_cours", 3: None}


# ── Recherche ────────────────────────────────────────────────────────────────

def test_recherche_trouve_une_carte_mentale_par_sa_source_avec_l_identifiant_de_l_atelier(cl3, app_6e):
    from services.recherche_atomes import rechercher
    r = rechercher(app_6e.json_store, texte="entiers")       # dans le titre central de CARTE
    assert [a["id"] for a in r["carte_mentale"]] == ["1", "2"]
    a = r["carte_mentale"][0]
    # id = numéro de la partie : identifiant de l'élément dans l'atelier (mode
    # séquence), donc celui du lien « Ouvrir » (?atelier=carte_mentale&atome=1).
    assert a == {"id": "1", "type": "carte_mentale", "niveau": "N09", "sequence": "S01",
                 "num": 1, "identifiant": "N09/S01/Carte mentale P1", "titre": "C1",
                 "etat_code": "en_cours"}
    assert r["total"] >= 2


def test_recherche_filtres_type_niveau_sequence_etat(cl3, app_6e):
    from services.recherche_atomes import rechercher
    cl3.patch(f"{URL}/2", json={"etat_code": "valide"})
    st = app_6e.json_store
    seul = rechercher(st, type="carte_mentale")
    assert set(k for k, v in seul.items() if isinstance(v, list) and v) == {"carte_mentale"}
    assert [a["id"] for a in rechercher(st, type="carte_mentale", etat="valide")["carte_mentale"]] == ["2"]
    assert rechercher(st, type="carte_mentale", niveau="N10")["carte_mentale"] == []
    assert rechercher(st, type="carte_mentale", sequence="S02")["carte_mentale"] == []
    r = app_6e.test_client().get("/api/recherche?type=carte_mentale&texte=C2")
    assert r.status_code == 200 and [a["id"] for a in r.get_json()["carte_mentale"]] == ["2"]


def test_recherche_sans_table_des_cartes_mentales_et_rendu_par_lot_inchange(tmp_path):
    from persistence.sqlite_store import SqliteStore
    from services.compilation_batch import ORDRE_TYPES
    from services.recherche_atomes import TYPES_RECHERCHE, rechercher
    st = SqliteStore(tmp_path)
    r = rechercher(st)
    assert r["carte_mentale"] == [] and r["total"] == 0
    # v0.60.1 (C11) : le rendu par lot compile aussi les cartes mentales, au
    # même rang que la Recherche (qui les avait depuis la v0.56.3).
    assert ORDRE_TYPES == ("notion", "methode", "exercice", "fiche", "carte", "carte_mentale")
    assert TYPES_RECHERCHE == ORDRE_TYPES
