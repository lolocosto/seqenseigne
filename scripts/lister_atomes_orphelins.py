#!/usr/bin/env python3
"""scripts/lister_atomes_orphelins.py — v0.10.7

Affiche les notions et méthodes potentiellement "orphelines" :
  - SANS_SCOPE : pas de (niveau, sequence) renseignés (champ vide).
                 Cause typique : atome créé dans une version legacy,
                 ou import sans métadonnées.
  - SANS_LIEN  : aucune liaison vers un objectif_v2.

Un atome peut cumuler les deux statuts (SANS_SCOPE + SANS_LIEN).

Usage :
    python3 -m scripts.lister_atomes_orphelins [--db CHEMIN]

Sans argument, utilise data/seqenseigne.db (chemin par défaut de
SqliteStore). Sortie tabulaire texte sur stdout.

Cible : intégration UI dans v0.14 (refonte admin). Pour l'instant
script CLI à exécuter à la main.
"""

from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path


def _chemin_db_par_defaut() -> Path:
    """Retourne le chemin par défaut de la BDD (data/seqenseigne.db
    relatif à la racine de l'appli).
    """
    # Le script est dans appli/scripts/ → racine = parent.parent
    racine_appli = Path(__file__).resolve().parent.parent
    return racine_appli / "data" / "seqenseigne.db"


def _lister(conn: sqlite3.Connection, table: str) -> list[dict]:
    """Retourne tous les atomes (`notions` ou `methodes`) avec leurs
    statuts SANS_SCOPE / SANS_LIEN calculés.
    """
    if table not in ("notions", "methodes"):
        raise ValueError(f"Table inconnue : {table!r}")

    # Comptage des liaisons par atome (selon le type)
    if table == "notions":
        # objectif_notions : table de liaison N-N
        liens = {r["nid"]: r["n"] for r in conn.execute("""
            SELECT notion_id AS nid, COUNT(*) AS n
            FROM objectif_notions
            GROUP BY notion_id
        """)}
    else:  # methodes
        # objectifs.methode_id : liaison 1-1 (au plus 1 obj par
        # méthode, contrainte v0.10.7)
        liens = {r["mid"]: r["n"] for r in conn.execute("""
            SELECT methode_id AS mid, COUNT(*) AS n
            FROM objectifs
            WHERE methode_id IS NOT NULL
            GROUP BY methode_id
        """)}

    rows = conn.execute(f"""
        SELECT id, titre, niveau, sequence, fichier
        FROM {table}
        ORDER BY niveau, sequence, titre
    """).fetchall()

    out = []
    for r in rows:
        atome_id = r["id"]
        statuts = []
        if not (r["niveau"] or "").strip() or not (r["sequence"] or "").strip():
            statuts.append("SANS_SCOPE")
        if liens.get(atome_id, 0) == 0:
            statuts.append("SANS_LIEN")
        if statuts:  # ne garder que les "potentiellement orphelins"
            out.append({
                "id":       atome_id,
                "titre":    r["titre"] or "",
                "niveau":   r["niveau"] or "",
                "sequence": r["sequence"] or "",
                "fichier":  r["fichier"] or "",
                "statuts":  ",".join(statuts),
            })
    return out


def _formater_tableau(titre: str, lignes: list[dict]) -> str:
    """Format texte aligné pour la sortie console."""
    if not lignes:
        return f"\n=== {titre} ===\n  (aucun atome orphelin)\n"
    # Largeur dynamique des colonnes
    cols = ["statuts", "niveau", "sequence", "id", "titre", "fichier"]
    largeurs = {c: max(len(c), max(len(str(l[c])) for l in lignes)) for c in cols}
    sep = "  "
    entete = sep.join(c.upper().ljust(largeurs[c]) for c in cols)
    sortie = [f"\n=== {titre} ({len(lignes)}) ===", entete, "-" * len(entete)]
    for l in lignes:
        sortie.append(sep.join(str(l[c]).ljust(largeurs[c]) for c in cols))
    return "\n".join(sortie) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, default=_chemin_db_par_defaut(),
        help="Chemin de la base SQLite (défaut: data/seqenseigne.db)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERREUR: base introuvable : {args.db}", file=sys.stderr)
        sys.exit(2)

    with sqlite3.connect(args.db) as conn:
        conn.row_factory = sqlite3.Row
        notions  = _lister(conn, "notions")
        methodes = _lister(conn, "methodes")

    print(_formater_tableau("Notions orphelines",  notions))
    print(_formater_tableau("Méthodes orphelines", methodes))

    # Résumé final
    n_sans_scope_n = sum(1 for n in notions  if "SANS_SCOPE" in n["statuts"])
    n_sans_lien_n  = sum(1 for n in notions  if "SANS_LIEN"  in n["statuts"])
    n_sans_scope_m = sum(1 for m in methodes if "SANS_SCOPE" in m["statuts"])
    n_sans_lien_m  = sum(1 for m in methodes if "SANS_LIEN"  in m["statuts"])
    print("\n=== Résumé ===")
    print(f"  Notions  : {len(notions):4d} signalées "
          f"({n_sans_scope_n} sans scope, {n_sans_lien_n} sans lien)")
    print(f"  Méthodes : {len(methodes):4d} signalées "
          f"({n_sans_scope_m} sans scope, {n_sans_lien_m} sans lien)")


if __name__ == "__main__":
    main()
