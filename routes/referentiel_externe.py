"""routes/referentiel_externe.py — v0.25.0

API REST des référentiels externes (structure séquences/parties + documents).
"""

from flask import Blueprint, jsonify, request, current_app, Response

from services import referentiel_externe as svc
from services.referentiel_externe import RefExterneErreur
from services import annees_scolaires

bp = Blueprint("referentiel_externe", __name__)


def _store():
    return current_app.json_store


def _data_dir():
    return current_app.json_store.data_dir


def _err(e: RefExterneErreur):
    return jsonify({"error": str(e), "code": e.code, **e.details}), 400


# ── Référentiels ─────────────────────────────────────────────────────────────

@bp.route("/api/referentiels-externes", methods=["GET"])
def api_lister():
    niveau = request.args.get("niveau")
    annee = request.args.get("annee")
    type_ = request.args.get("type")
    with _store()._conn() as conn:
        items = svc.lister(conn, niveau=niveau, annee=annee, type=type_)
    return jsonify({"referentiels": items, "types": list(svc.TYPES),
                    "etats": list(svc.ETATS)})


@bp.route("/api/referentiels-externes", methods=["POST"])
def api_creer():
    b = request.get_json() or {}
    annee = b.get("annee") or annees_scolaires.courante()
    try:
        with _store()._conn() as conn:
            item = svc.creer(conn, niveau=b.get("niveau", ""), annee=annee,
                             type=b.get("type", "mer"), nom=b.get("nom", ""))
        return jsonify(item), 201
    except RefExterneErreur as e:
        return _err(e)


@bp.route("/api/referentiels-externes/<rid>", methods=["GET"])
def api_lire(rid):
    try:
        with _store()._conn() as conn:
            return jsonify(svc.lire(conn, rid))
    except RefExterneErreur as e:
        return _err(e)


@bp.route("/api/referentiels-externes/<rid>", methods=["PUT"])
def api_modifier(rid):
    b = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            return jsonify(svc.modifier(conn, rid, b))
    except RefExterneErreur as e:
        return _err(e)


@bp.route("/api/referentiels-externes/<rid>/etat", methods=["POST"])
def api_etat(rid):
    b = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            return jsonify(svc.changer_etat(conn, rid, b.get("etat", "")))
    except RefExterneErreur as e:
        return _err(e)


@bp.route("/api/referentiels-externes/<rid>", methods=["DELETE"])
def api_supprimer(rid):
    try:
        with _store()._conn() as conn:
            svc.supprimer(conn, rid, data_dir=_data_dir())
        return jsonify({"ok": True})
    except RefExterneErreur as e:
        return _err(e)


# ── Séquences ────────────────────────────────────────────────────────────────

@bp.route("/api/referentiels-externes/<rid>/sequences", methods=["POST"])
def api_seq_ajouter(rid):
    b = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            return jsonify(svc.ajouter_sequence(
                conn, rid, code=b.get("code", ""), nom=b.get("nom", ""))), 201
    except RefExterneErreur as e:
        return _err(e)


@bp.route("/api/referentiels-externes/sequences/<seq_id>", methods=["PUT"])
def api_seq_modifier(seq_id):
    b = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            return jsonify(svc.modifier_sequence(conn, seq_id, b))
    except RefExterneErreur as e:
        return _err(e)


@bp.route("/api/referentiels-externes/sequences/<seq_id>/deplacer",
          methods=["POST"])
def api_seq_deplacer(seq_id):
    b = request.get_json() or {}
    sens = 1 if (b.get("sens") == "bas" or b.get("sens") == 1) else -1
    try:
        with _store()._conn() as conn:
            return jsonify({"sequences": svc.deplacer_sequence(conn, seq_id, sens)})
    except RefExterneErreur as e:
        return _err(e)


@bp.route("/api/referentiels-externes/sequences/<seq_id>", methods=["DELETE"])
def api_seq_supprimer(seq_id):
    try:
        with _store()._conn() as conn:
            svc.supprimer_sequence(conn, seq_id, data_dir=_data_dir())
        return jsonify({"ok": True})
    except RefExterneErreur as e:
        return _err(e)


