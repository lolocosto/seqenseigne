"""
services/cycle_auto_import.py — v0.10.2 / amélioré v0.10.3

Auto-import des structures de cycle (C03, C04, …) depuis les CSV présents
dans data/, au démarrage de l'application.

Logique :
  - Pour chaque code de cycle bien connu (C03, C04, …), si les CSV
    `<code>_themes.csv` et `<code>_sequences.csv` existent dans data/
    ET que le cycle n'a pas encore été importé en BDD (table cycles vide
    pour ce code), alors on lance importer_cycle().
  - Idempotent : un cycle déjà présent en BDD ne sera pas réimporté.

Journalisation v0.10.3 :
  - Tous les évènements sont écrits dans `data/auto_import.log` (mode 'a',
    append). C'est plus fiable que stderr seul, qui peut être avalé par
    le reloader Flask en mode debug.
  - Stderr reste utilisé en parallèle pour les démarrages "normaux".

Pourquoi pas dans `_init_db` ? Parce que `_init_db` est purement DDL ;
mélanger DDL et import de données métier complique le test isolé du schéma.
On préfère un service dédié, appelé depuis `create_app` après l'init du
SqliteStore.

Cycles connus (extensible ici plutôt qu'en config — ces codes sont stables) :
  C03 : cycle 3 (CM1, CM2, 6ème)
  C04 : cycle 4 (5ème, 4ème, 3ème)
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
import sqlite3
import sys
import traceback


# Mapping code → (nom long, description) — uniquement pour la création
# initiale du cycle en BDD. Si le cycle existe déjà, ces valeurs sont
# ignorées par importer_cycle().
_CYCLES_CONNUS = {
    "C03": ("Cycle 3", "Cycle de consolidation : CM1, CM2 et 6ème."),
    "C04": ("Cycle 4", "Cycle des approfondissements : 5ème, 4ème et 3ème."),
}


def _log(data_dir: Path, message: str) -> None:
    """Écrit une ligne horodatée dans data/auto_import.log et stderr.

    Robuste : si l'écriture fichier plante (permissions, etc.), on
    continue silencieusement vers stderr seulement.
    """
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ligne = f"[{horodatage}] {message}"
    # stderr (visible si l'app n'est pas en debug+reloader)
    print(f"[seqenseigne] {message}", file=sys.stderr)
    # fichier (toujours fiable)
    try:
        with (data_dir / "auto_import.log").open("a", encoding="utf-8") as f:
            f.write(ligne + "\n")
    except Exception:
        pass


def auto_importer_cycles(data_dir: Path, db_path: Path) -> dict:
    """
    Pour chaque cycle connu, si les CSV existent et le cycle n'est pas en
    BDD, lance importer_cycle.

    Retourne un rapport global :
      {
        "C03": {"importe": True, ...rapport...} | {"importe": False, "raison": "..."},
        "C04": ...
      }
    """
    _log(data_dir, "─── Démarrage de l'auto-import des cycles ───")
    rapport_global = {}
    for code, (nom_long, description) in _CYCLES_CONNUS.items():
        rapport_global[code] = _traiter_cycle(
            code, nom_long, description, data_dir, db_path,
        )
    _log(data_dir, "─── Fin de l'auto-import des cycles ───")
    return rapport_global


def _traiter_cycle(
    code: str,
    nom_long: str,
    description: str,
    data_dir: Path,
    db_path: Path,
) -> dict:
    """Traite un cycle individuellement.

    Cas de non-import (retournés silencieusement) :
      - "csv_absents"   : un des deux CSV manque
      - "deja_en_bdd"   : un cycle de ce code existe déjà
                          (idempotent : on ne ré-importe pas)
      - "erreur:<code>" : ImportCycleErreur levée
    """
    # Import différé pour éviter une dépendance circulaire au chargement
    # de ce module.
    from services.cycle_import import importer_cycle, ImportCycleErreur

    chemin_themes = data_dir / f"{code}_themes.csv"
    chemin_sequences = data_dir / f"{code}_sequences.csv"

    if not chemin_themes.exists() or not chemin_sequences.exists():
        _log(data_dir,
             f"  {code} : CSV absent ({chemin_themes.name} et/ou "
             f"{chemin_sequences.name}), import sauté.")
        return {"importe": False, "raison": "csv_absents"}

    # Vérifier si le cycle est déjà en BDD
    try:
        conn_check = sqlite3.connect(db_path)
        try:
            r = conn_check.execute(
                "SELECT code FROM cycles WHERE code = ?", (code,)
            ).fetchone()
        finally:
            conn_check.close()
    except sqlite3.Error as e:
        _log(data_dir,
             f"  {code} : erreur de lecture de la table cycles : {e}. "
             f"Import sauté (la BDD est peut-être en cours d'initialisation).")
        return {"importe": False, "raison": f"erreur_lecture:{e}"}

    if r is not None:
        _log(data_dir,
             f"  {code} : déjà présent en BDD, rien à faire (idempotent).")
        return {"importe": False, "raison": "deja_en_bdd"}

    # Import effectif
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            rapport = importer_cycle(
                conn,
                cycle_code=code,
                cycle_nom=nom_long,
                chemin_themes=chemin_themes,
                chemin_sequences=chemin_sequences,
                description_cycle=description,
            )
        _log(data_dir,
             f"  {code} importé : "
             f"{rapport['themes']['crees']} thèmes, "
             f"{rapport['sequences']['crees']} séquences.")
        return {"importe": True, "rapport": rapport}
    except ImportCycleErreur as e:
        _log(data_dir, f"  {code} : ImportCycleErreur — {e}")
        return {"importe": False, "raison": f"erreur:{e.code}"}
    except Exception as e:
        # Filet de sécurité : toute autre exception ne doit pas tuer l'app.
        _log(data_dir,
             f"  {code} : exception inattendue — {type(e).__name__}: {e}\n"
             + traceback.format_exc())
        return {"importe": False, "raison": f"exception:{type(e).__name__}"}
