"""routes/bascule.py — v0.51.12

Bascule de la base partagée vers data_atelier\\ et data_classe\\ (profil
complet seulement) : aperçu, puis exécution sur confirmation.
"""

from flask import Blueprint, current_app, jsonify, request

from services import bascule as bsc

bp = Blueprint("bascule", __name__)

_CODES = {"bascule_refusee": 409, "profil": 409, "paquet": 422, "import": 422,
          "echec": 500}


@bp.route("/api/bascule/apercu", methods=["GET"])
def api_apercu():
    return jsonify(bsc.apercu(current_app.json_store))


@bp.route("/api/bascule", methods=["POST"])
def api_executer():
    if not (request.get_json(silent=True) or {}).get("confirmer"):
        return jsonify({"error": "Confirmation requise.", "code": "confirmation"}), 400
    try:
        return jsonify(bsc.executer(current_app.json_store))
    except bsc.BasculeErreur as e:
        details = {k: v for k, v in (e.details or {}).items() if k != "referentiels"}
        return jsonify({"error": str(e), "code": e.code, "details": details}), \
            _CODES.get(e.code, 400)
