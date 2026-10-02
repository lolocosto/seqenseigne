# Redémarrage v0.43.0 — Début de séance (séance, mise en route, absents)

Deuxième livraison du chantier « suivi en séance » (ROADMAP).

## Décisions validées

- **Séance affichée** (Suivi › Début de séance) : celle dont le créneau
  contient l'heure ; sinon la prochaine de la journée (« pas encore
  commencée ») ; sinon la dernière (« terminée »). Calcul sur la projection
  (alternance A/B, fériés, versions d'EdT) ; cours en classe entière
  seulement ; séances touchées par une indisponibilité écartées.
  À l'ouverture : séance en cours toutes classes confondues, et sa classe
  devient la classe sélectionnée. Bouton « Séance en cours » pour y revenir ;
  champ Jour et liste des séances du jour pour saisir après coup.
- **Mise en route** affichée au professeur : automatismes (Leitner) avec le
  n° de séance et les enveloppes, ou progression de MER avec le n° de séance,
  ou « pas de mise en route ».
- **Absents** : clic sur l'élève (plan de classe de la semaine, élèves non
  placés à côté), second clic pour annuler ; sans plan (pas de salle ou
  aucun élève placé) : liste alphabétique. Enregistré à chaque clic,
  modifiable après la séance. Compteur « absents / effectif ». Pas de
  retards (politique du collège : au-delà de 5 min l'élève est pris en
  charge ailleurs).

## Code

- Migration : table `absences(classe_id, eleve_id, date, creneau_code)`
  (schéma porté par `services/seance.py`). Données de mineurs : base locale,
  à intégrer au futur processus de conservation de fin d'année.
- `services/seance.py` : `seances_du_jour`, `statut`, `seance_en_cours`,
  `lire`, `absents`, `definir_absence`.
- `routes/seance.py` : `GET /api/seance/en-cours`, `GET /api/seance/jour`,
  `GET /api/seance`, `PUT /api/seance/absence`.
- `services/planification_hebdo.detail_seance` : nouveau champ `mer_rang`
  (rang de la séance dans sa série de MER) ; `contexte_projection.
  seances_de_la_semaine` : `heure_debut` / `heure_fin`. Capture v0.41.1
  régénérée : seule la nouvelle clé `mer_rang` apparaît.
- `static/seance.js`, panneau `stab-debut`, branchements dans `app.js`
  (ouverture du sous-onglet, changement de classe, d'année ou
  d'établissement).

## Tests

- pytest `tests/test_v0_43_0_debut_seance.py` (9) : en cours / prochaine /
  dernière, par classe, jour sans cours, indisponibilité, mise en route,
  liste alphabétique sans plan, plan de la semaine, absences et validations,
  routes.
- Suite complète : pytest 4089 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur : séance en cours détectée (vendredi 02/10, M3, « pas
  encore commencée »), choix du lundi 05/10, plan de la 302, deux absents.
