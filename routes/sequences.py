"""routes/sequences.py — Séquences, composition de livrets, bibliothèque.

Nettoyage post-R4e4b :
  - La route PUT /api/composition/<niveau>/<seq> a été supprimée avec la
    disparition du bouton « Enregistrer dans le YAML » de l'atelier
    Séquence (niveau). Toute l'édition passe désormais par les routes v2
    (/api/v2/...). save_sequences_yaml reste utilisé uniquement comme
    fallback automatique de build_sequences() et disparaîtra avec l'Option C.
"""

from flask import Blueprint, jsonify, request, current_app
from services.sequences import build_sequences, trouver_sequence
from services.latex_gen import generer_livret_tex
import os

bp = Blueprint("sequences", __name__)


def _stores():
    a = current_app
    return a.json_store, a.yaml_store, a.csv_store


@bp.route("/api/sequences")
def api_sequences():
    js, ys, cs = _stores()
    niveau = request.args.get("niveau", "N10")
    return jsonify(build_sequences(niveau, ys, js, cs))


@bp.route("/api/referentiel/sequences")
def api_referentiel_sequences():
    _, _, cs = _stores()
    return jsonify(cs.sequences_avec_themes())


@bp.route("/api/composition/<niveau>/<seq>", methods=["GET"])
def api_composition_get(niveau, seq):
    js, ys, cs = _stores()
    sequences = build_sequences(niveau, ys, js, cs)
    seq_data = trouver_sequence(sequences, seq)
    if not seq_data:
        return jsonify({"error": "séquence introuvable"}), 404

    raw = ys.lire_brut(niveau) or {}
    raw_seq = next((s for s in raw.get("sequences", []) if s["code"] == seq), {})

    return jsonify({
        "code":    seq_data["code"],
        "nom":     seq_data["nom"],
        "theme":   raw_seq.get("theme", ""),
        "paquets": raw_seq.get("paquets_supplementaires", []),
        "prerequis": raw_seq.get("prerequis", {}),
        "objectifs": [
            {
                "code":      obj["code"],
                "nom":       obj["nom"],
                "is01":      obj.get("is01", False),
                "fin_cycle": raw_obj.get("fin_cycle", False),
                "criteres":  raw_obj.get("criteres", {}),
                "notions":   raw_obj.get("notions", []),
                "exercices": obj["exercices"],
            }
            for obj in seq_data["objectifs"]
            for raw_obj in (
                next((o for o in raw_seq.get("objectifs", [])
                      if o["code"] == obj["code"]), {}),
            )
        ],
        "connaissances": raw_seq.get("connaissances", []),
    })


@bp.route("/api/composition/<niveau>/<seq>/generer", methods=["POST"])
def api_composition_generer(niveau, seq):
    js, ys, cs = _stores()
    body = request.get_json() or {}
    sequences = build_sequences(niveau, ys, js, cs)
    seq_data = trouver_sequence(sequences, seq)
    if not seq_data:
        return jsonify({"error": "séquence introuvable"}), 404

    raw = ys.lire_brut(niveau) or {}
    raw_seq = next((s for s in raw.get("sequences", []) if s["code"] == seq), {})
    tex = generer_livret_tex(niveau, seq, raw_seq, seq_data)

    fichier_ecrit = None
    chemin = body.get("chemin_sequences", "").strip()
    if chemin:
        dest_dir = os.path.join(chemin, niveau, "livrets_de_sequence")
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, f"{niveau}_{seq}_Livret.tex")
        with open(dest, "w", encoding="utf-8") as fout:
            fout.write(tex)
        fichier_ecrit = dest

    return jsonify({"ok": True, "tex": tex, "fichier": fichier_ecrit})


@bp.route("/api/bibliotheque/<niveau>/<seq>", methods=["GET"])
def api_bibliotheque(niveau, seq):
    js, ys, cs = _stores()
    sequences_all = build_sequences(niveau, ys, js, cs)
    seq_data = trouver_sequence(sequences_all, seq)
    if not seq_data:
        return jsonify({"error": "séquence introuvable"}), 404

    all_F, all_A, all_E = set(), set(), set()
    for obj in seq_data["objectifs"]:
        if obj.get("is01"):
            continue
        ex = obj["exercices"]
        all_F.update(ex.get("F", []))
        all_A.update(ex.get("A", []))
        all_E.update(ex.get("E", []))

    inventaire = {
        "F": [{"num": n, "fichier": f"{niveau}{seq}F{n:02d}.tex"} for n in sorted(all_F)],
        "A": [{"num": n, "fichier": f"{niveau}{seq}A{n:02d}.tex"} for n in sorted(all_A)],
        "E": [{"num": n, "fichier": f"{niveau}{seq}E{n:02d}.tex"} for n in sorted(all_E)],
        "revisions": [],
    }

    niveau_prec = f"N{int(niveau[1:]) - 1:02d}"
    seq_prec_all = build_sequences(niveau_prec, ys, js, cs)
    seq_prec = trouver_sequence(seq_prec_all, seq)
    if seq_prec:
        rev_A = set()
        for obj in seq_prec["objectifs"]:
            if not obj.get("is01"):
                rev_A.update(obj["exercices"].get("A", []))
        inventaire["revisions"] = [
            {"num": n, "fichier": f"{niveau_prec}{seq}A{n:02d}.tex"}
            for n in sorted(rev_A)
        ]

    return jsonify(inventaire)
