"""Tests v0.14.4 — Étape finale du chantier d'unification rendu PDF.

Cette livraison :
1. Supprime la classe intermédiaire AtelierAtomique et descend toute sa
   machinerie de rendu PDF dans AtelierEditeur (méthodes héritées par
   les 5 ateliers).
2. Supprime le fichier rendu_atome.js (devenu inutile depuis v0.14.3).
3. Migre la carte sur l'URL unifiée /api/atomes/carte/<id>/... et
   supprime les anciennes routes /api/cartes/<id>/rendu-* du backend.
4. Ajoute le spinner visuel (cercle qui tourne + texte) pendant la
   compilation pour les 5 ateliers, sur le modèle de l'ancien
   rendu_atome.js (que les 4 ateliers hors carte avaient déjà).

Les tests valident l'aboutissement de chaque point.
"""
from __future__ import annotations
from pathlib import Path

import pytest


RACINE_APPLI = Path(__file__).resolve().parent.parent
CHEMIN_HTML = RACINE_APPLI / "templates" / "index.html"
CHEMIN_ATEL_EDITEUR = RACINE_APPLI / "static" / "atelier_editeur.js"
CHEMIN_ATEL_ATOMIQUE = RACINE_APPLI / "static" / "atelier_atomique.js"
CHEMIN_RENDU_ATOME = RACINE_APPLI / "static" / "rendu_atome.js"
CHEMIN_CSS = RACINE_APPLI / "static" / "app.css"
CHEMIN_CARTES_PY = RACINE_APPLI / "routes" / "cartes_automatisme.py"
CHEMIN_RENDU_PY = RACINE_APPLI / "routes" / "rendu_atome.py"

ATELIERS_5 = ['exercice', 'notion', 'methode', 'fiche', 'carte']


@pytest.fixture(scope="module")
def html():
    return CHEMIN_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def atel_editeur():
    return CHEMIN_ATEL_EDITEUR.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def atel_atomique():
    return CHEMIN_ATEL_ATOMIQUE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rendu_atome():
    return CHEMIN_RENDU_ATOME.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css():
    return CHEMIN_CSS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cartes_py():
    return CHEMIN_CARTES_PY.read_text(encoding="utf-8")


# ── 1. Suppression de la classe AtelierAtomique ──────────────────────────

class TestSuppressionAtelierAtomique:
    """La classe AtelierAtomique a été supprimée et sa machinerie
    intégrée dans AtelierEditeur.
    """

    def test_atelier_atomique_est_un_stub(self, atel_atomique):
        """Le fichier atelier_atomique.js doit être réduit à un stub
        (commentaire de suppression + rien d'autre). Pas de classe,
        pas de méthodes.
        """
        assert "class AtelierAtomique" not in atel_atomique, (
            "Le fichier atelier_atomique.js ne doit plus définir la classe "
            "AtelierAtomique en v0.14.4."
        )
        assert "SUPPRIMÉ" in atel_atomique.upper(), (
            "Le fichier doit contenir un marqueur 'SUPPRIMÉ' dans son "
            "en-tête pour signaler qu'il s'agit d'un stub."
        )
        # Pas plus de quelques dizaines de lignes (juste le commentaire).
        nb_lignes = len(atel_atomique.splitlines())
        assert nb_lignes < 50, (
            f"Le stub atelier_atomique.js fait {nb_lignes} lignes, on "
            f"attendait <50 (juste un commentaire de suppression)."
        )

    def test_atelier_atomique_pas_charge_dans_html(self, html):
        """Le <script src="atelier_atomique.js"> doit être retiré du HTML."""
        # On accepte qu'il soit mentionné dans un commentaire (historique)
        # mais pas dans une balise <script src=> active.
        import re
        m = re.search(r'<script\s+src=["\'][^"\']*atelier_atomique\.js[^"\']*["\']',
                      html)
        assert m is None, (
            "Le fichier atelier_atomique.js ne doit plus être chargé via "
            "<script> dans index.html."
        )


# ── 2. Suppression du fichier rendu_atome.js ─────────────────────────────

class TestSuppressionRenduAtome:
    """Le fichier rendu_atome.js a été supprimé (réduit à un stub
    explicatif pour écraser les versions précédentes).
    """

    def test_rendu_atome_est_un_stub(self, rendu_atome):
        """Le fichier doit être un stub sans aucune fonction active."""
        # Pas de fonctions globales historiques
        assert "function rendreAtomeTab" not in rendu_atome
        assert "function rendreAtomeLancer" not in rendu_atome
        assert "function rendreAtomeToggleTex" not in rendu_atome
        # Marqueur de suppression dans l'en-tête
        assert "SUPPRIMÉ" in rendu_atome.upper()
        # Pas plus de quelques dizaines de lignes
        nb_lignes = len(rendu_atome.splitlines())
        assert nb_lignes < 50, (
            f"Le stub rendu_atome.js fait {nb_lignes} lignes, on "
            f"attendait <50."
        )

    def test_rendu_atome_pas_charge_dans_html(self, html):
        """Le <script src="rendu_atome.js"> doit être retiré du HTML."""
        import re
        m = re.search(r'<script\s+src=["\'][^"\']*rendu_atome\.js[^"\']*["\']',
                      html)
        assert m is None, (
            "Le fichier rendu_atome.js ne doit plus être chargé via "
            "<script> dans index.html."
        )


