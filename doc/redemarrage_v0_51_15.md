# Redémarrage v0.51.15 — Ordre des créneaux, indisponibilités par créneaux

## Constat

Une indisponibilité « le 01/10, de M4 à M5 » rayait toute la journée dans le
tableau de bord. Cause : l'ordre des créneaux de la grille horaire était
l'ordre de création ; M5, ajouté après S4, avait l'ordre le plus grand, et la
plage « M4 → M5 » couvrait aussi S1 à S4 (même effet sur l'ordre des séances
d'une journée dans la projection).

## Correction

- L'ordre d'un créneau est sa **position dans la journée** (heure de début,
  puis ordre de saisie ; créneaux sans heure à la fin). Il est renuméroté
  (10, 20, …) à chaque création ou modification d'un créneau, et toutes les
  grilles existantes le sont au démarrage.
- Une indisponibilité par créneaux ne retire que les séances de sa plage.

## Rang des séances (question de la v0.51.14)

Déjà le cas : le rang « (n/N) » est compté sur les séances réellement faites
dans le créneau de la progression (indisponibilités retirées), pas sur la
durée prévue au référentiel. Test ajouté.

## Code

- `services/grille_horaire.py` (`renumeroter`, `renumeroter_tout`, tri de
  `lister`), `persistence/sqlite_store.py` (migration au démarrage).
- Tests : `tests/test_v0_51_15_ordre_creneaux.py`.
