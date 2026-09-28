"""routes/progression_doc.py — v0.32.5

API d'association de documents à la progression (au niveau) :
  - GET  /api/progression-doc?prog_kind=&prog_ref=[&creneau_ref=] : associations
  - POST /api/progression-doc : ajouter une association
  - DELETE /api/progression-doc/<id> : supprimer une association
  - GET  /api/progression-doc/disponibles?niveau=&annee=&sequence=[&suivante=]
        : documents proposables pour un créneau (les sources)
"""

from flask import Blueprint, jsonify, request, current_app

from services import progression_doc as pd

bp = Blueprint("progression_doc", __name__)


def _store():
    return current_app.json_store


@bp.route("/api/progression-doc", methods=["GET"])
def api_lister():
    prog_kind = request.args.get("prog_kind", "")
    prog_ref = request.args.get("prog_ref", "")
    creneau_ref = request.args.get("creneau_ref")  # optionnel
    if not prog_kind or not prog_ref:
        return jsonify({"error": "prog_kind et prog_ref requis"}), 400
    with _store()._conn() as conn:
        data = pd.lister(conn, prog_kind, prog_ref, creneau_ref)
    return jsonify({"associations": data})


@bp.route("/api/progression-doc", methods=["POST"])
def api_ajouter():
    b = request.get_json() or {}
    try:
        with _store()._conn() as conn:
            a = pd.ajouter(
                conn,
                prog_kind=b.get("prog_kind", ""),
                prog_ref=b.get("prog_ref", ""),
                creneau_ref=b.get("creneau_ref", ""),
                rang_seance=b.get("rang_seance", 1),
                doc_source=b.get("doc_source", ""),
                doc_ref=b.get("doc_ref", ""),
                doc_libelle=b.get("doc_libelle", ""),
            )
        return jsonify(a), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/progression-doc/<assoc_id>", methods=["DELETE"])
def api_supprimer(assoc_id):
    with _store()._conn() as conn:
        pd.supprimer(conn, assoc_id)
    return jsonify({"ok": True})


@bp.route("/api/progression-doc/disponibles", methods=["GET"])
def api_disponibles():
    niveau = request.args.get("niveau", "")
    annee = request.args.get("annee", "")
    sequence = request.args.get("sequence", "")
    suivante = request.args.get("suivante")  # optionnel
    if not niveau or not sequence:
        return jsonify({"error": "niveau et sequence requis"}), 400
    with _store()._conn() as conn:
        data = pd.documents_disponibles(conn, niveau, annee, sequence,
                                        sequence_suivante=suivante)
    return jsonify(data)
