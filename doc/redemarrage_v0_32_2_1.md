# Redémarrage v0.32.2.1 — Correctif indisponibilités + bornage de la navigation

Corrige l'onglet Indisponibilités (vide) et borne la navigation de la
planification hebdo à l'année scolaire.

## Bug corrigé — onglet Indisponibilités vide

L'insertion du panneau « Planification hebdo » (v0.32.0) avait, par erreur,
absorbé la balise d'ouverture du panneau `stab-indispo` : le contenu des
indisponibilités (titre, formulaire, liste) se retrouvait hors de son conteneur,
donc jamais affiché. Le panneau `stab-indispo` est rétabli et englobe de nouveau
tout son contenu.

## Bornage de la navigation (planification hebdo)

Les boutons de navigation sont désactivés aux bornes de l'année scolaire
(1er septembre → 31 juillet) :
- **« Semaine précédente »** désactivée quand la semaine précédente se termine
  avant le 1er septembre ;
- **« Semaine suivante »** désactivée quand la semaine suivante commence après le
  31 juillet.

## Fichiers

- `templates/index.html` : panneau `stab-indispo` rétabli ; `id` sur les boutons
  de navigation.
- `static/planification_hebdo.js` : `_planifBornesAnnee`, `_planifMajBornes`
  (désactivation des boutons), appelées au rendu de la grille.

## Tests

- vitest : 193 passed. `node --check` (exit 0). Bornage vérifié (1ère semaine →
  précédente désactivée ; dernière → suivante désactivée ; semaine courante →
  rien désactivé). Panneau `stab-indispo` vérifié : contient de nouveau le
  formulaire et la liste.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Se déploie par-dessus la
v0.32.2. L'onglet Indisponibilités réaffiche son contenu ; la navigation de la
planification est bornée à l'année.
