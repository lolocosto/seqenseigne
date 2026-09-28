"""routes/versions.py — Versions (snapshots) de livrets."""

from flask import Blueprint, jsonify, request, current_app
from services import versions as svc
from services.sequences import build_sequences, trouver_sequence

bp = Blueprint("versions", __name__)


def _stores():
    a = current_app
    return a.json_store, a.yaml_store, a.csv_store


@bp.route("/api/versions", methods=["GET"])
def api_versions_get():
    js, _, _ = _stores()
    niveau = request.args.get("niveau")
    seq    = request.args.get("seq")
    d = js.lire_versions()
    if niveau and seq:
        return jsonify(d.get(niveau, {}).get(seq, []))
    if niveau:
        return jsonify(d.get(niveau, {}))
    return jsonify(d)


@bp.route("/api/versions/creer", methods=["POST"])
def api_versions_creer():
    js, ys, cs = _stores()
    body   = request.get_json()
    niveau = body.get("niveau", "").strip()
    seq    = body.get("seq", "").strip()
    tag    = body.get("tag", "").strip()
    label  = body.get("label", "").strip()

    if not niveau or not seq or not tag:
        return jsonify({"error": "niveau, seq et tag sont requis"}), 400

    sequences = build_sequences(niveau, ys, js, cs)
    seq_data  = trouver_sequence(sequences, seq)
    if not seq_data:
        return jsonify({"error": "séquence introuvable"}), 404

    versions, snapshot, erreur = svc.creer_snapshot(
        js.lire_versions(), niveau, seq, tag, label, seq_data
    )
    if erreur:
        return jsonify({"error": erreur}), 409
    js.ecrire_versions(versions)
    return jsonify(snapshot)


@bp.route("/api/versions/supprimer", methods=["POST"])
def api_versions_supprimer():
    js, _, _ = _stores()
    body   = request.get_json()
    niveau = body.get("niveau", "").strip()
    seq    = body.get("seq", "").strip()
    tag    = body.get("tag", "").strip()

    versions, erreur = svc.supprimer_snapshot(
        js.lire_versions(), js.lire_classes(), niveau, seq, tag
    )
    if erreur:
        return jsonify({"error": erreur}), 409
    js.ecrire_versions(versions)
    return jsonify({"ok": True})
