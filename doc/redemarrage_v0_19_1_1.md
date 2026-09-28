# Redémarrage v0.19.1.1 — Correctifs et harmonisation visuelle de l'atelier Progression

Patch de la livraison v0.19.1.0 (ossature OO de l'atelier Progression), suite
aux retours de déploiement. Correction d'un bug bloquant le calendrier et
harmonisation de l'apparence avec les autres ateliers.

> ⚠️ Cette livraison **ne contient pas** encore le drag-and-drop ni le
> changement de référentiel (toujours prévus pour une étape ultérieure du
> chantier v0.19.1). Elle stabilise l'ossature 0.19.1.0.

## Correctifs

- **Calendrier vide / `TypeError: window.MOIS_FR is undefined` au lancement.**
  `AtelierProgression` (fichier séparé) consomme les helpers calendrier
  d'`app.js` via `window.*`. Or `const MOIS_FR` / `function _lundisEntre…` au
  niveau racine d'`app.js` créent des liaisons globales qui **ne sont pas** des
  propriétés de `window`. Résultat : `window.MOIS_FR` était `undefined` et
  `_renderCalendrier` levait une exception, laissant le panneau principal vide.
  - `app.js` **ré-expose** désormais nommément sur `window` :
    `MOIS_FR`, `JOUR_FR`, `_dateToISO`, `_lundisEntre`, `_bornesAnneeScolaire`,
    `_jourSemaine`, `_vacancesDeLaSemaine`, `_feriesDeLaSemaine`, `_dateCourte`.
  - `AtelierProgression` est en outre **découplé** des fonctions
    `_vacancesDeLaSemaine` / `_feriesDeLaSemaine` d'`app.js` (qui lisaient les
    variables module-locales `CAL_VACANCES` / `CAL_FERIES`) : il calcule
    vacances et fériés depuis ses propres champs `this._calVacances` /
    `this._calFeries`. Plus de réaffectation `window.CAL_* = …`. En cas
    d'indisponibilité de l'API vacances/fériés, le calendrier se rend quand
    même (grille + créneaux), sans coloration.

## Harmonisation visuelle (alignement sur les autres ateliers)

- **Bandeau supérieur** du panneau principal reconstruit sur le modèle
  `.atl-toolbar` commun : **titre à gauche** (« Progression annuelle »,
  `flex:1`), puis **sélecteurs + badge d'état + boutons alignés à droite**,
  enfin le statut. Les 4 sélecteurs (Année · Étab. · Niveau · Référentiel)
  adoptent le style compact des sélecteurs contextuels du bandeau ateliers
  (`.prog-sel` : label court en capitales + `select` compact). Suppression de
  l'ancien bloc `.prog-bandeau*` (sélecteurs empilés à gauche).
- **Barre latérale redimensionnable** : un splitter (poignée de
  redimensionnement, largeur mémorisée en `localStorage`) est posé sur le
  panneau Progression. Profitant de la passe, on **ajoute aussi les splitters
  manquants** sur trois ateliers qui n'en avaient pas : **Thème**, **Découpage
  en séquences** et **Évaluation**. (Les ateliers d'atomes, Séquence-niveau et
  Référentiel en avaient déjà.) Clés : `split:prog:aside`,
  `split:atl-theme:aside`, `split:atl-seqcycle:aside`,
  `split:atl-evaluation:aside`.
- **Hauteur du shell** ajustée pour le panneau Progression
  (`calc(100vh - 104px)`) : il vit sous une sous-navigation à une seule barre
  (`.sub-tabs`), contrairement aux ateliers (deux barres).

## Changements (fichiers)

- `static/app.js` : ré-exposition des helpers calendrier sur `window`
  (juste après `_dateCourte`) ; ajout des 4 splitters manquants dans
  `initAtelierSplitters`.
- `static/atelier_progression.js` : `_vacancesDeLaSemaine` /
  `_feriesDeLaSemaine` internes à la classe ; suppression de la réaffectation
  `window.CAL_*`.
- `templates/index.html` : bandeau Progression reconstruit en `.atl-toolbar`
  (titre + `.prog-toolbar-selecteurs` + état + boutons).
- `static/app.css` : remplacement de `.prog-bandeau*` par `.prog-toolbar*` /
  `.prog-sel*` ; hauteur de shell `#stab-progression .atl-shell`.
- `tests_js/atelier_progression.test.js` : +5 cas de régression vérifiant que
  `app.js` ré-expose bien les helpers calendrier sur `window`.

## Tests

**Zéro régression** : pytest → 3854 passed, 7 skipped ; vitest → 172 passed
(167 + 5 nouveaux).

## Déploiement & vérification

Aucune migration de base. Décompresser le delta sur D:/E:, puis :

    python -m outils.verifier_md5

Dans « Progression annuelle » : le calendrier s'affiche désormais dans le
panneau principal (grille des semaines + créneaux), les 4 sélecteurs sont en
haut à droite du bandeau au style des autres ateliers, et la barre latérale
peut être redimensionnée par sa poignée. Vérifier au passage que Thème,
Découpage en séquences et Évaluation ont aussi une poignée de redimensionnement.

## Suite

Drag-drop parties → calendrier ; changement de référentiel support (purge des
créneaux, confirmation, restreint à `en_cours`, rétrogradation de l'ancien
référentiel).
