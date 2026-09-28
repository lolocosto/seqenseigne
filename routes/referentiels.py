"""
routes/referentiels.py — API REST des référentiels de niveau.

Endpoints :
  GET    /api/referentiels?niveau=N10
        → liste triée par version décroissante.
  POST   /api/referentiels/coquille  body {niveau, description?}
        → crée une coquille en_cours (v0.13.5.1).
  DELETE /api/referentiels/<ref_id>
        → supprime un référentiel en_cours uniquement (v0.13.5.1).
  POST   /api/referentiels/<ref_id>/figer  body {force_confirme: bool}
        → fait passer un valide à fige, écarte les concurrents (v0.13.5.1
          minimal : sans compilation PDF, voir v0.13.5.3 pour effets complets).
  GET    /api/referentiels/<ref_id>/arbre
        → arbre séquence → partie → objectif → atomes du niveau du
          référentiel, pour le tableau de bord de l'atelier (v0.13.5.1).
"""

import sqlite3

from flask import Blueprint, request, jsonify, current_app

from services import referentiels as svc

bp = Blueprint("referentiels", __name__)


def _store():
    return current_app.json_store


# Note : SqliteStore._conn() est un context manager (@contextmanager).
# Les routes ci-dessous l'utilisent via `with store._conn() as conn:`
# pour récupérer la vraie connection sqlite3.


# ── Lister ────────────────────────────────────────────────────────────────────

@bp.route("/api/referentiels", methods=["GET"])
def api_lister():
    """
    Liste les référentiels.
    Query :
      niveau (optionnel) : filtre par niveau (N10, N11, N12…).
                           Si absent, retourne la liste complète.
      etats  (optionnel) : liste d'états séparés par des virgules
                           (ex. `verrouille,utilise`). Si présent, ne
                           retourne que les référentiels dont l'état est
                           dans cette liste. Utilisé par l'atelier
                           Progression (v0.19.1) qui ne peut s'appuyer que
                           sur des référentiels `verrouille` ou `utilise`.
    Retour : { referentiels: [{id, niveau, version, description, etat,
                                date_debut, date_fin}, ...] }
    Le plus récent (version décroissante) est en tête pour chaque niveau.
    """
    niveau = request.args.get("niveau", "").strip()
    etats_param = request.args.get("etats", "").strip()
    # Ensemble d'états autorisés (vide → pas de filtre par état).
    etats_filtre = {
        e.strip() for e in etats_param.split(",") if e.strip()
    } if etats_param else None
    store = _store()

    if niveau:
        refs = svc.lister_par_niveau(store, niveau)
    else:
        tous = list(store.lister_referentiels())
        tous.sort(key=lambda r: (r.get("niveau", ""),
                                 r.get("version", "")),
                  reverse=False)
        tous.sort(key=lambda r: (r.get("niveau", ""),
                                 -int(r.get("version") or "0")
                                   if (r.get("version") or "").isdigit()
                                   else 0))
        refs = [
            {"id":          r.get("id"),
             "niveau":      r.get("niveau"),
             "version":     r.get("version"),
             "description": r.get("description", ""),
             "etat":        r.get("etat", ""),
             "date_debut":  r.get("date_debut"),
             "date_fin":    r.get("date_fin")}
            for r in tous
        ]

    # v0.19.1 — Filtre par état (post-filtrage, après l'éventuelle maj lazy
    # de lister_par_niveau, pour que les états reflètent l'éligibilité courante).
    if etats_filtre is not None:
        refs = [r for r in refs if r.get("etat", "") in etats_filtre]

    return jsonify({"referentiels": refs})


# ── v0.13.5.1 — Création coquille ─────────────────────────────────────────────

@bp.route("/api/referentiels/coquille", methods=["POST"])
def api_creer_coquille():
    """
    Crée une coquille de référentiel à l'état `en_cours`.
    Body JSON : { niveau: str, description?: str }
    Retour : 201 + { ref: {id, niveau, version, etat, ...} }
             400 si niveau manquant.
             409 si conflit unique (cas extrême : >25 référentiels même
                  niveau-année).
    """
    body = request.get_json(silent=True) or {}
    niveau = (body.get("niveau") or "").strip()
    description = (body.get("description") or "").strip()

    if not niveau:
        return jsonify({"error": "niveau obligatoire"}), 400

    store = _store()
    if not hasattr(store, "_conn"):
        return jsonify({"error": "store non SQLite"}), 500

    with store._conn() as conn:
        try:
            ref = svc.creer_coquille(conn, niveau, description)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 409
        except sqlite3.IntegrityError as e:
            return jsonify({"error": f"conflit BDD : {e}"}), 409

    return jsonify({"ref": ref}), 201


