"""
routes/cartes_automatisme.py — API REST des cartes d'automatisme.

v0.13.6.8.2 — Suppression des routes /valider et /devalider au profit
              du mécanisme unifié PATCH /api/atomes/carte/<id>/etat
              (cf. routes/etats_edition.py). La validation pédagogique
              est conservée sous forme de hook dans
              services/cartes_automatisme._valider_carte_hook.
v0.13.6.2 — Ajout du rendu PDF élémentaire d'une carte (rendu-tex / rendu-pdf).
v0.13.6.1.2 — Refonte du lien (notion/méthode au lieu d'objectifs).

Endpoints implémentés :

  Cartes (CRUD)
    GET    /api/cartes?niveau=N10&sequence=S01     → liste filtrée
    GET    /api/cartes/<carte_id>                  → détail
    POST   /api/cartes                             → création
    PATCH  /api/cartes/<carte_id>                  → modification PATCH-like
    DELETE /api/cartes/<carte_id>                  → suppression

  Transitions d'état (v0.13.6.8.2 — unifié via etats_edition)
    PATCH  /api/atomes/carte/<carte_id>/etat       → en_cours ↔ valide
    Cf. routes/etats_edition.py pour le détail.

  Config atelier
    GET    /api/cartes/config/<cle>                → lit une valeur
    PUT    /api/cartes/config/<cle>                → modifie

  Aides UI (v0.13.6.1.2)
    GET    /api/cartes/niveau/<niveau>/sequence/<sequence>/notions-disponibles
    GET    /api/cartes/niveau/<niveau>/sequence/<sequence>/methodes-disponibles

Pattern d'erreurs : aligné sur routes/evaluations.py (CarteErreur avec
code stable + details, mappé en HTTP par _CODE_HTTP).

Note v0.13.6.1.2 : les routes /objectifs (v0.13.6.1) sont supprimées.
"""
from flask import Blueprint, request, jsonify, current_app

from services import cartes_automatisme as svc
from services.cartes_automatisme import CarteErreur

bp = Blueprint("cartes_automatisme", __name__)


def _store():
    return current_app.json_store


_CODE_HTTP = {
    # 404 Not Found
    "carte_introuvable":              404,
    "lien_introuvable":               404,

    # 409 Conflict
    "num_deja_utilise":               409,
    # v0.13.6.8.2 : deja_valide et deja_en_cours supprimés (filtrage en
    # amont côté client + plus de routes /valider /devalider qui les
    # levaient).

    # 400 Bad Request
    "type_pedago_invalide":           400,
    "type_tech_invalide":             400,
    "etat_code_invalide":             400,
    "num_invalide":                   400,
    "lien_type_invalide":             400,
    "lien_incoherent":                400,
    "champ_invalide":                 400,
    # v0.13.6.8.2 : validation_pedagogique_echouee supprimé (la
    # validation pédagogique passe maintenant par etats_edition.py
    # avec le code 'validation_pedagogique_echec').
    "cle_config_inconnue":            400,
    "valeur_config_invalide":         400,
}


def _erreur_metier(e: CarteErreur):
    statut = _CODE_HTTP.get(e.code, 400)
    return jsonify({
        "error":   str(e),
        "code":    e.code,
        "details": e.details,
    }), statut


# ═════════════════════════════════════════════════════════════════════════════
# Cartes — CRUD
# ═════════════════════════════════════════════════════════════════════════════


@bp.route("/api/cartes", methods=["GET"])
def api_lister():
    """v0.13.6.15 — Liste légère pour la sidebar (contrat à 6 clés).

    Avant : retournait `{"cartes": [...]}` avec tous les champs détaillés.
    Maintenant : retourne une liste directe `[{id, titre, num, code,
    etat_code, liens}, ...]` cohérent avec les autres ateliers d'atomes.
    """
    niveau = (request.args.get("niveau") or "").strip()
    sequence = (request.args.get("sequence") or "").strip()
    # v0.30.2 — niveau obligatoire ; sequence optionnelle (toutes séquences).
    if not niveau:
        return jsonify({
            "error": "Paramètre 'niveau' requis.",
            "code":  "params_manquants",
        }), 400
    from services.atomes_liste import (
        lister_atomes_sequence, TypeAtomeInvalide,
    )
    store = _store()
    try:
        with store._conn() as conn:
            atomes = lister_atomes_sequence(conn, 'carte', niveau, sequence)
    except TypeAtomeInvalide as e:
        return jsonify({"error": str(e), "code": "type_atome_invalide"}), 400
    return jsonify(atomes)


