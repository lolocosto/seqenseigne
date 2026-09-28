"""routes/scanner.py — Import de fichiers LaTeX via le scanner."""

from flask import Blueprint, jsonify, request, current_app
from importers.scanner_latex import scanner_niveau, scanner_vers_bdd

bp = Blueprint("scanner", __name__)


def _js():
    return current_app.json_store


@bp.route("/api/scanner/apercu", methods=["GET"])
def api_scanner_apercu():
    chemin = request.args.get("chemin", "").strip()
    niveau = request.args.get("niveau", "N11").strip()
    if not chemin:
        return jsonify({"error": "chemin manquant"}), 400
    data = scanner_niveau(chemin, niveau)
    return jsonify({
        "notions":   len(data["notions"]),
        "methodes":  len(data["methodes"]),
        "exercices": len(data["exercices"]),
        "livrets":   len(data["livrets"]),
        "erreurs":   data["erreurs"],
    })


@bp.route("/api/scanner/detail", methods=["GET"])
def api_scanner_detail():
    chemin = request.args.get("chemin", "").strip()
    niveau = request.args.get("niveau", "N11").strip()
    if not chemin:
        return jsonify({"error": "chemin manquant"}), 400
    js = _js()
    data = scanner_niveau(chemin, niveau)

    notions_ex   = {n.get("fichier", "") for n in js.lire_notions()}
    methodes_ex  = {m.get("fichier", "") for m in js.lire_methodes()}
    exercices_ex = {e.get("fichier", "") for e in js.lire_exercices()}
    livrets_ex   = {(l["niveau"], l["sequence"]) for l in js.lire_livrets_importes()}

    return jsonify({
        "notions":   [{**n, "_statut": "existant" if n.get("fichier") in notions_ex   else "nouveau"} for n in data["notions"]],
        "methodes":  [{**m, "_statut": "existant" if m.get("fichier") in methodes_ex  else "nouveau"} for m in data["methodes"]],
        "exercices": [{**e, "_statut": "existant" if e.get("fichier") in exercices_ex else "nouveau"} for e in data["exercices"]],
        "livrets":   [{**l, "_statut": "existant" if (l["niveau"], l["sequence"]) in livrets_ex else "nouveau"} for l in data["livrets"]],
        "erreurs":   data["erreurs"],
    })


@bp.route("/api/scanner/lancer", methods=["POST"])
def api_scanner_lancer():
    body   = request.get_json(force=True)
    chemin = body.get("chemin_sequences", "").strip()
    niveau = body.get("niveau", "N11").strip()
    if not chemin:
        return jsonify({"error": "chemin_sequences manquant"}), 400
    js = _js()
    cs = current_app.csv_store
    data   = scanner_niveau(chemin, niveau)
    # `chemin` pointe vers le dossier parent qui contient N10/, N11/, N12/
    # et éventuellement les plans de travail. On le passe tel quel :
    # `peupler_v2_depuis_base` sait chercher en direct, dans le sous-dossier
    # du niveau, ou récursivement.
    resume = scanner_vers_bdd(data, js, cs, plans_dir=chemin)
    return jsonify(resume)
