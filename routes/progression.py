"""routes/progression.py — Progressions et import historique."""

from flask import Blueprint, jsonify, request, current_app
from services.progression import (
    progression_vide, modifier_creneau,
    reordonner_creneaux, valider_progression,
)
from importers.sequencesdb import lire_sequencesdb, importer_classe_historique, suivi_historique_vers_niveaux

bp = Blueprint("progression", __name__)


def _stores():
    a = current_app
    return a.json_store, a.yaml_store, a.csv_store


# ── Progressions ───────────────────────────────────────────────────────────────

@bp.route("/api/progression/<niveau>", methods=["GET"])
def api_progression_get(niveau):
    """
    Retourne une progression.
    ?annee=2023-2024&etablissement=Collège+Les+Hautes+Ourmes — progression précise.
    Sans paramètre : retourne la plus récente pour ce niveau.
    """
    js, _, _ = _stores()
    annee         = request.args.get("annee", "").strip()
    etablissement = request.args.get("etablissement", "").strip()
    prog = js.lire_progression(niveau, annee or None, etablissement)
    if prog is None:
        return jsonify({"error": f"Aucune progression pour {niveau}"}), 404
    return jsonify(prog)


@bp.route("/api/progression/<niveau>/liste", methods=["GET"])
def api_progression_liste(niveau):
    """
    Liste toutes les progressions disponibles pour un niveau.
    Retourne [{id, annee, etablissement}, ...] triés par annee+etablissement.
    """
    js, _, _ = _stores()
    return jsonify(js.lister_progressions(niveau))


@bp.route("/api/progression/<niveau>/rechercher", methods=["GET"])
def api_progression_rechercher(niveau):
    """
    Recherche une progression par son triplet métier (niveau, année,
    établissement_id). Utilisé par le bloc « Sélection de progression »
    de l'écran Progression annuelle.

    Query params :
      annee            : '2025-2026' (obligatoire)
      etablissement_id : 'et_xxx…'    (obligatoire)

    Réponses :
      200 { "trouve": true,  "progression": {...} }         — cas nominal
      200 { "trouve": false, "triplet": {...} }             — 0 résultat
      400 si annee ou etablissement_id manquants
      500 si incohérence base (≥ 2 progressions — impossible en pratique)
    """
    js, _, _ = _stores()
    annee            = request.args.get("annee", "").strip()
    etablissement_id = request.args.get("etablissement_id", "").strip()

    if not annee or not etablissement_id:
        return jsonify({
            "error": "annee et etablissement_id requis",
        }), 400

    try:
        prog = js.lire_progression_par_triplet(niveau, annee, etablissement_id)
    except RuntimeError as e:
        return jsonify({"error": str(e), "code": "doublon_base"}), 500

    if prog is None:
        return jsonify({
            "trouve":  False,
            "triplet": {
                "niveau":           niveau,
                "annee":            annee,
                "etablissement_id": etablissement_id,
            },
        })

    return jsonify({"trouve": True, "progression": prog})


@bp.route("/api/progression_id/<path:progression_id>/etat", methods=["POST"])
def api_progression_etat(progression_id):
    """
    Change l'état d'une progression.
    Body : { "etat": "en_cours" | "valide" }

    La transition vers 'verrouille' est automatique côté serveur dès qu'une
    évaluation est saisie pour une classe utilisant la progression — l'UI
    n'a pas à la déclencher.

    Refus si la progression est déjà 'verrouille' : le déverrouillage
    n'est pas géré par cet endpoint (il nécessiterait la suppression des
    évaluations en cascade, prévu pour plus tard).
    """
    js, _, _ = _stores()
    if not hasattr(js, "changer_etat_progression"):
        return jsonify({"error": "Store ne supporte pas l'état de progression"}), 501

    body = request.get_json(silent=True) or {}
    etat = body.get("etat", "").strip()
    if etat not in ("en_cours", "valide"):
        return jsonify({
            "error": "État invalide. Valeurs autorisées : en_cours, valide."
        }), 400

    prog = js.lire_progression_par_id(progression_id)
    if not prog:
        return jsonify({"error": "Progression introuvable"}), 404

    if prog.get("etat") == "verrouille":
        return jsonify({
            "error": "Progression verrouillée : des évaluations ont été "
                     "saisies. Le déverrouillage n'est pas encore géré."
        }), 409

    try:
        js.changer_etat_progression(progression_id, etat)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(js.lire_progression_par_id(progression_id))


