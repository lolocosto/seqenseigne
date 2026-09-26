"""Utilitaire : vide le cache API des vacances.
À exécuter après chaque mise à jour de services/calendrier_scolaire.py.

Usage :
    python clean_cache.py
"""
import sqlite3
c = sqlite3.connect('data/seqenseigne.db')
n = c.execute("DELETE FROM cache_api WHERE cle LIKE 'vacances:%'").rowcount
c.commit()
c.close()
print(f"{n} entree(s) supprimee(s)")
