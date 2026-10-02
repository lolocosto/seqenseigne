"""routes/seance.py — v0.43.0

API du début de séance (services/seance.py).
"""

from datetime import datetime

from flask import Blueprint, jsonify, request, current_app

from services import seance as svc
from services import annees_scolaires
from services.seance import SeanceErreur

bp = Blueprint("seance", __name__)


def _store():
    return current_app.json_store


def _erreur(e: SeanceErreur):
    return jsonify({"error": str(e), "code": e.code}), (404 if e.code == "introuvable" else 400)


def _maintenant() -> datetime:
    return datetime.now()


@bp.route("/api/seance/en-cours", methods=["GET"])
def api_en_cours():
    """Séance en cours (ou prochaine, ou dernière) du jour ; `classe_id`
    facultatif (sinon toutes les classes de l'année)."""
    annee = request.args.get("annee") or annees_scolaires.courante()
    with _store()._conn() as conn:
        s = svc.seance_en_cours(conn, _store(), annee, _maintenant(),
                                request.args.get("classe_id") or None)
    return jsonify({"seance": s})


@bp.route("/api/seance/jour", methods=["GET"])
def api_jour():
    """Séances d'une classe un jour donné (pour choisir après coup)."""
    from datetime import date
    a = request.args
    annee = a.get("annee") or annees_scolaires.courante()
    try:
        jour = date.fromisoformat(a.get("date", ""))
    except ValueError:
        return jsonify({"error": "date invalide"}), 400
    with _store()._conn() as conn:
        liste = svc.seances_du_jour(conn, _store(), annee, jour,
                                    a.get("classe_id") or None)
    for x in liste:
        x["statut"] = svc.statut(x, _maintenant())
    return jsonify({"seances": liste})


@bp.route("/api/seance", methods=["GET"])
def api_lire():
    a = request.args
    annee = a.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            return jsonify(svc.lire(conn, _store(), annee, a.get("classe_id", ""),
                                    a.get("date", ""), a.get("creneau", ""),
                                    _maintenant()))
    except SeanceErreur as e:
        return _erreur(e)


@bp.route("/api/seance/absence", methods=["PUT"])
def api_absence():
    b = request.get_json() or {}
    annee = b.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            liste = svc.definir_absence(conn, _store(), annee, b.get("classe_id", ""),
                                        b.get("eleve_id", ""), b.get("date", ""),
                                        b.get("creneau", ""), bool(b.get("absent")))
        return jsonify({"absents": liste})
    except SeanceErreur as e:
        return _erreur(e)
