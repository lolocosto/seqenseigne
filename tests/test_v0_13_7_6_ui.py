"""Tests v0.13.7.6 — Suppressions et améliorations d'UX :

- Slider largeur de colonne visible (label « Largeur : » + classes CSS
  spécifiques au rail webkit/firefox)
- Groupe « Listes » retiré du JSON toolbar (redondant avec générateur)
- Astérisques rouges sur champs obligatoires + légende dans les 5 ateliers
- Suppressions de textes parenthétiques (LaTeX libre, optionnel, …)
- Boutons ✎ Éditer manuels (skip scanner) sur Exercice/Variables,
  Notion/Méthode/items, Fiche/sections, Carte/Recto+Verso

Pas de test fonctionnel JS dynamique (dette héritée). On vérifie la
structure des fichiers livrés.
"""
import json
import re
from pathlib import Path

import pytest


RACINE_APPLI = Path(__file__).resolve().parent.parent
CHEMIN_JSON  = RACINE_APPLI / "static" / "data" / "toolbar_seqenseigne.json"
CHEMIN_JS    = RACINE_APPLI / "static" / "editeur_latex.js"
CHEMIN_CSS   = RACINE_APPLI / "static" / "app.css"
CHEMIN_HTML  = RACINE_APPLI / "templates" / "index.html"
CHEMIN_NOTION  = RACINE_APPLI / "static" / "atelier_notion.js"
CHEMIN_METHODE = RACINE_APPLI / "static" / "atelier_methode.js"
CHEMIN_FICHE   = RACINE_APPLI / "static" / "atelier_fiche.js"


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def toolbar():
    with CHEMIN_JSON.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def html():
    return CHEMIN_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css():
    return CHEMIN_CSS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def js_editeur():
    return CHEMIN_JS.read_text(encoding="utf-8")


# ── Versions ──────────────────────────────────────────────────────────────

class TestVersion:
    def test_json_version_bumpee(self, toolbar):
        version = toolbar.get("_meta", {}).get("version", "")
        assert version >= "0.13.7.6", f"Version inattendue : {version!r}"

    def test_js_version_bumpee(self, js_editeur):
        # On cherche la chaîne « v0.13.7.6 » dans le commentaire d'en-tête.
        debut = js_editeur[:1000]
        assert "v0.13.7.6" in debut, "L'en-tête de editeur_latex.js doit mentionner v0.13.7.6"


# ── Suppression du groupe Listes ───────────────────────────────────────────

class TestGroupeListesRetire:
    def test_aucun_contexte_ne_reference_listes(self, toolbar):
        """Le groupe 'listes' a été retiré : aucun contexte ne doit
        plus le référencer, sinon le rendu côté JS chercherait un
        groupe désormais marqué obsolète et rendrait du vide.
        """
        contextes = toolbar["contextes"]
        avec_listes = [nom for nom, grps in contextes.items() if "listes" in grps]
        assert avec_listes == [], (
            f"Contextes qui référencent encore 'listes' : {avec_listes}"
        )

    def test_groupe_listes_si_present_est_marque_obsolete(self, toolbar):
        """Si le groupe 'listes' existe encore (pour traçabilité), il
        doit avoir une marque d'obsolescence et une liste d'items vide.
        """
        listes = toolbar["groupes"].get("listes")
        if listes is None:
            return  # supprimé complètement : OK
        assert listes.get("items") == [], (
            "Le groupe 'listes' obsolète doit avoir items vide"
        )
        assert any("obsolete" in k.lower() for k in listes.keys()), (
            "Le groupe 'listes' obsolète doit porter une clé d'obsolescence "
            "(ex. _obsolete_v0_13_7_6) pour traçabilité"
        )

    def test_generateur_liste_toujours_disponible(self, js_editeur):
        """Le générateur ☰ Liste doit rester accessible côté JS : on
        ne supprime que le groupe de boutons rapides, pas le générateur.
        """
        assert 'data-generateur="liste"' in js_editeur, (
            "Le bouton générateur Liste doit toujours être présent"
        )


# ── Slider de largeur de colonne ──────────────────────────────────────────

