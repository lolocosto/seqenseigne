"""Tests v0.13.7.5 — Scission mise_en_forme/mise_en_page, icônes SVG,
groupe Image partout, picker de taille, lettres calligraphiques.

Validation de la structure du JSON toolbar et de la cohérence avec
le dictionnaire ICONES_SVG du JS. Les générateurs (tableau, picker
taille) vivent côté JS et sont validés visuellement.
"""
import json
import re
from pathlib import Path

import pytest


RACINE_APPLI = Path(__file__).resolve().parent.parent
CHEMIN_JSON = RACINE_APPLI / "static" / "data" / "toolbar_seqenseigne.json"
CHEMIN_JS   = RACINE_APPLI / "static" / "editeur_latex.js"


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def toolbar():
    """Charge le JSON toolbar une fois par session."""
    with CHEMIN_JSON.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def codes_icones_js():
    """Extrait l'ensemble des clés du dictionnaire ICONES_SVG depuis le JS.

    On lit le JS comme texte et on extrait les noms entre la déclaration
    `const ICONES_SVG = {` et le `};` correspondant via une regex sur
    les clés au début de chaque ligne (format `nom: '...'`).
    """
    src = CHEMIN_JS.read_text(encoding="utf-8")
    debut = src.index("const ICONES_SVG = {")
    fin = src.index("\n  };", debut)
    bloc = src[debut:fin]
    cles = set(re.findall(r"^\s{4}([a-zA-Z][a-zA-Z0-9]*)\s*:", bloc, flags=re.M))
    cles.discard("const")
    return cles


# ── Structure générale du JSON ────────────────────────────────────────────

class TestStructureJSON:
    def test_version_majeure(self, toolbar):
        version = toolbar.get("_meta", {}).get("version", "")
        assert version.startswith("0.13.7.5") or version >= "0.13.7.5", \
            f"Version inattendue : {version!r}"

    def test_meta_documente_la_convention_icone(self, toolbar):
        meta = toolbar.get("_meta", {})
        conventions = " ".join(str(v) for v in meta.values())
        assert "icone" in conventions.lower(), \
            "Aucune convention 'icone' documentée dans _meta"

    def test_meta_documente_le_picker_taille(self, toolbar):
        """v0.13.7.5 introduit __PICKER_TAILLE__ : le _meta doit le
        mentionner pour que la convention reste découvrable.
        """
        meta = toolbar.get("_meta", {})
        textes = " ".join(str(v) for v in meta.values())
        assert "PICKER_TAILLE" in textes or "__PICKER_TAILLE__" in textes, \
            "La convention __PICKER_TAILLE__ doit être documentée dans _meta"

    def test_neuf_contextes(self, toolbar):
        contextes = toolbar["contextes"]
        attendus = {
            "variables", "exo-enonce", "exo-corrige", "notion-corps",
            "methode-corps", "fiche-section", "carte-recto", "carte-verso",
            "theme-description",
        }
        assert set(contextes.keys()) == attendus


# ── Scission mise_en_forme / mise_en_page ─────────────────────────────────

class TestScissionGroupes:
    def test_mise_en_forme_existe(self, toolbar):
        assert "mise_en_forme" in toolbar["groupes"]

    def test_mise_en_page_existe(self, toolbar):
        assert "mise_en_page" in toolbar["groupes"]

    def test_mise_en_forme_contient_les_six_items_attendus(self, toolbar):
        """Cadrage v0.13.7.5 révisé : gras, italique, monotype, souligné,
        exposant, indice (+ bouton taille via picker).
        """
        items = toolbar["groupes"]["mise_en_forme"]["items"]
        snippets = [it["snippet"] for it in items]
        assert any(r"\textbf"          in s for s in snippets), "\\textbf manquant"
        assert any(r"\textit"          in s for s in snippets), "\\textit manquant"
        assert any(r"\texttt"          in s for s in snippets), "\\texttt manquant"
        assert any(r"\underline"       in s for s in snippets), "\\underline manquant"
        assert any(r"\textsuperscript" in s for s in snippets), "\\textsuperscript manquant"
        assert any(r"\textsubscript"   in s for s in snippets), "\\textsubscript manquant"

    def test_mise_en_forme_contient_bouton_picker_taille(self, toolbar):
        """Le picker de taille s'ouvre via un snippet spécial."""
        items = toolbar["groupes"]["mise_en_forme"]["items"]
        snippets = [it["snippet"] for it in items]
        assert "__PICKER_TAILLE__" in snippets, \
            "Le bouton taille (snippet __PICKER_TAILLE__) doit être dans mise_en_forme"

    def test_mise_en_page_contient_les_items_attendus(self, toolbar):
        items = toolbar["groupes"]["mise_en_page"]["items"]
        snippets = [it["snippet"] for it in items]
        for cmd in [r"\centering", r"\raggedleft", r"\raggedright",
                    r"\smallskip", r"\medskip", r"\bigskip",
                    r"\newline", r"\par"]:
            assert any(cmd in s for s in snippets), f"{cmd} manquant"

    def test_mise_en_page_ne_contient_pas_de_mise_en_forme(self, toolbar):
        """Garantit que la scission a éloigné le gras/italique de
        mise_en_page (sinon doublon visuel pour l'utilisateur).
        """
        items = toolbar["groupes"]["mise_en_page"]["items"]
        snippets = [it["snippet"] for it in items]
        for cmd in [r"\textbf", r"\textit", r"\underline"]:
            assert not any(cmd in s for s in snippets), \
                f"{cmd} doit être dans mise_en_forme, pas mise_en_page"