@bp.route("/api/progression_id/<path:progression_id>/referentiel", methods=["POST"])
def api_progression_changer_referentiel(progression_id):
    """v0.22.1 — Change le référentiel support d'une progression `en_cours`.

    Purge tous les créneaux existants (option (a) : on repart d'une
    progression vide sur le nouveau référentiel). L'UI demande une
    confirmation avant l'appel.

    Body : { "referentiel_id": "N11_v2025" }
    """
    js, _, _ = _stores()
    body = request.get_json(silent=True) or {}
    nouveau_ref = (body.get("referentiel_id") or "").strip()
    if not nouveau_ref:
        return jsonify({"error": "referentiel_id requis"}), 400

    prog = js.lire_progression_par_id(progression_id)
    if not prog:
        return jsonify({"error": "Progression introuvable"}), 404
    if prog.get("etat") != "en_cours":
        return jsonify({
            "error": "Le référentiel ne peut être changé que sur une "
                     "progression « en cours »."
        }), 409

    # Le nouveau référentiel doit exister et être figé (verrouille/utilise) —
    # une progression s'appuie toujours sur un référentiel figé.
    ref = js.lire_referentiel(nouveau_ref) if hasattr(js, "lire_referentiel") \
        else None
    if not ref:
        return jsonify({"error": f"Référentiel introuvable : {nouveau_ref}"}), 404
    # v0.48.2 — Un référentiel principal externe est utilisable dès sa
    # création (même incomplet), sauf s'il est annulé.
    externe = (ref.get("source") == "externe")
    if (externe and ref.get("etat") == "annule") or \
            (not externe and ref.get("etat") not in ("verrouille", "utilise")):
        return jsonify({
            "error": "Le référentiel choisi n'est pas exploitable "
                     "(il doit être verrouillé ou utilisé)."
        }), 400
    if ref.get("niveau") and prog.get("niveau") \
            and ref["niveau"] != prog["niveau"]:
        return jsonify({
            "error": "Le référentiel choisi n'est pas du même niveau que la "
                     "progression."
        }), 400

    # Changer le référentiel + purger les créneaux (option a).
    prog["referentiel_id"] = nouveau_ref
    prog["creneaux"] = []
    js.ecrire_progression(prog)
    return jsonify(js.lire_progression_par_id(progression_id))


@bp.route("/api/progression_id/<path:progression_id>", methods=["GET"])
def api_progression_get_by_id(progression_id):
    """Retourne une progression par son id complet (ex: N11-2025-2026-HAUTES_OURMES)."""
    js, _, _ = _stores()
    prog = js.lire_progression_par_id(progression_id)
    if prog is None:
        return jsonify({"error": f"Progression '{progression_id}' introuvable"}), 404
    return jsonify(prog)


@bp.route("/api/progression/<niveau>", methods=["POST"])
def api_progression_save(niveau):
    """Sauvegarde ou crée la progression d'un niveau."""
    from services.progression import progression_id as build_pid
    js, _, _ = _stores()
    body = request.get_json() or {}
    body["niveau"] = niveau
    # Construire l'id si absent (création depuis l'UI)
    if not body.get("id"):
        annee = body.get("annee", "")
        etab  = body.get("etablissement", "")
        if not annee:
            return jsonify({"error": "annee requis"}), 400
        body["id"] = build_pid(niveau, annee, etab)
    if not body.get("creneaux"):
        body["creneaux"] = []
    avertissements = valider_progression(body)
    js.ecrire_progression(body)
    return jsonify({"ok": True, "id": body["id"], "avertissements": avertissements})


@bp.route("/api/progression/<niveau>/reset", methods=["POST"])
def api_progression_reset(niveau):
    """
    Recrée une progression vide dans l'ordre naturel des séquences.
    Body : { "annee": "2025-2026" }
    """
    js, _, cs = _stores()
    body = request.get_json() or {}
    annee = body.get("annee", "").strip()
    if not annee:
        return jsonify({"error": "annee requis"}), 400
    etablissement = body.get("etablissement", "").strip()
    seqs = sorted(cs.lire_c04_sequences().values(), key=lambda s: s["numero"])
    prog = progression_vide(niveau, annee, seqs, etablissement=etablissement)
    js.ecrire_progression(prog)
    return jsonify(prog)


