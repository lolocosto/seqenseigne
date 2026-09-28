# Redémarrage v0.21.0 — Indisponibilités (modèle + saisie + projection)

Première livraison du chantier « indisponibilités ». Enregistre les périodes où
des séances prévues à l'EDT n'ont pas lieu (surveillance d'examen, sortie,
journée de cohésion…) et les retire du planning projeté, ce qui décale la suite.

Périmètre A (validé) : modèle + saisie + prise en compte dans la **projection**.
L'effet sur la **progression principale** (choix décaler/absorber) fait l'objet
de la livraison suivante (v0.21.1). L'effet sur les MER (décalage automatique de
fin) viendra avec le chantier MER.

## Modèle

Table `indisponibilites(id, annee, etablissement_id, type, date_debut,
date_fin, creneau_debut, creneau_fin, portee, classes_ids, motif)` (migration
idempotente).

- **type** : `journees` (plage de jours entiers, ex. du 09/09 au 11/09) ou
  `seances` (plage de créneaux dans une journée, ex. M2 → S3 le 08/09).
- **portee** : `moi` (toutes mes séances du moment sautent) ou `classes`
  (seulement les classes de `classes_ids`).
- **motif** : texte libre.

## Fonction pure

`indisponibilites.concerne_seance` / `filtrer_seances` : déterminent si une
séance projetée est couverte par une indisponibilité (pure, testable). Le type
`seances` situe les créneaux via leur `ordre` dans la grille horaire.

## Intégration à la projection

`projection_seances.projeter` reçoit `indisponibilites` + `classe_id`. Les
séances couvertes sont retirées **avant** la numérotation, donc les numéros se
recalent tout seuls (le décalage est intrinsèque). Ordre de traitement :
vacances/fériés → indisponibilités → numérotation.

Les routes `projection` et `affectation` chargent les indisponibilités de
l'année/établissement et les passent à `projeter`.

## API

- `GET /api/indisponibilites[?annee=&etablissement_id=]`
- `POST /api/indisponibilites`
- `PUT /api/indisponibilites/<id>`
- `DELETE /api/indisponibilites/<id>`

Validations : type `seances` exige les créneaux ; portée `classes` exige au
moins une classe ; date de fin ≥ début.

## UI

Nouvel onglet **« Indisponibilités »** dans Suivi annuel, entre « EdT » et
« Progression ». Formulaire de saisie (type, dates, créneaux, portée, classes,
motif) qui adapte ses champs selon le type et la portée, + liste des
indisponibilités avec suppression.

## Fichiers

- `persistence/sqlite_store.py` : table `indisponibilites` (migration).
- `services/indisponibilites.py` (nouveau).
- `services/projection_seances.py` : paramètres `indisponibilites`/`classe_id`,
  filtrage avant numérotation.
- `routes/indisponibilites.py` (nouveau).
- `routes/projection.py`, `routes/affectation.py` : chargent et passent les
  indisponibilités.
- `app.py` : blueprint `bp_indisponibilites`.
- `templates/index.html` : bouton + panneau `stab-indispo`, inclusion
  `static/indispo.js`.
- `static/app.js` : entrée `indispo` dans `SUIVI_ATELIER_PANNEAU` + init.
- `static/indispo.js` (nouveau).
- `tests/test_v0_21_0_indisponibilites.py` (nouveau, 6 cas).

## Tests

- `tests/test_v0_21_0_indisponibilites.py` : 6 passed (table, filtrage
  journees/seances, portées moi/classes, décalage de projection, CRUD +
  validations).
- pytest ciblé (indispo + projection + affectation + edt + grille) : 37 passed,
  0 régression.
- vitest : 192 passed. Syntaxe indispo.js/app.js OK, routes + fichiers servis
  vérifiés.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. La table se crée au premier
lancement (idempotent). Onglet Suivi annuel › Indisponibilités.

## Suite

- **v0.21.1** : effet des indisponibilités sur la progression principale
  (proposer, à chaque indisponibilité, de décaler la fin d'une semaine ou de
  laisser les élèves absorber — travail à la maison).
- Puis chantier MER (v0.22+) : effet automatique sur la progression de MER
  (décalage de fin pour préserver le nombre de séances).
