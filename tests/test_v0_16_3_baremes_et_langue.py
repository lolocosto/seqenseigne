r"""
tests/test_v0_16_3_baremes_et_langue.py — v0.16.3 (2b-1).

Trois changements backend + amélioration item langue française :

1. Item « langue française » OPTIONNEL : un total de 0 pt = item désactivé,
   donc NON émis dans le barème auto (avant : émis dès que points != None).
2. Exercice à 0 pt = ERREUR de validation (`bareme_zero`) : un exo ajouté doit
   être noté (sémantique opposée à l'item langue, optionnel).
3. Endpoint barèmes GROUPÉS : PATCH /api/evaluations/<id>/baremes pousse tous
   les barèmes modifiés en un appel (support du régime mixte 2b à venir).
"""

from __future__ import annotations

import pytest

from services.render_evaluation import _bareme_langue_str
from tests.test_v0_13_5_2_4_evaluations_routes import (
    _peupler_struct_pedago, _creer_exo,
)


@pytest.fixture
def setup_n10(client, sqlite_store):
    """Structure pédagogique N10 + quelques exos (réutilise les helpers
    du fichier de tests des routes évaluations)."""
    _peupler_struct_pedago(sqlite_store)
    for i in range(1, 5):
        _creer_exo(sqlite_store, exo_id=f"ex{i}", titre=f"Exo {i}")
    return sqlite_store


# ── 1. Item langue française : 0 pt = omis ────────────────────────────────────

class TestItemLangueOptionnel:
    def test_points_positifs_emis(self):
        assert _bareme_langue_str({"points": 4}, "note") == "4 points"
        assert _bareme_langue_str({"points": 1}, "note") == "1 point"

    def test_points_zero_omis(self):
        # v0.16.3 — 0 pt = item désactivé → ligne non émise.
        assert _bareme_langue_str({"points": 0}, "note") == ""
        assert _bareme_langue_str({"points": 0.0}, "note") == ""

    def test_none_ou_vide_omis(self):
        assert _bareme_langue_str(None, "note") == ""
        assert _bareme_langue_str({}, "note") == ""

    def test_mode_criteres_toujours_omis(self):
        assert _bareme_langue_str({"points": 4}, "criteres") == ""


# ── 2. Exercice à 0 pt = erreur de validation ─────────────────────────────────

class TestExoZeroErreur:
    """`_valider_bareme_exo` doit signaler bareme_zero pour un exo en mode
    barème obligatoire dont le barème vaut 0."""

    def _valider(self, exo_row, mode="note"):
        from services.evaluations import _evaluer_critere_bareme
        return _evaluer_critere_bareme(exo_row, mode)

    def _row(self, **kw):
        base = {
            "exercice_id": "EX1", "type_format": "standard",
            "bareme_points": None, "bareme_qcm_ok": None,
            "bareme_qcm_partiel": None, "bareme_qcm_ko": None,
        }
        base.update(kw)
        return base

    def test_standard_zero_erreur(self):
        raisons = self._valider(self._row(bareme_points=0))
        codes = [r["code"] for r in raisons]
        assert "bareme_zero" in codes

    def test_standard_positif_ok(self):
        raisons = self._valider(self._row(bareme_points=4))
        assert raisons == []

    def test_standard_negatif_reste_negatif(self):
        # Le négatif garde son propre code (pas confondu avec zéro).
        raisons = self._valider(self._row(bareme_points=-2))
        assert [r["code"] for r in raisons] == ["bareme_negatif"]

    def test_standard_manquant_reste_manquant(self):
        raisons = self._valider(self._row(bareme_points=None))
        assert [r["code"] for r in raisons] == ["bareme_manquant"]

    def test_qcm_ok_zero_erreur(self):
        raisons = self._valider(self._row(
            type_format="qcm", bareme_qcm_ok=0,
            bareme_qcm_partiel=0, bareme_qcm_ko=0))
        assert "bareme_zero" in [r["code"] for r in raisons]

    def test_qcm_ok_positif_ok(self):
        raisons = self._valider(self._row(
            type_format="qcm", bareme_qcm_ok=2,
            bareme_qcm_partiel=1, bareme_qcm_ko=0))
        assert raisons == []

    def test_mode_criteres_zero_tolere(self):
        # En mode critères, pas de barème obligatoire → 0 toléré.
        raisons = self._valider(self._row(bareme_points=0), mode="criteres")
        assert "bareme_zero" not in [r["code"] for r in raisons]


# ── 3. Endpoint barèmes groupés ───────────────────────────────────────────────

class TestBaremesGroupes:
    def _creer_eval_avec_exos(self, client, setup_n10):
        r = client.post("/api/evaluations",
                        json={"niveau": "N10", "titre": "E"})
        eval_id = r.get_json()["evaluation"]["id"]
        return eval_id

    def test_patch_groupe_liste_requise(self, client, setup_n10):
        eval_id = self._creer_eval_avec_exos(client, setup_n10)
        r = client.patch(f"/api/evaluations/{eval_id}/baremes",
                         json={"baremes": "pasuneliste"})
        assert r.status_code == 400

    def test_patch_groupe_entree_sans_id_400(self, client, setup_n10):
        eval_id = self._creer_eval_avec_exos(client, setup_n10)
        r = client.patch(f"/api/evaluations/{eval_id}/baremes",
                         json={"baremes": [{"bareme_points": 4}]})
        assert r.status_code == 400

    def test_patch_groupe_liste_vide_ok(self, client, setup_n10):
        eval_id = self._creer_eval_avec_exos(client, setup_n10)
        r = client.patch(f"/api/evaluations/{eval_id}/baremes",
                         json={"baremes": []})
        assert r.status_code == 200
        assert r.get_json() == {"baremes": []}


# ── 4. UI (tests structurels — pas de tests JS dans le dépôt) ─────────────────

class TestUI:
    def _eval_js(self):
        from pathlib import Path
        appli = Path(__file__).resolve().parent.parent
        return (appli / "static" / "atelier_evaluation_oo.js").read_text(
            encoding="utf-8")

    def _template(self):
        from pathlib import Path
        appli = Path(__file__).resolve().parent.parent
        return (appli / "templates" / "index.html").read_text(encoding="utf-8")

    def test_indicateur_langue_present_dans_template(self):
        assert 'id="atl-eval-langue-indic"' in self._template()
        assert 'atelEvalMajLangueIndic()' in self._template()

    def test_methode_majLangueIndic_existe(self):
        import re
        js = self._eval_js()
        assert re.search(r"^\s{2}majLangueIndic\s*\(", js, re.MULTILINE)
        assert "window.atelEvalMajLangueIndic" in js

    def test_libelle_bareme_zero_present(self):
        # Le libellé d'erreur bareme_zero doit être présent dans le switch.
        assert "'bareme_zero'" in self._eval_js()
        assert "doit être noté" in self._eval_js()
