"""routes/retour_usage.py — v0.51.8

Retour d'usage appli en ligne → appli locale (services/retour_usage.py) :

  POST /api/retour-usage/creer                  (classe) → fichier usage_<n>_<date>.json
  POST /api/retour-usage/analyse  (multipart « fichier », atelier) → contrôle, sans rien écrire
  POST /api/retour-usage/importer (multipart « fichier », atelier) → rapport
  GET  /api/retour-usage/apercu                 (classe) → contenu du prochain retour
  GET  /api/retour-usage/etat                   (atelier) → usage reçu par référentiel
"""

import json

from flask import Blueprint, Response, current_app, jsonify, request

from services import retour_usage as ru

bp = Blueprint("retour_usage", __name__)


def _store():
    return current_app.json_store


def _erreur(e: ru.UsageErreur):
    return jsonify({"error": str(e), "code": e.code, "erreurs": e.erreurs[:20]}), \
        (409 if e.code == "sequence" else 422)


def _fichier():
    f = request.files.get("fichier")
    return f.read() if f is not None else None


@bp.route("/api/retour-usage/creer", methods=["POST"])
def api_creer():
    store = _store()
    with store._conn() as conn:
        nom, contenu, doc = ru.creer(conn, store.data_dir)
    return Response(contenu, mimetype="application/json", headers={
        "Content-Disposition": f'attachment; filename="{nom}"',
        "X-Usage-Resume": json.dumps({"nom": nom, "numero": doc["echange"]["numero"],
                                      "nb_referentiels": len(doc["referentiels"])})})


@bp.route("/api/retour-usage/apercu", methods=["GET"])
def api_apercu():
    with _store()._conn() as conn:
        return jsonify(ru.construire(conn))


@bp.route("/api/retour-usage/analyse", methods=["POST"])
def api_analyse():
    contenu = _fichier()
    if not contenu:
        return jsonify({"error": "Aucun fichier reçu (champ « fichier »).",
                        "code": "donnees_invalides"}), 400
    try:
        with _store()._conn() as conn:
            return jsonify(ru.analyser(conn, contenu))
    except ru.UsageErreur as e:
        return _erreur(e)


@bp.route("/api/retour-usage/importer", methods=["POST"])
def api_importer():
    contenu = _fichier()
    if not contenu:
        return jsonify({"error": "Aucun fichier reçu (champ « fichier »).",
                        "code": "donnees_invalides"}), 400
    store = _store()
    try:
        with store._conn() as conn:
            return jsonify(ru.importer(conn, store.data_dir, contenu))
    except ru.UsageErreur as e:
        return _erreur(e)


@bp.route("/api/retour-usage/etat", methods=["GET"])
def api_etat():
    with _store()._conn() as conn:
        return jsonify({"usages": ru.journal(conn)})
