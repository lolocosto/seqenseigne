"""routes/fiches_resume.py — v0.10.5

Endpoints REST pour les fiches de résumé.

CRUD :
  GET    /api/fiches-resume?niveau=N10&sequence=S01     — lister
  GET    /api/fiches-resume/<fiche_id>                  — détail
  POST   /api/fiches-resume                             — créer
  PUT    /api/fiches-resume/<fiche_id>                  — modifier
  DELETE /api/fiches-resume/<fiche_id>                  — supprimer

Liens (drop sur le Connaître) :
  POST   /api/objectifs-v2/<objectif_id>/fiches         — attacher
  DELETE /api/objectifs-v2/<objectif_id>/fiches/<fid>   — détacher
  GET    /api/objectifs-v2/<objectif_id>/fiches         — lister attachées

Sidebar assemblage (mode Connaître ouvert) :
  GET    /api/parties/<partie_id>/fiches-disponibles    — fiches de la partie

Helper aplatissement :
  POST   /api/fiches-resume/aplatir-atome
         body: {"type_atome": "notion", "atome_id": "..."}
         retour: {"contenu": "..."}
"""

from __future__ import annotations
from contextlib import contextmanager
from flask import Blueprint, jsonify, request, current_app

from services.fiches_resume import (
    creer_fiche, lire_fiche, lister_fiches, modifier_fiche, supprimer_fiche,
    attacher_fiche_a_objectif, detacher_fiche_de_objectif,
    lister_fiches_attachees, lister_fiches_de_partie,
    aplatir_atome_pour_initialisation,
    FicheErreur, FicheIntrouvable, ObjectifIntrouvable,
    ObjectifDejaLie, FicheDejaPresente,
)


bp_fiches_resume = Blueprint("fiches_resume", __name__)


# ── Mapping erreur → code HTTP ──────────────────────────────────────────────

_CODE_HTTP = {
    "fiche_introuvable":     404,
    "objectif_introuvable":  404,
    "objectif_deja_lie":     409,
    "fiche_deja_presente":   409,
    "type_atome_invalide":   400,
}


def _erreur(e: FicheErreur):
    payload = {"error": str(e), "code": e.code, **e.details}
    return jsonify(payload), _CODE_HTTP.get(e.code, 500)


@contextmanager
def _store_conn():
    store = current_app.json_store
    with store._conn() as conn:
        yield conn


# ── CRUD fiches ──────────────────────────────────────────────────────────────


@bp_fiches_resume.route("/api/fiches-resume", methods=["GET"])
def api_lister_fiches():
    """v0.13.6.15 — Liste légère pour la sidebar (contrat à 6 clés).

    Avant (v0.13.6.10) : renvoyait la liste complète (titre + objectif_id
    + num_fiche + niveau + sequence + etat_code + liens). Maintenant on
    passe par le service générique `lister_atomes_sequence` qui ne
    retourne que les 6 clés du contrat uniforme {id, titre, num, code,
    etat_code, liens}.

    Niveau et sequence sont désormais obligatoires (avant : optionnels,
    mais aucun appelant ne s'en servait sans filtre dans la version
    actuelle).
    """
    niveau = (request.args.get("niveau") or "").strip()
    sequence = (request.args.get("sequence") or "").strip()
    # v0.30.2 — niveau obligatoire ; sequence optionnelle (mode « toutes
    # les séquences » : liste tout le niveau).
    if not niveau:
        return jsonify({
            "error": "Paramètre 'niveau' requis.",
            "code":  "params_manquants",
        }), 400
    from services.atomes_liste import (
        lister_atomes_sequence, TypeAtomeInvalide,
    )
    try:
        with _store_conn() as conn:
            atomes = lister_atomes_sequence(conn, 'fiche', niveau, sequence)
    except TypeAtomeInvalide as e:
        return jsonify({"error": str(e), "code": "type_atome_invalide"}), 400
    return jsonify(atomes)


@bp_fiches_resume.route("/api/fiches-resume/<fiche_id>", methods=["GET"])
def api_lire_fiche(fiche_id: str):
    """Détail d'une fiche avec ses sections.

    v0.13.6.14.1 — Enrichit aussi avec le champ `liens` (cohérence avec
    api_lister_fiches qui l'enrichit déjà). Sans ça, l'atelier fiche
    qui ouvre un item via GET unitaire perd le champ `liens` à
    chaque ouverture, et le bouton « ⤵ reprendre titre objectif »
    (mécanisme chantier B) reste invisible — il s'appuie sur
    `itemActif.liens` pour décider de s'afficher.
    """
    try:
        with _store_conn() as conn:
            fiche = lire_fiche(conn, fiche_id)
            from services.liaisons_atomes import enrichir_liste_atomes
            enrichir_liste_atomes(conn, [fiche], 'fiche')
    except FicheErreur as e:
        return _erreur(e)
    return jsonify(fiche)


@bp_fiches_resume.route("/api/fiches-resume", methods=["POST"])
def api_creer_fiche():
    """Créer une fiche.

    Body (deux modes — v0.13.6.14, chantier D) :

    1. **Avec objectif** (historique) :
       ``{"objectif_id": "...", "titre": "...", "sections": [...]}``
       niveau et sequence sont déduits de l'objectif.

    2. **Sans objectif** (nouveau, fiche orpheline à rattacher plus tard
       depuis l'assemblage) :
       ``{"niveau": "N10", "sequence": "S01", "titre": "...",
          "sections": [...]}``
       objectif_id absent ou vide ⇒ niveau et sequence obligatoires.
    """
    payload = request.get_json(silent=True) or {}
    objectif_id = (payload.get("objectif_id") or "").strip() or None
    niveau = (payload.get("niveau") or "").strip() or None
    sequence = (payload.get("sequence") or "").strip() or None

    if objectif_id is None and (not niveau or not sequence):
        return jsonify({
            "error": ("Sans 'objectif_id', les champs 'niveau' et "
                      "'sequence' sont obligatoires."),
            "code": "champ_manquant",
        }), 400
    try:
        with _store_conn() as conn:
            fiche = creer_fiche(
                conn,
                objectif_id=objectif_id,
                niveau=niveau,
                sequence=sequence,
                titre=payload.get("titre", ""),
                sections=payload.get("sections"),
            )
    except FicheErreur as e:
        return _erreur(e)
    except ValueError as e:
        return jsonify({
            "error": str(e), "code": "params_invalides",
        }), 400
    return jsonify(fiche), 201


