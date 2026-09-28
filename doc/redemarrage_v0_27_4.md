# Redémarrage v0.27.4 — Logique métier restante rapatriée côté serveur

Termine le chantier « logique métier côté serveur » : migre les deux règles de
gestion qui subsistaient en JS et clôt les points à examiner de
`doc/inventaire_logique_metier_js.md`.

## Migrations

### 1. Année scolaire courante (`anneeScolaireCourante`)
Le calcul de l'année scolaire à partir de la date (règle de calendrier) est
retiré du JS. L'année courante est fournie par le serveur
(`services/annees_scolaires` via `/api/annees-scolaires`) et chargée à l'init
dans la globale `ANNEE_COURANTE`. La fonction `anneeScolaireCourante()` est
conservée comme simple accesseur (retourne `ANNEE_COURANTE`), pour ne pas
toucher ses nombreux appelants (fallbacks d'année dans edt/indispo/mer/…).

### 2. Semaines touchées par une indisponibilité (`_semainesTouchees`)
Le calcul du nombre de semaines civiles touchées par une indisponibilité
(valeur par défaut d'un décalage) est déplacé côté serveur
(`services/indisponibilites.semaines_touchees`) et exposé dans l'API : chaque
indisponibilité listée porte `semaines_touchees`. La méthode JS
`_semainesTouchees` est supprimée ; l'atelier lit `ind.semaines_touchees`.

## Points examinés (clôturés)

- `prefDerive` / `prefRecalculerDerives` : présentation d'un formulaire de
  préférences (aide à la saisie de chemins), sans règle métier partagée →
  **gardé en JS** (c'est de la présentation).
- Cadence Leitner et projection à la séance : **vérifié**, aucun recalcul en JS
  (déjà exclusivement côté serveur).

Après cette version, il ne reste plus de règle de gestion connue côté client :
le JS demande les résultats et les affiche.

## Fichiers

- `static/app.js` : `ANNEE_COURANTE` chargée du serveur ;
  `anneeScolaireCourante()` devient un accesseur.
- `services/indisponibilites.py` : `semaines_touchees` + exposée par `lister`.
- `static/atelier_progression.js` : lit `ind.semaines_touchees` ;
  `_semainesTouchees` supprimée.
- `doc/inventaire_logique_metier_js.md` : mis à jour (🔴/🟡 → 🟢).

## Tests

- vitest : 193 passed. pytest indispo : 8 passed.
- `semaines_touchees` vérifiée (1 jour → 1 ; à cheval → 2 ; 2 semaines → 2) et
  exposée par l'API. Année courante servie par le serveur.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.27.3.1.

## Suite

- MER panachées (automatismes + progression sur des séances distinctes,
  affectation par séance sur l'EdT).
