"""routes/v2_edition.py — R4e2 + R4e3.

Blueprint d'édition du modèle v2 : parties, précédences, objectifs.

Endpoints parties / précédences / réassignation (R4e2) :
  POST   /api/v2/sequences-par-niveau/<sn_id>/parties
  PATCH  /api/v2/parties/<partie_id>
  DELETE /api/v2/parties/<partie_id>
  POST   /api/v2/parties/<partie_id>/precedences
  DELETE /api/v2/parties/<partie_id>/precedences/<precedent_niveau>/<precedent_seq>
  PATCH  /api/v2/objectifs/<objectif_id>/partie

Endpoints édition objectif (R4e3) :
  PATCH  /api/v2/objectifs/<objectif_id>/code
  PATCH  /api/v2/objectifs/<objectif_id>/nom
  PATCH  /api/v2/objectifs/<objectif_id>/methode
  PATCH  /api/v2/objectifs/<objectif_id>/criteres
  GET    /api/v2/methodes?niveau=N11&sequence=S03   — catalogue read-only

Codes HTTP :
  200 OK           — succès
  201 Created      — création réussie (POST)
  400 Bad Request  — payload invalide (champs manquants/mal formés)
  404 Not Found    — ressource introuvable
  409 Conflict     — violation d'invariant métier (partie non vide,
                     numéro déjà utilisé, conflit de code, etc.)
"""

from __future__ import annotations
from flask import Blueprint, jsonify, request, current_app

from services.v2_edition import (
    creer_partie,
    supprimer_partie,
    renumeroter_partie,
    ajouter_precedence,
    supprimer_precedence,
    reassigner_objectif_a_partie,
    # R4e3
    modifier_code_objectif,
    modifier_nom_objectif,
    modifier_methode_objectif,
    modifier_criteres_objectif,
    lister_methodes_de_sequence,
    # v0.6.4
    modifier_fin_cycle_objectif,
    ajouter_notion_objectif,
    retirer_notion_objectif,
    lister_notions_de_sequence,
    # R4e4b
    ajouter_exo_a_objectif,
    retirer_exo_de_objectif,
    reordonner_exos,
    lister_exos_disponibles,
    lister_exos_disponibles_pour_revision,
    # v0.10 — atelier d'assemblage
    reordonner_parties,
    reordonner_objectifs_dans_partie,
    activer_objectif_connaitre,
    # v0.12.3.0 — déplacement atomique inter-partie + position
    deplacer_objectif_avec_position,
    lister_exos_revision_approche,
    ajouter_exo_revision_approche,
    retirer_exo_revision_approche,
    reordonner_exos_revision_approche,
    lire_etat_ui_atelier_sequence,
    ecrire_etat_ui_atelier_sequence,
    # v0.10.1 — création/suppression d'objectif simple
    creer_objectif_simple,
    supprimer_objectif,
    # v0.10.2 — précédences au niveau séquence
    lister_precedences_sequence,
    ajouter_precedence_sequence,
    retirer_precedence_sequence,
    # v0.12.0 — plan de travail générique : nb de séances
    modifier_seances_partie,
    modifier_seances_objectif,
    # v0.16.9 — état validable + verrou de la séquence-niveau
    lire_etat_sequence,
    changer_etat_sequence_niveau,
    assert_sequence_modifiable,
    assert_sequence_modifiable_par_partie,
    assert_sequence_modifiable_par_objectif,
    V2EditionErreur,
    SequenceParNiveauIntrouvable,
    PartieIntrouvable,
    ObjectifIntrouvable,
    NumeroPartieInvalide,
    NumeroPartieDejaUtilise,
    PartieNonVide,
    PrecedenceDejaPresente,
    PrecedenceInvalide,
    PrecedenceIntrouvable,
    ReassignationImpossible,
    # R4e3
    CodeObjectifInvalide,
    CodeObjectifDejaUtilise,
    MethodeIntrouvable,
    # R4e4b
    ExerciceIntrouvable,
    SerieInvalide,
    ExoDejaPresent,
    ExoIntrouvableDansObjectif,
    OriginInvalide,
    ReordonnancementInvalide,
    # v0.10
    TypeRevisionApprocheInvalide,
    ExoRevisionApprocheDejaPresent,
    ExoRevisionApprocheIntrouvable,
    ObjectifConnaitreDejaPresent,
    # v0.10.2
    PrecedenceSeqDejaPresente,
    PrecedenceSeqIntrouvable,
    ExoRevisionHorsPrecedences,
    ExoRevisionMauvaiseSerie,
    ExoApprocheHorsSequence,
    ExoApprocheMauvaiseSerie,
    # v0.12.0
    SeancesInvalides,
)


bp_v2_edition = Blueprint("v2_edition", __name__)


# ── Mapping code d'erreur → code HTTP ────────────────────────────────────────
#
# Règle : 404 pour « la ressource référencée n'existe pas », 409 pour
# « la ressource existe mais la mutation casse un invariant »,
# 400 pour « le payload reçu est malformé ».

