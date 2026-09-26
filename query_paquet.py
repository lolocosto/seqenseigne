import sqlite3
c = sqlite3.connect('data/seqenseigne.db')
sql = """
SELECT nom, type_latex, statut_rendu_atome, fichier_source
FROM paquet_definitions
WHERE nom LIKE '%boiteContenuFlashcard%'
   OR nom LIKE '%boiteFillContenuFlashcard%'
   OR nom LIKE '%boiteTitreFlashcard%'
   OR nom LIKE '%seqTitreSection%'
"""
for row in c.execute(sql).fetchall():
    print(row)
print("---")
print("Total paquet_definitions:", c.execute("SELECT COUNT(*) FROM paquet_definitions").fetchone()[0])