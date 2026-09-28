"""routes/preferences.py — v0.10.5.2

Endpoints REST pour les préférences utilisateur paramétrables.

Endpoints :
  GET    /api/preferences/<type>            — lister les items d'un type
  POST   /api/preferences/<type>            — ajouter un item
                                              body: {"valeur": "...", "ordre": int?}
  PUT    /api/preferences/items/<id>        — modifier
                                              body: {"valeur"?: "...", "ordre"?: int}
  DELETE /api/preferences/items/<id>        — supprimer
  PUT    /api/preferences/<type>/ordre      — réordonner
                                              body: {"ids": ["...", "..."]}

  GET    /api/preferences/valeur/<type>     — lire valeur unique
  PUT    /api/preferences/valeur/<type>     — définir valeur unique (upsert)
                                              body: {"valeur": "..."}
"""

from __future__ import annotations
from contextlib import contextmanager
from flask import Blueprint, jsonify, request, current_app

from services.preferences import (
    lister_items, ajouter_item, modifier_item, supprimer_item,
    reordonner_items, lire_valeur_unique, definir_valeur_unique,
    PreferencesErreur, ItemIntrouvable, ValeurInvalide,
)


bp_preferences = Blueprint("preferences", __name__)


_CODE_HTTP = {
    "item_introuvable": 404,
    "valeur_invalide":  400,
}


def _erreur(e: PreferencesErreur):
    return jsonify({"error": str(e), "code": e.code, **e.details}), \
        _CODE_HTTP.get(e.code, 500)


@contextmanager
def _store_conn():
    store = current_app.json_store
    with store._conn() as conn:
        yield conn


# ── Liste ────────────────────────────────────────────────────────────────────


@bp_preferences.route("/api/preferences/<type_>", methods=["GET"])
def api_lister(type_: str):
    with _store_conn() as conn:
        items = lister_items(conn, type_)
    return jsonify({"type": type_, "items": items})


@bp_preferences.route("/api/preferences/<type_>", methods=["POST"])
def api_ajouter(type_: str):
    payload = request.get_json(silent=True) or {}
    valeur = payload.get("valeur") or ""
    ordre = payload.get("ordre")
    try:
        with _store_conn() as conn:
            item = ajouter_item(conn, type_, valeur, ordre=ordre)
    except PreferencesErreur as e:
        return _erreur(e)
    return jsonify(item), 201


@bp_preferences.route("/api/preferences/items/<item_id>", methods=["PUT"])
def api_modifier(item_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        with _store_conn() as conn:
            item = modifier_item(
                conn, item_id,
                valeur=payload.get("valeur"),
                ordre=payload.get("ordre"),
            )
    except PreferencesErreur as e:
        return _erreur(e)
    return jsonify(item)


@bp_preferences.route("/api/preferences/items/<item_id>", methods=["DELETE"])
def api_supprimer(item_id: str):
    try:
        with _store_conn() as conn:
            supprimer_item(conn, item_id)
    except PreferencesErreur as e:
        return _erreur(e)
    return jsonify({"ok": True})


@bp_preferences.route("/api/preferences/<type_>/ordre", methods=["PUT"])
def api_reordonner(type_: str):
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids") or []
    if not isinstance(ids, list):
        return jsonify({
            "error": "Champ 'ids' attendu sous forme de liste.",
            "code":  "champ_invalide",
        }), 400
    with _store_conn() as conn:
        items = reordonner_items(conn, type_, ids)
    return jsonify({"type": type_, "items": items})


# ── Valeur unique ───────────────────────────────────────────────────────────


@bp_preferences.route("/api/preferences/valeur/<type_>", methods=["GET"])
def api_lire_valeur(type_: str):
    with _store_conn() as conn:
        val = lire_valeur_unique(conn, type_)
    return jsonify({"type": type_, "valeur": val})


@bp_preferences.route("/api/preferences/valeur/<type_>", methods=["PUT"])
def api_definir_valeur(type_: str):
    payload = request.get_json(silent=True) or {}
    if "valeur" not in payload:
        return jsonify({
            "error": "Champ 'valeur' obligatoire.",
            "code":  "champ_manquant",
        }), 400
    with _store_conn() as conn:
        item = definir_valeur_unique(conn, type_, payload["valeur"])
    return jsonify(item)
