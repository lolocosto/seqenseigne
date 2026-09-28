"""
services/cycle_import.py — R1.

Import initial de la structure du cycle depuis les CSV legacy :
  - C04_themes.csv    → tables themes
  - C04_sequences.csv → table sequences_du_cycle

Le cycle parent (ex: 'C04') est créé si absent.

Idempotent :
  - Si le cycle existe déjà, on l'utilise
  - Les thèmes sont rapprochés par (cycle_code, code) — UPSERT
  - Les séquences sont rapprochées par (cycle_code, code) — UPSERT

Format attendu des CSV :
  C04_themes.csv    : Code, Nom, CodeCouleur, Description
  C04_sequences.csv : Code, Numero, Nom, Theme  (Theme = code d'un thème du cycle)

Utilisable en ligne de commande et depuis une route Flask (via importer_cycle()).
"""

from __future__ import annotations
import csv
import sqlite3
from pathlib import Path

from persistence.ids import nouveau_id_theme, nouveau_id_sequence_du_cycle


# ── Exceptions ───────────────────────────────────────────────────────────────

class ImportCycleErreur(Exception):
    """Erreur lors de l'import de la structure du cycle."""
    def __init__(self, message: str, code: str = "erreur"):
        super().__init__(message)
        self.code = code


# ── Import principal ─────────────────────────────────────────────────────────

