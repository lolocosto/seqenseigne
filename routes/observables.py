"""routes/observables.py — v0.45.0

API des observables de séance (services/observables.py).
"""

from datetime import date

from flask import Blueprint, jsonify, request, current_app

from services import observables as svc
from services import annees_scolaires
from services.observables import ObservableErreur

bp = Blueprint("observables", __name__)


def _store():
    return current_app.json_store


def _erreur(e):
    return jsonify({"error": str(e), "code": e.code}), (404 if e.code == "introuvable" else 400)


def _ok(fn):
    try:
        with _store()._conn() as conn:
            return fn(conn)
    except ObservableErreur as e:
        return _erreur(e)


@bp.route("/api/observables", methods=["GET"])
def api_lister():
    niveau = request.args.get("niveau", "")
    annee = request.args.get("annee") or annees_scolaires.courante()
    return _ok(lambda c: jsonify({
        "niveau": niveau,
        "observables": svc.lister(c, niveau),
        "eleves": svc.eleves_du_niveau(c, niveau, annee),
        "eleves_avec_exceptions": svc.eleves_avec_exceptions(c, niveau),
    }))


@bp.route("/api/observables", methods=["POST"])
def api_creer():
    b = request.get_json() or {}
    return _ok(lambda c: (jsonify(svc.creer(c, b.get("niveau", ""), b.get("section", ""),
                                            b.get("libelle", ""))), 201))


@bp.route("/api/observables/<obs_id>", methods=["PUT"])
def api_modifier(obs_id):
    b = request.get_json() or {}
    return _ok(lambda c: jsonify(svc.modifier(c, obs_id, b)))


@bp.route("/api/observables/<obs_id>/deplacer", methods=["POST"])
def api_deplacer(obs_id):
    sens = int((request.get_json() or {}).get("sens", 1))
    return _ok(lambda c: (svc.deplacer(c, obs_id, sens), jsonify({"ok": True}))[1])


@bp.route("/api/observables/copier", methods=["POST"])
def api_copier():
    b = request.get_json() or {}
    return _ok(lambda c: jsonify({"copies": svc.copier_depuis(
        c, b.get("source", ""), b.get("cible", ""))}))


@bp.route("/api/observables/<obs_id>/exceptions", methods=["GET"])
def api_exceptions(obs_id):
    return _ok(lambda c: jsonify({"exceptions": svc.lister_exceptions(c, obs_id)}))


@bp.route("/api/observables/<obs_id>/exceptions", methods=["POST"])
def api_ajouter_exception(obs_id):
    b = request.get_json() or {}
    return _ok(lambda c: (jsonify(svc.ajouter_exception(
        c, obs_id, b.get("eleve_id", ""), b.get("du", ""), b.get("au", ""),
        b.get("commentaire", ""))), 201))


@bp.route("/api/observables/exceptions/<exc_id>", methods=["PUT"])
def api_modifier_exception(exc_id):
    b = request.get_json() or {}
    return _ok(lambda c: jsonify(svc.modifier_exception(c, exc_id, b)))


@bp.route("/api/observables/exceptions/<exc_id>", methods=["DELETE"])
def api_supprimer_exception(exc_id):
    return _ok(lambda c: (svc.supprimer_exception(c, exc_id), jsonify({"ok": True}))[1])


@bp.route("/api/observables/effectifs", methods=["GET"])
def api_effectifs():
    """Liste effective d'un élève (aperçu ; observation en v0.46)."""
    a = request.args
    jour = a.get("date") or date.today().isoformat()
    return _ok(lambda c: jsonify(svc.liste_effective(c, a.get("niveau", ""),
                                                     a.get("eleve_id", ""), jour)))
