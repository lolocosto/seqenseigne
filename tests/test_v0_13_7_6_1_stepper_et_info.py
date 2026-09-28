"""Tests v0.13.7.6.1 — Patchs UI tableau + endpoint info cache PDF carte.

Cette livraison contient :
1. Stepper [−] ×N [+] à la place du slider dans le générateur tableau
2. Boutons d'alignement à largeur fixe (corrige scrollbar horizontale)
3. Tooltip `\\cellVert` corrigé (« verticale », pas « verte »)
4. Endpoint backend `GET /api/cartes/<id>/rendu-pdf/info` pour vérifier
   l'existence du cache PDF sans recompiler
5. Auto-chargement du PDF à l'ouverture de l'onglet Rendu PDF de la
   carte si le cache est valide (côté JS : tests visuels uniquement)
"""
import json
import re
from pathlib import Path

import pytest


RACINE_APPLI = Path(__file__).resolve().parent.parent
CHEMIN_JSON  = RACINE_APPLI / "static" / "data" / "toolbar_seqenseigne.json"
CHEMIN_JS_ED = RACINE_APPLI / "static" / "editeur_latex.js"
# v0.14.4 — Le contenu d'atelier_atomique.js a migré dans
# atelier_editeur.js (suppression de la classe AtelierAtomique).
# Les tests qui validaient le comportement du code ont juste besoin
# de pointer vers le nouveau fichier.
CHEMIN_JS_AT = RACINE_APPLI / "static" / "atelier_editeur.js"
CHEMIN_CSS   = RACINE_APPLI / "static" / "app.css"
# v0.14.4 — Les routes /api/cartes/<id>/rendu-pdf, /info, /rendu-tex
# ont été supprimées de routes/cartes_automatisme.py. La carte utilise
# désormais l'API unifiée /api/atomes/carte/<id>/... portée par
# routes/rendu_atome.py. Les tests qui validaient la route /info ont
# besoin de pointer vers ce fichier.
CHEMIN_ROUTE = RACINE_APPLI / "routes" / "rendu_atome.py"


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def toolbar():
    with CHEMIN_JSON.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def js_editeur():
    return CHEMIN_JS_ED.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def js_atomique():
    return CHEMIN_JS_AT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css():
    return CHEMIN_CSS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def route_carte():
    return CHEMIN_ROUTE.read_text(encoding="utf-8")


# ── Versions ──────────────────────────────────────────────────────────────

class TestVersionBumpee:
    def test_json_version_v0_13_7_6_1(self, toolbar):
        version = toolbar.get("_meta", {}).get("version", "")
        assert version == "0.13.7.6.1" or version > "0.13.7.6", \
            f"Version inattendue : {version!r}"

    def test_js_editeur_version_bumpee(self, js_editeur):
        debut = js_editeur[:1500]
        assert "v0.13.7.6.1" in debut, "En-tête de editeur_latex.js doit mentionner v0.13.7.6.1"


# ── Tooltip cellVert ──────────────────────────────────────────────────────

class TestTooltipCellVert:
    def test_tooltip_corrige(self, toolbar):
        """\\cellVert : verticale, pas verte (corrige confusion v0.13.7.5/6)."""
        # On scanne tous les groupes qui contiennent un item cellVert
        items_cellvert = []
        for nom_groupe, grp in toolbar.get("groupes", {}).items():
            for item in grp.get("items", []):
                if "cellVert" in item.get("snippet", ""):
                    items_cellvert.append((nom_groupe, item))
        assert items_cellvert, "Aucun item \\cellVert trouvé dans le JSON"
        for nom_groupe, item in items_cellvert:
            tooltip = item.get("tooltip", "")
            assert "verticale" in tooltip.lower(), \
                f"Tooltip de \\cellVert ({nom_groupe}) doit mentionner « verticale »"
            assert "verte" not in tooltip.lower(), \
                f"Tooltip de \\cellVert ({nom_groupe}) ne doit plus dire « verte »"


# ── Stepper de largeur de colonne ─────────────────────────────────────────

