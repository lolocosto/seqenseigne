# Redémarrage v0.14.7 — Renommage cosmétique `objectifs_v2` → `objectifs`

## Position dans le chantier

| Étape | Statut |
|---|---|
| v0.14.5 : Audit lecture seule | ✓ Déployé |
| v0.14.6.a : Migration v1→v2 + backup | ✓ Déployé |
| v0.14.6.b.1 : Réécriture services + suppression UI | ✓ Déployé |
| v0.14.6.b.2 : DROP TABLE v1 + nettoyage code | ✓ Déployé |
| **v0.14.7 : Renommage cosmétique (cette livraison)** | ⏳ |

**Chantier v1 cosmétiquement clos après cette livraison.**

## Cadrage validé (Q1-Q4)

| Question | Réponse |
|---|---|
| Q1 — Périmètre SQL | (b) Renommer la table + nettoyer les commentaires |
| Q2 — Fichiers `v2_*.py` | (a) Garder (`v2` désigne le modèle, pas la table) |
| Q3 — Routes `/api/v2/...` | (a) Garder (contrats avec le frontend) |
| Q4 — Identifiants Python avec `v2` | (b) Renommage mécanique quand `v2` est trompeur |

Concrètement, Q4=(b) signifie :
- ✅ Toutes les **requêtes SQL** : `objectifs_v2` → `objectifs`
- ✅ **Commentaires SQL/Python** qui mentionnent `objectifs_v2` comme nom de table
- ✅ **Fixtures de tests** qui faisaient `CREATE TABLE objectifs_v2`
- ❌ **Pas** renommer les classes `V2LectureErreur`, `V2EditionErreur` (cohérence avec les fichiers gardés)
- ❌ **Pas** renommer les blueprints `bp_v2_lecture`, `bp_v2_edition`
- ❌ **Pas** renommer les références au **modèle v2** comme concept

## Ce qui change dans cette livraison

### 1. Script SQL `scripts/renommer_objectifs_v2.py`

Nouveau script qui effectue 3 opérations sur la base existante :

1. `ALTER TABLE objectifs_v2 RENAME TO objectifs`
2. `DROP INDEX idx_objectifs_v2_partie`
3. `CREATE INDEX idx_objectifs_partie ON objectifs(partie_id)`

SQLite met **automatiquement** à jour les FK qui pointaient vers
`objectifs_v2(id)` (depuis SQLite 3.25). Les 4 FK concernées :
- `objectif_notions.objectif_id`
- `objectif_cartes.objectif_id`
- `objectif_exos.objectif_id`
- `fiches_resume.objectif_id`

