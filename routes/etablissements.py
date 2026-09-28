"""
routes/etablissements.py — API REST des établissements.

Endpoints :
  GET  /api/etablissements                → liste
  GET  /api/etablissements/<id>           → détail
  POST /api/etablissements                → créer (état 'propose')
  PATCH /api/etablissements/<id>          → mettre à jour méta
  POST /api/etablissements/<id>/valider   → valider par UAI (annuaire EN)
  DELETE /api/etablissements/<id>         → supprimer (si non utilisé)
"""

from flask import Blueprint, request, jsonify, current_app
from services import etablissements as svc_etab

bp = Blueprint("etablissements", __name__)


def _store():
    return current_app.json_store


@bp.route("/api/etablissements", methods=["GET"])
def api_lister():
    return jsonify({"etablissements": svc_etab.lister(_store())})


@bp.route("/api/etablissements/<eid>", methods=["GET"])
def api_lire(eid):
    etab = svc_etab.lire(_store(), eid)
    if not etab:
        return jsonify({"error": f"Établissement {eid} introuvable"}), 404
    return jsonify(etab)


@bp.route("/api/etablissements", methods=["POST"])
def api_creer():
    body = request.get_json(silent=True) or {}
    nom = body.get("nom", "").strip()
    if not nom:
        return jsonify({"error": "nom requis"}), 400
    etab = svc_etab.creer(
        _store(),
        nom=nom,
        academie=body.get("academie","").strip(),
        ville=body.get("ville","").strip(),
        adresse=body.get("adresse","").strip(),
        uai=body.get("uai","").strip(),
    )
    return jsonify(etab), 201


@bp.route("/api/etablissements/<eid>", methods=["PATCH"])
def api_modifier(eid):
    body = request.get_json(silent=True) or {}
    etab = svc_etab.mettre_a_jour(_store(), eid, body)
    if not etab:
        return jsonify({"error": f"Établissement {eid} introuvable"}), 404
    return jsonify(etab)


@bp.route("/api/etablissements/<eid>/valider", methods=["POST"])
def api_valider(eid):
    body = request.get_json(silent=True) or {}
    uai = body.get("uai","").strip()
    if not uai:
        return jsonify({"error": "uai requis"}), 400
    try:
        etab = svc_etab.valider_par_uai(_store(), eid, uai)
    except svc_etab.DoublonEtablissement as e:
        # 409 Conflict : l'UI doit proposer une fusion
        return jsonify({
            "error":         str(e),
            "code":          "doublon_detecte",
            "etab_cible_id": e.etab_cible_id,
            "nom_officiel":  e.nom,
        }), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(etab)


@bp.route("/api/etablissements/<source_id>/fusionner", methods=["POST"])
def api_fusionner(source_id):
    """
    Fusionne source dans cible.
    Body : { "cible_id": "et_xxx" }
    """
    body = request.get_json(silent=True) or {}
    cible_id = body.get("cible_id", "").strip()
    if not cible_id:
        return jsonify({"error": "cible_id requis"}), 400
    try:
        cible = svc_etab.fusionner(_store(), source_id, cible_id)
    except svc_etab.ConflitFusion as e:
        return jsonify({
            "error":   str(e),
            "code":    e.code,
            "details": e.details,
        }), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(cible)


@bp.route("/api/etablissements/<eid>", methods=["DELETE"])
def api_supprimer(eid):
    try:
        _store().supprimer_etablissement(eid)
    except Exception as e:
        # ON DELETE RESTRICT si établissement utilisé → sqlite3.IntegrityError
        return jsonify({"error": f"Suppression impossible : {e}"}), 400
    return jsonify({"ok": True})
