r"""
tests/test_v0_16_2_consolidation_eval.py — Étape 2a : consolidation de la base.

CONTEXTE
--------
L'atelier Évaluation (`atelier_evaluation_oo.js`) dupliquait des méthodes de
rendu PDF de sa classe de base `AtelierEditeur`, avec des IDs HTML en dur et
l'ancien `iframe.src = blob` (pas le viewer pdf.js de v0.16).

v0.16.2 (2a) aligne les IDs du template sur la convention `this.$()` de la base
(`pdf-iframe`, `rendu-status`, `rendu-erreur`, `rendu-loading`,
`rendu-placeholder`), configure `endpointRenduPdf`, et SUPPRIME les méthodes
dupliquées au profit de l'héritage. Bénéfice : l'évaluation passe au viewer
pdf.js sans code dédié.

CE QUE CES TESTS VERROUILLENT (structurels — pas de tests JS dans ce dépôt)
-------------------------------------------------------------------------
1. Le template a les IDs attendus par la base pour l'évaluation.
2. Les anciens IDs divergents ont disparu.
3. Les méthodes dupliquées ont été retirées de `atelier_evaluation_oo.js`
   (l'éval hérite). `voirLatex` est conservé (absent de la base).
4. `endpointRenduPdf` est configuré.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_APPLI = Path(__file__).resolve().parent.parent
_EVAL_JS = _APPLI / "static" / "atelier_evaluation_oo.js"
_BASE_JS = _APPLI / "static" / "atelier_editeur.js"
_TEMPLATE = _APPLI / "templates" / "index.html"


@pytest.fixture(scope="module")
def eval_js():
    return _EVAL_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def base_js():
    return _BASE_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def html():
    return _TEMPLATE.read_text(encoding="utf-8")


class TestIdsTemplateAlignes:
    """Le template doit porter les IDs attendus par this.$() de la base,
    avec le préfixe atl-eval."""

    @pytest.mark.parametrize("suffixe", [
        "pdf-iframe", "rendu-erreur",
        "rendu-loading", "rendu-placeholder",
        # v0.17.0 — rendu-status et btn-compiler ne sont plus statiques : ils
        # sont générés par AtelierEditeur._assurerToolbarRendu dans le
        # conteneur #atl-eval-rendu-toolbar.
        "rendu-toolbar",
    ])
    def test_id_present(self, html, suffixe):
        assert f'id="atl-eval-{suffixe}"' in html, (
            f"L'ID atl-eval-{suffixe} (attendu par AtelierEditeur via "
            f"this.$('{suffixe}')) est absent du template."
        )

    def test_toolbar_rendu_generee_v0_17_0(self, html):
        """v0.17.0 — btn-compiler de l'éval n'est plus dans le HTML statique
        (généré dans #atl-eval-rendu-toolbar)."""
        assert 'id="atl-eval-rendu-toolbar"' in html
        assert 'id="atl-eval-btn-compiler"' not in html

    @pytest.mark.parametrize("ancien", ["rendu-iframe", "rendu-message"])
    def test_ancien_id_supprime(self, html, ancien):
        assert f'id="atl-eval-{ancien}"' not in html, (
            f"L'ancien ID divergent atl-eval-{ancien} aurait dû être "
            f"renommé (v0.16.2)."
        )


class TestMethodesDupliqueesSupprimees:
    """Les copies locales de méthodes de la base doivent avoir disparu :
    l'évaluation en hérite désormais."""

    @pytest.mark.parametrize("methode", [
        "compilerRendu",
        "_afficherErreurCompilation",
        "toggleTexBrut",
        "_afficherTexBrut",
        "scrollToLigneTex",
    ])
    def test_methode_supprimee_de_eval(self, eval_js, methode):
        # On cherche une DÉCLARATION de méthode (2 espaces d'indentation),
        # pas une mention en commentaire.
        motif = re.compile(rf"^\s{{2}}(async\s+)?{re.escape(methode)}\s*\(",
                           re.MULTILINE)
        assert not motif.search(eval_js), (
            f"{methode} est encore déclarée dans atelier_evaluation_oo.js : "
            f"elle devrait être héritée d'AtelierEditeur (v0.16.2)."
        )

    def test_voirlatex_conserve(self, eval_js, base_js):
        # v0.16.2 : voirLatex n'existait que dans l'éval.
        # v0.17.1 : voirLatex est UNIFIÉ dans la base (récupère le .tex serveur
        # et l'affiche dans la modale commune). L'éval conserve encore sa propre
        # surcharge (déjà serveur+modale, compatible) — son éventuel retrait au
        # profit de l'unifié est prévu lors du nettoyage v0.17.2.
        decl = re.compile(r"^\s{2}async\s+voirLatex\s*\(", re.MULTILINE)
        assert decl.search(eval_js), (
            "voirLatex est conservé dans l'évaluation en v0.17.1."
        )
        # v0.17.1 — voirLatex est maintenant AUSSI dans la base (unification).
        assert decl.search(base_js), (
            "v0.17.1 : voirLatex doit être présent dans AtelierEditeur "
            "(unifié, récupère le .tex serveur)."
        )

    def test_sauvegarder_surchargee(self, eval_js):
        # 2a : sauvegarder() est surchargée dans l'éval (route renvoie
        # {evaluation:…}, format différent de la base). compilerRendu hérité
        # l'appelle pour la sauvegarde silencieuse avant compil.
        decl = re.compile(r"^\s{2}async\s+sauvegarder\s*\(", re.MULTILINE)
        assert decl.search(eval_js), (
            "sauvegarder() doit être surchargée dans l'évaluation (v0.16.2)."
        )


class TestConfigEndpoints:
    def test_endpoint_rendu_pdf_configure(self, eval_js):
        # Sans endpointRenduPdf, le compilerRendu hérité taperait la
        # mauvaise URL.
        assert re.search(r"endpointRenduPdf:\s*'/api/evaluations'", eval_js), (
            "endpointRenduPdf doit être configuré à '/api/evaluations' pour "
            "que compilerRendu hérité construise la bonne URL."
        )


class TestPasDeReferenceOrpheline:
    @pytest.mark.parametrize("ancien_id", [
        "atl-eval-rendu-message", "atl-eval-rendu-iframe",
    ])
    def test_pas_de_getElementById_orphelin(self, eval_js, ancien_id):
        # Hors commentaires : aucune ligne de code ne doit encore lire les
        # anciens IDs.
        for ligne in eval_js.splitlines():
            sans_commentaire = ligne.split("//")[0]
            assert ancien_id not in sans_commentaire, (
                f"Référence de code orpheline à {ancien_id} : {ligne.strip()!r}"
            )

    def test_wrapper_scroll_delegue_au_bon_nom(self, eval_js):
        # window.atelEvalScrollToLigneTex doit déléguer à scrollVersLigneTex
        # (méthode héritée), pas à l'ancienne scrollToLigneTex supprimée.
        m = re.search(
            r"atelEvalScrollToLigneTex\s*=\s*function[^}]*?"
            r"ATELIER_EVALUATION\.(\w+)\(",
            eval_js, re.DOTALL,
        )
        assert m, "Wrapper atelEvalScrollToLigneTex introuvable."
        assert m.group(1) == "scrollVersLigneTex", (
            f"Le wrapper délègue à {m.group(1)} ; attendu scrollVersLigneTex "
            f"(la copie locale scrollToLigneTex a été supprimée)."
        )
