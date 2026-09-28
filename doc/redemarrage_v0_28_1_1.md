# Redémarrage v0.28.1.1 — Correctif : onglet Mises en route cassé (mer.js)

Correctif d'une erreur de syntaxe introduite en v0.28.1 qui cassait tout
l'onglet « Mises en route ». Purement front (un fichier).

## Cause

Dans `static/mer.js`, la fonction `merCyclerAffectation` n'était pas fermée
(bloc `try`/PUT + accolade manquants) : une accolade ouvrante sans fermante.
Résultat : `SyntaxError: Unexpected end of input` → le fichier entier ne
s'exécutait pas → aucune fonction MER définie → la liste des classes (et le
reste de l'onglet) ne s'affichait plus.

## Correctif

`merCyclerAffectation` est correctement fermée (persistance de l'affectation via
`PUT /api/classes/<id>/affectations` au format `items` + année, puis
rafraîchissement du planning). Fichier revérifié : accolades équilibrées,
`node --check` sans erreur, exécution sans erreur.

## Fichiers

- `static/mer.js` : fermeture de `merCyclerAffectation`.

## Tests

- `node --check static/mer.js` : OK (0 erreur). Exécution du fichier : OK.
- vitest : 193 passed.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Purement front. Se déploie
par-dessus la v0.28.1. La liste des classes et la grille d'affectation
réapparaissent.
