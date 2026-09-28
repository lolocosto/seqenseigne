"""Tests v0.14.2 — Backend unifié pour le rendu PDF des 5 ateliers.

Cette livraison ajoute :
1. Une constante `TYPES_ATOMES_TOUS` qui inclut 'carte' à côté des 4
   types classiques (exercice, notion, methode, fiche).
2. Une fonction dispatch `generer_tex_par_type(conn, type, id, ...)`
   qui route vers `generer_tex_atome` (4 types classiques) ou
   `generer_tex_carte` (type='carte'), avec homogénéisation des
   exceptions (CarteIntrouvable → LookupError).
3. Une nouvelle route `GET /api/atomes/<type>/<id>/rendu-pdf/info`
   qui répond `{cache_valide: bool}` sans déclencher de compilation.

Les tests d'intégration vérifient les codes HTTP des cas dégénérés
(type invalide, atome introuvable) sans nécessiter de peuplement BDD
lourd. Les tests fonctionnels « cache valide / non valide » seront
exercés via les ateliers en v0.14.3 et v0.14.4 quand les 4 ateliers
manquants auront le HTML statique pour appeler /info.
"""
from __future__ import annotations
import pytest


# ── Constantes : TYPES_ATOMES_TOUS ────────────────────────────────────────

class TestConstantesUnifiees:
    def test_types_atomes_tous_inclut_carte(self):
        """TYPES_ATOMES_TOUS doit contenir les 5 types (4 classiques + carte)."""
        from services.latex_rendu_atome import TYPES_ATOMES_TOUS, TABLES_ATOMES
        attendus = {'exercice', 'notion', 'methode', 'fiche', 'carte'}
        assert TYPES_ATOMES_TOUS == attendus, (
            f"Set incohérent. Attendu : {attendus}, reçu : {set(TYPES_ATOMES_TOUS)}"
        )

    def test_tables_atomes_ne_contient_pas_carte(self):
        """TABLES_ATOMES reste limité aux 4 types « atome classique »
        car les cartes ne passent pas par generer_tex_atome (qui utilise
        TABLES_ATOMES pour mapper type → nom de table SQL). La carte a
        son propre générateur (services.render_carte.generer_tex_carte).
        """
        from services.latex_rendu_atome import TABLES_ATOMES
        assert 'carte' not in TABLES_ATOMES, (
            "TABLES_ATOMES ne doit PAS contenir 'carte' : la carte a son "
            "propre générateur via services.render_carte"
        )

    def test_types_classiques_recouvrent_tables(self):
        """Tous les types de TABLES_ATOMES doivent être dans TYPES_ATOMES_TOUS."""
        from services.latex_rendu_atome import TABLES_ATOMES, TYPES_ATOMES_TOUS
        for t in TABLES_ATOMES:
            assert t in TYPES_ATOMES_TOUS, f"Type {t!r} manquant dans TYPES_ATOMES_TOUS"


# ── Dispatch generer_tex_par_type ────────────────────────────────────────

class TestDispatchGenereTexParType:
    def test_dispatch_existe_et_importable(self):
        """La fonction de dispatch doit être exportée depuis le service."""
        from services.latex_rendu_atome import generer_tex_par_type
        assert callable(generer_tex_par_type)

    def test_type_inconnu_leve_valueerror(self, store):
        """Un type non listé dans TYPES_ATOMES_TOUS → ValueError."""
        from services.latex_rendu_atome import generer_tex_par_type
        with store._conn() as conn:
            with pytest.raises(ValueError, match="type_atome inconnu"):
                generer_tex_par_type(conn, 'inconnu', 'qqid_inexistant')

    def test_atome_introuvable_classique_leve_lookuperror(self, store):
        """Pour un type classique (notion), un id absent → LookupError."""
        from services.latex_rendu_atome import generer_tex_par_type
        with store._conn() as conn:
            with pytest.raises(LookupError):
                generer_tex_par_type(conn, 'notion', 'no_existe_pas')

    def test_carte_introuvable_leve_lookuperror(self, store):
        """Pour type='carte', un id absent doit AUSSI lever LookupError
        (et non CarteIntrouvable qui est l'exception métier interne).
        C'est la conversion explicite faite par le dispatch pour
        homogénéiser le contrat des routes.
        """
        from services.latex_rendu_atome import generer_tex_par_type
        with store._conn() as conn:
            with pytest.raises(LookupError):
                generer_tex_par_type(conn, 'carte', 'crt_nexiste_pas')


# ── Route /api/atomes/<type>/<id>/rendu-pdf/info ─────────────────────────