(SQLite ne supporte pas `ALTER INDEX RENAME` ; d'où le DROP+CREATE.)

Sécurités :
- Mode `--dry-run` par défaut
- Backup automatique avant écriture
  (`data/backups/seqenseigne-pre-renommage-v0.14.7-{timestamp}.db`)
- Transaction unique avec ROLLBACK si erreur
- Idempotent (relançable sur base déjà à jour)

### 2. Schéma `persistence/schema.sql` mis à jour

- `CREATE TABLE objectifs_v2` → `CREATE TABLE objectifs`
- `CREATE INDEX idx_objectifs_v2_partie` → `CREATE INDEX idx_objectifs_partie`
- Toutes les `REFERENCES objectifs_v2(id)` → `REFERENCES objectifs(id)`
- Commentaires "phase de cohabitation v2" mis à jour pour refléter
  la chronologie complète du chantier

### 3. Code de prod nettoyé (renommage en masse)

**335 occurrences** de `objectifs_v2` remplacées par `objectifs` dans
**les requêtes SQL** des fichiers suivants :

- `persistence/sqlite_store.py`
- `services/cartes_automatisme.py`, `evaluations.py`, `fiches_import.py`,
  `fiches_resume.py`, `latex_rendu_atome.py`, `liaisons_atomes.py`,
  `livret_plans_de_travail.py`, `livret_sequence.py`, `referentiels.py`,
  `sequences_du_cycle.py`, `v2_edition.py`, `v2_lecture.py`
- `routes/atomes.py`, `routes/evaluations.py`
- `importers/scanner_latex.py`
- `scripts/diagnostic_livret_N10_S01.py`,
  `scripts/lister_atomes_orphelins.py`

Note : les noms de fichiers `v2_lecture.py`, `v2_edition.py`,
`bp_v2_lecture`, `bp_v2_edition`, et les routes `/api/v2/...` restent
inchangés (Q2 + Q3).

### 4. Fichiers supprimés (4 scripts + 4 tests)

Scripts historiques de migration v1→v2 dont la raison d'être disparaît :

- `scripts/audit_v1_v2.py` (la table v1 n'existe plus → audit impossible)
- `scripts/migrer_v1_vers_v2.py` (migration déjà appliquée + plus possible)
- `scripts/migrer_methodes_objectifs.py` (migration ponctuelle de
  v0.13.7.6.1.1 déjà appliquée chez tous les utilisateurs)
- `scripts/peuplement_12_migrer_schema_sequences.py` (migration vers
  le modèle R4, déjà appliquée)

Tests associés supprimés :
- `tests/test_v0_14_5_audit_v1_v2.py`
- `tests/test_v0_14_6a_migration_v1_vers_v2.py`
- `tests/test_migrer_methodes_objectifs.py`
- `tests/test_R4a_schema.py` (testait `peuplement_12_*` supprimé)

### 5. Tests existants adaptés

- `tests/test_v0_14_6_b2_suppression_v1.py::TestTablesV1Absentes` :
  les tests `test_objectifs_absente` et `test_objectifs_v2_present`
  retirés (l'assertion n'a plus de sens : `objectifs` existe maintenant,
  c'est l'ex-`objectifs_v2`). Tests équivalents dans le nouveau fichier
  dédié.
- `tests/test_latex_rendu_atome.py` : fixture nettoyée (avait 2 `CREATE
  TABLE objectifs` : v1 + v2 → fusionnées en une seule).
- `tests/test_v0_13_5_3_render_evaluation.py` : idem (2 `CREATE TABLE
  objectifs` fusionnés).
- + 33 autres fichiers de tests : renommage SQL automatique
  (`objectifs_v2` → `objectifs`).

### 6. Nouveau test dédié v0.14.7

`tests/test_v0_14_7_renommage.py` — 19 tests qui valident l'état final :

- **3 tests** : table `objectifs` présente, `objectifs_v2` absente,
  colonnes attendues
- **2 tests** : index renommé (`idx_objectifs_partie` présent,
  ancien absent)
- **4 tests** : les 4 FK pointent vers `objectifs` (et pas vers
  `objectifs_v2`)
- **1 test** : CASCADE ON DELETE fonctionne sur le nouveau nom
- **3 tests** : script `renommer_objectifs_v2.py` présent, idempotent
  sur base déjà renommée, et renommage effectif sur base au schéma
  pré-v0.14.7
- **4 tests** : les 4 scripts historiques sont bien supprimés
- **2 tests** : chaînes principales (création d'un objectif, JOIN
  canonique avec parties et séquences) fonctionnent

## Vérifs

- Suite complète : **3379 passed, 6 skipped, 0 failed**
- Script `renommer_objectifs_v2.py` testé en dry-run + écriture +
  idempotence + FK mises à jour automatiquement par SQLite
- Sanity Python OK sur tous les fichiers modifiés
- Sanity SQL OK sur le schéma (54 tables créées, FK correctes)

## Procédure d'application

### 1. Supprimer les 8 fichiers obsolètes

Voir `MANIFEST_SUPPRESSIONS.md` à la racine du ZIP.

### 2. Décompresser le ZIP sur la racine `seqenseigne/`

### 3. Lancer le script SQL — DRY-RUN d'abord

```
cd appli
python -m scripts.renommer_objectifs_v2
```

Tu verras :
- État avant : `objectifs_v2` présente (X lignes) + index
  `idx_objectifs_v2_partie` présent
- Plan : 3 étapes (RENAME + DROP INDEX + CREATE INDEX)
- Mode `DRY-RUN` (rien modifié)

### 4. Appliquer

```
python -m scripts.renommer_objectifs_v2 --ecrire
```

Backup automatique créé avant.

### 5. Tests automatiques

```
python -m pytest tests/test_v0_14_7_renommage.py -v
# Attendu : 19 passed

python -m pytest -q
# Attendu : 3379 passed, 6 skipped, 0 failed
```

### 6. Tests fonctionnels manuels

Cette livraison est **purement cosmétique côté données** : aucune
structure, aucune donnée ne change. Le risque fonctionnel est faible
mais il faut quand même valider :

#### a) Démarrage Flask

```
lancer.bat
```

Console propre.

#### b) Atelier Méthode + Exercice

Comme à chaque release : ouvrir, modifier, sauvegarder, compiler PDF.

#### c) Atelier Séquence-niveau

Particulièrement important : c'est l'atelier qui utilise le plus
intensément la table `objectifs` (anciennement `objectifs_v2`).
Tester l'assemblage complet d'une séquence N10/S01.

#### d) Compilation d'un livret de séquence

Doit produire le même PDF qu'avant.

#### e) Fiches de résumé

Si tu en utilises : ouvrir une fiche, vérifier qu'elle se compile.

## Sécurité

- Backup pré-renommage créé automatiquement par le script
- Tous les backups précédents restent disponibles dans
  `appli/data/backups/`
- Opération SQL encapsulée dans une transaction avec ROLLBACK auto

## Métriques

- 4 fichiers de code supprimés + 4 fichiers de tests supprimés
- 1 table renommée + 1 index renommé
- 4 FK automatiquement mises à jour par SQLite
- 335 occurrences SQL `objectifs_v2 → objectifs` dans le code Python
- 19 nouveaux tests dédiés
- Suite : 3379 passed, 0 failed

## Le chantier v1 est-il vraiment terminé ?

Oui, fonctionnellement et cosmétiquement. La table `objectifs` est
désormais le modèle unique. Les concepts "v1" et "v2" ne survivent que
dans :
- Les noms de fichiers `services/v2_lecture.py` et `services/v2_edition.py`
- Les classes d'exception `V2LectureErreur`, `V2EditionErreur`
- Les routes `/api/v2/...`
- Les blueprints `bp_v2_lecture`, `bp_v2_edition`

Ces éléments désignent le **modèle de données** établi en R4
(séquences-par-niveau, parties, précédences) — pas la table. Ils
peuvent rester tels quels ; si tu veux un jour les renommer aussi,
ce sera un chantier dédié de refactoring (différent de la suppression
de v1).
