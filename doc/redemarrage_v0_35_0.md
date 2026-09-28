# Redémarrage v0.35.0 — Homogénéisation des sélecteurs, étape B1 (Gestion)

Étape B1 du chantier « sélecteurs homogènes » : la Gestion des classes utilise
désormais le même mécanisme de sélecteurs que le Suivi et la Planification (pool
partagé), au lieu de ses filtres codés en dur.

## Changement

Avant : la Gestion avait 3 `<select>` propres (`cl-filtre-etab/annee/niveau`),
peuplés et lus séparément, filtrant par NOM d'établissement.

Après : les ateliers `classe` et `etab` (portée Gestion) déclarent les
sélecteurs du pool partagé — `classe` : Année · Établissement · Niveau ;
`etab` : Année · Établissement. `renderClassesList` lit ces sélecteurs communs
(`#prog-sel-etab` = id établissement, `#prog-sel-niveau`, année globale). Filtrage
par id d'établissement (cohérent avec le Suivi v0.34).

Résultat : Suivi, Planification ET Gestion partagent le même moteur et la même
présentation. La Conception reste sur son mécanisme propre → étape B2 (v0.36).

## Fichiers

- `templates/index.html` : bloc `#classes-filtres` (filtres en dur) supprimé.
- `static/app.js` : ateliers `classe`/`etab` déclarent les sélecteurs du pool ;
  `_filtrerClasses` lit le pool (par id) ; `_majOptionsFiltresClasses`
  neutralisée ; `onEtabChangeGlobal` / `onNiveauChangeGlobal` gèrent la Gestion
  (refiltrage de la liste).
- `tests_js/suivi_navigation.test.js` : test Gestion adapté (sélecteurs du pool).

## Tests

- vitest : 195 passed. `_filtrerClasses` vérifié (filtre par année globale,
  robuste sans sélecteurs montés).

## Reste (ROADMAP)

- B2 (v0.36) : unifier la Conception (sélecteurs dynamiques sequence/cycle,
  dépendances niveau→séquence, stockage ATL_SELECTIONS) dans le moteur commun.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Ctrl+Shift+R.
Se déploie par-dessus la v0.34.1.
