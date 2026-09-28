# Redémarrage v0.33.2 — Correctif : panneaux Suivi/Gestion invisibles (div non fermé)

Corrige définitivement le bug des onglets « Suivi » et « Gestion » au contenu
invisible (panneau vide à l'écran).

## Cause racine

Dans `templates/index.html`, le div `#prog-creneau-form` (détail du créneau de
la Progression principale) n'était **pas fermé** : sa balise `</div>` avait été
perdue lors de l'insertion du formulaire « Documents à distribuer » (v0.32.8).

Conséquence : `#stab-suivi` et `#stab-parametrage` se retrouvaient imbriqués
DANS `#prog-creneau-form` (au lieu d'être ses frères dans `#tab-classe`).
Comme `prog-creneau-form` est un panneau de détail à largeur contrôlée / masqué,
ses « faux enfants » étaient rendus avec une taille de 0×0 → contenu présent dans
le DOM (6120 caractères) mais **invisible** à l'écran. Aucune erreur JS (d'où la
difficulté du diagnostic).

Diagnostic confirmé par `getBoundingClientRect()` : `stab-parametrage` et
`classes-list` à width:0/height:0, alors que `display` valait bien « block ».

## Correctif

Ajout du `</div>` fermant de `#prog-creneau-form` au bon niveau
d'imbrication. Vérifié : `stab-progression`, `stab-suivi` et `stab-parametrage`
sont désormais frères dans `#tab-classe`.

## Fichiers

- `templates/index.html` : fermeture de `#prog-creneau-form` restaurée.

## Tests

- vitest : 193 passed. Test structurel (jsdom) : les trois panneaux `stab-*`
  ont le même parent `#tab-classe`. Équilibre des `<div>` de `#tab-classe`
  rétabli (0).

## Dette repérée (préexistante, NON corrigée ici)

`#tab-preferences` a un `</div>` orphelin (diff -1). Sans symptôme signalé (les
navigateurs tolèrent un `</div>` en trop). Laissé tel quel pour ne pas risquer
de perturber les Préférences ; à examiner à froid.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.33.1. Recharger le navigateur (Ctrl+Shift+R).