@bp.route("/api/progression/<niveau>/creneau/<creneau_id>", methods=["PATCH"])
def api_creneau_modifier(niveau, creneau_id):
    """
    Met à jour les champs d'un créneau (date_debut, date_fin, periode, partie, ordre).
    Body : dict des champs à modifier + optionnellement {"progression_id": "..."}.
    """
    js, _, _ = _stores()
    body = request.get_json() or {}
    pid  = body.pop("progression_id", None)
    prog = js.lire_progression_par_id(pid) if pid else js.lire_progression(niveau)
    if prog is None:
        return jsonify({"error": "progression introuvable"}), 404
    prog, erreur = modifier_creneau(prog, creneau_id, body)
    if erreur:
        return jsonify({"error": erreur}), 404
    js.ecrire_progression(prog)
    return jsonify({"ok": True})


@bp.route("/api/progression/<niveau>/creneau-ajouter", methods=["POST"])
def api_creneau_ajouter(niveau):
    """
    Ajoute un nouveau créneau à la progression.
    Body : { annee, sequence, partie_debut, partie_fin, partie, periode,
             date_debut, date_fin, revisions }

    Rétrocompat : les anciennes clés rang_debut / rang_fin sont aussi acceptées.
    """
    from persistence.ids import nouveau_id_creneau
    js, _, _ = _stores()
    body     = request.get_json() or {}
    annee    = body.get("annee", "")
    # v0.19.1 — Désambiguïsation par progression_id (l'UI gère plusieurs
    # établissements pour un même couple niveau/année ; lire_progression seul
    # retomberait sur l'établissement « Non renseigné »).
    pid      = body.get("progression_id")
    prog     = (js.lire_progression_par_id(pid) if pid
                else js.lire_progression(niveau, annee or None))
    if prog is None:
        return jsonify({"error": "progression introuvable"}), 404

    # Construire le nouveau créneau
    cid_creneau = nouveau_id_creneau()
    # Rétrocompat : accepter rang_debut / rang_fin en entrée
    partie_debut = int(body.get("partie_debut", body.get("rang_debut", 1)))
    partie_fin   = int(body.get("partie_fin",   body.get("rang_fin",   partie_debut)))

    # Vérifier que les parties ne sont pas déjà placées
    seq = body.get("sequence", "")
    places = set()
    for c in prog.get("creneaux", []):
        if c.get("sequence") == seq:
            rd = c.get("partie_debut", c.get("rang_debut", 1))
            rf = c.get("partie_fin",   c.get("rang_fin",   rd))
            for r in range(rd, rf + 1):
                places.add(r)
    conflits = [r for r in range(partie_debut, partie_fin + 1) if r in places]
    if conflits:
        return jsonify({"error": f"Parties déjà placées : {conflits}"}), 409

    nouveau = {
        "id":           cid_creneau,
        "sequence":     seq,
        "partie_debut": partie_debut,
        "partie_fin":   partie_fin,
        "partie":     body.get("partie", ""),
        "periode":    body.get("periode", ""),
        "date_debut": body.get("date_debut", ""),
        "date_fin":   body.get("date_fin", ""),
        "revisions":  body.get("revisions", ""),
        "ordre":      len(prog.get("creneaux", [])) + 1,
        "objectifs":  [],
        "objectifs_exos": [],
    }
    prog.setdefault("creneaux", []).append(nouveau)
    js.ecrire_progression(prog)
    return jsonify({"ok": True, "creneau": nouveau})


@bp.route("/api/progression/<niveau>/creneau/<creneau_id>", methods=["DELETE"])
def api_creneau_supprimer(niveau, creneau_id):
    """Supprime un créneau de la progression."""
    js, _, _ = _stores()
    body  = request.get_json() or {}
    annee = body.get("annee", "")
    # v0.19.1 — Désambiguïsation par progression_id (cf. creneau-ajouter).
    pid   = body.get("progression_id")
    prog  = (js.lire_progression_par_id(pid) if pid
             else js.lire_progression(niveau, annee or None))
    if prog is None:
        return jsonify({"error": "progression introuvable"}), 404
    avant = len(prog.get("creneaux", []))
    prog["creneaux"] = [c for c in prog["creneaux"] if c["id"] != creneau_id]
    if len(prog["creneaux"]) == avant:
        return jsonify({"error": "créneau introuvable"}), 404
    # Réajuster les ordres
    for i, c in enumerate(prog["creneaux"]):
        c["ordre"] = i + 1
    js.ecrire_progression(prog)
    return jsonify({"ok": True})