# ── Parties ──────────────────────────────────────────────────────────────────

@bp.route("/api/referentiels-externes/sequences/<seq_id>/parties",
          methods=["POST"])
def api_partie_ajouter(seq_id):
    b = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            return jsonify(svc.ajouter_partie(
                conn, seq_id, libelle=b.get("libelle", ""),
                nb_seances=b.get("nb_seances", 1))), 201
    except RefExterneErreur as e:
        return _err(e)


@bp.route("/api/referentiels-externes/parties/<partie_id>", methods=["PUT"])
def api_partie_modifier(partie_id):
    b = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            return jsonify(svc.modifier_partie(conn, partie_id, b))
    except RefExterneErreur as e:
        return _err(e)


@bp.route("/api/referentiels-externes/parties/<partie_id>/deplacer",
          methods=["POST"])
def api_partie_deplacer(partie_id):
    b = request.get_json() or {}
    sens = 1 if (b.get("sens") == "bas" or b.get("sens") == 1) else -1
    try:
        with _store()._conn() as conn:
            return jsonify({"parties": svc.deplacer_partie(conn, partie_id, sens)})
    except RefExterneErreur as e:
        return _err(e)


@bp.route("/api/referentiels-externes/parties/<partie_id>", methods=["DELETE"])
def api_partie_supprimer(partie_id):
    try:
        with _store()._conn() as conn:
            svc.supprimer_partie(conn, partie_id, data_dir=_data_dir())
        return jsonify({"ok": True})
    except RefExterneErreur as e:
        return _err(e)


# ── Documents ────────────────────────────────────────────────────────────────

@bp.route("/api/referentiels-externes/<rid>/docs-annuels", methods=["POST"])
def api_doc_annuel_ajouter(rid):
    if "fichier" not in request.files:
        return jsonify({"error": "Aucun fichier fourni."}), 400
    f = request.files["fichier"]
    contenu = f.read()
    try:
        with _store()._conn() as conn:
            doc = svc.ajouter_doc_annuel(
                conn, rid, nom_fichier=f.filename or "document",
                contenu=contenu, mime=f.mimetype or "", data_dir=_data_dir())
        return jsonify(doc), 201
    except RefExterneErreur as e:
        return _err(e)


@bp.route("/api/referentiels-externes/parties/<partie_id>/docs",
          methods=["POST"])
def api_doc_ajouter(partie_id):
    if "fichier" not in request.files:
        return jsonify({"error": "Aucun fichier fourni."}), 400
    f = request.files["fichier"]
    contenu = f.read()
    try:
        with _store()._conn() as conn:
            doc = svc.ajouter_doc(
                conn, partie_id, nom_fichier=f.filename or "document",
                contenu=contenu, mime=f.mimetype or "", data_dir=_data_dir())
        return jsonify(doc), 201
    except RefExterneErreur as e:
        return _err(e)


@bp.route("/api/referentiels-externes/docs/<doc_id>", methods=["GET"])
def api_doc_telecharger(doc_id):
    """Sert le document : inline pour les PDF (affichables), en pièce jointe
    (téléchargement) pour les autres formats."""
    from pathlib import Path
    try:
        with _store()._conn() as conn:
            doc = svc.lire_doc(conn, doc_id)
    except RefExterneErreur as e:
        return _err(e)
    chemin = Path(_data_dir()) / doc["chemin"]
    if not chemin.exists():
        return jsonify({"error": "Fichier introuvable."}), 404
    mime = doc.get("mime") or "application/octet-stream"
    inline = mime in svc.MIMES_AFFICHABLES
    disp = "inline" if inline else "attachment"
    return Response(
        chemin.read_bytes(), mimetype=mime,
        headers={"Content-Disposition":
                 f'{disp}; filename="{doc["nom_fichier"]}"'})


@bp.route("/api/referentiels-externes/docs/<doc_id>", methods=["DELETE"])
def api_doc_supprimer(doc_id):
    try:
        with _store()._conn() as conn:
            svc.supprimer_doc(conn, doc_id, data_dir=_data_dir())
        return jsonify({"ok": True})
    except RefExterneErreur as e:
        return _err(e)
