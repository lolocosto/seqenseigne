"""routes/etats_edition.py — v0.13.6.8.2

Routes pour la gestion de l'état d'édition des atomes pédagogiques.

Endpoints :
  - GET  /api/etats-edition
        Liste des états possibles (en_cours, valide, etc.).
  - GET  /api/atomes/<type>/<id>/etat
        État courant d'un atome.
  - PATCH /api/atomes/<type>/<id>/etat
        Change l'état. Body JSON : {"etat_code": "..."}.
        Au passage → 'valide', un hook de validation pédagogique peut
        être déclenché (cf. services/etats_edition.HOOKS_VALIDATION_*).
        Si la validation échoue, retourne HTTP 400 avec
        {error, code: 'validation_pedagogique_echec', raisons: [...]}.
  - GET  /api/etats-edition/recap
        Récap par (type, état) — diagnostic.
"""

from __future__ import annotations
from contextlib import contextmanager
from flask import Blueprint, jsonify, request, current_app

from services.etats_edition import (
    lister_etats,
    lire_etat_atome,
    changer_etat_atome,
    compter_atomes_par_etat,
    EtatEditionErreur,
    TypeAtomeInvalide,
    AtomeIntrouvable,
    EtatInconnu,
    ValidationPedagogiqueErreur,
)


bp_etats_edition = Blueprint("etats_edition", __name__)


# ── Mapping erreur → code HTTP ──────────────────────────────────────────────

_CODE_HTTP = {
    "type_atome_invalide":             400,
    "atome_introuvable":                404,
    "etat_inconnu":                     404,
    "validation_pedagogique_echec":     400,  # v0.13.6.8.2
}


def _erreur(e: EtatEditionErreur):
    payload = {"error": str(e), "code": e.code, **e.details}
    return jsonify(payload), _CODE_HTTP.get(e.code, 500)


@contextmanager
def _store_conn():
    """Ouvre une connexion sur la BDD de l'app courante."""
    store = current_app.json_store
    with store._conn() as conn:
        yield conn


# ── Routes ───────────────────────────────────────────────────────────────────


@bp_etats_edition.route("/api/etats-edition", methods=["GET"])
def api_lister_etats():
    """Liste des états d'édition possibles."""
    with _store_conn() as conn:
        etats = lister_etats(conn)
    return jsonify({"etats": etats})


@bp_etats_edition.route(
    "/api/atomes/<type_atome>/<atome_id>/etat",
    methods=["GET"],
)
def api_lire_etat(type_atome: str, atome_id: str):
    """État courant d'un atome."""
    try:
        with _store_conn() as conn:
            etat = lire_etat_atome(conn, type_atome, atome_id)
    except EtatEditionErreur as e:
        return _erreur(e)
    return jsonify({
        "type_atome": type_atome,
        "atome_id":   atome_id,
        "etat_code":  etat,
    })


@bp_etats_edition.route(
    "/api/atomes/<type_atome>/<atome_id>/etat",
    methods=["PATCH"],
)
def api_changer_etat(type_atome: str, atome_id: str):
    """Change l'état d'un atome.

    Body JSON : {"etat_code": "valide"}.
    """
    payload = request.get_json(silent=True) or {}
    nouvel_etat = (payload.get("etat_code") or "").strip()
    if not nouvel_etat:
        return jsonify({
            "error": "Champ 'etat_code' manquant ou vide.",
            "code":  "champ_manquant",
        }), 400
    try:
        with _store_conn() as conn:
            rep = changer_etat_atome(conn, type_atome, atome_id, nouvel_etat)
    except EtatEditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


@bp_etats_edition.route("/api/etats-edition/recap", methods=["GET"])
def api_recap_par_etat():
    """Diagnostic : nombre d'atomes par (type, etat)."""
    with _store_conn() as conn:
        rep = compter_atomes_par_etat(conn)
    return jsonify({"recap": rep})