@bp.route("/api/progression/<niveau>/reordonner", methods=["POST"])
def api_progression_reordonner(niveau):
    """
    Réordonne les créneaux.
    Body : { "ordre": ["id1", "id2", ...] }
    """
    js, _, _ = _stores()
    body = request.get_json() or {}
    pid  = body.pop("progression_id", None)
    prog = js.lire_progression_par_id(pid) if pid else js.lire_progression(niveau)
    if prog is None:
        return jsonify({"error": "progression introuvable"}), 404
    ordre = body.get("ordre", [])
    prog = reordonner_creneaux(prog, ordre)
    js.ecrire_progression(prog)
    return jsonify({"ok": True})


# ── Import depuis SequencesDB ──────────────────────────────────────────────────

@bp.route("/api/progression/<niveau>/importer-sequencesdb", methods=["POST"])
def api_progression_importer_sequencesdb(niveau):
    """
    Construit une progression depuis un répertoire SequencesDB.
    Body : { "chemin": "...", "annee": "2023-2024" }
    """
    js, _, _ = _stores()
    body = request.get_json() or {}
    chemin        = body.get("chemin", "").strip()
    annee         = body.get("annee", "").strip()
    etablissement = body.get("etablissement", "").strip()
    if not chemin or not annee:
        return jsonify({"error": "chemin et annee requis"}), 400
    try:
        prog = lire_sequencesdb(chemin, niveau, annee, etablissement=etablissement)
        erreurs = prog.pop("erreurs", [])
        js.ecrire_progression(prog)
        return jsonify({
            "ok":       True,
            "creneaux": len(prog["creneaux"]),
            "erreurs":  erreurs,
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "detail": traceback.format_exc()}), 500


# ── Import complet d'une classe historique ─────────────────────────────────────

@bp.route("/api/import/historique", methods=["POST"])
def api_import_historique():
    """
    Import complet d'une classe historique depuis ses CSV.

    Body :
    {
      "chemin_classe":      "F:/.../.../4e3",
      "chemin_sequencesdb": "F:/.../.../SequencesDB",
      "niveau":             "N11",
      "annee":              "2023-2024",
      "nom_classe":         "4e3",
      "etablissement":      "Collège Les Hautes Ourmes"
    }

    Actions :
    - Construit ou réutilise la progression du niveau/année
    - Crée la classe avec ses élèves
    - Persiste le suivi historique lié à la progression
    """
    js, _, _ = _stores()
    body = request.get_json() or {}

    chemin_classe      = body.get("chemin_classe", "").strip()
    chemin_sequencesdb = body.get("chemin_sequencesdb", "").strip()
    niveau             = body.get("niveau", "").strip()
    annee              = body.get("annee", "").strip()
    nom_classe         = body.get("nom_classe", "").strip()
    etablissement      = body.get("etablissement", "").strip()

    if not all([chemin_classe, chemin_sequencesdb, niveau, annee, nom_classe]):
        return jsonify({"error": "chemin_classe, chemin_sequencesdb, niveau, annee et nom_classe requis"}), 400

    # ── Vérif anti-doublon : (nom, établissement, année) doivent être uniques ──
    # On vérifie AVANT le parsing des CSV (fail-fast).
    def _norm(s):
        return (s or "").strip().casefold()
    cle_nouvelle = (_norm(nom_classe), _norm(etablissement), _norm(annee))
    for c in js.lire_classes().get("classes", []):
        cle_existante = (_norm(c.get("nom")),
                         _norm(c.get("etablissement")),
                         _norm(c.get("annee")))
        if cle_existante == cle_nouvelle:
            etab_txt = etablissement or "(sans établissement)"
            return jsonify({
                "error": (f"Une classe '{nom_classe}' existe déjà pour "
                          f"{etab_txt} en {annee} "
                          f"(id existant : {c.get('id')}). "
                          f"Supprimez-la avant de la réimporter, "
                          f"ou importez-la avec un nom différent.")
            }), 409

    try:
        result = importer_classe_historique(
            chemin_classe, chemin_sequencesdb,
            niveau, annee, nom_classe, etablissement,
            store=js,
        )

        # Persister la progression
        prog = result["progression"]
        js.ecrire_progression(prog)

        # Persister la classe
        classes_data = js.lire_classes()
        # Éviter les doublons par id
        existants = {c["id"] for c in classes_data["classes"]}
        classe = result["classe"]
        if classe["id"] in existants:
            classe["id"] += "_hist"
        classes_data["classes"].append(classe)
        js.ecrire_classes(classes_data)

        # Note : on ne persiste plus le fichier JSON d'archive
        # suivi_historique_<classe_id>_<annee>.json — il n'était jamais
        # relu par l'application. Les niveaux sont directement injectés
        # dans niveaux.json ci-dessous, ce qui est suffisant pour le
        # front-end.

        # Convertir et injecter dans niveaux.json pour que le front-end
        # affiche immédiatement les niveaux dans la grille de suivi
        niveaux_convertis = suivi_historique_vers_niveaux(result["suivi"])
        niveaux_existants = js.lire_niveaux()
        cid = classe["id"]
        niveaux_existants.setdefault(cid, {})
        for seq_code, eleves_niv in niveaux_convertis.items():
            niveaux_existants[cid].setdefault(seq_code, {})
            for eid, objs in eleves_niv.items():
                niveaux_existants[cid][seq_code].setdefault(eid, {})
                niveaux_existants[cid][seq_code][eid].update(objs)
        js.ecrire_niveaux(niveaux_existants)

        return jsonify({
            "ok":            True,
            "classe_id":     classe["id"],
            "progression_id": prog["id"],
            "eleves":        len(result["eleves"]),
            "creneaux":      len(prog["creneaux"]),
            "erreurs":       result["erreurs"],
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "detail": traceback.format_exc()}), 500


