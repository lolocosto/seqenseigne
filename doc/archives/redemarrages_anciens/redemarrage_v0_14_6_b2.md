# Redémarrage v0.14.6.b.2 — Suppression effective des tables v1

## Position dans le chantier de suppression v1

| Étape | Statut |
|---|---|
| v0.14.5 : Audit lecture seule | ✓ Déployé |
| v0.14.6.a : Migration v1→v2 + backup | ✓ Déployé |
| v0.14.6.b.1 : Réécriture services + suppression UI | ✓ Déployé et validé |
| **v0.14.6.b.2 : DROP TABLE + nettoyage** (cette livraison) | ⏳ |
| v0.14.7 : Renommage cosmétique `objectifs_v2` → `objectifs` | À venir |

## Cadrage validé (Q1-Q4 + Q6-Q9)

| Question | Réponse |
|---|---|
| Q1 — `livret_exercices` | (a) Supprimer la table — table fantôme |
| Q2 — Script `supprimer_v1.py` | (a) OK, même pattern que `migrer_v1_vers_v2.py` |
| Q3 — Tests skippés en b.1 | (a) Supprimer |
| Q4 — `test_peuplement_plans_de_travail.py` + parseur | (a) Tout supprimer |
| Q6 — `livret_exercices` confirmé | (a) Table à supprimer (legacy : la liaison directe `exercice ↔ objectif` via `objectif_exos` v2 suffit) |
| Q7 — `scanner_vers_v2.py` | À supprimer : sa raison d'être (migration v1→v2) disparaît avec v1. La BDD est désormais source de vérité, plus besoin de re-scanner les .tex |
| Q8 — Scripts peuplement_03/04/05/06/13/15 | À supprimer (chaîne legacy v1) |
| Q9 — `edition_progression.py` (stub en b.1) | Suppression complète |

## Ce qui change dans cette livraison

### 1. Script SQL `scripts/supprimer_v1.py`

Nouveau script qui effectue les 4 opérations SQL nécessaires sur la base
existante :

1. **`ALTER TABLE niveaux DROP COLUMN objectif_id`** (préalable
   obligatoire — FK orpheline vers `objectifs(id)` qui aurait empêché
   tout INSERT dans `niveaux` après le DROP avec
   `PRAGMA foreign_keys=ON`)
2. **`DROP TABLE exercice_objectifs`**
3. **`DROP TABLE livret_exercices`**
4. **`DROP TABLE objectifs`**

Sécurités :

- Mode `--dry-run` par défaut (affiche le plan sans rien modifier)
- Backup automatique avant toute écriture
  (`data/backups/seqenseigne-pre-suppression-v0.14.6.b.2-{timestamp}.db`)
- Transaction unique avec ROLLBACK si erreur
- Idempotent (relançable, ignore les tables/colonnes déjà supprimées)

Requiert SQLite ≥ 3.35 (Python 3.13+ embarque SQLite 3.45, OK).

### 2. Schéma `persistence/schema.sql` mis à jour

Pour les **bases neuves** créées après cette livraison :

- Les 3 tables v1 (`objectifs`, `exercice_objectifs`, `livret_exercices`)
  ne sont **plus déclarées** dans le schéma.
- La table `niveaux` est déclarée **sans** la colonne `objectif_id`.

### 3. Code de prod nettoyé

**`persistence/sqlite_store.py`** — 4 zones nettoyées :
- `ecrire_exercices` : DELETE résiduels sur `exercice_objectifs` et
  `livret_exercices` retirés
- `ecrire_livrets_importes` : tout le bloc qui peuplait
  `livret_exercices` via `exercice_objectifs` retiré (~50 lignes
  supprimées). Le champ JSON `contenu` du livret reste accessible.
- `reset_reference` : DELETE des tables supprimées retirés
- `set_niveau` / `ecrire_niveaux` : INSERT ne passe plus
  `objectif_id` (colonne retirée). La méthode privée
  `_objectif_id_pour` n'est plus appelée mais conservée (sans effet
  de bord — peut être supprimée plus tard).

**`importers/scanner_latex.py`** — étape 4 retirée :
- `_peupler_v2()` (helper interne) supprimé
- L'appel après l'écriture des atomes est retiré
- La clé `"v2"` du rapport disparaît
- Docstring du module mise à jour

**`app.py`** — blueprint `bp_peuplement_v2` retiré (import + registre)