_CODE_HTTP = {
    # 404
    "sequence_par_niveau_introuvable":  404,
    "partie_introuvable":               404,
    "objectif_introuvable":             404,
    "precedence_introuvable":           404,
    "methode_introuvable":              404,   # R4e3
    "exercice_introuvable":             404,   # R4e4b
    "exo_introuvable_dans_objectif":    404,   # R4e4b
    "notion_introuvable":               404,   # v0.6.4
    "exo_revision_approche_introuvable": 404,  # v0.10
    "precedence_seq_introuvable":       404,   # v0.10.2
    # 409
    "numero_deja_utilise":              409,
    "partie_non_vide":                  409,
    "precedence_deja_presente":         409,
    "partie_hors_sequence":             409,
    "conflit_code_dans_partie_cible":   409,
    "code_objectif_deja_utilise":       409,   # R4e3
    "exo_deja_present":                 409,   # R4e4b
    "exo_revision_approche_deja_present": 409, # v0.10
    "objectif_connaitre_deja_present":  409,   # v0.10
    "precedence_seq_deja_presente":     409,   # v0.10.2
    "exo_revision_hors_precedences":    409,   # v0.10.2
    "exo_revision_mauvaise_serie":      409,   # v0.10.2
    "exo_approche_hors_sequence":       409,   # v0.10.2
    "exo_approche_mauvaise_serie":      409,   # v0.10.2
    "notion_hors_sequence":             409,   # v0.10.7
    "methode_hors_sequence":            409,   # v0.10.7
    "methode_deja_liee":                409,   # v0.10.7
    "item_verrouille":                  409,   # v0.16.9 — séquence validée
    # 400
    "numero_invalide":                  400,
    "precedence_invalide":              400,
    "code_objectif_invalide":           400,   # R4e3
    "serie_invalide":                   400,   # R4e4b
    "origin_invalide":                  400,   # R4e4b
    "reordonnancement_invalide":        400,   # R4e4b
    "type_revision_approche_invalide":  400,   # v0.10
    "seances_invalides":                400,   # v0.12.0
    "etat_sequence_invalide":           400,   # v0.16.9
    "validation_pedagogique_echec":     400,   # v0.16.9 — hook séquence
}


def _erreur(e: V2EditionErreur):
    """Format d'erreur homogène avec routes existantes (R2/R3)."""
    status = _CODE_HTTP.get(e.code, 400)
    payload = {"error": str(e), "code": e.code}
    if e.details:
        payload["details"] = e.details
    return jsonify(payload), status


def _store_conn():
    """Raccourci : renvoie le context manager de connexion SqliteStore."""
    return current_app.json_store._conn()


# ═════════════════════════════════════════════════════════════════════════════
# Parties
# ═════════════════════════════════════════════════════════════════════════════

@bp_v2_edition.route(
    "/api/v2/sequences-par-niveau/<sn_id>/parties",
    methods=["POST"],
)
def api_creer_partie(sn_id: str):
    """Créer une partie dans une séquence par niveau.

    Body JSON (optionnel) :
        {"numero": 2}   — numéro explicite
        {}              — auto-incrément (max + 1, ou 1 si vide)
    """
    payload = request.get_json(silent=True) or {}
    numero = payload.get("numero")  # peut être None
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable(conn, sn_id)
            partie = creer_partie(conn, sn_id, numero)
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(partie), 201


@bp_v2_edition.route("/api/v2/parties/<partie_id>", methods=["PATCH"])
def api_renumeroter_partie(partie_id: str):
    """Renuméroter une partie.

    Body JSON obligatoire : {"numero": N}
    """
    payload = request.get_json(silent=True) or {}
    if "numero" not in payload:
        return jsonify({
            "error": "Champ 'numero' obligatoire pour renumérotation.",
            "code":  "numero_invalide",
        }), 400

    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_partie(conn, partie_id)
            partie = renumeroter_partie(conn, partie_id, payload["numero"])
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(partie)


@bp_v2_edition.route("/api/v2/parties/<partie_id>", methods=["DELETE"])
def api_supprimer_partie(partie_id: str):
    """Supprimer une partie vide. 409 si elle contient des objectifs."""
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_partie(conn, partie_id)
            rep = supprimer_partie(conn, partie_id)
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


# ── v0.12.0 — Plan de travail générique : nb de séances ──────────────────────

