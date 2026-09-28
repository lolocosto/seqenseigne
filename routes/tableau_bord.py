"""routes/tableau_bord.py — v0.30.0

API du tableau de bord (écran d'accueil). Chaque endpoint alimente une tuile.
"""

from flask import Blueprint, jsonify, request, current_app

from services import tableau_bord as tb
from services import annees_scolaires

bp = Blueprint("tableau_bord", __name__)


def _store():
    return current_app.json_store


@bp.route("/api/tableau-bord/atomes-en-cours", methods=["GET"])
def api_atomes_en_cours():
    with _store()._conn() as conn:
        data = tb.atomes_en_cours_par_niveau(conn)
    return jsonify({"niveaux": data})


@bp.route("/api/tableau-bord/atomes-non-rattaches", methods=["GET"])
def api_atomes_non_rattaches():
    with _store()._conn() as conn:
        data = tb.atomes_non_rattaches_par_niveau(conn)
    return jsonify({"niveaux": data})


@bp.route("/api/tableau-bord/seances-semaine", methods=["GET"])
def api_seances_semaine():
    annee = request.args.get("annee") or annees_scolaires.courante()
    store = _store()
    with store._conn() as conn:
        data = tb.seances_de_la_semaine(conn, store, annee)
    return jsonify(data)