@bp.route("/api/cartes/<carte_id>", methods=["GET"])
def api_lire(carte_id):
    """v0.13.6.13 : enrichit la carte avec le champ `liens` également."""
    store = _store()
    with store._conn() as conn:
        try:
            carte = svc.lire_carte(conn, carte_id)
        except CarteErreur as e:
            return _erreur_metier(e)
        from services.liaisons_atomes import enrichir_liste_atomes
        enrichir_liste_atomes(conn, [carte], 'carte')
    return jsonify(carte)


@bp.route("/api/cartes", methods=["POST"])
def api_creer():
    """Crée une nouvelle carte.

    Body JSON :
      niveau       (requis)
      sequence     (requis)
      type_pedago  (optionnel, défaut 'definition')
      type_tech    (optionnel, défaut 'fixe')
      nom          (optionnel)
      recto        (optionnel)
      verso        (optionnel)
      variables    (optionnel)
      lien_type    (optionnel, 'notion' | 'methode' | null) — legacy
      lien_id      (optionnel, id de la notion/méthode | null) — legacy
      objectif_ids (optionnel, liste d'ids — v0.13.6.13)
      num          (optionnel — auto si absent)
      ordre        (optionnel — auto si absent)

    v0.13.6.13 : si `objectif_ids` est fourni, il prime sur lien_*. Sinon,
    les lien_* sont traités comme avant pour rétrocompat et leurs
    objectifs dérivés sont écrits dans objectif_cartes.
    """
    data = request.get_json(silent=True) or {}
    niveau = (data.get("niveau") or "").strip()
    sequence = (data.get("sequence") or "").strip()
    if not niveau or not sequence:
        return jsonify({
            "error": "Champs 'niveau' et 'sequence' requis.",
            "code":  "params_manquants",
        }), 400

    kwargs = {"niveau": niveau, "sequence": sequence}
    for champ in ("type_pedago", "type_tech", "nom",
                  "recto", "verso", "variables"):
        if champ in data:
            kwargs[champ] = data[champ]
    for champ in ("lien_type", "lien_id"):
        if champ in data:
            kwargs[champ] = data[champ]
    # v0.13.6.13 — Nouveau paramètre objectif_ids (liste)
    if "objectif_ids" in data:
        kwargs["objectif_ids"] = data["objectif_ids"] or []
    for champ in ("num", "ordre"):
        if champ in data and data[champ] is not None:
            kwargs[champ] = data[champ]

    store = _store()
    with store._conn() as conn:
        try:
            carte = svc.creer_carte(conn, **kwargs)
        except CarteErreur as e:
            return _erreur_metier(e)
    return jsonify(carte), 201


@bp.route("/api/cartes/<carte_id>", methods=["PATCH"])
def api_modifier(carte_id):
    """Modifie une carte. Body JSON : champs à mettre à jour.

    Pour les transitions d'état, utiliser /valider ou /devalider.
    Pour modifier le lien (legacy) : envoyer le couple (lien_type, lien_id)
    ensemble, même si un seul des deux change.

    v0.13.6.13 : nouveau paramètre `objectif_ids` (liste d'ids). Si fourni,
    il remplace intégralement les liaisons de la carte. Une liste vide
    supprime toutes les liaisons (carte orpheline). Si `objectif_ids` ET
    `lien_type`/`lien_id` sont fournis, `objectif_ids` prime.

    v0.13.7.0e : route maintenue en PATCH strict (déjà le cas), cohérence
    désormais alignée avec les autres atomes qui sont aussi passés en
    PATCH strict.
    """
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({
            "error": "Aucun champ fourni.",
            "code":  "params_manquants",
        }), 400
    store = _store()
    with store._conn() as conn:
        # v0.16.4 — Refuse la modification d'une carte validée (409).
        from services.etats_edition import (
            assert_atome_modifiable, ItemVerrouille,
        )
        try:
            assert_atome_modifiable(conn, "carte", carte_id)
        except ItemVerrouille as e:
            return jsonify({"error": str(e), "code": e.code}), 409
        try:
            carte = svc.modifier_carte(conn, carte_id, **data)
        except CarteErreur as e:
            return _erreur_metier(e)
    return jsonify(carte)


