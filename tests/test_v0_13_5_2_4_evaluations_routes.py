"""tests/test_v0_13_5_2_4_evaluations_routes.py — v0.13.5.2.4.

Tests des routes Flask de l'atelier Évaluation.

Couvre :
  - CRUD evaluations (création, lecture, liste, PATCH, suppression,
    réordonnancement)
  - Liaisons exos (ajout, retrait, modification de barème, réordonner)
  - Liaisons objectifs (ajout, retrait, listage)
  - Transitions d'état (valider contrôlée, dévalider libre)
  - Couverture (matrice creuse)
  - Aides UI : exos-disponibles et objectifs-disponibles par niveau
  - Codes HTTP corrects pour chaque cas d'erreur métier

Pattern : utilise la fixture `client` du conftest (app Flask + data_dir
temporaire). On crée nos pré-conditions (séquence, partie, objectif,
exercice) directement en BDD via store._conn() avant d'attaquer l'API.
"""
from __future__ import annotations
import sqlite3
import uuid

import pytest


# ── Helpers de peuplement BDD ────────────────────────────────────────────────


def _peupler_struct_pedago(store, niveaux=("N10", "N11")):
    """Crée la structure pédagogique minimale (séquences, parties,
    objectifs) en BDD pour qu'on puisse y rattacher des évals."""
    with store._conn() as conn:
        for niveau in niveaux:
            sn_id = f"sn_{niveau}_S01"
            conn.execute(
                "INSERT INTO sequences_par_niveau (id, niveau, sequence_code) "
                "VALUES (?, ?, 'S01')",
                (sn_id, niveau),
            )
            for partie_num in (1, 2):
                sp_id = f"sp_{niveau}_S01_p{partie_num}"
                conn.execute(
                    "INSERT INTO sequence_parties "
                    "(id, sequence_par_niveau_id, numero) VALUES (?, ?, ?)",
                    (sp_id, sn_id, partie_num),
                )
                for code in ("01", "02"):
                    ob_id = f"ob_{niveau}_S01_p{partie_num}_{code}"
                    conn.execute(
                        "INSERT INTO objectifs "
                        "(id, partie_id, code, nom) "
                        "VALUES (?, ?, ?, ?)",
                        (ob_id, sp_id, code, f"Objectif {code} {niveau}"),
                    )


def _creer_exo(store, exo_id="ex_test", serie="fondamental",
               type_format="standard", titre="Test", enonce="..."):
    """Insère un exo standard ou QCM en BDD."""
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO exercices "
            "(id, serie, titre, enonce, corrige, type_format) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (exo_id, serie, titre, enonce, "corrigé", type_format),
        )


def _lier_exo_objectif(store, exo_id, obj_id, serie="F"):
    """Lien direct exo ↔ objectif (table objectif_exos)."""
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO objectif_exos "
            "(objectif_id, serie, exercice_id, ordre) VALUES (?, ?, ?, 1)",
            (obj_id, serie, exo_id),
        )


# ── Fixtures combinées ──────────────────────────────────────────────────────


@pytest.fixture
def setup_n10(client, sqlite_store):
    """Structure pédagogique N10 et N11 + 4 exos standard."""
    _peupler_struct_pedago(sqlite_store)
    for i in range(1, 5):
        _creer_exo(sqlite_store, exo_id=f"ex{i}", titre=f"Exo {i}")
    return sqlite_store


# ═════════════════════════════════════════════════════════════════════════════
# Section A — CRUD évaluations
# ═════════════════════════════════════════════════════════════════════════════


