#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""outils/import_cartes_n11_lot3.py — v0.19.2.0

Insère (idempotent) les cartes d'automatisme 4e du LOT 3 (S07 à S14) dans
la table cartes_automatisme, à partir de outils/cartes_n11_lot3_data.py.

Chaque carte est liée à sa notion/méthode source (lien_type + lien_num résolu
en id via niveau/sequence/numéro). Les cartes sont créées en état 'en_cours'
pour relecture/validation par l'enseignant.

Idempotence : une carte est identifiée par (niveau, sequence, num). Ré-exécuter
le script met à jour les cartes existantes sans en créer de doublon.

Usage :
    python -m outils.import_cartes_n11_lot3              # dry-run (aperçu)
    python -m outils.import_cartes_n11_lot3 --apply      # applique (confirme)
    python -m outils.import_cartes_n11_lot3 --apply --yes  # sans confirmation
"""

import argparse
import sqlite3
import sys
import time
import uuid
from pathlib import Path

# Import des données (exécuté comme module : python -m outils....)
try:
    from outils.cartes_n11_lot3_data import CARTES
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from outils.cartes_n11_lot3_data import CARTES

NIVEAU = "N11"
DB = Path(__file__).resolve().parent.parent / "data" / "seqenseigne.db"


def _resoudre_lien(conn, lien_type, sequence, lien_num):
    """Retourne l'id de la notion/méthode source, ou None si introuvable."""
    if not lien_type or lien_num is None:
        return None
    if lien_type == "notion":
        row = conn.execute(
            "SELECT id FROM notions WHERE niveau=? AND sequence=? "
            "AND num_connaissance=?",
            (NIVEAU, sequence, lien_num)).fetchone()
    elif lien_type == "methode":
        row = conn.execute(
            "SELECT id FROM methodes WHERE niveau=? AND sequence=? "
            "AND num_methode=?",
            (NIVEAU, sequence, lien_num)).fetchone()
    else:
        return None
    return row[0] if row else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="applique les insertions (sinon dry-run)")
    ap.add_argument("--yes", action="store_true",
                    help="ne pas demander de confirmation")
    ap.add_argument("--db", default=str(DB), help="chemin de la base")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    total = len(CARTES)
    a_creer, a_maj, liens_manquants = [], [], []
    for carte in CARTES:
        seq = carte["sequence"]
        num = carte["num"]
        lien_id = _resoudre_lien(conn, carte.get("lien_type"), seq,
                                 carte.get("lien_num"))
        if carte.get("lien_type") and lien_id is None:
            liens_manquants.append(
                f"{seq} C{num} → {carte['lien_type']} {carte.get('lien_num')}")
        existe = conn.execute(
            "SELECT id FROM cartes_automatisme WHERE niveau=? AND sequence=? "
            "AND num=?", (NIVEAU, seq, num)).fetchone()
        (a_maj if existe else a_creer).append((carte, lien_id, existe))

    print(f"LOT 3 cartes 4e — {total} cartes ({NIVEAU})")
    print(f"  à créer      : {len(a_creer)}")
    print(f"  à mettre à jour : {len(a_maj)}")
    if liens_manquants:
        print(f"  ⚠ liens source introuvables ({len(liens_manquants)}) :")
        for lm in liens_manquants:
            print(f"      {lm}")
    # Aperçu
    print("\n  Aperçu (séquence, num, type, titre) :")
    for carte in CARTES:
        print(f"    {carte['sequence']} C{carte['num']:<2} "
              f"[{carte['type_pedago']}/{carte['type_tech']}] "
              f"{carte['titre']}")

    if not args.apply:
        print("\n(dry-run — utilise --apply pour insérer)")
        return

    if not args.yes:
        rep = input("\nAppliquer ? [o/N] ").strip().lower()
        if rep not in ("o", "oui", "y", "yes"):
            print("Annulé.")
            return

    now = time.time()
    try:
        for carte, lien_id, existe in a_creer + a_maj:
            seq, num = carte["sequence"], carte["num"]
            if existe:
                conn.execute(
                    "UPDATE cartes_automatisme SET type_pedago=?, type_tech=?, "
                    "titre=?, lien_type=?, lien_id=?, recto=?, verso=?, "
                    "variables=?, mtime=? WHERE niveau=? AND sequence=? "
                    "AND num=?",
                    (carte["type_pedago"], carte["type_tech"], carte["titre"],
                     carte.get("lien_type"), lien_id, carte["recto"],
                     carte["verso"], carte.get("variables", ""), now,
                     NIVEAU, seq, num))
            else:
                conn.execute(
                    "INSERT INTO cartes_automatisme "
                    "(id, niveau, sequence, num, type_pedago, type_tech, "
                    " titre, lien_type, lien_id, recto, verso, variables, "
                    " etat_code, ordre, mtime) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("ca_" + uuid.uuid4().hex[:12], NIVEAU, seq, num,
                     carte["type_pedago"], carte["type_tech"], carte["titre"],
                     carte.get("lien_type"), lien_id, carte["recto"],
                     carte["verso"], carte.get("variables", ""),
                     "en_cours", num, now))
        conn.commit()
        print(f"\n✅ {len(a_creer)} créées, {len(a_maj)} mises à jour.")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Erreur, rollback : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
