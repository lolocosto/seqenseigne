# Redémarrage v0.47.1 — Synthèse pour le cahier de textes Pronote

## Décisions validées

- Bouton **« Synthèse Pronote »** dans Suivi › Travail (fin de séance), qui
  ouvre un panneau de saisie et deux zones à copier (texte brut, une
  information par ligne).
- **Contenu de la séance** :
  1. mise en route : « Mise en route : <partie de la progression de MER>
     (r/N) » | « Mise en route : automatismes (enveloppe(s) …) » |
     « Pas de mise en route » (classe à MER sans mise en route, dont « non
     faite ») ; aucune ligne pour une classe sans MER ;
  2. séquence : « <code> <nom> — <partie> (n/N) » ;
  3. « Cours : notions (…) et méthodes (…) » : cases à cocher parmi les
     notions rattachées aux objectifs de la partie du créneau et les méthodes
     de ces objectifs ; les éléments **déjà cochés aux séances précédentes du
     même créneau** sont repliés (« Déjà faits dans ce créneau ») ;
  4. activités en multi-sélection **ordonnée** (ordre de la séance) :
     Évaluation, Révisions, Exercices, Correction par défaut, liste
     extensible dans Paramétrage › Observables (« Activités de séance ») ;
  5. texte libre (référentiel externe, ou complément) ;
  6. « Documents distribués : … » (cochés distribués à la séance, hors
     travaux).
- **Travail à faire** : « Pour le jj/mm : <libellé> » (+ « (à rendre) »),
  triés par échéance.
- Les choix sont enregistrés pour la séance (on les retrouve en rouvrant ;
  base du « déjà fait »).

## Code

- Migration : tables `seance_contenu`, `activites_seance` (activités par
  défaut créées) — `services/synthese_seance.py` (`migrer`).
- `services/synthese_seance.py` : `candidats`, `lire_contenu`,
  `enregistrer_contenu`, `deja_faits`, `lire`, activités.
- `services/planification_hebdo.detail_seance` : nouveau champ
  `creneau_prog` (id, parties, dates du créneau de progression) ; capture
  v0.41.1 régénérée (seule cette clé apparaît).
- `routes/seance.py` : `GET/PUT /api/seance/synthese`,
  `GET/POST /api/activites-seance`, `PUT /api/activites-seance/<id>`.
- `static/travail.js`, `static/observables.js`, `templates/index.html`,
  `static/app.css`.

## Tests

- pytest `tests/test_v0_47_1_synthese_pronote.py` (6).
- Suite complète : pytest 4129 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur (référentiel externe) : activités dans l'ordre, texte
  libre, documents distribués, travail à faire ; liste des activités dans
  Paramétrage.