class TestRouteInfo:
    """Tests d'intégration de la nouvelle route GET .../rendu-pdf/info."""

    def test_type_invalide_renvoie_400(self, client):
        """type_atome='inconnu' → 400 avec message d'erreur explicite."""
        r = client.get('/api/atomes/inconnu/qqid/rendu-pdf/info')
        assert r.status_code == 400
        data = r.get_json()
        assert 'error' in data
        assert 'invalide' in data['error']
        # Liste des valeurs attendues présente
        assert 'valeurs_attendues' in data
        assert 'carte' in data['valeurs_attendues']
        assert 'exercice' in data['valeurs_attendues']

    def test_carte_introuvable_renvoie_404(self, client):
        """carte avec id absent → 404."""
        r = client.get('/api/atomes/carte/crt_inexistant/rendu-pdf/info')
        assert r.status_code == 404
        data = r.get_json()
        assert 'error' in data

    def test_notion_introuvable_renvoie_404(self, client):
        """notion avec id absent → 404."""
        r = client.get('/api/atomes/notion/notion_inexistante/rendu-pdf/info')
        assert r.status_code == 404

    def test_exercice_introuvable_renvoie_404(self, client):
        """exercice avec id absent → 404."""
        r = client.get('/api/atomes/exercice/ex_inexistant/rendu-pdf/info')
        assert r.status_code == 404

    def test_methode_introuvable_renvoie_404(self, client):
        """methode avec id absent → 404."""
        r = client.get('/api/atomes/methode/me_inexistante/rendu-pdf/info')
        assert r.status_code == 404

    def test_fiche_introuvable_renvoie_404(self, client):
        """fiche avec id absent → 404."""
        r = client.get('/api/atomes/fiche/fc_inexistante/rendu-pdf/info')
        assert r.status_code == 404


# ── Route /rendu-pdf et /rendu-tex acceptent maintenant 'carte' ──────────

class TestRoutesUnifieesCarte:
    """Les routes /api/atomes/carte/<id>/rendu-pdf, /rendu-tex et
    /rendu-log doivent maintenant accepter type_atome='carte'
    (validation), même si la carte ciblée n'existe pas (404).
    """

    def test_carte_rendu_pdf_carte_introuvable_404(self, client):
        """POST /api/atomes/carte/<id>/rendu-pdf sur id inconnu → 404,
        pas 400 (le type 'carte' est valide).
        """
        r = client.post('/api/atomes/carte/crt_inexistant/rendu-pdf')
        # 404 (introuvable) attendu, surtout pas 400 (validation type).
        assert r.status_code == 404, (
            f"Attendu 404, reçu {r.status_code}. Si on a 400, c'est que "
            f"'carte' n'est pas accepté comme type valide."
        )

    def test_carte_rendu_tex_carte_introuvable_404(self, client):
        """GET /api/atomes/carte/<id>/rendu-tex sur id inconnu → 404."""
        r = client.get('/api/atomes/carte/crt_inexistant/rendu-tex')
        assert r.status_code == 404

    def test_carte_type_dans_valeurs_attendues(self, client):
        """Erreur de validation : la liste des types attendus doit inclure
        'carte' (sinon l'utilisateur ne sait pas qu'elle est supportée).
        """
        r = client.get('/api/atomes/xyz/qq/rendu-tex')
        assert r.status_code == 400
        data = r.get_json()
        assert 'valeurs_attendues' in data
        attendus = data['valeurs_attendues']
        assert 'carte' in attendus, (
            f"'carte' devrait être dans la liste des valeurs attendues "
            f"renvoyée par l'erreur 400. Reçu : {attendus}"
        )


# ── Route ancienne /api/cartes/<id>/... reste fonctionnelle (alias) ──────

class TestAncienneRouteCartesSupprimee:
    """v0.14.4 — Inversion de la sémantique de ce test groupe.

    Avant v0.14.4 (livraisons v0.14.2 et v0.14.3) : on conservait les
    routes /api/cartes/<id>/rendu-pdf et /info comme alias pour la
    rétrocompatibilité jusqu'au passage du client sur la nouvelle URL.

    À partir de v0.14.4 : le client a basculé sur /api/atomes/carte/...
    et les anciennes routes sont SUPPRIMÉES. Les tests vérifient
    maintenant qu'elles renvoient bien un 404 Flask (route inexistante)
    et non une réponse métier — c'est la preuve que la suppression a
    bien eu lieu.
    """

    def test_ancienne_route_rendu_pdf_supprimee(self, client):
        """POST /api/cartes/<id>/rendu-pdf doit renvoyer 404
        (route supprimée en v0.14.4). Flask renvoie 404 NOT FOUND HTML
        par défaut quand aucune route ne matche.
        """
        r = client.post('/api/cartes/crt_inexistant/rendu-pdf')
        assert r.status_code == 404, (
            f"La route /api/cartes/<id>/rendu-pdf doit être supprimée "
            f"(404 attendu), reçu : {r.status_code}"
        )

    def test_ancienne_route_info_supprimee(self, client):
        """L'ancienne route /api/cartes/<id>/rendu-pdf/info doit
        également être supprimée.
        """
        r = client.get('/api/cartes/crt_inexistant/rendu-pdf/info')
        assert r.status_code == 404, (
            f"La route /api/cartes/<id>/rendu-pdf/info doit être "
            f"supprimée (404 attendu), reçu : {r.status_code}"
        )

    def test_ancienne_route_rendu_tex_supprimee(self, client):
        """L'ancienne route /api/cartes/<id>/rendu-tex doit également
        être supprimée.
        """
        r = client.get('/api/cartes/crt_inexistant/rendu-tex')
        assert r.status_code == 404, (
            f"La route /api/cartes/<id>/rendu-tex doit être supprimée "
            f"(404 attendu), reçu : {r.status_code}"
        )
