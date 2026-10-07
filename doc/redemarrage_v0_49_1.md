# Redémarrage v0.49.1 — Documents de MER (placement, délai, associations)

Suite du plan d'unification (après B / v0.49.0). Concerne les référentiels de
MER de la structure figée (l'ancien modèle de MER n'est pas concerné).

## Décisions validées

- Un document de **partie** d'un référentiel de MER porte, comme pour les
  principaux, sa **séance de distribution dans la partie**, un **retour**
  (à faire / à rendre) et un **délai** : prochaine séance, x jours,
  x semaines ou **« pour la fin de la partie »** (dernière séance de MER de
  la partie, même échéance pour tous).
- **Placement automatique** : à la séance de MER de rang n dans sa partie,
  pour chaque classe dont les mises en route utilisent ce référentiel (mode
  « progression » ou « panache »).
- **Panneau « 📄 documents »** sur chaque partie posée de la Progression de
  MER : documents placés automatiquement (barrés s'ils sont remplacés),
  associations manuelles (séance dans la partie, retour, délai) — une
  association manuelle **remplace** le placement automatique du même
  document ; on peut aussi associer un document sans séance prévue (de la
  partie, de la séquence, ou annuel).
- **Au même endroit** que les autres documents : détail de la planification
  hebdo (même sans créneau de progression principale), bloc Documents du
  début de séance, travail suivi (retour), synthèse Pronote.

## Code

- `services/progression_doc.py` : délai `fin_partie`.
- `services/documents_seance.py` : `seances_mer` (séances de MER de la classe
  avec leur partie de référentiel), `_prevus_mer` (clés `automer:<fichier>`,
  `mer:<association>`) ; documents de MER placés même sans progression
  principale.
- `services/planification_hebdo.detail_seance` : documents de MER de la
  séance.
- `static/progression_mer.js` (panneau documents d'une partie),
  `static/progression_doc.js` (liste de délais paramétrable),
  `static/referentiel_pe.js` (« fin de la partie » pour une MER),
  `static/app.css`.

## Tests

- pytest `tests/test_v0_49_1_documents_mer.py` (5).
- Suite complète : pytest 4170 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur : Progression de MER, partie posée, panneau documents,
  association « à faire — pour la fin de la partie ».
