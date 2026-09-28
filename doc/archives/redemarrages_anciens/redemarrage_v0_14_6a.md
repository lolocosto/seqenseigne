# Redémarrage v0.14.6.a — Migration v1 → v2 des objectifs

## Position dans le chantier de suppression v1

| Étape | Statut |
|---|---|
| **v0.14.5** : Audit lecture seule | ✓ Déployé chez Laurent (sortie reçue) |
| **v0.14.6.a** : Script de migration v1 → v2 (cette livraison) | ⏳ |
| **v0.14.6.b** : Réécriture services + DROP TABLE | Après validation 6.a |
| **v0.14.7** : Renommage `objectifs_v2` → `objectifs` | Après v0.14.6.b |

## Diagnostic de l'audit (v0.14.5)

Sortie sur la BDD de production :

| Catégorie | Compte | Verdict |
|---|---|---|
| Concordants stricts | 57 | ✓ |
| Orphelins v1 (pas en v2) | **32** | À créer en v2 |
| Divergences `methode_id` | **156** | v1 a la valeur, v2 = NULL |
| Divergences `critere_F` | **99** | v1 a un texte, v2 vide |
| Divergences `critere_A` | **153** | idem |
| Divergences `critere_E` | **154** | idem |
| Liaisons v1 sans pendant v2 | **2** | À créer dans `objectif_exos` |
| `est_nouveau`, `obj_precedent_id` perdus | **0** | (de toute façon abandonnés en v2) |

**Conclusion** : la v2 a la structure mais le contenu pédagogique est
en v1. **Décision (Q1)** : v1 source de vérité, on copie v1 → v2 en
écrasant.

## Cadrage validé pour v0.14.6.a

| Question | Réponse |
|---|---|
| Q1 — Source de vérité | (a) v1 systématiquement, on écrase v2 |
| Q2 — Sur les 32 orphelins | (a) Migration normale (ils sont valides) |
| Q3 — Stratégie backup | (a) Backup auto dans `data/backups/` avec timestamp |
| Q4 — Ordre de livraison | (a) v0.14.6.a (migration) puis v0.14.6.b (suppression) |

## Ce que fait le script

`scripts/migrer_v1_vers_v2.py` — environ 700 lignes.

### Algorithme

**Pour chaque clé `(niveau, sequence, code)` de v1** :

- **Présente en v2** : UPDATE des champs `methode_id`, `nom`,
  `critere_F/A/E` avec les valeurs v1 (overwrite). Les champs déjà
  identiques ne sont pas touchés (compteur « inchangés »).

- **Absente en v2** : INSERT en v2.
  - La partie de rattachement est déterminée par le premier chiffre
    du code (convention canonique documentée dans
    `services/scanner_vers_v2.py`) :
    - code `01..09` → partie 1
    - code `11..19` → partie 2
    - code `21..29` → partie 3
    - etc.
  - Si la partie n'existe pas dans `sequence_parties`, elle est créée
    avec un nouvel id (`pt_xxxxxx`).
  - L'objectif est créé avec un nouvel id (`ob_xxxxxx`).

**Pour chaque liaison `exercice_objectifs` (v1) sans pendant v2** :

- Mapper `objectif_id_v1` → `objectif_id_v2` via la clé
  `(niveau, sequence, code)` (en utilisant la map v2 reconstituée
  APRÈS la création des orphelins, pour que les nouvelles liaisons
  puissent pointer vers les objectifs fraîchement créés).
- Lire `serie` depuis la table `exercices`.
- Calculer `num = max(num existants) + 1` pour cette `(objectif_id_v2, serie)`.
- INSERT dans `objectif_exos`.

### Sécurités

1. **Dry-run par défaut**. Le script ne modifie rien tant qu'on ne
   passe pas `--ecrire`.
2. **Backup automatique** avant écriture, dans
   `data/backups/seqenseigne-pre-migration-v0.14.6a-YYYYMMDD-HHMMSS.db`.
   La base initiale reste intouchée à cet emplacement.
