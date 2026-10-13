"""routes/depot.py — v0.51.9

Boîte aux lettres (services/depot.py), commune aux profils :

  GET  /api/depot/etat                → réglages, envois en attente, journal
  POST /api/depot/relever {appliquer} → relève (appliquer : true / false / absent = selon le mode)
  PUT  /api/depot/reglages {entrants, sortants, mode, periode_min}
"""

from flask import Blueprint, current_app, jsonify, request

from services import depot

bp = Blueprint("depot", __name__)


def _profil():
    return current_app.config.get("SEQ_PROFIL", "complet")


@bp.route("/api/depot/etat", methods=["GET"])
def api_etat():
    return jsonify(depot.etat(current_app.json_store, _profil()))


@bp.route("/api/depot/relever", methods=["POST"])
def api_relever():
    b = request.get_json(silent=True) or {}
    a = b.get("appliquer")
    return jsonify(depot.relever(current_app.json_store, _profil(),
                                 None if a is None else bool(a)))


@bp.route("/api/depot/reglages", methods=["PUT"])
def api_reglages():
    store = current_app.json_store
    try:
        with store._conn() as conn:
            return jsonify(depot.definir(conn, store.data_dir, request.get_json(silent=True) or {}))
    except depot.DepotErreur as e:
        return jsonify({"error": str(e), "code": e.code}), 400
