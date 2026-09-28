#!/usr/bin/env python3
"""scripts/purger_fiches.py — v0.11.1.x

Vide les fiches de résumé en base de manière sélective, en cascade
sur les sections et leurs items, et sur les liaisons objectif_fiches.

Cas d'usage : rejeu d'un import de fiches après détection d'erreurs
(ex: mauvais fichiers source) sans toucher au reste de la base
(notions, méthodes, exercices, etc.).

Filtres optionnels :
    --niveau N10            : restreindre à un niveau
    --sequence S01          : restreindre à une séquence (combinable avec --niveau)
    (sans filtre)           : TOUTES les fiches sont concernées

Sécurités :
    - Dry-run par défaut : compte ce qui serait supprimé, ne touche à rien.
    - Avec --apply, demande une confirmation interactive (OUI/non) sauf
      si --yes est passé (mode batch / tests).
    - Active PRAGMA foreign_keys=ON pour que la cascade ON DELETE marche
      sur objectif_fiches (qui a FK vers fiches_resume) et sur
      atome_section_items (qui a FK vers atome_sections).
    - Note : atome_sections n'a PAS de FK vers fiches_resume — la
      suppression des sections est faite explicitement avant celle des
      fiches, dans la même transaction.

Usage :
    python -m scripts.purger_fiches [--db CHEMIN] [--niveau N] [--sequence S] [--apply] [--yes]

    # Dry-run sur N10 :
    python -m scripts.purger_fiches --niveau N10

    # Apply réel sur N10/S01 (avec confirmation interactive) :
    python -m scripts.purger_fiches --niveau N10 --sequence S01 --apply

    # Apply sur tout, sans confirmation (batch) :
    python -m scripts.purger_fiches --apply --yes

Codes de sortie :
    0  : opération réussie (dry-run ou apply confirmé)
    1  : apply annulé par l'utilisateur (réponse != OUI)
    2  : base introuvable
    3  : erreur de paramètres / SQL
"""

from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path


def _chemin_db_par_defaut() -> Path:
    """Retourne le chemin par défaut de la BDD (data/seqenseigne.db
    relatif à la racine de l'appli, comme lister_atomes_orphelins.py).
    """
    racine_appli = Path(__file__).resolve().parent.parent
    return racine_appli / "data" / "seqenseigne.db"


def _construire_filtres(niveau: str | None,
                        sequence: str | None) -> tuple[str, list]:
    """Construit la clause WHERE pour les filtres optionnels.

    Retourne (clause_sql, params) où clause_sql commence par 'WHERE …' si
    au moins un filtre est posé, ou est vide sinon.

    Pourquoi pas un f-string : on passe les valeurs en paramètres SQL
    pour éviter toute injection (même si le script est local).
    """
    conditions = []
    params: list = []
    if niveau:
        conditions.append("niveau = ?")
        params.append(niveau)
    if sequence:
        conditions.append("sequence = ?")
        params.append(sequence)
    if not conditions:
        return "", params
    return "WHERE " + " AND ".join(conditions), params


def _compter_impact(conn: sqlite3.Connection,
                    niveau: str | None,
                    sequence: str | None) -> dict:
    """Compte ce qui serait supprimé, sans rien modifier.

    Retourne un dict avec les comptes : fiches, sections, items, liaisons.
    """
    where, params = _construire_filtres(niveau, sequence)

    # 1. Combien de fiches matchent ?
    n_fiches = conn.execute(
        f"SELECT COUNT(*) FROM fiches_resume {where}", params,
    ).fetchone()[0]

    if n_fiches == 0:
        return {"fiches": 0, "sections": 0, "items": 0, "liaisons": 0}

    # 2. Sections rattachées à ces fiches (entite_type='fiche_resume',
    #    entite_id IN (...))
    n_sections = conn.execute(
        f"""
        SELECT COUNT(*) FROM atome_sections
        WHERE entite_type = 'fiche_resume'
          AND entite_id IN (SELECT id FROM fiches_resume {where})
        """,
        params,
    ).fetchone()[0]

    # 3. Items rattachés à ces sections (cascade naturelle, on compte
    #    pour information seulement)
    n_items = conn.execute(
        f"""
        SELECT COUNT(*) FROM atome_section_items
        WHERE section_id IN (
            SELECT id FROM atome_sections
            WHERE entite_type = 'fiche_resume'
              AND entite_id IN (SELECT id FROM fiches_resume {where})
        )
        """,
        params,
    ).fetchone()[0]

    # 4. Liaisons objectif_fiches (cascade naturelle via FK ON DELETE)
    n_liaisons = conn.execute(
        f"""
        SELECT COUNT(*) FROM objectif_fiches
        WHERE fiche_id IN (SELECT id FROM fiches_resume {where})
        """,
        params,
    ).fetchone()[0]

    return {
        "fiches":   n_fiches,
        "sections": n_sections,
        "items":    n_items,
        "liaisons": n_liaisons,
    }


