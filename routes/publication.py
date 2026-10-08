"""routes/publication.py — v0.51.1

Format d'échange des référentiels (profil atelier) :

  GET /api/publication/referentiels/<rid>.json      → fichier JSON (téléchargé)
  GET /api/publication/referentiels/<rid>/verification
        → { valide, erreurs, bilan } (vérification avant publication)

Voir services/format_referentiel.py et doc/format_referentiel.md.
"""

import json

from flask import Blueprint, Response, current_app, jsonify

from services import format_referentiel as fmt

bp = Blueprint("publication", __name__)


def _store():
    return current_app.json_store


def _profil():
    return current_app.config.get("SEQ_PROFIL", "complet")


def _erreur(e: fmt.FormatErreur):
    statut = 404 if e.code == "introuvable" else 400
    return jsonify({"error": str(e), "code": e.code}), statut


@bp.route("/api/publication/referentiels/<rid>.json", methods=["GET"])
def api_export(rid):
    store = _store()
    try:
        with store._conn() as conn:
            doc = fmt.exporter(conn, rid, store.data_dir, _profil())
    except fmt.FormatErreur as e:
        return _erreur(e)
    erreurs = fmt.valider(doc)
    if erreurs:
        return jsonify({"error": "Le référentiel ne respecte pas le format "
                                 "d'échange.", "code": "format_invalide",
                        "erreurs": erreurs}), 422
    corps = json.dumps(doc, ensure_ascii=False, indent=1)
    nom = f"referentiel_{rid}.json"
    return Response(corps, mimetype="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{nom}"'})


@bp.route("/api/publication/referentiels/<rid>/verification", methods=["GET"])
def api_verification(rid):
    """Vérification seule : ne fige pas la publication d'un interne verrouillé."""
    store = _store()
    try:
        with store._conn() as conn:
            doc = fmt.exporter(conn, rid, store.data_dir, _profil(), figer=False)
    except fmt.FormatErreur as e:
        return _erreur(e)
    erreurs = fmt.valider(doc)
    return jsonify({"valide": not erreurs, "erreurs": erreurs, "bilan": fmt.bilan(doc)})
