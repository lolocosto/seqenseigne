"""Tests v0.14.1 — Renommage `exo` → `exercice` partout pour cohérence
avec le préfixe utilisé par les 4 autres ateliers (notion, methode,
fiche, carte).

Cette livraison est un pur renommage cosmétique, sans changement de
comportement. Les tests vérifient que l'ancien suffixe `exo` n'apparaît
plus dans les identifiants DOM / JS / Python concernés.

Ne sont PAS dans le périmètre du renommage :
- Le mot 'exos' (pluriel, lié à des concepts métier — recap_exos.py,
  table exercice_objectifs etc.)
- Les commentaires en français qui contiennent 'exo' comme abréviation
  du métier
- Le type 'exercice' déjà utilisé dans TABLES_ATOMES et les URLs
  /api/atomes/exercice/...
"""
from pathlib import Path

import pytest


RACINE_APPLI = Path(__file__).resolve().parent.parent
CHEMIN_HTML  = RACINE_APPLI / "templates" / "index.html"
CHEMIN_APP_JS = RACINE_APPLI / "static" / "app.js"
CHEMIN_EXERCICE_JS = RACINE_APPLI / "static" / "atelier_exercice.js"

# Fichiers concernés par le renommage (où le pattern ne doit plus
# apparaître).
FICHIERS_RENOMMES = [
    "templates/index.html",
    "static/app.js",
    "static/atelier.js",
    "static/atelier_commun.js",
    "static/atelier_editeur.js",
    "static/atelier_etat_edition.js",
    "static/atelier_exercice.js",
    "static/rendu_atome.js",
]


@pytest.fixture(scope="module")
def html():
    return CHEMIN_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def app_js():
    return CHEMIN_APP_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def exercice_js():
    return CHEMIN_EXERCICE_JS.read_text(encoding="utf-8")


# ── Anciens patterns absents ─────────────────────────────────────────────

class TestAnciensPatternsAbsents:
    """L'ancien préfixe `exo` ne doit plus apparaître dans les
    identifiants DOM, JavaScript et CSS. On vérifie avec des regex
    bornées pour éviter les faux positifs (commentaires, mots métiers).
    """

    def test_html_aucun_atl_exo(self, html):
        """Le HTML ne doit plus contenir aucun ID `atl-exo-*` —
        renommés en `atl-exercice-*`.
        """
        import re
        # Pattern : "atl-exo" suivi d'un tiret OU d'un caractère
        # non-alphanumérique (= fin d'identifiant).
        matches = re.findall(r'atl-exo[-"\s]', html)
        assert not matches, f"Reste {len(matches)} occurrence(s) de atl-exo-* dans index.html"

    def test_app_js_aucun_atl_exo_ni_ATL_EXO(self, app_js):
        """app.js ne doit plus contenir aucun pattern atl-exo, ATL_EXO_,
        atelExoXxx — tous renommés vers exercice.
        """
        import re
        # atl-exo suivi de tiret
        assert not re.search(r'atl-exo[-"\s]', app_js)
        # ATL_EXO_ (chaîne suivi d'un underscore)
        assert "ATL_EXO_" not in app_js
        # atelExo suivi d'une majuscule (= identifiant de fonction)
        assert not re.search(r'atelExo[A-Z]', app_js)

    def test_atelier_exercice_js_aucun_pattern_ancien(self, exercice_js):
        """atelier_exercice.js ne doit plus contenir aucun pattern
        ancien après renommage.
        """
        import re
        assert not re.search(r'atl-exo[-"\s]', exercice_js)
        assert "ATL_EXO_" not in exercice_js
        assert not re.search(r'atelExo[A-Z]', exercice_js)

    @pytest.mark.parametrize("nom_fichier", FICHIERS_RENOMMES)
    def test_fichier_aucun_pattern_ancien(self, nom_fichier):
        """Test paramétré : chacun des 8 fichiers concernés doit avoir
        zéro occurrence des 3 patterns anciens.
        """
        import re
        chemin = RACINE_APPLI / nom_fichier
        contenu = chemin.read_text(encoding="utf-8")
        anciens_atl = re.findall(r'atl-exo[-"\s]', contenu)
        anciens_atelExo = re.findall(r'atelExo[A-Z][a-zA-Z]*', contenu)
        anciens_atl_const = "ATL_EXO_" in contenu
        message = []
        if anciens_atl:
            message.append(f"{len(anciens_atl)} atl-exo-* (ex: {anciens_atl[0]})")
        if anciens_atelExo:
            message.append(f"{len(anciens_atelExo)} atelExoXxx (ex: {anciens_atelExo[0]})")
        if anciens_atl_const:
            message.append("ATL_EXO_ présent")
        assert not message, f"Patterns anciens dans {nom_fichier} : {', '.join(message)}"


