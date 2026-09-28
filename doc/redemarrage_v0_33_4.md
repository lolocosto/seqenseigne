# Redémarrage v0.33.4 — Suivi : niveau par défaut « - » + rattachement progression

Deux correctifs pour le suivi de classe. (Delta cumulatif : inclut aussi
v0.33.1/2/3, cf. plus bas.)

## Point 3 — Niveau par défaut « - » (non évalué) au lieu de « I »

`getNiv` renvoyait '1' (Insuffisant = 4 pts) par défaut, ce qui donnait une note
d'environ 4/20 AVANT toute saisie. Corrigé : défaut = '0' (Aucune donnée, « - »,
points:null). La note vaut « — » tant qu'aucun objectif n'est évalué, et « - »
distingue « pas encore évalué » d'« Insuffisant ».

## Correctif — Rattachement de la progression (bon référentiel)

La 4E4 2026-2027 n'a pas de `progression_id` rattaché ; le fallback comparait par
NOM d'établissement (`lire_progression`) et échouait, si bien que le suivi lisait
un vieux référentiel (N11_v2021, exercices vides). Ajout d'un fallback prioritaire
par TRIPLET (niveau, année, id établissement) via `lire_progression_par_triplet`.
Vérifié : la 4E4 2026-2027 pointe désormais vers N11_v2025.

## Fichiers

- `static/app.js` : `getNiv` défaut '0' ; (+ v0.33.1 atelier, v0.33.3 clés exos).
- `routes/classes.py` : fallback progression par triplet.
- `templates/index.html` : (v0.33.2 fermeture prog-creneau-form).

## Delta cumulatif

Le déploiement courant pouvait ne pas contenir les correctifs précédents. Ce zip
regroupe : v0.33.1 (deeplink `atelier` défini), v0.33.2 (`#prog-creneau-form`
fermé → panneaux visibles), v0.33.3 (clés d'exercices longues), v0.33.4 (ce doc).

## Tests

- vitest : 193 passed. Vérifié : 4E4 2026-2027 → N11_v2025 ; niveau défaut '0'.

## Reste à faire (cf. ROADMAP)

- Point 2 : exercices dans le suivi (liaison référentiel → atomes). NON un bug
  d'une ligne : fonctionnalité non implémentée (documentée dans le code). À
  cadrer en v0.34.
- Point 1 : saisie par créneau (partie), pas par séquence. À cadrer.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Ctrl+Shift+R.
