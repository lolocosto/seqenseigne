"""
routes/evaluations.py — API REST des évaluations.

Endpoints implémentés (v0.13.5.2.4) :

  Évaluations
    GET    /api/evaluations?niveau=N10           → liste filtrée par niveau
    GET    /api/evaluations/<eval_id>            → détail
    POST   /api/evaluations                      → création
    PATCH  /api/evaluations/<eval_id>            → modification PATCH-like
    DELETE /api/evaluations/<eval_id>            → suppression
    POST   /api/evaluations/reordonner           → réordonnance d'un niveau

  Liaisons exos
    GET    /api/evaluations/<eval_id>/exos
    POST   /api/evaluations/<eval_id>/exos       → attache un exo
    DELETE /api/evaluations/<eval_id>/exos/<exo_id>
    PATCH  /api/evaluations/<eval_id>/exos/<exo_id>  → modifie barème
    POST   /api/evaluations/<eval_id>/exos/reordonner

  Liaisons objectifs (v0.13.5.2.2+)
    GET    /api/evaluations/<eval_id>/objectifs
    POST   /api/evaluations/<eval_id>/objectifs
    DELETE /api/evaluations/<eval_id>/objectifs/<obj_id>

  Transitions d'état (v0.13.5.2.2+)
    POST   /api/evaluations/<eval_id>/valider    → en_cours → valide (contrôlé)
    POST   /api/evaluations/<eval_id>/devalider  → valide → en_cours (libre)

  Couverture (v0.13.5.2.2+)
    GET    /api/evaluations/<eval_id>/couverture → matrice creuse obj × exos

  Aides pour l'UI (lecture seule)
    GET    /api/evaluations/niveau/<niveau>/exos-disponibles
           → liste des exos du niveau, groupés par séquence, pour le sélecteur
    GET    /api/evaluations/niveau/<niveau>/objectifs-disponibles
           → liste des objectifs du niveau, groupés par séquence, pour le sélecteur

Pattern d'erreurs : les services lèvent des exceptions héritant de
`EvaluationErreur` qui portent un code stable. La route mappe ce code
vers un statut HTTP via `_CODE_HTTP`. Pour `ValidationPedagogiqueErreur`,
on expose en plus le champ `details.raisons` pour permettre à l'UI de
cibler les éléments fautifs.
"""

import sqlite3
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app, Response

from services import evaluations as svc
from services.evaluations import EvaluationErreur

bp = Blueprint("evaluations", __name__)


def _store():
    return current_app.json_store


# ── Mapping erreurs métier → codes HTTP ──────────────────────────────────────
#
# Chaque exception du service `evaluations.py` porte un `code` stable.
# Ce mapping centralise la traduction en code HTTP, conformément au
# pattern `CONVENTIONS.md` section 2 "Hiérarchie d'exceptions par
# domaine". Les codes absents tombent en 400 par défaut.

_CODE_HTTP = {
    # 404 Not Found
    "evaluation_introuvable":              404,
    "exo_introuvable_dans_evaluation":     404,
    "objectif_introuvable_dans_evaluation": 404,
    "objectif_introuvable":                404,
    "exercice_introuvable":                404,

    # 409 Conflict
    "numero_deja_utilise":                 409,
    "exo_deja_present":                    409,
    "objectif_deja_present":               409,
    "objectif_niveau_incoherent":          409,
    "reordonnancement_invalide":           409,
    "deja_valide":                         409,
    "deja_en_cours":                       409,
    "item_verrouille":                     409,   # v0.16.4

    # 400 Bad Request
    "mode_notation_invalide":              400,
    "etat_code_invalide":                  400,
    "item_langue_francaise_invalide":      400,
    "validation_pedagogique_echouee":      400,
}


def _erreur_metier(e: EvaluationErreur):
    """Convertit une exception EvaluationErreur en réponse JSON Flask.

    Format : { "error": <message>, "code": <code_stable>, "details": {…} }
    Le frontend peut s'appuyer sur `code` (stable) plutôt que sur le
    message (qui peut évoluer).
    """
    statut = _CODE_HTTP.get(e.code, 400)
    return jsonify({
        "error":   str(e),
        "code":    e.code,
        "details": e.details,
    }), statut