class TestStepperLargeur:
    def test_stepper_present_dans_js(self, js_editeur):
        """Le HTML rendu par _construireLigneColonne doit contenir des
        boutons stepper, pas un slider.
        """
        assert "ed-latex-tab-stepper-btn" in js_editeur, (
            "Le bouton stepper (.ed-latex-tab-stepper-btn) doit exister "
            "dans editeur_latex.js"
        )
        # Le caractère « − » du bouton diminuer (U+2212, pas un trait d'union ASCII)
        # ou « + » du bouton augmenter doivent être présents dans le code.
        assert "−" in js_editeur or "data-direction=\"-1\"" in js_editeur, (
            "Le bouton « − » du stepper doit être présent"
        )

    def test_slider_remplace(self, js_editeur):
        """Le slider <input type=range class=ed-latex-tab-slider> ne
        doit plus apparaître dans le HTML rendu (il est remplacé par
        le stepper). Les références CSS résiduelles sont tolérées
        (commentées).
        """
        # On cherche la chaîne d'instanciation du <input type="range" du slider
        assert 'type="range"' not in js_editeur, (
            "Le slider <input type=range> doit être supprimé du HTML rendu"
        )

    def test_lecture_ratio_depuis_dataset(self, js_editeur):
        """`_lireConfigColonnes` doit lire le ratio depuis le dataset
        du compteur, pas depuis un slider.
        """
        # On vérifie la présence du nouveau pattern de lecture
        assert "dataset.ratio" in js_editeur, (
            "_lireConfigColonnes doit lire le ratio depuis dataset.ratio"
        )

    def test_css_stepper_defini(self, css):
        """La classe .ed-latex-tab-stepper-btn doit être stylée."""
        assert ".ed-latex-tab-stepper-btn" in css, (
            "Style CSS .ed-latex-tab-stepper-btn manquant"
        )

    def test_css_align_largeur_fixe(self, css):
        """Le bug v0.13.7.6 (boutons d'alignement excessifs causant
        scrollbar horizontale) est corrigé par une largeur fixe
        explicite sur .ed-latex-tab-align.
        """
        # On vise les styles v0.13.7.6.1 ajoutés en fin de fichier
        # (le sélecteur existe aussi plus haut sans largeur fixe).
        # Recherche d'un bloc qui combine .ed-latex-tab-align et width: 28px
        # ou similaire.
        match = re.search(
            r"\.ed-latex-tab-align\s*\{[^}]*width\s*:\s*\d+px",
            css,
            re.S
        )
        assert match, (
            "Style .ed-latex-tab-align doit avoir une width fixe en pixels "
            "(correction du bug scrollbar horizontale)"
        )


# ── Backend : route /info ─────────────────────────────────────────────────

