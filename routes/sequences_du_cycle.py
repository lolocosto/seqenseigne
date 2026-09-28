"""routes/sequences_du_cycle.py — R3.

Blueprint pour le CRUD des séquences du cycle.
"""

from __future__ import annotations
from flask import Blueprint, jsonify, request, current_app

from services.sequences_du_cycle import (
    creer_sequence,
    modifier_sequence,
    supprimer_sequence,
    lire_sequence,
    lister_sequences,
    SequenceErreur,
    SequenceEnUsage,
)


bp_sequences_du_cycle = Blueprint("sequences_du_cycle", __name__)


_MAP_HTTP = {
    "sequence_introuvable": 404,
    "cycle_introuvable":    404,
    "doublon_code":         409,
    "doublon_numero":       409,
    "theme_invalide":       400,
    "code_vide":            400,
    "numero_vide":          400,
    "numero_invalide":      400,
    "nom_vide":             400,
    "en_usage":             409,
}


def _erreur(e: SequenceErreur):
    code_http = _MAP_HTTP.get(e.code, 400)
    payload = {"error": str(e), "code": e.code}
    # Enrichir avec les détails des atomes en cas de en_usage
    if isinstance(e, SequenceEnUsage):
        payload["details"] = e.details
    return jsonify(payload), code_http


# ── Liste d'un cycle ─────────────────────────────────────────────────────────

@bp_sequences_du_cycle.route(
    "/api/cycles/<cycle_code>/sequences/detail", methods=["GET"]
)
def api_lister_sequences_detail(cycle_code: str):
    """Liste des séquences d'un cycle, enrichies avec thème et compteurs."""
    store = current_app.json_store
    with store._conn() as conn:
        seqs = lister_sequences(conn, cycle_code)
    return jsonify({"sequences": seqs})


# ── CRUD ─────────────────────────────────────────────────────────────────────

@bp_sequences_du_cycle.route(
    "/api/cycles/<cycle_code>/sequences", methods=["POST"]
)
def api_creer_sequence(cycle_code: str):
    payload = request.get_json(silent=True) or {}
    store = current_app.json_store
    try:
        with store._conn() as conn:
            seq = creer_sequence(
                conn,
                cycle_code=cycle_code,
                code=payload.get("code", ""),
                numero=payload.get("numero"),
                nom=payload.get("nom", ""),
                theme_id=payload.get("theme_id") or None,
            )
    except SequenceErreur as e:
        return _erreur(e)
    return jsonify({"sequence": seq}), 201


@bp_sequences_du_cycle.route(
    "/api/sequences_du_cycle/<seq_id>", methods=["GET"]
)
def api_lire_sequence(seq_id: str):
    store = current_app.json_store
    try:
        with store._conn() as conn:
            seq = lire_sequence(conn, seq_id)
    except SequenceErreur as e:
        return _erreur(e)
    return jsonify({"sequence": seq})


@bp_sequences_du_cycle.route(
    "/api/sequences_du_cycle/<seq_id>", methods=["PUT", "PATCH"]
)
def api_modifier_sequence(seq_id: str):
    payload = request.get_json(silent=True) or {}
    store = current_app.json_store
    try:
        with store._conn() as conn:
            seq = modifier_sequence(
                conn,
                seq_id=seq_id,
                code=payload.get("code"),
                numero=payload.get("numero"),
                nom=payload.get("nom"),
                theme_id=payload.get("theme_id"),
                detacher_theme=bool(payload.get("detacher_theme", False)),
            )
    except SequenceErreur as e:
        return _erreur(e)
    return jsonify({"sequence": seq})


@bp_sequences_du_cycle.route(
    "/api/sequences_du_cycle/<seq_id>", methods=["DELETE"]
)
def api_supprimer_sequence(seq_id: str):
    store = current_app.json_store
    try:
        with store._conn() as conn:
            rapport = supprimer_sequence(conn, seq_id)
    except SequenceErreur as e:
        return _erreur(e)
    return jsonify(rapport)
