"""
routes/calendrier.py — API REST du calendrier scolaire.

Endpoints :
  GET /api/calendrier/vacances?annee=2021-2022&academie=Rennes
  GET /api/calendrier/vacances?annee=2021-2022&zone=B
  GET /api/calendrier/jours-feries?annee=2024
  GET /api/calendrier/jours-feries?annee_scolaire=2021-2022
"""

from flask import Blueprint, request, jsonify, current_app
from services import calendrier_scolaire as svc_cal

bp = Blueprint("calendrier", __name__)


def _store():
    return current_app.json_store


@bp.route("/api/calendrier/vacances", methods=["GET"])
def api_vacances():
    annee    = request.args.get("annee", "").strip()
    academie = request.args.get("academie", "").strip()
    zone     = request.args.get("zone", "").strip()
    force    = request.args.get("force", "").strip() == "1"

    if not annee:
        return jsonify({"error": "annee requise (ex: 2021-2022)"}), 400

    # Résoudre la zone depuis l'académie si pas fournie directement
    if not zone:
        if not academie:
            return jsonify({
                "error": "zone ou academie requise",
                "hint":  "Renseignez l'académie de l'établissement dans "
                         "Gestion des classes pour voir les vacances.",
            }), 400
        zone = svc_cal.zone_academie(academie)
        if not zone:
            return jsonify({
                "error": f"Académie inconnue : '{academie}'",
                "academies_connues": sorted(svc_cal.ACADEMIE_ZONE.keys()),
            }), 400

    try:
        data = svc_cal.vacances(annee, zone, _store(),
                                force_refresh=force,
                                academie=academie or None)
    except Exception as e:
        return jsonify({
            "error": f"Impossible de récupérer les vacances : {e}",
            "zone":  zone,
            "annee": annee,
        }), 502

    return jsonify({
        "annee":    annee,
        "zone":     zone,
        "academie": academie,
        "vacances": data,
    })


@bp.route("/api/calendrier/jours-feries", methods=["GET"])
def api_jours_feries():
    annee_scolaire = request.args.get("annee_scolaire", "").strip()
    annee_civile   = request.args.get("annee", "").strip()
    force          = request.args.get("force", "").strip() == "1"

    if annee_scolaire:
        try:
            data = svc_cal.jours_feries_annee_scolaire(annee_scolaire, _store())
        except Exception as e:
            return jsonify({"error": f"API jours fériés indisponible : {e}"}), 502
        return jsonify({"annee_scolaire": annee_scolaire, "feries": data})

    if annee_civile:
        try:
            annee_int = int(annee_civile)
        except ValueError:
            return jsonify({"error": "annee doit être un entier"}), 400
        try:
            data = svc_cal.jours_feries(annee_int, _store(), force_refresh=force)
        except Exception as e:
            return jsonify({"error": f"API jours fériés indisponible : {e}"}), 502
        return jsonify({"annee": annee_int, "feries": data})

    return jsonify({"error": "annee ou annee_scolaire requis"}), 400