# ── Nouveaux patterns présents et utilisés ──────────────────────────────

class TestNouveauxPatternsPresents:
    """Les nouveaux patterns (atl-exercice, ATELIER_EXERCICE, atelExercice)
    doivent être présents et utilisés à la place des anciens.
    """

    def test_html_a_atl_exercice(self, html):
        """index.html doit contenir des IDs `atl-exercice-*` (issus du
        renommage de `atl-exo-*`).
        """
        # On attend au moins 30 occurrences (sur 38 anciennes,
        # certaines peuvent être déjà en atl-exercice avant renommage).
        nb = html.count("atl-exercice-")
        assert nb >= 30, f"Attendu >=30 occurrences atl-exercice-*, trouvé {nb}"

    def test_classe_javascript_atelier_exercice_existe(self, exercice_js):
        """La classe AtelierExercice doit toujours exister (renommage
        ne change pas le nom de classe).
        """
        assert "class AtelierExercice" in exercice_js

    def test_prefixe_atelier_exercice_est_atl_exercice(self, exercice_js):
        """La config de la classe doit déclarer prefixe: 'atl-exercice'
        (et non plus 'atl-exo').
        """
        assert "prefixe:" in exercice_js
        # On cherche la chaîne 'atl-exercice' à proximité du mot
        # 'prefixe' (sans contrainte d'espacement trop stricte).
        import re
        m = re.search(r"prefixe\s*:\s*['\"]atl-exercice['\"]", exercice_js)
        assert m, "Le préfixe DOM de AtelierExercice doit être 'atl-exercice'"

    def test_id_form_renomme(self, html):
        """L'ID `atl-exo-form` est devenu `atl-exercice-form`."""
        assert 'id="atl-exercice-form"' in html
        assert 'id="atl-exo-form"' not in html

    def test_id_rendu_aligne(self, html):
        """L'ID de la zone Rendu PDF (cas mismatch v0.13.7.6) :
        avant `atl-exercice-rendu`, après aussi `atl-exercice-rendu`
        (la cohérence est atteinte avec le préfixe de classe).
        """
        assert 'id="atl-exercice-rendu"' in html


# ── Sécurité : on n'a pas cassé les types métier ────────────────────────

class TestTypesMetierIntacts:
    """Le type-string 'exercice' utilisé dans les URLs / les services /
    TABLES_ATOMES NE DOIT PAS avoir été renommé en quoi que ce soit
    d'autre. Idem pour 'exos' (pluriel métier).
    """

    def test_url_api_atomes_exercice_intacte(self, exercice_js):
        """L'URL /api/atomes/exercice/... doit rester telle quelle
        (le 'exercice' dans l'URL est un type-string métier).
        """
        # On vérifie que la chaîne 'exercice' apparaît bien comme
        # type-string quelque part dans le JS (autre que dans des IDs
        # DOM).
        assert "'exercice'" in exercice_js or '"exercice"' in exercice_js

    def test_pas_de_double_renommage(self, html):
        """Pas de séquence 'atl-exerciceexercice' ou similaire qui
        traduirait un double renommage erroné.
        """
        assert "atl-exerciceexercice" not in html
        assert "atelExerciceExercice" not in html
