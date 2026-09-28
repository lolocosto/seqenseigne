r"""
tests/test_v0_16_5_regime_mixte_eval.py — v0.16.5 (2b-2).

Régime de persistance mixte de l'évaluation + verrou UI lecture seule.

CONCEPTION Y (cf. doc/cadrage_2b2_regime_mixte_verrou_eval.md) :
- Champs STABLES (titre, mode, afficher-barème, langue) → snapshot de la base
  via collecterFormulaire() + <form id="atl-eval-form">.
- BARÈMES → hors snapshot, drapeau _baremesModifies (oninput), poussés en un
  appel groupé à l'Enregistrer. sauverBareme (PATCH immédiat) supprimé.
- Opérations de structure → bloquées si modifications en attente
  (_garderAvantStructure), pour ne pas écraser une saisie via le re-render.
- Verrou lecture seule éval : réutilise _appliquerVerrouLectureSeule (base) via
  le <form>.

Pas de tests JS dans le dépôt → tests structurels + validation visuelle Laurent.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_APPLI = Path(__file__).resolve().parent.parent
_EVAL_JS = (_APPLI / "static" / "atelier_evaluation_oo.js").read_text("utf-8")
_TEMPLATE = (_APPLI / "templates" / "index.html").read_text("utf-8")


class TestFormEtSnapshot:
    def test_form_present_dans_template(self):
        assert 'id="atl-eval-form"' in _TEMPLATE

    def test_collecter_formulaire_champs_stables(self):
        # collecterFormulaire ne capture QUE les champs stables (pas les
        # barèmes — conception Y).
        m = re.search(r"collecterFormulaire\s*\(\s*\)\s*\{.*?\n  \}",
                      _EVAL_JS, re.DOTALL)
        assert m, "collecterFormulaire introuvable"
        corps = m.group(0)
        for champ in ("titre", "mode_notation",
                      "afficher_bareme_dans_exos", "item_langue_francaise"):
            assert champ in corps, f"{champ} attendu dans collecterFormulaire"
        # Les barèmes NE doivent PAS y être.
        assert "bareme_points" not in corps
        assert "data-exo-id" not in corps

    def test_listener_form_installe(self):
        assert "_installerListenerForm()" in _EVAL_JS

    def test_getter_modifie_combine(self):
        # modifie = snapshot (super) OU drapeau barèmes.
        assert "super.modifie || this._baremesModifies" in _EVAL_JS


class TestBaremesRegimeMixte:
    def test_sauver_bareme_supprime(self):
        # Plus de méthode ni de wrapper sauverBareme (hors commentaires).
        for ligne in _EVAL_JS.splitlines():
            sans_com = ligne.split("//")[0]
            assert "async sauverBareme" not in sans_com
            assert "window.atelEvalSauverBareme =" not in sans_com

    def test_inputs_bareme_ont_data_attrs_et_oninput(self):
        # Les inputs barème portent data-exo-id + data-bareme-champ et
        # marquent modifié via oninput (plus de PATCH immédiat).
        assert "data-bareme-champ=\"bareme_points\"" in _EVAL_JS
        assert "data-bareme-champ=\"bareme_qcm_ok\"" in _EVAL_JS
        assert 'oninput="atelEvalMarquerModifie()"' in _EVAL_JS

    def test_collecter_baremes_existe(self):
        assert re.search(r"_collecterBaremes\s*\(\s*\)\s*\{", _EVAL_JS)

    def test_sauvegarder_pousse_baremes_groupes(self):
        # sauvegarder() appelle l'endpoint barèmes groupés.
        assert "/baremes`" in _EVAL_JS


class TestGardeStructure:
    def test_garde_avant_structure_existe(self):
        assert re.search(r"_garderAvantStructure\s*\(\s*\)\s*\{", _EVAL_JS)

    @pytest.mark.parametrize("methode", [
        "ajouterExo", "retirerExo", "deplacerExo",
        "ajouterObjectif", "retirerObjectif",
    ])
    def test_garde_appelee_dans_structure(self, methode):
        # Chaque méthode de structure appelle la garde.
        m = re.search(rf"async {methode}\s*\([^)]*\)\s*\{{(.*?)\n  \}}",
                      _EVAL_JS, re.DOTALL)
        assert m, f"{methode} introuvable"
        assert "_garderAvantStructure()" in m.group(1), (
            f"{methode} doit appeler _garderAvantStructure()"
        )


class TestVerrouUIEval:
    def test_verrou_applique_dans_majtoolbar(self):
        # _majToolbar appelle le verrou hérité selon l'état.
        assert "_appliquerVerrouLectureSeule(etat === 'valide')" in _EVAL_JS


class TestPlusDeModifieFlag:
    def test_modifie_flag_supprime(self):
        # _modifieFlag ne doit plus apparaître que dans des commentaires.
        for ligne in _EVAL_JS.splitlines():
            sans_com = ligne.split("//")[0].split("*")[0]
            assert "_modifieFlag" not in sans_com, (
                f"_modifieFlag résiduel : {ligne.strip()!r}"
            )
