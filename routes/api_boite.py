"""routes/api_boite.py — v0.51.16

Appli de classe : boîte aux lettres par API, appelée par l'atelier avec le
jeton d'accès (en-tête « Authorization: Bearer <jeton> »), et gestion du
jeton (session de l'enseignant).

  GET    /api/boite/v1/etat             identité, n° de paquet attendu, expiration du jeton
  POST   /api/boite/v1/paquets          dépôt d'un paquet (corps : le zip ; en-tête X-Nom-Fichier)
  GET    /api/boite/v1/usages?apres=n   retours d'usage disponibles (n° > n)
  GET    /api/boite/v1/usages/<n>       un retour d'usage

  GET    /api/jeton                     état du jeton
  POST   /api/jeton {expire_le}         nouveau jeton (montré une seule fois ; révoque l'actuel)
  DELETE /api/jeton                     révoque le jeton
"""

import urllib.parse

from flask import Blueprint, Response, current_app, jsonify, request

from services import api_boite as ab

bp = Blueprint("api_boite", __name__)


def _store():
    return current_app.json_store


def _erreur(e: ab.ApiErreur):
    return jsonify({"error": str(e), "code": e.code}), e.statut


@bp.before_request
def _authentifier():
    if not request.path.startswith("/api/boite/v1/"):
        return None
    adresse = request.remote_addr or "?"
    if not ab.limiter(adresse):
        return jsonify({"error": "Trop d'appels : réessayez plus tard.", "code": "limite"}), 429
    entete = request.headers.get("Authorization", "")
    jeton = entete[7:].strip() if entete.lower().startswith("bearer ") else ""
    try:
        with _store()._conn() as conn:
            ab.verifier(conn, jeton)
    except ab.ApiErreur as e:
        ab.limiter(adresse, echec=True)
        return _erreur(e)
    return None


@bp.route("/api/boite/v1/etat", methods=["GET"])
def api_etat():
    store = _store()
    with store._conn() as conn:
        return jsonify(ab.etat_boite(conn, store.data_dir))


@bp.route("/api/boite/v1/paquets", methods=["POST"])
def api_deposer():
    if (request.content_length or 0) > ab.TAILLE_MAX:
        return jsonify({"error": "Paquet trop volumineux.", "code": "trop_gros"}), 413
    nom = urllib.parse.unquote(request.headers.get("X-Nom-Fichier", ""))
    try:
        return jsonify(ab.deposer_paquet(_store(), request.get_data(), nom))
    except ab.ApiErreur as e:
        return _erreur(e)


@bp.route("/api/boite/v1/usages", methods=["GET"])
def api_usages():
    try:
        apres = int(request.args.get("apres") or 0)
    except ValueError:
        apres = 0
    return jsonify({"usages": ab.usages_disponibles(_store(), apres)})


@bp.route("/api/boite/v1/usages/<int:numero>", methods=["GET"])
def api_usage(numero):
    try:
        nom, contenu = ab.lire_usage(_store(), numero)
    except ab.ApiErreur as e:
        return _erreur(e)
    return Response(contenu, mimetype="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{nom}"'})


# ── Jeton (enseignant connecté) ──────────────────────────────────────────────

@bp.route("/api/jeton", methods=["GET"])
def api_jeton_etat():
    with _store()._conn() as conn:
        return jsonify(ab.etat_jeton(conn))


@bp.route("/api/jeton", methods=["POST"])
def api_jeton_generer():
    b = request.get_json(silent=True) or {}
    try:
        with _store()._conn() as conn:
            return jsonify(ab.generer(conn, b.get("expire_le", "")))
    except ab.ApiErreur as e:
        return _erreur(e)


@bp.route("/api/jeton", methods=["DELETE"])
def api_jeton_revoquer():
    with _store()._conn() as conn:
        ab.revoquer(conn)
        return jsonify(ab.etat_jeton(conn))
