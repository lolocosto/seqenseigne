"""routes/plans_classe.py — v0.39.0

API des plans de classe hebdomadaires (services/plans_classe.py) et de leur
impression (v0.50.1 : HTML + SVG, services/impression.plan_svg ; le rendu
LaTeX/TikZ a été retiré en v0.50.2).
"""

from datetime import date

from flask import Blueprint, jsonify, request, current_app, render_template

from services import plans_classe as svc
from services.plans_classe import PlanErreur
from services.salles import SalleErreur

bp = Blueprint("plans_classe", __name__)


def _store():
    return current_app.json_store


def _erreur(e):
    code = getattr(e, "code", "donnees_invalides")
    statut = 404 if code in ("introuvable", "salle_introuvable",
                             "version_introuvable") else 400
    return jsonify({"error": str(e), "code": code}), statut


def _args():
    a = request.args if request.method in ("GET", "DELETE") else (request.get_json() or {})
    return a.get("classe_id", ""), a.get("salle_id", ""), a.get("lundi") or date.today().isoformat()


@bp.route("/api/plans-classe/salles", methods=["GET"])
def api_salles():
    classe_id, _, lundi = _args()
    try:
        with _store()._conn() as conn:
            lundi = svc.lundi_iso(lundi)
            salles = svc.salles_de_la_semaine(conn, classe_id, lundi)
        return jsonify({"classe_id": classe_id, "lundi": lundi, "salles": salles,
                        "semaine_courante": svc.lundi_iso(date.today())})
    except (PlanErreur, SalleErreur) as e:
        return _erreur(e)


@bp.route("/api/plans-classe", methods=["GET"])
def api_lire():
    classe_id, salle_id, lundi = _args()
    try:
        with _store()._conn() as conn:
            return jsonify(svc.lire(conn, classe_id, salle_id, lundi, date.today()))
    except (PlanErreur, SalleErreur) as e:
        return _erreur(e)


@bp.route("/api/plans-classe", methods=["PUT"])
def api_enregistrer():
    body = request.get_json() or {}
    classe_id, salle_id, lundi = _args()
    try:
        with _store()._conn() as conn:
            return jsonify(svc.enregistrer(conn, classe_id, salle_id, lundi,
                                           body.get("placements"), date.today(),
                                           reservations=body.get("reservations")))
    except (PlanErreur, SalleErreur) as e:
        return _erreur(e)


@bp.route("/api/plans-classe", methods=["DELETE"])
def api_reinitialiser():
    classe_id, salle_id, lundi = _args()
    try:
        with _store()._conn() as conn:
            return jsonify(svc.reinitialiser(conn, classe_id, salle_id, lundi,
                                             date.today()))
    except (PlanErreur, SalleErreur) as e:
        return _erreur(e)


@bp.route("/api/plans-classe/aleatoire", methods=["POST"])
def api_aleatoire():
    """Placement aléatoire ; `mode` = 'pur' (défaut) ou 'mixte' (v0.40.0 :
    maximise les paires garçon-fille voisines). Places AESH jamais touchées."""
    classe_id, salle_id, lundi = _args()
    mode = (request.get_json() or {}).get("mode", "pur")
    try:
        with _store()._conn() as conn:
            plan = svc.lire(conn, classe_id, salle_id, lundi, date.today())
            numeros = [p["numero"] for p in plan["places"]]
            if mode == "mixte":
                nouveaux = svc.aleatoire_mixte(
                    plan["placements"], numeros,
                    {e["id"]: e.get("sexe") or "" for e in plan["eleves"]},
                    plan["voisins"], reservees=plan["reservations"])
            else:
                nouveaux = svc.aleatoire(plan["placements"], numeros,
                                         [e["id"] for e in plan["eleves"]],
                                         reservees=plan["reservations"])
            return jsonify(svc.enregistrer(conn, classe_id, salle_id, lundi,
                                           nouveaux, date.today()))
    except (PlanErreur, SalleErreur) as e:
        return _erreur(e)


def _plans_a_imprimer():
    """Plans de la semaine : une classe (classe_id) ou toutes les classes qui
    ont cours dans la salle cette semaine-là."""
    classe_id, salle_id, lundi = _args()
    with _store()._conn() as conn:
        if classe_id:
            plans = [svc.lire(conn, classe_id, salle_id, lundi, date.today())]
        else:
            plans = svc.plans_de_la_salle(conn, salle_id, lundi, date.today())
    return plans, svc.lundi_iso(lundi)


@bp.route("/impression/plans-classe", methods=["GET"])
def impression_plans():
    """v0.50.1 — Plans de classe imprimables (HTML + SVG, une page A4 par
    plan), imprimés ou enregistrés en PDF par le navigateur, sans LaTeX."""
    from services.impression import plan_svg, _date_fr
    try:
        plans, lundi = _plans_a_imprimer()
    except (PlanErreur, SalleErreur) as e:
        return _erreur(e)
    return render_template("impression/plans_classe.html",
                           pages=[plan_svg(p) for p in plans],
                           semaine=_date_fr(lundi))
