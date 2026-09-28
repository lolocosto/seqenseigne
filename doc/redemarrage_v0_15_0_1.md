# Redémarrage v0.15.0.1 — Migration auto de réconciliation `objectifs ← objectifs_v2`

## Contexte (= incident)

En testant v0.15 chez Laurent, l'atelier Évaluation a révélé que :
- Le sélecteur d'objectifs déclarés était vide
- La matrice de couverture ne s'affichait pas
- Le rendu PDF prenait les barèmes des exos mais pas les objectifs

Le diagnostic via deux routes temporaires de lecture (`/api/diag/...`)
a montré :

```
objectifs       :   0 lignes  ← table active, vide
objectifs_v2    : 245 lignes  ← anciennes données, intactes
objectif_exos   : 735 liens   ← OK
sequence_parties:  55 lignes  ← OK
```

Les 245 objectifs étaient donc toujours en BDD, mais dans la table
`objectifs_v2` au lieu de la table active `objectifs`.

### Reconstitution du scénario

v0.14.7 avait prévu le renommage `objectifs_v2` → `objectifs` via un
script `scripts/renommer_objectifs_v2.py` à lancer **manuellement avant
le premier démarrage post-déploiement** :

```
1. Décompresser le ZIP
2. python -m scripts.renommer_objectifs_v2 --ecrire
3. python -m pytest  (vérification)
4. lancer.bat
```

Si l'étape 2 était omise et que `lancer.bat` était lancé directement
(réflexe naturel d'utilisateur), alors :
1. `schema.sql` (via `CREATE TABLE IF NOT EXISTS objectifs`) créait une
   table `objectifs` **vide**
2. `objectifs_v2` restait intacte à côté, avec ses 245 lignes
3. Le code de v0.14.7 (toutes les requêtes SQL réécrites pour cibler
   `objectifs`) lisait la table vide → aucun objectif n'apparaissait
   dans l'UI
4. Si l'utilisateur lançait ensuite le script de renommage, il
   refusait de tourner avec « ⚠ CONFLIT — La table de destination
   `objectifs` existe déjà ! ». Sans correction manuelle (SQL direct),
   l'utilisateur restait bloqué dans cet état.

C'est exactement ce qui s'est passé chez Laurent.

### Réparation immédiate

Un script de réparation `outils/reparer_objectifs_v0_15.py` a été livré
le jour J et exécuté avec succès :

```
INSERT OR IGNORE INTO objectifs
  (id, partie_id, code, nom, methode_id,
   critere_F, critere_A, critere_E, fin_cycle, nb_seances)
SELECT id, partie_id, code, nom, methode_id,
       critere_F, critere_A, critere_E, fin_cycle, nb_seances
FROM objectifs_v2
```

Résultat : 245 lignes copiées, vérification OK (jointures par niveau
N10/N11/N12 complètes, liens `objectif_exos` valides). L'atelier
Évaluation est revenu à la normale immédiatement.

## Ce que résout v0.15.0.1

v0.15.0.1 transforme cette réparation manuelle en **migration
automatique au démarrage** de `SqliteStore`. Elle se déclenche
silencieusement si :
- La table `objectifs_v2` existe (= BDD pré-v0.14.7 ou en état
  pathologique post-v0.14.7)
- La table `objectifs` est vide (cas pathologique)
- La table `objectifs_v2` n'est pas vide

Action effectuée : `INSERT OR IGNORE INTO objectifs SELECT * FROM
objectifs_v2`. Idempotente, silencieuse en cas de no-op.

Concrètement :
- Sur la BDD de Laurent (déjà réparée manuellement) : aucun effet
  au démarrage (la condition « objectifs vide » est fausse).
- Sur une BDD hypothétique d'un autre utilisateur qui aurait
  reproduit le même scénario v0.14.7 incomplet : réparation
  automatique au prochain `lancer.bat`.

Le message imprimé en console au démarrage si la migration tourne :

```
[seqenseigne] ✓ migration v0.15.0.1 : 245 objectif(s) reconciliés depuis objectifs_v2 (cf. note v0.14.7 incomplète)
```

## Cadrage validé (C1-C3)

| Question | Réponse |
|---|---|
| C1 — Stratégie | (a) Migration silencieuse au démarrage, idempotente |
| C2 — Script v0.14.7 | (b) Supprimer `scripts/renommer_objectifs_v2.py` |
| C3 — `objectifs_v2` | À garder ; inscrit dans la dette technique |

## Ce qui change dans cette livraison

### 1. Migration auto ajoutée — `persistence/sqlite_store.py`

Bloc ajouté à la fin de `_migrer_schema_post_ddl` (juste après la
migration `cartes_automatisme.nom → titre` de v0.13.6.15). Pattern
strictement identique aux autres migrations du fichier : `try/except`
large, `print` succinct si action effective, idempotence par
condition de garde (`if n_actif == 0 and n_v2 > 0`).

### 2. Script supprimé — `scripts/renommer_objectifs_v2.py`

La fonction d'origine (renommer la table) est remplacée par la
migration auto qui fait l'équivalent fonctionnel (les données
arrivent au bon endroit). La table `objectifs_v2` n'est **pas**
renommée — elle reste en place comme filet de sécurité, à supprimer
plus tard (cf. `doc/DETTE_TECHNIQUE.md`).

### 3. Tests — `tests/test_v0_14_7_renommage.py`

- **Supprimés** : `TestScriptRenommer` (3 tests qui dépendaient du
  script supprimé)
