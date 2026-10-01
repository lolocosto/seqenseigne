"""routes/classes.py — Classes et élèves."""

import csv
import io
from flask import Blueprint, jsonify, request, current_app
from services import classes as svc
from services.sequences import build_sequences, build_sequences_from_referentiel

bp = Blueprint("classes", __name__)


def _js():
    return current_app.json_store


def _stores():
    a = current_app
    return a.json_store, a.yaml_store, a.csv_store


@bp.route("/api/classes", methods=["GET"])
def api_classes_get():
    js = _js()
    annee         = request.args.get("annee", "").strip() or None
    etablissement = request.args.get("etablissement", "").strip() or None
    if hasattr(js, 'lire_classes') and (annee or etablissement):
        # SqliteStore supporte les filtres directs
        try:
            return jsonify(js.lire_classes(annee=annee, etablissement=etablissement))
        except TypeError:
            pass
    data = js.lire_classes()
    # Filtrage côté Python pour JsonStore
    if annee or etablissement:
        classes = data.get("classes", [])
        if annee:
            classes = [c for c in classes if c.get("annee") == annee]
        if etablissement:
            classes = [c for c in classes if c.get("etablissement") == etablissement]
        return jsonify({"classes": classes})
    return jsonify(data)


@bp.route("/api/classes/<cid>/sequences")
def api_classes_sequences(cid):
    """
    Retourne la liste des séquences à afficher pour une classe donnée.

    Stratégie (v0.6.2d) :
    1. Charger la classe et sa progression.
    2. Si la progression a un referentiel_id → charger depuis la BDD
       (tables referentiel_*).
    3. Sinon → fallback sur build_sequences (YAML courant du niveau).

    Le fallback permet de conserver un comportement correct pour les
    progressions créées manuellement ou anciennes sans référentiel rattaché.

    Robustesse : si classe.progression_id est NULL (cas observé pour les
    classes non-principales d'un même niveau+année+établissement après
    import historique), on retrouve la progression par clé métier.
    """
    js, ys, cs = _stores()
    classes = js.lire_classes().get("classes", [])
    classe = next((c for c in classes if c["id"] == cid), None)
    if not classe:
        return jsonify({"error": f"classe {cid} introuvable"}), 404

    niveau = classe.get("niveau", "N10")
    annee  = classe.get("annee", "")
    etab   = classe.get("etablissement", "")
    etab_id = classe.get("etablissement_id", "")
    prog_id = classe.get("progression_id")

    # Charger la progression, soit par id direct, soit par clé métier
    prog = None
    if prog_id and hasattr(js, "lire_progression_par_id"):
        prog = js.lire_progression_par_id(prog_id)
    # v0.33.4 — Fallback prioritaire par TRIPLET (id établissement), robuste aux
    # homonymes de classes et aux classes sans progression_id rattaché.
    if prog is None and annee and etab_id \
            and hasattr(js, "lire_progression_par_triplet"):
        try:
            prog = js.lire_progression_par_triplet(niveau, annee, etab_id)
        except Exception:
            prog = None
    if prog is None and annee and hasattr(js, "lire_progression"):
        # Fallback historique par nom d'établissement.
        try:
            prog = js.lire_progression(niveau, annee, etab)
        except Exception:
            prog = None

    referentiel_id = prog.get("referentiel_id") if prog else None

    if referentiel_id and hasattr(js, "lire_referentiel"):
        seqs = build_sequences_from_referentiel(referentiel_id, js)
        if seqs is not None:
            return jsonify({
                "source":         "referentiel",
                "referentiel_id": referentiel_id,
                "sequences":      seqs,
            })

    # Fallback : YAML courant
    return jsonify({
        "source":         "yaml",
        "referentiel_id": None,
        "sequences":      build_sequences(niveau, ys, js, cs),
    })


@bp.route("/api/classes", methods=["POST"])
def api_classes_post():
    body = request.get_json()
    nom   = body.get("nom", "").strip()
    if not nom:
        return jsonify({"error": "nom requis"}), 400
    js = _js()
    etab_id = (body.get("etablissement_id") or "").strip() or None
    if etab_id:
        # v0.41.2 — établissement choisi dans le sélecteur : il doit exister.
        with js._conn() as conn:
            r = conn.execute("SELECT nom FROM etablissements WHERE id=?",
                             (etab_id,)).fetchone()
        if r is None:
            return jsonify({"error": "établissement inconnu"}), 400
    data, nouvelle = svc.creer_classe(
        js.lire_classes(),
        nom=nom,
        niveau=body.get("niveau", "N10").strip(),
        annee=body.get("annee", "").strip(),
        etablissement=(r["nom"] if etab_id else body.get("etablissement", "").strip()),
        etablissement_id=etab_id,
    )
    js.ecrire_classes(data)
    c = next((x for x in js.lire_classes()["classes"] if x["id"] == nouvelle["id"]),
             nouvelle)
    return jsonify(c)


@bp.route("/api/classes/<cid>", methods=["PUT"])
def api_classes_put(cid):
    js = _js()
    data = js.lire_classes()
    c = svc.modifier_classe(data, cid, request.get_json())
    if not c:
        return jsonify({"error": "classe introuvable"}), 404
    js.ecrire_classes(data)
    return jsonify(c)


