"""routes/leitner.py — v0.22.0

API du planning d'automatismes (Leitner) d'une classe.

Réutilise la projection des séances (EdT × calendrier × indisponibilités) et
applique la cadence Leitner (enveloppes 1..4). En mode « automatismes pur »,
toutes les séances comptées de la classe sont des séances d'automatismes.
"""

from flask import Blueprint, jsonify, request, current_app, render_template

from services import contexte_projection as ctx
from services import leitner
from services import annees_scolaires

bp = Blueprint("leitner", __name__)


def _store():
    return current_app.json_store


def _annee():
    return request.args.get("annee") or annees_scolaires.courante()


def _collecter(classe_id, annee):
    """Récupère tout le nécessaire au planning : infos classe, séances
    projetées (avec enveloppes), vacances, fériés, indispos, grille. Retourne
    un dict, ou (None, reponse_erreur) en cas de problème."""
    store = _store()
    with store._conn() as conn:
        row = conn.execute(
            "SELECT c.nom AS nom, c.etablissement_id AS eid, "
            "c.mer_active AS mer_active, c.mer_mode AS mer_mode, "
            "e.academie AS academie "
            "FROM classes c LEFT JOIN etablissements e "
            "ON e.id = c.etablissement_id WHERE c.id=?",
            (classe_id,)).fetchone()
        if row is None:
            return None
        etab_id = row["eid"]
        academie = row["academie"] or ""
        donnees = ctx.donnees_classe(conn, annee, classe_id, etab_id)
        grille, indispos = donnees["grille"], donnees["indispos"]
        # v0.28.0 — Affectations MER par créneau (panachage) + exceptions.
        from services import affectation as aff_svc
        affectations = aff_svc.lire_affectations(conn, classe_id, annee)
        exceptions = aff_svc.dates_exceptions(conn, classe_id, annee) \
            if hasattr(aff_svc, "dates_exceptions") else set()
        mer_mode = row["mer_mode"] or "automatismes"

    cal = ctx.calendrier(store, annee, academie)     # hors du _conn
    vacances, feries = cal["vacances"], cal["feries"]
    seances = ctx.projeter_donnees(annee, classe_id, donnees, cal)
    # v0.28.0 — Ne compter que les séances affectées « automatisme ».
    from services import affectation as aff_svc
    reparties = aff_svc.repartir_mer(seances, mer_mode, affectations, exceptions)
    seances = reparties["automatisme"]
    # Renuméroter (la cadence Leitner avance sur les seules séances auto).
    for i, s in enumerate(seances, start=1):
        s["numero"] = i
    return {
        "row": row, "nom": row["nom"], "etab_id": etab_id,
        "seances": leitner.planning(seances),
        "vacances": vacances, "feries": feries, "indispos": indispos,
        "grille": grille,
    }


@bp.route("/api/classes/<classe_id>/planning-automatismes", methods=["GET"])
def api_planning(classe_id):
    annee = _annee()
    data = _collecter(classe_id, annee)
    if data is None:
        return jsonify({"error": "classe introuvable"}), 404
    row = data["row"]
    return jsonify({
        "classe_id": classe_id,
        "classe_nom": data["nom"],
        "annee": annee,
        "mer_active": bool(row["mer_active"]),
        "mer_mode": row["mer_mode"],
        "nb_enveloppes": leitner.NB_ENVELOPPES,
        "nb_seances": len(data["seances"]),
        "seances": data["seances"],
    })


def _blocs(classe_id, annee):
    """(données, blocs de frise) du planning, ou None si classe inconnue.
    Utilisé par le rendu imprimable HTML (v0.50.0)."""
    from services.planning_leitner_detaille import assembler
    data = _collecter(classe_id, annee)
    if data is None:
        return None
    blocs = assembler(data["seances"], data["vacances"], data["feries"],
                      data["indispos"], data["grille"], classe_id, annee)
    return data, blocs


@bp.route("/impression/classes/<classe_id>/planning-automatismes",
          methods=["GET"])
def impression_planning(classe_id):
    """v0.50.0 — Planning d'automatismes imprimable (HTML, A3 paysage) :
    imprimé ou enregistré en PDF par le navigateur, sans LaTeX."""
    annee = _annee()
    res = _blocs(classe_id, annee)
    if res is None:
        return jsonify({"error": "classe introuvable"}), 404
    data, blocs = res
    return render_template("impression/planning_automatismes.html",
                           classe_nom=data["nom"], annee=annee, blocs=blocs)