@bp_fiches_resume.route("/api/fiches-resume/<fiche_id>", methods=["PATCH"])
def api_modifier_fiche(fiche_id: str):
    """Modifier une fiche existante (PATCH partial update).

    Body : {"titre": "...", "sections": [...], "objectif_id": "..."}
    Tous les champs sont optionnels (champ omis = pas de modif).

    Préserve l'etat_code (Q2-N).

    v0.13.7.0e — Route passée de PUT à PATCH strict pour aligner la
    sémantique HTTP avec le comportement réel (partial update). Cohérent
    avec les routes notion/methode/exercice/carte.
    """
    payload = request.get_json(silent=True) or {}
    try:
        with _store_conn() as conn:
            # v0.16.4 — Refuse la modification d'une fiche validée (409).
            from services.etats_edition import (
                assert_atome_modifiable, ItemVerrouille,
            )
            try:
                assert_atome_modifiable(conn, "fiche_resume", fiche_id)
            except ItemVerrouille as e:
                return jsonify({"error": str(e), "code": e.code}), 409
            fiche = modifier_fiche(
                conn, fiche_id,
                titre=payload.get("titre"),
                sections=payload.get("sections"),
                objectif_id=payload.get("objectif_id"),
            )
    except FicheErreur as e:
        return _erreur(e)
    return jsonify(fiche)


@bp_fiches_resume.route("/api/fiches-resume/<fiche_id>", methods=["DELETE"])
def api_supprimer_fiche(fiche_id: str):
    """Supprimer une fiche (et ses sections, et ses liens)."""
    try:
        with _store_conn() as conn:
            supprimer_fiche(conn, fiche_id)
    except FicheErreur as e:
        return _erreur(e)
    return jsonify({"ok": True})


# ── Aplatissement pour le bouton « Initialiser depuis... » ──────────────────


@bp_fiches_resume.route("/api/fiches-resume/aplatir-atome", methods=["POST"])
def api_aplatir_atome():
    """Aplatir une notion ou méthode (corps + sections, hors Exemples)
    en un bloc LaTeX prêt à insérer dans une zone de fiche.

    Body : {"type_atome": "notion"|"methode", "atome_id": "..."}.
    Retour : {"contenu": "..."}.
    """
    payload = request.get_json(silent=True) or {}
    type_atome = (payload.get("type_atome") or "").strip()
    atome_id = (payload.get("atome_id") or "").strip()
    if not type_atome or not atome_id:
        return jsonify({
            "error": "Champs 'type_atome' et 'atome_id' obligatoires.",
            "code": "champ_manquant",
        }), 400
    try:
        with _store_conn() as conn:
            contenu = aplatir_atome_pour_initialisation(
                conn, type_atome=type_atome, atome_id=atome_id,
            )
    except FicheErreur as e:
        return _erreur(e)
    return jsonify({"contenu": contenu})


# ── Liens fiche ↔ objectif (drop sur Connaître) ─────────────────────────────


@bp_fiches_resume.route(
    "/api/objectifs-v2/<objectif_id>/fiches", methods=["GET"],
)
def api_lister_fiches_attachees(objectif_id: str):
    """Liste les fiches attachées à un objectif."""
    with _store_conn() as conn:
        fiches = lister_fiches_attachees(conn, objectif_id)
    return jsonify({"fiches": fiches})


@bp_fiches_resume.route(
    "/api/objectifs-v2/<objectif_id>/fiches", methods=["POST"],
)
def api_attacher_fiche(objectif_id: str):
    """Attacher une fiche à un objectif (drop).

    Body : {"fiche_id": "..."}.
    """
    payload = request.get_json(silent=True) or {}
    fiche_id = (payload.get("fiche_id") or "").strip()
    if not fiche_id:
        return jsonify({
            "error": "Champ 'fiche_id' obligatoire.",
            "code": "champ_manquant",
        }), 400
    try:
        with _store_conn() as conn:
            rep = attacher_fiche_a_objectif(
                conn, objectif_id=objectif_id, fiche_id=fiche_id,
            )
    except FicheErreur as e:
        return _erreur(e)
    return jsonify(rep), 201


@bp_fiches_resume.route(
    "/api/objectifs-v2/<objectif_id>/fiches/<fiche_id>",
    methods=["DELETE"],
)
def api_detacher_fiche(objectif_id: str, fiche_id: str):
    """Détacher une fiche d'un objectif. No-op si la liaison n'existe pas."""
    with _store_conn() as conn:
        detacher_fiche_de_objectif(
            conn, objectif_id=objectif_id, fiche_id=fiche_id,
        )
    return jsonify({"ok": True})


@bp_fiches_resume.route(
    "/api/parties/<partie_id>/fiches-disponibles", methods=["GET"],
)
def api_fiches_de_partie(partie_id: str):
    """Pour la sidebar de l'assemblage en mode "obj Connaître ouvert" :
    liste les fiches dont l'objectif lié est dans la même partie."""
    with _store_conn() as conn:
        fiches = lister_fiches_de_partie(conn, partie_id)
    return jsonify({"fiches": fiches})
