#!/usr/bin/env python3
"""outils/coherence_etats_referentiels.py — v0.19.1.12

Met en cohérence l'état des référentiels avec les progressions qui s'appuient
dessus.

Règle (identique à la transition automatique de l'app, v0.19.0) : un
référentiel `verrouille` lié à au moins une progression doit passer à
`utilise` (il devient alors non déverrouillable). Idempotent : un référentiel
déjà `utilise` reste `utilise` ; un référentiel `en_cours`/`valide` n'est pas
promu (cas anormal, on ne force pas).

Pourquoi ce script : les imports historiques ad hoc écrivent la structure et le
suivi directement en SQL, sans passer par la sauvegarde de progression qui, en
usage normal, déclenche la promotion `verrouille → utilise`. Résultat : des
référentiels restent `verrouille` alors qu'une progression les utilise. Ce
script (et la fonction `promouvoir_referentiels_utilises`, appelée par les
imports) corrige cela.

La fonction `promouvoir_referentiels_utilises(conn)` est réutilisable : les
scripts d'import l'appellent en fin de transaction pour rester cohérents.

Usage :
    python -m outils.coherence_etats_referentiels            # dry-run
    python -m outils.coherence_etats_referentiels --apply

Codes de sortie : 0 = rien à faire / ok ; 1 = des référentiels ont été (ou
seraient) promus ; 2 = base introuvable ; 3 = erreur.
"""

from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path


def _chemin_db_par_defaut() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "seqenseigne.db"


def referentiels_a_promouvoir(conn) -> list[str]:
    """Liste des référentiels `verrouille` liés à ≥ 1 progression."""
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT rn.id FROM referentiel_niveaux rn "
        "JOIN progressions p ON p.referentiel_id = rn.id "
        "WHERE rn.etat = 'verrouille' ORDER BY rn.id").fetchall()]


def promouvoir_referentiels_utilises(conn) -> list[str]:
    """Promeut `verrouille → utilise` tout référentiel lié à une progression.

    Retourne la liste des ids promus. À appeler dans une transaction ouverte
    par l'appelant (ne committe pas). Idempotent.
    """
    a_promouvoir = referentiels_a_promouvoir(conn)
    for ref_id in a_promouvoir:
        conn.execute(
            "UPDATE referentiel_niveaux SET etat='utilise' "
            "WHERE id=? AND etat='verrouille'", (ref_id,))
    return a_promouvoir


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=_chemin_db_par_defaut())
    ap.add_argument("--apply", action="store_true",
                    help="applique réellement (sinon dry-run)")
    args = ap.parse_args(argv)

    if not args.db.exists():
        print(f"[cohérence états] base introuvable : {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        a_promouvoir = referentiels_a_promouvoir(conn)
        if not a_promouvoir:
            print("[cohérence états] ✓ rien à faire : aucun référentiel "
                  "`verrouille` n'est lié à une progression.")
            return 0

        print("[cohérence états] référentiels `verrouille` liés à une "
              "progression (à promouvoir `utilise`) :")
        for ref_id in a_promouvoir:
            np = conn.execute(
                "SELECT COUNT(*) FROM progressions WHERE referentiel_id=?",
                (ref_id,)).fetchone()[0]
            print(f"  • {ref_id}  ({np} progression(s))")

        if not args.apply:
            print("\n[cohérence états] DRY-RUN : aucune modification "
                  "(rejouer avec --apply pour promouvoir).")
            return 1

        conn.execute("BEGIN")
        promus = promouvoir_referentiels_utilises(conn)
        conn.commit()
        print(f"\n[cohérence états] ✓ {len(promus)} référentiel(s) promu(s) "
              "`utilise`. 🎉")
        return 1
    except Exception as e:
        conn.rollback()
        print(f"[cohérence états] erreur : {e}", file=sys.stderr)
        return 3
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