@bp_v2_edition.route(
    "/api/v2/parties/<partie_id>/seances",
    methods=["PATCH"],
)
def api_modifier_seances_partie(partie_id: str):
    """Met à jour le nombre de séances R+AE prévues pour une partie.

    Body JSON : {"nb_seances": 1.5}

    Renvoie : {"id", "numero", "nb_seances_R_AE"}.

    Codes HTTP :
      200  — succès
      400  — payload manquant ou nb_seances invalide
      404  — partie introuvable
    """
    payload = request.get_json(silent=True) or {}
    if "nb_seances" not in payload:
        return jsonify({
            "code":    "champ_manquant",
            "message": "Le champ 'nb_seances' est requis.",
        }), 400
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_partie(conn, partie_id)
            rep = modifier_seances_partie(
                conn, partie_id, payload["nb_seances"],
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


# ═════════════════════════════════════════════════════════════════════════════
# Précédences
# ═════════════════════════════════════════════════════════════════════════════

@bp_v2_edition.route(
    "/api/v2/parties/<partie_id>/precedences",
    methods=["POST"],
)
def api_ajouter_precedence(partie_id: str):
    """Ajouter une précédence sur une partie.

    Body JSON : {"precedent_niveau": "N10", "precedent_seq": "S03"}
    """
    payload = request.get_json(silent=True) or {}
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_partie(conn, partie_id)
            rep = ajouter_precedence(
                conn,
                partie_id,
                payload.get("precedent_niveau") or "",
                payload.get("precedent_seq") or "",
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep), 201


@bp_v2_edition.route(
    "/api/v2/parties/<partie_id>/precedences/"
    "<precedent_niveau>/<precedent_seq>",
    methods=["DELETE"],
)
def api_supprimer_precedence(
    partie_id: str,
    precedent_niveau: str,
    precedent_seq: str,
):
    """Supprimer une précédence. 404 si absente."""
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_partie(conn, partie_id)
            rep = supprimer_precedence(
                conn, partie_id, precedent_niveau, precedent_seq,
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


# ═════════════════════════════════════════════════════════════════════════════
# Réassignation d'un objectif
# ═════════════════════════════════════════════════════════════════════════════

@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>/partie",
    methods=["PATCH"],
)
def api_reassigner_objectif(objectif_id: str):
    """Déplacer un objectif dans une autre partie de la même séquence.

    Body JSON : {"partie_id": "pt_xxx"}

    Retour : {objectif_id, code, partie_id, numero_partie, code_coherent,
              deplace}
    """
    payload = request.get_json(silent=True) or {}
    partie_id_cible = payload.get("partie_id")
    if not partie_id_cible:
        return jsonify({
            "error": "Champ 'partie_id' obligatoire.",
            "code":  "partie_id_manquant",
        }), 400

    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = reassigner_objectif_a_partie(
                conn, objectif_id, partie_id_cible,
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>/deplacer",
    methods=["PATCH"],
)
def api_deplacer_objectif(objectif_id: str):
    """Déplacer un objectif vers une partie cible à une position précise,
    avec recalcul automatique des codes des deux parties (source et cible).

    Conçu pour le drag-and-drop d'objectifs dans l'atelier d'assemblage
    (v0.12.3.0). Diffère de `/partie` qui préserve le code (et peut donc
    échouer en `conflit_code_dans_partie_cible`) — ici on réordonne dans
    les deux parties, ce qui garantit l'absence de conflit.

    Body JSON : {
        "partie_cible_id":      "pt_xxx",
        "position_dans_cible":  int (0 à nb_objs_cible inclus)
    }

    Retour : {
        "objectif_id":           id de l'objectif déplacé,
        "code_apres":            son nouveau code après recalcul,
        "partie_source_id":      id partie source,
        "partie_cible_id":       id partie cible,
        "objectifs_source":      [{id, code}, ...] dans l'ordre final,
        "objectifs_cible":       [{id, code}, ...] dans l'ordre final
    }

    Codes d'erreur :
      400 partie_cible_id_manquant / position_invalide
      404 objectif_introuvable / partie_introuvable
      409 partie_hors_sequence / connaitre_non_deplaceable / position_0_avec_connaitre
    """
    payload = request.get_json(silent=True) or {}
    partie_cible_id = payload.get("partie_cible_id")
    position = payload.get("position_dans_cible")
    if not partie_cible_id:
        return jsonify({
            "error": "Champ 'partie_cible_id' obligatoire.",
            "code":  "partie_cible_id_manquant",
        }), 400
    if not isinstance(position, int):
        return jsonify({
            "error": "Champ 'position_dans_cible' obligatoire (entier).",
            "code":  "position_invalide",
        }), 400

    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = deplacer_objectif_avec_position(
                conn, objectif_id, partie_cible_id, position,
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


# ═════════════════════════════════════════════════════════════════════════════
# R4e3 — Édition granulaire d'un objectif
# ═════════════════════════════════════════════════════════════════════════════

@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>/code",
    methods=["PATCH"],
)
def api_modifier_code_objectif(objectif_id: str):
    """Renommer le code d'un objectif.

    Body JSON : {"code": "05"}
    """
    payload = request.get_json(silent=True) or {}
    if "code" not in payload:
        return jsonify({
            "error": "Champ 'code' obligatoire.",
            "code":  "code_objectif_invalide",
        }), 400
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = modifier_code_objectif(conn, objectif_id, payload["code"])
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>/nom",
    methods=["PATCH"],
)
def api_modifier_nom_objectif(objectif_id: str):
    """Changer le nom d'un objectif.

    Body JSON : {"nom": "..."} — chaîne vide acceptée.
    """
    payload = request.get_json(silent=True) or {}
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = modifier_nom_objectif(conn, objectif_id, payload.get("nom", ""))
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>/methode",
    methods=["PATCH"],
)
def api_modifier_methode_objectif(objectif_id: str):
    """Changer la méthode liée à un objectif.

    Body JSON : {"methode_id": "me_xxx"} pour attacher
                {"methode_id": null}     pour détacher
                {"methode_id": ""}       idem (détacher)
    """
    payload = request.get_json(silent=True) or {}
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = modifier_methode_objectif(
                conn, objectif_id, payload.get("methode_id"),
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>/criteres",
    methods=["PATCH"],
)
def api_modifier_criteres_objectif(objectif_id: str):
    """Changer un ou plusieurs critères d'un objectif.

    Body JSON partiel : {"critere_F": "...", "critere_A": "...",
                         "critere_E": "..."}
    Les champs absents du payload ne sont pas modifiés (permet l'édition
    ciblée d'un seul critère sans renvoyer les autres).
    """
    payload = request.get_json(silent=True) or {}
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = modifier_criteres_objectif(
                conn, objectif_id,
                critere_F=payload.get("critere_F"),
                critere_A=payload.get("critere_A"),
                critere_E=payload.get("critere_E"),
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


# ── v0.12.0 — Plan de travail générique : nb de séances par objectif ─────────

@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>/seances",
    methods=["PATCH"],
)
def api_modifier_seances_objectif(objectif_id: str):
    """Met à jour le nombre de séances prévues pour un objectif.

    Pour l'objectif 'cours' (code 01/11/21) : séances d'explication par
    l'enseignant. Pour les autres : séances de réalisation des exercices.

    Body JSON : {"nb_seances": 2.5}

    Renvoie l'objectif mis à jour (format _format_retour_objectif), avec
    son nouveau champ `nb_seances`.

    Codes HTTP :
      200  — succès
      400  — payload manquant ou nb_seances invalide
      404  — objectif introuvable
    """
    payload = request.get_json(silent=True) or {}
    if "nb_seances" not in payload:
        return jsonify({
            "code":    "champ_manquant",
            "message": "Le champ 'nb_seances' est requis.",
        }), 400
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = modifier_seances_objectif(
                conn, objectif_id, payload["nb_seances"],
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


# ── v0.6.4 : édition fin_cycle et notions associées ──────────────────────────

@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>/fin-cycle",
    methods=["PATCH"],
)
def api_modifier_fin_cycle_objectif(objectif_id: str):
    """Bascule le marqueur 'fin de cycle 4' d'un objectif.

    Body JSON : {"fin_cycle": "O" | "N" | true | false}
    Retourne l'objectif mis à jour (format _format_retour_objectif).
    """
    payload = request.get_json(silent=True) or {}
    if "fin_cycle" not in payload:
        return jsonify({
            "error": "Champ 'fin_cycle' obligatoire dans le body.",
            "code":  "champ_manquant",
        }), 400
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = modifier_fin_cycle_objectif(
                conn, objectif_id, payload["fin_cycle"]
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>/notions",
    methods=["POST"],
)
def api_ajouter_notion_objectif(objectif_id: str):
    """Associe une notion à un objectif.

    Body JSON : {"notion_id": "..."}
    Idempotent : une 2e association de la même paire est sans effet.
    Retourne l'objectif mis à jour (avec sa liste de notions).
    """
    payload = request.get_json(silent=True) or {}
    notion_id = (payload.get("notion_id") or "").strip()
    if not notion_id:
        return jsonify({
            "error": "Champ 'notion_id' obligatoire dans le body.",
            "code":  "champ_manquant",
        }), 400
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = ajouter_notion_objectif(conn, objectif_id, notion_id)
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep), 201


