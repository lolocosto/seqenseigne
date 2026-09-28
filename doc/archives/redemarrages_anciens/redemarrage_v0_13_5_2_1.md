# Redémarrage — v0.13.5.2.1 (BDD + migration + service CRUD)

> Livraison du 9 mai 2026.
> Première sous-version de v0.13.5.2 : schéma BDD, migration, et
> service CRUD bas niveau pour les évaluations. Pas encore d'UI ni
> de génération PDF.

## Périmètre livré

### 1. Schéma BDD

**Modifications de tables existantes** (via migration `_migrer_schema_post_ddl`) :
- Ajout `mtime DATETIME` sur `notions`, `methodes`, `exercices`,
  `fiches_resume` (initialisé à `CURRENT_TIMESTAMP` pour les
  enregistrements existants)
- Ajout `type_format TEXT NOT NULL DEFAULT 'standard'` sur
  `exercices` (valeurs prévues : `'standard'`, `'qcm'`)

**Nouvelles tables** (créées par le DDL principal `schema.sql`) :
- `evaluations` : id, niveau, numero (stable), ordre (réordonnable),
  titre, mode_notation, afficher_bareme_dans_exos,
  item_langue_francaise, etat_code, mtime
  - Contraintes : UNIQUE (niveau, numero), CHECK sur les énumérés
- `evaluation_exercices` : liaison N:N avec ordre et barèmes
  (bareme_points pour modes note/criteres ;
  bareme_qcm_ok/partiel/ko pour les QCM)
  - PK composite (evaluation_id, exercice_id)
  - UNIQUE (evaluation_id, ordre)
  - ON DELETE CASCADE côté evaluations
  - ON DELETE RESTRICT côté exercices (protection : on ne supprime
    pas un exo référencé par une éval, contrôle métier en .2)

### 2. Migration auto au démarrage

Les modifications sur les tables existantes sont appliquées
automatiquement quand l'appli démarre (via
`SqliteStore._migrer_schema_post_ddl`). Idempotent : si la migration
a déjà eu lieu, no-op silencieux.

### 3. Script de migration CLI dédié

Fichier : `scripts/migrer_v0_13_5_2.py`

Pattern : `argparse` + dry-run par défaut + confirmation interactive
'OUI' (sauf `--yes`). Compatible avec les autres scripts de migration.

Usages :
- Diagnostic avant l'application : `python scripts/migrer_v0_13_5_2.py`
- Application : `python scripts/migrer_v0_13_5_2.py --apply`
- Application non interactive : `python scripts/migrer_v0_13_5_2.py --apply --yes`
- Sur une autre BDD : `python scripts/migrer_v0_13_5_2.py --db /chemin/autre.db --apply`

**Note** : ce script n'est pas indispensable en pratique vu la
migration auto au démarrage. Mais il est utile pour diagnostiquer
en mode dry-run et pour appliquer la migration sur une BDD hors-appli.

### 4. Service CRUD `services/evaluations.py`

API publique :
- `creer_evaluation(conn, *, niveau, titre, mode_notation, ...)` →
  dict
- `lire_evaluation(conn, evaluation_id)` → dict
- `lister_evaluations(conn, niveau=None)` → list[dict]
- `modifier_evaluation(conn, evaluation_id, *, ...)` → dict
  (PATCH-like, sentinelle `'__no_change__'` pour distinguer
  « pas modifié » de « effacé »)
- `supprimer_evaluation(conn, evaluation_id)` → None
- `ajouter_exo_a_evaluation(conn, evaluation_id, exercice_id, *, ...)`
- `retirer_exo_de_evaluation(conn, evaluation_id, exercice_id)`
- `lister_exos_evaluation(conn, evaluation_id)` → list[dict]
- `reordonner_exos_evaluation(conn, evaluation_id, ordre_exercices)`
- `modifier_bareme_exo(conn, evaluation_id, exercice_id, *, ...)`
- `reordonner_evaluations(conn, niveau, ordre_evaluations)`

