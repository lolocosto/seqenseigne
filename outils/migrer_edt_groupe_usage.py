#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""outils/migrer_edt_groupe_usage.py — v0.20.2

Reventile les cases d'EDT existantes de l'ancien modèle (un seul champ `usage`
mélangeant groupe et usage) vers le nouveau modèle à deux champs :
  - groupe : classe_entiere | demi_classe_A/_B | groupe_option |
             groupe_horaire_ordinaire | autre
  - usage  : cours | vie_de_classe | co_animation | autre

Règles de reventilation (à partir de l'ancien `usage` et du `libelle`) :
  - ancien usage 'classe_entiere'            -> groupe=classe_entiere
  - ancien usage 'demi_classe_A'/'_B'        -> groupe idem
  - ancien usage 'groupe_option'             -> groupe=groupe_option
  - ancien usage 'groupe_horaire_ordinaire'  -> groupe=groupe_horaire_ordinaire
  - ancien usage 'autre'                     -> groupe=classe_entiere (par défaut)
  Puis, pour le nouvel `usage`, on déduit du libellé (insensible à la casse) :
  - libellé contient 'co-anim' / 'coanim'    -> usage=co_animation
  - libellé contient 'vie de classe'         -> usage=vie_de_classe
  - libellé contient 'concert'               -> usage=autre (précisé au libellé)
  - sinon                                    -> usage=cours

La migration NE fait qu'écrire les colonnes `groupe` et `usage` ; elle ne
touche à rien d'autre. Idempotente (ré-exécutable). Toujours tester sur une
copie de la base d'abord.

Usage :
    python -m outils.migrer_edt_groupe_usage              # dry-run
    python -m outils.migrer_edt_groupe_usage --apply      # applique (confirme)
    python -m outils.migrer_edt_groupe_usage --apply --yes
    python -m outils.migrer_edt_groupe_usage --db chemin/vers/seqenseigne.db
"""

import argparse
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "seqenseigne.db"

GROUPES_CONNUS = {
    "classe_entiere", "demi_classe_A", "demi_classe_B",
    "groupe_option", "groupe_horaire_ordinaire", "autre",
}


def _reventiler(ancien_usage: str, libelle: str) -> tuple[str, str]:
    """Retourne (groupe, usage) selon l'ancien usage et le libellé."""
    au = (ancien_usage or "").strip()
    lib = (libelle or "").lower()

    # Groupe : repris de l'ancien usage s'il désignait un groupe ; sinon défaut.
    if au in GROUPES_CONNUS and au != "autre":
        groupe = au
    else:
        groupe = "classe_entiere"

    # Usage : déduit du libellé.
    if "co-anim" in lib or "coanim" in lib or "co anim" in lib:
        usage = "co_animation"
    elif "vie de classe" in lib or "vie-de-classe" in lib:
        usage = "vie_de_classe"
    elif "concert" in lib:
        usage = "autre"
    elif au == "autre":
        usage = "autre"
    else:
        usage = "cours"

    return groupe, usage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--db", default=str(DB))
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    # La colonne `groupe` doit exister (créée par la migration de schéma au
    # premier lancement du serveur en v0.20.2).
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(edt_creneaux)")}
    if "groupe" not in cols:
        print("⚠ La colonne `groupe` n'existe pas encore. Lance d'abord le "
              "serveur une fois (la migration de schéma l'ajoute), puis "
              "relance ce script.")
        sys.exit(1)

    rows = conn.execute(
        "SELECT id, jour, creneau_code, semaine, usage, libelle, groupe "
        "FROM edt_creneaux ORDER BY jour, creneau_code, semaine").fetchall()

    plan = []
    for r in rows:
        groupe, usage = _reventiler(r["usage"], r["libelle"])
        change = (groupe != r["groupe"]) or (usage != r["usage"])
        plan.append((r, groupe, usage, change))

    n_change = sum(1 for _, _, _, ch in plan if ch)
    print(f"EDT : {len(rows)} cases, {n_change} à reventiler.")
    print("\n  jour créneau sem | ancien usage / libellé -> groupe + usage")
    for r, groupe, usage, ch in plan:
        flag = "*" if ch else " "
        print(f"  {flag} {r['jour']} {r['creneau_code']:<3} {r['semaine']:<2} | "
              f"{(r['usage'] or ''):<24} {(r['libelle'] or '')!r:<26} -> "
              f"{groupe} + {usage}")

    if not args.apply:
        print("\n(dry-run — utilise --apply pour écrire)")
        return
    if not args.yes:
        rep = input("\nAppliquer la reventilation ? [o/N] ").strip().lower()
        if rep not in ("o", "oui", "y", "yes"):
            print("Annulé.")
            return

    try:
        for r, groupe, usage, ch in plan:
            if ch:
                conn.execute(
                    "UPDATE edt_creneaux SET groupe=?, usage=? WHERE id=?",
                    (groupe, usage, r["id"]))
        conn.commit()
        print(f"\n✅ {n_change} cases reventilées.")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Erreur, rollback : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