@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>/notions/<notion_id>",
    methods=["DELETE"],
)
def api_retirer_notion_objectif(objectif_id: str, notion_id: str):
    """Dissocie une notion d'un objectif. Idempotent."""
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = retirer_notion_objectif(conn, objectif_id, notion_id)
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


@bp_v2_edition.route("/api/v2/methodes", methods=["GET"])
def api_lister_methodes_de_sequence():
    """Liste les méthodes rattachées à une (niveau, sequence).

    Query params obligatoires : ?niveau=N11&sequence=S03
    Retour : {"methodes": [{"id", "titre", "num_methode", "num_objectif",
              "fichier"}, ...]}
    """
    niveau = request.args.get("niveau", "").strip()
    sequence = request.args.get("sequence", "").strip()
    if not niveau or not sequence:
        return jsonify({
            "error": "Paramètres 'niveau' et 'sequence' obligatoires.",
            "code":  "parametres_manquants",
        }), 400

    with _store_conn() as conn:
        methodes = lister_methodes_de_sequence(conn, niveau, sequence)
    return jsonify({"methodes": methodes})


@bp_v2_edition.route("/api/v2/notions-de-sequence", methods=["GET"])
def api_lister_notions_de_sequence():
    """Liste les notions rattachées à une (niveau, sequence).

    Query params obligatoires : ?niveau=N11&sequence=S03
    Retour : {"notions": [{"id", "titre", "num_connaissance", "fichier"}, ...]}

    Endpoint nommé /notions-de-sequence (et non /notions) pour ne pas
    entrer en conflit avec la route déjà existante /api/notions du
    blueprint atomes (qui retourne TOUTES les notions sans filtre).
    """
    niveau = request.args.get("niveau", "").strip()
    sequence = request.args.get("sequence", "").strip()
    if not niveau or not sequence:
        return jsonify({
            "error": "Paramètres 'niveau' et 'sequence' obligatoires.",
            "code":  "parametres_manquants",
        }), 400

    with _store_conn() as conn:
        notions = lister_notions_de_sequence(conn, niveau, sequence)
    return jsonify({"notions": notions})


