"""routes/v2_lecture.py — R4e1.

Blueprint pour la lecture seule du modèle v2.

Une seule route pour l'instant :
    GET /api/v2/sequences-par-niveau/<niveau>/<sequence_code>

Pas de POST/PUT/DELETE : la mutation du modèle v2 arrivera en R4e2+.
"""

from __future__ import annotations
from flask import Blueprint, jsonify, current_app

from services.v2_lecture import (
    lire_sequence_par_niveau,
    SequenceParNiveauIntrouvable,
    V2LectureErreur,
)


bp_v2_lecture = Blueprint("v2_lecture", __name__)


@bp_v2_lecture.route(
    "/api/v2/sequences-par-niveau/<niveau>/<sequence_code>",
    methods=["GET"],
)
def api_lire_sequence_par_niveau(niveau: str, sequence_code: str):
    """Lit la structure v2 complète d'une (niveau, sequence_code).

    Retourne 200 + JSON hiérarchique en cas de succès.
    Retourne 404 avec code=sequence_par_niveau_introuvable si la séquence
    n'a pas encore été peuplée dans le modèle v2 (cas typique : N09 non migré,
    ou peuplement non exécuté sur une base fraîche).
    """
    store = current_app.json_store
    try:
        with store._conn() as conn:
            data = lire_sequence_par_niveau(conn, niveau, sequence_code)
    except SequenceParNiveauIntrouvable as e:
        return jsonify({
            "error": str(e),
            "code":  e.code,
            "niveau": e.niveau,
            "sequence_code": e.sequence_code,
        }), 404
    except V2LectureErreur as e:
        # Défensif : si d'autres sous-classes d'erreur apparaissent plus tard,
        # on renvoie 400 par défaut (la route reste strictement read-only).
        return jsonify({"error": str(e), "code": e.code}), 400

    return jsonify(data)