# ── 3. Méthodes rendu PDF dans AtelierEditeur ────────────────────────────

class TestMethodesDansEditeur:
    """Les méthodes de rendu PDF (qui vivaient dans AtelierAtomique
    avant v0.14.4) sont maintenant dans AtelierEditeur.
    """

    @pytest.mark.parametrize("methode", [
        "verifierCacheEtAfficher",
        "_remettrePlaceholderRendu",
        "compilerRendu",
        "_afficherErreurCompilation",
        "toggleTexBrut",
        "_afficherTexBrut",
        "scrollVersLigneTex",
        "voirLatex",
    ])
    def test_methode_presente(self, atel_editeur, methode):
        """Chacune des méthodes du rendu PDF doit être définie dans
        atelier_editeur.js.
        """
        # On cherche la définition : soit "methode(" ou "async methode("
        # avec une indentation de 2 espaces (méthode de classe).
        import re
        pattern = rf"^\s{{2}}(async\s+)?{re.escape(methode)}\s*\("
        m = re.search(pattern, atel_editeur, re.MULTILINE)
        assert m, f"Méthode {methode} introuvable dans atelier_editeur.js"

    def test_basculer_onglet_branche_verifier_cache(self, atel_editeur):
        """La méthode basculerOnglet doit appeler verifierCacheEtAfficher
        quand on passe sur l'onglet 'rendu' avec un item actif. C'est
        l'intégration de l'ancien override d'AtelierAtomique.basculerOnglet
        dans la méthode parent.
        """
        # On cherche basculerOnglet et on vérifie que verifierCacheEtAfficher
        # est appelée à proximité.
        idx = atel_editeur.index("basculerOnglet(tab)")
        zone = atel_editeur[idx: idx + 1800]
        assert "verifierCacheEtAfficher" in zone, (
            "AtelierEditeur.basculerOnglet doit appeler "
            "verifierCacheEtAfficher pour l'onglet 'rendu'."
        )

    def test_constructeur_initialise_gen_rendu(self, atel_editeur):
        """Le constructeur d'AtelierEditeur doit initialiser
        this._genRendu (compteur pour la race condition).
        """
        assert "this._genRendu = 0" in atel_editeur

    def test_constructeur_initialise_endpoint_rendu_pdf(self, atel_editeur):
        """Le constructeur doit fixer endpointRenduPdf par défaut à
        endpointBase si non précisé.
        """
        assert "endpointRenduPdf" in atel_editeur
        # On cherche la garde de fallback
        assert "if (!this.config.endpointRenduPdf)" in atel_editeur


# ── 4. Héritage direct AtelierEditeur ────────────────────────────────────

class TestHeritageDirect:
    """Les 5 ateliers étendent maintenant directement AtelierEditeur
    (sans passer par AtelierAtomique).
    """

    FICHIERS = {
        'exercice': 'atelier_exercice.js',
        'notion':   'atelier_notion.js',
        'methode':  'atelier_methode.js',
        'fiche':    'atelier_fiche.js',
        'carte':    'atelier_carte_automatisme.js',
    }

    @pytest.mark.parametrize("type_atelier", ATELIERS_5)
    def test_etend_atelier_editeur(self, type_atelier):
        """L'atelier doit étendre AtelierEditeur (et plus AtelierAtomique)."""
        nom_fichier = self.FICHIERS[type_atelier]
        chemin = RACINE_APPLI / "static" / nom_fichier
        contenu = chemin.read_text(encoding="utf-8")
        import re
        # Recherche d'une déclaration de classe qui étend AtelierEditeur.
        m = re.search(r"class\s+Atelier\w+\s+extends\s+AtelierEditeur", contenu)
        assert m, (
            f"Atelier {type_atelier} ({nom_fichier}) doit étendre "
            f"AtelierEditeur directement."
        )
        # Surtout pas extends AtelierAtomique.
        assert "extends AtelierAtomique" not in contenu, (
            f"{nom_fichier} ne doit plus étendre AtelierAtomique en v0.14.4."
        )


# ── 5. Carte migrée sur API unifiée ──────────────────────────────────────

