"""routes/progression_rituels.py — v0.60.0

Ordre des parties de la progression (saisie de l'enseignant) et document de
rituels d'automatismes / séances d'évaluation (`services/progression_rituels`,
décisions P0 à P7, `doc/redemarrage_v0_60_0.md`). Profil atelier.

  GET  /api/progression-rituels/<ref_id>             ordre, paramètres, parties
  PUT  /api/progression-rituels/<ref_id>             {texte | ordre, parametres}
  GET  /api/progression-rituels/<ref_id>/calendrier  calendrier calculé (JSON)
  GET  /api/progression-rituels/<ref_id>/tex         source .tex du document
  POST /api/progression-rituels/<ref_id>/compiler    compile (synchrone) → PDF
  GET  /api/progression-rituels/<ref_id>/pdf         dernier PDF compilé
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_file

from services import progression_rituels as svc

bp = Blueprint("progression_rituels", __name__)


def _store():
    return current_app.json_store


def _erreur(e: svc.ProgressionErreur, statut: int = 400):
    return jsonify({"error": str(e), "erreurs": e.erreurs}), statut


def _introuvable(conn, ref_id):
    return conn.execute("SELECT 1 FROM referentiel_niveaux WHERE id = ?",
                        (ref_id,)).fetchone() is None


@bp.route("/api/progression-rituels/<ref_id>", methods=["GET"])
def api_lire(ref_id):
    with _store()._conn() as conn:
        if _introuvable(conn, ref_id):
            return jsonify({"error": f"Référentiel introuvable : {ref_id}"}), 404
        return jsonify(svc.lire(conn, ref_id))


@bp.route("/api/progression-rituels/<ref_id>", methods=["PUT"])
def api_enregistrer(ref_id):
    body = request.get_json(silent=True) or {}
    with _store()._conn() as conn:
        if _introuvable(conn, ref_id):
            return jsonify({"error": f"Référentiel introuvable : {ref_id}"}), 404
        try:
            out = svc.enregistrer(conn, ref_id, texte=body.get("texte"),
                                  ordre=body.get("ordre"), parametres=body.get("parametres"))
        except svc.ProgressionErreur as e:
            return _erreur(e)
        conn.commit()
        return jsonify(out)


@bp.route("/api/progression-rituels/<ref_id>/calendrier", methods=["GET"])
def api_calendrier(ref_id):
    with _store()._conn() as conn:
        if _introuvable(conn, ref_id):
            return jsonify({"error": f"Référentiel introuvable : {ref_id}"}), 404
        try:
            return jsonify(svc.calendrier(conn, ref_id))
        except svc.ProgressionErreur as e:
            return _erreur(e)


def _options():
    mode = request.args.get("cartes")
    return {"cartes_document": mode} if mode in ("aucune", "nouvelles", "toutes") else {}


@bp.route("/api/progression-rituels/<ref_id>/tex", methods=["GET"])
def api_tex(ref_id):
    with _store()._conn() as conn:
        if _introuvable(conn, ref_id):
            return jsonify({"error": f"Référentiel introuvable : {ref_id}"}), 404
        tex = svc.generer_tex(conn, ref_id, _options())
    return Response(tex, mimetype="text/plain; charset=utf-8")


def _dossier(ref_id: str) -> Path:
    d = Path(_store().data_dir) / "referentiels" / ref_id / "_rituels"
    d.mkdir(parents=True, exist_ok=True)
    return d


@bp.route("/api/progression-rituels/<ref_id>/compiler", methods=["POST"])
def api_compiler(ref_id):
    from services import orchestrateur_compilation as orch
    from routes.referentiel_documents_compilation import _configuration
    with _store()._conn() as conn:
        if _introuvable(conn, ref_id):
            return jsonify({"error": f"Référentiel introuvable : {ref_id}"}), 404
        config = _configuration()
        res = orch.compiler(conn, "rituels_progression", {"referentiel_id": ref_id},
                            _options(), dossier_artefacts=_dossier(ref_id),
                            cible_key="rituels", racine_sources=config.chemin_sources_livrets(),
                            dossier_images=Path(_store().data_dir) / "images",
                            racine_appli=Path(current_app.root_path), timeout=600,
                            tikz_libraries=config.tikz_libraries(),
                            tblr_libraries=config.tblr_libraries())
    return jsonify({"ok": bool(res.ok), "type_echec": res.type_echec,
                    "erreurs": [getattr(x, "message", str(x)) for x in (res.erreurs or [])][:20],
                    "pdf": f"/api/progression-rituels/{ref_id}/pdf" if res.ok else None})


@bp.route("/api/progression-rituels/<ref_id>/pdf", methods=["GET"])
def api_pdf(ref_id):
    p = Path(_store().data_dir) / "referentiels" / ref_id / "_rituels" / "rituels.pdf"
    if not p.is_file():
        return jsonify({"error": "Aucun PDF compilé."}), 404
    return send_file(p, mimetype="application/pdf", download_name=f"rituels_{ref_id}.pdf")


# ── v0.60.1 (D-SE) — Document « séance d'évaluation » d'une semaine ─────────
#
#   GET  /api/progression-rituels/<ref_id>/seance/<semaine>          contenu (JSON)
#   GET  /api/progression-rituels/<ref_id>/seance/<semaine>/tex      source .tex
#   POST /api/progression-rituels/<ref_id>/seance/<semaine>/compiler compile → PDF
#   GET  /api/progression-rituels/<ref_id>/seance/<semaine>/pdf      dernier PDF
# Query : sujet=A|B, version=eleve|corrigee. 400 : pas de séance cette semaine,
# séance vide, ou trop chargée (plus de 50 min ou de 5 objectifs, sauf une
# évaluation seule).

def _options_seance():
    return {k: request.args[k] for k in ("sujet", "version") if request.args.get(k)}


def _cle_seance(semaine: int) -> str:
    o = _options_seance()
    return f"seance_s{semaine:02d}_{o.get('sujet', 'A')}_{o.get('version', 'eleve')}"


@bp.route("/api/progression-rituels/<ref_id>/seance/<int:semaine>", methods=["GET"])
def api_seance(ref_id, semaine):
    from services import documents_evaluation_v2 as dev
    with _store()._conn() as conn:
        if _introuvable(conn, ref_id):
            return jsonify({"error": f"Référentiel introuvable : {ref_id}"}), 404
        try:
            se = dev.seance(conn, ref_id, semaine)
        except dev.DocumentEvaluationErreur as e:
            return jsonify({"error": str(e)}), 400
    return jsonify({**se, "refus": dev.controler_seance(se)})


@bp.route("/api/progression-rituels/<ref_id>/seance/<int:semaine>/tex", methods=["GET"])
def api_seance_tex(ref_id, semaine):
    from services import documents_evaluation_v2 as dev
    with _store()._conn() as conn:
        if _introuvable(conn, ref_id):
            return jsonify({"error": f"Référentiel introuvable : {ref_id}"}), 404
        try:
            tex = dev.generer_seance_evaluation(conn, ref_id, semaine, _options_seance())
        except (dev.DocumentEvaluationErreur, ValueError) as e:
            return jsonify({"error": str(e)}), 400
    return Response(tex, mimetype="text/plain; charset=utf-8")


@bp.route("/api/progression-rituels/<ref_id>/seance/<int:semaine>/compiler", methods=["POST"])
def api_seance_compiler(ref_id, semaine):
    from services import documents_evaluation_v2 as dev
    from services import orchestrateur_compilation as orch
    from routes.referentiel_documents_compilation import _configuration
    with _store()._conn() as conn:
        if _introuvable(conn, ref_id):
            return jsonify({"error": f"Référentiel introuvable : {ref_id}"}), 404
        try:                                   # refus explicites avant LaTeX
            dev.generer_seance_evaluation(conn, ref_id, semaine, _options_seance())
        except (dev.DocumentEvaluationErreur, ValueError) as e:
            return jsonify({"ok": False, "error": str(e), "erreurs": [str(e)]}), 400
        config = _configuration()
        cle = _cle_seance(semaine)
        res = orch.compiler(conn, "seance_evaluation",
                            {"referentiel_id": ref_id, "semaine": semaine},
                            _options_seance(), dossier_artefacts=_dossier(ref_id),
                            cible_key=cle, racine_sources=config.chemin_sources_livrets(),
                            dossier_images=Path(_store().data_dir) / "images",
                            racine_appli=Path(current_app.root_path), timeout=600,
                            tikz_libraries=config.tikz_libraries(),
                            tblr_libraries=config.tblr_libraries())
    q = "&".join(f"{k}={v}" for k, v in _options_seance().items())
    return jsonify({"ok": bool(res.ok), "type_echec": res.type_echec,
                    "erreurs": [getattr(x, "message", str(x)) for x in (res.erreurs or [])][:20],
                    "pdf": (f"/api/progression-rituels/{ref_id}/seance/{semaine}/pdf"
                            + (f"?{q}" if q else "")) if res.ok else None})


@bp.route("/api/progression-rituels/<ref_id>/seance/<int:semaine>/pdf", methods=["GET"])
def api_seance_pdf(ref_id, semaine):
    p = (Path(_store().data_dir) / "referentiels" / ref_id / "_rituels"
         / f"{_cle_seance(semaine)}.pdf")
    if not p.is_file():
        return jsonify({"error": "Aucun PDF compilé."}), 404
    return send_file(p, mimetype="application/pdf",
                     download_name=f"seance_evaluation_{ref_id}_s{semaine:02d}.pdf")
