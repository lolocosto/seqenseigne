"""routes/edt.py — v0.19.1.17 (v0.38.0 : EdT versionné)

API REST de l'emploi du temps de l'enseignant (année scolaire courante par
défaut). Les cases d'EDT référencent des créneaux de la grille horaire.
"""

from datetime import date

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


def _date_arg(nom: str):
    v = request.args.get(nom)
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


@bp.route("/api/edt", methods=["GET"])
def api_lister():
    """Cases d'EdT valides la semaine de `semaine_du` (défaut : cette semaine).

    Avec `etablissement_id` : ajoute l'état de l'EdT (en saisie / figé), les
    changements programmés et la première date d'effet possible."""
    annee = _annee()
    classe_id = request.args.get("classe_id")
    etab_id = request.args.get("etablissement_id")
    aujourd_hui = date.today()
    ref = _date_arg("semaine_du") or aujourd_hui
    store = _store()
    with store._conn() as conn:
        items = svc.lister(conn, annee, classe_id=classe_id, a_la_date=ref,
                           etablissement_id=etab_id)
        extra = {}
        if etab_id:
            extra = {
                "etat": svc.etat(conn, annee, etab_id),
                "changements": svc.changements_programmes(conn, annee, etab_id,
                                                          aujourd_hui),
            }
    return jsonify({
        "annee": annee,
        "classe_id": classe_id,
        "semaine_du": svc.lundi_de(ref).isoformat(),
        "semaine_courante": svc.lundi_de(aujourd_hui).isoformat(),
        "date_effet_min": svc.prochain_lundi(aujourd_hui).isoformat(),
        "creneaux": items,
        "groupes": list(svc.GROUPES),
        "groupes_comptes": list(svc.GROUPES_COMPTES),
        "usages": list(svc.USAGES),
        "usages_comptes": list(svc.USAGES_COMPTES),
        "jours": list(svc.JOURS),
        "semaines": list(svc.SEMAINES),
        **extra,
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
                salle_id=body.get("salle_id") or None,
                nb_aesh=body.get("nb_aesh", 0),
                a_partir_du=body.get("a_partir_du") or None,
                aujourd_hui=date.today(),
            )
        return jsonify(item), 201
    except EdtErreur as e:
        return _erreur(e)


@bp.route("/api/edt/<edt_id>", methods=["PUT"])
def api_modifier(edt_id: str):
    body = request.get_json() or {}
    a_partir_du = body.pop("a_partir_du", None) or None
    store = _store()
    try:
        with store._conn() as conn:
            item = svc.modifier(conn, edt_id, body, a_partir_du=a_partir_du,
                                aujourd_hui=date.today())
        return jsonify(item)
    except EdtErreur as e:
        return _erreur(e)


@bp.route("/api/edt/<edt_id>", methods=["DELETE"])
def api_supprimer(edt_id: str):
    store = _store()
    try:
        with store._conn() as conn:
            svc.supprimer(conn, edt_id,
                          a_partir_du=request.args.get("a_partir_du") or None,
                          aujourd_hui=date.today())
        return jsonify({"ok": True})
    except EdtErreur as e:
        return _erreur(e)


@bp.route("/api/edt/figer", methods=["POST"])
def api_figer():
    body = request.get_json() or {}
    annee = body.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            et = svc.figer(conn, annee, body.get("etablissement_id", ""),
                           date.today())
        return jsonify(et)
    except EdtErreur as e:
        return _erreur(e)


@bp.route("/api/edt/changements/<lundi>", methods=["DELETE"])
def api_annuler_changement(lundi: str):
    annee = _annee()
    try:
        with _store()._conn() as conn:
            svc.annuler_changement(conn, annee,
                                   request.args.get("etablissement_id", ""),
                                   lundi, date.today())
        return jsonify({"ok": True})
    except EdtErreur as e:
        return _erreur(e)


@bp.route("/api/edt/appliquer-salle", methods=["POST"])
def api_appliquer_salle():
    body = request.get_json() or {}
    annee = body.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            n = svc.appliquer_salle(conn, annee, body.get("etablissement_id", ""),
                                    body.get("salle_id", ""),
                                    a_partir_du=body.get("a_partir_du") or None,
                                    aujourd_hui=date.today())
        return jsonify({"ok": True, "cases_modifiees": n})
    except EdtErreur as e:
        return _erreur(e)


@bp.route("/api/edt/apercu", methods=["POST"])
def api_apercu():
    """Aperçu de l'effet d'un changement sur le nombre de séances restantes
    de chaque classe (de la date d'effet à la fin de l'année), SANS
    l'enregistrer : l'opération est jouée puis annulée (savepoint).

    Corps : {annee, etablissement_id, operation: ajouter|modifier|supprimer|
             appliquer_salle, edt_id?, champs?, a_partir_du?}"""
    from services import edt_apercu
    body = request.get_json() or {}
    annee = body.get("annee") or annees_scolaires.courante()
    try:
        lignes = edt_apercu.apercu(_store(), annee, body, date.today())
        return jsonify({"classes": lignes})
    except EdtErreur as e:
        return _erreur(e)


@bp.route("/api/classes/<classe_id>/seances-edt", methods=["GET"])
def api_compter_seances(classe_id: str):
    """Comptage des séances/semaine (A/B) dérivé de l'EDT en vigueur cette
    semaine pour une classe."""
    annee = _annee()
    store = _store()
    with store._conn() as conn:
        compte = svc.compter_seances(conn, classe_id, annee, date.today())
    return jsonify({"classe_id": classe_id, "annee": annee, **compte})
