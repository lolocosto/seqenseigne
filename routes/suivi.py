"""routes/suivi.py — Suivi des exercices, niveaux, export/import."""

from flask import Blueprint, jsonify, request, current_app
from services import suivi as svc_suivi
from services import classes as svc_cls
from services.sequences import build_sequences, trouver_sequence
from services.niveaux import est_code_valide

bp = Blueprint("suivi", __name__)


def _stores():
    a = current_app
    return a.json_store, a.yaml_store, a.csv_store


def _verrouiller_referentiel_de_classe(js, cid: str) -> None:
    """
    Verrouillage automatique dès qu'une évaluation est saisie pour une classe.
    Verrouille :
    - le référentiel (si la progression y est rattachée)
    - la progression elle-même (transition valide|en_cours → verrouille)

    Idempotent : no-op si déjà verrouillé.
    Robustesse : si classe.progression_id est NULL, on retrouve la progression
    par clé métier (niveau, annee, etablissement) — cohérent avec la logique
    de routes/classes.py.
    """
    if not hasattr(js, "lire_progression_par_id"):
        return
    classes = js.lire_classes().get("classes", [])
    classe = next((c for c in classes if c["id"] == cid), None)
    if not classe:
        return

    # Récupérer la progression : par id direct, sinon par clé métier
    prog = None
    prog_id = classe.get("progression_id")
    if prog_id:
        prog = js.lire_progression_par_id(prog_id)
    if prog is None and hasattr(js, "lire_progression"):
        prog = js.lire_progression(
            classe.get("niveau", ""),
            classe.get("annee", ""),
            classe.get("etablissement", ""),
        )
    if not prog:
        return

    # Verrouiller le référentiel
    ref_id = prog.get("referentiel_id")
    if ref_id and hasattr(js, "verrouiller_referentiel"):
        js.verrouiller_referentiel(ref_id)

    # Verrouiller la progression
    if prog.get("etat") != "verrouille" and hasattr(js, "verrouiller_progression"):
        js.verrouiller_progression(prog["id"])


# ── Suivi (exercices cochés) ───────────────────────────────────────────────────

@bp.route("/api/suivi", methods=["GET"])
def api_suivi_get():
    js, _, _ = _stores()
    cid = request.args.get("classe")
    if cid and hasattr(js, 'lire_suivi_classe'):
        return jsonify(js.lire_suivi_classe(cid))
    d = js.lire_suivi()
    return jsonify(d.get(cid, {}) if cid else d)


@bp.route("/api/suivi/exo", methods=["POST"])
def api_suivi_exo():
    js, ys, cs = _stores()
    body    = request.get_json()
    cid     = body["classe"]
    seq     = body["seq"]
    eid     = body["eleve_id"]
    serie   = body["serie"]
    num     = int(body["num"])
    checked = bool(body["checked"])

    # Méthode atomique si disponible (SqliteStore), sinon fallback JSON
    if hasattr(js, 'cocher_exercice'):
        js.cocher_exercice(cid, seq, eid, serie, num, checked)
    else:
        suivi = svc_suivi.cocher_exercice(
            js.lire_suivi(), cid, seq, eid, serie, num, checked
        )
        js.ecrire_suivi(suivi)

    # Verrouiller la séquence dès la première saisie
    classe = svc_cls.trouver_classe(js.lire_classes(), cid)
    if classe:
        niveau = classe.get("niveau", "N10")
        if hasattr(js, 'verrouiller'):
            js.verrouiller(cid, niveau, seq)
        else:
            classes_data = svc_cls.verrouiller_sequence(
                js.lire_classes(), cid, niveau, seq
            )
            js.ecrire_classes(classes_data)

    return jsonify({"ok": True})


# ── Niveaux ────────────────────────────────────────────────────────────────────