- **Ajoutés** : `TestMigrationReconciliationV0_15_0_1` (4 tests)
  - `test_reconciliation_quand_objectifs_vide` : reproduit le bug
    v0.14.7 et vérifie que la migration copie les données.
  - `test_idempotence_sur_base_deja_reconciliee` : si les deux tables
    sont déjà identiques, aucune duplication.
  - `test_pas_de_migration_si_objectifs_v2_absente` : sur BDD propre
    (jamais passée par v0.14.6/v0.14.7), aucune erreur.
  - `test_script_renommer_supprime` : assertion factuelle que le
    script v0.14.7 n'existe plus.
- Docstring du module et un séparateur mis à jour pour refléter
  l'évolution v0.14.7 → v0.15.0.1.

### 4. Nouveau fichier — `doc/DETTE_TECHNIQUE.md`

Centralise les éléments de dette technique connus :
- **Supprimer `objectifs_v2`** (différé sur demande de Laurent — C3)
- **Supprimer `static/atelier_evaluation.js`** (cohabitation v0.15
  arrivée à terme une fois v0.15 stable)
- **Corriger `ATL_ATOME_CONFIG is not defined`** dans `app.js:2589`
  (code mort depuis v0.13.7.0c, erreur dans la console)

## Vérifs

- **Suite complète** : 3390 passed, 6 skipped, 0 failed
  (état v0.15 = 3389 ; +4 nouveaux tests v0.15.0.1, -3 tests
  `TestScriptRenommer`)
- **Test end-to-end manuel** dans un dossier temporaire reproduit
  exactement l'état de Laurent (245 dans v2, 0 dans actif) :
  la migration auto déclenche et reconcilie au prochain démarrage,
  comme attendu.
- **Sanity Python** sur tous les fichiers modifiés.

## Fichiers livrés

```
MODIFIÉ
  appli/persistence/sqlite_store.py        (migration auto ajoutée)
  appli/tests/test_v0_14_7_renommage.py    (-3 tests / +4 tests)

SUPPRIMÉ
  appli/scripts/renommer_objectifs_v2.py   (remplacé par migration auto)

NOUVEAU
  appli/doc/DETTE_TECHNIQUE.md             (suivi global de la dette)
  appli/doc/redemarrage_v0_15_0_1.md       (cette note)
```

## Procédure d'application

### 1. Sauvegarde de la BDD (par prudence)

```powershell
cd D:\Enseignement\seqenseigne\appli\data
copy seqenseigne.db seqenseigne.db.avant_v0_15_0_1
```

### 2. Avant de décompresser : nettoyage des fichiers temporaires v0.15

Les deux fichiers de diagnostic et le script de réparation manuel
deviennent inutiles. Tu peux les supprimer **chez toi** (ils ne sont
pas dans le ZIP de cette livraison) :

```
appli/routes/diag_v0_15.py            ← supprimer
appli/outils/reparer_objectifs_v0_15.py ← supprimer
```

Et retirer dans `app.py` les lignes :
```python
from routes.diag_v0_15 import bp as bp_diag_v0_15  # TEMPORAIRE v0.15
... + bp_diag_v0_15 dans le for bp in (...)
```

Ces nettoyages sont indépendants de v0.15.0.1 ; ils étaient à faire
de toute façon.

### 3. Décompresser le ZIP v0.15.0.1

Aucun fichier à supprimer manuellement (le ZIP supprime
`scripts/renommer_objectifs_v2.py` via le MANIFEST de suppressions
ci-dessous — à appliquer à la main si tu n'as pas la procédure
automatique).

⚠ **Suppressions à faire manuellement** :
- `appli/scripts/renommer_objectifs_v2.py`

### 4. Vérifier l'intégrité

```powershell
.\outils\python\python.exe appli\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
```

### 5. Lancer la suite de tests

```
cd appli
python -m pytest -q
```

Attendu : `3390 passed, 6 skipped, 0 failed`.

### 6. Lancer l'app et vérifier les logs

```
lancer.bat
```

Sur ta BDD actuelle (déjà réparée manuellement), tu **ne dois PAS**
voir le message `[seqenseigne] ✓ migration v0.15.0.1 : ...` — la
migration est silencieuse car `objectifs` n'est plus vide. C'est le
résultat attendu.

Si jamais tu vois le message, ça signifie qu'il y a une régression
inattendue dans ta BDD ; ouvre un sujet.

### 7. Vérifier que l'atelier Évaluation fonctionne toujours

Comme à chaque livraison : ouvrir une éval, vérifier que le sélecteur
d'objectifs est peuplé, que la matrice de couverture s'affiche, et
que la compilation PDF inclut les objectifs déclarés.

## Métriques

- 1 méthode modifiée (`_migrer_schema_post_ddl`) — +47 lignes
- 1 script supprimé (`scripts/renommer_objectifs_v2.py`, 255 lignes)
- 4 nouveaux tests / 3 tests supprimés
- 2 nouveaux fichiers de doc

## Prochaine étape

Au choix selon priorité :
- **v0.15.0.2** : nettoyage final v0.15 (suppression de
  `static/atelier_evaluation.js` ancien + correction d'`ATL_ATOME_CONFIG`).
  Petit chantier, isolé.
- **v0.15.1** : migration de l'atelier Livret (`atelier_seqniv_assemblage.js`,
  2642 lignes) vers `AtelierLivret extends AtelierAssemblage`. Gros
  chantier, ferme la dette OO.
- **v0.16+** : nouvelles fonctionnalités métier (cf. roadmap dans
  `INDEX.md`).