class TestRouteInfoCarte:
    """v0.14.4 — La route a migré de cartes_automatisme.py (URL
    /api/cartes/<id>/rendu-pdf/info) vers rendu_atome.py (URL unifiée
    /api/atomes/<type>/<id>/rendu-pdf/info, valable pour les 5 types).
    Les tests valident la même logique au nouvel emplacement.
    """

    def test_route_info_existe(self, route_carte):
        """L'endpoint GET .../rendu-pdf/info doit exister."""
        # v0.14.4 — On cherche au moins une occurrence DANS un décorateur
        # @bp.route, pas dans un docstring/commentaire d'en-tête.
        # Pattern : "@bp.route" suivi de la chaîne contenant "rendu-pdf/info".
        import re
        m = re.search(
            r"@bp\.route\([^)]*rendu-pdf/info[^)]*\)",
            route_carte,
        )
        assert m, (
            "Route GET .../rendu-pdf/info manquante (aucun @bp.route ne "
            "définit cet endpoint)."
        )
        # On accepte les guillemets simples et doubles : routes/rendu_atome.py
        # utilise methods=['GET'] tandis que routes/cartes_automatisme.py
        # historique utilisait methods=["GET"].
        decorateur = m.group(0)
        assert "methods=['GET']" in decorateur or 'methods=["GET"]' in decorateur, (
            f"Le décorateur doit déclarer methods=['GET'] : {decorateur}"
        )

    def test_route_info_renvoie_cache_valide(self, route_carte):
        """La route info doit renvoyer une réponse JSON contenant la
        clé `cache_valide`.
        """
        # v0.14.4 — On cherche le décorateur @bp.route qui définit la
        # route /info (pas la première occurrence textuelle, qui peut
        # être dans un docstring d'en-tête).
        import re
        m = re.search(
            r"@bp\.route\([^)]*rendu-pdf/info[^)]*\)",
            route_carte,
        )
        assert m, "Décorateur @bp.route(.../rendu-pdf/info) introuvable"
        # On vise la zone autour de la déclaration de la route
        idx = m.start()
        zone = route_carte[idx: idx + 2500]
        assert "cache_valide" in zone, (
            "La route /info doit renvoyer une réponse JSON {cache_valide: bool}"
        )

    def test_route_info_n_appelle_pas_compiler_atome(self, route_carte):
        """La route info NE doit PAS appeler compiler_atome — sinon
        elle déclencherait une compilation, perdant tout l'intérêt
        de la séparation info/compilation.
        """
        # v0.14.4 — Idem : on cible le décorateur, pas un commentaire.
        import re
        m = re.search(
            r"@bp\.route\([^)]*rendu-pdf/info[^)]*\)",
            route_carte,
        )
        assert m
        idx = m.start()
        # On extrait la fonction (jusqu'au prochain @bp.route ou EOF)
        fin = route_carte.find("@bp.route", idx + 1)
        fin = fin if fin > 0 else len(route_carte)
        corps_route = route_carte[idx: fin]
        assert "compiler_atome(" not in corps_route, (
            "La route /info ne doit PAS appeler compiler_atome — elle doit "
            "seulement hasher le .tex et vérifier l'existence du fichier de cache"
        )

    def test_route_info_utilise_hash_et_chemin_cache(self, route_carte):
        """La route info doit utiliser les helpers hash_tex et
        chemin_pdf_cache pour faire son travail de manière standard.
        """
        # v0.14.4 — Idem.
        import re
        m = re.search(
            r"@bp\.route\([^)]*rendu-pdf/info[^)]*\)",
            route_carte,
        )
        assert m
        idx = m.start()
        fin = route_carte.find("@bp.route", idx + 1)
        fin = fin if fin > 0 else len(route_carte)
        corps = route_carte[idx: fin]
        assert "hash_tex" in corps, "Doit utiliser hash_tex"
        assert "chemin_pdf_cache" in corps, "Doit utiliser chemin_pdf_cache"


# ── JS : auto-chargement à l'ouverture de l'onglet (côté carte/atomique) ──

class TestAutoChargementCarte:
    """v0.14.4 — La machinerie d'auto-chargement a migré de
    AtelierAtomique (atelier_atomique.js) vers AtelierEditeur
    (atelier_editeur.js). La logique est inchangée, juste la classe
    porteuse a changé. Les tests valident le code au nouvel emplacement.
    """

    def test_basculer_onglet_surcharge(self, js_atomique):
        """AtelierEditeur.basculerOnglet doit déclencher la vérification
        du cache à l'ouverture de l'onglet rendu.

        Avant v0.14.4 : AtelierAtomique surchargeait basculerOnglet
        pour appeler verifierCacheEtAfficher. La classe intermédiaire
        a été supprimée et la logique est désormais directement dans
        AtelierEditeur.basculerOnglet — plus de surcharge nécessaire,
        on cherche juste la présence du branchement.
        """
        assert "basculerOnglet(tab)" in js_atomique, (
            "AtelierEditeur doit définir une méthode basculerOnglet"
        )
        # Doit faire un traitement spécifique pour 'rendu' qui appelle
        # verifierCacheEtAfficher.
        idx = js_atomique.index("basculerOnglet(tab)")
        zone = js_atomique[idx: idx + 1800]
        assert "verifierCacheEtAfficher" in zone, (
            "basculerOnglet doit appeler verifierCacheEtAfficher pour 'rendu'"
        )

    def test_methode_verifier_cache_definie(self, js_atomique):
        """Méthode verifierCacheEtAfficher définie et bien câblée."""
        assert "verifierCacheEtAfficher" in js_atomique
        assert "/rendu-pdf/info" in js_atomique, (
            "verifierCacheEtAfficher doit appeler l'endpoint /rendu-pdf/info"
        )
        assert "cache_valide" in js_atomique, (
            "Le résultat de l'endpoint info contient `cache_valide`"
        )

    def test_status_chargement_auto(self, js_atomique):
        """Quand on charge depuis le cache automatiquement, le statut
        affiché doit être différent du « Compilation en cours… »
        classique.
        """
        assert "Chargement du PDF en cache" in js_atomique or \
               "Chargement depuis le cache" in js_atomique, (
            "Un message de statut spécifique au chargement-cache doit exister"
        )
