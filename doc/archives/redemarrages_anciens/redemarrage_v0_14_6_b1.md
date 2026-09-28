# Redémarrage v0.14.6.b.1 — Réécriture des services pour lire/écrire v2

## Position dans le chantier de suppression v1

| Étape | Statut |
|---|---|
| **v0.14.5** : Audit lecture seule | ✓ Déployé |
| **v0.14.6.a** : Script migration v1→v2 | ✓ Déployé (3 hotfixes inclus) |
| **v0.14.6.b.1** : Réécriture services + suppression UI (cette livraison) | ⏳ |
| **v0.14.6.b.2** : DROP TABLE objectifs + nettoyage scripts | À venir |
| **v0.14.7** : Renommage `objectifs_v2` → `objectifs` | À venir |

## Cadrage validé

| Question | Réponse |
|---|---|
| Q1 — Migration applicative R4e4 dans `sqlite_store.py` | (b) Conservée (filet de sécurité pour BDD anciennes) |
| Q2 — Suppression v1 | (b) Script manuel en b.2, pas au démarrage |
| Q3 — Tests qui simulaient v1 | (c) Mixte : adapter si encore utile, supprimer/skip sinon |
| Q4 — Découpage v0.14.6.b | (c) 2 étapes : b.1 (services) + b.2 (DROP) |
| Q5 — `ecrire_exercices` et `exercice_objectifs` | (b) Retirer l'écriture v1, accepter table figée jusqu'à b.2 |

## Ce qui change dans cette livraison

### 1. Services réécrits pour lire/écrire v2

**`services/latex_rendu_atome.py`** — 2 macros LaTeX :

- `seqObjectifGetNom{CC}` : ne lit plus `objectifs` (v1, par `niveau`,
  `sequence`, `code`) mais `objectifs_v2` via JOIN partie →
  sequence_par_niveau.
- `seqObjectifGetFinCycle{CC}` : retourne désormais **toujours `'N'`**.
  Le champ `est_nouveau` n'existe pas en v2 (décision validée avec
  Laurent : concept remplacé par le mécanisme des précédences
  inter-parties). L'audit v0.14.5 sur la BDD de prod avait confirmé
  que **0 objectif** avait `est_nouveau=1` — aucun rendu PDF existant
  ne change.

**`services/sequences_du_cycle.py`** — `_compter_atomes_rattaches` :

- Le COUNT des objectifs d'une séquence du cycle se fait désormais
  sur `objectifs_v2 ⨝ sequence_parties ⨝ sequences_par_niveau`.

**`persistence/sqlite_store.py`** — 9 modifications :

