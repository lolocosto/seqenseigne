"""tests/test_v0_49_0_mer_modele_fige.py — v0.49.0

Référentiel externe de MER dans la structure figée : création (type MER,
codes M01…, nom calculé), libellé de partie, documents annuels, alerte
« partie sans capacité », progression de MER branchée sur la source
« fige » (parties disponibles, pose, verrouillage de la séquence, état
« utilisé »), ancien modèle encore lisible.
"""
from datetime import date

import pytest

from persistence.sqlite_store import SqliteStore
from services import referentiel_principal_externe as rpe
from services import progression_mer as pm

ANNEE = "2026-2027"
AUJ = date(2026, 9, 1)


@pytest.fixture
def st(tmp_path):
    return SqliteStore(tmp_path / "data")


def _mer(c):
    r = rpe.creer(c, "N09", ANNEE, "Calcul mental", type_ref="mer")
    rpe.ajouter_sequence(c, r["id"], "Compléter à 10, 100, 1 000")
    rpe.ajouter_partie(c, r["id"], "M01", 6, AUJ, libelle="Série 2")
    return r["id"]


def test_creation_et_structure(st):
    with st._conn() as c:
        rid = _mer(c)
        ref = rpe.lire(c, rid, AUJ)
        assert rid == "M2026_N09" and ref["nom"] == "6e — 2026-2027 — MER"
        s = ref["sequences"][0]
        assert s["code"] == "M01" and s["parties"][0]["libelle"] == "Série 2"
        rpe.libeller_partie(c, rid, "M01", 1, "Série 2.1 à 2.6")
        assert rpe.lire(c, rid, AUJ)["sequences"][0]["parties"][0]["libelle"] == "Série 2.1 à 2.6"
        # Coexiste avec un principal de même niveau / année.
        assert rpe.creer(c, "N09", ANNEE)["id"] == "X2026_N09"
        assert [r["id"] for r in rpe.lister(c, "N09")] == ["X2026_N09"]
        assert [r["id"] for r in rpe.lister(c, "N09", type_ref="mer")] == [rid]


def test_alerte_capacite_et_documents_annuels(st):
    with st._conn() as c:
        rid = _mer(c)
        ref = rpe.lire(c, rid, AUJ)
        assert ref["sequences"][0]["parties"][0]["sans_capacite"] and len(ref["alertes"]) == 1
        rpe.ajouter_objectif(c, rid, "M01", 1, "Compléter un entier à 1 000", 6)
        assert rpe.lire(c, rid, AUJ)["alertes"] == []
        f = rpe.ajouter_fichier(c, rid, "", 3, nom_fichier="recap.pdf", contenu=b"%",
                                mime="application/pdf", data_dir=st.data_dir)
        assert f["seq_code"] == "" and f["partie_numero"] == 0
        assert [d["nom_fichier"] for d in rpe.lire(c, rid, AUJ)["documents_annuels"]] == ["recap.pdf"]


def test_progression_de_mer(st):
    with st._conn() as c:
        rid = _mer(c)
        rpe.ajouter_partie(c, rid, "M01", 4, AUJ)
        prog = pm.creer_ou_lire(c, "N09", ANNEE)
        pm.definir_referentiel(c, prog["id"], rid, "fige")
        dispo = pm.lister_parties_disponibles(c, rid, "fige")
        assert [(p["id"], p["libelle"]) for p in dispo] == [
            (f"{rid}|M01|1", "Série 2"), (f"{rid}|M01|2", "Partie 2")]
        pm.poser_partie(c, prog["id"], dispo[0]["id"], "fige")
        posees = pm.lire_par_niveau(c, "N09", ANNEE)["parties"]
        assert posees[0]["libelle"] == "Série 2" and posees[0]["nb_seances"] == 6
        ref = rpe.lire(c, rid, AUJ)
        assert ref["utilise"] and ref["sequences"][0]["commencee"]
        with pytest.raises(rpe.RefExtErreur):
            rpe.supprimer_partie(c, rid, "M01", 2, AUJ)          # séquence verrouillée
        rpe.libeller_partie(c, rid, "M01", 1, "Série 2 bis")    # libellé : permis
        with pytest.raises(rpe.RefExtErreur):
            rpe.supprimer(c, rid, st.data_dir)                  # utilisé


def test_routes(client):
    P = "/api/referentiels-principaux-externes"
    r = client.post(P, json={"niveau": "N09", "annee": ANNEE, "type_ref": "mer"})
    assert r.status_code == 201 and r.get_json()["type_ref"] == "mer"
    rid = r.get_json()["id"]
    assert client.post(P, json={"niveau": "N09", "annee": ANNEE, "type_ref": "zz"}).status_code == 400
    assert len(client.get(f"{P}?niveau=N09&type=mer").get_json()["referentiels"]) == 1
    assert len(client.get(f"{P}?niveau=N09&type=tous").get_json()["referentiels"]) == 1
    assert client.get(f"{P}?niveau=N09").get_json()["referentiels"] == []
    client.post(f"{P}/{rid}/sequences", json={"nom": "Calcul"})
    assert client.post(f"{P}/{rid}/sequences/M01/parties",
                       json={"nb_seances": 6, "libelle": "Série 1"}).status_code == 201
    assert client.put(f"{P}/{rid}/sequences/M01/parties/1/libelle",
                      json={"libelle": "Série 1 bis"}).status_code == 200
    import io
    assert client.post(f"{P}/{rid}/documents-annuels", data={
        "fichier": (io.BytesIO(b"%PDF"), "recap.pdf", "application/pdf")},
        content_type="multipart/form-data").status_code == 201
