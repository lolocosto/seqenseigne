"""Tests v0.14.3 — HTML statique + adaptation atelier_atomique + préférence
auto-compile.

Cette livraison :
1. Ajoute le bloc rendu PDF standardisé dans index.html pour les 4
   ateliers (exercice, notion, methode, fiche) sur le modèle de la carte.
2. Configure `endpointRenduPdf` pour ces 4 ateliers pointant vers
   `/api/atomes/<type>/` (et conserve `endpointBase` pour le CRUD).
3. Supprime les surcharges `basculerOnglet` qui appelaient
   `window.rendreAtomeTab(type)` — l'héritage via `AtelierAtomique`
   prend le relais.
4. Ajoute le paramètre `options.silencieuse` à `AtelierEditeur.sauvegarder`
   et retour booléen.
5. Branche une sauvegarde silencieuse en amont de `compilerRendu` quand
   l'item a des modifications en attente.
6. Ajoute la préférence localStorage `seqenseigne_pref_auto_compile`
   (cochée par défaut) qui déclenche `compilerRendu()` à l'ouverture du
   panneau Rendu PDF quand le cache n'est pas valide.
7. Marque `rendu_atome.js` comme obsolète (suppression définitive en
   v0.14.4).
"""
from __future__ import annotations
from pathlib import Path

import pytest


RACINE_APPLI = Path(__file__).resolve().parent.parent
CHEMIN_HTML = RACINE_APPLI / "templates" / "index.html"
CHEMIN_APP_JS = RACINE_APPLI / "static" / "app.js"
CHEMIN_ATEL_ATOMIQUE = RACINE_APPLI / "static" / "atelier_atomique.js"
CHEMIN_ATEL_EDITEUR = RACINE_APPLI / "static" / "atelier_editeur.js"

# Les 4 ateliers qui gagnent le HTML statique en v0.14.3.
ATELIERS_4 = ['exercice', 'notion', 'methode', 'fiche']
ATELIERS_5 = ATELIERS_4 + ['carte']


@pytest.fixture(scope="module")
def html():
    return CHEMIN_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def app_js():
    return CHEMIN_APP_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def atel_atomique():
    """v0.14.4 — Le contenu d'atelier_atomique.js a migré dans
    atelier_editeur.js (la classe AtelierAtomique a été supprimée et
    sa machinerie de rendu PDF intégrée dans la parente). Cette fixture
    retourne maintenant le contenu d'atelier_editeur.js pour que les
    tests v0.14.3 continuent de valider le comportement à l'endroit
    correct.
    """
    return CHEMIN_ATEL_EDITEUR.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def atel_editeur():
    return CHEMIN_ATEL_EDITEUR.read_text(encoding="utf-8")


# ── HTML standardisé pour les 5 ateliers ────────────────────────────────

class TestHtmlStandardise:
    """Les 5 ateliers doivent avoir les MÊMES sous-éléments DOM dans la
    zone Rendu PDF, avec des IDs suivant la convention atl-<type>-<role>.
    """

    @pytest.mark.parametrize("type_atelier", ATELIERS_5)
    @pytest.mark.parametrize("role", [
        'rendu',                # conteneur
        'pdf-iframe',           # iframe d'affichage du PDF
        # v0.17.0 — btn-compiler et rendu-status ne sont PLUS dans le HTML
        # statique : ils sont générés par AtelierEditeur._assurerToolbarRendu
        # dans le conteneur #atl-<type>-rendu-toolbar (cf. test dédié plus bas).
        'rendu-toolbar',        # conteneur de la mini-toolbar (généré dynamiquement)
        'rendu-erreur',         # zone d'affichage des erreurs
        'rendu-placeholder',    # placeholder « Cliquez sur Compiler »
    ])
    def test_id_present(self, html, type_atelier, role):
        """Pour chaque combinaison (type, rôle), l'ID HTML doit exister."""
        id_attendu = f'id="atl-{type_atelier}-{role}"'
        assert id_attendu in html, (
            f"ID HTML manquant : {id_attendu}. Les 5 ateliers doivent "
            f"avoir un bloc rendu PDF standardisé."
        )

    @pytest.mark.parametrize("type_atelier", ATELIERS_5)
    def test_conteneur_toolbar_rendu_vide(self, html, type_atelier):
        """v0.17.0 — Le conteneur #atl-<type>-rendu-toolbar est présent mais
        VIDE dans le HTML (rempli par _assurerToolbarRendu). On ne doit donc
        plus trouver de bouton compiler statique ni de onclick inline."""
        assert f'id="atl-{type_atelier}-rendu-toolbar"' in html
        # Plus de bouton compiler statique avec onclick inline.
        assert f'id="atl-{type_atelier}-btn-compiler"' not in html, (
            f"v0.17.0 : btn-compiler de {type_atelier} doit être généré en JS, "
            f"pas présent dans le HTML statique."
        )

    def test_base_genere_toolbar_rendu(self, atel_atomique):
        """v0.17.0 — La base AtelierEditeur génère la mini-toolbar (méthode
        _assurerToolbarRendu) avec les boutons Compiler et LaTeX généré, câblés
        en addEventListener (pas d'onclick inline)."""
        assert "_assurerToolbarRendu" in atel_atomique
        assert "'-btn-compiler'" in atel_atomique or "-btn-compiler" in atel_atomique
        assert "'-btn-latex'" in atel_atomique or "-btn-latex" in atel_atomique
        # Câblage par addEventListener (découplé du nom de l'instance globale).
        assert "addEventListener('click'" in atel_atomique


