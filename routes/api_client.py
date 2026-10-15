"""routes/api_client.py — v0.51.16

Atelier : adresse et jeton de l'appli de classe, test, synchronisation.

  GET  /api/api-client/etat
  PUT  /api/api-client/destination {url, jeton}   (jeton vide : inchangé)
  POST /api/api-client/tester
  POST /api/api-client/synchroniser
"""

from flask import Blueprint, current_app, jsonify, request

from services import api_client as ac

bp = Blueprint("api_client", __name__)


def _store():
    return current_app.json_store


@bp.route("/api/api-client/etat", methods=["GET"])
def api_etat():
    with _store()._conn() as conn:
        return jsonify(ac.etat(conn))


@bp.route("/api/api-client/destination", methods=["PUT"])
def api_definir():
    b = request.get_json(silent=True) or {}
    try:
        with _store()._conn() as conn:
            return jsonify(ac.definir(conn, b.get("url"), b.get("jeton") or None))
    except ac.ClientErreur as e:
        return jsonify({"error": str(e), "code": e.code}), 400


@bp.route("/api/api-client/tester", methods=["POST"])
def api_tester():
    return jsonify(ac.tester(_store()))


@bp.route("/api/api-client/synchroniser", methods=["POST"])
def api_synchroniser():
    store = _store()
    res = ac.synchroniser(store, current_app.config.get("SEQ_PROFIL", "atelier"))
    res.pop("releve", None)
    with store._conn() as conn:
        res["etat"] = ac.etat(conn)
    return jsonify(res)
