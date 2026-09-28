"""routes/referentiel_documents.py — v0.13.6.4

API REST des documents publiables d'un référentiel.

Endpoints :
  GET    /api/referentiels/<ref_id>/documents
      → liste les 9 documents publiables du référentiel (initialise si vide).
  PUT    /api/referentiels/<ref_id>/documents/<doc_id>
      → met à jour les options (PATCH-like, validation côté service).
"""

from flask import Blueprint, request, jsonify, current_app

from services import referentiel_documents as svc

bp = Blueprint("referentiel_documents", __name__)


def _store():
    return current_app.json_store


# ── Lister ──────────────────────────────────────────────────────────────────

@bp.route("/api/referentiels/<ref_id>/documents", methods=["GET"])
def api_lister(ref_id: str):
    """Liste les 9 documents publiables du référentiel.

    Initialise auto si vide (cas premier accès à l'onglet).
    """
    store = _store()
    with store._conn() as conn:
        # On vérifie que le référentiel existe pour renvoyer 404 propre.
        row = conn.execute(
            "SELECT id FROM referentiel_niveaux WHERE id = ?",
            (ref_id,),
        ).fetchone()
        if row is None:
            return jsonify({
                "error": "referentiel_introuvable",
                "message": f"Référentiel {ref_id} introuvable",
            }), 404
        documents = svc.lister_documents(conn, ref_id, data_dir=store.data_dir)
        # v0.32.4 — Ajouter les cibles à chaque document pour que le client
        # sache s'il est multi-cible (et générer un lien PDF par cible).
        from services.referentiel_documents_compilation import (
            lister_cibles_document)
        for doc in documents:
            try:
                doc["cibles"] = lister_cibles_document(
                    conn, doc["id"], ref_id, doc.get("type_document", ""))
            except Exception:
                doc["cibles"] = []
    return jsonify({"documents": documents})



# ── Mettre à jour les options ───────────────────────────────────────────────

@bp.route("/api/referentiels/<ref_id>/documents/<doc_id>",
          methods=["PUT"])
def api_maj(ref_id: str, doc_id: str):
    """Met à jour les options d'un document publiable.

    Body JSON : {"options": {...}}  (partiel — PATCH-like)
    """
    body = request.get_json(silent=True) or {}
    options = body.get("options")
    if not isinstance(options, dict):
        return jsonify({
            "error": "body_invalide",
            "message": "Le champ 'options' (objet) est requis",
        }), 400

    store = _store()
    with store._conn() as conn:
        # 1. Référentiel existe ?
        row = conn.execute(
            "SELECT id FROM referentiel_niveaux WHERE id = ?",
            (ref_id,),
        ).fetchone()
        if row is None:
            return jsonify({
                "error": "referentiel_introuvable",
                "message": f"Référentiel {ref_id} introuvable",
            }), 404

        # 2. Document existe ET appartient au référentiel ?
        row = conn.execute(
            "SELECT id FROM referentiel_documents "
            "WHERE id = ? AND referentiel_id = ?",
            (doc_id, ref_id),
        ).fetchone()
        if row is None:
            return jsonify({
                "error": "document_introuvable",
                "message": (
                    f"Document {doc_id} introuvable dans ce référentiel"
                ),
            }), 404

        # 3. Maj via service
        try:
            doc = svc.maj_options(conn, doc_id, options)
        except svc.DocumentErreur as e:
            return jsonify({
                "error": e.code,
                "message": str(e),
                "details": e.details,
            }), 400

    return jsonify({"document": doc})
