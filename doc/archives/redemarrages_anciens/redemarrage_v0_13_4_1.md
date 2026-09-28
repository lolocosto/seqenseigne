# Redémarrage v0.13.4.1 — Bug fix sélection déterministe des référentiels

## Périmètre

Pré-livraison standalone avant la série v0.13.5. Corrige un bug latent
dans la résolution des macros LaTeX qui s'appuient sur les tables
`referentiel_*`, et nettoie l'incohérence des données de production.

**Frontend** : aucun changement. **Paquet LaTeX** : aucun changement.

## Procédure de déploiement

1. Décompresser le ZIP `seqenseigne-v0.13.4.1.zip` à la racine de
   `appli/`.
2. **Important : exécuter le script de migration des données AVANT le
   premier rendu d'atome** :
   ```
   python scripts/migration_v0_13_4_1_dates_fin.py            # dry-run
   python scripts/migration_v0_13_4_1_dates_fin.py --apply    # appliquer
   ```
   La migration demande une confirmation interactive (`OUI`). Elle est
   **idempotente** : on peut la relancer sans risque.
3. Aucune action navigateur (pas de fichier statique modifié).

## Fichiers modifiés / ajoutés

| Fichier | Nature |
|---------|--------|
| `services/latex_rendu_atome.py` | Modifié — 5 requêtes patchées avec tri déterministe |
| `scripts/migration_v0_13_4_1_dates_fin.py` | Ajouté — script de migration de données |
| `tests/test_latex_rendu_atome.py` | Modifié — ajout classe `TestRefSelectionDeterministe` (8 tests) |
| `tests/test_migration_v0_13_4_1.py` | Ajouté — tests du script de migration (11 tests) |

## Le bug corrigé

Dans `services/latex_rendu_atome.py`, 5 requêtes utilisaient le filtre
`WHERE rn.date_fin IS NULL` pour sélectionner "le référentiel courant"
d'un niveau. Comme tous les référentiels en BDD ont historiquement
`date_fin = NULL`, le `LIMIT 1` sans `ORDER BY` retournait un
référentiel arbitraire (choix SQLite, non déterministe).

Aujourd'hui ça marchait par chance — les noms des séquences sont
identiques entre millésimes — mais c'était un bug latent qui aurait
explosé dès qu'un nom changerait.

## Approche en 2 temps

### Temps 1 : Migration des données (ponctuelle)

Le script `migration_v0_13_4_1_dates_fin.py` pose `date_fin` sur les
référentiels obsolètes pour rétablir la cohérence : un seul référentiel
par niveau garde `date_fin = NULL` (le plus récent).

**Règle** : la `date_fin` cible est le **1er septembre de la version du
référentiel suivant** de même niveau. Reflète "remplacé à la rentrée
suivante".

**État final attendu** dans la BDD de Laurent :

| Référentiel | Action | date_fin |
|-------------|--------|----------|
| N10_v2021 | modifié | 2022-09-01 |
| N10_v2022 | modifié | 2023-09-01 |
| N10_v2023 | modifié | 2024-09-01 |
| **N10_v2024** | inchangé | NULL |
| N11_v2021 | modifié | 2023-09-01 |
| N11_v2023 | modifié | 2024-09-01 |
| N11_v2024 | modifié | 2025-09-01 |
| **N11_v2025** | inchangé | NULL |
| N12_v2022 | modifié | 2024-09-01 |
| **N12_v2024** | inchangé | NULL |

### Temps 2 : Bug fix code (durable)

Les 5 requêtes utilisent désormais une clause `ORDER BY` déterministe
factorisée en constante `_REF_ORDER_BY` :

```sql
ORDER BY
  CASE rn.etat WHEN 'verrouille' THEN 0
               WHEN 'fige'       THEN 1
               WHEN 'valide'     THEN 2
               WHEN 'en_cours'   THEN 3
               ELSE 4 END,
  rn.version DESC
```

Préférence par état : `verrouille` (en usage actif suivi) > `fige`
(compilé) > `valide` (auto, attend figeage) > `en_cours` (construction)
> autres. Puis version décroissante.

**Note** : `fige` est inclus en anticipation de la v0.13.5.1 qui
l'ajoutera au CHECK constraint. Pas de risque ici, c'est un simple
`CASE WHEN` SQL indépendant du CHECK.

**Défense en profondeur** : la migration de données et le tri
fonctionnent ensemble mais aussi indépendamment. Si la BDD redevient
incohérente plus tard (par ex. plusieurs référentiels avec
`date_fin = NULL`), le tri continue de donner un résultat déterministe.

## Tests

- Avant : 1981 passed + 5 skipped (baseline v0.13.4)
- Après : **2000 passed + 5 skipped** — 19 nouveaux tests, aucune
  régression.

Nouveaux tests :
- `TestRefSelectionDeterministe` (8 tests) : vérifie que le tri donne
  le bon résultat dans tous les cas (préférence d'état, version, mix
  des deux, cas réaliste post-migration, niveau absent).
- `tests/test_migration_v0_13_4_1.py` (11 tests) : vérifie le calcul
  des modifications, l'idempotence, le cas réaliste de la base de
  Laurent.

## Migration en cas de re-déploiement

Le script est idempotent. Si tu redéploies une base "fraîche" (par
exemple en restaurant une sauvegarde), il suffit de relancer le
script — les référentiels déjà migrés ne sont pas touchés, seuls les
nouveaux candidats sont mis à jour.

## Suite

La série **v0.13.5** est prête à démarrer (cf.
`doc/scoping_v0_13_5_referentiels.md`). Première sous-version :
v0.13.5.1 (schéma + service de snapshot + UI minimale).
