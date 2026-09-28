"""routes/themes.py — R2.

Blueprint pour le CRUD des thèmes et l'exposition des familles de
couleurs disponibles pour le sélecteur.
"""

from __future__ import annotations
from flask import Blueprint, jsonify, request, current_app

from services.themes import (
    creer_theme,
    modifier_theme,
    supprimer_theme,
    lire_theme,
    lister_themes_avec_compteurs,
    ThemeErreur,
)
from services.couleurs_themes import FAMILLES_COULEURS


bp_themes = Blueprint("themes", __name__)


# ── Code d'erreur → code HTTP ────────────────────────────────────────────────

_MAP_HTTP = {
    "theme_introuvable": 404,
    "cycle_introuvable": 404,
    "doublon_code":      409,
    "doublon_nom":       409,
    "couleur_invalide":  400,
    "code_vide":         400,
    "nom_vide":          400,
    "en_usage":          409,
}


def _erreur(e: ThemeErreur):
    code_http = _MAP_HTTP.get(e.code, 400)
    return jsonify({"error": str(e), "code": e.code}), code_http


# ── Couleurs disponibles ─────────────────────────────────────────────────────

@bp_themes.route("/api/couleurs_themes", methods=["GET"])
def api_couleurs_themes():
    """Liste des familles de couleurs disponibles, pour alimenter le
    sélecteur du formulaire."""
    return jsonify({"familles": FAMILLES_COULEURS})


# ── Liste thèmes d'un cycle (avec compteurs) ─────────────────────────────────

@bp_themes.route("/api/cycles/<cycle_code>/themes/detail", methods=["GET"])
def api_lister_themes_detail(cycle_code: str):
    """Liste détaillée : thèmes + nombre de séquences rattachées.

    Route distincte de GET /api/cycles/<code>/themes (R1) qui renvoie
    une version allégée sans compteur.
    """
    store = current_app.json_store
    with store._conn() as conn:
        themes = lister_themes_avec_compteurs(conn, cycle_code)
    return jsonify({"themes": themes})


# ── CRUD ─────────────────────────────────────────────────────────────────────

@bp_themes.route("/api/cycles/<cycle_code>/themes", methods=["POST"])
def api_creer_theme(cycle_code: str):
    """Créer un thème dans le cycle."""
    payload = request.get_json(silent=True) or {}
    store = current_app.json_store
    try:
        with store._conn() as conn:
            theme = creer_theme(
                conn,
                cycle_code=cycle_code,
                code=payload.get("code", ""),
                nom=payload.get("nom", ""),
                code_couleur=payload.get("code_couleur", ""),
                description=payload.get("description", ""),
                ordre=payload.get("ordre"),
            )
    except ThemeErreur as e:
        return _erreur(e)
    return jsonify({"theme": theme}), 201


@bp_themes.route("/api/themes/<theme_id>", methods=["GET"])
def api_lire_theme(theme_id: str):
    store = current_app.json_store
    try:
        with store._conn() as conn:
            theme = lire_theme(conn, theme_id)
    except ThemeErreur as e:
        return _erreur(e)
    return jsonify({"theme": theme})


@bp_themes.route("/api/themes/<theme_id>", methods=["PUT", "PATCH"])
def api_modifier_theme(theme_id: str):
    payload = request.get_json(silent=True) or {}
    store = current_app.json_store
    try:
        with store._conn() as conn:
            theme = modifier_theme(
                conn,
                theme_id=theme_id,
                code=payload.get("code"),
                nom=payload.get("nom"),
                code_couleur=payload.get("code_couleur"),
                description=payload.get("description"),
                ordre=payload.get("ordre"),
            )
    except ThemeErreur as e:
        return _erreur(e)
    return jsonify({"theme": theme})


@bp_themes.route("/api/themes/<theme_id>", methods=["DELETE"])
def api_supprimer_theme(theme_id: str):
    store = current_app.json_store
    try:
        with store._conn() as conn:
            rapport = supprimer_theme(conn, theme_id)
    except ThemeErreur as e:
        return _erreur(e)
    return jsonify(rapport)