def _assert_eval_modifiable(conn, eval_id):
    """v0.16.4 — Lève une réponse 409 si l'évaluation est validée.

    Garde « validé = lecture seule » (défense en profondeur). À appeler en
    début des routes qui MODIFIENT le contenu d'une évaluation (champs, exos,
    objectifs, barèmes). NE PAS appeler sur /valider, /devalider (la sortie),
    ni sur la suppression (autorisée après confirmation UI).

    Retourne None si modifiable, ou un tuple (response, 409) à renvoyer tel
    quel par la route si verrouillé. Si l'éval est introuvable, retourne None
    (la route renverra son propre 404).
    """
    try:
        ev = svc.lire_evaluation(conn, eval_id)
    except EvaluationErreur:
        return None
    if ev.get("etat_code") == "valide":
        return jsonify({
            "error": ("L'évaluation est validée (lecture seule). "
                      "Repassez-la en cours pour la modifier."),
            "code":  "item_verrouille",
            "details": {"evaluation_id": eval_id},
        }), 409
    return None


# ═════════════════════════════════════════════════════════════════════════════
# Évaluations — CRUD
# ═════════════════════════════════════════════════════════════════════════════


@bp.route("/api/evaluations", methods=["GET"])
def api_lister():
    """Liste les évaluations.

    Query :
      niveau (optionnel) : filtre par niveau (N09..N12).
    """
    niveau = (request.args.get("niveau") or "").strip() or None
    store = _store()
    with store._conn() as conn:
        evals = svc.lister_evaluations(conn, niveau=niveau)
    return jsonify({"evaluations": evals})


@bp.route("/api/evaluations/<eval_id>", methods=["GET"])
def api_lire(eval_id):
    store = _store()
    with store._conn() as conn:
        try:
            ev = svc.lire_evaluation(conn, eval_id)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return jsonify({"evaluation": ev})


@bp.route("/api/evaluations", methods=["POST"])
def api_creer():
    """Crée une évaluation. Body JSON :
       { niveau, titre?, mode_notation?, afficher_bareme_dans_exos?,
         item_langue_francaise? }
    """
    body = request.get_json(silent=True) or {}
    niveau = (body.get("niveau") or "").strip()
    if not niveau:
        return jsonify({"error": "Champ 'niveau' manquant."}), 400

    # Construire le kwargs : on passe à creer_evaluation tous les champs
    # fournis (les autres prennent leur défaut côté service).
    kwargs = {"niveau": niveau, "titre": (body.get("titre") or "").strip()}
    for champ in ("mode_notation", "afficher_bareme_dans_exos",
                  "item_langue_francaise"):
        if champ in body:
            kwargs[champ] = body[champ]

    store = _store()
    with store._conn() as conn:
        try:
            ev = svc.creer_evaluation(conn, **kwargs)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return jsonify({"evaluation": ev}), 201


@bp.route("/api/evaluations/<eval_id>", methods=["PATCH"])
def api_modifier(eval_id):
    """Modifie une évaluation. Body JSON : champs à modifier
    (titre, mode_notation, afficher_bareme_dans_exos,
     item_langue_francaise, etat_code).

    Note : `etat_code` peut être modifié librement ici (héritage
    compatibilité). Les transitions contrôlées passent par les endpoints
    /valider et /devalider qui exposent les contrôles métier.
    """
    body = request.get_json(silent=True) or {}
    # Sélectionner uniquement les champs modifiables
    kwargs = {}
    for champ in ("titre", "mode_notation", "afficher_bareme_dans_exos",
                  "item_langue_francaise", "etat_code"):
        if champ in body:
            kwargs[champ] = body[champ]

    if not kwargs:
        return jsonify({"error": "Aucun champ à modifier."}), 400

    store = _store()
    with store._conn() as conn:
        # v0.16.4 — Si l'éval est validée, on refuse toute modification de
        # CONTENU. Exception : un PATCH qui ne touche QUE `etat_code` est en
        # fait une (dé)validation → autorisé (c'est la sortie du verrou).
        champs_contenu = set(kwargs) - {"etat_code"}
        if champs_contenu:
            verrou = _assert_eval_modifiable(conn, eval_id)
            if verrou is not None:
                return verrou
        try:
            ev = svc.modifier_evaluation(conn, eval_id, **kwargs)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return jsonify({"evaluation": ev})


@bp.route("/api/evaluations/<eval_id>", methods=["DELETE"])
def api_supprimer(eval_id):
    store = _store()
    with store._conn() as conn:
        try:
            svc.supprimer_evaluation(conn, eval_id)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return "", 204