# ═════════════════════════════════════════════════════════════════════════════
# R4e4b — Édition des exos d'un objectif
# ═════════════════════════════════════════════════════════════════════════════

@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>/exos",
    methods=["POST"],
)
def api_ajouter_exo(objectif_id: str):
    """Ajouter un exo à une (objectif, série).

    Body JSON :
      - EA/F/A/E : {"serie": "F", "exercice_id": "ex_xxx"}

    v0.11.2 — La série 'R' a été retirée. Pour affecter un exo comme
    révision à une partie de séquence, passer par les routes de
    `partie_exos_revision_approche` (cf. routes_v2 plus bas).

    Retour : {"objectif_id", "serie", "exos": [...]} — liste à jour.
    """
    payload = request.get_json(silent=True) or {}
    serie = payload.get("serie", "")
    exercice_id = payload.get("exercice_id", "")
    if not exercice_id:
        return jsonify({
            "error": "Champ 'exercice_id' obligatoire.",
            "code":  "exercice_id_manquant",
        }), 400
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = ajouter_exo_a_objectif(
                conn, objectif_id, serie, exercice_id,
                origin_niveau=payload.get("origin_niveau"),
                origin_seq=payload.get("origin_seq"),
                origin_serie=payload.get("origin_serie"),
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep), 201


@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>/exos/<serie>/<exercice_id>",
    methods=["DELETE"],
)
def api_retirer_exo(objectif_id: str, serie: str, exercice_id: str):
    """Retirer un exo d'une (objectif, série). Recompacte les ordres
    restants (1, 2, 3... dense).

    Retour : {"objectif_id", "serie", "exos": [...]} — liste à jour.
    """
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = retirer_exo_de_objectif(
                conn, objectif_id, serie, exercice_id,
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>/exos/<serie>/ordre",
    methods=["PATCH"],
)
def api_reordonner_exos(objectif_id: str, serie: str):
    """Réordonner les exos d'une (objectif, série).

    Body JSON : {"exercice_ids": ["ex_a", "ex_b", "ex_c"]} — ordre voulu.
    La liste doit contenir exactement les mêmes exercice_ids que ce qui
    est en base.

    Retour : {"objectif_id", "serie", "exos": [...]}.
    """
    payload = request.get_json(silent=True) or {}
    exercice_ids = payload.get("exercice_ids")
    if exercice_ids is None:
        return jsonify({
            "error": "Champ 'exercice_ids' (liste) obligatoire.",
            "code":  "reordonnancement_invalide",
        }), 400
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = reordonner_exos(conn, objectif_id, serie, exercice_ids)
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