# ── Configuration endpointRenduPdf des 4 ateliers ───────────────────────

class TestConfigEndpointRenduPdf:
    """Les 4 ateliers doivent déclarer endpointRenduPdf pointant vers
    l'API unifiée /api/atomes/<type>/.
    """

    @pytest.mark.parametrize("type_atelier,endpoint_attendu", [
        ('exercice', '/api/atomes/exercice'),
        ('notion',   '/api/atomes/notion'),
        ('methode',  '/api/atomes/methode'),
        ('fiche',    '/api/atomes/fiche'),
    ])
    def test_endpoint_rendu_pdf_dans_atelier(self, type_atelier, endpoint_attendu):
        chemin = RACINE_APPLI / "static" / f"atelier_{type_atelier}.js"
        contenu = chemin.read_text(encoding="utf-8")
        import re
        m = re.search(
            r"endpointRenduPdf\s*:\s*['\"]" + re.escape(endpoint_attendu) + r"['\"]",
            contenu,
        )
        assert m, (
            f"atelier_{type_atelier}.js doit déclarer "
            f"endpointRenduPdf: '{endpoint_attendu}' dans sa config."
        )


# ── Surcharges basculerOnglet supprimées ────────────────────────────────

class TestSurchargesBasculerOngletSupprimees:
    """Les 4 ateliers ne doivent plus surcharger basculerOnglet pour
    appeler rendreAtomeTab : l'héritage AtelierAtomique prend le relais.
    """

    @pytest.mark.parametrize("type_atelier", ATELIERS_4)
    def test_aucun_appel_rendreAtomeTab(self, type_atelier):
        """Le fichier atelier_<type>.js ne doit plus contenir d'appel
        à rendreAtomeTab (ni window.rendreAtomeTab).
        """
        chemin = RACINE_APPLI / "static" / f"atelier_{type_atelier}.js"
        contenu = chemin.read_text(encoding="utf-8")
        # On exclut les commentaires : la regex cherche soit en début de
        # ligne (hors commentaire), soit après ; soit après {
        import re
        # Pattern : 'rendreAtomeTab(' précédé d'un caractère non-commentaire
        # On filtre les lignes qui démarrent par '//' ou contiennent ' * '
        lignes_actives = [
            l for l in contenu.splitlines()
            if 'rendreAtomeTab' in l
            and not l.lstrip().startswith('//')
            and not l.lstrip().startswith('*')
        ]
        assert not lignes_actives, (
            f"atelier_{type_atelier}.js contient encore des appels à "
            f"rendreAtomeTab :\n" + "\n".join(lignes_actives)
        )


# ── Sauvegarde silencieuse ──────────────────────────────────────────────

class TestSauvegardeSilencieuse:
    """AtelierEditeur.sauvegarder doit accepter un paramètre options
    avec une clé silencieuse, et retourner un booléen.
    """

    def test_methode_accepte_options(self, atel_editeur):
        """La signature `sauvegarder(options = {})` doit être présente
        (au lieu de `sauvegarder()`).
        """
        import re
        # Pattern : la méthode prend un paramètre options avec valeur
        # par défaut, ou au moins un argument.
        m = re.search(
            r"async\s+sauvegarder\s*\(\s*options\s*=\s*\{\s*\}\s*\)",
            atel_editeur,
        )
        assert m, (
            "AtelierEditeur.sauvegarder doit accepter un paramètre "
            "options avec valeur par défaut (au moins sa signature)."
        )

    def test_methode_lit_silencieuse(self, atel_editeur):
        """La méthode doit consulter options.silencieuse pour adapter
        son comportement (pas de toast, pas de chargerListe).
        """
        # Chercher l'utilisation explicite de la clé silencieuse.
        assert "silencieuse" in atel_editeur

    def test_methode_retourne_bool(self, atel_editeur):
        """La méthode doit avoir au moins un `return true` et un
        `return false` (le contrat booléen).
        """
        assert "return true;" in atel_editeur
        assert "return false;" in atel_editeur


