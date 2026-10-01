"""routes/leitner.py — v0.22.0

API du planning d'automatismes (Leitner) d'une classe.

Réutilise la projection des séances (EdT × calendrier × indisponibilités) et
applique la cadence Leitner (enveloppes 1..4). En mode « automatismes pur »,
toutes les séances comptées de la classe sont des séances d'automatismes.
"""

from flask import Blueprint, jsonify, request, current_app, Response

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


@bp.route("/api/classes/<classe_id>/planning-automatismes.pdf", methods=["GET"])
def api_planning_pdf(classe_id):
    """PDF A3 paysage du planning d'automatismes (frise), à imprimer/afficher."""
    from services.planning_automatismes_tex import generer_planning_tex
    from services.planning_leitner_detaille import assembler
    from services.compilateur_pdf import compiler_atome
    from services.configuration import Configuration

    annee = _annee()
    data = _collecter(classe_id, annee)
    if data is None:
        return jsonify({"error": "classe introuvable"}), 404

    blocs = assembler(data["seances"], data["vacances"], data["feries"],
                      data["indispos"], data["grille"], classe_id, annee)
    tex = generer_planning_tex(data["nom"], annee, blocs)

    # Configuration (mise en cache sur l'app), comme les autres routes PDF.
    if not hasattr(current_app, "configuration"):
        current_app.configuration = Configuration(
            current_app.json_store.data_dir)
    config = current_app.configuration

    try:
        resultat = compiler_atome(
            tex_source=tex,
            pdflatex=config.chemin_pdflatex(),
            timeout=config.timeout_compilation_court(),
        )
    except Exception as e:  # pragma: no cover
        return jsonify({"error": f"Compilation impossible : {e}"}), 503

    if getattr(resultat, "ok", False):
        # Pas de Content-Disposition : le PDF s'affiche dans l'iframe (comme le
        # rendu d'atome), au lieu d'être capté par le lecteur PDF du système.
        return Response(resultat.pdf_bytes, mimetype="application/pdf")
    msg = (resultat.erreurs[0].message if getattr(resultat, "erreurs", None)
           else "Erreur de compilation.")
    code = 503 if "pdflatex introuvable" in msg.lower() else 422
    return jsonify({"error": msg}), code
