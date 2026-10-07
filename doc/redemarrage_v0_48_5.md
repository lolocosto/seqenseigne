# Redémarrage v0.48.5 — Fichiers externes placés automatiquement ; types MER

Découpage validé (plus facile à tester) : v0.48.5 côté progression
principale + typage des documents de MER ; v0.48.6 placement et panneau
« documents à distribuer » côté progression de MER (avec le délai « fin de
la partie de MER »).

## Décisions validées

- Un fichier de **partie** d'un référentiel principal externe porte :
  sa **séance de distribution dans la partie** (vide = à associer à la main),
  un **retour** (aucun / à faire / à rendre) et un **délai** (prochaine
  séance, x jours, x semaines, fin du créneau). Modifiable à tout moment.
- **Placement automatique** dans la progression principale qui utilise ce
  référentiel : séance de rang (séances des parties précédentes du même
  créneau) + n du créneau qui couvre la partie. Il apparaît partout comme un
  document prévu (détail de la planification hebdo, bloc Documents du début
  de séance, conversion en travail à la distribution, synthèse Pronote).
- **Une association manuelle du même fichier** dans la progression
  **remplace** le placement automatique.
- Documents annuels : association manuelle seulement.
- **Documents des référentiels externes de MER typés** (même liste que les
  principaux, Système › Préférences).

## Code

- Migration : colonnes `seance_n`, `retour`, `delai_type`, `delai_n` de
  `referentiel_fichiers` ; `type_id` de `referentiel_externe_doc`.
- `services/referentiel_principal_externe.py` : `placer_fichier`,
  `placements_automatiques`, `typer_doc_mer`.
- `services/documents_seance.py` : `_placements_auto` (clé
  `auto:<fichier>:<créneau>`), ajoutés à `documents_prevus`.
- `services/planification_hebdo.detail_seance` : documents automatiques de la
  séance dans `docs_a_distribuer`.
- Routes : `PUT /api/referentiels-principaux-externes/fichiers/<id>/placement`,
  `PUT /api/referentiels-externes/docs/<id>/type`.
- `static/referentiel_pe.js` (contrôles de placement, réutilise ceux de
  `progression_doc.js` ; sélecteur de type des documents MER),
  `static/referentiel_externe.js`, `static/app.css`.

## Tests

- pytest `tests/test_v0_48_5_placement_fichiers.py` (5).
- Suite complète : pytest 4159 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur : séance 2, « à rendre », sur un fichier de partie.
- À vérifier chez l'auteur : progression principale réelle sur un
  référentiel externe (créneau couvrant plusieurs parties).
