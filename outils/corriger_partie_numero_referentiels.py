#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""outils/corriger_partie_numero_referentiels.py — v0.22.1

Corrige `referentiel_objectifs.partie_numero` dans les référentiels FIGÉS
(verrouille / utilise) à partir du préfixe du code d'objectif, selon la
convention établie :

    code 0x (01, 02, …)  → partie 1
    code 1x (11, 12, …)  → partie 2
    code 2x (21, 22, …)  → partie 3
    …

Contexte : certains référentiels importés/figés ont tous leurs objectifs avec
`partie_numero = 1`, même ceux de la 2nde partie (dont le code commence par 1x).
Résultat : l'atelier Progression n'affiche qu'une partie par séquence et on ne
peut pas placer la partie 2. Ce script rétablit le bon `partie_numero`.

Il régénère aussi la table `referentiel_parties` (le découpage figé) à partir
des parties ainsi déduites, pour que la source de vérité soit cohérente.

Idempotent. Transactionnel. Dry-run par défaut.

Usage :
    python -m outils.corriger_partie_numero_referentiels                 # aperçu
    python -m outils.corriger_partie_numero_referentiels --apply         # applique
    python -m outils.corriger_partie_numero_referentiels --apply --yes
    python -m outils.corriger_partie_numero_referentiels --ref N11_v2025 # cibler
    python -m outils.corriger_partie_numero_referentiels --db chemin.db
"""

import argparse
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "seqenseigne.db"


def _partie_du_code(code: str) -> int:
    """Partie déduite du préfixe du code (0x→1, 1x→2, 2x→3…). Défaut 1."""
    code = (code or "").strip()
    if len(code) >= 2 and code[0].isdigit():
        return int(code[0]) + 1
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--ref", default=None,
                    help="ne corriger qu'un référentiel (ex. N11_v2025)")
    ap.add_argument("--db", default=str(DB))
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    # Référentiels figés concernés (verrouille / utilise). On ne touche pas aux
    # référentiels en_cours (leur structure vit dans le modèle actif).
    q = ("SELECT id, niveau, version, etat FROM referentiel_niveaux "
         "WHERE etat IN ('verrouille','utilise')")
    params: list = []
    if args.ref:
        q += " AND id = ?"
        params.append(args.ref)
    refs = conn.execute(q, params).fetchall()

    if not refs:
        print("Aucun référentiel figé à traiter.")
        return

    total_maj = 0
    total_parties = 0
    plan = []
    for r in refs:
        rid = r["id"]
        objs = conn.execute(
            "SELECT seq_code, code, partie_numero FROM referentiel_objectifs "
            "WHERE referentiel_id=? ORDER BY seq_code, code", (rid,)).fetchall()
        maj = []
        parties_par_seq: dict = {}
        for o in objs:
            attendu = _partie_du_code(o["code"])
            parties_par_seq.setdefault(o["seq_code"], set()).add(attendu)
            if o["partie_numero"] != attendu:
                maj.append((o["seq_code"], o["code"],
                            o["partie_numero"], attendu))
        nb_parties = sum(len(v) for v in parties_par_seq.values())
        plan.append((r, maj, parties_par_seq, nb_parties))
        total_maj += len(maj)
        total_parties += nb_parties
        seqs_multi = sorted(s for s, v in parties_par_seq.items() if len(v) > 1)
        print(f"— {rid} ({r['etat']}) : {len(maj)} objectif(s) à recaler ; "
              f"séquences multi-parties : {seqs_multi or 'aucune'}")

    print(f"\nTotal : {total_maj} objectif(s) à corriger, "
          f"{total_parties} entrée(s) de partie à régénérer.")

    if not args.apply:
        print("\n(dry-run — utilise --apply pour écrire)")
        return
    if not args.yes:
        rep = input("\nAppliquer la correction ? [o/N] ").strip().lower()
        if rep not in ("o", "oui", "y", "yes"):
            print("Annulé.")
            return

    try:
        for r, maj, parties_par_seq, _ in plan:
            rid = r["id"]
            # 1) Recaler partie_numero des objectifs.
            for seq_code, code, _ancien, attendu in maj:
                conn.execute(
                    "UPDATE referentiel_objectifs SET partie_numero=? "
                    "WHERE referentiel_id=? AND seq_code=? AND code=?",
                    (attendu, rid, seq_code, code))
            # 2) Régénérer referentiel_parties (découpage figé) depuis les
            #    parties déduites. On préserve nb_seances_R_AE existant si
            #    présent, sinon 0.
            anciens = {(p["seq_code"], p["numero"]): p["nb_seances_R_AE"]
                       for p in conn.execute(
                           "SELECT seq_code, numero, nb_seances_R_AE "
                           "FROM referentiel_parties WHERE referentiel_id=?",
                           (rid,)).fetchall()}
            conn.execute("DELETE FROM referentiel_parties WHERE referentiel_id=?",
                         (rid,))
            for seq_code, parties in parties_par_seq.items():
                for numero in sorted(parties):
                    nb = anciens.get((seq_code, numero), 0) or 0
                    conn.execute(
                        "INSERT INTO referentiel_parties "
                        "(referentiel_id, seq_code, numero, nb_seances_R_AE) "
                        "VALUES (?,?,?,?)", (rid, seq_code, numero, nb))
        conn.commit()
        print(f"\n✅ {total_maj} objectif(s) recalé(s), "
              f"referentiel_parties régénérée pour {len(plan)} référentiel(s).")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Erreur, rollback : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
