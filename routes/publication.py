"""routes/publication.py — v0.51.1

Format d'échange des référentiels (profil atelier) :

  GET /api/publication/referentiels/<rid>.json      → fichier JSON (téléchargé)
  GET /api/publication/referentiels/<rid>/verification
        → { valide, erreurs, bilan } (vérification avant publication)
  GET  /api/publication/publiables   → référentiels publiables (v0.51.2)
  POST /api/publication/paquet {referentiels:[id…]} → paquet zip (v0.51.2)
  GET  /api/publication/journal      → dernières publications (v0.51.2)

Voir services/format_referentiel.py et doc/format_referentiel.md.
"""

import json

from flask import Blueprint, Response, current_app, jsonify, request

from services import format_referentiel as fmt
from services import paquet_publication as pqt

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
            omis: list = []
            doc = fmt.exporter(conn, rid, store.data_dir, _profil(), figer=False, omis=omis)
    except fmt.FormatErreur as e:
        return _erreur(e)
    erreurs = fmt.valider(doc)
    return jsonify({"valide": not erreurs, "erreurs": erreurs,
                    "bilan": fmt.bilan(doc, omis)})


# ── v0.51.2 — Paquet de publication ─────────────────────────────────────────

@bp.route("/api/publication/publiables", methods=["GET"])
def api_publiables():
    store = _store()
    with store._conn() as conn:
        return jsonify({"referentiels": pqt.lister_publiables(conn, store.data_dir),
                        "journal": pqt.journal(conn, 5)})


@bp.route("/api/publication/journal", methods=["GET"])
def api_journal():
    with _store()._conn() as conn:
        return jsonify({"journal": pqt.journal(conn)})


@bp.route("/api/publication/paquet", methods=["POST"])
def api_paquet():
    store = _store()
    rids = (request.get_json(silent=True) or {}).get("referentiels") or []
    try:
        with store._conn() as conn:
            contenu, manifeste = pqt.creer(conn, store.data_dir, rids, _profil())
    except pqt.PaquetErreur as e:
        return jsonify({"error": str(e), "code": e.code, "rapport": e.rapport}), 422
    rapport = manifeste["rapport"]
    return Response(contenu, mimetype="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{manifeste["nom"]}"',
        # Résumé lisible par l'écran (le manifeste complet est dans le zip).
        "X-Paquet-Resume": json.dumps({
            "nom": manifeste["nom"], "nb_referentiels": len(manifeste["referentiels"]),
            "nb_fichiers": len(manifeste["fichiers"]), "taille": len(contenu),
            "documents_sans_pdf": len(rapport["documents_sans_pdf"]),
            "parties_ecart": len(rapport["parties_ecart"])}, ensure_ascii=True)})
