# Redémarrage v0.19.1.6 — Calendrier : masquer les créneaux sur les semaines entièrement en vacances

Correctif d'affichage du calendrier de l'atelier Progression.

## Problème

Un créneau qui enjambe une période de vacances (typiquement : une semaine de
classe avant les vacances, une semaine après) s'affichait **en continu**, y
compris sur les semaines tombant entièrement pendant les vacances. Il ne
devrait apparaître que sur les semaines où il y a effectivement classe.

## Correctif

Sur le calendrier, un créneau n'est plus affiché sur une semaine **entièrement
en vacances**, c'est-à-dire dont les cinq jours lundi→vendredi sont tous
couverts par une période de vacances.

Distinction importante : une semaine qui conserve **au moins un jour de classe**
continue d'afficher le créneau. En particulier, un **jour férié** n'est pas
traité comme des vacances — une semaine de classe contenant un férié reste une
semaine de classe et affiche le créneau normalement.

## Détails

- `static/atelier_progression.js` :
  - `_creneauxDeLaSemaine(lundiISO)` renvoie une liste vide si la semaine est
    entièrement en vacances ;
  - nouveau `_jourEnVacances(iso)` : un jour est en vacances si
    `start_date <= iso < end_date` (la date de reprise est exclue) ;
  - nouveau `_semaineEntierementEnVacances(lundiISO)` : vrai si les 5 jours
    lundi→vendredi sont tous en vacances (les fériés ne comptent pas).

Aucun changement de modèle ni de backend.

## Tests

- `tests_js/atelier_progression.test.js` (+5 cas) : créneau masqué sur une
  semaine pleine de vacances ; affiché la semaine de reprise ; semaine avec un
  férié seul non considérée comme vacances ; fin exclusive du jour de reprise.

**Zéro régression** : vitest → 192 passed (187 + 5).

## Déploiement

Aucune migration. Décompresser le delta sur D:/E:, puis :

    python -m outils.verifier_md5

Dans « Suivi de classe » > Progression, un créneau qui enjambe des vacances
n'apparaît plus sur les semaines entièrement en vacances, mais reste visible
sur les semaines de classe encadrantes (et sur les semaines avec un simple
jour férié).
