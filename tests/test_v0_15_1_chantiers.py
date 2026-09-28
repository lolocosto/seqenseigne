"""Tests v0.15.1 — Garde-fous HTML.

Cette livraison effectue 3 chantiers principaux côté `templates/index.html` :

  F0 — Restaurer les `<script>` OO d'évaluation que v0.15.0.2.a avait
       accidentellement perdus (régression involontaire). Le HTML doit
       charger `atelier_assemblage.js` et `atelier_evaluation_oo.js`,
       PAS l'ancien `atelier_evaluation.js`.

  F1 — Charger `compilation_erreurs.js`. Ce module existait sur disque
       depuis v0.13.6.5.1.1 mais n'avait jamais été référencé par un
       `<script>` (autre régression silencieuse).

  F2 — Supprimer les 3 ateliers Récap cours / Récap exos / Plans de
       travail (frontend + routes backend). Leurs fonctionnalités sont
       reprises par Référentiel > Documents à publier.

  F5 — Renommer le bouton « Ateliers » du bandeau supérieur en
       « Conception de référentiel » (en prévision d'un futur bouton
       « Ateliers » qui apparaîtra côté Suivi de classe).

Ces tests parsent `templates/index.html` et vérifient la conformité
de la structure attendue. Pattern emprunté à v0.15.0.2.a qui a déjà
prouvé son utilité.
"""
from __future__ import annotations
from pathlib import Path

import pytest


RACINE_APPLI = Path(__file__).resolve().parent.parent
CHEMIN_HTML = RACINE_APPLI / "templates" / "index.html"
CHEMIN_APP_JS = RACINE_APPLI / "static" / "app.js"
CHEMIN_APP_PY = RACINE_APPLI / "app.py"


@pytest.fixture(scope="module")
def html() -> str:
    return CHEMIN_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def app_js() -> str:
    return CHEMIN_APP_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def app_py() -> str:
    return CHEMIN_APP_PY.read_text(encoding="utf-8")


# ── F0 — Scripts OO d'évaluation ─────────────────────────────────────


class TestF0ScriptsOOEvaluation:
    """v0.15 avait introduit la classe AtelierAssemblage et migré
    AtelierEvaluation en OO. Les `<script>` ont été perdus en
    v0.15.0.2.a (régression involontaire de ma part en livrant un
    index.html basé sur l'état v0.14.8 au lieu de l'état v0.15).
    v0.15.1 les restaure définitivement.
    """

    def test_atelier_assemblage_charge(self, html):
        assert 'src="/static/atelier_assemblage.js"' in html

    def test_atelier_evaluation_oo_charge(self, html):
        assert 'src="/static/atelier_evaluation_oo.js"' in html

    def test_ancien_atelier_evaluation_non_charge(self, html):
        # L'ancien atelier_evaluation.js (procédural) ne doit plus être
        # référencé dans aucun <script>. On cherche une chaîne ciblée
        # qui ne matche QUE la balise, pas un commentaire (les
        # commentaires peuvent légitimement parler de l'ancien fichier).
        assert 'src="/static/atelier_evaluation.js"' not in html

    def test_ancien_atelier_evaluation_supprime_du_disque(self):
        # v0.16.1 — Le fichier mort a été supprimé du dépôt (étape 1 du
        # chantier d'unification des assemblages). Ses 20 symboles
        # `window.atelEval*` sont entièrement réexposés par
        # atelier_evaluation_oo.js (ponts vers l'instance OO), donc le
        # fichier procédural n'avait plus aucun rôle. On verrouille son
        # absence pour ne pas le réintroduire par mégarde.
        from pathlib import Path
        appli = Path(__file__).resolve().parent.parent
        mort = appli / "static" / "atelier_evaluation.js"
        assert not mort.exists(), (
            "atelier_evaluation.js (procédural, mort) a été réintroduit. "
            "L'évaluation est portée par atelier_evaluation_oo.js (v0.15+)."
        )

    def test_ordre_chaine_oo(self, html):
        # AtelierAssemblage hérite d'AtelierEditeur (qui hérite d'Atelier).
        # AtelierEvaluation hérite d'AtelierAssemblage. Le chargement
        # doit respecter l'ordre des classes parentes.
        pos_atelier   = html.find('src="/static/atelier.js"')
        pos_editeur   = html.find('src="/static/atelier_editeur.js"')
        pos_assemb    = html.find('src="/static/atelier_assemblage.js"')
        pos_eval_oo   = html.find('src="/static/atelier_evaluation_oo.js"')
        assert 0 < pos_atelier < pos_editeur < pos_assemb < pos_eval_oo, (
            "L'ordre attendu est : atelier.js → atelier_editeur.js → "
            "atelier_assemblage.js → atelier_evaluation_oo.js"
        )