@bp.route("/api/evaluations/reordonner", methods=["POST"])
def api_reordonner_evaluations():
    """Body JSON : { niveau, ordre: [eval_id_1, eval_id_2, ...] }."""
    body = request.get_json(silent=True) or {}
    niveau = (body.get("niveau") or "").strip()
    ordre = body.get("ordre")
    if not niveau or not isinstance(ordre, list):
        return jsonify({
            "error": "Champs requis : niveau (str), ordre (liste d'IDs)."
        }), 400

    store = _store()
    with store._conn() as conn:
        try:
            svc.reordonner_evaluations(conn, niveau, ordre)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return "", 204


# ═════════════════════════════════════════════════════════════════════════════
# Liaisons éval ↔ exercices
# ═════════════════════════════════════════════════════════════════════════════


@bp.route("/api/evaluations/<eval_id>/exos", methods=["GET"])
def api_lister_exos(eval_id):
    store = _store()
    with store._conn() as conn:
        try:
            exos = svc.lister_exos_evaluation(conn, eval_id)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return jsonify({"exos": exos})


@bp.route("/api/evaluations/<eval_id>/exos", methods=["POST"])
def api_ajouter_exo(eval_id):
    """Body JSON : { exercice_id, bareme_points?, bareme_qcm_ok?,
                     bareme_qcm_partiel?, bareme_qcm_ko? }
    """
    body = request.get_json(silent=True) or {}
    exo_id = (body.get("exercice_id") or "").strip()
    if not exo_id:
        return jsonify({"error": "Champ 'exercice_id' manquant."}), 400

    kwargs = {}
    for champ in ("bareme_points", "bareme_qcm_ok",
                  "bareme_qcm_partiel", "bareme_qcm_ko"):
        if champ in body:
            kwargs[champ] = body[champ]

    store = _store()
    with store._conn() as conn:
        verrou = _assert_eval_modifiable(conn, eval_id)
        if verrou is not None:
            return verrou
        try:
            res = svc.ajouter_exo_a_evaluation(conn, eval_id, exo_id, **kwargs)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return jsonify(res), 201


@bp.route("/api/evaluations/<eval_id>/exos/<exo_id>", methods=["DELETE"])
def api_retirer_exo(eval_id, exo_id):
    store = _store()
    with store._conn() as conn:
        verrou = _assert_eval_modifiable(conn, eval_id)
        if verrou is not None:
            return verrou
        try:
            svc.retirer_exo_de_evaluation(conn, eval_id, exo_id)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return "", 204


@bp.route("/api/evaluations/<eval_id>/exos/<exo_id>", methods=["PATCH"])
def api_modifier_bareme(eval_id, exo_id):
    """Body JSON : { bareme_points?, bareme_qcm_ok?, ... }
    Valeur null → barème effacé (NULL en BDD).
    """
    body = request.get_json(silent=True) or {}
    kwargs = {}
    for champ in ("bareme_points", "bareme_qcm_ok",
                  "bareme_qcm_partiel", "bareme_qcm_ko"):
        if champ in body:
            kwargs[champ] = body[champ]

    if not kwargs:
        return jsonify({"error": "Aucun barème à modifier."}), 400

    store = _store()
    with store._conn() as conn:
        verrou = _assert_eval_modifiable(conn, eval_id)
        if verrou is not None:
            return verrou
        try:
            res = svc.modifier_bareme_exo(conn, eval_id, exo_id, **kwargs)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return jsonify(res)


@bp.route("/api/evaluations/<eval_id>/baremes", methods=["PATCH"])
def api_modifier_baremes_groupes(eval_id):
    """v0.16.3 — Endpoint barèmes GROUPÉS (régime de persistance mixte 2b).

    À l'« Enregistrer » d'une évaluation, tous les barèmes modifiés sont
    poussés en un seul appel, au lieu d'un PATCH par exo à la frappe.

    Body JSON : { baremes: [ { exercice_id, bareme_points?, bareme_qcm_ok?,
                               bareme_qcm_partiel?, bareme_qcm_ko? }, ... ] }
    Valeur null → barème effacé. Chemin distinct de /exos/<exo_id> pour ne
    pas être capté par cette route (exo_id='baremes').
    """
    body = request.get_json(silent=True) or {}
    baremes = body.get("baremes")
    if not isinstance(baremes, list):
        return jsonify({"error": "Champ 'baremes' (liste) requis."}), 400

    resultats = []
    store = _store()
    with store._conn() as conn:
        verrou = _assert_eval_modifiable(conn, eval_id)
        if verrou is not None:
            return verrou
        try:
            for entree in baremes:
                if not isinstance(entree, dict) or "exercice_id" not in entree:
                    return jsonify({
                        "error": "Chaque entrée doit avoir un 'exercice_id'."
                    }), 400
                exo_id = entree["exercice_id"]
                kwargs = {}
                for champ in ("bareme_points", "bareme_qcm_ok",
                              "bareme_qcm_partiel", "bareme_qcm_ko"):
                    if champ in entree:
                        kwargs[champ] = entree[champ]
                if kwargs:
                    res = svc.modifier_bareme_exo(conn, eval_id, exo_id, **kwargs)
                    resultats.append(res)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return jsonify({"baremes": resultats})


