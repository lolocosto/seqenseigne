#!/usr/bin/env python3
"""scripts/creation_livret_N10_S01.py — Test rapide du service livret_sequence.

Génère le source .tex du livret de séquence N10/S01 et l'écrit dans
livret_test.tex à la racine du projet. Permet de valider le service
livret_sequence avant que les routes API et l'UI soient en place.

Usage :
    python -m scripts.creation_livret_N10_S01

Ou directement :
    python scripts/creation_livret_N10_S01.py

(Le bloc sys.path en tête permet le second mode.)
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

# Permettre l'import des modules de l'appli quand le script est lancé
# directement (et pas avec -m). On insère le dossier parent (= racine appli)
# au début du sys.path.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.livret_sequence import generer_livret_sequence


def main():
    db_path = ROOT / "data" / "seqenseigne.db"
    if not db_path.exists():
        print(f"Erreur : base introuvable à {db_path}", file=sys.stderr)
        sys.exit(2)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Génération avec options par défaut (livret « tout en un »).
        # Pour tester un autre profil, passer un dict en 4e argument.
        # Exemple sans la série A :
        #   tex = generer_livret_sequence(conn, "N10", "S01",
        #                                 options={"exercices": {"serie_A": False}})
        tex = generer_livret_sequence(conn, "N10", "S01")
    finally:
        conn.close()

    sortie = ROOT / "livret_test_N10_S01.tex"
    sortie.write_text(tex, encoding="utf-8")
    print(f"Généré : {sortie} ({len(tex):,} caractères)")
    print("Pour compiler :")
    print(f"  cd {ROOT}")
    print(f"  pdflatex {sortie.name}")


if __name__ == "__main__":
    main()
