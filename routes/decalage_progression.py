"""routes/decalage_progression.py — v0.21.4

API REST des décalages de progression par classe.
"""

from flask import Blueprint, jsonify, request, current_app

from services import decalage_progression as svc
from services.decalage_progression import DecalageErreur
from services import annees_scolaires

bp = Blueprint("decalage_progression", __name__)


def _store():
    return current_app.json_store


def _annee():
    return request.args.get("annee") or annees_scolaires.courante()


def _erreur(e: DecalageErreur):
    return jsonify({"error": str(e), "code": e.code, **e.details}), 400


@bp.route("/api/classes/<classe_id>/decalages-progression", methods=["GET"])
def api_lister(classe_id):
    annee = _annee()
    with _store()._conn() as conn:
        items = svc.lister(conn, classe_id, annee)
    return jsonify({"classe_id": classe_id, "annee": annee, "decalages": items})


@bp.route("/api/classes/<classe_id>/decalages-progression", methods=["POST"])
def api_creer(classe_id):
    body = request.get_json() or {}
    annee = body.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            item = svc.creer(
                conn, classe_id, annee,
                a_partir_de=body.get("a_partir_de", ""),
                nb_semaines=body.get("nb_semaines", 1),
                motif=body.get("motif", ""),
                indispo_id=body.get("indispo_id"),
            )
        return jsonify(item), 201
    except DecalageErreur as e:
        return _erreur(e)


@bp.route("/api/decalages-progression/<did>", methods=["PUT"])
def api_modifier(did):
    body = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            item = svc.modifier(conn, did, body)
        return jsonify(item)
    except DecalageErreur as e:
        return _erreur(e)


@bp.route("/api/decalages-progression/<did>", methods=["DELETE"])
def api_supprimer(did):
    try:
        with _store()._conn() as conn:
            svc.supprimer(conn, did)
        return jsonify({"ok": True})
    except DecalageErreur as e:
        return _erreur(e)


@bp.route("/api/classes/<classe_id>/progression-realisee", methods=["GET"])
def api_progression_realisee(classe_id):
    """Créneaux de la progression de la classe, DÉCALÉS côté serveur selon les
    décalages (semaines neutralisées) + la liste des semaines neutralisées et
    leur motif. Le client se contente d'afficher : aucun calcul métier en JS.
    """
    from services import calendrier_scolaire as cal
    annee = _annee()
    store = _store()
    with store._conn() as conn:
        row = conn.execute(
            "SELECT c.niveau AS niveau, c.etablissement_id AS eid, "
            "e.academie AS aca FROM classes c LEFT JOIN etablissements e "
            "ON e.id=c.etablissement_id WHERE c.id=?", (classe_id,)).fetchone()
        if row is None:
            return jsonify({"error": "classe introuvable"}), 404
        decalages = svc.lister(conn, classe_id, annee)
    # La progression principale est identifiée par (niveau, année,
    # établissement) — pas par classe.progression_id (obsolète).
    prog = store.lire_progression_par_triplet(row["niveau"], annee, row["eid"]) \
        if row["eid"] else None
    creneaux = (prog or {}).get("creneaux", []) if prog else []
    pid = (prog or {}).get("id") if prog else None

    # Vacances de l'année (pour le calcul des semaines de cours).
    academie = row["aca"] or ""
    vacances = []
    zone = cal.zone_academie(academie) if academie else None
    if zone:
        try:
            vacances = cal.vacances(annee, zone, store, academie=academie)
        except Exception:
            vacances = []

    res = svc.calculer_pour_classe(creneaux, decalages, annee, vacances)
    return jsonify({"classe_id": classe_id, "annee": annee,
                    "progression_id": pid, **res})
