#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""outils/purge_rgpd_eleves.py — v0.23.0

Purge RGPD des données d'élèves des années scolaires anciennes.

Contexte (cf. audit) : les données d'élèves (mineurs) ne doivent pas être
conservées indéfiniment. Ce script supprime les données rattachées aux années
scolaires antérieures à un seuil choisi par l'enseignant/le DPO :
  - liens élève↔classe (eleves_classes) des classes de ces années ;
  - suivi et niveaux (résultats) rattachés à ces classes ;
  - les élèves qui, après purge, n'appartiennent plus à AUCUNE classe conservée
    (un élève présent aussi dans une année récente est préservé).

La DURÉE DE CONSERVATION n'est pas imposée : elle est passée en paramètre
(`--conserver-depuis AAAA-AAAA` ou `--garder-annees N`). À définir avec le DPO
de l'établissement.

Dry-run par défaut : n'affiche que ce qui serait supprimé. `--apply` pour
exécuter. Transactionnel. Toujours tester sur une copie de la base.

Usage :
    # aperçu : purger tout ce qui précède 2024-2025
    python -m outils.purge_rgpd_eleves --conserver-depuis 2024-2025

    # garder les 2 dernières années scolaires (par rapport à aujourd'hui)
    python -m outils.purge_rgpd_eleves --garder-annees 2

    # exécuter
    python -m outils.purge_rgpd_eleves --conserver-depuis 2024-2025 --apply
"""

import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "seqenseigne.db"


def _annee_scolaire_courante() -> str:
    d = date.today()
    deb = d.year if d.month >= 9 else d.year - 1
    return f"{deb}-{deb + 1}"


def _seuil_depuis_garder(n: int) -> str:
    """Année scolaire = courante - (n-1). Ex. n=2 en 2026-2027 → 2025-2026."""
    cur = _annee_scolaire_courante()
    deb = int(cur.split("-")[0]) - (n - 1)
    return f"{deb}-{deb + 1}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conserver-depuis", default=None,
                    help="année scolaire à partir de laquelle on CONSERVE "
                         "(ex. 2024-2025) ; tout ce qui précède est purgé")
    ap.add_argument("--garder-annees", type=int, default=None,
                    help="nombre d'années scolaires récentes à conserver")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--db", default=str(DB))
    args = ap.parse_args()

    if args.conserver_depuis:
        seuil = args.conserver_depuis
    elif args.garder_annees:
        seuil = _seuil_depuis_garder(args.garder_annees)
    else:
        print("Préciser --conserver-depuis AAAA-AAAA ou --garder-annees N.")
        sys.exit(2)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    # Années à purger = celles strictement antérieures au seuil.
    annees = [r[0] for r in conn.execute(
        "SELECT DISTINCT annee FROM classes WHERE annee!='' ORDER BY annee")]
    a_purger = [a for a in annees if a < seuil]
    a_garder = [a for a in annees if a >= seuil]

    print(f"Seuil de conservation : à partir de {seuil}")
    print(f"  Années conservées : {a_garder or '(aucune)'}")
    print(f"  Années purgées    : {a_purger or '(aucune)'}")
    if not a_purger:
        print("\nRien à purger.")
        return

    # Classes des années à purger.
    ph = ",".join("?" * len(a_purger))
    classes_purge = [r["id"] for r in conn.execute(
        f"SELECT id FROM classes WHERE annee IN ({ph})", a_purger)]
    # Élèves rattachés à ces classes.
    if classes_purge:
        phc = ",".join("?" * len(classes_purge))
        eleves_concernes = {r["eleve_id"] for r in conn.execute(
            f"SELECT DISTINCT eleve_id FROM eleves_classes "
            f"WHERE classe_id IN ({phc})", classes_purge)}
    else:
        eleves_concernes = set()

    # Élèves qui restent dans une classe CONSERVÉE (à ne pas supprimer).
    classes_gardees = [r["id"] for r in conn.execute(
        f"SELECT id FROM classes WHERE annee IN "
        f"({','.join('?' * len(a_garder))})", a_garder)] if a_garder else []
    eleves_gardes = set()
    if classes_gardees:
        phg = ",".join("?" * len(classes_gardees))
        eleves_gardes = {r["eleve_id"] for r in conn.execute(
            f"SELECT DISTINCT eleve_id FROM eleves_classes "
            f"WHERE classe_id IN ({phg})", classes_gardees)}

    eleves_supprimables = eleves_concernes - eleves_gardes

    print(f"\n  Classes purgées        : {len(classes_purge)}")
    print(f"  Élèves concernés       : {len(eleves_concernes)}")
    print(f"  Élèves aussi présents  : {len(eleves_concernes & eleves_gardes)}"
          " (préservés)")
    print(f"  Élèves supprimés       : {len(eleves_supprimables)}")

    if not args.apply:
        print("\n(dry-run — utilise --apply pour exécuter)")
        return
    if not args.yes:
        rep = input(f"\nPurger définitivement les données de "
                    f"{len(a_purger)} année(s) ? [o/N] ").strip().lower()
        if rep not in ("o", "oui", "y", "yes"):
            print("Annulé.")
            return

    try:
        phc = ",".join("?" * len(classes_purge)) if classes_purge else "''"
        if classes_purge:
            # Résultats (suivi, niveaux) des classes purgées.
            conn.execute(f"DELETE FROM niveaux WHERE classe_id IN ({phc})",
                         classes_purge)
            conn.execute(f"DELETE FROM suivi WHERE classe_id IN ({phc})",
                         classes_purge)
            # Liens élève↔classe.
            conn.execute(
                f"DELETE FROM eleves_classes WHERE classe_id IN ({phc})",
                classes_purge)
        # Élèves devenus orphelins (plus dans aucune classe conservée).
        for eid in eleves_supprimables:
            conn.execute("DELETE FROM eleves WHERE id=?", (eid,))
        conn.commit()
        print(f"\n✅ Purge effectuée : {len(classes_purge)} classe(s), "
              f"{len(eleves_supprimables)} élève(s) supprimé(s).")
        print("Note : les classes/progressions elles-mêmes ne sont pas "
              "supprimées (données pédagogiques, non personnelles). Adapter si "
              "besoin.")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Erreur, rollback : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
