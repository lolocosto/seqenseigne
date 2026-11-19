# Redémarrage v0.60.2 — tests courts en QCM, règles d'import des tests courts, rituels hors de l'atelier

Delta par rapport à 0abb41f « v0.60.1 » (déployée et poussée par Laurent). Brief :
`col4/BRIEF_V0602.md`. Signalement du 18 novembre, 22 h 39 : après le réimport des lots de 4e
avec les tests courts en QCM, la revalidation groupée du module Évaluations donnait « 16
validé, 16 en échec » — les 16 tests courts : « validation impossible — bareme_qcm_manquant ».

## Ce qui change pour Laurent

- **Barème QCM posé par l'import.** Un exercice QCM (énoncé avec `\begin{seqQcm}`) d'une
  évaluation notée doit avoir, pour être validé, les trois champs du module Évaluations
  « OK / Partiel / KO » (bonne réponse, réponse partielle, mauvaise réponse, par question) ;
  l'import ne posait que les points de l'exercice. Il pose maintenant OK = points d'une
  question (points de l'exercice / nombre de `\seqQcmQuestion` : **1 pt** pour les tests
  courts de 4e), Partiel = 0, KO = 0. Les points de l'exercice (lus par les sujets, le
  barème par objectif et les totaux) ne changent pas : **aucun sujet ne change**.
- **Réparation par un nouvel `--apply` des mêmes lots** : sur un test court en cours, le
  réimport pose les champs manquants et rien d'autre (vérifié sur l'état rejoué : seules les
  colonnes de barème QCM de 50 exercices et la date de modification des 16 tests courts
  changent). Pas d'outil séparé.
- **Évaluation validée identique au lot** : plus d'anomalie « validée dans le module
  Évaluations : non modifiée » (ligne « validée, identique au lot — non modifiée ») ; une
  évaluation validée que le lot modifie reste signalée comme avant.
- **Tests courts** (décisions 16 et 17) : plus d'avertissement « un test court est sur 10 »
  ni « pas de bonus » ; total = somme des points des questions (1 pt par carte). Le bonus de
  1 pt reste contrôlé pour les **évaluations** du cycle 4 ; rien pour la 6e (bonus 2 pts).
- **Figures d'origine** (ajout du coordinateur) : une figure citée par un lot mais absente
  de son dossier `figures\` n'est plus une anomalie si un fichier du même nom est déjà dans
  `images\` de l'appli (images d'origine des exercices repris, ex.
  `N11S04E07_enonce.png`) : ligne « déjà présente dans images (non fournie par le lot) »
  dans la section des figures ; introuvable partout : anomalie, comme avant.
- **Rituels hors de l'atelier** : le cadre « Rituels d'automatismes et séances d'évaluation
  (progression) » n'est plus dans l'onglet Documents à publier de l'atelier Référentiel. Il
  relève des progressions, donc du suivi de classe (jour d'évaluation de chaque classe selon
  son emploi du temps). Le calcul, le document, les routes et l'ordre déjà saisi restent en
  base pour le chantier « progressions » (`doc/ROADMAP.md`).

## Décisions

- **Q1** — bonne réponse = points de l'exercice / nombre de `\seqQcmQuestion` quand cela
  tombe au pas de 0,5 (pas du module Évaluations), sinon 1 pt (avertissement) ; partielle et
  mauvaise = 0. Type et énoncé lus en base (un exercice validé non réécrit garde les siens).
  Pas de clé de lot : aucun usage identifié (une seule bonne réponse par question) ; le
  module Évaluations reste le lieu d'un autre réglage — qu'un réimport sur une évaluation en
  cours remet au barème du lot (le lot fait foi, R6).
- **Q2** — l'import compare et écrit les trois champs QCM (jamais pour un exercice standard) ;
  le diagnostic « À repasser en cours » les compte dans « identique au lot ».
- **Q4 (R4)** — évaluation validée identique au lot : information, pas d'anomalie ; ses liens
  exercice EV → objectif gardent leur rang parmi ceux du lot (sans cela, au rejeu, les
  exercices des tests courts passaient devant ceux des évaluations validées : 110 rangs
  décalés).
- **D16-17** — aucun contrôle de barème pour un test court ; description du document
  « Tests courts » : « QCM sur les cartes d'automatisme de la partie, 1 pt par carte ».
- **FIG** — `copier_figures` : figure absente du lot, présente dans `images\` → signalée,
  rien n'est copié ni remplacé ; absente partout → anomalie.
- **RIT** — cadre retiré de l'interface (HTML, chargement, fonctions `atelRefRituels*`) ;
  gardés : `services/progression_rituels.py`, routes `/api/progression-rituels/…`, producteur
  `rituels_progression`, données saisies.

## Marche à suivre (Windows)

1. Fermer l'appli, décompresser `seqenseigne_v0_60_2_delta.zip` à la racine (le dossier
   `appli\` du zip sur `appli\`), puis depuis `appli\` :
   ```
   ..\outils\python\python.exe .\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
   ```
2. **Réparer les 16 tests courts** (lots QCM déjà dans `..\reference\lot4e\`, tests courts
   restés en cours) — essai à blanc, puis application :
   ```
   ..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11
   ..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11 --apply
   ```
   Essai : pas de section « À repasser en cours » ; application (sauvegarde et journal
   écrits par l'outil) — sur la copie : 0 anomalie, 0 avertissement, 16 tests courts « mise
   à jour … QCM : n exercice(s), barème bonne/partielle/mauvaise posé », 16 évaluations
   « validée, identique au lot ». Si l'essai liste des éléments à repasser en cours, faire
   comme en v0.60.1 (multisélection, « ⟲ En cours ») puis relancer.
3. `.\lancer.bat atelier` ; Ateliers › portée Niveau › 4ème › Évaluation : clic sur la
   première, Maj+clic sur la dernière, « ✓ Valider » → sur la copie : 32 validé, 0 échec
   (130 exercices EV validés). Séquences encore en cours : Séquence › A1…E1 › « ✓ Valider ».
4. Rien à recompiler pour le contenu (sujets identiques au caractère près) ; les tests
   courts peuvent apparaître « à recompiler » (date de modification) : le PDF obtenu est le
   même.

## Pièges

- Un barème QCM réglé à la main dans le module Évaluations (ex. partielle 0,5) est remis au
  barème du lot par un réimport tant que l'évaluation est en cours (le lot fait foi).
- Les points d'un exercice QCM restent dans la base mais le module Évaluations n'affiche
  pour lui que OK / Partiel / KO (inchangé).
- Un référentiel externe ou interne garde l'ordre des parties déjà saisi : il n'est plus
  modifiable depuis l'interface (API seulement) jusqu'au chantier des progressions.

## Fichiers

Modifiés : `outils/import_lot6e.py`, `services/gabarits_documents.py`,
`services/evaluations_v2.py` (docstring), `static/atelier_referentiel.js`,
`tests/test_v0_60_0_version2_fiches.py`, `tests_js/v0_60_0_rituels_type_evaluation.test.js`,
`tests_js/v0_60_1_suite_fiches.test.js`, `doc/ETAT_COURANT.md`, `doc/ROADMAP.md`,
`paquet/CHANGELOG.md`. Nouveaux : `tests/test_v0_60_2_tests_courts_qcm.py`,
`tests_js/v0_60_2_rituels_hors_atelier.test.js`, `doc/redemarrage_v0_60_2.md`. Aucun fichier
supprimé.