Erreurs métier (toutes héritent de `EvaluationErreur`) :
- `EvaluationIntrouvable` (code `evaluation_introuvable`, → 404)
- `NumeroDejaUtilise` (code `numero_deja_utilise`, → 409)
- `ModeNotationInvalide` (code `mode_notation_invalide`, → 400)
- `EtatCodeInvalide` (code `etat_code_invalide`, → 400)
- `ItemLangueFrancaiseInvalide` (code
  `item_langue_francaise_invalide`, → 400)
- `ExerciceIntrouvable` (code `exercice_introuvable`, → 404)
- `ExoDejaPresent` (code `exo_deja_present`, → 409)
- `ExoIntrouvableDansEvaluation` (code
  `exo_introuvable_dans_evaluation`, → 404)
- `ReordonnancementInvalide` (code `reordonnancement_invalide`,
  → 409)

**Détail** : la mise à jour automatique du `mtime` de l'évaluation
est faite par les services dès qu'ils modifient le contenu (création,
modification, ajout/retrait/réordonnancement d'exos, modification
de barème). Le réordonnancement *des évaluations* (pas leur contenu)
ne touche pas au mtime.

**Hors périmètre v0.13.5.2.1** :
- Validation pédagogique en_cours → valide → reportée à v0.13.5.2.2
- Calcul de couverture des objectifs → reporté à v0.13.5.2.2 ou .3
- Routes Flask et UI → reportées à v0.13.5.2.3
- Génération PDF → reportée à v0.13.5.3
- Mécanisme `compile_*` → reporté à v0.13.5.5

## Tests

**55 nouveaux tests** dans `tests/test_v0_13_5_2_1_evaluations.py` :
- Création / lecture / liste / modification / suppression
- Validation des paramètres (mode_notation, etat_code,
  item_langue_francaise)
- Numéros et ordres auto-incrémentés
- Liaisons evaluation ↔ exercice (ajout, retrait, réordonnancement)
- Modification de barème
- Réordonnancement d'évaluations
- Migration v0.13.5.2 (script CLI : ajout mtime, type_format,
  création des tables)
- Idempotence de la migration (dry-run + apply + relance)
- Migration partielle idempotente (certaines colonnes déjà là)
- Migration auto via SqliteStore (BDD neuve, BDD pré-v0.13.5.2)

## Bilan tests

- État de référence : 1929 tests passent, 5 préexistants en échec
  (tous dans `test_route_rendu_atome.py`, liés à `pdflatex` non
  disponible côté Linux), 5 skippés.
- État après v0.13.5.2.1 : **1984 tests passent** (1929 + 55 nouveaux),
  **0 régression**, mêmes 5 échecs préexistants, mêmes 5 skippés.

## Vérification sur la BDD réelle

Migration testée sur la BDD réelle livrée par Laurent (`data/seqenseigne.db`) :
- Avant migration : 127 notions, 1213 exercices, pas de tables
  evaluations
- Migration appliquée en 7 opérations (4 ajouts mtime + 1 ajout
  type_format + 2 créations de tables)
- Après migration : 127 notions toutes avec mtime peuplé,
  1213 exercices tous en `type_format='standard'`, tables
  `evaluations` et `evaluation_exercices` créées avec les bonnes
  contraintes
- Re-passage en dry-run après migration : « Aucune modification à
  appliquer (BDD déjà à jour v0.13.5.2). » → idempotence confirmée

## Fichiers livrés

```
appli/
├── persistence/
│   ├── schema.sql                                   (modifié)
│   └── sqlite_store.py                              (modifié)
├── services/
│   └── evaluations.py                               (NOUVEAU)
├── scripts/
│   └── migrer_v0_13_5_2.py                          (NOUVEAU)
└── tests/
    └── test_v0_13_5_2_1_evaluations.py              (NOUVEAU)
```

## Plan de la suite

- **v0.13.5.2.2** — Services Python métier : validation pédagogique
  (transition `en_cours` → `valide` avec contrôles), calcul de
  couverture des objectifs.
- **v0.13.5.2.3** — UI atelier Évaluation : routes Flask, templates,
  JS, drag-and-drop pour `ordre`. Pas encore d'onglet « Rendu PDF »
  fonctionnel.
- **v0.13.5.3** — Génération `.tex` depuis BDD avec les macros
  finalisées en paquet v0.13.5.2.

---

*Fin du redémarrage v0.13.5.2.1.*