# ── Rangs disponibles pour une séquence dans une progression ──────────────────

@bp.route("/api/progression/<niveau>/rangs-disponibles", methods=["GET"])
def api_rangs_disponibles(niveau):
    """
    Pour une séquence donnée, retourne les rangs déjà placés et les rangs
    disponibles (premier rang non encore placé et ses suivants immédiats).

    Query params : seq=S01 (obligatoire), annee=2025-2026 (optionnel)

    Retourne :
      { seq, rangs_max, rangs_places, rangs_disponibles, prochain_rang }
      rangs_max     : nombre total de rangs de la séquence (déduit des objectifs)
      rangs_places  : [1, 2, …] rangs déjà dans la progression
      rangs_disponibles : [3, …] rangs qu'on peut encore ajouter (contiguïté)
      prochain_rang : 3 (premier disponible)
    """
    from flask import current_app, request, jsonify
    from services.progression import rang_creneau as _rang_creneau
    from services.sequences import build_sequences, trouver_sequence

    js  = current_app.json_store
    ys  = current_app.yaml_store
    cs  = current_app.csv_store

    seq_code = request.args.get("seq", "").strip()
    annee    = request.args.get("annee", "").strip() or None
    if not seq_code:
        return jsonify({"error": "param seq requis"}), 400

    prog = js.lire_progression(niveau, annee)
    if not prog:
        return jsonify({"error": "Progression introuvable"}), 404

    # Parties déjà placées pour cette séquence
    places = set()
    for c in prog.get("creneaux", []):
        if c.get("sequence") == seq_code:
            rd = c.get("partie_debut", c.get("rang_debut", 1))
            rf = c.get("partie_fin",   c.get("rang_fin",   rd))
            for r in range(rd, rf + 1):
                places.add(r)

    # Nombre max de rangs : déduit des objectifs YAML
    sequences = build_sequences(niveau, ys, js, cs)
    seq_data = trouver_sequence(sequences, seq_code)
    rangs_max = 1
    if seq_data:
        codes = [o.get("code", "01") for o in seq_data.get("objectifs", [])]
        if codes:
            rangs_max = max(_rang_creneau(c) for c in codes)

    # Rangs disponibles = rangs non placés dont tous les prédécesseurs sont placés
    disponibles = []
    for r in range(1, rangs_max + 1):
        if r in places:
            continue
        # Vérifier que tous les rangs 1..(r-1) sont placés
        if all(p in places for p in range(1, r)):
            disponibles.append(r)
        else:
            break  # pas contiguïté → s'arrêter

    return jsonify({
        "seq":              seq_code,
        "rangs_max":        rangs_max,
        "rangs_places":     sorted(places),
        "rangs_disponibles": disponibles,
        "prochain_rang":    disponibles[0] if disponibles else None,
    })
