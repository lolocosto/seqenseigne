"""routes/progression_mer.py — v0.26.0

API REST des progressions de mise en route « à la séance ».
"""

from flask import Blueprint, jsonify, request, current_app, render_template

from services import progression_mer as svc
from services.progression_mer import ProgMerErreur
from services import contexte_projection as ctx
from services import annees_scolaires

bp = Blueprint("progression_mer", __name__)


def _store():
    return current_app.json_store


def _annee():
    return request.args.get("annee") or annees_scolaires.courante()


def _err(e: ProgMerErreur):
    return jsonify({"error": str(e), "code": e.code, **e.details}), 400


@bp.route("/api/progression-mer", methods=["GET"])
def api_lire(): 
    """Progression MER d'un niveau/année (créée si besoin)."""
    annee = _annee()
    niveau = request.args.get("niveau", "")
    if not niveau:
        return jsonify({"error": "niveau requis"}), 400
    with _store()._conn() as conn:
        prog = svc.creer_ou_lire(conn, niveau, annee)
    return jsonify(prog)


@bp.route("/api/progression-mer/referentiel", methods=["POST"])
def api_definir_ref():
    annee = _annee()
    b = request.get_json() or {}
    niveau = b.get("niveau", "")
    if not niveau:
        return jsonify({"error": "niveau requis"}), 400
    try:
        with _store()._conn() as conn:
            prog = svc.creer_ou_lire(conn, niveau, annee)
            prog = svc.definir_referentiel(
                conn, prog["id"], b.get("ref_mer_id", ""),
                b.get("ref_mer_source", "externe"))
        return jsonify(prog)
    except ProgMerErreur as e:
        return _err(e)


@bp.route("/api/progression-mer/<prog_id>/etat", methods=["POST"])
def api_etat(prog_id):
    b = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            return jsonify(svc.changer_etat(conn, prog_id, b.get("etat", "")))
    except ProgMerErreur as e:
        return _err(e)


@bp.route("/api/progression-mer/<prog_id>/parties-disponibles",
          methods=["GET"])
def api_parties_disponibles(prog_id):
    with _store()._conn() as conn:
        p = conn.execute("SELECT ref_mer_id, ref_mer_source FROM "
                         "progression_mer WHERE id=?", (prog_id,)).fetchone()
        if p is None or not p["ref_mer_id"]:
            return jsonify({"parties": []})
        parties = svc.lister_parties_disponibles(
            conn, p["ref_mer_id"], p["ref_mer_source"])
    return jsonify({"parties": parties})


@bp.route("/api/progression-mer/<prog_id>/parties", methods=["POST"])
def api_poser_partie(prog_id):
    b = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            return jsonify(svc.poser_partie(
                conn, prog_id, b.get("partie_id", ""),
                b.get("partie_source", "externe")))
    except ProgMerErreur as e:
        return _err(e)


@bp.route("/api/progression-mer/parties/<pose_id>", methods=["DELETE"])
def api_retirer_partie(pose_id):
    try:
        with _store()._conn() as conn:
            svc.retirer_partie(conn, pose_id)
        return jsonify({"ok": True})
    except ProgMerErreur as e:
        return _err(e)


@bp.route("/api/progression-mer/parties/<pose_id>/deplacer", methods=["POST"])
def api_deplacer_partie(pose_id):
    b = request.get_json() or {}
    sens = 1 if (b.get("sens") == "bas" or b.get("sens") == 1) else -1
    try:
        with _store()._conn() as conn:
            return jsonify(svc.deplacer_partie(conn, pose_id, sens))
    except ProgMerErreur as e:
        return _err(e)


@bp.route("/api/classes/<classe_id>/planning-mer", methods=["GET"])
def api_planning(classe_id):
    """Projette les parties posées sur les séances datées de la classe."""
    annee = _annee()
    store = _store()
    with store._conn() as conn:
        row = conn.execute(
            "SELECT c.nom AS nom, c.niveau AS niveau, c.mer_mode AS mer_mode, "
            "c.etablissement_id AS eid, e.academie AS aca "
            "FROM classes c LEFT JOIN etablissements e "
            "ON e.id=c.etablissement_id WHERE c.id=?", (classe_id,)).fetchone()
        if row is None:
            return jsonify({"error": "classe introuvable"}), 404
        prog = svc.creer_ou_lire(conn, row["niveau"], annee)
        etab_id = row["eid"]
        academie = row["aca"] or ""
        donnees = ctx.donnees_classe(conn, annee, classe_id, etab_id)
        grille, indispos = donnees["grille"], donnees["indispos"]
        parties = prog.get("parties", [])
        from services import affectation as aff_svc
        affectations = aff_svc.lire_affectations(conn, classe_id, annee)
        exceptions = aff_svc.dates_exceptions(conn, classe_id, annee)
        mer_mode = row["mer_mode"] or "automatismes"

    cal = ctx.calendrier(store, annee, academie)     # hors du _conn
    vacances, feries = cal["vacances"], cal["feries"]
    seances = ctx.projeter_donnees(annee, classe_id, donnees, cal)
    # v0.28.0 — En progression MER, ne consommer que les séances affectées
    # « progression » (défaut selon le mode ; panachage = choix par créneau).
    from services import affectation as aff_svc
    reparties = aff_svc.repartir_mer(seances, mer_mode, affectations, exceptions)
    seances = reparties["progression"]
    for i, s in enumerate(seances, start=1):
        s["numero"] = i
    planning = svc.projeter_mer(seances, parties)
    return jsonify({
        "classe_id": classe_id, "classe_nom": row["nom"], "annee": annee,
        "nb_seances": len(planning),
        "nb_seances_utilisees": sum(1 for s in planning if s.get("mer_partie_id")),
        "seances": planning,
    })


