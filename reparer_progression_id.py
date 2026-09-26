"""
Répare les classes dont progression_id est NULL en base, en les reliant
à la progression existante (si elle existe) pour la même clé métier
(niveau, annee, etablissement).

Usage (depuis D:\\Enseignement\\seqenseigne\\appli) :
    python reparer_progression_id.py
"""

import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "data" / "seqenseigne.db"

def main():
    if not DB.exists():
        print(f"Base introuvable : {DB}")
        return
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # Trouver les classes avec progression_id NULL
    orphelines = conn.execute("""
        SELECT id, nom, niveau, annee, etablissement
        FROM classes WHERE progression_id IS NULL
    """).fetchall()

    print(f"{len(orphelines)} classe(s) sans progression_id :")
    reparees = 0
    for c in orphelines:
        # Chercher une progression correspondante
        prog = conn.execute("""
            SELECT id, referentiel_id FROM progressions
            WHERE niveau=? AND annee=? AND etablissement=?
        """, (c["niveau"], c["annee"], c["etablissement"])).fetchone()
        if prog:
            conn.execute(
                "UPDATE classes SET progression_id=? WHERE id=?",
                (prog["id"], c["id"])
            )
            print(f"  ✓ {c['nom']} {c['annee']} → progression {prog['id']} (ref={prog['referentiel_id']})")
            reparees += 1
        else:
            print(f"  ✗ {c['nom']} {c['annee']} : aucune progression correspondante trouvée")

    conn.commit()
    conn.close()
    print(f"\n{reparees}/{len(orphelines)} classe(s) réparée(s).")

if __name__ == "__main__":
    main()
