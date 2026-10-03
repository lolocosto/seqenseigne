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


@bp.route("/api/seance/mer-non-faite", methods=["PUT"])
def api_mer_non_faite():
    """v0.43.2 — Mise en route non faite (case + commentaire facultatif)."""
    b = request.get_json() or {}
    annee = b.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            return jsonify(svc.marquer_mer_non_faite(
                conn, _store(), annee, b.get("classe_id", ""), b.get("date", ""),
                b.get("creneau", ""), bool(b.get("non_faite")),
                b.get("commentaire", "")))
    except SeanceErreur as e:
        return _erreur(e)


# ── v0.44.0 — Documents ──────────────────────────────────────────────────────

def _docs():
    from services import documents_seance
    return documents_seance


@bp.route("/api/seance/document", methods=["POST"])
def api_document_ajouter():
    """Document ajouté à la volée : pour cette séance (`pour`='cette') ou pour
    la séance suivante de la classe (`pour`='prochaine')."""
    b = request.get_json() or {}
    annee = b.get("annee") or annees_scolaires.courante()
    docs = _docs()
    try:
        with _store()._conn() as conn:
            svc._seance(conn, _store(), annee, b.get("classe_id", ""), b.get("date", ""),
                        b.get("creneau", ""))
            cible = {"date": b.get("date"), "creneau": b.get("creneau")}
            if b.get("pour") == "prochaine":
                cible = svc.seance_suivante(conn, _store(), annee, b.get("classe_id", ""),
                                            b.get("date", ""), b.get("creneau", ""))
                if cible is None:
                    return jsonify({"error": "Pas de séance suivante cette année."}), 400
            d = docs.ajouter_ponctuel(conn, annee, b.get("classe_id", ""),
                                      b.get("libelle", ""), b.get("categorie", "pedagogique"),
                                      cible["date"], cible["creneau"])
        return jsonify(d), 201
    except (SeanceErreur, docs.DocumentErreur) as e:
        return _erreur(e)


@bp.route("/api/seance/document/<document_id>", methods=["DELETE"])
def api_document_supprimer(document_id):
    docs = _docs()
    try:
        with _store()._conn() as conn:
            docs.supprimer_ponctuel(conn, document_id)
        return jsonify({"ok": True})
    except docs.DocumentErreur as e:
        return _erreur(e)


@bp.route("/api/seance/document/<document_id>/distribue", methods=["PUT"])
def api_document_distribue(document_id):
    b = request.get_json() or {}
    docs = _docs()
    try:
        with _store()._conn() as conn:
            docs.marquer_distribue(conn, document_id, b.get("date", ""),
                                   b.get("creneau", ""), bool(b.get("distribue")))
        return jsonify({"ok": True})
    except docs.DocumentErreur as e:
        return _erreur(e)


@bp.route("/api/seance/document/<document_id>/donne", methods=["PUT"])
def api_document_donne(document_id):
    b = request.get_json() or {}
    docs = _docs()
    try:
        with _store()._conn() as conn:
            docs.marquer_donne(conn, document_id, b.get("eleve_id", ""), b.get("date", ""),
                               b.get("creneau", ""), bool(b.get("donne")))
        return jsonify({"ok": True})
    except docs.DocumentErreur as e:
        return _erreur(e)