def _ref_nom(conn, prog) -> str:
    """Nom du référentiel MER de la progression (ancien modèle « externe » ou
    référentiel figé v0.49.0), '' sinon."""
    if prog.get("ref_mer_id") and prog.get("ref_mer_source") == "externe":
        r = conn.execute("SELECT nom FROM referentiel_externe WHERE id=?",
                         (prog["ref_mer_id"],)).fetchone()
        return r["nom"] if r else ""
    if prog.get("ref_mer_id") and prog.get("ref_mer_source") == "fige":   # v0.49.0
        from services import referentiel_principal_externe as _rpe
        r = conn.execute("SELECT * FROM referentiel_niveaux WHERE id=?",
                         (prog["ref_mer_id"],)).fetchone()
        return _rpe.nom_calcule(dict(r)) if r else ""
    return ""


def _planning_mer_classe(classe_id, annee):
    """v0.50.0 — Blocs de frise du planning MER (progression) d'une classe,
    pour le rendu imprimable HTML. None si la classe est inconnue."""
    from services.planning_mer_detaille import assembler
    store = _store()
    with store._conn() as conn:
        row = conn.execute(
            "SELECT c.nom AS nom, c.niveau AS niveau, c.mer_mode AS mer_mode, "
            "c.etablissement_id AS eid, e.academie AS aca "
            "FROM classes c LEFT JOIN etablissements e "
            "ON e.id=c.etablissement_id WHERE c.id=?", (classe_id,)).fetchone()
        if row is None:
            return None
        prog = svc.creer_ou_lire(conn, row["niveau"], annee)
        etab_id = row["eid"]
        academie = row["aca"] or ""
        donnees = ctx.donnees_classe(conn, annee, classe_id, etab_id)
        grille, indispos = donnees["grille"], donnees["indispos"]
        parties = prog.get("parties", [])
        from services import affectation as aff_svc
        affectations = aff_svc.lire_affectations(conn, classe_id, annee)
        exceptions = aff_svc.dates_exceptions(conn, classe_id, annee)
        mer_mode = row["mer_mode"] or "automatismes"
        ref_nom = _ref_nom(conn, prog)

    cal = ctx.calendrier(store, annee, academie)     # hors du _conn
    vacances, feries = cal["vacances"], cal["feries"]
    seances = ctx.projeter_donnees(annee, classe_id, donnees, cal)
    # v0.28.0 — Ne consommer que les séances affectées « progression ».
    from services import affectation as aff_svc
    reparties = aff_svc.repartir_mer(seances, mer_mode, affectations, exceptions)
    seances = reparties["progression"]
    for i, s in enumerate(seances, start=1):
        s["numero"] = i
    blocs = assembler(seances, parties, vacances, feries, indispos, grille,
                      classe_id, annee)
    return {"classe_nom": row["nom"], "ref_nom": ref_nom, "blocs": blocs}


@bp.route("/impression/classes/<classe_id>/planning-mer", methods=["GET"])
def impression_planning_mer(classe_id):
    """v0.50.0 — Planning MER (progression) imprimable, HTML A3 paysage."""
    annee = _annee()
    d = _planning_mer_classe(classe_id, annee)
    if d is None:
        return jsonify({"error": "classe introuvable"}), 404
    return render_template("impression/planning_mer.html", annee=annee, **d)


def _theorique(prog_id):
    """v0.50.0 — (niveau, réf., parties) de l'aperçu théorique, None si la
    progression est inconnue."""
    store = _store()
    with store._conn() as conn:
        prog = conn.execute("SELECT * FROM progression_mer WHERE id=?",
                            (prog_id,)).fetchone()
        if prog is None:
            return None
        prog = svc._lire(conn, prog_id)
        ref_nom = _ref_nom(conn, prog)
    return {"niveau": prog.get("niveau", ""), "ref_nom": ref_nom,
            "parties": prog.get("parties", [])}


@bp.route("/impression/progression-mer/<prog_id>/planning-theorique",
          methods=["GET"])
def impression_planning_theorique(prog_id):
    """v0.50.0 — Aperçu théorique imprimable (HTML A4 portrait)."""
    from services.impression import lignes_theoriques
    annee = _annee()
    d = _theorique(prog_id)
    if d is None:
        return jsonify({"error": "progression introuvable"}), 404
    lignes, total = lignes_theoriques(d["parties"])
    return render_template("impression/planning_mer_theorique.html",
                           annee=annee, niveau=d["niveau"],
                           ref_nom=d["ref_nom"], lignes=lignes, total=total)