def _executer_purge(conn: sqlite3.Connection,
                    niveau: str | None,
                    sequence: str | None) -> dict:
    """Exécute la purge dans une transaction.

    Ordre :
      1. atome_sections (FK ON DELETE CASCADE → atome_section_items
         partent automatiquement).
      2. fiches_resume (FK ON DELETE CASCADE depuis objectif_fiches.fiche_id
         → liaisons partent automatiquement).

    Précondition : PRAGMA foreign_keys=ON activé sur la connexion.

    Retourne le dict des comptes effectivement supprimés (utile pour
    vérification post-coup et logs).
    """
    where, params = _construire_filtres(niveau, sequence)

    # Mémoriser les comptes avant suppression pour les retourner
    avant = _compter_impact(conn, niveau, sequence)

    # 1. Sections (cascade vers items via FK)
    conn.execute(
        f"""
        DELETE FROM atome_sections
        WHERE entite_type = 'fiche_resume'
          AND entite_id IN (SELECT id FROM fiches_resume {where})
        """,
        params,
    )
    # 2. Fiches (cascade vers objectif_fiches via FK)
    conn.execute(
        f"DELETE FROM fiches_resume {where}",
        params,
    )

    return avant


def _formater_resume(impact: dict, filtres_str: str, mode: str) -> str:
    """Formate le résumé human-readable.

    `mode` : 'DRY-RUN' ou 'APPLIQUÉ'.
    """
    lignes = [
        f"=== Mode : {mode} ===",
        f"Filtres : {filtres_str}",
        "",
        "Impact :",
        f"  Fiches              : {impact['fiches']:6d}",
        f"  Sections            : {impact['sections']:6d}",
        f"  Items de section    : {impact['items']:6d}  (cascade)",
        f"  Liaisons obj_fiches : {impact['liaisons']:6d}  (cascade)",
    ]
    return "\n".join(lignes)


def _decrire_filtres(niveau: str | None, sequence: str | None) -> str:
    """Représentation textuelle des filtres pour les logs."""
    parties = []
    if niveau:
        parties.append(f"niveau={niveau}")
    if sequence:
        parties.append(f"sequence={sequence}")
    return ", ".join(parties) if parties else "(aucun — TOUTES les fiches)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Purge sélective des fiches de résumé en base.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            "  Dry-run sur N10 :\n"
            "    python -m scripts.purger_fiches --niveau N10\n"
            "  Apply N10/S01 avec confirmation :\n"
            "    python -m scripts.purger_fiches --niveau N10 --sequence S01 --apply\n"
            "  Apply tout, batch :\n"
            "    python -m scripts.purger_fiches --apply --yes\n"
        ),
    )
    parser.add_argument(
        "--db", type=Path, default=_chemin_db_par_defaut(),
        help="Chemin de la base SQLite (défaut: data/seqenseigne.db)",
    )
    parser.add_argument(
        "--niveau", type=str, default=None,
        help="Filtrer par niveau (ex: N10, N11, N12). Optionnel.",
    )
    parser.add_argument(
        "--sequence", type=str, default=None,
        help="Filtrer par séquence (ex: S01, S07). Optionnel, "
             "combinable avec --niveau.",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Exécute réellement la purge. Sans ce flag, mode dry-run.",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Saute la confirmation interactive (mode batch). "
             "N'a d'effet qu'avec --apply.",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERREUR: base introuvable : {args.db}", file=sys.stderr)
        return 2

    filtres_str = _decrire_filtres(args.niveau, args.sequence)

    # Ouverture de la connexion. PRAGMA foreign_keys=ON est posé avant
    # toute requête pour que les cascades ON DELETE fonctionnent (cf.
    # objectif_fiches.fiche_id et atome_section_items.section_id).
    with sqlite3.connect(args.db) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        # 1. Compter l'impact (toujours, dry-run comme apply)
        impact = _compter_impact(conn, args.niveau, args.sequence)

        if not args.apply:
            # Dry-run : on affiche et on s'arrête.
            print(_formater_resume(impact, filtres_str, "DRY-RUN"))
            print("")
            print("Aucune modification effectuée.")
            print("Pour appliquer réellement : ajouter --apply.")
            return 0

        # 2. Apply : afficher l'impact prévu, demander confirmation
        print(_formater_resume(impact, filtres_str, "APPLY (à confirmer)"))
        print("")

        if impact["fiches"] == 0:
            print("Rien à supprimer — aucune fiche ne matche les filtres.")
            return 0

        if not args.yes:
            print("Pour confirmer la suppression DÉFINITIVE, taper exactement OUI :")
            try:
                reponse = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAnnulé (entrée fermée).", file=sys.stderr)
                return 1
            if reponse != "OUI":
                print(f"Annulé (réponse : {reponse!r} — attendu : 'OUI').",
                      file=sys.stderr)
                return 1

        # 3. Exécution dans une transaction (le `with sqlite3.connect`
        #    commit automatiquement à la sortie sans exception, sinon
        #    rollback).
        try:
            avant = _executer_purge(conn, args.niveau, args.sequence)
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERREUR SQL pendant la purge : {e}", file=sys.stderr)
            return 3

        # 4. Vérification post-coup : les compteurs doivent être à zéro
        apres = _compter_impact(conn, args.niveau, args.sequence)
        print("")
        print(_formater_resume(avant, filtres_str, "APPLIQUÉ"))
        if any(apres[k] > 0 for k in ("fiches", "sections", "liaisons")):
            print("")
            print("AVERTISSEMENT : il reste des résidus après suppression :",
                  file=sys.stderr)
            for k, v in apres.items():
                if v > 0:
                    print(f"  {k}: {v}", file=sys.stderr)
            return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
