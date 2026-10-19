# Redémarrage v0.52.3 — Retours de Laurent sur la v0.52.2

## Besoin

Quatre retours du 19 octobre sur la v0.52.2 déployée, plus les corrigés des
lots S01–S03 rédigés (209 corrigés, à réimporter).

1. Une activité d'approche importée (ex. N09/S01/AE03), enregistrée avec un
   corrigé, disparaît de la liste ; aucun bouton de série n'est sélectionné.
2. Module Évaluations : l'onglet « Rendu PDF » garde le dernier PDF compilé
   quand on change d'évaluation.
3. TP, AC, AT (et EV, F, A, E, AE) de 6e compilés au format du cycle 4 dans
   l'atelier d'exercices.
4. Plan de travail d'une séquence de 6e au format du cycle 4.

## Causes

1. `services/atomes._SERIE_VERS_CODE` faisait correspondre « approche » à
   `EA` alors que tout le reste (base, import, livrets, JS) utilise `AE`
   depuis v0.18.3. L'enregistrement envoie `serie='approche'` :
   `modifier_exercice` voyait un code différent, réécrivait `serie_code='EA'`
   et redonnait un numéro (AE03 → EA01). La liste lisait le code `EA01`
   comme une Exploration (section repliée) ; l'import 6e, qui retrouve un
   exercice par (niveau, séquence, code, numéro), ne le retrouvait plus et
   en aurait créé un doublon. En-tête : le bouton s'appelait
   `atl-serie-AP`, `changerSerie` cherchait `atl-serie-approche` → jamais
   sélectionné. (`static/app.js:3424`, code mort écrasé par
   `atelier_exercice.js`, aligné aussi.) `sequence` n'était pas touchée.
2. `AtelierEvaluation` surcharge `basculerOnglet` et la sélection sans
   appeler `verifierCacheEtAfficher`, et n'avait pas de route
   `/rendu-pdf/info`. Les autres ateliers (exercice, notion, méthode, fiche,
   carte) passent par `AtelierEditeur.ouvrirItem → basculerOnglet →
   verifierCacheEtAfficher` : pas de défaut.
3. `latex_rendu_atome.generer_tex_par_type` n'avait que le rendu du cycle 4.
4. `routes/plans_de_travail.py` n'appelait que le plan du cycle 4.

## Décisions

- **A1 Rendu d'atome 6e** (`services/rendu_atome_6e.py`, appelé par
  `generer_tex_par_type`) : gabarit de la règle R1
  (`gabarit_atelier_du_niveau`). TP, AC, AT → document du catalogue
  (`documents_6e`) ; EV → `\seqExoEval` sujet A ou B, barème et compétence
  de son évaluation ; F, A, E → `seqExoSix` + remédiation ; AE →
  `seqActiviteSix`, au numéro du livret 6e. Archives `Xnn` : rendu du
  cycle 4. Cycle 4 : même `.tex`.
