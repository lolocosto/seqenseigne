# Redémarrage v0.47.0 — Travail à faire / à rendre, documents à rapporter

Sixième livraison du chantier « suivi en séance » (ROADMAP).

## Décisions validées

- **Sous-onglet Suivi › Travail** (entre Observation et Compétences), sous le
  même en-tête de séance que Début de séance et Observation.
- **Donner du travail** (fin de séance) : libellé, **à faire** (vérifié en
  classe) ou **à rendre** (ramassé), échéance « prochaine séance », « au moins
  3 jours », « au moins 1 semaine » (= première séance de la classe au moins
  N jours après). Un travail est un document de séance (origine « travail »)
  distribué aussitôt : les **absents** le reçoivent par le rattrapage du Début
  de séance, et **leur échéance part de cette remise** (délai individualisé).
- **À vérifier** : « à faire » dont l'échéance est la séance ; on coche les
  élèves qui **ne l'ont pas fait** (constat ; le mot aux parents est hors
  appli), avec l'option **« à rattraper »** qui lui fixe une nouvelle échéance
  à la séance suivante, pour lui seul. Les absents ne sont pas concernés ce
  jour-là.
- **À ramasser** : « à rendre » et documents **« à rapporter »** ; coche
  « rendu » à n'importe quelle séance ; reste ouvert tant qu'un élève qui l'a
  reçu ne l'a pas rendu, sauf **« Clore »**. Après son échéance, l'élève est
  en retard.
- **Document à rapporter** (autorisation signée…) : dans le bloc Documents du
  Début de séance, un document distribué peut être marqué « à rapporter sous
  3 jours / 1 semaine » ; le retour est attendu des élèves qui l'ont reçu
  (distribution ou rattrapage), avec une échéance individuelle.
- **En retard** : récapitulatif de la classe, par élève, avec la liste
  précise (libellé, type, échéance).

## Code

- Migration : colonnes `retour`, `delai_jours`, `clos` de `seance_documents` ;
  tables `retours`, `echeances_individuelles` (`services/travail.py`,
  `migrer`).
- `services/travail.py` : `seances_classe`, `premiere_seance_apres`,
  `remises`, `echeances`, `donner`, `definir_retour`, `supprimer_travail`,
  `clore`, `marquer_rendu`, `marquer_non_fait`, `pour_seance`.
- `services/documents_seance.py` : les travaux ne figurent pas dans les
  « nouveaux documents » ; le rattrapage indique le type de retour.
- `routes/seance.py` : `GET/POST /api/travail`, `DELETE /api/travail/<id>`,
  `PUT /api/travail/<id>/clos|rendu|non-fait`,
  `PUT /api/seance/document/<id>/retour`.
- `static/travail.js`, `static/seance.js`, `static/app.js`,
  `templates/index.html`, `static/app.css`.

## Suite (v0.48)

Attribut « travail à rendre » sur les documents des référentiels (principal
et MER), délai fixé à l'association à une séance d'un créneau, et
association des documents à la progression de MER.

## Tests

- pytest `tests/test_v0_47_0_travail.py` (7).
- Suite complète : pytest 4123 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur : 4EME3 le 05/10 (deux absents) — un DM à rendre sous
  une semaine et des exercices à faire pour la prochaine séance ; le 09/10,
  vérification (absents du 05/10 non concernés, un non fait « à rattraper »)
  et un premier DM rendu.
