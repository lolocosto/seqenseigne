"""routes/import_publication.py — v0.51.3

Import d'un paquet de publication (profil classe ; aussi en complet) :

  POST /api/import-publication/analyse   (multipart, champ « paquet ») → analyse
  POST /api/import-publication/importer  (multipart, champ « paquet ») → résultat
  GET  /api/import-publication/etat      → référentiels importés + journal

Voir services/import_publication.py et doc/format_paquet.md.
"""

from flask import Blueprint, current_app, jsonify, request

from services import import_publication as imp

bp = Blueprint("import_publication", __name__)


def _store():
    return current_app.json_store


def _contenu():
    f = request.files.get("paquet")
    if f is None:
        return None
    return f.read()


def _erreur(e: imp.ImportErreur):
    return jsonify({"error": str(e), "code": e.code, "erreurs": e.erreurs[:50]}), 422


@bp.route("/api/import-publication/analyse", methods=["POST"])
def api_analyse():
    contenu = _contenu()
    if not contenu:
        return jsonify({"error": "Aucun paquet reçu (champ « paquet »).",
                        "code": "donnees_invalides"}), 400
    store = _store()
    try:
        with store._conn() as conn:
            return jsonify(imp.analyser(conn, store.data_dir, contenu))
    except imp.ImportErreur as e:
        return _erreur(e)


@bp.route("/api/import-publication/importer", methods=["POST"])
def api_importer():
    contenu = _contenu()
    if not contenu:
        return jsonify({"error": "Aucun paquet reçu (champ « paquet »).",
                        "code": "donnees_invalides"}), 400
    store = _store()
    try:
        return jsonify(imp.importer(store._conn, store.data_dir, contenu))
    except imp.ImportErreur as e:
        return _erreur(e)


@bp.route("/api/import-publication/etat", methods=["GET"])
def api_etat():
    with _store()._conn() as conn:
        return jsonify({"importes": imp.importes(conn), "journal": imp.journal(conn)})
