"""routes/grille_horaire.py — v0.19.1.16

API REST de la grille horaire par établissement (créneaux M1..M4 / S1..S4).
"""

from flask import Blueprint, jsonify, request, current_app

from services import grille_horaire as svc
from services.grille_horaire import GrilleHoraireErreur

bp = Blueprint("grille_horaire", __name__)


def _store():
    return current_app.json_store


def _erreur(e: GrilleHoraireErreur):
    return jsonify({"error": str(e), "code": e.code, **e.details}), 400


@bp.route("/api/etablissements/<etab_id>/grille-horaire", methods=["GET"])
def api_lister(etab_id: str):
    store = _store()
    with store._conn() as conn:
        # Amorçage paresseux : si l'établissement n'a pas encore de créneaux,
        # on lui pose les défauts (utile pour un établissement créé après la
        # migration initiale).
        svc.peupler_defauts_si_vide(conn, etab_id)
        items = svc.lister(conn, etab_id)
    return jsonify({"etablissement_id": etab_id, "creneaux": items})


@bp.route("/api/etablissements/<etab_id>/grille-horaire", methods=["POST"])
def api_creer(etab_id: str):
    body = request.get_json() or {}
    store = _store()
    try:
        with store._conn() as conn:
            item = svc.creer(
                conn, etab_id, body.get("code", ""),
                libelle=body.get("libelle", ""),
                heure_debut=body.get("heure_debut", ""),
                heure_fin=body.get("heure_fin", ""),
                demi_journee=body.get("demi_journee", "M"),
                ordre=body.get("ordre"),
            )
        return jsonify(item), 201
    except GrilleHoraireErreur as e:
        return _erreur(e)


@bp.route("/api/grille-horaire/<creneau_id>", methods=["PUT"])
def api_modifier(creneau_id: str):
    body = request.get_json() or {}
    store = _store()
    try:
        with store._conn() as conn:
            item = svc.modifier(conn, creneau_id, body)
        return jsonify(item)
    except GrilleHoraireErreur as e:
        return _erreur(e)


@bp.route("/api/grille-horaire/<creneau_id>", methods=["DELETE"])
def api_supprimer(creneau_id: str):
    store = _store()
    try:
        with store._conn() as conn:
            svc.supprimer(conn, creneau_id)
        return jsonify({"ok": True})
    except GrilleHoraireErreur as e:
        return _erreur(e)
