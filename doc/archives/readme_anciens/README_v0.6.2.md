# seqenseigne v0.6.2 — UUID opaques partout

Livraison qui assainit les identifiants de toutes les entités : plus aucun
id ne porte de sémantique métier. Cette refonte corrige un bug de fond
détecté en v0.6.1 (plusieurs classes de même nom à travers les années
s'écrasaient mutuellement en base) et pose des bases saines pour la suite.

## Le bug qui a déclenché la refonte

Après ré-import complet en v0.6.1, l'écran Admin affichait
**Classes=1 / Élèves=44** au lieu des 20 classes attendues. Cause : le
générateur d'id `generer_id_classe(nom, existants)` retournait le même
identifiant (`4E3`) pour toutes les classes nommées `4e3`, et la logique
d'anti-collision (`_hist` ajouté en cas de conflit) écrasait les classes
précédentes dès qu'on dépassait 2 occurrences d'un même nom.

Correctif de surface possible : détecter les collisions et suffixer avec
l'année+établissement. Mais ça perpétuait le principe douteux "l'id
encode la sémantique métier". On a préféré faire le refacto propre.

## Le principe

**Les ids de la base sont des UUID opaques préfixés** pour aider au
débogage visuel. Exemples :

| Entité | Préfixe | Exemple |
|---|---|---|
| Classe | `cl_` | `cl_a1b2c3d4` |
| Élève | `el_` | `el_e7b7b33d` |
| Progression | `pg_` | `pg_dad5dec1` |
| Créneau | `cr_` | `cr_8ec503cf` |
| Référentiel | `rf_` | (disponible, pas utilisé — les référentiels gardent `N11_v2024`) |
| Notion / Méthode / Exercice / Livret / Image | `no_` / `me_` / `ex_` / `lv_` / `im_` | |

Les **contraintes d'unicité métier** ne sont plus portées par l'id, mais
par la table via des index `UNIQUE` :

```sql
classes:       UNIQUE (nom, annee, etablissement)
progressions:  UNIQUE (niveau, annee, etablissement)
```

Une tentative d'insérer un deuxième `(4e3, 2024-2025, Collège X)` est
rejetée par la base, indépendamment des ids opaques des deux entités.

## Nouveautés de code

**Module `persistence/ids.py`** centralise toutes les générations d'id :
`nouveau_id_classe()`, `nouveau_id_eleve()`, `nouveau_id_progression()`
etc. C'est l'unique point d'entrée ; plus aucun `uuid.uuid4()` disséminé.

**`SqliteStore.ecrire_progression`** refactorée : upsert par clé métier
`(niveau, annee, etablissement)`, l'id opaque existant est préservé. Si
on appelle avec une progression "nouvelle" (id opaque différent) mais les
mêmes clés métier, c'est traité comme un update, pas une création
(sinon violation UNIQUE).

**`JsonStore.ecrire_progression`** alignée : le nom de fichier est dérivé
de `(niveau, annee, etablissement)` slugifié, plus de l'id opaque.

**`importer_arborescence.py`** allégé : toute la logique d'anti-collision
des ids (`_hist`, `_annee`, `_etab`, compteur) est supprimée. Les UUID
garantissent l'unicité, la contrainte SQL fait la validation métier.

## Tests

**325 tests verts** (320 v0.6.1 + 4 nouveaux sur imports multi-années,
+ 1 sur la contrainte UNIQUE). Tests notables :

- `test_sqlite_store.py::TestClasses::test_contrainte_unique_nom_annee_etab` :
  validation SQL que 2 classes avec même `(nom, annee, etab)` sont rejetées.
- `test_import_arborescence.py` (4 tests) : import multi-années et
  multi-établissements, détection de doublons métier.
- Tous les tests de progression/classes/élèves mis à jour avec le
  nouveau format d'id opaque.

## Ce qui reste en état `en_cours` pour plus tard

La **bascule auto d'état du référentiel** (`valide → verrouille`) et
l'**écran de gestion des référentiels** annoncés en v0.6.1 sont toujours
d'actualité. La v0.6.2 ne les touche pas — elle corrige un bug de fond
qui aurait pollué tout ce qui suivait.

## Fichiers modifiés par rapport à v0.6.1

```
appli/persistence/ids.py           ← NOUVEAU
appli/persistence/schema.sql       ← UNIQUE sur classes et progressions
appli/persistence/sqlite_store.py  ← ecrire_progression par clé métier, _rowid
appli/persistence/json_store.py    ← fichiers progressions par clé métier
appli/services/classes.py          ← alias vers nouveau_id_classe/eleve
appli/services/progression.py      ← progression_id → UUID opaque
appli/services/atomes.py           ← ids typés
appli/importers/sequencesdb.py     ← nouveau_id_classe
appli/routes/progression.py        ← nouveau_id_creneau
appli/scanner_latex.py             ← ids typés
appli/importer_arborescence.py    ← logique anti-collision supprimée
appli/tests/*                      ← adaptation aux ids opaques
```

## Déploiement

Le schéma change (UNIQUE composite) donc il faut encore une fois effacer :

```
del data\seqenseigne.db
python importer_arborescence.py --racine D:\Enseignement_old
```

**Vérification attendue après import** (Admin → Base de données) :

- Classes : **20** (pas 1 !)
- Élèves : somme des élèves uniques, typiquement **400-500**
- Progressions : **10** (1 par niveau × année × établissement)
- Créneaux : ~180
- Niveaux saisis : >10 000
- Référentiels : **10**, tous verrouillés

Et le test fondamental : ouvrir la 4e6 de 2021-2022, séquence S03 —
Romane Chailloux doit avoir ses niveaux `E` et `A` sur les objectifs
`05` et `06` d'époque (c'était l'objectif initial du chantier v0.6).
