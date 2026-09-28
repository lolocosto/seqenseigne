"""routes/cycle.py — R1.

Routes pour la gestion du cycle (thèmes + séquences du cycle).

POC en R1 : essentiellement l'import initial depuis CSV + lecture.
Les CRUD complets arriveront dans R2 (thèmes) et R3 (séquences du cycle).
"""

from __future__ import annotations
from pathlib import Path
from flask import Blueprint, jsonify, request, current_app

from services.cycle_import import (
    importer_cycle,
    lister_cycles,
    lister_themes,
    lister_sequences_du_cycle,
    ImportCycleErreur,
)


bp_cycle = Blueprint("cycle", __name__)


# ── Lecture ──────────────────────────────────────────────────────────────────

@bp_cycle.route("/api/cycles", methods=["GET"])
def api_lister_cycles():
    """Liste des cycles en base."""
    store = current_app.json_store
    with store._conn() as conn:
        return jsonify({"cycles": lister_cycles(conn)})


@bp_cycle.route("/api/cycles/<code>/themes", methods=["GET"])
def api_lister_themes(code: str):
    """Liste des thèmes d'un cycle."""
    store = current_app.json_store
    with store._conn() as conn:
        return jsonify({"themes": lister_themes(conn, code)})


@bp_cycle.route("/api/cycles/<code>/sequences", methods=["GET"])
def api_lister_sequences(code: str):
    """Liste des séquences d'un cycle."""
    store = current_app.json_store
    with store._conn() as conn:
        return jsonify({"sequences": lister_sequences_du_cycle(conn, code)})


# ── Import (admin) ───────────────────────────────────────────────────────────

@bp_cycle.route("/api/admin/cycle/importer", methods=["POST"])
def api_admin_importer_cycle():
    """
    Importe la structure d'un cycle depuis les CSV legacy.

    Body JSON (tous optionnels sauf cycle_code) :
      {
        "cycle_code":       "C04",
        "cycle_nom":        "Cycle 4",      # défaut : "Cycle <num>"
        "description":      "...",          # défaut : ""
        "chemin_themes":    "data/C04_themes.csv",     # défaut : data/<code>_themes.csv
        "chemin_sequences": "data/C04_sequences.csv"   # défaut : data/<code>_sequences.csv
      }

    Si les chemins sont relatifs, ils sont résolus par rapport au dossier
    data/ de l'appli (celui qui contient seqenseigne.db).

    Retourne un rapport détaillé :
      {
        "ok": true,
        "rapport": {
          "cycle":    {"code": "C04", "cree": true, "maj": false},
          "themes":   {"crees": 5, "mis_a_jour": 0},
          "sequences":{"crees": 14, "mis_a_jour": 0},
          "avertissements": []
        }
      }
    """
    payload = request.get_json(silent=True) or {}
    cycle_code = payload.get("cycle_code")
    if not cycle_code:
        return jsonify({
            "error": "cycle_code obligatoire",
            "code":  "champ_manquant"
        }), 400

    cycle_nom = payload.get(
        "cycle_nom",
        f"Cycle {cycle_code[-1]}" if cycle_code.startswith("C") else cycle_code
    )
    description = payload.get("description", "")

    store = current_app.json_store
    data_dir = Path(store.db_path).parent

    def _resoudre(chemin: str | None, defaut_nom: str) -> Path:
        if chemin:
            p = Path(chemin)
            return p if p.is_absolute() else (data_dir / p).resolve()
        return (data_dir / defaut_nom).resolve()

    chemin_themes = _resoudre(
        payload.get("chemin_themes"),
        f"{cycle_code}_themes.csv"
    )
    chemin_sequences = _resoudre(
        payload.get("chemin_sequences"),
        f"{cycle_code}_sequences.csv"
    )

    try:
        with store._conn() as conn:
            rapport = importer_cycle(
                conn,
                cycle_code=cycle_code,
                cycle_nom=cycle_nom,
                chemin_themes=chemin_themes,
                chemin_sequences=chemin_sequences,
                description_cycle=description,
            )
    except ImportCycleErreur as e:
        return jsonify({
            "error": str(e),
            "code":  e.code
        }), 400

    return jsonify({"ok": True, "rapport": rapport})


# ── v0.10.3 — Diagnostic + relance manuelle de l'auto-import ───────────────


@bp_cycle.route("/api/admin/cycles/auto-import-status", methods=["GET"])
def api_auto_import_status():
    """Diagnostic de l'auto-import.

    Pour chaque cycle connu, indique :
      - csv_themes_present : bool
      - csv_sequences_present : bool
      - en_bdd : bool

    Permet de comprendre pourquoi l'auto-import au démarrage n'a pas
    fait ce qu'on attendait, sans devoir lire les logs.
    """
    from services.cycle_auto_import import _CYCLES_CONNUS
    store = current_app.json_store
    data_dir = store.data_dir
    db_path = store.db_path

    import sqlite3
    cycles_en_bdd = set()
    try:
        with sqlite3.connect(db_path) as c:
            for r in c.execute("SELECT code FROM cycles"):
                cycles_en_bdd.add(r[0])
    except sqlite3.Error:
        pass

    rep = []
    for code in _CYCLES_CONNUS.keys():
        rep.append({
            "code": code,
            "csv_themes_present":    (data_dir / f"{code}_themes.csv").exists(),
            "csv_sequences_present": (data_dir / f"{code}_sequences.csv").exists(),
            "en_bdd": code in cycles_en_bdd,
        })

    log_path = data_dir / "auto_import.log"
    log_excerpt = ""
    if log_path.exists():
        try:
            # Dernières ~50 lignes du log
            with log_path.open("r", encoding="utf-8") as f:
                lignes = f.readlines()
            log_excerpt = "".join(lignes[-50:])
        except Exception:
            log_excerpt = "(lecture du log impossible)"

    return jsonify({
        "cycles": rep,
        "log_path": str(log_path),
        "log_excerpt": log_excerpt,
    })


@bp_cycle.route("/api/admin/cycles/auto-import-relancer", methods=["POST"])
def api_auto_import_relancer():
    """Relance manuelle de l'auto-import. Idempotent : ne fait rien pour
    les cycles déjà en BDD. Utile si le démarrage initial a échoué et
    qu'on veut réessayer sans redémarrer toute l'app.
    """
    from services.cycle_auto_import import auto_importer_cycles
    store = current_app.json_store
    rep = auto_importer_cycles(store.data_dir, store.db_path)
    return jsonify({"ok": True, "rapport": rep})