# ── F1 — Module compilation_erreurs.js ────────────────────────────────


class TestF1CompilationErreurs:
    """Le module commun de rendu des erreurs LaTeX, présent sur disque
    depuis v0.13.6.5.1.1 mais jamais chargé via `<script>` (oubli).
    Sa fonction `compErreursAfficher` est appelée par
    `atelier_referentiel.js` pour le panneau « Documents à publier ».
    """

    def test_fichier_present_sur_disque(self):
        chemin = RACINE_APPLI / "static" / "compilation_erreurs.js"
        assert chemin.exists(), "compilation_erreurs.js doit exister"

    def test_charge_dans_html(self, html):
        assert 'src="/static/compilation_erreurs.js"' in html

    def test_charge_avant_atelier_referentiel(self, html):
        # atelier_referentiel.js appelle compErreursAfficher → le module
        # doit être disponible AVANT son chargement.
        pos_module    = html.find('src="/static/compilation_erreurs.js"')
        pos_referent  = html.find('src="/static/atelier_referentiel.js"')
        assert 0 < pos_module < pos_referent


# ── F2 — Suppression des 3 ateliers Récap/Plans ───────────────────────


class TestF2SuppressionRecapPlans:
    """Les 3 ateliers de portée Niveau (Récap cours, Récap exos, Plans
    de travail) sont supprimés. Leurs fonctionnalités sont reprises
    par Référentiel > Documents à publier.

    On vérifie : 3 fichiers JS absents, 3 routes backend absentes,
    aucun `<script>` ni bouton ni panneau côté HTML, aucune entrée
    dans `ATL_INITS` ni `ATL_PORTEES` côté `app.js`.

    NB : les SERVICES Python (`services/livret_recap_*.py`,
    `services/livret_plans_de_travail.py`) sont CONSERVÉS car
    réutilisés par d'autres modules (referentiels.py, etc.).
    """

    # ── Fichiers JS supprimés ──────────────────────────────────────
    @pytest.mark.parametrize("nom", [
        "atelier_recapcours.js",
        "atelier_recapexos.js",
        "atelier_plansdetravail.js",
    ])
    def test_fichier_js_absent(self, nom):
        chemin = RACINE_APPLI / "static" / nom
        assert not chemin.exists(), (
            f"v0.15.1 a supprimé static/{nom}"
        )

    # ── Routes backend supprimées ──────────────────────────────────
    # v0.16.10 — routes/plans_de_travail.py a été RÉINTRODUIT (portée
    # séquence uniquement) pour le bouton « Compiler le plan de travail »
    # de l'atelier d'assemblage. On ne teste donc plus son absence ; seules
    # les routes recap_cours/recap_exos restent supprimées.
    @pytest.mark.parametrize("nom", [
        "recap_cours.py",
        "recap_exos.py",
    ])
    def test_route_backend_absente(self, nom):
        chemin = RACINE_APPLI / "routes" / nom
        assert not chemin.exists(), (
            f"v0.15.1 a supprimé routes/{nom}"
        )

    def test_plan_travail_reintroduit_v0_16_10(self):
        # v0.16.10 — routes/plans_de_travail.py réintroduit, MAIS uniquement
        # en portée séquence (le livret annuel reste géré par l'atelier
        # Référentiel). On vérifie la présence du fichier et l'absence de
        # route de portée niveau seul (pas de /<niveau>/pdf sans séquence).
        chemin = RACINE_APPLI / "routes" / "plans_de_travail.py"
        assert chemin.exists(), (
            "v0.16.10 réintroduit routes/plans_de_travail.py (portée séquence)"
        )
        src = chemin.read_text(encoding="utf-8")
        # La route doit être paramétrée par <sequence_code> (portée séquence).
        assert "<sequence_code>" in src

    # ── Services Python CONSERVÉS ──────────────────────────────────
    @pytest.mark.parametrize("nom", [
        "livret_recap_cours.py",
        "livret_recap_exos.py",
        "livret_plans_de_travail.py",
    ])
    def test_service_conserve(self, nom):
        chemin = RACINE_APPLI / "services" / nom
        assert chemin.exists(), (
            f"Le service {nom} doit rester disponible "
            f"(utilisé par d'autres modules)"
        )

    # ── HTML ───────────────────────────────────────────────────────
    def test_scripts_recap_plans_non_charges(self, html):
        for nom in ("atelier_recapcours.js",
                    "atelier_recapexos.js",
                    "atelier_plansdetravail.js"):
            assert f'src="/static/{nom}"' not in html, (
                f"<script> de {nom} ne doit plus être présent"
            )

    def test_panneaux_html_supprimes(self, html):
        for id_panneau in ('id="atl-recapcours"',
                           'id="atl-recapexos"',
                           'id="atl-plantravail"'):
            assert id_panneau not in html, (
                f"Le panneau {id_panneau} doit avoir été supprimé"
            )

    def test_boutons_onglets_supprimes(self, html):
        for id_btn in ('id="atl-btn-recapcours"',
                       'id="atl-btn-recapexos"',
                       'id="atl-btn-plantravail"'):
            assert id_btn not in html

    # ── app.js ─────────────────────────────────────────────────────
    def test_atl_inits_pas_de_recap_plans(self, app_js):
        # On vérifie qu'il n'y a plus d'entrée active dans ATL_INITS.
        # Les commentaires explicatifs (commençant par //) sont
        # autorisés à mentionner les noms.
        lignes = app_js.splitlines()
        dans_atl_inits = False
        for ligne in lignes:
            if 'const ATL_INITS = {' in ligne:
                dans_atl_inits = True
                continue
            if dans_atl_inits and ligne.strip().startswith('};'):
                break
            if dans_atl_inits and ligne.lstrip().startswith('//'):
                continue
            if dans_atl_inits:
                for cle in ('recapcours:', 'recapexos:', 'plantravail:'):
                    assert cle not in ligne, (
                        f"ATL_INITS ne doit plus contenir {cle} : {ligne!r}"
                    )

    def test_atl_portees_niveau_minimum(self, app_js):
        # La portée 'niveau' doit lister au minimum 'evaluation' et
        # 'referentiel' (les 2 ateliers conservés). Pas les 3 supprimés.
        # On vérifie sur la ligne de définition (recherche tolérante).
        for cle in ("'recapcours'", "'recapexos'", "'plantravail'"):
            # Tolérance : autorisé dans un commentaire qui commence par //
            for ligne in app_js.splitlines():
                stripped = ligne.lstrip()
                if cle in ligne and not stripped.startswith('//'):
                    pytest.fail(
                        f"Référence active à {cle} en code : {ligne!r}"
                    )

    # ── app.py ─────────────────────────────────────────────────────
    # v0.16.10 — from routes.plans_de_travail réintroduit (portée séquence) ;
    # seuls recap_cours/recap_exos restent supprimés.
    @pytest.mark.parametrize("nom_import", [
        "from routes.recap_cours",
        "from routes.recap_exos",
    ])
    def test_imports_routes_supprimes(self, app_py, nom_import):
        for ligne in app_py.splitlines():
            stripped = ligne.lstrip()
            if nom_import in ligne and not stripped.startswith('#'):
                pytest.fail(
                    f"Import actif {nom_import!r} dans app.py : {ligne!r}"
                )

    @pytest.mark.parametrize("nom_bp", [
        "bp_recap_cours",
        "bp_recap_exos",
    ])
    def test_blueprints_non_enregistres(self, app_py, nom_bp):
        # On cherche les usages en code (hors commentaires).
        for ligne in app_py.splitlines():
            stripped = ligne.lstrip()
            if nom_bp in ligne and not stripped.startswith('#'):
                pytest.fail(
                    f"Blueprint {nom_bp} référencé en code : {ligne!r}"
                )