# ── v0.13.5.1 — Suppression ──────────────────────────────────────────────────

@bp.route("/api/referentiels/<ref_id>", methods=["DELETE"])
def api_supprimer(ref_id):
    """
    Supprime un référentiel `en_cours`. Refuse les autres états.
    Retour : 204 si OK.
             404 si introuvable.
             409 si l'état n'est pas `en_cours`.
    """
    store = _store()
    if not hasattr(store, "_conn"):
        return jsonify({"error": "store non SQLite"}), 500

    with store._conn() as conn:
        try:
            svc.supprimer(conn, ref_id)
        except ValueError as e:
            msg = str(e)
            if "introuvable" in msg.lower():
                return jsonify({"error": msg}), 404
            return jsonify({"error": msg}), 409

    return "", 204


# ── v0.13.5.1 — Figer (transition d'état seule, pas de PDF) ──────────────────

@bp.route("/api/referentiels/<ref_id>/verrouiller", methods=["POST"])
@bp.route("/api/referentiels/<ref_id>/figer", methods=["POST"])
def api_verrouiller(ref_id):
    """v0.15.3 — Verrouille un référentiel `valide` (transition vers
    `verrouille`).

    L'ancien endpoint `/figer` est conservé en alias rétro-compat
    (Flask permet plusieurs URLs sur une même vue).

    1. Vérifie l'éligibilité (atomes/évals/docs).
    2. Liste les concurrents ; si présents et `force_confirme=False`,
       retourne `confirmation_requise: True` sans rien modifier.
    3. Génère la trace JSON dans `<ref>/_verrouille/trace.json`.
    4. Copie les PDF actifs dans `<ref>/_verrouille/pdfs/`.
    5. Annule les concurrents et passe le référentiel à `verrouille`
       + date_debut.

    Body JSON : { force_confirme?: bool }  default False.
    Retour :
      - 200 + {confirmation_requise: True, concurrents: [...]} si
        concurrents détectés et force_confirme=False.
      - 200 + {confirmation_requise: False, ref: {...},
               concurrents_annules: [...],
               verrouille: {dossier, trace, nb_pdfs_copies,
                            echecs_copie}} sinon.
      - 404 si introuvable.
      - 409 si état pas `valide` OU si non éligible (raisons remontées).
    """
    body = request.get_json(silent=True) or {}
    force_confirme = bool(body.get("force_confirme", False))

    store = _store()
    if not hasattr(store, "_conn"):
        return jsonify({"error": "store non SQLite"}), 500

    from services.referentiel_figeage import verrouiller_complet
    from services.referentiel_documents_compilation import (
        _dossier_du_referentiel, lister_cibles_document,
    )

    with store._conn() as conn:
        try:
            res = verrouiller_complet(
                conn, ref_id,
                dossier_referentiel=_dossier_du_referentiel(store, ref_id),
                lister_cibles=lister_cibles_document,
                force_confirme=force_confirme,
            )
        except ValueError as e:
            msg = str(e)
            if "introuvable" in msg.lower():
                return jsonify({"error": msg}), 404
            return jsonify({"error": msg}), 409

    return jsonify(res), 200


@bp.route("/api/referentiels/<ref_id>/deverrouiller", methods=["POST"])
def api_deverrouiller(ref_id):
    """v0.15.3 — Déverrouille un référentiel `verrouille` (transition
    vers `valide`).

    Action utilisateur (bouton « Déverrouiller » côté UI). Le dossier
    `_verrouille/` est conservé pour permettre un re-verrouillage rapide
    à l'identique. Il sera écrasé au prochain verrouillage.

    Refus si l'état n'est pas exactement `verrouille` (par exemple
    `utilise` : on ne peut pas déverrouiller si le référentiel est
    déjà attaché à au moins une progression).

    Retour :
      - 200 + {ref: {id, niveau, version, etat: 'valide'}}.
      - 404 si introuvable.
      - 409 si état différent de `verrouille`.
    """
    store = _store()
    if not hasattr(store, "_conn"):
        return jsonify({"error": "store non SQLite"}), 500

    with store._conn() as conn:
        try:
            res = svc.deverrouiller(conn, ref_id)
        except ValueError as e:
            msg = str(e)
            if "introuvable" in msg.lower():
                return jsonify({"error": msg}), 404
            return jsonify({"error": msg}), 409
    return jsonify(res), 200


