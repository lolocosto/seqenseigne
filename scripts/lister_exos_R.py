import sqlite3
c = sqlite3.connect('data/seqenseigne.db')
sql = """
SELECT COUNT(*) FROM objectif_exos WHERE serie='R'
"""
for row in c.execute(sql).fetchall():
    print(row)
print("---")