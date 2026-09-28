# seqenseigne v0.6.1 — L'UI consomme le bon référentiel

Livraison qui rend visibles les référentiels versionnés de la v0.6.0.
Désormais, chaque classe affiche les objectifs **de son référentiel**,
pas ceux du YAML courant. **Le cas Romane est résolu** : les notes saisies
à l'époque pour les objectifs `05` et `06` de la 4e6 en 2021-2022 se
réaffichent correctement au lieu d'être perdues parce que l'UI cherchait
`12` et `13` (codes actuels).

## Cycle de vie des référentiels

Introduction de l'état `etat` (remplace `verrouille` 0/1), avec trois
valeurs :

| État | Ateliers (édition future) | Suivi de classe | Transitions |
|---|---|---|---|
| `en_cours` | ✅ modifiable | ❌ | → `valide` (manuel, en v0.6.2) |
| `valide` | ✅ modifiable | ✅ | → `verrouille` (auto, 1re évaluation) |
| `verrouille` | ❌ immuable | ✅ | → `valide` (déverrouillage manuel, v0.6.2) |

**Bascule auto implémentée** (cette livraison) : dès qu'un niveau est
saisi via `/api/niveaux/set` ou calculé via `/api/niveaux/calculer`
pour une classe, son référentiel bascule automatiquement en
`verrouille` (idempotent).

**Les référentiels créés par l'import** sont directement en état
`verrouille` (ils ont déjà servi à évaluer).

Ce qui **n'est pas encore fait** (v0.6.2) : l'écran de gestion des
référentiels, la validation manuelle avec récapitulatif, la duplication,
le déverrouillage avec confirmation.

## Nouveau endpoint

`GET /api/classes/<cid>/sequences` — retourne
`{ source, referentiel_id, sequences }`. Stratégie :

1. Charge la classe et sa progression.
2. Si la progression a un `referentiel_id` → lit depuis les tables
   `referentiel_*` via `build_sequences_from_referentiel`.
3. Sinon → fallback sur `build_sequences` (YAML courant du niveau), pour
   les cas legacy ou progressions créées manuellement.

Le format de sortie des séquences est identique à celui de
`/api/sequences?niveau=...`, pour ne rien casser côté UI.

## Côté UI

`loadSuiviNiveaux()` dans `static/app.js` utilise le nouvel endpoint
pour charger `SEQ`. Les autres appels à `/api/sequences?niveau=...`
(atelier Livret, etc.) restent inchangés — ils n'ont pas de contexte
classe, donc continuent de lire le YAML.

Deux variables globales ajoutées :
- `SEQ_SOURCE` — `'referentiel'` ou `'yaml'`
- `SEQ_REFERENTIEL` — l'id du référentiel utilisé (ou `null`)

Elles ne sont pas encore affichées dans l'UI, mais seront utiles pour
les évolutions futures (badge, tooltip).

## Schéma SQLite

**Changement de schéma** : la colonne `verrouille` de
`referentiel_niveaux` est remplacée par `etat TEXT NOT NULL DEFAULT
'en_cours' CHECK (etat IN ('en_cours', 'valide', 'verrouille'))`.

**Pas de migration automatique** : il faut effacer la base et
réimporter. Tu t'y attendais (tu l'as déjà fait plusieurs fois).

## API Python (store)

Nouvelle méthode : `changer_etat_referentiel(ref_id, etat)` pour les
transitions arbitraires (utilisée par l'écran de gestion à venir).

`verrouiller_referentiel(ref_id)` devient **idempotent** : no-op si
déjà verrouillé.

`creer_referentiel` accepte `etat` (défaut `en_cours`) et conserve une
compat avec la clé `verrouille=True` des appels v0.6.0.

`lire_referentiel` et `lister_referentiels` retournent toujours
`verrouille` (booléen dérivé de `etat == 'verrouille'`) pour simplifier
le code appelant, en plus de `etat` (chaîne exacte).

## Tests

**320 tests verts** (314 v0.6.0b + 6 nouveaux).

Les 6 nouveaux couvrent :
- Route qui retourne depuis le référentiel (vérifie notamment que les
  **codes d'objectifs d'époque** `05`, `06` sont préservés, pas remappés).
- Fallback YAML si pas de référentiel.
- 404 sur classe inconnue.
- Bascule auto `valide → verrouille` lors de la saisie.
- Idempotence si déjà verrouillé.
- Robustesse : classe sans référentiel = pas d'erreur.

Plus 4 tests de transitions d'état (déjà dans v0.6.1, ajoutés
incrémentalement pendant le développement).

## Fichiers modifiés par rapport à v0.6.0b

```
appli/persistence/schema.sql               ← colonne etat au lieu de verrouille
appli/persistence/sqlite_store.py          ← méthodes etat, verrouiller_referentiel idempotent
appli/importers/referentiel_builder.py     ← etat='verrouille' pour les imports
appli/services/sequences.py                ← nouvelle fonction build_sequences_from_referentiel
appli/routes/classes.py                    ← nouvel endpoint /api/classes/<cid>/sequences
appli/routes/suivi.py                      ← bascule auto valide→verrouille
appli/static/app.js                        ← loadSuiviNiveaux utilise le nouvel endpoint
appli/tests/test_referentiels.py           ← 4 tests sur les transitions d'état
appli/tests/test_sqlite_store.py           ← (inchangé depuis v0.6.0b, inclus pour cohérence)
appli/tests/test_sequences_par_classe.py   ← NOUVEAU, 6 tests v0.6.1
```

## Déploiement

1. Dézipper l'archive à la racine de `D:\Enseignement\seqenseigne\`.
2. Effacer la base (changement de schéma) :
   ```
   del data\seqenseigne.db
   ```
3. Réimporter :
   ```
   python importer_arborescence.py --racine D:\Enseignement_old
   ```
4. Ouvrir l'appli et tester :
   - Sélectionner la 4e6 de 2021-2022.
   - Aller à la séquence S03.
   - **Vérifier que Romane Chailloux a bien ses niveaux E/A sur les
     objectifs 05 et 06** (et non plus des I à tort).
   - Sélectionner la 4e3 de 2024-2025 pour la même séquence — les
     objectifs affichés seront cette fois 01-04, 11-13 (codes actuels),
     avec les niveaux saisis.

## Petite subtilité

La couleur/état des référentiels dans l'écran Admin n'a pas encore
été mise à jour : tu verras toujours les icônes 🔒 pour les verrouillés
mais pas de distinction `en_cours` / `valide`. Ce sera corrigé en
v0.6.2 avec l'écran de gestion des référentiels.
