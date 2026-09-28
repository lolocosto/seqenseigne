# Redémarrage v0.32.0 — Onglet « Planification hebdo » (socle)

Premier volet de la planification par séance : un onglet « Planification hebdo »
(Suivi de classe › Suivi annuel), vue calendaire d'une semaine façon EdT, avec
le détail d'une séance au clic (lecture seule). L'association de documents et les
rappels viendront ensuite.

## Contenu

- Nouveau sous-onglet **« Planification hebdo »** (après « EdT hebdo »).
- **Vue calendaire** d'une **semaine unique** (navigation ‹ précédente /
  suivante › / cette semaine), **toutes les classes**, code couleur EdT.
- Grille jours × créneaux : chaque séance comptée (classe entière, cours)
  apparaît avec sa classe, son type MER (Cours / MER auto / MER prog) et, si
  concernée, l'**indisponibilité** (barré + ⛔).
- **Détail au clic** (modale, lecture) : classe, date, créneau, et **séquence
  principale en cours** à cette date (calculée via la progression réalisée,
  décalages appliqués). Un message annonce l'association de documents à venir.

## Architecture

- `services/planification_hebdo.py` (nouveau) : `semaine_de` (bornes),
  `grille_semaine` (assemblage léger EdT × MER × indispos, toutes classes),
  `detail_seance` (séquence principale par croisement date × progression
  réalisée). N'assemble que des données déjà produites ailleurs.
- `routes/planification_hebdo.py` (nouveau) : `GET /api/planification-hebdo`
  (grille) et `…/seance` (détail).
- `app.py` : blueprint `bp_planification_hebdo`.
- `templates/index.html` : sous-onglet + panneau `stab-planif` + modale de
  détail ; inclusion du JS.
- `static/app.js` : `planif` dans le mapping (sélecteur établissement), liste des
  panneaux, init.
- `static/planification_hebdo.js` (nouveau) : grille, navigation, détail.

## Tests

- `tests/test_v0_32_0_planification_hebdo.py` : 3 passed (bornes de semaine,
  défaut, structure de grille). vitest : 193 passed.
- Endpoints vérifiés sur la base réelle : grille de la semaine du 14/09
  (19 séances, 9 créneaux), détail d'une séance. Croisement date → séquence
  validé sur une progression datée (S14) ; « non datée / aucune » pour 2026-2027
  (progressions pas encore datées — normal).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Suivi de
classe › Suivi annuel › Planification hebdo.

## Suite

- v0.32.1 : associer des documents (à publier du référentiel interne / attachés
  aux parties du référentiel externe) de la séquence de la séance (et en option
  la séquence suivante).
- v0.32.2 : rappels d'impression (todo automatique dérivée, délai 7 j
  configurable, tuile « À imprimer »).
- v0.32.3 : rendre la tuile « Séances de la semaine » cliquable (voir le prévu).