@bp_v2_edition.route("/api/v2/exos-disponibles", methods=["GET"])
def api_exos_disponibles():
    """Catalogue pour ajout en séries EA/F/A/E.

    Query params :
      - niveau (ex. N11)            — requis
      - sequence (ex. S03)          — requis
      - serie_cible (EA/F/A/E)      — requis
      - objectif_id (optionnel)     — pour exclure les exos déjà présents

    Retour : {"exos": [{id, nom, fichier, niveau, sequence, num, serie_code}]}
    """
    niveau = (request.args.get("niveau") or "").strip()
    sequence = (request.args.get("sequence") or "").strip()
    serie_cible = (request.args.get("serie_cible") or "").strip()
    objectif_id = request.args.get("objectif_id") or None

    if not niveau or not sequence or not serie_cible:
        return jsonify({
            "error": "Paramètres 'niveau', 'sequence' et 'serie_cible' "
                     "obligatoires.",
            "code":  "parametres_manquants",
        }), 400

    try:
        with _store_conn() as conn:
            exos = lister_exos_disponibles(
                conn, niveau, sequence, serie_cible, objectif_id=objectif_id,
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify({"exos": exos})


@bp_v2_edition.route("/api/v2/exos-disponibles-revision", methods=["GET"])
def api_exos_disponibles_revision():
    """Catalogue pour ajout en série R : exos de (origin_niveau, origin_seq).

    Query params :
      - niveau (ex. N10)    — origin_niveau, requis
      - sequence (ex. S01)  — origin_seq, requis

    Retour : {"exos": [...]} toutes séries confondues, triées par serie_code/num.
    """
    niveau = (request.args.get("niveau") or "").strip()
    sequence = (request.args.get("sequence") or "").strip()
    if not niveau or not sequence:
        return jsonify({
            "error": "Paramètres 'niveau' et 'sequence' obligatoires.",
            "code":  "parametres_manquants",
        }), 400
    with _store_conn() as conn:
        exos = lister_exos_disponibles_pour_revision(conn, niveau, sequence)
    return jsonify({"exos": exos})


# ═════════════════════════════════════════════════════════════════════════════
# v0.10 — Atelier d'assemblage (drag-drop, objectif Connaître, état UI)
# ═════════════════════════════════════════════════════════════════════════════

# ── Réordonnancement parties / objectifs ────────────────────────────────────

@bp_v2_edition.route(
    "/api/v2/sequences-par-niveau/<sn_id>/parties/ordre",
    methods=["PATCH"],
)
def api_reordonner_parties(sn_id: str):
    """Réordonner les parties d'une séquence (drag & drop).

    Body JSON : {"partie_ids": ["pt_a", "pt_b", "pt_c"]} — ordre voulu.
    La position dans la liste devient le numéro (1..N).

    Retour : {"sequence_par_niveau_id", "parties": [{id, numero}, ...]}.

    Note : les codes des objectifs ne sont PAS automatiquement renumérotés ;
    c'est au frontend de chaîner avec /parties/<id>/objectifs/ordre si la
    convention "code 0X en partie 1" doit être respectée.
    """
    payload = request.get_json(silent=True) or {}
    partie_ids = payload.get("partie_ids")
    if partie_ids is None:
        return jsonify({
            "error": "Champ 'partie_ids' (liste) obligatoire.",
            "code":  "reordonnancement_invalide",
        }), 400
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable(conn, sn_id)
            parties = reordonner_parties(conn, sn_id, partie_ids)
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify({
        "sequence_par_niveau_id": sn_id,
        "parties": parties,
    })


@bp_v2_edition.route(
    "/api/v2/parties/<partie_id>/objectifs/ordre",
    methods=["PATCH"],
)
def api_reordonner_objectifs_dans_partie(partie_id: str):
    """Réordonner les objectifs DANS une partie (drag & drop).

    Body JSON : {"objectif_ids": ["ob_a", "ob_b", ...]} — ordre voulu.
    Les codes des objectifs sont automatiquement réécrits en cohérence avec
    la position. L'objectif "Connaître" (code finissant par '1' avec
    convention respectée) doit rester en première position.

    Retour : {"partie_id", "objectifs": [{id, code}, ...]}.
    """
    payload = request.get_json(silent=True) or {}
    objectif_ids = payload.get("objectif_ids")
    if objectif_ids is None:
        return jsonify({
            "error": "Champ 'objectif_ids' (liste) obligatoire.",
            "code":  "reordonnancement_invalide",
        }), 400
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_partie(conn, partie_id)
            objs = reordonner_objectifs_dans_partie(
                conn, partie_id, objectif_ids,
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify({
        "partie_id": partie_id,
        "objectifs": objs,
    })


# ── Activation de l'objectif "Connaître" ────────────────────────────────────

@bp_v2_edition.route(
    "/api/v2/parties/<partie_id>/objectif-connaitre",
    methods=["POST"],
)
def api_activer_objectif_connaitre(partie_id: str):
    """Crée l'objectif "Connaître les notions et les méthodes" dans une partie.

    Body JSON (tous optionnels) :
      {
        "nom": "Connaître les notions et les méthodes",
        "critere_F": "...",
        "critere_A": "...",
        "critere_E": "..."
      }

    Le code est calculé automatiquement ('01' partie 1, '11' partie 2, ...).
    409 si l'objectif Connaître existe déjà dans cette partie.

    Retour : structure complète de l'objectif créé.
    """
    payload = request.get_json(silent=True) or {}
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_partie(conn, partie_id)
            obj = activer_objectif_connaitre(
                conn,
                partie_id,
                nom=payload.get("nom") or "Connaître les notions et les méthodes",
                critere_F=payload.get("critere_F") or "",
                critere_A=payload.get("critere_A") or "",
                critere_E=payload.get("critere_E") or "",
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(obj), 201


# ── Exos de révision/approche au niveau partie ──────────────────────────────

@bp_v2_edition.route(
    "/api/v2/parties/<partie_id>/exos-revision-approche",
    methods=["GET"],
)
def api_lister_exos_revision_approche(partie_id: str):
    """Liste les exos R/EA d'une partie.

    Retour : {"partie_id", "exos": {"R": [...], "EA": [...]}}.
    """
    try:
        with _store_conn() as conn:
            exos = lister_exos_revision_approche(conn, partie_id)
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify({"partie_id": partie_id, "exos": exos})


@bp_v2_edition.route(
    "/api/v2/parties/<partie_id>/exos-revision-approche",
    methods=["POST"],
)
def api_ajouter_exo_revision_approche(partie_id: str):
    """Ajoute un exo R ou EA à une partie.

    Body JSON :
      - EA : {"type": "EA", "exercice_id": "ex_xxx"}
      - R  : {"type": "R",  "exercice_id": "ex_xxx",
              "origin_niveau": "N10", "origin_seq": "S03",
              "origin_serie": "A", "origin_num": 3}

    Retour : {"partie_id", "exos": {"R": [...], "EA": [...]}} — listes à jour.
    """
    payload = request.get_json(silent=True) or {}
    type_ = payload.get("type", "")
    exercice_id = payload.get("exercice_id", "")
    if not exercice_id:
        return jsonify({
            "error": "Champ 'exercice_id' obligatoire.",
            "code":  "exercice_id_manquant",
        }), 400
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_partie(conn, partie_id)
            exos = ajouter_exo_revision_approche(
                conn, partie_id, type_, exercice_id,
                origin_niveau=payload.get("origin_niveau"),
                origin_seq=payload.get("origin_seq"),
                origin_serie=payload.get("origin_serie"),
                origin_num=payload.get("origin_num"),
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify({"partie_id": partie_id, "exos": exos}), 201


@bp_v2_edition.route(
    "/api/v2/parties/<partie_id>/exos-revision-approche/<type_>/<exercice_id>",
    methods=["DELETE"],
)
def api_retirer_exo_revision_approche(
    partie_id: str, type_: str, exercice_id: str,
):
    """Retire un exo R/EA d'une partie. Recompacte les ordres."""
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_partie(conn, partie_id)
            exos = retirer_exo_revision_approche(
                conn, partie_id, type_, exercice_id,
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify({"partie_id": partie_id, "exos": exos})


@bp_v2_edition.route(
    "/api/v2/parties/<partie_id>/exos-revision-approche/<type_>/ordre",
    methods=["PATCH"],
)
def api_reordonner_exos_revision_approche(partie_id: str, type_: str):
    """Réordonner les exos R ou EA d'une partie.

    Body JSON : {"exercice_ids": ["ex_a", "ex_b", "ex_c"]} — ordre voulu.
    """
    payload = request.get_json(silent=True) or {}
    exercice_ids = payload.get("exercice_ids")
    if exercice_ids is None:
        return jsonify({
            "error": "Champ 'exercice_ids' (liste) obligatoire.",
            "code":  "reordonnancement_invalide",
        }), 400
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_partie(conn, partie_id)
            exos = reordonner_exos_revision_approche(
                conn, partie_id, type_, exercice_ids,
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify({"partie_id": partie_id, "exos": exos})


# ── État UI persistant : objectif ouvert ────────────────────────────────────

@bp_v2_edition.route(
    "/api/v2/sequences-par-niveau/<sn_id>/etat-ui",
    methods=["GET"],
)
def api_lire_etat_ui_atelier_sequence(sn_id: str):
    """Lit l'état UI de l'atelier d'assemblage pour une séquence.

    Retour : {"sequence_par_niveau_id", "objectif_ouvert_id", "derniere_maj"}.
    Si aucune ligne n'a encore été créée, objectif_ouvert_id = null.
    """
    try:
        with _store_conn() as conn:
            etat = lire_etat_ui_atelier_sequence(conn, sn_id)
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(etat)


@bp_v2_edition.route(
    "/api/v2/sequences-par-niveau/<sn_id>/etat-ui",
    methods=["PUT"],
)
def api_ecrire_etat_ui_atelier_sequence(sn_id: str):
    """Persiste l'objectif ouvert pour une séquence (UPSERT).

    Body JSON : {"objectif_ouvert_id": "ob_xxx" | null}.
    null = aucun objectif ouvert (mode liste des méthodes à gauche).
    """
    payload = request.get_json(silent=True) or {}
    # On accepte explicitement None : "objectif_ouvert_id" peut valoir null
    # en JSON. payload.get retourne None si absent OU si null.
    objectif_ouvert_id = payload.get("objectif_ouvert_id")
    try:
        with _store_conn() as conn:
            etat = ecrire_etat_ui_atelier_sequence(
                conn, sn_id, objectif_ouvert_id,
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(etat)


# ═════════════════════════════════════════════════════════════════════════════
# v0.10.1 — Création / suppression d'objectif simple
# ═════════════════════════════════════════════════════════════════════════════

@bp_v2_edition.route(
    "/api/v2/parties/<partie_id>/objectif",
    methods=["POST"],
)
def api_creer_objectif(partie_id: str):
    """Crée un objectif "simple" dans une partie, avec code auto-incrémenté.

    Body JSON (tous optionnels) :
      {
        "nom": "...",
        "methode_id": "me_xxx" | null,
        "critere_F": "...", "critere_A": "...", "critere_E": "..."
      }

    Le code est calculé automatiquement (convention '0X/1X/2X' selon la
    partie). Le premier code disponible est attribué.

    Cas d'usage principal : drop d'une méthode dans une partie depuis le
    nouvel atelier d'assemblage.

    Retour : structure complète de l'objectif créé.
    """
    payload = request.get_json(silent=True) or {}
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_partie(conn, partie_id)
            obj = creer_objectif_simple(
                conn,
                partie_id,
                nom=payload.get("nom") or "",
                methode_id=payload.get("methode_id") or None,
                critere_F=payload.get("critere_F") or "",
                critere_A=payload.get("critere_A") or "",
                critere_E=payload.get("critere_E") or "",
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(obj), 201


@bp_v2_edition.route(
    "/api/v2/objectifs/<objectif_id>",
    methods=["DELETE"],
)
def api_supprimer_objectif(objectif_id: str):
    """Supprime un objectif et ses dépendances (exos, notions, état UI).

    Retour : {"objectif_id", "supprime": True}.
    """
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable_par_objectif(conn, objectif_id)
            rep = supprimer_objectif(conn, objectif_id)
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)


# ═════════════════════════════════════════════════════════════════════════════
# v0.10.2 — Précédences au niveau séquence-niveau
# ═════════════════════════════════════════════════════════════════════════════

@bp_v2_edition.route(
    "/api/v2/sequences-par-niveau/<sn_id>/precedences",
    methods=["GET"],
)
def api_lister_precedences_sequence(sn_id: str):
    """Liste les précédences d'une séquence-niveau, dans l'ordre déclaré.

    Retour : {"sequence_par_niveau_id", "precedences": [{precedent_niveau,
              precedent_seq, ordre}, ...]}.
    """
    try:
        with _store_conn() as conn:
            precs = lister_precedences_sequence(conn, sn_id)
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify({
        "sequence_par_niveau_id": sn_id,
        "precedences": precs,
    })


@bp_v2_edition.route(
    "/api/v2/sequences-par-niveau/<sn_id>/precedences",
    methods=["POST"],
)
def api_ajouter_precedence_sequence(sn_id: str):
    """Ajoute une précédence à une séquence-niveau.

    Body JSON : {"precedent_niveau": "N10", "precedent_seq": "S03"}.

    Refuse :
      - 400 si champs vides (precedence_invalide)
      - 400 si pointeur circulaire (sn → sn) (precedence_invalide)
      - 409 si déjà présente (precedence_seq_deja_presente)

    Retour : {"sequence_par_niveau_id", "precedences": [...]} mise à jour.
    """
    payload = request.get_json(silent=True) or {}
    pn = payload.get("precedent_niveau", "")
    ps = payload.get("precedent_seq", "")
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable(conn, sn_id)
            precs = ajouter_precedence_sequence(conn, sn_id, pn, ps)
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify({
        "sequence_par_niveau_id": sn_id,
        "precedences": precs,
    }), 201


@bp_v2_edition.route(
    "/api/v2/sequences-par-niveau/<sn_id>/precedences"
    "/<precedent_niveau>/<precedent_seq>",
    methods=["DELETE"],
)
def api_retirer_precedence_sequence(
    sn_id: str, precedent_niveau: str, precedent_seq: str,
):
    """Retire une précédence. Recompacte les ordres."""
    try:
        with _store_conn() as conn:
            assert_sequence_modifiable(conn, sn_id)
            precs = retirer_precedence_sequence(
                conn, sn_id, precedent_niveau, precedent_seq,
            )
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify({
        "sequence_par_niveau_id": sn_id,
        "precedences": precs,
    })


# ── v0.16.9 — État validable de la séquence-niveau ──────────────────────────
#
# PATCH /api/v2/sequences-par-niveau/<sn_id>/etat  body {"etat_code": "valide"|"en_cours"}
#   - 'valide'   : déclenche le hook pédagogique strict (cf.
#                  _valider_sequence_hook). 400 + raisons si échec.
#   - 'en_cours' : dévalidation, toujours autorisée.
# Cette route NE POSE PAS assert_sequence_modifiable (elle doit pouvoir
# dévalider une séquence verrouillée).
@bp_v2_edition.route(
    "/api/v2/sequences-par-niveau/<sn_id>/etat", methods=["PATCH"],
)
def api_changer_etat_sequence(sn_id: str):
    body = request.get_json(silent=True) or {}
    nouvel_etat = body.get("etat_code")
    if not nouvel_etat:
        return jsonify({
            "error": "Champ 'etat_code' manquant.",
            "code": "etat_code_manquant",
        }), 400
    try:
        with _store_conn() as conn:
            rep = changer_etat_sequence_niveau(conn, sn_id, nouvel_etat)
    except V2EditionErreur as e:
        return _erreur(e)
    return jsonify(rep)
