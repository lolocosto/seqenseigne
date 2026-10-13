"""routes/echanges.py — v0.51.7

Protocole d'échange atelier ↔ classe (voir services/echanges.py) :

  GET    /api/echanges/etat                       → identité, correspondants, envois, réceptions
  PUT    /api/echanges/instance {nom}             → renomme cette instance
  GET    /api/echanges/envois/<type>/<n>          → renvoi d'un envoi archivé (fichier)
  DELETE /api/echanges/correspondants/<role>      → oublie le correspondant (atelier | classe)
"""

from flask import Blueprint, Response, current_app, jsonify, request

from services import echanges as ech

bp = Blueprint("echanges", __name__)


def _store():
    return current_app.json_store


def _err(e: ech.EchangeErreur):
    return jsonify({"error": str(e), "code": e.code}), (404 if e.code == "introuvable" else 400)


@bp.route("/api/echanges/etat", methods=["GET"])
def api_etat():
    with _store()._conn() as conn:
        return jsonify(ech.etat(conn))


@bp.route("/api/echanges/instance", methods=["PUT"])
def api_renommer():
    try:
        with _store()._conn() as conn:
            return jsonify(ech.renommer(conn, (request.get_json(silent=True) or {}).get("nom", "")))
    except ech.EchangeErreur as e:
        return _err(e)


@bp.route("/api/echanges/envois/<type_>/<int:numero>", methods=["GET"])
def api_renvoyer(type_, numero):
    store = _store()
    try:
        with store._conn() as conn:
            nom, contenu = ech.lire_archive(conn, store.data_dir, type_, numero)
    except ech.EchangeErreur as e:
        return _err(e)
    mime = "application/zip" if nom.endswith(".zip") else "application/json"
    return Response(contenu, mimetype=mime,
                    headers={"Content-Disposition": f'attachment; filename="{nom}"'})


@bp.route("/api/echanges/correspondants/<role>", methods=["DELETE"])
def api_delier(role):
    if role not in ("atelier", "classe"):
        return jsonify({"error": "Rôle inconnu.", "code": "donnees_invalides"}), 400
    with _store()._conn() as conn:
        ech.delier(conn, role)
    return jsonify({"ok": True})