class TestSliderLargeur:
    def test_label_largeur_present(self, js_editeur):
        """Cadrage v0.13.7.6 : le contrôle de largeur de colonne dans
        le générateur de tableau doit afficher un label « Largeur : »
        visible, sinon il n'est pas découvrable.
        """
        assert "Largeur :" in js_editeur or "Largeur&nbsp;:" in js_editeur, (
            "Le label « Largeur : » doit être ajouté devant le slider de ratio"
        )

    def test_css_slider_stylise_explicitement(self, css):
        """Le slider doit avoir un style explicite (rail bleu, poignée
        ronde) pour rester visible quel que soit le thème navigateur.
        """
        # Style webkit
        assert "ed-latex-tab-slider::-webkit-slider-runnable-track" in css, (
            "Style webkit du rail manquant"
        )
        assert "ed-latex-tab-slider::-webkit-slider-thumb" in css, (
            "Style webkit de la poignée manquant"
        )
        # Style firefox
        assert "ed-latex-tab-slider::-moz-range-track" in css, (
            "Style firefox du rail manquant"
        )
        assert "ed-latex-tab-slider::-moz-range-thumb" in css, (
            "Style firefox de la poignée manquant"
        )

    def test_slider_couleur_visible(self, css):
        """La couleur du rail rempli ou de la poignée doit être un bleu
        franc (pas un gris quasi invisible).
        """
        # On vise spécifiquement les zones de style webkit/firefox du
        # slider : c'est là que vit la couleur de la poignée et du rail
        # rempli (mozprogress).
        for marqueur in [
            "ed-latex-tab-slider::-webkit-slider-thumb",
            "ed-latex-tab-slider::-moz-range-thumb",
            "ed-latex-tab-slider::-moz-range-progress",
        ]:
            assert marqueur in css, f"Sélecteur CSS manquant : {marqueur}"
        # Cherche une couleur bleue explicite quelque part dans les 3000
        # caractères suivant le premier sélecteur du slider style v0.13.7.6.
        idx = css.find("ed-latex-tab-slider::-webkit-slider-runnable-track")
        assert idx >= 0
        bloc = css[idx: idx + 3000]
        rouges = ["#4a90e2", "#2c6cb0", "#3b82f6", "#2563eb", "#1f5a99"]
        assert any(c in bloc for c in rouges), (
            "Le slider doit utiliser une couleur bleue franche dans son "
            "rail et/ou sa poignée, pas du gris"
        )


# ── Astérisques rouges et légendes (HTML) ────────────────────────────────

class TestAsterisquesEtLegendes:
    def test_legende_dans_les_cinq_ateliers(self, html):
        """Une légende `atl-legende-obligatoire` doit apparaître dans
        chacun des 5 formulaires d'atelier (Exercice, Notion, Méthode,
        Fiche, Carte). On compte les occurrences ; doit être >= 5.
        """
        nb = html.count("atl-legende-obligatoire")
        # Compte les divs (chaque légende a ouverture + utilisation dans la
        # phrase, donc on compte les ouvertures de div).
        ouvertures = html.count('class="atl-legende-obligatoire"')
        assert ouvertures >= 5, (
            f"Attendu >= 5 légendes obligatoires, trouvé {ouvertures} "
            f"(occurrences totales du nom de classe : {nb})"
        )

    def test_asterisque_dans_titre_exercice(self, html):
        """L'asterisque doit être attaché au label Titre de l'atelier
        Exercice. Le label vient juste avant l'input ; on vise sa
        position en cherchant le bloc data-slot-reprendre-obj qui le
        contient (l'id atl-exercice-titre est aussi présent dans ce bloc).
        """
        idx = html.index('data-slot-reprendre-obj="atl-exercice-titre"')
        zone = html[idx: idx + 300]
        assert 'atl-label-obligatoire' in zone, (
            "Le label Titre de Exercice doit porter une asterisque"
        )

    def test_asterisques_corps_obligatoires(self, html):
        """Notion et Méthode : le label « Corps » doit porter l'asterisque."""
        # Notion
        idx = html.index("atl-notion-corps")
        zone = html[max(0, idx - 300): idx + 100]
        assert "atl-label-obligatoire" in zone, "Corps de Notion sans *"
        # Méthode
        idx = html.index("atl-methode-corps")
        zone = html[max(0, idx - 300): idx + 100]
        assert "atl-label-obligatoire" in zone, "Corps de Méthode sans *"

    def test_asterisques_carte(self, html):
        """Carte : titre, type pédagogique, type technique, recto, verso."""
        # Titre : on vise le LABEL associé (pas la première mention de l'id,
        # qui apparaît avant dans data-slot-reprendre-obj).
        idx = html.index('for="atl-carte-titre"')
        zone = html[idx: idx + 200]
        assert "atl-label-obligatoire" in zone, (
            "Le label associé à atl-carte-titre doit porter une asterisque"
        )
        # Type pédago + tech : on cherche le label
        for label_recherche in ["Type pédagogique", "Type technique"]:
            idx = html.index(label_recherche)
            zone = html[idx: idx + 200]
            assert "atl-label-obligatoire" in zone, (
                f"Label « {label_recherche} » de Carte sans *"
            )

    def test_asterisques_carte_recto_verso(self, html):
        """Le titre du cadre Recto et Verso doit porter l'asterisque."""
        # On cherche la chaîne « Recto (question) » et « Verso (réponse) »
        for nom in ["Recto (question)", "Verso (réponse)"]:
            idx = html.index(nom)
            zone = html[idx: idx + 200]
            assert "atl-label-obligatoire" in zone, (
                f"Le titre du cadre « {nom} » de Carte doit porter une asterisque"
            )