@bp.route("/api/evaluations/<eval_id>/exos/reordonner", methods=["POST"])
def api_reordonner_exos(eval_id):
    """Body JSON : { ordre: [exo_id_1, exo_id_2, ...] }."""
    body = request.get_json(silent=True) or {}
    ordre = body.get("ordre")
    if not isinstance(ordre, list):
        return jsonify({"error": "Champ 'ordre' (liste d'IDs) requis."}), 400

    store = _store()
    with store._conn() as conn:
        verrou = _assert_eval_modifiable(conn, eval_id)
        if verrou is not None:
            return verrou
        try:
            svc.reordonner_exos_evaluation(conn, eval_id, ordre)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return "", 204


# ═════════════════════════════════════════════════════════════════════════════
# Liaisons éval ↔ objectifs (v0.13.5.2.2)
# ═════════════════════════════════════════════════════════════════════════════


@bp.route("/api/evaluations/<eval_id>/objectifs", methods=["GET"])
def api_lister_objectifs(eval_id):
    store = _store()
    with store._conn() as conn:
        try:
            objs = svc.lister_objectifs_evaluation(conn, eval_id)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return jsonify({"objectifs": objs})


@bp.route("/api/evaluations/<eval_id>/objectifs", methods=["POST"])
def api_ajouter_objectif(eval_id):
    """Body JSON : { objectif_id }."""
    body = request.get_json(silent=True) or {}
    obj_id = (body.get("objectif_id") or "").strip()
    if not obj_id:
        return jsonify({"error": "Champ 'objectif_id' manquant."}), 400

    store = _store()
    with store._conn() as conn:
        verrou = _assert_eval_modifiable(conn, eval_id)
        if verrou is not None:
            return verrou
        try:
            res = svc.ajouter_objectif_a_evaluation(conn, eval_id, obj_id)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return jsonify(res), 201


@bp.route("/api/evaluations/<eval_id>/objectifs/<obj_id>", methods=["DELETE"])
def api_retirer_objectif(eval_id, obj_id):
    store = _store()
    with store._conn() as conn:
        verrou = _assert_eval_modifiable(conn, eval_id)
        if verrou is not None:
            return verrou
        try:
            svc.retirer_objectif_de_evaluation(conn, eval_id, obj_id)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return "", 204


# ═════════════════════════════════════════════════════════════════════════════
# Transitions d'état pédagogique (v0.13.5.2.2)
# ═════════════════════════════════════════════════════════════════════════════


@bp.route("/api/evaluations/<eval_id>/valider", methods=["POST"])
def api_valider(eval_id):
    """Tente la transition en_cours → valide avec contrôles métier.

    En cas d'échec de la validation pédagogique (barèmes manquants, etc.),
    retourne 400 avec `details.raisons` détaillant chaque manquement,
    permettant à l'UI de cibler les cellules fautives.
    """
    store = _store()
    with store._conn() as conn:
        try:
            ev = svc.valider_evaluation(conn, eval_id)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return jsonify({"evaluation": ev})


@bp.route("/api/evaluations/<eval_id>/devalider", methods=["POST"])
def api_devalider(eval_id):
    """Dévalidation libre valide → en_cours (cohérent pattern etats_edition)."""
    store = _store()
    with store._conn() as conn:
        try:
            ev = svc.devalider_evaluation(conn, eval_id)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return jsonify({"evaluation": ev})


# ═════════════════════════════════════════════════════════════════════════════
# Couverture (matrice objectifs × exos)
# ═════════════════════════════════════════════════════════════════════════════


@bp.route("/api/evaluations/<eval_id>/couverture", methods=["GET"])
def api_couverture(eval_id):
    store = _store()
    with store._conn() as conn:
        try:
            res = svc.calculer_couverture(conn, eval_id)
        except EvaluationErreur as e:
            return _erreur_metier(e)
    return jsonify(res)


# ═════════════════════════════════════════════════════════════════════════════
# Aides pour l'UI : sélecteurs exos et objectifs disponibles par niveau
# ═════════════════════════════════════════════════════════════════════════════


