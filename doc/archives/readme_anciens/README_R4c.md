# seqenseigne — R4c : Renommage `rang_*` → `partie_*`

Troisième sous-chantier de R4. Renomme les colonnes `creneaux.rang_debut`
et `creneaux.rang_fin` en `creneaux.partie_debut` et `creneaux.partie_fin`
pour aligner le vocabulaire de la progression annuelle sur le nouveau
modèle v2.

**Status** : 9 nouveaux tests, **715 verts au total**, 0 régression.

## Pourquoi ce renommage

Jusqu'ici, un créneau de la progression annuelle mentionnait des « rangs »
qui couvraient mécaniquement une tranche d'objectifs (rang 1 = 01-09,
rang 2 = 11-19, etc.). Avec le modèle v2 (R4a/R4b), chaque séquence est
explicitement découpée en **parties** via la table `sequence_parties`.
Le vocabulaire des créneaux est donc maintenant aligné : un créneau
couvre les parties `partie_debut` à `partie_fin`.

Note : le mot « rang » reste utilisé dans la documentation interne pour
décrire le **concept** sous-jacent (dizaines d'objectifs). Seuls les
**noms de colonnes et de clés** changent.

## Ce que fait R4c

1. **Renomme les colonnes** `creneaux.rang_debut` → `partie_debut` et
   `creneaux.rang_fin` → `partie_fin`, via `ALTER TABLE RENAME COLUMN`
2. **Renomme aussi l'index** `idx_creneaux_seq` qui portait sur `rang_debut`
3. **Met à jour** tous les usages dans le code Python et JavaScript
4. **Rétrocompat en entrée JSON** : les anciennes clés `rang_debut` /
   `rang_fin` restent acceptées dans les payloads API, pour ne pas
   casser si un navigateur a du JS en cache

## Rétrocompat

Pendant quelques jours après le déploiement, les deux conventions peuvent
coexister. Le backend accepte les deux formats en **entrée** (JSON POST
vers l'API, données JSON persistées) mais n'émet que le **nouveau format**
en sortie.

| Côté | Nouveau format | Ancien format |
|---|---|---|
| Colonnes SQL | `partie_debut`, `partie_fin` | ❌ Disparues |
| Payload POST (entrée) | ✅ Accepté | ✅ Accepté (rétrocompat) |
| Payload GET (sortie) | ✅ Émis | ❌ Jamais émis |
| JS : lecture | ✅ Prioritaire | ✅ Fallback via `??` |
| JS : écriture | ✅ Émis | ❌ Jamais émis |

## Fichiers livrés

| Fichier | Changement |
|---|---|
| `appli/persistence/schema.sql` | Colonnes `partie_debut`/`partie_fin`, commentaires adaptés, index renommé |
| `appli/persistence/sqlite_store.py` | Migration idempotente `rang_*` → `partie_*` via `ALTER TABLE RENAME COLUMN` + 4 usages renommés avec rétrocompat d'entrée |
| `appli/services/edition_progression.py` | 7 usages renommés |
| `appli/routes/progression.py` | 2 handlers avec rétrocompat d'entrée |
| `appli/importers/sequencesdb.py` | Import de progression en nouveau format |
| `appli/static/app.js` | Lecture avec `??` rétrocompat, écriture en nouveau format |
| `appli/tests/test_progression.py` | Tests mis à jour |
| `appli/tests/test_edition_progression_service.py` | idem |
| `appli/tests/test_sqlite_store.py` | idem |
| `appli/tests/test_edition_progression_schema.py` | idem |
| `appli/tests/test_edition_progression_routes.py` | idem |
| `appli/tests/test_R4c_renommage_rang_partie.py` | **Nouveau** — 9 tests de validation de la migration et de la rétrocompat |

## Déploiement

### 1. Extraire le ZIP dans `appli/`

Remplace les 6 fichiers applicatifs + 5 fichiers de tests, ajoute un nouveau
fichier de test.

### 2. Relancer Flask

Au démarrage, `SqliteStore._migrer_schema()` détecte automatiquement les
anciennes colonnes et les renomme. **Aucune commande manuelle à lancer.**

Si tu veux vérifier que la migration a bien eu lieu :

```powershell
..\outils\python\python.exe -c "import sqlite3; c=sqlite3.connect('data/seqenseigne.db'); cols=[r[1] for r in c.execute('PRAGMA table_info(creneaux)')]; print('Colonnes creneaux:', cols)"
```

Sortie attendue :
```
Colonnes creneaux: ['id', 'progression_id', 'seq_code', 'partie_debut', 'partie_fin', 'partie', 'periode', 'date_debut', 'date_fin', 'revisions', 'ordre', 'nb_seances_total', 'nb_seances_revisions', 'nb_seances_cours']
```

### 3. Vérifier

```powershell
..\outils\python\python.exe -m pytest tests -q
# Attendu : 691 verts chez toi (tu étais à 682 + 9 nouveaux)
```

Puis côté UI : ouvre Suivi de classe → Progression annuelle. Le
calendrier et l'ajout de créneau doivent fonctionner comme avant. Si
tu vois la console du navigateur avec Ctrl+Shift+I, il faut faire
**Ctrl+F5** pour recharger le JS (sinon cache).

## Points d'attention

### La migration est à sens unique

Une fois que tu as déployé R4c et redémarré Flask, les colonnes
`rang_debut` / `rang_fin` n'existent plus en base. Si tu devais revenir
en arrière, il faudrait ressusciter l'ancien schéma. En pratique : pas
un souci, SQLite sait faire `ALTER TABLE RENAME COLUMN` dans les deux
sens.

### Payloads API en cache navigateur

Si un onglet navigateur avait chargé l'ancien JS avant le déploiement,
ses requêtes POST avec `rang_debut`/`rang_fin` sont toujours acceptées
grâce à la rétrocompat d'entrée. Après `Ctrl+F5`, tout bascule en
nouveau format.

### Le mot « rang » reste dans les docstrings

La logique métier (rang 1 = objectifs 01-09) reste intacte et
pédagogiquement parlante. Seuls les **noms de colonnes et les clés JSON**
changent.

## Prochaine étape : R4d

Renommage UI « Livret » → « Séquence (par niveau) ». Encore un
renommage — cette fois dans les libellés affichés à l'enseignant et
dans les noms internes de l'atelier concerné.