3. **Transaction unique** : `BEGIN TRANSACTION` → … → `COMMIT`. Si
   erreur SQL, `ROLLBACK` automatique et la base reste intacte (le
   backup est de toute façon disponible en filet de sécurité).
4. **Idempotent** : relancer le script sur une base déjà migrée est
   un no-op (testé).
5. **Erreur explicite** sur les codes non-standards (alphanumériques,
   à 1 ou 3+ chiffres). La migration est bloquée tant que ces cas ne
   sont pas résolus à la main. Sur ta BDD, **aucun code non-standard
   n'a été détecté à l'audit** — ce filet de sécurité ne devrait
   donc pas se déclencher.

### Codes de sortie

- `0` : Migration réussie (ou no-op en dry-run).
- `1` : Erreurs critiques détectées (codes non-standards, séquences
  introuvables). La migration est bloquée.
- `2` : Base introuvable.
- `3` : Erreur SQL pendant l'écriture (ROLLBACK effectué).

## Usage prévu

### Étape 1 — Dry-run d'abord

```
cd appli
python -m scripts.migrer_v1_vers_v2
```

Affiche le plan détaillé sans rien modifier. **Sortie attendue sur
ta BDD** :

```
v1 (objectifs)   : 245 entrées
v2 (objectifs_v2): 213 entrées

──────────────────────────────────────────────────────────────────────
  Objectifs à CRÉER en v2 — 32
──────────────────────────────────────────────────────────────────────
  + ('N10', 'S14', '03')  partie=1 (partie existe)  nom='Mettre en ordre…'
  + ('N10', 'S10', '05')  partie=1 (partie existe)  nom='Calculer l'aire…'
  …

──────────────────────────────────────────────────────────────────────
  Objectifs v2 à METTRE À JOUR — 156
──────────────────────────────────────────────────────────────────────
  Synthèse par champ :
    methode_id: 156 mises à jour
    critere_A:  153 mises à jour
    critere_E:  154 mises à jour
    critere_F:   99 mises à jour
  …

──────────────────────────────────────────────────────────────────────
  Liaisons exercice→objectif à créer en v2 — 2
──────────────────────────────────────────────────────────────────────
  …

──────────────────────────────────────────────────────────────────────
  DRY-RUN — aucune écriture effectuée
──────────────────────────────────────────────────────────────────────
```

### Étape 2 — Exécution

Si le plan te convient :

```
python -m scripts.migrer_v1_vers_v2 --ecrire
```

Sortie attendue :

```
Backup créé : data/backups/seqenseigne-pre-migration-v0.14.6a-20260520-XXXXXX.db
…
  ✓ 32 objectifs créés
  ✓ 156 objectifs mis à jour
  ✓ N parties créées
  ✓ 2 liaisons exercice→objectif créées

Tu peux relancer scripts/audit_v1_v2.py pour vérifier
que la base est maintenant prête pour la suppression v1.
```

### Étape 3 — Re-audit

```
python -m scripts.audit_v1_v2
```

**Doit donner verdict ✓ (exit 0)** :

```
──────────────────────────────────────────────────────────────────────
  VERDICT
──────────────────────────────────────────────────────────────────────
  ✓ Aucun obstacle détecté. La suppression de v1 peut se faire sans
    perte de données.
  ✓ Tu peux enchaîner sur v0.14.6 (réécriture services + DROP TABLE).
```

### En cas de souci

Si tu veux annuler la migration et revenir à l'état d'avant :

```
# Stopper l'application si elle tourne
# Puis remplacer la base par le backup
cp data/backups/seqenseigne-pre-migration-v0.14.6a-XXXXXXXX-XXXXXX.db data/seqenseigne.db
```

## Validation effectuée chez moi

Le script a été testé sur une BDD synthétique reproduisant ta
situation :

- 4 objectifs v1 (1 concordant, 1 divergent, 2 orphelins dont 1 avec
  partie inexistante)
- 2 liaisons `exercice_objectifs` (1 OK, 1 vers orphelin)

Résultat du `--ecrire` :

```
✓ 2 objectifs créés
✓ 1 objectifs mis à jour
✓ 2 parties créées
✓ 2 liaisons exercice→objectif créées
```

