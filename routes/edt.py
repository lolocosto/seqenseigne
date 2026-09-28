"""routes/edt.py — v0.19.1.17

API REST de l'emploi du temps de l'enseignant (année scolaire courante par
défaut). Les cases d'EDT référencent des créneaux de la grille horaire.
"""

from flask import Blueprint, jsonify, request, current_app

from services import edt as svc
from services.edt import EdtErreur
from services import annees_scolaires

bp = Blueprint("edt", __name__)


def _store():
    return current_app.json_store


def _erreur(e: EdtErreur):
    return jsonify({"error": str(e), "code": e.code, **e.details}), 400


def _annee(defaut=None):
    return request.args.get("annee") or defaut or annees_scolaires.courante()


@bp.route("/api/edt", methods=["GET"])
def api_lister():
    annee = _annee()
    classe_id = request.args.get("classe_id")
    store = _store()
    with store._conn() as conn:
        items = svc.lister(conn, annee, classe_id=classe_id)
    return jsonify({
        "annee": annee,
        "classe_id": classe_id,
        "creneaux": items,
        "groupes": list(svc.GROUPES),
        "groupes_comptes": list(svc.GROUPES_COMPTES),
        "usages": list(svc.USAGES),
        "usages_comptes": list(svc.USAGES_COMPTES),
        "jours": list(svc.JOURS),
        "semaines": list(svc.SEMAINES),
    })


@bp.route("/api/edt", methods=["POST"])
def api_ajouter():
    body = request.get_json() or {}
    annee = body.get("annee") or annees_scolaires.courante()
    store = _store()
    try:
        with store._conn() as conn:
            item = svc.ajouter(
                conn, annee, body.get("jour", ""), body.get("creneau_code", ""),
                body.get("etablissement_id", ""),
                semaine=body.get("semaine", "AB"),
                classe_id=body.get("classe_id"),
                libelle=body.get("libelle", ""),
                groupe=body.get("groupe", "classe_entiere"),
                usage=body.get("usage", "cours"),
                ordre=body.get("ordre"),
            )
        return jsonify(item), 201
    except EdtErreur as e:
        return _erreur(e)


@bp.route("/api/edt/<edt_id>", methods=["PUT"])
def api_modifier(edt_id: str):
    body = request.get_json() or {}
    store = _store()
    try:
        with store._conn() as conn:
            item = svc.modifier(conn, edt_id, body)
        return jsonify(item)
    except EdtErreur as e:
        return _erreur(e)


@bp.route("/api/edt/<edt_id>", methods=["DELETE"])
def api_supprimer(edt_id: str):
    store = _store()
    try:
        with store._conn() as conn:
            svc.supprimer(conn, edt_id)
        return jsonify({"ok": True})
    except EdtErreur as e:
        return _erreur(e)


@bp.route("/api/classes/<classe_id>/seances-edt", methods=["GET"])
def api_compter_seances(classe_id: str):
    """Comptage des séances/semaine (A/B) dérivé de l'EDT pour une classe."""
    annee = _annee()
    store = _store()
    with store._conn() as conn:
        compte = svc.compter_seances(conn, classe_id, annee)
    return jsonify({"classe_id": classe_id, "annee": annee, **compte})
