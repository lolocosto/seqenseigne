# Redémarrage v0.51.14 — Résumé des séances (planification hebdo, Journée)

## Décisions (validées)

- **Planification hebdo** : chaque séance affiche
  - le nom de la classe ;
  - « MER : automatismes (<enveloppes>) », « MER : <partie> (<n°>/<nb>) »
    (progression de MER ; « progression (aucune partie posée) » au-delà des
    parties posées) ou « MER : aucune » ;
  - « Principale : <code> <nom> (partie <n°>) (<n°>/<nb>) » — la partie
    seulement si la séquence en a plusieurs (« 1–2 » pour un créneau qui en
    couvre deux), le rang de la séance dans le créneau — ou « Principale :
    aucune » ;
  - « Docs : <documents à distribuer> » ou « Docs : aucun ».
  Le clic garde le détail de la séance.
- **Tuile Journée** : même résumé ; clic sur une séance → Suivi › Début de
  séance sur la classe, le jour et le créneau ; liens Observation, Travail
  (même séance) et Compétences (même classe) ; lien « Planification hebdo »
  gardé en bas de la tuile (semaine du jour affiché).

## Code

- `services/seances_resume.py` (nouveau) : résumé des séances, calculs faits
  une fois par classe (projection, répartition des MER, progression décalée,
  documents prévus) ; `services/planification_hebdo.py` (`grille_semaine`
  ajoute `resume` à chaque case).
- `static/planification_hebdo.js` (`planifResumeLignes`, `planifResumeHtml`,
  `PLANIF_CIBLE`), `static/tdb_tuiles.js` (`tdbOuvrirSuivi`), `static/seance.js`
  (`SC.cible`), `static/observation.js`, `static/travail.js`, `static/app.css`.
- Tests : `tests/test_v0_41_1_projection_figee.py` (résumé hors capture),
  `tests/test_v0_51_14_resume_seances.py` (dont cohérence avec le
  détail d'une séance), `tests_js/tdb_tuiles.test.js`.
