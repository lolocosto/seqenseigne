"""routes/atomes.py — Notions, méthodes, exercices, objectifs.

v0.13.6.15 — Refonte des routes GET :
  - GET liste : utilise le service générique `lister_atomes_sequence`
    qui retourne le contrat uniforme à 6 clés
    {id, titre, num, code, etat_code, liens}.
  - GET unitaire : nouveau, renvoie le détail complet (corps, enonce…)
    + enrichi avec `liens` (cohérence avec le GET liste, le frontend
    s'appuie sur ce champ pour le bouton « reprendre titre objectif »).
"""

from flask import Blueprint, jsonify, request, current_app
from services import atomes as svc
from services.atomes_liste import (
    lister_atomes_sequence,
    TypeAtomeInvalide,
)
from services.liaisons_atomes import enrichir_liste_atomes
from services.etats_edition import assert_atome_modifiable, ItemVerrouille

bp = Blueprint("atomes", __name__)


def _js():
    return current_app.json_store


def _store_conn():
    """Helper : retourne un context manager sur la connexion SQLite.
    Utilisé pour appeler `lister_atomes_sequence` qui prend une conn."""
    return _js()._conn()


def _params_niveau_sequence():
    """v0.13.6.15 — Lit niveau et sequence depuis les query params, lève
    une réponse 400 si l'un des deux manque.

    Retourne (niveau, sequence) ou (None, jsonify_response) en cas
    d'erreur — l'appelant inspecte le 2e élément pour décider."""
    niveau = (request.args.get("niveau") or "").strip()
    sequence = (request.args.get("sequence") or "").strip()
    if not niveau or not sequence:
        return None, (jsonify({
            "error": "Paramètres 'niveau' et 'sequence' requis.",
            "code":  "params_manquants",
        }), 400)
    return (niveau, sequence), None


def _lire_unitaire(type_atome: str, atome_id: str):
    """v0.13.6.15 — Helper pour les GET unitaires de notion/méthode/
    exercice. Charge la liste complète depuis le store, trouve l'item
    par ID, enrichit avec `liens` et renvoie. Si introuvable, 404.

    Pattern minimaliste : on n'a pas de fonction service dédiée à la
    lecture unitaire (les services manipulent toujours des listes), on
    réutilise donc les `lire_xxx` du store.
    """
    if type_atome == 'notion':
        liste = _js().lire_notions()
    elif type_atome == 'methode':
        liste = _js().lire_methodes()
    elif type_atome == 'exercice':
        liste = _js().lire_exercices()
    else:
        return jsonify({"error": f"Type inconnu : {type_atome}"}), 400

    atome = next((a for a in liste if a.get('id') == atome_id), None)
    if atome is None:
        return jsonify({
            "error": f"{type_atome} '{atome_id}' introuvable.",
            "code":  "atome_introuvable",
        }), 404

    # Enrichissement liens : nécessaire pour le bouton « reprendre titre
    # objectif » côté frontend (mécanisme chantier B).
    with _store_conn() as conn:
        enrichir_liste_atomes(conn, [atome], type_atome)

    return jsonify(atome)


# ── Factorisation des routes atomes (v0.13.7.0e) ──────────────────────────────
#
# Les 3 types d'atomes (notion, méthode, exercice) ont exactement les mêmes
# 5 routes REST :
#   GET    /api/<segment>?niveau=…&sequence=…  → liste (contrat à 6 clés)
#   GET    /api/<segment>/<id>                 → détail unitaire enrichi
#   POST   /api/<segment>                       → création
#   PATCH  /api/<segment>/<id>                  → modification (v0.13.7.0e :
#                                                 strict PATCH, plus PUT)
#   DELETE /api/<segment>/<id>                  → suppression
#
# La fonction `_enregistrer_routes_atome` génère ces 5 routes pour un type
# donné. Les seules variations entre les 3 types sont :
#   - le segment d'URL (notions / methodes / exercices)
#   - les fonctions service (creer_notion / modifier_notion / supprimer_notion)
#   - les méthodes du store  (lire_notions / ecrire_notions)
#   - le message « non trouvé(e) » (accord grammatical)
#
# Tout cela est passé par la config.

