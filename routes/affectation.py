"""routes/affectation.py — v0.19.1.19

API de l'affectation des séances (mises en route / automatismes). Gère le mode,
les affectations par créneau, le motif de répartition, les exceptions, et
l'endpoint composé « planning affecté » (projection + affectation).
"""

from flask import Blueprint, jsonify, request, current_app

from services import affectation as svc
from services.affectation import AffectationErreur
from services import edt as edt_svc
from services import grille_horaire as gh_svc
from services import projection_seances as proj
from services import indisponibilites as ind_svc
from services import calendrier_scolaire as cal
from services import annees_scolaires

bp = Blueprint("affectation", __name__)


def _store():
    return current_app.json_store


def _annee():
    return request.args.get("annee") or annees_scolaires.courante()


def _erreur(e: AffectationErreur):
    return jsonify({"error": str(e), "code": e.code, **e.details}), 400


# ── Mode ─────────────────────────────────────────────────────────────────────

@bp.route("/api/classes/<classe_id>/affectation-config", methods=["GET"])
def api_lire_config(classe_id):
    annee = _annee()
    with _store()._conn() as conn:
        mode = svc.lire_mode(conn, classe_id, annee)
        motif = svc.lire_motif(conn, classe_id, annee)
    return jsonify({"classe_id": classe_id, "annee": annee, "mode": mode,
                    "motif": motif, "modes": list(svc.MODES),
                    "reserves": list(svc.RESERVES)})


@bp.route("/api/classes/<classe_id>/affectation-config", methods=["PUT"])
def api_definir_config(classe_id):
    body = request.get_json() or {}
    annee = body.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            mode = svc.definir_mode(conn, classe_id, annee,
                                    body.get("mode", "par_seance"))
        return jsonify({"classe_id": classe_id, "annee": annee, "mode": mode})
    except AffectationErreur as e:
        return _erreur(e)


# ── Affectations par créneau (mode par_seance) ───────────────────────────────

@bp.route("/api/classes/<classe_id>/affectations", methods=["GET"])
def api_lire_affectations(classe_id):
    annee = _annee()
    with _store()._conn() as conn:
        aff = svc.lire_affectations(conn, classe_id, annee)
    return jsonify({"classe_id": classe_id, "annee": annee,
                    "affectations": aff})


@bp.route("/api/classes/<classe_id>/affectations", methods=["PUT"])
def api_definir_affectations(classe_id):
    body = request.get_json() or {}
    annee = body.get("annee") or annees_scolaires.courante()
    items = body.get("items", [])
    try:
        with _store()._conn() as conn:
            n = svc.definir_affectations(conn, classe_id, annee, items)
        return jsonify({"classe_id": classe_id, "annee": annee, "traites": n})
    except AffectationErreur as e:
        return _erreur(e)


# ── Motif de répartition (mode par_repartition) ──────────────────────────────

@bp.route("/api/classes/<classe_id>/repartition", methods=["PUT"])
def api_definir_motif(classe_id):
    body = request.get_json() or {}
    annee = body.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            motif = svc.definir_motif(conn, classe_id, annee,
                                      body.get("motif", []))
        return jsonify({"classe_id": classe_id, "annee": annee, "motif": motif})
    except AffectationErreur as e:
        return _erreur(e)


# ── Exceptions ───────────────────────────────────────────────────────────────

@bp.route("/api/classes/<classe_id>/affectation-exceptions", methods=["GET"])
def api_lister_exceptions(classe_id):
    annee = _annee()
    with _store()._conn() as conn:
        items = svc.lister_exceptions(conn, classe_id, annee)
    return jsonify({"classe_id": classe_id, "annee": annee, "exceptions": items})


@bp.route("/api/classes/<classe_id>/affectation-exceptions", methods=["POST"])
def api_ajouter_exception(classe_id):
    body = request.get_json() or {}
    annee = body.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            item = svc.ajouter_exception(conn, classe_id, annee,
                                         body.get("date", ""),
                                         body.get("motif", ""))
        return jsonify(item), 201
    except AffectationErreur as e:
        return _erreur(e)


@bp.route("/api/affectation-exceptions/<exception_id>", methods=["DELETE"])
def api_supprimer_exception(exception_id):
    with _store()._conn() as conn:
        svc.supprimer_exception(conn, exception_id)
    return jsonify({"ok": True})


# ── Planning affecté (composition projection + affectation) ──────────────────

@bp.route("/api/classes/<classe_id>/planning-affecte", methods=["GET"])
def api_planning_affecte(classe_id):
    annee = _annee()
    store = _store()
    with store._conn() as conn:
        row = conn.execute(
            "SELECT c.etablissement_id AS eid, e.academie AS academie "
            "FROM classes c LEFT JOIN etablissements e "
            "ON e.id = c.etablissement_id WHERE c.id=?",
            (classe_id,)).fetchone()
        if row is None:
            return jsonify({"error": "classe introuvable"}), 404
        etab_id = row["eid"]
        academie = row["academie"] or ""
        toutes = edt_svc.lister(conn, annee, classe_id=classe_id)
        edt_comptees = [c for c in toutes
                        if edt_svc.est_compte(c)]
        grille = gh_svc.lister(conn, etab_id) if etab_id else []
        indispos = ind_svc.lister(conn, annee, etablissement_id=etab_id) if etab_id else []
        mode = svc.lire_mode(conn, classe_id, annee)
        aff_par_edt = svc.lire_affectations(conn, classe_id, annee)
        motif = svc.lire_motif(conn, classe_id, annee)
        exceptions = svc.dates_exceptions(conn, classe_id, annee)

    # Vacances + fériés (réseau/cache hors _conn).
    vacances = []
    feries = {}
    zone = cal.zone_academie(academie) if academie else None
    if zone:
        try:
            vacances = cal.vacances(annee, zone, store, academie=academie)
        except Exception:
            vacances = []
    try:
        feries = cal.jours_feries_annee_scolaire(annee, store)
    except Exception:
        feries = {}
    d = int(annee.split("-")[0])
    date_min = f"{d}-09-01"

    seances = proj.projeter(annee, edt_comptees, grille, vacances, feries,
                            date_min=date_min, indisponibilites=indispos,
                            classe_id=classe_id)
    affectees = svc.affecter(seances, mode,
                             affectations_par_edt=aff_par_edt,
                             motif=motif, exceptions=exceptions)
    return jsonify({
        "classe_id": classe_id, "annee": annee, "mode": mode,
        "nb_seances": len(affectees), "seances": affectees,
    })