- **A2 Réparation par un outil** (`outils/reparer_series_approche.py`,
  essai à blanc puis `--apply`, sauvegarde `.db` + journal JSON dans
  `sauvegardes\`, idempotent), pas une migration au démarrage : le numéro
  d'origine se déduit des liens (`origin_num` de
  `partie_exos_revision_approche`, puis d'`objectif_exos`) et peut être
  pris par un doublon ; Laurent voit chaque correspondance. Numéro pris ou
  inconnu → prochain numéro AE libre, signalé. Un exercice relié comme
  activité mais rangé en F/A/E est seulement signalé. **À lancer avant tout
  réimport des lots.**
- **A3 Options du rendu d'atome** (query string) : `version`
  eleve|corrigee (défaut élève), `sujet` A|B (EV). Sélecteurs dans la barre
  du rendu de l'atelier d'exercices pour N09 (sujet : série EV seulement),
  transmis aussi à l'information de cache et au « .tex brut ».
- **A4 Garde** : `modifier_exercice` ne recalcule code et numéro que si la
  série change vraiment (ou si le code est vide).
- **E4 Évaluations** : route `GET /api/evaluations/<id>/rendu-pdf/info`
  (blueprint `evaluations`, catégorie atelier) ; `_synchroniserRendu`
  (changement d'évaluation : génération invalidée, placeholder, sélecteurs,
  rechargement si l'onglet est ouvert) ; l'onglet Rendu et les sélecteurs
  sujet/version rechargent le PDF.
- **P1 Plan de travail 6e** (`services/plan_travail_6e.py`) : route de
  l'atelier → paramètre `gabarit`, sinon R1 ; catalogue `sixieme` :
  `plans_travail_6e`, une cible par séquence, option `fiches`
  (`texte_complet` défaut | `titre`). Numéros = ceux du livret 6e publié
  par le même référentiel (options de son `livret_sequence_6e`), relevés
  pendant l'émission du livret (`numeros_livret`).
- **P2** Étiquette d'objectif `S01-02` (bandeau du livret, barème des
  évaluations) au lieu du « C1 » de l'équipe.
- **P3** Marques : O sans marque (F), ( ) A, [ ] remédiation (répétition),
  { } E (absente des plans de l'équipe ; légende complétée si besoin).
- **P4** TP/AC/AT après le dernier objectif relié ; sans objectif :
  « Synthèse et évaluation » (fiches de cours, évaluations de la séquence
  avec barème par compétence, ramassage des TP).
- **P5 Rien d'inventé** : référence du manuel, pages du livret (« livret
  p x »), nombre de pages du livret, déroulé des activités (sous-puces),
  durée si les séances ne sont pas renseignées (N09 : toutes à 0).

## Code

Nouveaux : `services/rendu_atome_6e.py`, `services/plan_travail_6e.py`,
`outils/reparer_series_approche.py`, `tests/test_v0_52_3_retours.py`,
`tests_js/retours_v0_52_3.test.js`.
Modifiés : `services/atomes.py`, `latex_rendu_atome.py`,
`livret_sequence_6e.py` (numéros relevés, `options_livret`,
`document(preambule_sup=…)` : sortie inchangée), `gabarits_documents.py`,
`orchestrateur_compilation.py`, `referentiel_documents_compilation.py`,
`peremption_atomes.py` ; routes `rendu_atome`, `evaluations`,
`plans_de_travail` ; `static/atelier_exercice.js`, `atelier_editeur.js`,
`atelier_evaluation_oo.js`, `app.js` ; `templates/index.html`.
Tests adaptés : `test_v0_52_1_gabarits_documents.py`,
`test_v0_15_2_6_peremption_atomes.py` (nouveau type).
Hors `appli\` : `reference\lot6e\S01…S03` (lots complétés des corrigés).
Aucune table, aucune migration.

## Vérifications

- Cycle 4 : 377 `.tex` identiques au caractère près entre v0.52.2 et
  v0.52.3 sur la base atelier de démonstration importée (128 documents de
  référentiels, 201 rendus d'atomes N10–N12, 42 plans de travail) ; livrets
  6e S01–S03 élève/corrigé identiques aussi.
- Scénario : activité abîmée comme le faisait la v0.52.2 → essai d'import
  sans réparation = doublon annoncé ; réparation puis import : aucun
  doublon, corrigés du lot appliqués, second essai tout inchangé.
- Compilés : plans de travail 6e S01–S03, rendus d'atome TP, AC, AT, EV
  (sujet B), F, A, AE.

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et
   `reference\lot6e\…`.
2. Depuis `appli\` :
   `..\outils\python\python.exe .\outils\reparer_series_approche.py`
   puis, si des exercices sont listés,
   `..\outils\python\python.exe .\outils\reparer_series_approche.py --apply`.
3. Ensuite seulement :
   `..\outils\python\python.exe .\outils\import_lot6e.py` puis
   `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.
4. `.\lancer.bat atelier` ; Conception › Référentiel 6e › Documents à
   publier : cocher « Plans de travail (6e) ».
