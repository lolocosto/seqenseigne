#!/usr/bin/env python3
"""outils/migrer_serie_ea_vers_ae.py — v0.18.3

Unifie la série « approche » des exercices vers le code 'AE' partout.

Contexte
--------
La série approche a coexisté en base sous DEUX codes `serie_code` :
'AE' (convention dominante, utilisée par les livrets, la compilation et le
nommage des fichiers `...AExx.tex`) et 'EA' (anomalie introduite par un
chemin de création v2 qui écrivait 'EA'). Cette dualité rendait des
exercices invisibles selon le chemin de code (un filtre attendait l'un, la
donnée portait l'autre). À partir de la v0.18.3, le code est unifié sur 'AE' ;
ce script aligne les DONNÉES en conséquence.

Ce que fait ce script
---------------------
1. `exercices`            : serie_code 'EA' → 'AE'.
2. `objectif_exos`        : serie 'EA' → 'AE' (par sécurité ; en pratique
                            cette table ne contient pas d'approche, mais on
                            couvre le cas).

Ce que ce script NE touche PAS
------------------------------
- `partie_exos_revision_approche.type` : la valeur 'EA' y est un RÔLE
  (approche), pas un serie_code. Elle reste 'EA' (convention inchangée).
- Le champ texte `exercices.serie` ('approche', 'avancé'…) : déjà cohérent.

Sécurités
---------
- Dry-run par défaut : compte ce qui serait modifié, ne touche à rien.
- Avec --apply : confirmation interactive 'OUI' (sauf --yes pour le batch).
- Vérification post-migration : 0 ligne 'EA' résiduelle dans les colonnes
  série migrées (le rôle dans partie_exos_revision_approche n'est pas vérifié
  puisqu'on ne le touche pas).

Usage
-----
    python -m outils.migrer_serie_ea_vers_ae [--db CHEMIN]            # dry-run
    python -m outils.migrer_serie_ea_vers_ae --apply                 # interactif
    python -m outils.migrer_serie_ea_vers_ae --apply --yes           # batch

Codes de sortie
---------------
    0 : succès (dry-run, ou apply confirmé et vérifié)
    1 : apply annulé par l'utilisateur (réponse != OUI)
    2 : base introuvable
    3 : erreur (paramètres, SQL, ou vérification post-migration échouée)
"""

from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

# Colonnes (table, colonne) où 'EA' est un serie_code à migrer vers 'AE'.
_CIBLES = [
    ("exercices", "serie_code"),
    ("objectif_exos", "serie"),
]


def _chemin_db_par_defaut() -> Path:
    racine_appli = Path(__file__).resolve().parent.parent
    return racine_appli / "data" / "seqenseigne.db"


def _compter(conn: sqlite3.Connection) -> dict:
    """Compte les lignes 'EA' par (table, colonne) sans rien modifier."""
    impact = {}
    for table, col in _CIBLES:
        try:
            n = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {col} = 'EA'"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            # Table/colonne absente (schéma différent) : on l'ignore.
            n = None
        impact[f"{table}.{col}"] = n
    return impact


def _migrer(conn: sqlite3.Connection) -> dict:
    """Exécute la migration 'EA' → 'AE' dans une transaction.

    Retourne le nombre de lignes modifiées par (table, colonne).
    """
    modifs = {}
    for table, col in _CIBLES:
        try:
            cur = conn.execute(
                f"UPDATE {table} SET {col} = 'AE' WHERE {col} = 'EA'"
            )
            modifs[f"{table}.{col}"] = cur.rowcount
        except sqlite3.OperationalError:
            modifs[f"{table}.{col}"] = None
    return modifs


def _verifier(conn: sqlite3.Connection) -> list[str]:
    """Retourne la liste des (table.col) où il reste des 'EA' (anomalies)."""
    restes = []
    for table, col in _CIBLES:
        try:
            n = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {col} = 'EA'"
            ).fetchone()[0]
            if n:
                restes.append(f"{table}.{col} ({n})")
        except sqlite3.OperationalError:
            pass
    return restes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Migre la série approche 'EA' → 'AE' (v0.18.3)."
    )
    parser.add_argument("--db", type=Path, default=None,
                        help="Chemin de la base (défaut : data/seqenseigne.db)")
    parser.add_argument("--apply", action="store_true",
                        help="Applique réellement (sinon dry-run)")
    parser.add_argument("--yes", action="store_true",
                        help="Saute la confirmation interactive (batch)")
    args = parser.parse_args(argv)

    db = args.db or _chemin_db_par_defaut()
    if not db.exists():
        print(f"[ERREUR] Base introuvable : {db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        impact = _compter(conn)
        total = sum(v for v in impact.values() if v)
        print(f"Base : {db}")
        print("Lignes avec serie 'EA' (à migrer vers 'AE') :")
        for cle, n in impact.items():
            etat = "(table/colonne absente)" if n is None else str(n)
            print(f"  - {cle:30} {etat}")
        print(f"  Total à migrer : {total}")

        if total == 0:
            print("Rien à migrer. Base déjà cohérente.")
            return 0

        if not args.apply:
            print("\n[DRY-RUN] Aucune modification effectuée. "
                  "Relancer avec --apply pour appliquer.")
            return 0

        if not args.yes:
            rep = input("\nConfirmer la migration ? Taper 'OUI' : ").strip()
            if rep != "OUI":
                print("Migration annulée.")
                return 1

        modifs = _migrer(conn)
        conn.commit()
        print("\nMigration appliquée :")
        for cle, n in modifs.items():
            etat = "(absente)" if n is None else f"{n} ligne(s)"
            print(f"  - {cle:30} {etat}")

        restes = _verifier(conn)
        if restes:
            print("\n[ERREUR] Des 'EA' subsistent après migration : "
                  + ", ".join(restes), file=sys.stderr)
            return 3
        print("\nVérification OK : plus aucune série 'EA' résiduelle.")
        return 0
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[ERREUR] SQL : {e}", file=sys.stderr)
        return 3
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