class TestCarteMigree:
    """La carte utilise désormais l'API unifiée /api/atomes/carte/...
    Côté client : endpointRenduPdf déclaré explicitement.
    Côté serveur : les anciennes routes /api/cartes/<id>/rendu-* sont
    supprimées.
    """

    def test_carte_declare_endpoint_rendu_pdf_unifie(self):
        """Le client AtelierCarte doit déclarer
        endpointRenduPdf: '/api/atomes/carte'.
        """
        chemin = RACINE_APPLI / "static" / "atelier_carte_automatisme.js"
        contenu = chemin.read_text(encoding="utf-8")
        import re
        m = re.search(
            r"endpointRenduPdf\s*:\s*['\"]/api/atomes/carte['\"]",
            contenu,
        )
        assert m, (
            "AtelierCarte doit déclarer endpointRenduPdf='/api/atomes/carte' "
            "pour utiliser l'API unifiée."
        )

    def test_route_carte_rendu_pdf_supprimee(self, cartes_py):
        """La route /api/cartes/<id>/rendu-pdf doit être supprimée de
        cartes_automatisme.py.
        """
        assert '/api/cartes/<carte_id>/rendu-pdf' not in cartes_py, (
            "L'ancienne route /api/cartes/<id>/rendu-pdf doit être "
            "supprimée en v0.14.4."
        )

    def test_route_carte_rendu_pdf_info_supprimee(self, cartes_py):
        """La route /api/cartes/<id>/rendu-pdf/info doit être supprimée."""
        assert '/api/cartes/<carte_id>/rendu-pdf/info' not in cartes_py

    def test_route_carte_rendu_tex_supprimee(self, cartes_py):
        """La route /api/cartes/<id>/rendu-tex doit être supprimée."""
        assert '/api/cartes/<carte_id>/rendu-tex' not in cartes_py

    def test_routes_crud_carte_preservees(self, cartes_py):
        """Les routes CRUD de carte (GET, POST, PATCH, DELETE) doivent
        rester en place — seules les routes rendu sont supprimées.
        """
        assert '/api/cartes/<carte_id>' in cartes_py, (
            "Au moins une route /api/cartes/<id> doit subsister pour le "
            "CRUD (GET/PATCH/DELETE)."
        )

    def test_anciennes_routes_repondent_404(self, client):
        """Vérification HTTP : les anciennes routes répondent maintenant
        404 (Flask renvoie 404 NOT FOUND quand aucune route ne matche).
        """
        r1 = client.post('/api/cartes/crt_inexistant/rendu-pdf')
        assert r1.status_code == 404, (
            "L'ancienne route POST /api/cartes/<id>/rendu-pdf doit avoir "
            "été supprimée (404 attendu)."
        )
        r2 = client.get('/api/cartes/crt_inexistant/rendu-pdf/info')
        assert r2.status_code == 404
        r3 = client.get('/api/cartes/crt_inexistant/rendu-tex')
        assert r3.status_code == 404


# ── 6. Spinner visuel ────────────────────────────────────────────────────

