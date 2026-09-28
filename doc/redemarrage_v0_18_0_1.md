# Redémarrage v0.18.0.1 — Correctif : ReferenceError au chargement de app.js

## Symptôme

Dans le Rendu par lot, le clic sur « Aperçu (compter) » affichait
« Erreur : can't access lexical declaration 'COMPIL_PREVIEW_OK' before
initialization », quel que soit le filtre — alors que les compteurs (Total,
Cartes…) s'affichaient correctement.

Console du navigateur (1re erreur, la vraie cause) :
`Uncaught ReferenceError: ATL_ATOME_CONFIG is not defined  — app.js:2589`

## Cause (bug latent, antérieur à v0.18.0)

Lors de la suppression de `atelier_atome_generique.js` (v0.13.7.0c), un bloc
top-level était resté **orphelin** dans `app.js` :

    ATL_ATOME_CONFIG.exercice.callbacks = { … };   // ~lignes 2589–2660

`ATL_ATOME_CONFIG` n'existant plus, ce bloc levait un `ReferenceError` **au
chargement** de app.js. L'exception interrompait l'évaluation du script : toutes
les déclarations situées après (dont `let COMPIL_PREVIEW_OK`, ligne ~5177)
n'étaient jamais initialisées et restaient en **zone morte temporelle (TDZ)**.
Les `function` (hoistées) restaient appelables, d'où l'erreur différée au clic.

Pourquoi seulement maintenant : le Rendu par lot est la première fonctionnalité
testée qui dépend d'une variable `let` déclarée *après* le bloc fautif. Les
autres écrans n'étaient pas affectés (leurs symboles sont déclarés avant la
ligne 2589, ou portés par les fichiers `atelier_*.js` chargés séparément).

## Correctif

- `static/app.js` — suppression du bloc mort `ATL_ATOME_CONFIG.exercice.callbacks
  = {…}` (la logique exo est entièrement portée par la classe `AtelierExercice`
  dans `atelier_exercice.js` depuis v0.13.7.0c). Nettoyage d'un commentaire
  obsolète associé.

Aucun changement backend. app.js s'évalue désormais jusqu'au bout (vérifié en
chargeant le script dans jsdom : plus d'exception au chargement), donc
`COMPIL_PREVIEW_OK` est bien initialisée.

## Tests

- **Vitest** : 96 passed (94 + 2 nouveaux).
  - `tests_js/app_chargement_sans_reference_morte.test.js` : aucune utilisation
    de code de `ATL_ATOME_CONFIG` ne subsiste dans app.js (commentaires
    tolérés) ; `COMPIL_PREVIEW_OK` est bien déclarée. C'est précisément la
    barrière qui aurait attrapé ce bug.
- **pytest** : inchangé (3801/7/0) — correctif JS pur.
- **Syntaxe** : node --check OK.

## Note / dette repérée (non corrigée ici)

Il subsiste dans app.js des wrappers morts vers l'ancien système générique,
appelés uniquement sur action utilisateur (donc sans impact au chargement) :
`atelExerciceTab` → `window.atelAtomeTabBasculer(...)`, ainsi que
`atelAtomeNouveau/Charger/Sauvegarder/Supprimer`. Ils sont remplacés par
`ATELIER_EXERCICE` (classe OO). Nettoyage à planifier (hors périmètre de ce
correctif ciblé).

## À vérifier côté Windows

1. Rendu par lot → « Aperçu (compter) » : plus d'erreur ; le statut passe à
   « ✓ N atomes éligibles » et le bouton « Lancer » s'active.
2. Console du navigateur : plus de `ReferenceError: ATL_ATOME_CONFIG`.
3. Lancer un run (ex. Cartes N10 S01) fonctionne de bout en bout.