@bp.route("/api/evaluations/niveau/<niveau>/exos-disponibles", methods=["GET"])
def api_exos_disponibles(niveau):
    """Renvoie les exos d'un niveau, groupés par séquence, pour le
    sélecteur (mini-formulaire inline « + Ajouter un exercice »).

    On expose `id`, `nom`, `serie`, `type_format`, le `sequence_code`
    déduit, ainsi que `niveau`, `serie_code` et `num` qui permettent
    à l'UI de construire le label métier `N10/S01/F01` dans le
    dropdown (v0.13.5.3 : correction du résidu v25 où ce label
    n'apparaissait que `?`).

    L'absence de jointure directe exo→séquence (les exos sont
    génériques) impose de passer par leur attachement via les parties
    (objectif_exos → objectifs → sequence_parties →
    sequences_par_niveau).
    """
    store = _store()
    with store._conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT e.id, e.titre, e.serie, e.type_format, "
            "       e.niveau, e.serie_code, e.num, "
            "       spn.sequence_code "
            "FROM exercices AS e "
            "JOIN objectif_exos AS oe ON oe.exercice_id = e.id "
            "JOIN objectifs AS o ON o.id = oe.objectif_id "
            "JOIN sequence_parties AS sp ON sp.id = o.partie_id "
            "JOIN sequences_par_niveau AS spn "
            "       ON spn.id = sp.sequence_par_niveau_id "
            "WHERE spn.niveau = ? "
            "ORDER BY spn.sequence_code, e.serie, e.titre",
            (niveau,),
        ).fetchall()

    # Grouper par séquence pour l'UI
    par_sequence = {}
    for r in rows:
        seq = r["sequence_code"]
        par_sequence.setdefault(seq, []).append({
            "id":          r["id"],
            "titre":       r["titre"],
            "serie":       r["serie"],
            "type_format": r["type_format"] or "standard",
            # v0.13.5.3 — Champs pour le label métier N10/S01/F01.
            # Note : `sequence` dans le payload côté UI = `sequence_code`
            # de la jointure (pas e.sequence qui n'est pas garanti
            # cohérent pour un exo cross-séquence). On utilise
            # sequence_code comme source de vérité de l'attachement.
            "niveau":      r["niveau"]     or "",
            "sequence":    seq             or "",
            "serie_code":  r["serie_code"] or "",
            "num":         r["num"],
        })

    return jsonify({"niveau": niveau, "par_sequence": par_sequence})


@bp.route("/api/evaluations/niveau/<niveau>/objectifs-disponibles",
          methods=["GET"])
def api_objectifs_disponibles(niveau):
    """Renvoie les objectifs d'un niveau, groupés par séquence puis
    par partie, pour le sélecteur « + Ajouter un objectif »."""
    store = _store()
    with store._conn() as conn:
        rows = conn.execute(
            "SELECT o.id, o.code, o.nom, o.fin_cycle, "
            "       sp.numero AS partie_numero, "
            "       spn.sequence_code "
            "FROM objectifs AS o "
            "JOIN sequence_parties AS sp ON sp.id = o.partie_id "
            "JOIN sequences_par_niveau AS spn "
            "       ON spn.id = sp.sequence_par_niveau_id "
            "WHERE spn.niveau = ? "
            "ORDER BY spn.sequence_code, sp.numero, o.code",
            (niveau,),
        ).fetchall()

    par_sequence = {}
    for r in rows:
        seq = r["sequence_code"]
        par_sequence.setdefault(seq, []).append({
            "id":            r["id"],
            "code":          r["code"],
            "nom":           r["nom"],
            "fin_cycle":     r["fin_cycle"],
            "partie_numero": r["partie_numero"],
        })

    return jsonify({"niveau": niveau, "par_sequence": par_sequence})


# ── Rendu .tex et .pdf (v0.13.5.3) ───────────────────────────────────────────
#
# Pattern strictement aligné sur routes/rendu_atome.py pour cohérence
# du pipeline de compilation. Les services réutilisés :
#   - services.render_evaluation.generer_tex_evaluation pour le .tex
#   - services.compilateur_pdf.compiler_atome pour la compilation (le
#     nom historique est `compiler_atome` mais il prend juste un .tex en
#     entrée — pas de couplage type d'atome)
#
# Cf. doc/finalisation_paquet_v0_13_5_2.md pour le contrat des macros
# côté paquet seqenseigne-core-eval.