class TestCRUDEvaluations:

    def test_creer_evaluation_simple(self, client, setup_n10):
        r = client.post("/api/evaluations", json={
            "niveau": "N10", "titre": "Bilan T1",
        })
        assert r.status_code == 201
        data = r.get_json()
        assert data["evaluation"]["niveau"] == "N10"
        assert data["evaluation"]["titre"] == "Bilan T1"
        assert data["evaluation"]["etat_code"] == "en_cours"

    def test_creer_sans_niveau_400(self, client, setup_n10):
        r = client.post("/api/evaluations", json={"titre": "X"})
        assert r.status_code == 400

    def test_lister_par_niveau(self, client, setup_n10):
        client.post("/api/evaluations", json={"niveau": "N10", "titre": "E1"})
        client.post("/api/evaluations", json={"niveau": "N10", "titre": "E2"})
        client.post("/api/evaluations", json={"niveau": "N11", "titre": "F1"})
        r = client.get("/api/evaluations?niveau=N10")
        assert r.status_code == 200
        evals = r.get_json()["evaluations"]
        assert len(evals) == 2
        assert all(e["niveau"] == "N10" for e in evals)

    def test_lister_tous(self, client, setup_n10):
        client.post("/api/evaluations", json={"niveau": "N10", "titre": "E1"})
        client.post("/api/evaluations", json={"niveau": "N11", "titre": "F1"})
        r = client.get("/api/evaluations")
        assert r.status_code == 200
        assert len(r.get_json()["evaluations"]) == 2

    def test_lire_evaluation(self, client, setup_n10):
        r1 = client.post("/api/evaluations",
                         json={"niveau": "N10", "titre": "E1"})
        eval_id = r1.get_json()["evaluation"]["id"]
        r2 = client.get(f"/api/evaluations/{eval_id}")
        assert r2.status_code == 200
        assert r2.get_json()["evaluation"]["titre"] == "E1"

    def test_lire_inexistante_404(self, client, setup_n10):
        r = client.get("/api/evaluations/ev_inexistant")
        assert r.status_code == 404
        assert r.get_json()["code"] == "evaluation_introuvable"

    def test_modifier_titre(self, client, setup_n10):
        r1 = client.post("/api/evaluations",
                         json={"niveau": "N10", "titre": "Avant"})
        eval_id = r1.get_json()["evaluation"]["id"]
        r2 = client.patch(f"/api/evaluations/{eval_id}",
                          json={"titre": "Après"})
        assert r2.status_code == 200
        assert r2.get_json()["evaluation"]["titre"] == "Après"

    def test_modifier_sans_champ_400(self, client, setup_n10):
        r1 = client.post("/api/evaluations",
                         json={"niveau": "N10", "titre": "X"})
        eval_id = r1.get_json()["evaluation"]["id"]
        r2 = client.patch(f"/api/evaluations/{eval_id}", json={})
        assert r2.status_code == 400

    def test_modifier_mode_notation_invalide_400(self, client, setup_n10):
        r1 = client.post("/api/evaluations",
                         json={"niveau": "N10", "titre": "X"})
        eval_id = r1.get_json()["evaluation"]["id"]
        r2 = client.patch(f"/api/evaluations/{eval_id}",
                          json={"mode_notation": "n_importe_quoi"})
        assert r2.status_code == 400
        assert r2.get_json()["code"] == "mode_notation_invalide"

    def test_supprimer(self, client, setup_n10):
        r1 = client.post("/api/evaluations",
                         json={"niveau": "N10", "titre": "X"})
        eval_id = r1.get_json()["evaluation"]["id"]
        r2 = client.delete(f"/api/evaluations/{eval_id}")
        assert r2.status_code == 204
        r3 = client.get(f"/api/evaluations/{eval_id}")
        assert r3.status_code == 404

    def test_supprimer_inexistante_404(self, client, setup_n10):
        r = client.delete("/api/evaluations/ev_inexistant")
        assert r.status_code == 404

    def test_reordonner(self, client, setup_n10):
        ids = []
        for titre in ("E1", "E2", "E3"):
            r = client.post("/api/evaluations",
                            json={"niveau": "N10", "titre": titre})
            ids.append(r.get_json()["evaluation"]["id"])
        # Inverser
        r = client.post("/api/evaluations/reordonner", json={
            "niveau": "N10", "ordre": list(reversed(ids)),
        })
        assert r.status_code == 204
        # Vérifier
        evals = client.get("/api/evaluations?niveau=N10").get_json()["evaluations"]
        assert [e["id"] for e in evals] == list(reversed(ids))

    def test_reordonner_sans_ordre_400(self, client, setup_n10):
        r = client.post("/api/evaluations/reordonner",
                        json={"niveau": "N10"})
        assert r.status_code == 400

    # ── item_langue_francaise : contrat de type (régression v0.16.1) ──────────
    #
    # Bug v0.16.1 : le frontend (atelier_evaluation_oo.js) envoyait
    # `item_langue_francaise` comme CHAÎNE JSON (`JSON.stringify({points})`)
    # au lieu de l'OBJET attendu. Le backend rejetait alors « attendu dict,
    # reçu str ». Ces tests documentent le contrat HTTP : le endpoint PATCH
    # attend un objet {points: nombre} (ou '' / null), jamais une chaîne JSON.

    def test_patch_item_langue_francaise_objet_ok(self, client, setup_n10):
        r1 = client.post("/api/evaluations",
                         json={"niveau": "N10", "titre": "E"})
        eval_id = r1.get_json()["evaluation"]["id"]
        r2 = client.patch(f"/api/evaluations/{eval_id}",
                          json={"item_langue_francaise": {"points": 3}})
        assert r2.status_code == 200
        ev = r2.get_json()["evaluation"]
        # Renvoyé parsé en objet (pas en str).
        assert ev["item_langue_francaise"] == {"points": 3}

    def test_patch_item_langue_francaise_chaine_json_400(self, client, setup_n10):
        # Le piège exact du bug : envoyer la chaîne '{"points": 3}'.
        r1 = client.post("/api/evaluations",
                         json={"niveau": "N10", "titre": "E"})
        eval_id = r1.get_json()["evaluation"]["id"]
        r2 = client.patch(f"/api/evaluations/{eval_id}",
                          json={"item_langue_francaise": '{"points": 3}'})
        assert r2.status_code == 400

    def test_patch_item_langue_francaise_vide_ok(self, client, setup_n10):
        # '' efface l'item (cas « pas de points langue française »).
        r1 = client.post("/api/evaluations",
                         json={"niveau": "N10", "titre": "E"})
        eval_id = r1.get_json()["evaluation"]["id"]
        r2 = client.patch(f"/api/evaluations/{eval_id}",
                          json={"item_langue_francaise": ""})
        assert r2.status_code == 200
        assert r2.get_json()["evaluation"]["item_langue_francaise"] is None


