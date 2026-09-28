# seqenseigne v0.6.3e — fix FK sur double repeuplement

Corrige un bug `sqlite3.IntegrityError: FOREIGN KEY constraint failed`
dans `peuplement_02_repeupler.py` quand on relance la migration
JSON → SQLite sur une base qui contient déjà des livrets.

## Cause

Dans `ecrire_methodes`, l'ordre des opérations était :

```python
conn.execute("DELETE FROM methodes")              # 1
conn.execute("DELETE FROM items_texte ...")       # 2
conn.execute("DELETE FROM methode_notions")       # 3
conn.execute("UPDATE objectifs SET methode_id=NULL")  # 4
```

Le `DELETE FROM methodes` (étape 1) déclenchait la cascade
`objectifs.methode_id → methodes ON DELETE CASCADE`, qui tentait de
supprimer les objectifs. Ces objectifs étant référencés par
`livret_exercices.objectif_id` (FK sans cascade), la suppression
violait cette dernière FK → `IntegrityError`.

## Fix

Inverser l'ordre : casser les FK (UPDATE methode_id=NULL) AVANT le DELETE.

```python
conn.execute("UPDATE objectifs SET methode_id=NULL")  # 1
conn.execute("DELETE FROM methode_notions")           # 2
conn.execute("DELETE FROM items_texte ...")           # 3
conn.execute("DELETE FROM methodes")                  # 4
```

## Fichiers modifiés (2)

| Fichier | Changement |
|---|---|
| `appli/persistence/sqlite_store.py` | `ecrire_methodes` : ordre des ops |
| `appli/tests/test_peuplement_repeupler.py` | +1 test de régression |

## Déploiement chez Laurent

1. Remplacer les 2 fichiers par ceux du ZIP
2. Relancer `peuplement_02_repeupler.py` → ça passe cette fois
3. Enchaîner avec `peuplement_05_plans_de_travail.py`, `03`, `04` comme prévu
4. Vérifier : `pytest tests -q` → **477 verts**

## Alternative : patch manuel

Dans `appli/persistence/sqlite_store.py`, chercher `def ecrire_methodes`
(vers ligne 888) et remplacer :

```python
    def ecrire_methodes(self, liste: list) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM methodes")
            conn.execute("DELETE FROM items_texte WHERE entite_type='methode'")
            conn.execute("DELETE FROM methode_notions")
            conn.execute("UPDATE objectifs SET methode_id=NULL")
            for m in liste:
```

par :

```python
    def ecrire_methodes(self, liste: list) -> None:
        with self._conn() as conn:
            # v0.6.3e — UPDATE AVANT DELETE pour éviter la cascade
            # objectifs.methode_id → methodes qui violerait livret_exercices
            conn.execute("UPDATE objectifs SET methode_id=NULL")
            conn.execute("DELETE FROM methode_notions")
            conn.execute("DELETE FROM items_texte WHERE entite_type='methode'")
            conn.execute("DELETE FROM methodes")
            for m in liste:
```
