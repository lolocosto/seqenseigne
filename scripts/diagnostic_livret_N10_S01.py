#!/usr/bin/env python3
"""scripts/diagnostic_livret_N10_S01.py — Diagnostic des liaisons cours.

Vérifie ce qui est attaché à N10/S01 en BDD pour comprendre pourquoi
le bloc Cours du livret est absent.

Usage :
    python scripts/diagnostic_livret_N10_S01.py
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
db_path = ROOT / "data" / "seqenseigne.db"

if not db_path.exists():
    print(f"Erreur : base introuvable à {db_path}", file=sys.stderr)
    sys.exit(2)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

print("─" * 60)
print("Diagnostic N10/S01 — pourquoi le bloc Cours est absent ?")
print("─" * 60)

# 1. La séquence-niveau existe-t-elle ?
sn = conn.execute(
    "SELECT id, niveau, sequence_code FROM sequences_par_niveau "
    "WHERE niveau='N10' AND sequence_code='S01'"
).fetchone()
print(f"\n[1] sequences_par_niveau N10/S01 : {dict(sn) if sn else 'INTROUVABLE'}")

# 2. Combien de parties ?
n_parties = conn.execute(
    "SELECT COUNT(*) FROM sequence_parties sp "
    "JOIN sequences_par_niveau sn ON sn.id = sp.sequence_par_niveau_id "
    "WHERE sn.niveau='N10' AND sn.sequence_code='S01'"
).fetchone()[0]
print(f"\n[2] Nombre de parties : {n_parties}")

# 3. Combien d'objectifs ?
n_obj = conn.execute(
    "SELECT COUNT(*) FROM objectifs obv "
    "JOIN sequence_parties sp ON sp.id = obv.partie_id "
    "JOIN sequences_par_niveau sn ON sn.id = sp.sequence_par_niveau_id "
    "WHERE sn.niveau='N10' AND sn.sequence_code='S01'"
).fetchone()[0]
print(f"\n[3] Nombre d'objectifs : {n_obj}")

# 4. Combien d'objectifs avec une méthode ?
n_obj_meth = conn.execute(
    "SELECT COUNT(*) FROM objectifs obv "
    "JOIN sequence_parties sp ON sp.id = obv.partie_id "
    "JOIN sequences_par_niveau sn ON sn.id = sp.sequence_par_niveau_id "
    "WHERE sn.niveau='N10' AND sn.sequence_code='S01' "
    "AND obv.methode_id IS NOT NULL"
).fetchone()[0]
print(f"\n[4] Objectifs avec methode_id renseigné : {n_obj_meth}")

# 5. Combien de liaisons objectif_notions ?
n_on = conn.execute(
    "SELECT COUNT(*) FROM objectif_notions onv "
    "JOIN objectifs obv ON obv.id = onv.objectif_id "
    "JOIN sequence_parties sp ON sp.id = obv.partie_id "
    "JOIN sequences_par_niveau sn ON sn.id = sp.sequence_par_niveau_id "
    "WHERE sn.niveau='N10' AND sn.sequence_code='S01'"
).fetchone()[0]
print(f"\n[5] Liaisons objectif_notions : {n_on}")

# 6. Notions distinctes liées
notions = conn.execute(
    "SELECT DISTINCT n.id, n.titre, n.num_connaissance "
    "FROM notions n "
    "JOIN objectif_notions onv ON onv.notion_id = n.id "
    "JOIN objectifs obv ON obv.id = onv.objectif_id "
    "JOIN sequence_parties sp ON sp.id = obv.partie_id "
    "JOIN sequences_par_niveau sn ON sn.id = sp.sequence_par_niveau_id "
    "WHERE sn.niveau='N10' AND sn.sequence_code='S01' "
    "ORDER BY n.num_connaissance"
).fetchall()
print(f"\n[6] Notions distinctes liées via objectif_notions ({len(notions)}) :")
for r in notions:
    print(f"     {r['num_connaissance'] or '?'}: {r['titre']}")

# 7. Méthodes distinctes liées
methodes = conn.execute(
    "SELECT DISTINCT m.id, m.titre, m.num_methode, m.num_objectif "
    "FROM methodes m "
    "JOIN objectifs obv ON obv.methode_id = m.id "
    "JOIN sequence_parties sp ON sp.id = obv.partie_id "
    "JOIN sequences_par_niveau sn ON sn.id = sp.sequence_par_niveau_id "
    "WHERE sn.niveau='N10' AND sn.sequence_code='S01' "
    "ORDER BY m.num_methode"
).fetchall()
print(f"\n[7] Méthodes distinctes liées via objectifs.methode_id ({len(methodes)}) :")
for r in methodes:
    print(f"     M{r['num_methode']}: {r['titre']} (num_obj={r['num_objectif']})")

# 8. Notions de N10/S01 (filtrage par dénormalisation)
notions_brut = conn.execute(
    "SELECT id, titre, num_connaissance FROM notions "
    "WHERE niveau='N10' AND sequence='S01' ORDER BY num_connaissance"
).fetchall()
print(f"\n[8] Notions avec niveau='N10' AND sequence='S01' ({len(notions_brut)}) :")
for r in notions_brut:
    print(f"     {r['num_connaissance'] or '?'}: {r['titre']}")

# 9. Méthodes de N10/S01 (filtrage par dénormalisation)
methodes_brut = conn.execute(
    "SELECT id, titre, num_methode FROM methodes "
    "WHERE niveau='N10' AND sequence='S01' ORDER BY num_methode"
).fetchall()
print(f"\n[9] Méthodes avec niveau='N10' AND sequence='S01' ({len(methodes_brut)}) :")
for r in methodes_brut:
    print(f"     M{r['num_methode']}: {r['titre']}")

# 10. Fiches
n_fi = conn.execute(
    "SELECT COUNT(*) FROM fiches_resume "
    "WHERE niveau='N10' AND sequence='S01'"
).fetchone()[0]
print(f"\n[10] Fiches de résumé N10/S01 : {n_fi}")

print("\n─── Conclusion ───")
if len(notions_brut) > 0 and len(notions) == 0:
    print("Il y a des notions N10/S01 EN BDD mais aucune n'est LIÉE à un objectif")
    print("(table objectif_notions vide pour N10/S01). C'est pourquoi le livret")
    print("ne montre pas de bloc Cours côté notions.")
if len(methodes_brut) > 0 and len(methodes) == 0:
    print("Idem pour les méthodes : présentes en BDD mais pas liées via")
    print("objectifs.methode_id.")
if len(notions_brut) == 0 and len(methodes_brut) == 0:
    print("Aucune notion ni méthode N10/S01 en BDD.")
elif len(notions) > 0 or len(methodes) > 0:
    print("Liaisons OK — le service livret_sequence devrait générer le bloc Cours.")
    print("Si ce n'est pas le cas, c'est un bug à investiguer.")

conn.close()