def _configuration():
    """Accès à la configuration utilisateur (mis en cache sur app).
    Pattern identique à routes/rendu_atome.py."""
    from services.configuration import Configuration
    if not hasattr(current_app, 'configuration'):
        current_app.configuration = Configuration(
            current_app.json_store.data_dir
        )
    return current_app.configuration


def _cache_dir():
    """Dossier de cache des PDFs rendus (partagé avec les atomes)."""
    return current_app.json_store.data_dir / 'cache_rendus'


def _racine_appli():
    """Racine de l'appli (pour détection MiKTeX portable)."""
    return Path(current_app.root_path)


@bp.route('/api/evaluations/<eval_id>/rendu-tex', methods=['GET'])
def api_eval_rendu_tex(eval_id: str):
    """Renvoie le .tex source qui serait compilé pour cette éval.

    Utile pour le bouton « LaTeX généré » de l'atelier, et pour le
    debug en cas d'erreur de compilation.

    Réponses :
      200 text/plain      : contenu .tex
      404 JSON            : évaluation introuvable
    """
    from services.render_evaluation import generer_tex_evaluation

    config = _configuration()
    store = _store()
    try:
        with store._conn() as conn:
            tex = generer_tex_evaluation(
                conn, eval_id,
                tikz_libraries=config.tikz_libraries(),
                tblr_libraries=config.tblr_libraries(),
            )
    except svc.EvaluationIntrouvable:
        return jsonify({'error': 'evaluation_introuvable', 'id': eval_id}), 404

    return Response(tex, mimetype='text/plain')


@bp.route('/api/evaluations/<eval_id>/rendu-pdf', methods=['POST'])
def api_eval_rendu_pdf(eval_id: str):
    """Compile l'éval et renvoie le PDF.

    Réponses :
      200 application/pdf : PDF compilé (ou servi depuis le cache)
      404 JSON            : éval introuvable
      422 JSON            : compilation échouée, détail des erreurs
      503 JSON            : pdflatex introuvable ou timeout
    """
    from services.render_evaluation import generer_tex_evaluation
    from services.compilateur_pdf import compiler_atome

    config = _configuration()
    racine_sources = config.chemin_sources_livrets()
    dossier_images = Path(current_app.json_store.data_dir) / 'images'

    # 1. Génération du .tex
    store = _store()
    try:
        with store._conn() as conn:
            tex = generer_tex_evaluation(
                conn, eval_id,
                tikz_libraries=config.tikz_libraries(),
                tblr_libraries=config.tblr_libraries(),
            )
    except svc.EvaluationIntrouvable:
        return jsonify({'error': 'evaluation_introuvable', 'id': eval_id}), 404

    # 2. Compilation (compiler_atome est générique : prend un .tex, sort un PDF)
    resultat = compiler_atome(
        tex_source=tex,
        racine_sources=racine_sources,
        cache_dir=_cache_dir(),
        pdflatex=config.chemin_pdflatex(),
        racine_appli=_racine_appli(),
        timeout=config.timeout_compilation_court(),
        dossier_images=dossier_images if dossier_images.is_dir() else None,
    )

    if resultat.ok:
        return Response(
            resultat.pdf_bytes,
            mimetype='application/pdf',
            headers={
                'X-Seq-Depuis-Cache': '1' if resultat.depuis_cache else '0',
                'X-Seq-Duree-Ms': str(resultat.duree_ms),
            },
        )

    # 3. Échec : distinguer infrastructure vs erreur de code LaTeX
    msg_principal = (
        resultat.erreurs[0].message if resultat.erreurs
        else 'Erreur inconnue de compilation.'
    )
    code_http = 422
    if 'pdflatex introuvable' in msg_principal.lower():
        code_http = 503
    elif 'timeout' in msg_principal.lower():
        code_http = 503

    return jsonify({
        'error': 'compilation_echouee',
        'message': msg_principal,
        'erreurs': [
            {
                'ligne':    e.ligne,
                'message':  e.message,
                'contexte': e.contexte,
            }
            for e in resultat.erreurs
        ],
        # v0.13.5.4 — Log complet exposé pour le diagnostic, comme dans
        # routes/recap_cours.py et routes/livret_sequence.py. L'UI ne
        # l'utilise pas directement (elle charge le .tex via rendu-tex
        # au clic sur "Voir le .tex brut") mais peut servir si on veut
        # afficher aussi le log plus tard.
        'log_complet': resultat.log_complet,
        'duree_ms': resultat.duree_ms,
    }), code_http