# ── Suppression des textes parenthétiques ─────────────────────────────────

class TestSuppressionsTextes:
    def test_pas_de_latex_libre_optionnel_dans_variables(self, html):
        """Le texte « (LaTeX libre, optionnel) » dans le header replicable
        de Variables doit être supprimé.
        """
        assert "(LaTeX libre, optionnel)" not in html, (
            "Le texte « (LaTeX libre, optionnel) » de Variables doit être supprimé"
        )

    def test_pas_de_latex_libre_dans_enonces(self, html):
        """L'énoncé/corrigé principal ne doit plus porter « (LaTeX libre) »
        ni « (obligatoire) ». Reste tolérée la présence de cette chaîne
        dans Thème (hors périmètre des 5 ateliers concernés).
        """
        # On vise les énoncés exercice par contexte data-contexte-latex
        for tex_id in ["atl-exercice-enonce", "atl-exercice-corrige",
                       "atl-exercice-remed-enonce", "atl-exercice-remed-corrige"]:
            idx = html.index(tex_id)
            zone = html[max(0, idx - 400): idx]
            # Le label associé est avant — il ne doit pas contenir « LaTeX libre »
            assert "(LaTeX libre)" not in zone, (
                f"Le label de {tex_id} contient encore « (LaTeX libre) »"
            )

    def test_pas_de_obligatoire_paren_corrige(self, html):
        """Corrigé principal : la mention « (obligatoire) » remplacée par
        l'asterisque rouge.
        """
        idx = html.index("atl-exercice-corrige")
        zone = html[max(0, idx - 400): idx]
        assert "(obligatoire)" not in zone, (
            "Le label Corrigé doit porter une asterisque, pas le mot « (obligatoire) »"
        )

    def test_pas_de_mention_corps_definition(self, html):
        """Notion : « (définition principale, LaTeX libre) » supprimé."""
        assert "(définition principale, LaTeX libre)" not in html

    def test_pas_de_mention_corps_methode(self, html):
        """Méthode : « (étapes de la méthode, LaTeX libre) » supprimé."""
        assert "(étapes de la méthode, LaTeX libre)" not in html

    def test_pas_de_mention_zones_fiche(self, html):
        """Fiche : « (chaque zone produit un bloc dans la fiche imprimée) »
        supprimé.
        """
        assert "(chaque zone produit un bloc dans la fiche imprimée)" not in html
        # On peut être plus tolérant et vérifier juste la fraction « chaque zone produit »
        assert "chaque zone produit un bloc" not in html

    def test_pas_de_mention_tikz_inline_carte(self, html):
        """Carte : les p « LaTeX libre. TikZ inline supporté pour les
        figures. » et « LaTeX libre. Pour Pythagore : … » supprimés.
        """
        assert "TikZ inline supporté pour les figures." not in html
        assert "Pour Pythagore : figure complétée" not in html


# ── Bouton ✎ Éditer manuel (skip scanner) ─────────────────────────────────