def _enregistrer_routes_atome(bp, type_atome, segment_url,
                              creer, modifier, supprimer,
                              nom_lire, nom_ecrire,
                              message_non_trouve):
    """Génère et enregistre les 5 routes REST pour un type d'atome.

    Args:
      bp:                 le Blueprint Flask à enrichir
      type_atome:         clé interne pour `lister_atomes_sequence` et
                          `_lire_unitaire` (ex: 'notion', 'methode',
                          'exercice')
      segment_url:        segment d'URL sans slash (ex: 'notions')
      creer:              fonction service de création
                          (liste, data) → (liste, atome|None, err)
      modifier:           fonction service de modification
                          (liste, id, data) → (liste, atome|None, err)
      supprimer:          fonction service de suppression
                          (liste, id) → (liste, err)
      nom_lire:           nom de la méthode `lire_*` sur le store JS
                          (ex: 'lire_notions')
      nom_ecrire:         nom de la méthode `ecrire_*` sur le store JS
                          (ex: 'ecrire_notions')
      message_non_trouve: substring qui doit apparaître dans le message
                          d'erreur du service pour qu'on retourne 404 au
                          lieu de 400 (ex: 'trouvée' / 'trouvé')
    """
    base = f"/api/{segment_url}"
    item = f"/api/{segment_url}/<atome_id>"

    # GET liste ────────────────────────────────────────────────
    def _liste():
        # v0.30.2 — niveau obligatoire ; sequence optionnelle : si absente, on
        # liste toutes les séquences du niveau (mode « toutes séquences »).
        niveau = (request.args.get("niveau") or "").strip()
        sequence = (request.args.get("sequence") or "").strip()
        if not niveau:
            return jsonify({"error": "Paramètre 'niveau' requis.",
                            "code": "params_manquants"}), 400
        try:
            with _store_conn() as conn:
                atomes = lister_atomes_sequence(conn, type_atome, niveau, sequence)
        except TypeAtomeInvalide as e:
            return jsonify({"error": str(e), "code": "type_atome_invalide"}), 400
        return jsonify(atomes)
    _liste.__name__ = f"api_get_{segment_url}"
    bp.add_url_rule(base, view_func=_liste, methods=["GET"])

    # GET unitaire ─────────────────────────────────────────────
    def _detail(atome_id):
        return _lire_unitaire(type_atome, atome_id)
    _detail.__name__ = f"api_get_{type_atome}"
    bp.add_url_rule(item, view_func=_detail, methods=["GET"])

    # POST ─────────────────────────────────────────────────────
    def _create():
        js = _js()
        liste = getattr(js, nom_lire)()
        liste, atome, err = creer(liste, request.get_json(force=True))
        if err:
            return jsonify({"error": err}), 400
        getattr(js, nom_ecrire)(liste)
        return jsonify(atome), 201
    _create.__name__ = f"api_create_{type_atome}"
    bp.add_url_rule(base, view_func=_create, methods=["POST"])

    # PATCH (modification partielle) ───────────────────────────
    # v0.13.7.0e — Strict PATCH (plus de PUT). Cohérent avec la sémantique
    # réelle des services `modifier_*` (whitelist + assignation partielle).
    def _update(atome_id):
        # v0.16.4 — Refuse la modification du contenu d'un atome validé
        # (défense en profondeur ; l'UI grise aussi les champs). Pour
        # modifier, l'utilisateur doit d'abord repasser l'atome en cours.
        with _store_conn() as conn:
            try:
                assert_atome_modifiable(conn, type_atome, atome_id)
            except ItemVerrouille as e:
                return jsonify({"error": str(e), "code": e.code}), 409
        js = _js()
        liste = getattr(js, nom_lire)()
        liste, atome, err = modifier(liste, atome_id, request.get_json(force=True))
        if err:
            code = 404 if message_non_trouve in err else 400
            return jsonify({"error": err}), code
        getattr(js, nom_ecrire)(liste)
        return jsonify(atome)
    _update.__name__ = f"api_update_{type_atome}"
    bp.add_url_rule(item, view_func=_update, methods=["PATCH"])

    # DELETE ───────────────────────────────────────────────────
    def _delete(atome_id):
        js = _js()
        liste = getattr(js, nom_lire)()
        liste, err = supprimer(liste, atome_id)
        if err:
            return jsonify({"error": err}), 404
        getattr(js, nom_ecrire)(liste)
        return jsonify({"deleted": atome_id})
    _delete.__name__ = f"api_delete_{type_atome}"
    bp.add_url_rule(item, view_func=_delete, methods=["DELETE"])


# ── Enregistrement des 3 types d'atomes ──────────────────────────────────────

_enregistrer_routes_atome(
    bp,
    type_atome='notion',
    segment_url='notions',
    creer=svc.creer_notion,
    modifier=svc.modifier_notion,
    supprimer=svc.supprimer_notion,
    nom_lire='lire_notions',
    nom_ecrire='ecrire_notions',
    message_non_trouve='trouvée',
)

_enregistrer_routes_atome(
    bp,
    type_atome='methode',
    segment_url='methodes',
    creer=svc.creer_methode,
    modifier=svc.modifier_methode,
    supprimer=svc.supprimer_methode,
    nom_lire='lire_methodes',
    nom_ecrire='ecrire_methodes',
    message_non_trouve='trouvée',
)

_enregistrer_routes_atome(
    bp,
    type_atome='exercice',
    segment_url='exercices',
    creer=svc.creer_exercice,
    modifier=svc.modifier_exercice,
    supprimer=svc.supprimer_exercice,
    nom_lire='lire_exercices',
    nom_ecrire='ecrire_exercices',
    message_non_trouve='trouvé',
)


# ── Objectifs (route retirée v0.14.6.b.1) ────────────────────────────────────
# La route GET /api/objectifs était l'endpoint legacy qui peuplait le
# sélecteur JS `ATL_OBJ_CAT` (atelier exercice). Ce sélecteur DOM
# (`#atl-exercice-obj-sel`) a été retiré du HTML depuis la refonte v0.10
# de l'atelier ; la route ne servait donc plus à rien depuis lors et est
# supprimée définitivement avec le chantier de suppression de v1.
# L'atelier exercice actuel utilise l'API `/api/objectifs-v2/...` qui
# lit directement la table `objectifs`.


# ── Livrets de séquence ────────────────────────────────────────────────────────


@bp.route("/api/atomes/livrets", methods=["GET"])
def api_get_livrets():
    """
    Retourne les livrets de séquence importés.
    Filtres optionnels : niveau=N11, sequence=S01
    """
    js = _js()
    livrets  = js.lire_livrets_importes()
    niveau   = request.args.get("niveau")
    sequence = request.args.get("sequence")
    if niveau:
        livrets = [l for l in livrets if l.get("niveau") == niveau]
    if sequence:
        livrets = [l for l in livrets if l.get("sequence") == sequence]
    return jsonify(livrets)
