"""routes/projection.py — v0.19.1.18

API d'orchestration de la projection des séances d'une classe sur le calendrier.
Récupère l'EDT de la classe, la grille horaire de l'établissement, les vacances
(zone de l'académie) et les jours fériés, puis délègue au service pur
`projection_seances.projeter`.
"""

from flask import Blueprint, jsonify, request, current_app

from services import edt as edt_svc
from services import grille_horaire as gh_svc
from services import projection_seances as proj
from services import indisponibilites as ind_svc
from services import calendrier_scolaire as cal
from services import annees_scolaires

bp = Blueprint("projection", __name__)


def _store():
    return current_app.json_store


@bp.route("/api/classes/<classe_id>/projection", methods=["GET"])
def api_projeter(classe_id: str):
    annee = request.args.get("annee") or annees_scolaires.courante()
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
        # EDT de la classe filtré sur les usages comptés.
        toutes = edt_svc.lister(conn, annee, classe_id=classe_id)
        edt_comptees = [c for c in toutes
                        if edt_svc.est_compte(c)]
        grille = gh_svc.lister(conn, etab_id) if etab_id else []
        indispos = ind_svc.lister(conn, annee, etablissement_id=etab_id) \
            if etab_id else []

    # Vacances (zone de l'académie) + fériés. Réseau + cache : hors du _conn.
    vacances = []
    feries = {}
    vacances_absentes = False
    zone = cal.zone_academie(academie) if academie else None
    if zone:
        try:
            vacances = cal.vacances(annee, zone, store, academie=academie)
        except Exception:
            vacances = []
    if not vacances:
        vacances_absentes = True
    try:
        feries = cal.jours_feries_annee_scolaire(annee, store)
    except Exception:
        feries = {}

    # Borne basse SYSTÉMATIQUE au 1er septembre : les données officielles ne
    # contiennent jamais les vacances d'été de DÉBUT d'année scolaire (elles
    # relèvent de l'année précédente), donc juillet-août ne sont couverts par
    # aucune période. Comme la rentrée est toujours en septembre en France,
    # borner au 1er septembre est correct et évite de projeter des séances
    # fantômes en août.
    d = int(annee.split("-")[0])
    date_min = f"{d}-09-01"

    # Avertissement UI seulement si les vacances sont réellement indisponibles
    # (problème réseau ou zone inconnue) — cas qui ne devrait jamais arriver
    # en pratique.
    avertissements = []
    if vacances_absentes:
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

    seances = proj.projeter(annee, edt_comptees, grille, vacances, feries,
                            date_min=date_min, indisponibilites=indispos,
                            classe_id=classe_id)
    return jsonify({
        "classe_id": classe_id,
        "annee": annee,
        "zone": zone,
        "vacances_absentes": vacances_absentes,
        "avertissements": avertissements,
        "nb_seances": len(seances),
        "seances": seances,
    })