# ── v0.15.3 — Lecture des données verrouillées ──────────────────────────────


@bp.route("/api/referentiels/<ref_id>/trace", methods=["GET"])
def api_trace_verrouillee(ref_id):
    """v0.15.3 — Retourne la trace JSON d'un référentiel verrouillé.

    Lit le fichier `data/referentiels/<ref_id>/_verrouille/trace.json`.

    Retour :
      - 200 + le contenu JSON brut (mime application/json) si trouvé.
      - 404 si référentiel introuvable OU si pas encore verrouillé
        (dossier `_verrouille/` absent).
    """
    import json as _json
    store = _store()
    if not hasattr(store, "_conn"):
        return jsonify({"error": "store non SQLite"}), 500

    from services.referentiel_documents_compilation import (
        _dossier_du_referentiel,
    )
    with store._conn() as conn:
        row = conn.execute(
            "SELECT id FROM referentiel_niveaux WHERE id = ?", (ref_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error":
                            f"référentiel introuvable : {ref_id}"}), 404
        chemin = (_dossier_du_referentiel(store, ref_id)
                  / "_verrouille" / "trace.json")
        if not chemin.is_file():
            return jsonify({"error":
                            "trace verrouillée absente (référentiel "
                            "pas encore verrouillé ?)"}), 404
        try:
            trace = _json.loads(chemin.read_text(encoding="utf-8"))
        except Exception as e:
            return jsonify({"error":
                            f"trace illisible : {e}"}), 500
    return jsonify(trace), 200


@bp.route("/api/referentiels/<ref_id>/pdf/<nom_fichier>", methods=["GET"])
def api_pdf_verrouille(ref_id, nom_fichier):
    """v0.15.3 — Sert un PDF figé d'un référentiel verrouillé.

    Lit `data/referentiels/<ref_id>/_verrouille/pdfs/<nom_fichier>` et
    le sert tel quel.

    `nom_fichier` est restreint au pattern PDF métier seqenseigne
    (lettres, chiffres, underscores, point, `.pdf` à la fin) — pas de
    chemin relatif, pas de slash, par sécurité (anti-path-traversal).

    Retour :
      - 200 + body PDF (mime application/pdf).
      - 400 si nom_fichier invalide.
      - 404 si fichier absent.
    """
    import re as _re
    from flask import send_file

    # Anti path-traversal : nom autorisé = caractères alphanumériques,
    # underscores, tirets, point final `.pdf`.
    if not _re.match(r'^[A-Za-z0-9_\-]+\.pdf$', nom_fichier):
        return jsonify({"error": "nom de fichier invalide"}), 400

    store = _store()
    if not hasattr(store, "_conn"):
        return jsonify({"error": "store non SQLite"}), 500

    from services.referentiel_documents_compilation import (
        _dossier_du_referentiel,
    )
    chemin = (_dossier_du_referentiel(store, ref_id)
              / "_verrouille" / "pdfs" / nom_fichier)
    if not chemin.is_file():
        return jsonify({"error":
                        f"PDF verrouillé introuvable : {nom_fichier}"}), 404
    return send_file(chemin, mimetype="application/pdf",
                     as_attachment=False, download_name=nom_fichier)


# ── v0.13.5.1 — Arbre du niveau pour tableau de bord ─────────────────────────

@bp.route("/api/referentiels/<ref_id>/arbre", methods=["GET"])
def api_arbre(ref_id):
    """
    Retourne l'arbre séquence → partie → objectif → atomes pour le
    niveau du référentiel donné, pour alimenter le tableau de bord de
    l'atelier Référentiel.

    Lit les tables actives. Le contenu retourné reflète l'état courant
    de la BDD active, indépendamment de l'état du référentiel.

    Retour : { ref: {id, niveau, version, etat}, arbre: {...} }
             404 si référentiel introuvable.
    """
    store = _store()
    if not hasattr(store, "_conn"):
        return jsonify({"error": "store non SQLite"}), 500

    with store._conn() as conn:
        row = conn.execute(
            "SELECT id, niveau, version, etat "
            "FROM referentiel_niveaux WHERE id = ?",
            (ref_id,),
        ).fetchone()
        if row is None:
            return jsonify({"error": f"référentiel introuvable : {ref_id}"}), 404
        niveau = row["niveau"]
        arbre = svc.arbre_du_niveau(conn, niveau)

        return jsonify({
            "ref": {
                "id":      row["id"],
                "niveau":  row["niveau"],
                "version": row["version"],
                "etat":    row["etat"],
            },
            "arbre": arbre,
        })


