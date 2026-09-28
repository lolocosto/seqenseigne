"""Tests v0.15.0.2.a — Restauration des onglets Référentiel.

Contexte
--------
v0.13.6.4 avait introduit dans `templates/index.html` un bandeau de
2 onglets dans l'atelier Référentiel (« Tableau de bord » / « Documents
à publier ») avec deux panneaux frères `#atl-ref-panneau-dashboard` et
`#atl-ref-panneau-documents`.

Une livraison post-v0.13.6.5.1.1 non documentée a supprimé silencieusement
ces éléments HTML, sans toucher au JS (`atelRefChangerOnglet`,
`atelRefRendreDocuments`, etc.) ni au backend (`routes/referentiel_documents.py`,
`routes/referentiel_documents_compilation.py`). Résultat : la
fonctionnalité « Documents à publier » est devenue inaccessible —
détecté fin mai 2026 par le mainteneur quand il a voulu y revenir.

v0.15.0.2.a restaure ces éléments à l'identique. Ces tests sont des
**garde-fous** pour éviter qu'une future livraison les supprime à
nouveau sans qu'on s'en aperçoive (= ce qui s'était passé entre
v0.13.6.5.1.1 et v0.15).
"""
from __future__ import annotations
from pathlib import Path

import pytest


RACINE_APPLI = Path(__file__).resolve().parent.parent
CHEMIN_HTML = RACINE_APPLI / "templates" / "index.html"


@pytest.fixture(scope="module")
def html() -> str:
    return CHEMIN_HTML.read_text(encoding="utf-8")


class TestOngletsReferentielHtml:
    """Les éléments DOM attendus par atelRefChangerOnglet sont présents
    dans le template, et dans le bon ordre.
    """

    def test_panneau_referentiel_present(self, html):
        # Sanity : le panneau de l'atelier Référentiel existe (c'est
        # le contexte dans lequel doivent vivre les onglets).
        assert 'id="atl-referentiel"' in html

    def test_bouton_onglet_dashboard_present(self, html):
        # data-tab="dashboard" est lu par atelRefChangerOnglet (ligne 827
        # de atelier_referentiel.js).
        assert 'data-tab="dashboard"' in html
        # Et il a la classe .atl-ref-onglet attendue par le sélecteur
        # `document.querySelectorAll('.atl-ref-onglet')` (ligne 826).
        # On vérifie la présence sur la même ligne que le data-tab pour
        # éviter un faux positif où la classe serait posée ailleurs.
        ligne_bouton = None
        for ligne in html.splitlines():
            if 'data-tab="dashboard"' in ligne:
                ligne_bouton = ligne
                break
        assert ligne_bouton is not None
        assert 'atl-ref-onglet' in ligne_bouton

    def test_bouton_onglet_documents_present(self, html):
        assert 'data-tab="documents"' in html
        ligne_bouton = None
        for ligne in html.splitlines():
            if 'data-tab="documents"' in ligne:
                ligne_bouton = ligne
                break
        assert ligne_bouton is not None
        assert 'atl-ref-onglet' in ligne_bouton

    def test_onglet_dashboard_appelle_le_handler_js(self, html):
        # L'onclick doit cibler atelRefChangerOnglet pour basculer.
        assert "atelRefChangerOnglet('dashboard')" in html

    def test_onglet_documents_appelle_le_handler_js(self, html):
        assert "atelRefChangerOnglet('documents')" in html

    def test_panneau_dashboard_present(self, html):
        # Le wrapper #atl-ref-panneau-dashboard englobe l'arbre. Le JS
        # masque ce panneau quand l'utilisateur bascule sur l'onglet
        # « Documents à publier ».
        assert 'id="atl-ref-panneau-dashboard"' in html

    def test_panneau_documents_present(self, html):
        # Le wrapper #atl-ref-panneau-documents est le réceptacle des
        # documents publiables, rempli dynamiquement par
        # atelRefChargerEtRendreDocuments().
        assert 'id="atl-ref-panneau-documents"' in html

    def test_arbre_dashboard_reste_present(self, html):
        # L'arbre du tableau de bord ne doit pas avoir été perdu en
        # cours de route. Reste à l'intérieur du nouveau wrapper.
        assert 'id="atl-ref-arbre"' in html

    def test_ordre_des_panneaux_dans_le_html(self, html):
        # Les onglets doivent venir AVANT les panneaux, et le panneau
        # dashboard AVANT le panneau documents (pour respecter l'ordre
        # de lecture logique).
        pos_onglet_dash = html.find('data-tab="dashboard"')
        pos_onglet_docs = html.find('data-tab="documents"')
        pos_panneau_dash = html.find('id="atl-ref-panneau-dashboard"')
        pos_panneau_docs = html.find('id="atl-ref-panneau-documents"')

        for pos, nom in [
            (pos_onglet_dash, "onglet dashboard"),
            (pos_onglet_docs, "onglet documents"),
            (pos_panneau_dash, "panneau dashboard"),
            (pos_panneau_docs, "panneau documents"),
        ]:
            assert pos > 0, f"Élément manquant : {nom}"

        assert pos_onglet_dash < pos_onglet_docs, (
            "Onglet 'Tableau de bord' doit précéder 'Documents à publier'"
        )
        assert pos_onglet_docs < pos_panneau_dash, (
            "Les onglets doivent venir avant les panneaux"
        )
        assert pos_panneau_dash < pos_panneau_docs, (
            "Panneau dashboard doit précéder panneau documents"
        )

    def test_panneau_documents_cache_par_defaut(self, html):
        # Le JS atelRefChangerOnglet('dashboard') est appelé à chaque
        # sélection d'un référentiel pour forcer l'onglet « Tableau de
        # bord ». Mais avant ce premier appel, il faut que le panneau
        # documents soit caché côté HTML statique pour ne pas montrer
        # un panneau vide au premier paint.
        # On cherche le passage à display:none autour de l'id.
        debut = html.find('id="atl-ref-panneau-documents"')
        assert debut > 0
        # Regarde dans les ~80 caractères qui suivent l'id, où devrait
        # se trouver `style="display:none"` sur le même tag.
        fenetre = html[debut: debut + 200]
        # On accepte les deux ordres possibles (style avant ou après id),
        # mais ici on a posé l'id en premier puis le style.
        assert 'display:none' in fenetre or 'display: none' in fenetre, (
            f"Le panneau documents doit avoir display:none par défaut. "
            f"Contexte : {fenetre!r}"
        )