@bp.route("/api/niveaux", methods=["GET"])
def api_niveaux_get():
    js, _, _ = _stores()
    cid = request.args.get("classe")
    if cid and hasattr(js, 'lire_niveaux_classe'):
        return jsonify(js.lire_niveaux_classe(cid))
    d = js.lire_niveaux()
    return jsonify(d.get(cid, {}) if cid else d)


@bp.route("/api/niveaux/set", methods=["POST"])
def api_niveaux_set():
    js, ys, cs = _stores()
    body     = request.get_json()
    cid      = body["classe"]
    seq      = body["seq"]
    eid      = body["eleve_id"]
    obj_code = body["obj_code"]
    niveau   = body["niveau"]

    if not est_code_valide(niveau):
        return jsonify({"error": f"Code de niveau invalide : {niveau}"}), 400

    if hasattr(js, 'set_niveau'):
        js.set_niveau(cid, seq, eid, obj_code, niveau)
    else:
        niveaux = svc_suivi.set_niveau_manuel(
            js.lire_niveaux(), cid, seq, eid, obj_code, niveau
        )
        js.ecrire_niveaux(niveaux)

    classe = svc_cls.trouver_classe(js.lire_classes(), cid)
    if classe:
        niv_classe = classe.get("niveau", "N10")
        if hasattr(js, 'verrouiller'):
            js.verrouiller(cid, niv_classe, seq)
        else:
            classes_data = svc_cls.verrouiller_sequence(
                js.lire_classes(), cid, niv_classe, seq
            )
            js.ecrire_classes(classes_data)

    # Bascule du référentiel en état verrouillé (idempotent)
    _verrouiller_referentiel_de_classe(js, cid)

    return jsonify({"ok": True})


@bp.route("/api/niveaux/calculer", methods=["POST"])
def api_niveaux_calculer():
    js, ys, cs = _stores()
    body        = request.get_json()
    cid         = body["classe"]
    seq_code    = body["seq"]
    niveau_code = body.get("niveau_code", "N10")

    classe = svc_cls.trouver_classe(js.lire_classes(), cid)
    if not classe:
        return jsonify({"error": "classe introuvable"}), 404

    sequences = build_sequences(niveau_code, ys, js, cs)
    seq = trouver_sequence(sequences, seq_code)
    if not seq:
        return jsonify({"error": "séquence introuvable"}), 404

    niveaux = svc_suivi.calculer_niveaux_sequence(
        js.lire_suivi(), js.lire_niveaux(),
        cid, seq_code,
        classe.get("eleves", []),
        seq["objectifs"],
    )
    js.ecrire_niveaux(niveaux)

    # Bascule du référentiel en état verrouillé (idempotent)
    _verrouiller_referentiel_de_classe(js, cid)

    return jsonify({"ok": True, "niveaux": niveaux[cid][seq_code]})


# ── Export / Import ────────────────────────────────────────────────────────────

@bp.route("/api/export")
def api_export():
    js, _, _ = _stores()
    cid = request.args.get("classe")
    classes = js.lire_classes()
    suivi   = js.lire_suivi()
    niveaux = js.lire_niveaux()

    if cid:
        classe = svc_cls.trouver_classe(classes, cid)
        return jsonify({
            "classe":  classe,
            "suivi":   suivi.get(cid, {}),
            "niveaux": niveaux.get(cid, {}),
        })
    return jsonify({"classes": classes, "suivi": suivi, "niveaux": niveaux})


@bp.route("/api/import", methods=["POST"])
def api_import():
    js, _, _ = _stores()
    body = request.get_json()
    if "classes" in body:
        js.ecrire_classes(body["classes"])
    if "suivi" in body:
        cid = body.get("classe_id")
        if cid:
            d = js.lire_suivi()
            d[cid] = body["suivi"]
            js.ecrire_suivi(d)
    if "niveaux" in body:
        cid = body.get("classe_id")
        if cid:
            d = js.lire_niveaux()
            d[cid] = body["niveaux"]
            js.ecrire_niveaux(d)
    return jsonify({"ok": True})