# ── compilerRendu : sauvegarde silencieuse en amont ─────────────────────

class TestCompilerRenduSauvegardeAmont:
    """compilerRendu doit appeler sauvegarder({silencieuse: true})
    quand l'atome a des modifications en attente (this.modifie === true)
    et qu'on n'est pas en mode auto-cache.
    """

    def test_appel_a_sauvegarder_silencieuse(self, atel_atomique):
        """Le fichier doit contenir l'appel `this.sauvegarder(
        { silencieuse: true })` (ou équivalent).
        """
        # On cherche la substring caractéristique. Tolérance sur les
        # espaces et le placement de la clé.
        import re
        m = re.search(
            r"this\.sauvegarder\s*\(\s*\{\s*silencieuse\s*:\s*true\s*\}\s*\)",
            atel_atomique,
        )
        assert m, (
            "AtelierAtomique.compilerRendu doit appeler "
            "this.sauvegarder({ silencieuse: true }) en amont."
        )

    def test_condition_sur_modifie(self, atel_atomique):
        """L'appel doit être gardé par une condition sur this.modifie
        (pas de save inutile si rien à enregistrer).
        """
        assert "this.modifie" in atel_atomique

    def test_condition_sur_chargement_auto(self, atel_atomique):
        """L'appel doit aussi être conditionné par !this._chargementAuto
        (en auto-cache on lit juste, pas la peine de sauver).
        """
        assert "this._chargementAuto" in atel_atomique


# ── Préférence auto-compile ─────────────────────────────────────────────

class TestPreferenceAutoCompile:
    """La préférence d'auto-compile doit être implémentée côté UI et
    consommée par AtelierAtomique.verifierCacheEtAfficher.
    """

    def test_cle_localstorage_definie(self, app_js):
        """app.js définit la constante PREF_AUTO_COMPILE_KEY."""
        assert "PREF_AUTO_COMPILE_KEY" in app_js
        assert "seqenseigne_pref_auto_compile" in app_js

    def test_fonction_prefAutoCompileEstActive(self, app_js):
        """Fonction de lecture exposée pour AtelierAtomique."""
        assert "function prefAutoCompileEstActive" in app_js
        assert "window.prefAutoCompileEstActive" in app_js

    def test_default_true_quand_cle_absente(self, app_js):
        """Quand la clé localStorage n'existe pas (utilisateur n'a
        jamais touché), la fonction doit renvoyer true (= cochée par
        défaut). On vérifie le pattern `!== '0'` qui couvre les cas
        null (absent) et '1' (explicitement coché).
        """
        # La fonction doit retourner true sauf si la valeur stockée
        # est exactement '0'.
        import re
        m = re.search(
            r"prefAutoCompileEstActive[\s\S]{0,300}?!==\s*['\"]0['\"]",
            app_js,
        )
        assert m, (
            "prefAutoCompileEstActive doit retourner true sauf si "
            "la valeur localStorage est exactement '0'."
        )

    def test_toggle_definie(self, app_js):
        """La fonction de bascule existe."""
        assert "function prefAutoCompileToggle" in app_js

    def test_html_toggle_existe(self, html):
        """Le toggle HTML doit exister dans la section Préférences."""
        assert 'id="pref-auto-compile"' in html
        assert 'onchange="prefAutoCompileToggle()"' in html

    def test_atelier_consulte_la_pref(self, atel_atomique):
        """AtelierAtomique.verifierCacheEtAfficher doit appeler
        window.prefAutoCompileEstActive() pour décider entre auto-compile
        et placeholder quand cache_valide=false.
        """
        assert "window.prefAutoCompileEstActive" in atel_atomique


# ── rendu_atome.js marqué obsolète ──────────────────────────────────────

class TestRenduAtomeObsolete:
    """Le fichier rendu_atome.js doit être marqué comme obsolète dans
    son en-tête (suppression définitive en v0.14.4).
    """

    def test_marque_obsolete_dans_entete(self):
        chemin = RACINE_APPLI / "static" / "rendu_atome.js"
        contenu = chemin.read_text(encoding="utf-8")
        # Test souple : « OBSOLÈTE » ou « obsolete » ou autre marqueur clair
        # dans les 1500 premiers caractères.
        entete = contenu[:1500].upper()
        assert (
            "OBSOLÈTE" in entete
            or "OBSOLETE" in entete
        ), (
            "rendu_atome.js doit être marqué comme obsolète dans son "
            "en-tête (v0.14.3) — suppression définitive en v0.14.4."
        )
