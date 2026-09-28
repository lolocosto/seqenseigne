# Redémarrage v0.20.1 — UI de saisie de l'emploi du temps

Deuxième livraison du chantier « saisie de l'EdT ». Écran de saisie de
l'emploi du temps de l'enseignant, façon PDF (grille jours × créneaux, demi-cases
semaine A/B), avec popover d'édition. **Fonctionnel d'abord** (raffinement
visuel volontairement minimal, à peaufiner plus tard).

## Emplacement

Nouvel onglet **« EdT »** dans Suivi de classe › Suivi annuel, en première
position (avant « Progression »).

## Contenu

- Sélecteur d'**établissement** et champ **année** (courante par défaut).
- **Grille** : lignes = créneaux de la grille horaire de l'établissement
  (M1..M4, S1..S4), colonnes = jours (lun–ven).
- **Cases** :
  - vide : cliquable pour saisir ;
  - « toutes semaines » (AB) : case pleine, occupe toute la hauteur ;
  - semaine A / B différentes : case divisée (A en haut, B en bas), chaque
    demi-case éditable.
- **Couleur par classe** (palette stable) ; les usages non comptés (tout sauf
  `classe_entiere`) sont affichés en légère transparence ; les cases sans classe
  (ex. « autre ») en gris.
- **Popover d'édition** au clic : semaine (AB / A / B), classe, usage (6 valeurs),
  libellé libre. Enregistrer (POST/PUT) / Supprimer (DELETE) / Fermer.

## Mécanisme AB vs A/B différent

Le champ **semaine** du popover décide de tout :
- `AB` → case pleine (identique toutes les semaines) ;
- `A` seul, ou `B` seul → demi-case ; saisir l'autre demi-case pour différencier.

Le popover masque les options contradictoires (pas de `AB` si une A/B existe,
pas de `A`/`B` si une `AB` existe).

## Garde de cohérence (backend renforcé)

`services/edt.ajouter` refuse désormais de mélanger, sur un même créneau, une
case « AB » et une case « A » ou « B » (états contradictoires). Message
explicite. La cohérence est ainsi garantie même hors de l'UI.

## Fichiers

- `templates/index.html` : bouton « EdT », panneau `stab-edt` (sélecteurs +
  grille + popover), inclusion de `static/edt.js`.
- `static/app.js` : entrée `edt` dans `SUIVI_ATELIER_PANNEAU`, affichage du
  panneau `stab-edt` et appel `edtInit()` dans `suiviSwitch`.
- `static/edt.js` (nouveau) : toute la logique de l'écran EdT.
- `services/edt.py` : garde de cohérence AB vs A/B dans `ajouter`.
- `tests/test_v0_19_1_17_edt.py` : test de la garde AB/A-B (7 cas au total).

## Tests

- pytest ciblé (edt + grille + projection + affectation) : 29 passed, 0
  régression. Garde AB/A-B vérifiée (AB+A refusé, A+B OK, A/B+AB refusé).
- vitest : 187 passed. Syntaxe `edt.js` et `app.js` OK.
- Démarrage app vérifié : edt.js servi, bouton/​panneau/​inclusion présents.
- Flux API vérifié : saisie AB (case pleine), saisie A + B distinctes (case
  divisée), couleur par classe.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. La garde backend s'applique
immédiatement. Dans Suivi annuel › EdT : choisir l'établissement, cliquer les
cases pour saisir.

## Suite

- Raffinement visuel de l'EdT (rendu plus proche du PDF) si souhaité.
- v0.21.x : utilisation des automatismes (ordonnancement Leitner).
- Chantier MER : renommer « Progression » → « Progression principale » et
  ajouter l'onglet « Progression MER » au même niveau que « EdT ».
