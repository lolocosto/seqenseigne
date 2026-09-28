# Redémarrage v0.33.3 — Correctif : saisie du suivi de classe impossible

Corrige le plantage du suivi de classe (onglet Suivi → Suivi de classe) qui
empêchait de déplier les objectifs d'exercices et de saisir les résultats.

## Cause

Dans `renderClasseView` (app.js), le calcul de la largeur de colonne d'un
objectif déplié accédait aux clés COURTES des séries d'exercices :
`obj.exercices.F`, `.A`, `.E`. Or la structure renvoyée par l'API utilise les
clés LONGUES : `fondamental`, `avancé`, `exploration` (le reste du code utilise
d'ailleurs ces clés longues). `obj.exercices.F` était donc toujours `undefined`,
et `.length` levait « can't access property length, obj.exercices.F is
undefined ».

Conséquence : déplier un objectif d'exercice (ou rouvrir une classe dont un tel
objectif était déplié) plantait le rendu. Bug jamais vu jusqu'ici car la saisie
du suivi n'avait pas encore été utilisée.

## Correctif

Ligne du calcul de `span` : clés longues + chaînage optionnel :
`1 + (obj.exercices.fondamental?.length?1:0) + (obj.exercices.avancé?.length?1:0)
+ (obj.exercices.exploration?.length?1:0)`.

## Fichiers

- `static/app.js` : `renderClasseView`, calcul de `span` (clés d'exercices).

## Tests

- `node --check` (exit 0). Calcul de `span` vérifié (2 avec exos fondamentaux,
  1 si tout vide ; ne plante plus sur clés absentes). vitest : 193 passed.

## Note

`expanded` (objectifs dépliés) est en mémoire, pas persistant : au rechargement,
la classe se rouvre sans objectif déplié. Le correctif permet désormais de
déplier les objectifs d'exercices et de saisir les résultats.

## Delta cumulatif (important)

Ce zip regroupe les correctifs v0.33.1, v0.33.2 ET v0.33.3, car le déploiement
courant pouvait ne pas contenir les précédents :
- v0.33.1 :  — variable  définie (sinon init() plante).
- v0.33.2 :  — fermeture de  (sinon panneaux vides).
- v0.33.3 : clés d'exercices longues dans  (ce correctif).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.33.2. Ctrl+Shift+R.
