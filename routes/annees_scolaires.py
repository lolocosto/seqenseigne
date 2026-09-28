"""
routes/annees_scolaires.py — API REST pour la liste des années scolaires.

Endpoints :
  GET /api/annees-scolaires → { annee_courante, annees_scolaires: [...] }
"""

from flask import Blueprint, jsonify
from services import annees_scolaires as svc

bp = Blueprint("annees_scolaires", __name__)


@bp.route("/api/annees-scolaires", methods=["GET"])
def api_lister():
    return jsonify({
        "annee_courante":    svc.courante(),
        "annees_scolaires":  svc.lister(),
    })
