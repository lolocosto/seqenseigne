"""routes/referentiel_principal_externe.py — v0.48.2

API des référentiels principaux externes (services/referentiel_principal_externe.py).
"""

from datetime import date
from pathlib import Path

from flask import Blueprint, jsonify, request, current_app, Response

from services import referentiel_principal_externe as svc
from services.referentiel_principal_externe import RefExtErreur

bp = Blueprint("referentiel_principal_externe", __name__)
P = "/api/referentiels-principaux-externes"


def _store():
    return current_app.json_store


def _data_dir():
    return Path(_store().data_dir)


def _auj():
    return date.today()


def _fait(fn, code=200):
    try:
        with _store()._conn() as conn:
            r = fn(conn)
        return jsonify(r if r is not None else {"ok": True}), code
    except RefExtErreur as e:
        return jsonify({"error": str(e), "code": e.code}), (404 if e.code == "introuvable" else 400)


def _b():
    return request.get_json(silent=True) or {}


@bp.route(P, methods=["GET"])
def api_lister():
    """`type` : principal (défaut) | mer | tous (v0.49.0)."""
    t = request.args.get("type", "principal")
    return _fait(lambda c: {"referentiels": svc.lister(c, request.args.get("niveau", ""),
                                                       type_ref=None if t == "tous" else t)})


@bp.route(P, methods=["POST"])
def api_creer():
    b = _b()
    return _fait(lambda c: svc.creer(c, b.get("niveau", ""), b.get("annee", ""),
                                     b.get("description", ""),
                                     type_ref=b.get("type_ref", "principal")), 201)


@bp.route(P + "/<rid>/sequences/<code>/parties/<int:num>/libelle", methods=["PUT"])
def api_partie_libeller(rid, code, num):
    """v0.49.0 — Libellé de partie (correction toujours permise)."""
    return _fait(lambda c: svc.libeller_partie(c, rid, code, num, _b().get("libelle", "")))


@bp.route(P + "/<rid>/documents-annuels", methods=["POST"])
def api_doc_annuel_ajouter(rid):
    """v0.49.0 — Document annuel (rattaché au référentiel)."""
    if "fichier" not in request.files:
        return jsonify({"error": "Aucun fichier fourni."}), 400
    f = request.files["fichier"]
    contenu = f.read()
    return _fait(lambda c: svc.ajouter_fichier(c, rid, "", 0, nom_fichier=f.filename or "document",
                                               contenu=contenu, mime=f.mimetype or "",
                                               data_dir=_data_dir()), 201)


@bp.route(P + "/<rid>", methods=["GET"])
def api_lire(rid):
    return _fait(lambda c: svc.lire(c, rid, _auj()))


@bp.route(P + "/<rid>", methods=["PUT"])
def api_modifier(rid):
    return _fait(lambda c: svc.modifier(c, rid, _b().get("description", "")))


@bp.route(P + "/<rid>", methods=["DELETE"])
def api_supprimer(rid):
    return _fait(lambda c: svc.supprimer(c, rid, _data_dir()))


@bp.route(P + "/<rid>/sequences", methods=["POST"])
def api_seq_ajouter(rid):
    return _fait(lambda c: svc.ajouter_sequence(c, rid, _b().get("nom", "")), 201)


@bp.route(P + "/<rid>/sequences/<code>", methods=["PUT"])
def api_seq_modifier(rid, code):
    return _fait(lambda c: svc.modifier_sequence(c, rid, code, _b().get("nom", "")))


@bp.route(P + "/<rid>/sequences/<code>/deplacer", methods=["POST"])
def api_seq_deplacer(rid, code):
    return _fait(lambda c: svc.deplacer_sequence(c, rid, code, int(_b().get("sens", 1)), _auj()))


@bp.route(P + "/<rid>/sequences/<code>", methods=["DELETE"])
def api_seq_supprimer(rid, code):
    return _fait(lambda c: svc.supprimer_sequence(c, rid, code, _auj(), _data_dir()))


@bp.route(P + "/<rid>/sequences/<code>/parties", methods=["POST"])
def api_partie_ajouter(rid, code):
    b = _b()
    return _fait(lambda c: svc.ajouter_partie(c, rid, code, b.get("nb_seances", 0), _auj(),
                                              b.get("libelle", "")), 201)


@bp.route(P + "/<rid>/sequences/<code>/parties/<int:num>", methods=["PUT"])
def api_partie_modifier(rid, code, num):
    return _fait(lambda c: svc.modifier_partie(c, rid, code, num, _b().get("nb_seances", 0), _auj()))


@bp.route(P + "/<rid>/sequences/<code>/parties/<int:num>/deplacer", methods=["POST"])
def api_partie_deplacer(rid, code, num):
    return _fait(lambda c: svc.deplacer_partie(c, rid, code, num, int(_b().get("sens", 1)), _auj()))


@bp.route(P + "/<rid>/sequences/<code>/parties/<int:num>", methods=["DELETE"])
def api_partie_supprimer(rid, code, num):
    return _fait(lambda c: svc.supprimer_partie(c, rid, code, num, _auj(), _data_dir()))


