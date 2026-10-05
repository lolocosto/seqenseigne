# Redémarrage v0.48.0 — Retour et délai sur les documents associés

Première des trois livraisons v0.48 (découpage validé : v0.48.0 associations
et conversion ; v0.48.1 progression principale sur référentiel interne ou
externe ; v0.48.2 documents externes portant leur séance + documents de MER).

## Décisions validées

- Une association de document de la **progression principale** (Planification
  › Progression principale › créneau › Documents à distribuer) porte un
  **retour** facultatif — à faire (non évalué) / à rendre (évalué) — et un
  **délai** : pour la prochaine séance, dans x jours, dans x semaines, ou
  **pour la fin du créneau**. Modifiable directement dans la liste des
  documents associés.
- **Fin du créneau** = dernière séance du créneau de progression, **même
  échéance pour tous**, absents compris (les documents sont aussi déposés dans
  Pronote le jour de la distribution). Usage : fiches de résumé de la partie
  (méthode « classe accompagnée »).
- **À la distribution** (Début de séance, coche « distribué »), un document
  prévu avec retour devient un travail suivi dans Suivi › Travail
  (à vérifier / à ramasser / retards), et figure dans la synthèse Pronote
  (« Pour le jj/mm : … ») et dans la liste des travaux donnés (« prévu dans
  la progression »).
- Tant qu'un document prévu n'est pas distribué, il suit les changements de
  son association (libellé, retour, délai) ; une fois distribué, il est figé.

## Code

- Migration : colonnes `retour`, `delai_type`, `delai_n` de
  `progression_doc` ; `echeance_date`, `echeance_creneau` de
  `seance_documents`.
- `services/progression_doc.py` : `RETOURS`, `DELAIS`, `migrer_v0_48`,
  `delai_en_jours`, `modifier_retour`, `ajouter(..., retour, delai_type,
  delai_n)`.
- `routes/progression_doc.py` : champs à l'ajout,
  `PUT /api/progression-doc/<id>/retour`.
- `services/documents_seance.py` : retour, délai et échéance fixe des
  documents prévus ; mise à jour tant que non distribués.
- `services/travail.py` : échéance fixe pour tous ; documents prévus avec
  retour dans `donnes_ici`.
- `static/progression_doc.js`, `static/travail.js`, `templates/index.html`,
  `static/app.css`.

## Tests

- pytest `tests/test_v0_48_0_retour_associations.py` (5).
- Suite complète : pytest 4134 réussis, 0 échec ; vitest 225 réussis.
