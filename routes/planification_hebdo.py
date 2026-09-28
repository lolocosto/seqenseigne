"""routes/planification_hebdo.py — v0.32.0

API de la vue « Planification hebdo » : grille d'une semaine + détail d'une
séance.
"""

from flask import Blueprint, jsonify, request, current_app

from services import planification_hebdo as ph
from services import annees_scolaires

bp = Blueprint("planification_hebdo", __name__)


def _store():
    return current_app.json_store


def _annee():
    return request.args.get("annee") or annees_scolaires.courante()


@bp.route("/api/planification-hebdo", methods=["GET"])
def api_grille():
    annee = _annee()
    lundi = request.args.get("lundi")  # ISO ; absent = semaine courante
    etab = request.args.get("etablissement_id")
    store = _store()
    with store._conn() as conn:
        data = ph.grille_semaine(conn, store, annee, lundi,
                                 etablissement_id=etab)
    return jsonify(data)


@bp.route("/api/planification-hebdo/seance", methods=["GET"])
def api_detail_seance():
    annee = _annee()
    classe_id = request.args.get("classe_id", "")
    date_iso = request.args.get("date", "")
    creneau = request.args.get("creneau", "")
    if not classe_id or not date_iso:
        return jsonify({"error": "classe_id et date requis"}), 400
    store = _store()
    with store._conn() as conn:
        data = ph.detail_seance(conn, store, annee, classe_id, date_iso, creneau)
    return jsonify(data)