@bp.route("/api/cartes/<carte_id>", methods=["DELETE"])
def api_supprimer(carte_id):
    store = _store()
    with store._conn() as conn:
        try:
            svc.supprimer_carte(conn, carte_id)
        except CarteErreur as e:
            return _erreur_metier(e)
    return jsonify({"deleted": carte_id}), 200


# ═════════════════════════════════════════════════════════════════════════════
# Transitions d'état
# ═════════════════════════════════════════════════════════════════════════════
#
# v0.13.6.8.2 — Les routes POST /api/cartes/<id>/valider et /devalider
# ont été supprimées au profit du mécanisme unifié :
#
#   PATCH /api/atomes/carte/<id>/etat
#   Body: {"etat_code": "valide" | "en_cours"}
#
# Cf. routes/etats_edition.py. La validation pédagogique est conservée
# sous forme de hook dans services/cartes_automatisme.py
# (_valider_carte_hook), enregistré dans le registre de etats_edition
# au chargement du module.


# ═════════════════════════════════════════════════════════════════════════════
# Configuration atelier
# ═════════════════════════════════════════════════════════════════════════════


@bp.route("/api/cartes/config/<cle>", methods=["GET"])
def api_config_lire(cle):
    store = _store()
    with store._conn() as conn:
        try:
            valeur = svc.lire_config(conn, cle)
        except CarteErreur as e:
            return _erreur_metier(e)
    return jsonify({"cle": cle, "valeur": valeur})


@bp.route("/api/cartes/config/<cle>", methods=["PUT"])
def api_config_modifier(cle):
    """Modifie une valeur de config. Body JSON : { "valeur": "..." }"""
    data = request.get_json(silent=True) or {}
    valeur = data.get("valeur")
    if valeur is None:
        return jsonify({
            "error": "Champ 'valeur' requis.",
            "code":  "params_manquants",
        }), 400
    store = _store()
    with store._conn() as conn:
        try:
            svc.modifier_config(conn, cle, str(valeur))
        except CarteErreur as e:
            return _erreur_metier(e)
    return jsonify({"cle": cle, "valeur": str(valeur)})


# ═════════════════════════════════════════════════════════════════════════════
# Aides UI : notions et méthodes disponibles
# ═════════════════════════════════════════════════════════════════════════════


@bp.route("/api/cartes/niveau/<niveau>/sequence/<sequence>/notions-disponibles",
          methods=["GET"])
def api_notions_disponibles(niveau, sequence):
    """v0.13.6.1.2 — Renvoie les notions d'un (niveau, séquence) pour le
    sélecteur de lien de l'atelier carte.

    Triées par num_connaissance puis titre.
    """
    store = _store()
    with store._conn() as conn:
        notions = svc.lister_notions_disponibles(conn, niveau, sequence)
    return jsonify({
        "niveau": niveau, "sequence": sequence,
        "notions": notions,
    })


@bp.route("/api/cartes/niveau/<niveau>/sequence/<sequence>/methodes-disponibles",
          methods=["GET"])
def api_methodes_disponibles(niveau, sequence):
    """v0.13.6.1.2 — Renvoie les méthodes d'un (niveau, séquence) pour le
    sélecteur de lien de l'atelier carte.

    Triées par num_methode puis titre.
    """
    store = _store()
    with store._conn() as conn:
        methodes = svc.lister_methodes_disponibles(conn, niveau, sequence)
    return jsonify({
        "niveau": niveau, "sequence": sequence,
        "methodes": methodes,
    })


# ═════════════════════════════════════════════════════════════════════════════
# v0.14.4 — Routes de rendu PDF supprimées.
# ═════════════════════════════════════════════════════════════════════════════
#
# Les routes /api/cartes/<id>/rendu-pdf, /info, /rendu-tex ont été
# retirées dans cette livraison. La carte utilise désormais l'API
# unifiée /api/atomes/carte/<id>/... (cf. routes/rendu_atome.py et le
# dispatch services.latex_rendu_atome.generer_tex_par_type ajouté en
# v0.14.2).
#
# Le client (static/atelier_carte_automatisme.js) déclare
# `endpointRenduPdf: '/api/atomes/carte'` depuis cette même v0.14.4.
#
# Les helpers internes `_configuration` et `_cache_dir` qui servaient
# UNIQUEMENT aux routes rendu ont été supprimés en même temps. Si une
# route CRUD ajoutée plus tard a besoin de la config ou du cache, il
# faudra les ré-instancier (ils sont triviaux : voir routes/rendu_atome.py).
