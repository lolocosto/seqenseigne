r"""
tests/test_v0_16_4_verrou_validation.py — Verrou « validé = lecture seule ».

CONTEXTE
--------
La validation (`etat_code = 'valide'`) certifie la cohérence d'un item
(barèmes, complétude). Pour que cette garantie ne soit pas contournable, un
item validé est en lecture seule : toute MODIFICATION de contenu est refusée
(409 `item_verrouille`) tant qu'il n'est pas repassé en cours.

Ce fichier teste la DÉFENSE EN PROFONDEUR côté backend (la vraie garantie).
Périmètre v0.16.4 : tous types (atomes + évaluation). L'UI grisée des atomes
est testée structurellement ; l'UI éval suivra en 2b-2.

RÈGLES
------
- PATCH/modif de contenu d'un item validé → 409.
- Changement d'état (valider/devalider, PATCH etat_code seul) → autorisé.
- Suppression d'un item validé → autorisée (confirmation côté UI).
"""

from __future__ import annotations

import pytest

from services.etats_edition import (
    assert_atome_modifiable, ItemVerrouille, changer_etat_atome,
)
from tests.test_v0_13_5_2_4_evaluations_routes import _peupler_struct_pedago


@pytest.fixture
def setup_n10(client, sqlite_store):
    """Structure pédagogique N10 pour pouvoir créer des évaluations."""
    _peupler_struct_pedago(sqlite_store)
    return sqlite_store


# ── Helper bas niveau : assert_atome_modifiable ───────────────────────────────

class TestAssertAtomeModifiable:
    def test_en_cours_passe(self, sqlite_store):
        # Un atome en cours est modifiable (pas d'exception).
        with sqlite_store._conn() as conn:
            _creer_notion_bdd(conn, "n1", etat="en_cours")
            assert_atome_modifiable(conn, "notion", "n1")  # ne lève pas

    def test_valide_leve(self, sqlite_store):
        with sqlite_store._conn() as conn:
            _creer_notion_bdd(conn, "n2", etat="valide")
            with pytest.raises(ItemVerrouille):
                assert_atome_modifiable(conn, "notion", "n2")

    def test_introuvable_ne_leve_pas(self, sqlite_store):
        # On laisse passer (la couche appelante renverra son 404).
        with sqlite_store._conn() as conn:
            assert_atome_modifiable(conn, "notion", "inexistant")


def _creer_notion_bdd(conn, notion_id, etat="en_cours"):
    """Insère une notion minimale en BDD avec l'état voulu."""
    conn.execute(
        "INSERT INTO notions (id, titre, etat_code) VALUES (?, ?, ?)",
        (notion_id, "Titre test", etat),
    )
    conn.commit()


# ── Routes atomes : PATCH refusé si validé ────────────────────────────────────

class TestRoutesAtomesVerrou:
    def test_patch_notion_validee_409(self, client, sqlite_store):
        with sqlite_store._conn() as conn:
            _creer_notion_bdd(conn, "nlock", etat="valide")
        r = client.patch("/api/notions/nlock", json={"titre": "Nouveau"})
        assert r.status_code == 409
        assert r.get_json().get("code") == "item_verrouille"

    def test_patch_notion_en_cours_ok(self, client, sqlite_store):
        with sqlite_store._conn() as conn:
            _creer_notion_bdd(conn, "nfree", etat="en_cours")
        r = client.patch("/api/notions/nfree", json={"titre": "Nouveau"})
        # 200 (modifiée) — pas de verrou.
        assert r.status_code == 200

    def test_delete_notion_validee_autorisee(self, client, sqlite_store):
        # La suppression d'un item validé reste permise (confirmation UI).
        with sqlite_store._conn() as conn:
            _creer_notion_bdd(conn, "ndel", etat="valide")
        r = client.delete("/api/notions/ndel")
        assert r.status_code == 200


# ── Routes évaluation : verrou + exceptions ───────────────────────────────────

class TestRoutesEvalVerrou:
    def _creer_eval(self, client):
        r = client.post("/api/evaluations",
                        json={"niveau": "N10", "titre": "E"})
        return r.get_json()["evaluation"]["id"]

    def _valider(self, client, eval_id):
        return client.post(f"/api/evaluations/{eval_id}/valider")

    def test_patch_champ_eval_validee_409(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        # Valider (éval sans exo : selon les règles métier, peut nécessiter
        # un contenu minimal — on force l'état via PATCH etat_code).
        r0 = client.patch(f"/api/evaluations/{eval_id}",
                          json={"etat_code": "valide"})
        assert r0.status_code == 200
        # Modifier un champ de contenu → refusé.
        r = client.patch(f"/api/evaluations/{eval_id}",
                        json={"titre": "Changé"})
        assert r.status_code == 409
        assert r.get_json().get("code") == "item_verrouille"

    def test_patch_etat_code_seul_autorise(self, client, setup_n10):
        # Un PATCH qui ne touche QUE etat_code = (dé)validation → autorisé.
        eval_id = self._creer_eval(client)
        client.patch(f"/api/evaluations/{eval_id}",
                    json={"etat_code": "valide"})
        r = client.patch(f"/api/evaluations/{eval_id}",
                        json={"etat_code": "en_cours"})
        assert r.status_code == 200

    def test_ajout_exo_eval_validee_409(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        client.patch(f"/api/evaluations/{eval_id}",
                    json={"etat_code": "valide"})
        r = client.post(f"/api/evaluations/{eval_id}/exos",
                       json={"exercice_id": "ex1"})
        assert r.status_code == 409
        assert r.get_json().get("code") == "item_verrouille"

    def test_baremes_groupes_eval_validee_409(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        client.patch(f"/api/evaluations/{eval_id}",
                    json={"etat_code": "valide"})
        r = client.patch(f"/api/evaluations/{eval_id}/baremes",
                        json={"baremes": [{"exercice_id": "ex1",
                                           "bareme_points": 4}]})
        assert r.status_code == 409

    def test_suppression_eval_validee_autorisee(self, client, setup_n10):
        eval_id = self._creer_eval(client)
        client.patch(f"/api/evaluations/{eval_id}",
                    json={"etat_code": "valide"})
        r = client.delete(f"/api/evaluations/{eval_id}")
        assert r.status_code == 204


# ── UI atomes : verrou structurel ─────────────────────────────────────────────

class TestUIVerrou:
    def _base_js(self):
        from pathlib import Path
        appli = Path(__file__).resolve().parent.parent
        return (appli / "static" / "atelier_editeur.js").read_text(
            encoding="utf-8")

    def test_methode_verrou_existe(self):
        import re
        js = self._base_js()
        assert re.search(r"_appliquerVerrouLectureSeule\s*\(", js)

    def test_verrou_appele_dans_afficher_editeur(self):
        js = self._base_js()
        # Appelé avec le test sur etat_code === 'valide'.
        assert "this._appliquerVerrouLectureSeule(" in js
        assert "etat_code === 'valide'" in js
