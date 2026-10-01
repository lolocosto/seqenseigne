"""routes/projection.py — v0.19.1.18 (v0.41.1 : contexte_projection)

API d'orchestration de la projection des séances d'une classe sur le calendrier.
Récupère l'EDT de la classe, la grille horaire de l'établissement, les vacances
(zone de l'académie) et les jours fériés, puis délègue au service pur
`projection_seances.projeter` (préparation : services/contexte_projection.py).
"""

from flask import Blueprint, jsonify, request, current_app

from services import contexte_projection as ctx
from services import annees_scolaires

bp = Blueprint("projection", __name__)


def _store():
    return current_app.json_store


@bp.route("/api/classes/<classe_id>/projection", methods=["GET"])
def api_projeter(classe_id: str):
    annee = request.args.get("annee") or annees_scolaires.courante()
    store = _store()
    with store._conn() as conn:
        infos = ctx.infos_classe(conn, classe_id)
        if infos is None:
            return jsonify({"error": "classe introuvable"}), 404
        donnees = ctx.donnees_classe(conn, annee, classe_id,
                                     infos["etablissement_id"])

    # Vacances + fériés : réseau + cache, hors du _conn.
    cal = ctx.calendrier(store, annee, infos["academie"])
    zone = cal["zone"]

    # Avertissement UI seulement si les vacances sont réellement indisponibles
    # (problème réseau ou zone inconnue) — cas qui ne devrait jamais arriver
    # en pratique.
    avertissements = []
    if cal["vacances_absentes"]:
        if not zone:
            avertissements.append(
                "Zone de vacances inconnue (académie non renseignée ou non "
                "reconnue) : le calendrier des vacances n'a pas pu être "
                "appliqué. La projection ignore les vacances (hors été).")
        else:
            avertissements.append(
                "Les dates de vacances officielles n'ont pas pu être "
                "récupérées : la projection ignore les vacances (hors été). "
                "Vérifiez la connexion ou réessayez.")

    seances = ctx.projeter_donnees(annee, classe_id, donnees, cal)
    return jsonify({
        "classe_id": classe_id,
        "annee": annee,
        "zone": zone,
        "vacances_absentes": cal["vacances_absentes"],
        "avertissements": avertissements,
        "nb_seances": len(seances),
        "seances": seances,
    })