# ═════════════════════════════════════════════════════════════════════════════
# Section B — Liaisons exos
# ═════════════════════════════════════════════════════════════════════════════


class TestLiaisonsExos:

    def _creer_eval(self, client, niveau="N10", titre="E1"):
        r = client.post("/api/evaluations",
                        json={"niveau": niveau, "titre": titre})
        return r.get_json()["evaluation"]["id"]

    def test_ajouter_exo(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        r = client.post(f"/api/evaluations/{eval_id}/exos", json={
            "exercice_id": "ex1", "bareme_points": 4.0,
        })
        assert r.status_code == 201

    def test_ajouter_exo_sans_id_400(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        r = client.post(f"/api/evaluations/{eval_id}/exos", json={})
        assert r.status_code == 400

    def test_ajouter_exo_inexistant_404(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        r = client.post(f"/api/evaluations/{eval_id}/exos", json={
            "exercice_id": "ex_inexistant",
        })
        assert r.status_code == 404
        assert r.get_json()["code"] == "exercice_introuvable"

    def test_ajouter_exo_doublon_409(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        client.post(f"/api/evaluations/{eval_id}/exos",
                    json={"exercice_id": "ex1"})
        r = client.post(f"/api/evaluations/{eval_id}/exos",
                        json={"exercice_id": "ex1"})
        assert r.status_code == 409
        assert r.get_json()["code"] == "exo_deja_present"

    def test_lister_exos(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        client.post(f"/api/evaluations/{eval_id}/exos",
                    json={"exercice_id": "ex1", "bareme_points": 4.0})
        client.post(f"/api/evaluations/{eval_id}/exos",
                    json={"exercice_id": "ex2", "bareme_points": 6.0})
        r = client.get(f"/api/evaluations/{eval_id}/exos")
        assert r.status_code == 200
        exos = r.get_json()["exos"]
        assert len(exos) == 2

    def test_retirer_exo(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        client.post(f"/api/evaluations/{eval_id}/exos",
                    json={"exercice_id": "ex1"})
        r = client.delete(f"/api/evaluations/{eval_id}/exos/ex1")
        assert r.status_code == 204
        exos = client.get(
            f"/api/evaluations/{eval_id}/exos").get_json()["exos"]
        assert exos == []

    def test_retirer_exo_inexistant_404(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        r = client.delete(f"/api/evaluations/{eval_id}/exos/ex1")
        assert r.status_code == 404

    def test_modifier_bareme(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        client.post(f"/api/evaluations/{eval_id}/exos",
                    json={"exercice_id": "ex1", "bareme_points": 4.0})
        r = client.patch(f"/api/evaluations/{eval_id}/exos/ex1",
                         json={"bareme_points": 6.0})
        assert r.status_code == 200
        # Vérifier la nouvelle valeur
        exos = client.get(
            f"/api/evaluations/{eval_id}/exos").get_json()["exos"]
        assert exos[0]["bareme_points"] == 6.0

    def test_modifier_bareme_sans_champ_400(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        client.post(f"/api/evaluations/{eval_id}/exos",
                    json={"exercice_id": "ex1"})
        r = client.patch(f"/api/evaluations/{eval_id}/exos/ex1", json={})
        assert r.status_code == 400

    def test_reordonner_exos(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        for ex_id in ("ex1", "ex2", "ex3"):
            client.post(f"/api/evaluations/{eval_id}/exos",
                        json={"exercice_id": ex_id})
        r = client.post(f"/api/evaluations/{eval_id}/exos/reordonner",
                        json={"ordre": ["ex3", "ex1", "ex2"]})
        assert r.status_code == 204
        exos = client.get(
            f"/api/evaluations/{eval_id}/exos").get_json()["exos"]
        assert [e["exercice_id"] for e in exos] == ["ex3", "ex1", "ex2"]


# ═════════════════════════════════════════════════════════════════════════════
# Section C — Liaisons objectifs
# ═════════════════════════════════════════════════════════════════════════════


class TestLiaisonsObjectifs:

    def _creer_eval_n10(self, client):
        r = client.post("/api/evaluations",
                        json={"niveau": "N10", "titre": "E1"})
        return r.get_json()["evaluation"]["id"]

    def test_ajouter_objectif(self, client, setup_n10):
        eval_id = self._creer_eval_n10(client)
        r = client.post(f"/api/evaluations/{eval_id}/objectifs", json={
            "objectif_id": "ob_N10_S01_p1_01",
        })
        assert r.status_code == 201

    def test_ajouter_objectif_niveau_incoherent_409(self, client, setup_n10):
        eval_id = self._creer_eval_n10(client)
        # Objectif N11 sur éval N10 → 409
        r = client.post(f"/api/evaluations/{eval_id}/objectifs", json={
            "objectif_id": "ob_N11_S01_p1_01",
        })
        assert r.status_code == 409
        assert r.get_json()["code"] == "objectif_niveau_incoherent"

    def test_ajouter_objectif_inexistant_404(self, client, setup_n10):
        eval_id = self._creer_eval_n10(client)
        r = client.post(f"/api/evaluations/{eval_id}/objectifs", json={
            "objectif_id": "ob_inexistant",
        })
        assert r.status_code == 404

    def test_ajouter_objectif_doublon_409(self, client, setup_n10):
        eval_id = self._creer_eval_n10(client)
        client.post(f"/api/evaluations/{eval_id}/objectifs",
                    json={"objectif_id": "ob_N10_S01_p1_01"})
        r = client.post(f"/api/evaluations/{eval_id}/objectifs",
                        json={"objectif_id": "ob_N10_S01_p1_01"})
        assert r.status_code == 409
        assert r.get_json()["code"] == "objectif_deja_present"

    def test_lister_objectifs(self, client, setup_n10):
        eval_id = self._creer_eval_n10(client)
        client.post(f"/api/evaluations/{eval_id}/objectifs",
                    json={"objectif_id": "ob_N10_S01_p1_01"})
        client.post(f"/api/evaluations/{eval_id}/objectifs",
                    json={"objectif_id": "ob_N10_S01_p2_01"})
        r = client.get(f"/api/evaluations/{eval_id}/objectifs")
        assert r.status_code == 200
        assert len(r.get_json()["objectifs"]) == 2

    def test_retirer_objectif(self, client, setup_n10):
        eval_id = self._creer_eval_n10(client)
        client.post(f"/api/evaluations/{eval_id}/objectifs",
                    json={"objectif_id": "ob_N10_S01_p1_01"})
        r = client.delete(
            f"/api/evaluations/{eval_id}/objectifs/ob_N10_S01_p1_01")
        assert r.status_code == 204

    def test_retirer_objectif_non_lie_404(self, client, setup_n10):
        eval_id = self._creer_eval_n10(client)
        r = client.delete(
            f"/api/evaluations/{eval_id}/objectifs/ob_N10_S01_p1_01")
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# Section D — Transitions d'état
# ═════════════════════════════════════════════════════════════════════════════


class TestTransitionsEtat:

    def _eval_remplie_pour_validation(self, client, setup_n10):
        """Crée une éval avec 1 exo + barème — prête à être validée."""
        r = client.post("/api/evaluations", json={
            "niveau": "N10", "titre": "E1", "mode_notation": "note",
        })
        eval_id = r.get_json()["evaluation"]["id"]
        client.post(f"/api/evaluations/{eval_id}/exos", json={
            "exercice_id": "ex1", "bareme_points": 4.0,
        })
        return eval_id

    def test_valider_succes(self, client, setup_n10):
        eval_id = self._eval_remplie_pour_validation(client, setup_n10)
        r = client.post(f"/api/evaluations/{eval_id}/valider")
        assert r.status_code == 200
        assert r.get_json()["evaluation"]["etat_code"] == "valide"

    def test_valider_echec_aucun_exo(self, client, setup_n10):
        r = client.post("/api/evaluations",
                        json={"niveau": "N10", "titre": "X",
                              "mode_notation": "note"})
        eval_id = r.get_json()["evaluation"]["id"]
        r2 = client.post(f"/api/evaluations/{eval_id}/valider")
        assert r2.status_code == 400
        data = r2.get_json()
        assert data["code"] == "validation_pedagogique_echouee"
        # Le détail des raisons doit être exposé
        raisons = data["details"]["raisons"]
        assert any(r["code"] == "aucun_exercice" for r in raisons)

    def test_valider_echec_bareme_manquant(self, client, setup_n10):
        r = client.post("/api/evaluations", json={
            "niveau": "N10", "titre": "X", "mode_notation": "note",
        })
        eval_id = r.get_json()["evaluation"]["id"]
        # Ajout d'un exo SANS barème
        client.post(f"/api/evaluations/{eval_id}/exos",
                    json={"exercice_id": "ex1"})
        r2 = client.post(f"/api/evaluations/{eval_id}/valider")
        assert r2.status_code == 400
        raisons = r2.get_json()["details"]["raisons"]
        assert any(
            r["code"] == "bareme_manquant" and r["exercice_id"] == "ex1"
            for r in raisons
        )

    def test_valider_deja_valide_409(self, client, setup_n10):
        eval_id = self._eval_remplie_pour_validation(client, setup_n10)
        client.post(f"/api/evaluations/{eval_id}/valider")
        r = client.post(f"/api/evaluations/{eval_id}/valider")
        assert r.status_code == 409
        assert r.get_json()["code"] == "deja_valide"

    def test_devalider(self, client, setup_n10):
        eval_id = self._eval_remplie_pour_validation(client, setup_n10)
        client.post(f"/api/evaluations/{eval_id}/valider")
        r = client.post(f"/api/evaluations/{eval_id}/devalider")
        assert r.status_code == 200
        assert r.get_json()["evaluation"]["etat_code"] == "en_cours"

    def test_devalider_deja_en_cours_409(self, client, setup_n10):
        r = client.post("/api/evaluations",
                        json={"niveau": "N10", "titre": "X"})
        eval_id = r.get_json()["evaluation"]["id"]
        r2 = client.post(f"/api/evaluations/{eval_id}/devalider")
        assert r2.status_code == 409


# ═════════════════════════════════════════════════════════════════════════════
# Section E — Couverture
# ═════════════════════════════════════════════════════════════════════════════


class TestCouverture:

    def test_couverture_eval_vide(self, client, setup_n10):
        r1 = client.post("/api/evaluations",
                         json={"niveau": "N10", "titre": "E"})
        eval_id = r1.get_json()["evaluation"]["id"]
        r2 = client.get(f"/api/evaluations/{eval_id}/couverture")
        assert r2.status_code == 200
        data = r2.get_json()
        assert data["objectifs"] == []
        assert data["exercices"] == []
        assert data["cellules"] == []

    def test_couverture_avec_cellule(self, client, setup_n10, sqlite_store):
        # Lier ex1 à l'objectif (côté table objectif_exos)
        _lier_exo_objectif(sqlite_store, "ex1", "ob_N10_S01_p1_01")
        # Créer éval, attacher ex1 et l'objectif
        r1 = client.post("/api/evaluations",
                         json={"niveau": "N10", "titre": "E"})
        eval_id = r1.get_json()["evaluation"]["id"]
        client.post(f"/api/evaluations/{eval_id}/exos",
                    json={"exercice_id": "ex1"})
        client.post(f"/api/evaluations/{eval_id}/objectifs",
                    json={"objectif_id": "ob_N10_S01_p1_01"})
        # Vérifier la couverture
        r2 = client.get(f"/api/evaluations/{eval_id}/couverture")
        assert r2.status_code == 200
        data = r2.get_json()
        assert len(data["cellules"]) == 1
        assert data["cellules"][0] == {
            "objectif_id": "ob_N10_S01_p1_01",
            "exercice_id": "ex1",
        }

    def test_couverture_eval_inexistante_404(self, client, setup_n10):
        r = client.get("/api/evaluations/ev_inexistant/couverture")
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# Section F — Sélecteurs (aides UI)
# ═════════════════════════════════════════════════════════════════════════════


class TestSelecteursAides:

    def test_exos_disponibles_par_niveau(self, client, setup_n10,
                                          sqlite_store):
        # Lier ex1 et ex2 à des objectifs N10 pour qu'ils soient
        # "disponibles" depuis ce niveau
        _lier_exo_objectif(sqlite_store, "ex1", "ob_N10_S01_p1_01")
        _lier_exo_objectif(sqlite_store, "ex2", "ob_N10_S01_p2_01")
        # ex3 et ex4 ne sont liés à aucun objectif — ne devraient pas
        # apparaître

        r = client.get("/api/evaluations/niveau/N10/exos-disponibles")
        assert r.status_code == 200
        data = r.get_json()
        assert data["niveau"] == "N10"
        # Le contenu est groupé par séquence
        assert "S01" in data["par_sequence"]
        ids_dispo = {e["id"] for e in data["par_sequence"]["S01"]}
        assert "ex1" in ids_dispo
        assert "ex2" in ids_dispo
        assert "ex3" not in ids_dispo

    def test_exos_disponibles_niveau_sans_liens_vide(self, client,
                                                      setup_n10):
        # Aucun exo lié à N11
        r = client.get("/api/evaluations/niveau/N11/exos-disponibles")
        assert r.status_code == 200
        assert r.get_json()["par_sequence"] == {}

    def test_objectifs_disponibles_par_niveau(self, client, setup_n10):
        r = client.get("/api/evaluations/niveau/N10/objectifs-disponibles")
        assert r.status_code == 200
        data = r.get_json()
        assert data["niveau"] == "N10"
        assert "S01" in data["par_sequence"]
        # 2 parties × 2 objectifs = 4 objectifs N10 dans S01
        assert len(data["par_sequence"]["S01"]) == 4

    def test_objectifs_disponibles_niveau_inexistant_vide(self, client,
                                                          setup_n10):
        r = client.get("/api/evaluations/niveau/N99/objectifs-disponibles")
        assert r.status_code == 200
        assert r.get_json()["par_sequence"] == {}
