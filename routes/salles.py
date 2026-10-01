"""routes/salles.py — v0.37.0

API REST des salles d'un établissement et de leurs plans versionnés
(cf. services/salles.py).
"""

from datetime import date

from flask import Blueprint, jsonify, request, current_app

from services import salles as svc
from services.salles import SalleErreur

bp = Blueprint("salles", __name__)


def _store():
    return current_app.json_store


def _erreur(e: SalleErreur):
    statut = 404 if e.code in ("salle_introuvable", "version_introuvable") else 400
    return jsonify({"error": str(e), "code": e.code, **e.details}), statut


@bp.route("/api/etablissements/<etab_id>/salles", methods=["GET"])
def api_lister(etab_id: str):
    with _store()._conn() as conn:
        items = svc.lister(conn, etab_id, date.today())
    return jsonify({"etablissement_id": etab_id, "salles": items})


@bp.route("/api/etablissements/<etab_id>/salles", methods=["POST"])
def api_creer(etab_id: str):
    body = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            item = svc.creer(conn, etab_id, body.get("nom", ""), date.today())
        return jsonify(item), 201
    except SalleErreur as e:
        return _erreur(e)


@bp.route("/api/salles/<salle_id>", methods=["PUT"])
def api_modifier(salle_id: str):
    body = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            item = svc.modifier(conn, salle_id, body, date.today())
        return jsonify(item)
    except SalleErreur as e:
        return _erreur(e)


@bp.route("/api/salles/<salle_id>", methods=["DELETE"])
def api_supprimer(salle_id: str):
    try:
        with _store()._conn() as conn:
            svc.supprimer(conn, salle_id)
        return jsonify({"ok": True})
    except SalleErreur as e:
        return _erreur(e)


@bp.route("/api/salles/<salle_id>/versions", methods=["GET"])
def api_versions(salle_id: str):
    try:
        with _store()._conn() as conn:
            items = svc.lister_versions(conn, salle_id, date.today())
        return jsonify({"salle_id": salle_id, "versions": items})
    except SalleErreur as e:
        return _erreur(e)


@bp.route("/api/salles/<salle_id>/plan", methods=["GET"])
def api_plan(salle_id: str):
    try:
        with _store()._conn() as conn:
            plan = svc.lire_plan(conn, salle_id, date.today(),
                                 version_id=request.args.get("version_id"))
        return jsonify(plan)
    except SalleErreur as e:
        return _erreur(e)


@bp.route("/api/salles/<salle_id>/plan", methods=["PUT"])
def api_enregistrer_plan(salle_id: str):
    body = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            plan = svc.enregistrer_plan(
                conn, salle_id, body.get("places"), date.today(),
                version_id=body.get("version_id") or None,
                date_effet=body.get("date_effet") or None)
        return jsonify(plan)
    except SalleErreur as e:
        return _erreur(e)


@bp.route("/api/salles/versions/<version_id>", methods=["DELETE"])
def api_supprimer_version(version_id: str):
    try:
        with _store()._conn() as conn:
            svc.supprimer_version(conn, version_id, date.today())
        return jsonify({"ok": True})
    except SalleErreur as e:
        return _erreur(e)