class TestBoutonsManuels:
    def test_exo_variables_a_bouton_manuel(self, html):
        """Le bouton ✎ Éditer manuel doit être présent dans le header
        repliable de Variables avec stopPropagation pour ne pas
        déclencher le toggle.
        """
        idx = html.index("atl-exercice-variables-chevron")
        zone = html[idx: idx + 1000]
        assert "btn-ed-latex-manuel" in zone, (
            "Bouton ✎ Éditer manuel absent dans le header de Variables"
        )
        assert "stopPropagation" in zone, (
            "stopPropagation manquant : le bouton va déclencher le toggle"
        )

    def test_exo_variables_textarea_skip_scanner(self, html):
        """Le textarea Variables doit porter data-ed-latex-attache="1"
        pour que le scanner global n'ajoute pas un deuxième bouton.
        """
        idx = html.index('id="atl-exercice-variables"')
        zone = html[idx: idx + 500]
        assert 'data-ed-latex-attache="1"' in zone, (
            "Le textarea Variables n'est pas marqué pour skip scanner — "
            "le scanner posera un deuxième bouton ✎"
        )

    def test_carte_recto_verso_textareas_skip_scanner(self, html):
        """Recto et Verso de Carte : textareas marqués skip scanner
        (les boutons ✎ sont posés manuellement à côté du titre du cadre).
        """
        for tid in ["atl-carte-recto", "atl-carte-verso"]:
            idx = html.index(f'id="{tid}"')
            zone = html[idx: idx + 500]
            assert 'data-ed-latex-attache="1"' in zone, (
                f"Textarea {tid} pas marqué pour skip scanner"
            )

    def test_carte_recto_verso_bouton_a_cote_titre(self, html):
        """Le bouton ✎ Éditer manuel doit apparaître dans la même ligne
        que le titre du cadre Recto/Verso (classe atl-cadre-titre-row).
        """
        assert "atl-cadre-titre-row" in html, (
            "La nouvelle classe atl-cadre-titre-row (titre + bouton ✎ sur "
            "une même ligne) doit exister dans le HTML"
        )

    def test_notion_items_skip_scanner_et_bouton_manuel(self):
        """Les items de section Notion (rows=2) doivent porter
        data-ed-latex-attache="1" et un bouton ✎ manuel inline.
        """
        src = CHEMIN_NOTION.read_text(encoding="utf-8")
        assert 'data-ed-latex-attache="1"' in src, (
            "Les textareas d'item de Notion doivent être marqués skip scanner"
        )
        assert "btn-ed-latex-manuel" in src, (
            "Les actions d'item de Notion doivent contenir un bouton ✎ manuel"
        )

    def test_methode_items_skip_scanner_et_bouton_manuel(self):
        """Idem pour Méthode."""
        src = CHEMIN_METHODE.read_text(encoding="utf-8")
        assert 'data-ed-latex-attache="1"' in src
        assert "btn-ed-latex-manuel" in src

    def test_fiche_sections_skip_scanner_et_bouton_manuel(self):
        """Fiche : textarea de section marqué skip scanner et bouton ✎
        manuel dans la ligne d'actions du haut.
        """
        src = CHEMIN_FICHE.read_text(encoding="utf-8")
        assert 'data-ed-latex-attache="1"' in src, (
            "Le textarea de section de Fiche doit être marqué skip scanner"
        )
        assert "btn-ed-latex-manuel" in src, (
            "Le bouton ✎ manuel doit être ajouté à la ligne d'actions de la "
            "section Fiche"
        )


# ── CSS legend, asterisque, bouton manuel ─────────────────────────────────

class TestCssV0_13_7_6:
    def test_classes_asterisque_definies(self, css):
        """Les classes utilisées dans le HTML doivent être stylées."""
        assert ".atl-label-obligatoire" in css, (
            "Style de .atl-label-obligatoire manquant"
        )
        assert ".atl-legende-obligatoire" in css, (
            "Style de .atl-legende-obligatoire manquant"
        )
        assert ".btn-ed-latex-manuel" in css, (
            "Style de .btn-ed-latex-manuel manquant"
        )

    def test_asterisque_est_rouge(self, css):
        """L'asterisque doit avoir une couleur rouge explicite (pas
        juste l'héritage du thème).
        """
        bloc = ""
        if ".atl-label-obligatoire" in css:
            idx = css.index(".atl-label-obligatoire")
            bloc = css[idx: idx + 400]
        # On accepte plusieurs nuances de rouge classique.
        rouges = ["#d32f2f", "#dc2626", "#ef4444", "#c00", "#e53935", "red"]
        assert any(r in bloc for r in rouges), (
            "L'asterisque obligatoire doit avoir une couleur rouge explicite "
            f"(cherché : {rouges})"
        )