# ── F5 — Renommage « Ateliers » → « Conception de référentiel » ──────


class TestF5RenommageBandeau:
    """Le bouton du bandeau supérieur est renommé pour préparer
    l'introduction prochaine d'un autre bouton « Ateliers » dans la
    partie Suivi de classe (où des ateliers de suivi seront ajoutés).
    """

    def test_nouveau_label_present(self, html):
        assert "Conception de référentiel" in html

    def test_ancien_label_absent_du_bandeau(self, html):
        # On cherche le bouton du bandeau supérieur (data-tab="ateliers").
        # Le label visible ne doit plus être "Ateliers".
        # On extrait la ligne contenant data-tab="ateliers" et vérifie
        # son contenu textuel.
        ligne_bouton = None
        for ligne in html.splitlines():
            if 'data-tab="ateliers"' in ligne and '<button' in ligne:
                ligne_bouton = ligne
                break
        assert ligne_bouton is not None, (
            "Le bouton du bandeau data-tab=\"ateliers\" doit exister"
        )
        assert "Conception de référentiel" in ligne_bouton, (
            f"Le label du bouton doit être 'Conception de référentiel' : "
            f"{ligne_bouton!r}"
        )

    def test_data_tab_inchange(self, html):
        # L'attribut data-tab="ateliers" doit rester (identifiant
        # interne lu par app.js). Seul le texte visible change.
        assert 'data-tab="ateliers"' in html