class TestSpinnerVisuel:
    """Pendant la compilation, un cercle qui tourne + texte
    « Compilation en cours… » s'affiche au centre de la zone iframe
    pour les 5 ateliers.
    """

    @pytest.mark.parametrize("type_atelier", ATELIERS_5)
    def test_zone_loading_dans_html(self, html, type_atelier):
        """Chaque atelier doit avoir une zone #atl-<type>-rendu-loading
        dans son HTML statique.
        """
        id_attendu = f'id="atl-{type_atelier}-rendu-loading"'
        assert id_attendu in html, (
            f"Zone loading manquante pour {type_atelier} : {id_attendu}"
        )

    @pytest.mark.parametrize("type_atelier", ATELIERS_5)
    def test_zone_loading_a_la_classe_css(self, html, type_atelier):
        """La zone doit porter la classe CSS rendu-loading qui contient
        le styling du spinner (déjà défini dans app.css).
        """
        import re
        # On cherche le bloc <div id="atl-<type>-rendu-loading" ...
        # et on vérifie qu'il contient class="rendu-loading"
        m = re.search(
            rf'<div\s+id="atl-{type_atelier}-rendu-loading"[^>]*class="[^"]*rendu-loading[^"]*"',
            html,
        )
        # Tolérance d'ordre attribut (class peut être avant id)
        if not m:
            m = re.search(
                rf'<div\s+[^>]*class="[^"]*rendu-loading[^"]*"[^>]*id="atl-{type_atelier}-rendu-loading"',
                html,
            )
        assert m, (
            f"Zone #atl-{type_atelier}-rendu-loading doit porter la classe "
            f"rendu-loading pour bénéficier du style spinner."
        )

    def test_zone_loading_contient_spinner(self, html):
        """Chaque zone loading doit contenir un .rendu-spinner enfant
        (le cercle qui tourne). On vérifie globalement.
        """
        # On compte les occurrences de "rendu-spinner" — au moins 5
        # (une par zone loading).
        nb = html.count('rendu-spinner')
        assert nb >= 5, (
            f"Attendu au moins 5 occurrences de 'rendu-spinner' (1 par "
            f"atelier), trouvé : {nb}"
        )

    def test_compiler_rendu_affiche_spinner(self, atel_editeur):
        """La méthode compilerRendu doit rendre la zone rendu-loading
        visible avant le fetch (style.display = 'flex' ou similaire).
        """
        # On cherche dans compilerRendu (méthode async) une référence à
        # rendu-loading qui passe en display:flex/block au début.
        idx = atel_editeur.index("async compilerRendu()")
        # On prend la portion du corps de la méthode (jusqu'à la fonction
        # suivante).
        fin = atel_editeur.find("\n  /**", idx + 1)
        if fin < 0:
            fin = atel_editeur.find("\n  async ", idx + 1)
        if fin < 0:
            fin = idx + 8000
        corps = atel_editeur[idx:fin]
        assert "rendu-loading" in corps or "'rendu-loading'" in corps, (
            "compilerRendu doit référencer la zone rendu-loading "
            "(pour afficher le spinner)."
        )
        # Doit aussi la masquer (display='none') quand le PDF est prêt
        # ou en erreur. On cherche au moins une assignation à 'none'.
        assert "loadingEl" in corps, (
            "compilerRendu doit manipuler la variable loadingEl pour "
            "afficher/masquer le spinner."
        )

    def test_compiler_rendu_masque_spinner_au_succes(self, atel_editeur):
        """Quand le PDF est prêt, le spinner doit être masqué."""
        idx = atel_editeur.index("async compilerRendu()")
        fin = idx + 8000
        corps = atel_editeur[idx:fin]
        # On cherche "loadingEl.style.display = 'none'" quelque part
        assert "loadingEl.style.display = 'none'" in corps, (
            "Le spinner doit être masqué (display='none') au succès / "
            "à l'échec / en erreur dans compilerRendu."
        )

    def test_remettre_placeholder_masque_spinner(self, atel_editeur):
        """La méthode _remettrePlaceholderRendu doit également masquer
        le spinner (filet de sécurité contre les états résiduels).
        """
        # On cherche la définition (méthode de classe, indentation 2
        # espaces) et non un appel (this._remettrePlaceholderRendu();)
        import re
        m = re.search(
            r"^\s{2}_remettrePlaceholderRendu\s*\(\s*\)\s*\{",
            atel_editeur, re.MULTILINE,
        )
        assert m, "Définition de _remettrePlaceholderRendu introuvable"
        idx = m.start()
        fin = idx + 2000
        corps = atel_editeur[idx:fin]
        assert "loadingEl" in corps or "rendu-loading" in corps, (
            "_remettrePlaceholderRendu doit aussi masquer la zone "
            "rendu-loading pour éviter qu'un spinner reste visible "
            "quand on remet l'UI en état initial."
        )

    def test_css_rendu_loading_existe(self, css):
        """Le CSS .rendu-loading et .rendu-spinner doit être défini
        (héritage v0.10.x — on vérifie juste qu'il n'a pas été retiré
        par erreur).
        """
        assert ".rendu-loading" in css
        assert ".rendu-spinner" in css
        assert "rendu-spin" in css, (
            "L'animation @keyframes rendu-spin doit être définie dans app.css."
        )


# ── 7. Imports nettoyés dans cartes_automatisme.py ───────────────────────

class TestImportsNettoyes:
    """Suite à la suppression des routes rendu de cartes_automatisme.py,
    plusieurs imports sont devenus orphelins. v0.14.4 les retire pour
    propreté.
    """

    def test_response_pas_importe(self, cartes_py):
        """Response (de flask) n'est plus utilisé après la suppression
        des routes rendu."""
        import re
        # On accepte Response dans des commentaires mais pas dans l'import.
        m = re.search(r"^from flask import .*Response", cartes_py, re.MULTILINE)
        assert m is None, (
            "Response n'est plus utilisé dans cartes_automatisme.py après "
            "v0.14.4 — à retirer de l'import."
        )

    def test_pathlib_pas_importe(self, cartes_py):
        """Path (de pathlib) n'est plus utilisé."""
        import re
        m = re.search(r"^from pathlib import", cartes_py, re.MULTILINE)
        assert m is None, (
            "pathlib.Path n'est plus utilisé dans cartes_automatisme.py "
            "après v0.14.4."
        )

    def test_sqlite3_pas_importe(self, cartes_py):
        """sqlite3 n'est plus utilisé directement (les helpers passaient
        par store._conn())."""
        import re
        m = re.search(r"^import sqlite3", cartes_py, re.MULTILINE)
        assert m is None, (
            "sqlite3 n'est plus importé directement dans "
            "cartes_automatisme.py après v0.14.4."
        )