# ── Maths : ajout des 4 commandes mathcal/mathbb/mathbf/mathrm ────────────

class TestMathsLettresSpeciales:
    def test_les_quatre_styles_maths_sont_presents(self, toolbar):
        """Cadrage v0.13.7.5 final : ajout de \\mathcal, \\mathbb,
        \\mathbf, \\mathrm dans le groupe maths_inline.
        """
        items = toolbar["groupes"]["maths_inline"]["items"]
        snippets = [it["snippet"] for it in items]
        for cmd in [r"\mathcal", r"\mathbb", r"\mathbf", r"\mathrm"]:
            assert any(cmd in s for s in snippets), \
                f"{cmd} manquant dans maths_inline"

    def test_ces_styles_acceptent_la_selection(self, toolbar):
        """Convention de wrapping : chaque snippet contient un • pour
        que la sélection soit prise en charge.
        """
        items = toolbar["groupes"]["maths_inline"]["items"]
        for it in items:
            snip = it["snippet"]
            if any(c in snip for c in [r"\mathcal", r"\mathbb", r"\mathbf", r"\mathrm"]):
                assert "•" in snip, \
                    f"Le snippet '{snip}' devrait contenir • pour entourer la sélection"


# ── Groupe Image disponible partout ───────────────────────────────────────

class TestImagePartout:
    def test_image_dans_tous_les_contextes(self, toolbar):
        contextes = toolbar["contextes"]
        manquants = [
            nom for nom, groupes in contextes.items()
            if "image" not in groupes
        ]
        assert manquants == [], \
            f"Contextes sans groupe 'image' : {manquants}"

    def test_groupe_image_existe(self, toolbar):
        assert "image" in toolbar["groupes"]

    def test_groupe_image_a_le_snippet_special(self, toolbar):
        items = toolbar["groupes"]["image"]["items"]
        assert any(it["snippet"] == "__NAVIGATEUR_IMAGES__" for it in items)


# ── Convention 'icone' : cohérence JSON ↔ JS ──────────────────────────────