Re-audit immédiat : **verdict ✓, exit 0**. Le backup contient bien
la base d'avant.

## Fichiers livrés

```
NOUVEAUX
  appli/scripts/migrer_v1_vers_v2.py                    (~700 lignes)
  appli/tests/test_v0_14_6a_migration_v1_vers_v2.py     (19 tests)
  appli/doc/redemarrage_v0_14_6a.md                     (ce document)
```

## Vérifs

- 19 tests pytest dédiés au script :
  - Présence/syntaxe/help du script
  - **Dry-run ne modifie rien** (snapshot avant/après identique)
  - **Mode --ecrire applique** : création d'orphelin, update de
    divergent, création de partie, migration de liaison, série
    correcte
  - **Backup créé et intact** (contient bien l'état d'avant)
  - **Gestion d'erreur** : code non-standard bloque l'écriture
    (exit 1, base inchangée), DB introuvable (exit 2)
  - **Idempotence** : 2ème run sur base déjà migrée = no-op
  - **Intégration avec audit** : après migration, l'audit donne ✓
  - **Transaction atomique** : présence de BEGIN/COMMIT/ROLLBACK
- Suite complète : **3536 passed, 5 skipped, 0 failed**
  (3517 baseline v0.14.5 + 19 nouveaux v0.14.6.a)

## À tester chez toi

### 1. Tests automatiques

```
cd appli
python -m pytest tests/test_v0_14_6a_migration_v1_vers_v2.py -v
```

Attendu : 19 passed.

### 2. Dry-run sur ta vraie BDD

```
cd appli
python -m scripts.migrer_v1_vers_v2
```

**M'envoyer la sortie complète** (le plan détaillé). Sur cette base :
- Je vérifie que les 32 créations, 156 mises à jour, 2 liaisons
  attendues sont bien planifiées
- Je vérifie qu'il n'y a pas d'erreur critique imprévue (ex. séquence
  introuvable pour un orphelin)
- Si tout est cohérent, tu peux passer à l'étape 3

### 3. Exécution réelle

```
python -m scripts.migrer_v1_vers_v2 --ecrire
```

Et **m'envoyer la sortie** (avec le rapport final qui dit combien créés/
mis à jour). Tu peux aussi me confirmer que :
- Un fichier de backup est bien apparu dans `data/backups/`
- Sa taille est cohérente avec celle de ton `seqenseigne.db`

### 4. Re-audit pour confirmer

```
python -m scripts.audit_v1_v2
```

Doit afficher « ✓ Aucun obstacle détecté » et retourner exit 0.

### 5. Tests fonctionnels (optionnel mais conseillé)

Avant de m'envoyer le go pour v0.14.6.b, vérifier rapidement que
l'application tourne toujours bien :
- Ouvrir Atelier Méthode, vérifier que les méthodes existent toujours
- Ouvrir un atome (exercice ou notion) et compiler son PDF
- Atelier Carte : ouvrir une carte avec cache, le PDF doit s'afficher
- Si tu as une fonctionnalité « plan de travail » ou « livret de
  séquence », vérifier qu'elle fonctionne aussi

La v1 est encore présente, donc rien ne devrait casser (le contenu
v2 est juste plus riche maintenant).

## Prochaine étape

Une fois que tu m'as confirmé :
- Re-audit donne ✓
- L'application fonctionne toujours

Je peux attaquer **v0.14.6.b** :

- Réécriture des 5 fichiers qui lisent v1 (`latex_rendu_atome.py`,
  `edition_progression.py`, `sequences_du_cycle.py`, `sqlite_store.py`,
  `scanner_vers_v2.py` à supprimer)
- Suppression de la route `/api/objectifs` et du JS `ATL_OBJ_CAT`
- Suppression de `services/edition_progression.py`
- `DROP TABLE objectifs` et `DROP TABLE exercice_objectifs`
- Suppression des scripts de peuplement v1 (03, 04, 05, 06, 15)
  devenus obsolètes
- Adaptation des tests qui simulaient v1

Et v0.14.7 sera le renommage cosmétique `objectifs_v2` → `objectifs`.
