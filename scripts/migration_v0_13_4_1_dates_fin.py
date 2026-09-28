#!/usr/bin/env python3
"""scripts/migration_v0_13_4_1_dates_fin.py — v0.13.4.1

Migration ponctuelle (idempotente) : pose `date_fin` sur les
référentiels obsolètes pour rétablir la cohérence des données.

Contexte
--------
Tous les référentiels actuels en BDD ont `date_fin = NULL`, alors que
seul le plus récent par niveau devrait avoir cet état. Conséquence :
le filtre `WHERE rn.date_fin IS NULL` (utilisé dans
services/latex_rendu_atome.py pour résoudre les macros LaTeX) renvoie
plusieurs candidats au lieu d'un seul, ce qui rend le résultat
non-déterministe.

Règle de migration
------------------
Pour chaque niveau, le référentiel de plus grande version garde
`date_fin = NULL` (= "courant"). Tous les autres reçoivent comme
`date_fin` le 1er septembre de la version du référentiel suivant
de même niveau (= "remplacé à la rentrée suivante").

Exemples :
- N10_v2021 (suivant : N10_v2022) → date_fin = '2022-09-01'
- N10_v2024 (le plus récent N10) → date_fin = NULL (inchangé)
- N11_v2021 (suivant : N11_v2023) → date_fin = '2023-09-01'

Sécurités
---------
- **Dry-run par défaut** : affiche ce qui serait modifié, ne touche
  à rien.
- Avec `--apply`, demande confirmation interactive (OUI) sauf si
  `--yes` est passé.
- **Idempotence** : si un référentiel a déjà une `date_fin` non-NULL,
  il est laissé tel quel (no-op, pas d'écrasement).
- Ne touche jamais au référentiel le plus récent d'un niveau.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Optional


def calculer_modifications(conn: sqlite3.Connection) -> list[dict]:
    """Détermine la liste des référentiels à mettre à jour.

    Retourne une liste de dicts {id, niveau, version, date_fin_actuelle,
    date_fin_cible} pour les référentiels qui DEVRAIENT être modifiés
    (i.e. n'ont pas déjà une date_fin posée).

    Pour chaque niveau, le référentiel de plus grande version est
    considéré comme courant (date_fin = NULL attendue) et exclu de la
    liste. Les autres reçoivent comme date_fin cible le 1er septembre
    de la version du référentiel suivant.
    """
    # Lecture de tous les référentiels, triés par (niveau, version).
    rows = list(conn.execute(
        "SELECT id, niveau, version, date_fin "
        "FROM referentiel_niveaux "
        "ORDER BY niveau, version"
    ))

    # Groupement par niveau.
    par_niveau: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        par_niveau.setdefault(r["niveau"], []).append(r)

    modifications = []
    for niveau, refs in par_niveau.items():
        # Trier par version croissante pour pouvoir lire le suivant.
        refs.sort(key=lambda r: r["version"])
        # Tous sauf le dernier : date_fin cible = 1er sept de la version
        # du suivant.
        for i in range(len(refs) - 1):
            ref = refs[i]
            suivant = refs[i + 1]
            date_fin_cible = f"{suivant['version']}-09-01"
            # Idempotence : skip si déjà posée.
            if ref["date_fin"] is not None:
                continue
            modifications.append({
                "id":               ref["id"],
                "niveau":           ref["niveau"],
                "version":          ref["version"],
                "date_fin_actuelle": ref["date_fin"],
                "date_fin_cible":   date_fin_cible,
            })
        # Le dernier : on s'attend à date_fin = NULL.
        # Si elle est non-NULL on signale (cas inattendu, mais on ne
        # touche pas non plus, principe de moindre surprise).

    return modifications


def afficher_plan(modifications: list[dict]) -> None:
    """Affiche le plan de migration en tableau lisible."""
    if not modifications:
        print("Aucune modification à appliquer (BDD déjà cohérente).")
        return
    print(f"{'id':<14} {'niveau':<6} {'version':<8} "
          f"{'date_fin actuelle':<20} {'date_fin cible':<14}")
    print("-" * 70)
    for m in modifications:
        actuelle = m["date_fin_actuelle"] or "(NULL)"
        print(f"{m['id']:<14} {m['niveau']:<6} {m['version']:<8} "
              f"{actuelle:<20} {m['date_fin_cible']:<14}")
    print()
    print(f"Total : {len(modifications)} référentiel(s) à modifier.")


def appliquer(conn: sqlite3.Connection, modifications: list[dict]) -> int:
    """Applique les modifications. Retourne le nombre de lignes modifiées."""
    n = 0
    for m in modifications:
        cur = conn.execute(
            "UPDATE referentiel_niveaux SET date_fin = ? WHERE id = ?",
            (m["date_fin_cible"], m["id"]),
        )
        n += cur.rowcount
    conn.commit()
    return n


def confirmer_interactif() -> bool:
    """Demande confirmation interactive. Accepte uniquement 'OUI'."""
    rep = input("Appliquer les modifications ? Tapez OUI pour confirmer : ")
    return rep.strip() == "OUI"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pose les date_fin sur les référentiels obsolètes "
                    "(v0.13.4.1).",
    )
    parser.add_argument(
        "--db",
        default="data/seqenseigne.db",
        help="Chemin vers la base SQLite (défaut : data/seqenseigne.db)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Appliquer réellement les modifications (sinon : dry-run)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Sauter la confirmation interactive (pour batch / tests)",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERREUR : base introuvable : {db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        modifications = calculer_modifications(conn)
        afficher_plan(modifications)

        if not modifications:
            return 0

        if not args.apply:
            print()
            print("Mode dry-run (aucune modification appliquée).")
            print("Relancer avec --apply pour appliquer.")
            return 0

        if not args.yes and not confirmer_interactif():
            print("Abandon.")
            return 1

        n = appliquer(conn, modifications)
        print(f"\nOK : {n} ligne(s) modifiée(s).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
