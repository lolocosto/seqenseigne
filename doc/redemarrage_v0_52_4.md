# Redémarrage v0.52.4 — Le gabarit devient un « modèle de référentiel »

## Besoin

Laurent a précisé (19 octobre) que le gabarit ne dépend pas du cycle : c'est
un **modèle de conception et de mise en forme**, que tout référentiel de N09
à N12 peut choisir, et que le concepteur choisit clairement à la création.

- **« Notions et méthodes »** (valeur technique `cycle4`) : notions et
  méthodes rattachées aux objectifs ; livrets du cycle 4.
- **« Fiches de résumé par objectif »** (valeur technique `sixieme`) : pas de
  notions ni de méthodes ; une fiche de résumé par objectif (à compléter dans
  le livret d'exercices, complète dans le plan de travail, distribuée pour le
  cahier de cours) ; séries TP, AC, AT, EV ; évaluations par compétence,
  sujet B dans la remédiation.

L'audit du 19 octobre (lecture seule sur a89223b) a relevé quatre défauts
bloquants (atelier qui retombait sur le défaut du niveau une fois le
référentiel validé, documents de l'autre modèle comptés, pas d'objectif sans
méthode dans l'assemblage, interface pilotée par « N09 ») et des défauts
gênants (« Méthode (manquante) », « 6e » en dur dans le module LaTeX, nom de
séquence C03/C04 ambigu).

## Décisions

- **M1 Noms des modèles** (`services/gabarits_documents.LIBELLES_GABARITS`,
  `MODELES`) : « Notions et méthodes » et « Fiches de résumé par objectif »,
  avec une description (documents produits, séries, règles de complétude)
  affichée à la création et dans « Documents à publier ». Les valeurs
  `cycle4` / `sixieme` restent en base et dans le format d'échange. Les
  libellés du catalogue perdent « (6e) » ; les clés de types ne changent pas.
  Route `GET /api/gabarits-documents` (modèles + modèle de l'atelier de
  chaque niveau ; catégorie structure).
- **R1b Référentiel de l'atelier d'un niveau**
  (`gabarits_documents.referentiel_atelier_du_niveau`) : le référentiel
  interne principal du niveau **quel que soit son état sauf « annule »**, le
  plus récent (version décroissante, puis id). Avant : « en_cours »
  seulement. Utilisé par `gabarit_atelier_du_niveau` (livret, plans de
  travail, évaluations, rendu d'atome) et `livret_sequence_6e.options_livret`
  (numérotation).
- **D2 Documents du modèle seulement** (`types_du_referentiel`) : la
  validation, le figeage (trace) et la publication (format d'échange)
  ignorent les documents d'un autre modèle, même actifs.
- **M2 Validation d'une séquence au modèle « Fiches »**
  (`v2_edition._valider_sequence_hook`) : par objectif d'exercices, au moins
  un exercice F et un exercice A, critères F et A (critère E seulement si
  l'objectif a des exercices E), fiche de résumé de l'objectif
  (`fiches_resume.objectif_id`). Série E facultative. « Notions et méthodes »
  garde F, A et E.
- **M3 Validation du référentiel**
  (`referentiel_validation._compter_atomes_non_valides`) : au modèle
  « Fiches », ni notions, ni méthodes, ni cartes ; archives `Xnn` jamais
  comptées, quel que soit le modèle (le cycle 4 n'en a pas).
- **M4 Partie « cours » = fiches de résumé** au modèle « Fiches » : synthèse
  Pronote (« Cours : fiches de résumé (…) », choix enregistrés dans
  `seance_contenu.fiches`, colonne ajoutée de façon idempotente) et format
  d'échange (`partie.fiches`). Fiches d'une partie = fiche de chaque objectif
  puis celles rattachées à l'objectif « Cours » (même règle que le livret,
  L2). Côté classe : titres importés de nature `fiche`.
- **F2 Format d'échange 1.2** (`partie.fiches`, facultatif) ; un document
  déclare la plus petite version qui décrit son contenu : un référentiel
  « Notions et méthodes » reste en **1.1**, sans `fiches`, même empreinte.
  Schéma et `doc/format_referentiel.md` à jour.
- **M5 Type « connaissance »** d'un objectif interne : règle de l'objectif
  Cours (code `(n-1)1`) et non plus le rang dans la partie.
- **M6 Nom par défaut de l'objectif Cours : « Connaître le cours »** (deux
  modèles ; création dans l'assemblage, préférences, référentiel externe,
  `outils/objectifs_6e.json`). Une configuration qui garde exactement
  l'ancien défaut (« Connaître les notions et les méthodes ») reçoit le
  nouveau (`Configuration.charger`). Les objectifs existants de N10 à N12 ne
  sont pas renommés ; les objectifs Cours de N09 le sont par
  `import_lot6e.py` (séquences non validées seulement).
- **G2b Modèle modifiable en « en_cours » et « valide »** (un référentiel
  validé est réévalué aussitôt) ; « (figé) » à partir du verrouillage ;
  avertissement s'il reste des documents actifs de l'ancien modèle ; choix
  non proposé pour un référentiel externe ou MER ; modèle affiché dans la
  liste des référentiels.
- **I2 Interface pilotée par le modèle du niveau**
  (`static/gabarits_atelier.js` : `atlModeleFiches(niveau)`, données de la
  route M1) : séries EV/TP/AC/AT, sélecteurs Version et Sujet de l'atelier
  d'exercices et du module Évaluations. Plus aucun test sur « N09 ».
- **A5 Assemblage au modèle « Fiches »** : bouton « + Nouvel objectif »
  (objectif sans méthode ; le code de l'objectif Cours est réservé,
  `reserver_cours`) ; zone « Fiche de l'objectif »
  (`PUT /api/v2/objectifs/<id>/fiche`, une fiche par objectif, même
  séquence) ; zones Notions, Méthode et cartes d'automatisme masquées ;
  zones EV, TP, AC, AT ;
  barre latérale : fiches de résumé de la séquence au lieu des notions. La
  route de lecture de l'assemblage ajoute `modele`, `fiche` et
  `exos_documents` (`v2_lecture.enrichir_pour_assemblage`) sans toucher à
  `lire_sequence_par_niveau` (lue par les livrets). Arbre « Référentiel » :
  présence de la fiche, ni méthode, ni notions, ni cartes.
- **T1 Niveau paramétrable** (`paquet/seqenseigne-style6e.dtx` **v0.5**) :
  `\seqNiveauCourt` (`6e`) et `\seqNiveauExposant` (`6\textsuperscript{e}`)
  remplacent « 6e » écrit en dur (couverture du livret, `\seqIdentEleve`,
  `\seqTitreTravailSix`, `\seqTitreComplementSix`) ; chaque document du
  modèle « Fiches » les redéfinit d'après `param_niveaux.nom_court`
  (`livret_sequence_6e.macros_niveau`) ; sous-titre du plan de travail aussi.
  Rendu de la 6e inchangé.
- **L6b Nom de séquence** (`v2_lecture`) : la séquence du cycle du niveau
  (`param_niveaux.cycle_code`) est préférée ; la 6e reçoit son nom de C03.

## Code

Nouveaux : `static/gabarits_atelier.js`, `tests/test_v0_52_4_modeles.py`.
Modifiés : `services/gabarits_documents.py`, `referentiel_validation.py`,
`referentiel_figeage.py`, `format_referentiel.py`, `import_publication.py`,
`synthese_seance.py`, `v2_edition.py`, `v2_lecture.py`, `configuration.py`,
`livret_sequence_6e.py`, `plan_travail_6e.py`, `style6e.py`, `profils.py` ;
routes `referentiel_documents`, `v2_edition`, `v2_lecture`,
`referentiel_principal_externe` ; `schemas/referentiel-1.json` ;
`static/atelier_exercice.js`, `atelier_evaluation_oo.js`,
`atelier_referentiel.js`, `referentiel_unifie.js`,
`atelier_seqniv_assemblage.js`, `travail.js`, `app.js`, `referentiel_pe.js`,
`app.css` ; `templates/index.html` ; `outils/objectifs_6e.json` ;
`paquet/seqenseigne-style6e.dtx`, `.sty` (régénéré), `paquet/CHANGELOG.md` ;
`doc/format_referentiel.md`.
Tests adaptés (comportement changé volontairement) :
`test_v0_52_1_gabarits_documents.py` (libellé, format 1.2),
`test_v0_52_2_documents_6e.py` (libellé), `test_v0_52_3_retours.py`
(`\seqNiveauCourt`), `test_v0_10_assemblage.py` (nom par défaut) ;
`tests_js/series_documents_6e.test.js`, `tests_js/gabarit_documents.test.js`.
Migration : colonne `seance_contenu.fiches` (idempotente) ; aucune table.

## Vérifications

- Cycle 4 : 397 sorties identiques au caractère près entre v0.52.3 et
  v0.52.4 sur la base atelier v0.52.2 migrée (128 documents des
  référentiels N10–N12, 201 rendus d'atomes, 42 plans de travail, format
  d'échange — empreinte et version 1.1 — et éligibilité des 13
  référentiels) ; seuls changent les livrets de 6e
  (deux lignes `\renewcommand{\seqNiveau…}`). Test permanent étendu : les 7
  `.tex` figés restent identiques avec un référentiel validé ou verrouillé,
  des documents actifs de l'autre modèle et un référentiel annulé au modèle
  « Fiches ».
- Rendu de la 6e : livret S01 (33 p.) identique au pixel près entre
  v0.52.3 et v0.52.4 ; en-têtes de travail personnel, d'activité
  complémentaire, d'évaluation et couverture identiques.
- Livret N10 S01 au modèle « Fiches » (référentiel de test) : « Niveau 5e ».

## Hors périmètre

- `outils/import_lot6e.py` reste limité à N09 (paramétrage plus tard).
- Mises en route non concernées.

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`).
2. Module LaTeX : copier `appli\paquet\seqenseigne-style6e.dtx` dans
   `reference\paquet\`, puis dans `reference\paquet\` : `tex seqenseigne.ins`.
3. `.\lancer.bat atelier` depuis `appli\` (migration de la colonne au
   démarrage). Conception › Niveau › Référentiel : vérifier le modèle de
   chaque référentiel ; N09 : « Fiches de résumé par objectif ».
4. Facultatif (renommer les objectifs Cours de N09) :
   `..\outils\python\python.exe .\outils\import_lot6e.py` puis `--apply`.
