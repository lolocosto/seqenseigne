# Redémarrage v0.32.2.2 — Planification hebdo : afficher les vacances et fériés

La grille de planification affichait les semaines de vacances comme des semaines
de cours normales. Elle marque désormais les jours de vacances et les jours
fériés.

## Correctif

- Le service `grille_semaine` calcule, pour chaque jour de la semaine, s'il est
  **en vacances** (avec le nom de la période) et/ou **férié** — via la même
  source (cachée en base) que les autres écrans du calendrier.
- La grille (client) :
  - un **jour de vacances** : en-tête coloré avec le nom de la période (ex.
    « Vacances de la Toussaint »), colonne grisée, aucune séance affichée ;
  - un **jour férié** : en-tête et cellules teintés, nom du férié affiché.

## Note technique

`calendrier_scolaire.vacances` interroge l'API des vacances scolaires puis met
en cache le résultat en base. Pour l'année en cours, le premier accès effectue
l'appel réseau (comme pour les plannings PDF, qui affichent déjà les vacances) ;
les accès suivants lisent le cache. En cas d'échec réseau, la grille s'affiche
normalement (sans info vacances) plutôt que de planter.

## Fichiers

- `services/planification_hebdo.py` : `grille_semaine` calcule `jours_info`
  (vacances/férié par jour) et `semaine_vacances`.
- `static/planification_hebdo.js` : rendu des colonnes vacances/fériées.

## Tests

- `node --check` (exit 0) + exécution OK. vitest : 193 passed.
- Vérifié (cache 2026-2027 simulé) : la semaine du 19/10 est reconnue « Vacances
  de la Toussaint » sur les 5 jours.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.32.2.1.
