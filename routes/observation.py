"""routes/observation.py — v0.46.0

API de l'observation en séance (services/observation.py).
"""

from flask import Blueprint, jsonify, request, current_app

from services import observation as svc
from services import observables as obs_svc
from services import annees_scolaires
from services.observation import ObservationErreur

bp = Blueprint("observation", __name__)


def _store():
    return current_app.json_store


def _erreur(e):
    return jsonify({"error": str(e), "code": e.code}), (404 if e.code == "introuvable" else 400)


@bp.route("/api/observation", methods=["GET"])
def api_lire():
    a = request.args
    try:
        with _store()._conn() as conn:
            return jsonify(svc.lire(conn, a.get("classe_id", ""), a.get("date", ""),
                                    a.get("creneau", "")))
    except ObservationErreur as e:
        return _erreur(e)


@bp.route("/api/observation/liste", methods=["GET"])
def api_liste_eleve():
    """Observables de l'élève à la date de la séance (liste effective)."""
    a = request.args
    try:
        with _store()._conn() as conn:
            niveau = svc._niveau(conn, a.get("classe_id", ""))
            return jsonify(obs_svc.liste_effective(conn, niveau, a.get("eleve_id", ""),
                                                   a.get("date", "")))
    except ObservationErreur as e:
        return _erreur(e)


@bp.route("/api/observation", methods=["POST"])
def api_ajouter():
    b = request.get_json() or {}
    annee = b.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            return jsonify(svc.ajouter(conn, _store(), annee, b.get("classe_id", ""),
                                       b.get("eleve_id", ""), b.get("date", ""),
                                       b.get("creneau", ""), b.get("observable_id", ""))), 201
    except ObservationErreur as e:
        return _erreur(e)


@bp.route("/api/observation/<occ_id>", methods=["DELETE"])
def api_supprimer(occ_id):
    try:
        with _store()._conn() as conn:
            return jsonify(svc.supprimer(conn, occ_id))
    except ObservationErreur as e:
        return _erreur(e)


@bp.route("/api/observation/annuler-derniere", methods=["POST"])
def api_annuler():
    b = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            return jsonify(svc.annuler_derniere(conn, b.get("classe_id", ""), b.get("date", ""),
                                                b.get("creneau", ""), b.get("eleve_id", "")))
    except ObservationErreur as e:
        return _erreur(e)
