# Redémarrage v0.14.1 — Renommage `exo` → `exercice`

## Contexte global : workstream « Unification rendu PDF »

Le rendu PDF a été développé indépendamment sur 5 ateliers, avec des
conventions divergentes :

| | Exercice | Notion | Méthode | Fiche | Carte |
|---|---|---|---|---|---|
| Préfixe DOM | `atl-exo` (sauf 1 ID) | `atl-notion` | `atl-methode` | `atl-fiche` | `atl-carte` |
| HTML de la zone Rendu | `<div>` vide, créé dynamiquement | `<div>` vide | `<div>` vide | `<div>` vide | HTML statique complet |
| Code JS rendu | `rendu_atome.js` (fonctions globales) | idem | idem | idem | `AtelierAtomique.compilerRendu()` |
| Route backend | `/api/atomes/exercice/<id>/rendu-pdf` | `/api/atomes/notion/...` | `/api/atomes/methode/...` | `/api/atomes/fiche/...` | `/api/cartes/<id>/rendu-pdf` |
| Endpoint `/info` | ✗ | ✗ | ✗ | ✗ | ✓ |
| Auto-chargement si cache valide | ✗ | ✗ | ✗ | ✗ | ✓ (depuis v0.13.7.6.1) |
| Spinner visuel pendant compilation | ✓ (rendu-spinner) | ✓ | ✓ | ✓ | ✗ (texte seul) |
| Race condition fix | ✗ | ✗ | ✗ | ✗ | ✓ (depuis v0.13.7.6.1.1.2) |

L'objectif du workstream est l'**unification complète**. Plan en 4
livraisons (v0.14.1 à v0.14.4) :

1. **v0.14.1** (cette livraison) : Renommer `exo` → `exercice`
   partout pour aligner Exercice sur les autres
2. **v0.14.2** : Backend — route `/info` générique pour les 4 ateliers
   manquants, unifier carte sous `/api/atomes/carte/<id>/...`
3. **v0.14.3** : HTML — bloc rendu standardisé pour les 4 ateliers
4. **v0.14.4** : Client — descendre tout le rendu PDF dans
   `AtelierEditeur`, supprimer `AtelierAtomique` et `rendu_atome.js`,
   ajouter spinner

## Cadrage validé pour v0.14.1

| Question | Réponse |
|---|---|
| Niveau d'unification global | Maximum, quitte à découper en plusieurs livraisons |
| Pour l'incohérence Exercice | Renommer `exo` → `exercice` partout |
| Pour `rendu_atome.js` | Suppression complète (en v0.14.4) |
| Pour `AtelierAtomique` | Suppression complète (en v0.14.4) |
| Ordre des livraisons | Backend avant HTML (le client peut survivre avec /api/cartes/...) |
| Versioning | Saut à v0.14 pour marquer la rupture cleanup |

## Stratégie de renommage

Trois patterns à remplacer avec des bornes strictes pour éviter les
faux positifs :

1. `atl-exo` suivi d'un tiret (= début d'ID DOM) → `atl-exercice`
2. `ATL_EXO_` (préfixe de constante globale) → `ATL_EXERCICE_`
3. `atelExo` suivi d'une majuscule (= fonction camelCase) → `atelExercice`

**NE PAS remplacer** :
- Le mot `exos` (pluriel) — concepts métier (recap_exos, etc.)
- `'exercice'` comme type-string (déjà cohérent)
- `AtelierExercice` comme nom de classe (inchangé)
- `ATELIER_EXERCICE` comme variable globale (inchangé, suit la
  convention partagée)

## Fichiers concernés

207 occurrences sur 8 fichiers, identifiés via `grep` :

| Fichier | Avant | Après | Notes |
|---|---|---|---|
| templates/index.html | 40 | 0 | IDs DOM, onclick handlers |
| static/app.js | 112 | 0 | gros fichier historique |
| static/atelier.js | 1 | 0 | exemple dans docstring |
| static/atelier_commun.js | 4 | 0 | sélecteurs CSS |
| static/atelier_editeur.js | 1 | 0 | doc d'un slot |
| static/atelier_etat_edition.js | 3 | 0 | hooks d'état |
| static/atelier_exercice.js | 37 | 0 | la classe Exercice elle-même |
| static/rendu_atome.js | 2 | 0 | référence à atelExoSauvegarder |
| tests/test_v0_13_7_6_ui.py | 7 | 0 | les tests vérifient les nouveaux IDs |

## Tests ajoutés

`tests/test_v0_14_1_renommage_exo_exercice.py` — 18 tests :
- **TestAnciensPatternsAbsents** : vérifie qu'aucun pattern ancien ne
  subsiste (test paramétré sur les 8 fichiers + 3 tests dédiés)
- **TestNouveauxPatternsPresents** : vérifie que les nouveaux patterns
  remplacent bien les anciens (count, ID-clés, déclaration de classe)
- **TestTypesMetierIntacts** : vérifie qu'on n'a pas renommé par
  erreur le type-string `'exercice'` ni créé des doublons
  (`atl-exerciceexercice` par exemple)

## Vérifs

- pytest : **3378 passed, 5 skipped, 0 failed** (3360 baseline + 18
  nouveaux, aucune régression sur les 3360 tests existants)
- `node --check` sur les 7 JS modifiés : OK

## À tester chez toi

### A — Atelier Exercice fonctionne (test critique)

1. Ouvrir l'atelier Exercice, choisir un exercice existant.
2. **Vérifier** : la liste s'affiche, l'item se charge, le formulaire
   se remplit.
3. **Tester** :
   - Saisir une petite modification (titre)
   - Cliquer Enregistrer → toast de succès
   - Onglet Rendu PDF → compile et affiche le PDF
   - Cliquer Variables (header repliable) → s'ouvre/se ferme
   - Cliquer ✎ Éditer dans Variables → ouvre l'éditeur LaTeX
4. **Tester création** :
   - Bouton + (Nouvel exercice)
   - Choisir une série (modale)
   - Saisir titre, énoncé, corrigé
   - Enregistrer → l'item apparaît dans la liste

### B — Aucune régression sur les 4 autres ateliers

1. Tester rapidement Notion, Méthode, Fiche, Carte :
   - Ouvrir la liste
   - Cliquer un item
   - Le formulaire se remplit ?
   - L'onglet Rendu PDF fonctionne ?
2. Pour Carte spécifiquement, vérifier que l'auto-chargement marche
   toujours (cf. v0.13.7.6.1.1.2 — race condition).

### C — Tests automatisés

```
cd appli
python -m pytest tests/ -q
```

Attendu : 3378 passed, 5 skipped, 0 failed.

## Prochaine étape : v0.14.2

Backend — ajouter l'endpoint `/info` pour les 4 ateliers manquants
(`/api/atomes/<type>/<id>/rendu-pdf/info`) et créer la nouvelle route
unifiée pour la carte (`/api/atomes/carte/<id>/...`).

La carte continue à fonctionner via `/api/cartes/<id>/...` qui reste
en alias temporaire — sera supprimée en v0.14.4 quand le client aura
basculé sur la nouvelle URL.