def importer_cycle(
    conn: sqlite3.Connection,
    cycle_code: str,
    cycle_nom: str,
    chemin_themes: Path,
    chemin_sequences: Path,
    description_cycle: str = "",
) -> dict:
    """
    Importe la structure d'un cycle (thèmes + séquences) depuis deux CSV.

    Retourne un rapport avec le nombre d'éléments créés/mis à jour et
    d'éventuels avertissements.

    Lève ImportCycleErreur si :
      - Un CSV référencé est absent
      - Une référence à un thème inconnu existe dans le CSV des séquences
    """
    if not chemin_themes.exists():
        raise ImportCycleErreur(
            f"Fichier thèmes introuvable : {chemin_themes}",
            code="themes_absent"
        )
    if not chemin_sequences.exists():
        raise ImportCycleErreur(
            f"Fichier séquences introuvable : {chemin_sequences}",
            code="sequences_absent"
        )

    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    rapport = {
        "cycle":           {"code": cycle_code, "cree": False, "maj": False},
        "themes":          {"crees": 0, "mis_a_jour": 0},
        "sequences":       {"crees": 0, "mis_a_jour": 0},
        "avertissements":  [],
    }

    # 1. Cycle : créer ou rien
    existant = conn.execute(
        "SELECT code FROM cycles WHERE code = ?", (cycle_code,)
    ).fetchone()
    if existant:
        rapport["cycle"]["maj"] = True
    else:
        conn.execute(
            "INSERT INTO cycles (code, nom, description) VALUES (?, ?, ?)",
            (cycle_code, cycle_nom, description_cycle)
        )
        rapport["cycle"]["cree"] = True

    # 2. Thèmes
    themes_par_code: dict[str, str] = {}  # code → id (pour résoudre séquences)
    with chemin_themes.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        colonnes_attendues = {"Code", "Nom", "CodeCouleur", "Description"}
        if set(reader.fieldnames or []) < colonnes_attendues:
            raise ImportCycleErreur(
                f"Colonnes manquantes dans {chemin_themes} : "
                f"{colonnes_attendues - set(reader.fieldnames or [])}",
                code="themes_colonnes"
            )

        for ordre, ligne in enumerate(reader, start=1):
            code         = (ligne["Code"] or "").strip()
            nom          = (ligne["Nom"] or "").strip()
            code_couleur = (ligne["CodeCouleur"] or "").strip()
            description  = ligne["Description"] or ""

            if not code or not nom:
                rapport["avertissements"].append(
                    f"Thème ligne {ordre} : code ou nom vide, ignoré"
                )
                continue

            existant = conn.execute(
                "SELECT id FROM themes WHERE cycle_code = ? AND code = ?",
                (cycle_code, code)
            ).fetchone()
            if existant:
                conn.execute(
                    "UPDATE themes "
                    "SET nom = ?, code_couleur = ?, description = ?, ordre = ? "
                    "WHERE id = ?",
                    (nom, code_couleur, description, ordre, existant["id"])
                )
                themes_par_code[code] = existant["id"]
                rapport["themes"]["mis_a_jour"] += 1
            else:
                theme_id = nouveau_id_theme()
                conn.execute(
                    "INSERT INTO themes "
                    "(id, cycle_code, code, nom, code_couleur, description, ordre) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (theme_id, cycle_code, code, nom, code_couleur, description, ordre)
                )
                themes_par_code[code] = theme_id
                rapport["themes"]["crees"] += 1

    # 3. Séquences
    with chemin_sequences.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        colonnes_attendues = {"Code", "Numero", "Nom", "Theme"}
        if set(reader.fieldnames or []) < colonnes_attendues:
            raise ImportCycleErreur(
                f"Colonnes manquantes dans {chemin_sequences} : "
                f"{colonnes_attendues - set(reader.fieldnames or [])}",
                code="sequences_colonnes"
            )

        for ligne in reader:
            code        = (ligne["Code"] or "").strip()
            numero_str  = (ligne["Numero"] or "").strip()
            nom         = (ligne["Nom"] or "").strip()
            theme_code  = (ligne["Theme"] or "").strip()

            if not code or not nom or not numero_str:
                rapport["avertissements"].append(
                    f"Séquence {code or '?'} : données incomplètes, ignorée"
                )
                continue

            try:
                numero = int(numero_str)
            except ValueError:
                rapport["avertissements"].append(
                    f"Séquence {code} : numéro '{numero_str}' non numérique, ignorée"
                )
                continue

            theme_id = None
            if theme_code:
                if theme_code not in themes_par_code:
                    # On récupère ce qu'il y a en base (au cas où le thème a
                    # été inséré par un import précédent mais pas dans ce fichier CSV)
                    r = conn.execute(
                        "SELECT id FROM themes WHERE cycle_code = ? AND code = ?",
                        (cycle_code, theme_code)
                    ).fetchone()
                    if r:
                        themes_par_code[theme_code] = r["id"]
                        theme_id = r["id"]
                    else:
                        rapport["avertissements"].append(
                            f"Séquence {code} : thème '{theme_code}' inconnu, "
                            "thème non renseigné"
                        )
                else:
                    theme_id = themes_par_code[theme_code]

            existant = conn.execute(
                "SELECT id FROM sequences_du_cycle WHERE cycle_code = ? AND code = ?",
                (cycle_code, code)
            ).fetchone()
            if existant:
                conn.execute(
                    "UPDATE sequences_du_cycle "
                    "SET numero = ?, nom = ?, theme_id = ? "
                    "WHERE id = ?",
                    (numero, nom, theme_id, existant["id"])
                )
                rapport["sequences"]["mis_a_jour"] += 1
            else:
                seq_id = nouveau_id_sequence_du_cycle()
                conn.execute(
                    "INSERT INTO sequences_du_cycle "
                    "(id, cycle_code, code, numero, nom, theme_id) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (seq_id, cycle_code, code, numero, nom, theme_id)
                )
                rapport["sequences"]["crees"] += 1

    conn.commit()
    return rapport


# ── Lecteurs ─────────────────────────────────────────────────────────────────

def lister_cycles(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [
        dict(r) for r in conn.execute(
            "SELECT code, nom, description FROM cycles ORDER BY code"
        )
    ]


def lister_themes(conn: sqlite3.Connection, cycle_code: str) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [
        dict(r) for r in conn.execute(
            "SELECT id, code, nom, code_couleur, description, ordre "
            "FROM themes WHERE cycle_code = ? ORDER BY ordre, code",
            (cycle_code,)
        )
    ]


def lister_sequences_du_cycle(
    conn: sqlite3.Connection,
    cycle_code: str,
) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [
        dict(r) for r in conn.execute(
            "SELECT s.id, s.code, s.numero, s.nom, "
            "       s.theme_id, t.code AS theme_code, t.nom AS theme_nom "
            "FROM sequences_du_cycle s "
            "LEFT JOIN themes t ON t.id = s.theme_id "
            "WHERE s.cycle_code = ? "
            "ORDER BY s.numero",
            (cycle_code,)
        )
    ]
