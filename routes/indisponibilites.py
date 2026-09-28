"""routes/indisponibilites.py — v0.21.0

API REST des indisponibilités (périodes où des séances n'ont pas lieu).
"""

from flask import Blueprint, jsonify, request, current_app

from services import indisponibilites as svc
from services.indisponibilites import IndispoErreur
from services import annees_scolaires

bp = Blueprint("indisponibilites", __name__)


def _store():
    return current_app.json_store


def _annee():
    return request.args.get("annee") or annees_scolaires.courante()


def _erreur(e: IndispoErreur):
    return jsonify({"error": str(e), "code": e.code, **e.details}), 400


@bp.route("/api/indisponibilites", methods=["GET"])
def api_lister():
    annee = _annee()
    etab = request.args.get("etablissement_id")
    with _store()._conn() as conn:
        items = svc.lister(conn, annee, etablissement_id=etab)
    return jsonify({"annee": annee, "etablissement_id": etab,
                    "indisponibilites": items,
                    "types": list(svc.TYPES), "portees": list(svc.PORTEES)})


@bp.route("/api/indisponibilites", methods=["POST"])
def api_creer():
    body = request.get_json() or {}
    annee = body.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            item = svc.creer(
                conn, annee, body.get("etablissement_id", ""),
                type=body.get("type", "journees"),
                date_debut=body.get("date_debut", ""),
                date_fin=body.get("date_fin", ""),
                creneau_debut=body.get("creneau_debut", ""),
                creneau_fin=body.get("creneau_fin", ""),
                portee=body.get("portee", "moi"),
                classes_ids=body.get("classes_ids", []),
                motif=body.get("motif", ""),
            )
        return jsonify(item), 201
    except IndispoErreur as e:
        return _erreur(e)


@bp.route("/api/indisponibilites/<iid>", methods=["PUT"])
def api_modifier(iid):
    body = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            item = svc.modifier(conn, iid, body)
        return jsonify(item)
    except IndispoErreur as e:
        return _erreur(e)


@bp.route("/api/indisponibilites/<iid>", methods=["DELETE"])
def api_supprimer(iid):
    try:
        with _store()._conn() as conn:
            svc.supprimer(conn, iid)
        return jsonify({"ok": True})
    except IndispoErreur as e:
        return _erreur(e)