@bp.route(P + "/<rid>/sequences/<code>/parties/<int:num>/objectifs", methods=["POST"])
def api_obj_ajouter(rid, code, num):
    b = _b()
    type_obj = b.get("type_obj", "capacite")
    nom, criteres = b.get("nom", ""), None
    if type_obj == "connaissance":
        # v0.48.6 — Nom et critères pré-remplis (Préférences, comme l'objectif
        # « Connaître » des référentiels internes).
        try:
            from services.configuration import Configuration
            cfg = Configuration(_store().data_dir).atelier_assemblage_criteres_connaitre()
        except Exception:
            cfg = {}
        nom = nom or cfg.get("nom") or "Connaître les notions et les méthodes"
        criteres = {k: cfg.get(f"critere_{k.upper()}", "") for k in ("f", "a", "e")}
    return _fait(lambda c: svc.ajouter_objectif(c, rid, code, num, nom, b.get("nb_seances", 0),
                                                _auj(), type_obj=type_obj, criteres=criteres), 201)


@bp.route(P + "/<rid>/sequences/<code>/objectifs/<obj>", methods=["PUT"])
def api_obj_modifier(rid, code, obj):
    return _fait(lambda c: svc.modifier_objectif(c, rid, code, obj, _b(), _auj()))


@bp.route(P + "/<rid>/sequences/<code>/objectifs/<obj>/deplacer", methods=["POST"])
def api_obj_deplacer(rid, code, obj):
    return _fait(lambda c: svc.deplacer_objectif(c, rid, code, obj, int(_b().get("sens", 1)), _auj()))


@bp.route(P + "/<rid>/sequences/<code>/objectifs/<obj>", methods=["DELETE"])
def api_obj_supprimer(rid, code, obj):
    return _fait(lambda c: svc.supprimer_objectif(c, rid, code, obj, _auj()))


@bp.route(P + "/<rid>/sequences/<code>/fichiers", methods=["POST"])
def api_fichier_ajouter(rid, code):
    """Fichier (tous formats) rattaché à la séquence (partie=0) ou à une partie."""
    if "fichier" not in request.files:
        return jsonify({"error": "Aucun fichier fourni."}), 400
    f = request.files["fichier"]
    contenu = f.read()
    partie = int(request.form.get("partie", 0) or 0)
    return _fait(lambda c: svc.ajouter_fichier(c, rid, code, partie,
                                               nom_fichier=f.filename or "document",
                                               contenu=contenu, mime=f.mimetype or "",
                                               data_dir=_data_dir()), 201)


@bp.route(P + "/fichiers/<fid>", methods=["GET"])
def api_fichier_lire(fid):
    """PDF : affiché dans l'appli (inline) ; autres formats : téléchargés."""
    try:
        with _store()._conn() as conn:
            f = svc.lire_fichier(conn, fid)
    except RefExtErreur as e:
        return jsonify({"error": str(e)}), 404
    chemin = _data_dir() / f["chemin"]
    if not chemin.exists():
        return jsonify({"error": "Fichier introuvable."}), 404
    mime = f["mime"] or "application/octet-stream"
    disp = "inline" if f["affichable"] else "attachment"
    return Response(chemin.read_bytes(), mimetype=mime,
                    headers={"Content-Disposition": f'{disp}; filename="{f["nom_fichier"]}"'})


@bp.route(P + "/fichiers/<fid>", methods=["DELETE"])
def api_fichier_supprimer(fid):
    return _fait(lambda c: svc.supprimer_fichier(c, fid, _data_dir()))


@bp.route(P + "/fichiers/<fid>/placement", methods=["PUT"])
def api_fichier_placer(fid):
    """v0.48.5 — Séance de distribution dans la partie, retour, délai."""
    b = _b()
    return _fait(lambda c: svc.placer_fichier(c, fid, b.get("seance_n", 0), b.get("retour", ""),
                                              b.get("delai_type", ""), b.get("delai_n", 1)))


@bp.route("/api/referentiels-externes/docs/<did>/type", methods=["PUT"])
def api_doc_mer_typer(did):
    """v0.48.5 — Type d'un document de référentiel externe de MER."""
    return _fait(lambda c: svc.typer_doc_mer(c, did, _b().get("type_id", "")))


@bp.route(P + "/fichiers/<fid>/type", methods=["PUT"])
def api_fichier_typer(fid):
    """v0.48.3 — Type d'un fichier (classement dans la séquence)."""
    return _fait(lambda c: svc.typer_fichier(c, fid, _b().get("type_id", "")))


# ── v0.48.3 — Types de documents (Système › Préférences) ────────────────────

@bp.route("/api/types-documents", methods=["GET"])
def api_types():
    return _fait(lambda c: {"types": svc.lister_types(c, tout=request.args.get("tout") == "1")})


@bp.route("/api/types-documents", methods=["POST"])
def api_type_ajouter():
    return _fait(lambda c: svc.ajouter_type(c, _b().get("libelle", "")), 201)


@bp.route("/api/types-documents/<tid>", methods=["PUT"])
def api_type_modifier(tid):
    return _fait(lambda c: svc.modifier_type(c, tid, _b()))


@bp.route("/api/types-documents/<tid>/deplacer", methods=["POST"])
def api_type_deplacer(tid):
    return _fait(lambda c: svc.deplacer_type(c, tid, int(_b().get("sens", 1))))