@bp.route("/api/referentiels/<ref_id>/parties", methods=["GET"])
def api_parties(ref_id):
    """
    v0.19.1 — Liste à plat des parties de séquence d'un référentiel figé,
    pour la barre latérale de l'atelier Progression (éléments posables sur
    le calendrier).

    Retour : { ref: {id, niveau, version, etat}, parties: [{seq_code,
              seq_numero, seq_nom, theme_code, partie_numero, nb_objectifs,
              nb_seances_prevues}, ...] }
             404 si référentiel introuvable.
    """
    store = _store()
    if not hasattr(store, "lister_parties_referentiel"):
        return jsonify({"error": "store ne supporte pas les parties"}), 501

    parties = store.lister_parties_referentiel(ref_id)
    if parties is None:
        return jsonify({"error": f"référentiel introuvable : {ref_id}"}), 404

    ref = store.lire_referentiel(ref_id) or {}
    mode_seances = ref.get("mode_seances", "par_objectif")
    # v0.19.1.4 — En mode 'par_serie' (modèle historique), joindre la matrice
    # des séances (niveau-cible × série) par (séquence, partie). Vide sinon.
    seances_par_serie = []
    if mode_seances == "par_serie" and hasattr(store, "lister_seances_par_serie"):
        seances_par_serie = store.lister_seances_par_serie(ref_id)
    return jsonify({
        "ref": {
            "id":           ref.get("id", ref_id),
            "niveau":       ref.get("niveau", ""),
            "version":      ref.get("version", ""),
            "etat":         ref.get("etat", ""),
            "mode_seances": mode_seances,
        },
        "parties": parties,
        "seances_par_serie": seances_par_serie,
    })


# ── v0.15.2.8 : éligibilité à la validation ─────────────────────────────────


@bp.route("/api/referentiels/<ref_id>/eligibilite_validation", methods=["GET"])
def api_eligibilite_validation(ref_id):
    """v0.15.2.8 — Diagnostic d'éligibilité à `valide` (lecture seule).

    Retourne le détail des critères : combien d'atomes non validés, par
    table, combien d'évaluations non validées, combien de documents
    non compilés ou périmés.

    NE MODIFIE PAS l'état du référentiel. Pour déclencher la transition
    (en plus du lazy automatique sur `lister_par_niveau`), utiliser le
    endpoint POST `/revalider`.

    Retour : { eligible, raisons, details, etat_courant, niveau }
             404 si référentiel introuvable.
    """
    store = _store()
    if not hasattr(store, "_conn"):
        return jsonify({"error": "store non SQLite"}), 500

    from services.referentiel_validation import evaluer_eligibilite_validation

    with store._conn() as conn:
        try:
            diag = evaluer_eligibilite_validation(conn, ref_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
    return jsonify(diag)


@bp.route("/api/referentiels/<ref_id>/revalider", methods=["POST"])
def api_revalider(ref_id):
    """v0.15.2.8 — Force le recalcul lazy de l'état (bouton manuel
    « Revérifier l'éligibilité » côté UI).

    Applique la transition d'état si applicable :
      - en_cours + éligible  → valide
      - valide   + non éligible → en_cours
      - fige, annule         → JAMAIS modifiés

    Retour : { etat: <nouvel_etat>, diagnostic: { eligible, raisons, ... } }
             404 si référentiel introuvable.
    """
    store = _store()
    if not hasattr(store, "_conn"):
        return jsonify({"error": "store non SQLite"}), 500

    from services.referentiel_validation import (
        evaluer_eligibilite_validation, maj_etat_lazy,
    )

    with store._conn() as conn:
        try:
            nouvel_etat = maj_etat_lazy(conn, ref_id)
            diag = evaluer_eligibilite_validation(conn, ref_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
    return jsonify({"etat": nouvel_etat, "diagnostic": diag})