**`scripts/peuplement_01_migrer_schema.py`** — Entrée `objectifs` dans
`COLONNES_A_AJOUTER` retirée + index `idx_objectifs_niv_seq` retiré.
Compteur d'index attendu passé de 7 à 6.

### 4. Fichiers supprimés (16 au total)

**Code (10)** :
- `services/scanner_vers_v2.py` — outil de migration v1→v2 (raison
  d'être disparue)
- `services/edition_progression.py` — était un stub en b.1, code mort
- `importers/scanner_plan_de_travail.py` — utilisé uniquement par
  `scanner_vers_v2.py`
- `routes/peuplement_v2.py` — endpoints `/api/admin/v2/peupler` et
  `/api/admin/v2/statistiques` (plus de raison d'être)
- `scripts/peuplement_03_deduire_liaisons.py` — déduisait les
  liaisons v1
- `scripts/peuplement_04_appliquer_liaisons.py` — écrivait
  `est_nouveau` / `obj_precedent_id` v1 (concepts abandonnés)
- `scripts/peuplement_05_plans_de_travail.py` — peuplait
  `methode_notions` via parsing v1
- `scripts/peuplement_06_resoudre_liaisons_interactif.py` — UI CLI
  pour liaisons v1
- `scripts/peuplement_13_v2_depuis_base.py` — wrapper CLI de
  `scanner_vers_v2.py`
- `scripts/peuplement_15_fin_cycle_vers_objectifs.py` — écrivait
  `fin_cycle` dans v1

**Tests (6)** :
- `test_R4b_routes.py` — testait les routes `/api/admin/v2/*`
- `test_R4b_scanner_vers_v2.py` — testait `scanner_vers_v2.py`
- `test_R4e1fix_premier_chiffre.py` — testait `scanner_vers_v2.py`
- `test_peuplement_15_fin_cycle.py` — testait
  `peuplement_15_fin_cycle_vers_objectifs.py`
- `test_peuplement_liaisons.py` — testait
  `peuplement_03/04_deduire/appliquer_liaisons.py`
- `test_peuplement_plans_de_travail.py` — testait
  `peuplement_05_plans_de_travail.py` et `scanner_plan_de_travail.py`

### 5. Tests existants adaptés (8 fichiers, Q3=c)

- `tests/test_v0_14_6_b1_services_lisent_v2.py` : 5 tests v1 obsolètes
  retirés + `TestEditionProgressionStub` → `TestEditionProgressionSupprime`
- `tests/test_sqlite_store.py::TestNiveaux` : INSERT v1 du setup
  retirés (plus utiles, FK supprimée)
- `tests/test_peuplement_repeupler.py` : 3 tests obsolètes retirés
  (`test_liaison_exercice_objectifs`, `test_objectifs_codes_inconnu_ignore`,
  `test_exo_sans_objectif_lie_ignore`)
- `tests/test_ecrire_exercices_fk.py` : helper `_creer_v2_et_liaison`
  simplifié (step 1 v1 retirée), test obsolète retiré
- `tests/test_R4a_schema.py` : `test_ancienne_objectifs_cohabite`
  → `test_ancienne_objectifs_supprimee` (assertion inversée)
- `tests/test_peuplement_schema.py` : `test_colonnes_ajoutees_dans_objectifs`
  retiré, compteur index ajusté
- `tests/test_resoudre_macros.py` : `test_peuplement_v2_saute_si_niveau_vide`
  retiré
- `tests/test_reset_reference_full.py` : fixture débarrassée des INSERT
  v1, liste de tables-à-vider ajustée

### 6. Nouveau test dédié

`tests/test_v0_14_6_b2_suppression_v1.py` — 25 tests qui valident
l'état final :

- **8 tests** : tables v1 absentes du schéma + `objectifs_v2` présente
- **3 tests** : colonne `niveaux.objectif_id` retirée + autres colonnes
  préservées + INSERT fonctionne sous `PRAGMA foreign_keys=ON`
- **10 tests** : 10 fichiers de code obsolètes absents
- **3 tests** : imports des modules supprimés échouent (ImportError)
- **2 tests** : routes `/api/admin/v2/*` retournent 404
- **1 test** : pas de helper `_peupler_v2` dans `scanner_latex`
- **2 tests** : script `supprimer_v1.py` présent et idempotent sur
  base déjà nettoyée

## Vérifs

- Suite complète : **3456 passed, 6 skipped, 0 failed**
- Schéma fraîchement créé : 54 tables, aucune des 3 tables v1
- Script `supprimer_v1.py` testé en dry-run + écriture + idempotence

## Procédure d'application chez toi

⚠ **Important** : à la différence des livraisons précédentes, celle-ci
**supprime des fichiers**. Il faut le faire manuellement avant ou après
décompression.

### 1. Vérifier le backup pré-migration (filet de sécurité)

Le backup créé à v0.14.6.a est toujours présent :
```
appli/data/backups/seqenseigne-pre-migration-v0.14.6a-20260520-230134.db
```

### 2. Supprimer les 16 fichiers obsolètes

Voir `MANIFEST_SUPPRESSIONS.md` à la racine du ZIP pour la commande
PowerShell prête à coller.

### 3. Décompresser le ZIP sur la racine `seqenseigne/`

Il écrase les fichiers modifiés et ajoute les nouveaux. Aucun fichier
de production existant ne va être supprimé par cette étape (les ZIPs
ne suppriment jamais — c'est l'étape précédente qui s'en charge).

### 4. Lancer le script SQL — DRY-RUN d'abord

```
cd appli
python -m scripts.supprimer_v1
```

Tu verras :
- État actuel de tes 3 tables v1 (avec nombre de lignes)
- État de la colonne `niveaux.objectif_id`
- Plan de suppression (4 étapes)
- Confirmation que le mode est `DRY-RUN` (rien n'a été modifié)

### 5. Appliquer la suppression

```
python -m scripts.supprimer_v1 --ecrire
```

Le script :
1. Crée un backup automatique
   (`data/backups/seqenseigne-pre-suppression-v0.14.6.b.2-{timestamp}.db`)
2. Ouvre une transaction
3. Effectue les 4 opérations
4. Commit (ou ROLLBACK si erreur)

### 6. Tests automatiques

```
python -m pytest tests/test_v0_14_6_b2_suppression_v1.py -v
# Attendu : 25 passed

python -m pytest -q
# Attendu : 3456 passed, 6 skipped, 0 failed
```

### 7. Tests fonctionnels manuels (essentiels)

Cette livraison touche au schéma et au code d'import — il faut valider
en réel :

#### a) Démarrage Flask

```
lancer.bat
```

La console doit être propre. Aucune erreur Python.

#### b) Atelier Méthode

- Ouvrir l'atelier Méthode
- Choisir une méthode existante (ex: N11/S05)
- Vérifier que les critères F/A/E s'affichent toujours
- Modifier un critère, sauvegarder
- Re-ouvrir : modification conservée

#### c) Atelier Exercice + compilation PDF

- Ouvrir un exercice
- Vérifier que les objectifs liés s'affichent
- Compiler le PDF

#### d) Compilation d'un livret de séquence

- Atelier Séquence-niveau → N10/S01
- Compiler le livret de séquence complet
- Doit produire le même PDF qu'avant

#### e) Saisie d'un niveau de maîtrise (suivi)

C'est le point qui touche au changement de schéma de `niveaux` :

- Ouvrir le suivi d'une classe
- Saisir un niveau de maîtrise sur un objectif
- Sauvegarder
- Re-ouvrir : valeur conservée

#### f) Réinitialisation BDD (Admin > BDD > Réinitialiser)

À tester si tu utilises cette fonction :

- Cliquer "Vider données de référence"
- Vérifier que ça marche sans erreur (la fonction `reset_reference`
  ne touche plus aux tables v1 supprimées)

## Sécurité

- Backup v0.14.6.a toujours disponible
- Backup automatique créé par `supprimer_v1.py --ecrire`
- En cas de problème majeur, restauration possible :
  copier le backup sur `data/seqenseigne.db`

## Métriques

- 16 fichiers code/tests supprimés
- ~1500 lignes de code v1 retirées (estimation)
- 3 tables SQL supprimées (`objectifs`, `exercice_objectifs`,
  `livret_exercices`)
- 1 colonne SQL retirée (`niveaux.objectif_id`)
- Suite de tests : 3456 passed, 0 failed
- Nouveau script CLI : `scripts/supprimer_v1.py` (dry-run par défaut,
  backup auto, transaction, idempotent)

## Prochaine étape : v0.14.7

Renommage cosmétique de `objectifs_v2` → `objectifs` (sans suffixe `_v2`).
Opération simple `ALTER TABLE objectifs_v2 RENAME TO objectifs`, suivie
d'une mise à jour de toutes les références SQL et Python. Sortira après
validation complète de b.2 chez toi.