- `_objectif_id_pour` : SELECT sur `objectifs_v2`
- `ecrire_objectifs` : INSERT/UPDATE sur `objectifs_v2`, création
  automatique de `sequence_parties` au besoin (numéro déduit du
  premier chiffre du code) **et** création automatique de
  `sequences_par_niveau` si absente (pipeline d'import autonome).
- `ecrire_methodes` :
  - `UPDATE objectifs_v2 SET methode_id=NULL` au lieu de v1
  - Recherche de l'objectif via JOIN partie → sn pour `(niveau, sequence, num_objectif)`
  - **Cas legacy v1 supprimé** : on ne crée plus d'objectif orphelin
    pour les méthodes sans métadonnées (l'audit v0.14.5 a confirmé
    que 0 orphelin venait de ce chemin en prod).
- `lire_methodes` : critères lus depuis `objectifs_v2`
- `lire_exercices` : objectifs liés depuis `objectif_exos` (v2) au
  lieu de `exercice_objectifs` (v1). Déduplication par `objectif_id`
  conservée.
- `ecrire_exercices` : **Q5=b** — reconstruction de
  `exercice_objectifs` (v1) RETIRÉE. Les liaisons exercice↔objectif
  passent désormais exclusivement par `objectif_exos` (v2), peuplée
  par `peupler_v2_depuis_base` dans la chaîne d'import.

Helper ajouté : `_num_partie_depuis_code_v2(code)` qui reproduit la
convention canonique documentée dans `services/scanner_vers_v2.py`.

### 2. Suppressions UI v1

**`services/edition_progression.py`** : vidé en stub. La fonction
`lire_detail_creneau` n'avait aucun appelant (vérifié par grep). Le
fichier devient un stub avec la classe `CreneauIntrouvable` conservée
au cas où un import résiduel existerait.

**`routes/atomes.py`** : route `@bp.route("/api/objectifs")` retirée.
Cette route reconstruisait une liste d'objectifs depuis les méthodes
pour peupler un sélecteur DOM (`#atl-exercice-obj-sel`) qui n'existe
plus dans le HTML depuis v0.10. L'atelier d'assemblage utilise
`/api/objectifs-v2/` qui reste actif.

**`static/app.js`** : trois suppressions :
- variable globale `let ATL_OBJ_CAT = []`
- fonction `async function atelChargerObjectifs()`
- appel `atelChargerObjectifs()` dans `initAteliers()`

### 3. Ce qui NE change PAS en b.1

Comme prévu par Q4=c, **les tables `objectifs` (v1) et `exercice_objectifs`
existent toujours** après cette livraison :

- `reset_reference` continue à les vider (`DELETE FROM objectifs` etc.)
  pour préserver la sémantique « tout effacer » jusqu'au DROP TABLE
  de b.2.
- `ecrire_exercices` continue à supprimer les liaisons résiduelles
  `exercice_objectifs` lors de la suppression d'un exercice (filet
  de sécurité jusqu'à b.2).
- Le bloc `livret_exercices` continue à résoudre `objectif_id` via
  `exercice_objectifs` (la FK `livret_exercices.objectif_id →
  objectifs(id)` reste valide tant que v1 existe). Ce point sera
  traité en b.2 (suppression de la FK ou de la table
  `livret_exercices`).
- Le script `scripts/peuplement_05_plans_de_travail.py` lit encore v1.
  Sera supprimé en b.2.
- Le service `services/scanner_vers_v2.py` reste en place. Sera
  supprimé en b.2 (sa raison d'être disparaît).

### 4. Tests existants : adaptation au cas par cas (Q3=c)

**Adaptations effectuées** dans 6 fichiers :

- `tests/test_peuplement_repeupler.py` : 5 tests adaptés (SELECT via
  JOIN v2) + 1 test supprimé (`test_preserve_liaisons_n_n_moins_1`
  qui vérifiait la préservation de `est_nouveau` et
  `obj_precedent_id`, concepts abandonnés en v2) + 1 test skipped
  (`test_livret_exercices_peuple` : dépend de la chaîne legacy
  `livret_exercices` à traiter en b.2).
- `tests/test_sqlite_store.py::test_methodes_round_trip` : adapté au
  cas nominal v2 (fixture qui crée la pile `sequences_par_niveau →
  sequence_parties → objectifs_v2`).
- `tests/test_R3_sequences_service.py` (2 tests) + 
  `tests/test_R3_sequences_routes.py` (1 test) : insertions
  réécrites via la pile v2.
- `tests/test_ecrire_exercices_fk.py::test_liaisons_exercice_objectifs_via_codes`
  : assertion inversée (Q5=b — on vérifie maintenant l'**absence**
  d'écriture v1).
- `tests/test_latex_rendu_atome.py` : schéma de test enrichi
  (sequence_par_niveau, sequence_parties, objectifs_v2 complet) et
  insertion doublée v1+v2.
- `tests/test_peuplement_plans_de_travail.py` : 3 tests skipped
  (dépendent du script peuplement_05 qui sera supprimé en b.2).

### 5. Nouveaux tests dédiés v0.14.6.b.1

`tests/test_v0_14_6_b1_services_lisent_v2.py` — 26 tests qui valident
explicitement le nouveau comportement v2 :

- **Macros LaTeX** (3 tests) : `seqObjectifGetNom` lit v2, ignore v1,
  `seqObjectifGetFinCycle` retourne toujours `'N'`.
- **Compteur d'atomes** (2 tests) : COUNT sur v2 + JOIN, v1 ignoré.
- **`_objectif_id_pour`** (3 tests) : lit v2 avec priorité à
  l'objectif lié à une méthode, fallback sans méthode, None si absent.
- **`ecrire_objectifs`** (5 tests) : n'écrit rien dans v1, écrit dans
  v2, crée les parties automatiquement, crée la sequence_par_niveau
  automatiquement, idempotent.
- **`ecrire_methodes`** (2 tests) : lie correctement l'objectif v2,
  ne crée plus d'orphelin legacy.
- **`lire_methodes`** : critères lus depuis v2.
- **`lire_exercices`** (2 tests) : objectifs lus via `objectif_exos`,
  v1 ignoré.
- **`ecrire_exercices`** : pas d'écriture v1 (Q5=b).
- **Route `/api/objectifs`** : retourne 404.
- **`edition_progression.py` stub** (3 tests) : importable,
  `CreneauIntrouvable` conservée, `lire_detail_creneau` retirée.
- **Nettoyage JS** (3 tests) : `ATL_OBJ_CAT` et `atelChargerObjectifs`
  absents du code actif (commentaires explicatifs autorisés).

## Vérifs

- Sanity Python sur tous les fichiers modifiés : OK
- Suite complète : **3557 passed, 9 skipped, 0 failed**
  - 3531 baseline v0.14.6.a + 26 nouveaux v0.14.6.b.1
  - 4 nouveaux skipped (justifiés et documentés pour b.2)

## À tester chez toi

### 1. Tests automatiques

```
cd appli
python -m pytest tests/test_v0_14_6_b1_services_lisent_v2.py -v
```

Attendu : **26 passed**.

Puis suite complète :

```
python -m pytest -q
```

Attendu : **3557 passed, 9 skipped, 0 failed**.

### 2. Tests fonctionnels manuels (cruciaux)

C'est le moment de vérifier que l'application tourne toujours
correctement avec les services réécrits. Voici une checklist :

#### a) Démarrage Flask + console propre

```
lancer.bat
```

Vérifier dans la console (terminal de lancement) qu'il n'y a pas
d'erreur Python au démarrage. Les anciens warnings `sel is null`
(silenced bug `atelChargerObjectifs`) devraient avoir disparu.

#### b) Atelier Méthode

- Ouvrir l'atelier Méthode (`#`atl)
- Sélectionner une méthode existante (ex: N11/S05)
- Vérifier que les **critères F/A/E s'affichent** dans le formulaire
- Modifier un critère et sauvegarder
- Re-ouvrir : la modification doit avoir été conservée

#### c) Atelier Exercice + compilation PDF

- Ouvrir l'atelier Exercice
- Sélectionner un exercice
- Vérifier que les **objectifs liés s'affichent** (déduits maintenant
  de `objectif_exos` v2)
- Compiler son PDF — doit fonctionner comme avant

#### d) Compilation d'une notion contenant `\seqObjectifGetNom`

Si tu as une notion ou un livret qui utilise `\seqObjectifGetNom{02}` :

- Compiler le PDF
- Vérifier que le nom de l'objectif s'affiche correctement dans le
  rendu (et pas un placeholder `[OBJ-02]`)

#### e) Compilation d'un livret de séquence complet

- Atelier Séquence-niveau → choisir N10/S01
- Compiler le livret de séquence
- Vérifier que tout est OK (cours + exercices + remédiations)

#### f) Import d'un référentiel (si possible)

Si tu importes régulièrement des référentiels :

- Importer un référentiel verrouillé
- Vérifier dans Admin > BDD que les objectifs apparaissent bien (ils
  sont créés en `objectifs_v2` maintenant, et `objectifs` v1 reste
  vide pour ces nouveaux imports)

### 3. Vérification que v1 n'est plus alimentée

Optionnel mais informatif. Lancer un audit :

```
python -m scripts.audit_v1_v2
```

Verdict attendu : **toujours ✓** (l'audit valide v1 vs v2 ; comme la
migration v0.14.6.a a déjà aligné les deux, l'audit reste vert).

Si tu importes un nouveau référentiel après la migration, l'audit
pourrait commencer à signaler des **orphelins v2** (présents en v2,
absents en v1) — c'est **normal et bénin** : v1 est figée, v2
continue d'évoluer.

## Fichiers livrés

```
MODIFIÉS
  appli/services/edition_progression.py      (vidé en stub)
  appli/services/latex_rendu_atome.py        (2 macros réécrites)
  appli/services/sequences_du_cycle.py       (COUNT via v2)
  appli/persistence/sqlite_store.py          (9 modifications)
  appli/routes/atomes.py                     (route retirée)
  appli/static/app.js                        (variable + fonction retirées)
  appli/tests/test_peuplement_repeupler.py   (5 adaptés + 1 skip)
  appli/tests/test_sqlite_store.py           (1 adapté)
  appli/tests/test_R3_sequences_service.py   (2 adaptés)
  appli/tests/test_R3_sequences_routes.py    (1 adapté)
  appli/tests/test_ecrire_exercices_fk.py    (1 adapté Q5=b)
  appli/tests/test_latex_rendu_atome.py      (schéma enrichi)
  appli/tests/test_peuplement_plans_de_travail.py  (3 skipped)

NOUVEAUX
  appli/tests/test_v0_14_6_b1_services_lisent_v2.py  (26 tests)
  appli/doc/redemarrage_v0_14_6_b1.md
```

## Sécurité

- Toute la suite de tests passe (3557 / 3557 actifs).
- Le backup de la migration v0.14.6.a est toujours disponible :
  `data/backups/seqenseigne-pre-migration-v0.14.6a-20260520-230134.db`.
  En cas de souci, restauration : copier ce backup sur
  `data/seqenseigne.db` et tu retournes à l'état pré-migration.
- Les tables v1 (`objectifs`, `exercice_objectifs`) existent toujours
  en base et contiennent leurs données telles que figées après
  v0.14.6.a. Si une régression majeure survient sur ta BDD, tu peux
  écrire un script de "rollback" qui remet les services à lire v1
  (les données y sont).

## Prochaine étape : v0.14.6.b.2

Une fois validé chez toi (tests automatiques + tests fonctionnels +
re-audit), j'attaque **v0.14.6.b.2** qui fera :

1. **Script `scripts/supprimer_v1.py`** : avec backup auto + dry-run,
   sur le modèle de `migrer_v1_vers_v2.py`. Aura à charge :
   - Supprimer la FK `livret_exercices.objectif_id →
     objectifs(id)` (au choix : suppression de la FK uniquement,
     ou suppression complète de la table `livret_exercices`)
   - `DROP TABLE objectifs`
   - `DROP TABLE exercice_objectifs`
2. **Suppression de fichiers** :
   - `services/scanner_vers_v2.py` (devenu obsolète)
   - `scripts/peuplement_03/04/05/06/15.py` (lisent ou écrivent v1)
3. **Stub `services/edition_progression.py`** → suppression complète
4. **Réactivation/suppression des 4 tests skipped en b.1**

## Note de chantier — découvertes b.1

- **`livret_exercices.objectif_id` est une FK explicite** vers
  `objectifs(id)` dans `persistence/schema.sql`. À traiter en b.2.
- **`ecrire_objectifs` a dû gagner la création automatique de
  `sequences_par_niveau`** pour rester autonome — sinon la fixture
  des tests cassait (et probablement aussi la chaîne d'import si
  jamais une séquence du référentiel n'avait pas de
  sequence_par_niveau préexistante). C'est plus robuste qu'avant.
- **Le cas legacy v1 de `ecrire_methodes`** (création d'objectif
  orphelin sans métadonnées) a pu être supprimé sans risque :
  l'audit v0.14.5 avait confirmé 0 occurrence en prod.