class TestIconesCoherence:
    def test_codes_du_json_existent_cote_js(self, toolbar, codes_icones_js):
        """Chaque item porteur d'une clé 'icone' doit avoir un code
        connu côté JS, sinon le bouton s'affiche vide.
        """
        problemes = []
        for nom_groupe, grp in toolbar["groupes"].items():
            for item in grp.get("items", []):
                icone = item.get("icone")
                if icone and icone not in codes_icones_js:
                    problemes.append(
                        f"{nom_groupe}/{item.get('label', '?')}: "
                        f"icone='{icone}' inconnue côté JS"
                    )
        assert problemes == [], (
            "Items avec icône non reconnue par le JS :\n  - "
            + "\n  - ".join(problemes)
        )

    def test_icone_italic_disponible(self, codes_icones_js):
        """L'ajout de \\textit (cadrage v0.13.7.5 révisé) impose
        l'existence du code 'italic'.
        """
        assert "italic" in codes_icones_js, \
            "Code 'italic' attendu dans ICONES_SVG (pour \\textit)"

    def test_icone_taille_disponible(self, codes_icones_js):
        """Bouton picker de taille → code 'taille' attendu."""
        assert "taille" in codes_icones_js, \
            "Code 'taille' attendu dans ICONES_SVG (pour le picker)"

    def test_icones_mathstyle_disponibles(self, codes_icones_js):
        """4 nouvelles icônes pour les lettres maths."""
        for code in ["mathcal", "mathbb", "mathbf", "mathrm"]:
            assert code in codes_icones_js, \
                f"Code '{code}' attendu dans ICONES_SVG"

    def test_mise_en_forme_tous_avec_icone(self, toolbar):
        items = toolbar["groupes"]["mise_en_forme"]["items"]
        sans = [it["label"] for it in items if "icone" not in it]
        assert sans == [], f"Items mise_en_forme sans icône : {sans}"

    def test_mise_en_page_tous_avec_icone(self, toolbar):
        items = toolbar["groupes"]["mise_en_page"]["items"]
        sans = [it["label"] for it in items if "icone" not in it]
        assert sans == [], f"Items mise_en_page sans icône : {sans}"

    def test_maths_inline_tous_avec_icone(self, toolbar):
        items = toolbar["groupes"]["maths_inline"]["items"]
        sans = [it["label"] for it in items if "icone" not in it]
        assert sans == [], f"Items maths_inline sans icône : {sans}"

    def test_listes_tous_avec_icone(self, toolbar):
        items = toolbar["groupes"]["listes"]["items"]
        sans = [it["label"] for it in items if "icone" not in it]
        assert sans == [], f"Items listes sans icône : {sans}"


# ── Picker de taille : présence des 10 commandes côté JS ──────────────────

class TestPickerTaille:
    @pytest.fixture(scope="class")
    def src_js(self):
        return CHEMIN_JS.read_text(encoding="utf-8")

    def test_les_dix_tailles_latex_sont_listees(self, src_js):
        """Le tableau TAILLES_LATEX dans le JS doit contenir les 10
        commandes standard de taille (cf. cadrage v0.13.7.5 révisé).
        """
        attendues = [
            "tiny", "scriptsize", "footnotesize", "small", "normalsize",
            "large", "Large", "LARGE", "huge", "Huge",
        ]
        # On cherche le bloc TAILLES_LATEX entre `const TAILLES_LATEX = [`
        # et le `];` qui le ferme.
        debut = src_js.index("const TAILLES_LATEX = [")
        fin = src_js.index("\n  ];", debut)
        bloc = src_js[debut:fin]
        # Extraire les valeurs de cmd:
        cmds = set(re.findall(r"cmd:\s*'([A-Za-z]+)'", bloc))
        manquantes = [c for c in attendues if c not in cmds]
        assert manquantes == [], \
            f"Tailles manquantes dans TAILLES_LATEX : {manquantes}"

    def test_le_snippet_special_picker_est_dispatche_dans_js(self, src_js):
        """`__PICKER_TAILLE__` doit ouvrir la mini-modale 'taille'
        depuis _gererClicSnippet.
        """
        assert "__PICKER_TAILLE__" in src_js, \
            "Le snippet spécial __PICKER_TAILLE__ doit être géré côté JS"
        assert "_ouvrirMiniModale('taille')" in src_js, \
            "Le dispatch vers _ouvrirMiniModale('taille') doit exister"


# ── Compatibilité ascendante ──────────────────────────────────────────────

class TestCompatibiliteAscendante:
    def test_items_sans_icone_restent_supportes(self, toolbar):
        """Les groupes sans icône (label texte uniquement) doivent
        porter au moins un label non vide.
        """
        groupes_sans_icone = [
            "completer", "boites_pedago", "boites_titrees", "mise_en_evidence",
            "etapes", "annexe", "image",
            "xint_definitions", "xint_aleatoire", "xint_conditionnel",
            "maths_display",
        ]
        for nom in groupes_sans_icone:
            grp = toolbar["groupes"][nom]
            for item in grp["items"]:
                assert item.get("label"), \
                    f"Groupe '{nom}' : item sans label (et sans icône) → bouton vide"

    def test_chaque_item_a_un_snippet(self, toolbar):
        for nom_groupe, grp in toolbar["groupes"].items():
            for item in grp["items"]:
                assert "snippet" in item, \
                    f"{nom_groupe}/{item.get('label', '?')}: snippet manquant"