@bp.route("/api/classes/<cid>", methods=["DELETE"])
def api_classes_delete(cid):
    js = _js()
    if hasattr(js, 'supprimer_donnees_classe'):
        js.supprimer_donnees_classe(cid)
    else:
        data, suivi, niveaux = svc.supprimer_classe(
            js.lire_classes(), js.lire_suivi(), js.lire_niveaux(), cid
        )
        js.ecrire_classes(data)
        js.ecrire_suivi(suivi)
        js.ecrire_niveaux(niveaux)
    return jsonify({"ok": True})


# ── Élèves ─────────────────────────────────────────────────────────────────────

@bp.route("/api/classes/<cid>/eleves", methods=["POST"])
def api_eleve_add(cid):
    body = request.get_json()
    nom    = body.get("nom", "").strip()
    prenom = body.get("prenom", "").strip()
    if not nom or not prenom:
        return jsonify({"error": "nom et prénom requis"}), 400
    js = _js()
    data, eleve = svc.ajouter_eleve(js.lire_classes(), cid, nom, prenom)
    if not eleve:
        return jsonify({"error": "classe introuvable"}), 404
    js.ecrire_classes(data)
    return jsonify(eleve)


@bp.route("/api/classes/<cid>/eleves/import", methods=["POST"])
def api_eleves_import(cid):
    if "file" in request.files:
        raw = request.files["file"].read().decode("utf-8-sig")
    elif request.is_json:
        raw = request.get_json().get("csv", "")
    else:
        return jsonify({"error": "fichier CSV requis"}), 400

    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    if not rows:
        return jsonify({"error": "CSV vide"}), 400

    cols = {k.strip().lower(): k for k in rows[0].keys()}
    col_nom    = cols.get("nom")
    col_prenom = cols.get("prenom") or cols.get("prénom")
    if not col_nom or not col_prenom:
        return jsonify({
            "error": f"colonnes Nom/Prenom introuvables. "
                     f"Colonnes disponibles : {list(rows[0].keys())}"
        }), 400

    js = _js()
    data, resume = svc.importer_eleves_csv(
        js.lire_classes(), cid, rows, col_nom, col_prenom
    )
    if "erreur" in resume:
        return jsonify({"error": resume["erreur"]}), 404
    js.ecrire_classes(data)
    # v0.40.0 — Colonne Sexe (export Pronote) : complète aussi les élèves déjà
    # présents. Aucune autre colonne n'est lue (date de naissance, projet
    # d'accompagnement… jamais importés).
    col_sexe = cols.get("sexe")
    resume["sexes_mis_a_jour"] = 0
    if col_sexe and hasattr(js, "_conn"):
        from services import eleves_sexe
        with js._conn() as conn:
            resume["sexes_mis_a_jour"] = eleves_sexe.maj_depuis_import(
                conn, cid, rows, col_nom, col_prenom, col_sexe)
        c = next((x for x in js.lire_classes()["classes"] if x["id"] == cid), None)
        if c:
            resume["eleves"] = c.get("eleves", [])
    return jsonify(resume)


@bp.route("/api/eleves/<eid>/sexe", methods=["PUT"])
def api_eleve_sexe(eid):
    """v0.40.0 — Saisie manuelle du sexe d'un élève (M, F ou vide)."""
    from services import eleves_sexe
    body = request.get_json() or {}
    try:
        with _js()._conn() as conn:
            s = eleves_sexe.definir(conn, eid, body.get("sexe", ""))
        return jsonify({"id": eid, "sexe": s})
    except eleves_sexe.SexeErreur as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/classes/<cid>/eleves/<eid>", methods=["DELETE"])
def api_eleve_delete(cid, eid):
    js = _js()
    if hasattr(js, 'supprimer_donnees_eleve'):
        # 1. Mettre à jour la liste d'élèves dans la classe
        classes_data = js.lire_classes()
        c = next((x for x in classes_data["classes"] if x["id"] == cid), None)
        if c:
            c["eleves"] = [e for e in c.get("eleves", []) if e["id"] != eid]
            js.ecrire_classes(classes_data)
        # 2. Supprimer les données de suivi de l'élève
        js.supprimer_donnees_eleve(cid, eid)
    else:
        data, suivi, niveaux = svc.supprimer_eleve(
            js.lire_classes(), js.lire_suivi(), js.lire_niveaux(), cid, eid
        )
        js.ecrire_classes(data)
        js.ecrire_suivi(suivi)
        js.ecrire_niveaux(niveaux)
    return jsonify({"ok": True})


# ── Versions ───────────────────────────────────────────────────────────────────

@bp.route("/api/classes/<cid>/version", methods=["POST"])
def api_classe_version_set(cid):
    body   = request.get_json()
    niveau = body.get("niveau", "").strip()
    seq    = body.get("seq", "").strip()
    tag    = body.get("tag")
    js = _js()
    # Vérifier le verrouillage directement dans SQLite si disponible
    if hasattr(js, 'est_verrouille') and js.est_verrouille(cid, niveau, seq):
        return jsonify({"error": "Séquence verrouillée — créer une nouvelle version"}), 409

    data, erreur = svc.definir_version_active(
        js.lire_classes(), cid, niveau, seq, tag
    )
    if erreur:
        code = 404 if "introuvable" in erreur else 409
        return jsonify({"error": erreur}), code

    # Persister aussi dans versions_classes SQLite si disponible
    if hasattr(js, 'set_version_active'):
        js.set_version_active(cid, niveau, seq, tag)
    js.ecrire_classes(data)
    return jsonify({"ok": True, "key": f"{niveau}_{seq}", "tag": tag})
