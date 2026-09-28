"""routes/paquet.py — Exposition de paquet_definitions vers le frontend.

Route unique : GET /api/paquet/definitions
Utilisée par l'onglet « Tout le paquet » de l'éditeur LaTeX (v0.13.7.1+).
"""

from flask import Blueprint, jsonify, current_app, request
from services.paquet_expose import lister_definitions

bp = Blueprint("paquet", __name__)


def _store_conn():
    return current_app.json_store._conn()


@bp.route("/api/paquet/definitions", methods=["GET"])
def api_get_definitions():
    """v0.13.7.1 — Retourne la liste des définitions du paquet seqenseigne
    organisées par fichier source (4 fichiers exposés).

    v0.13.7.2.1 — Paramètre `?inclure_structurelles=1` : si présent,
    inclut les macros structurelles (seqExercice, seqCorrige, seqNotion,
    etc.) qui sont par défaut exclues. Sert à la case à cocher de l'UI
    « Afficher les macros structurelles ».
    Cf. services.paquet_expose pour la sémantique du filtrage.
    """
    val = (request.args.get('inclure_structurelles') or '').strip().lower()
    inclure = val in ('1', 'true', 'oui', 'yes')
    with _store_conn() as conn:
        return jsonify(lister_definitions(conn, inclure_structurelles=inclure))
