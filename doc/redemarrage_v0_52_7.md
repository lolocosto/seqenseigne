# Redémarrage v0.52.7 — Marqueurs « ordinateur » et « calculatrice » des exercices

## Besoin (Laurent, 20 octobre 2026)

> « On peut marquer les exercices qui nécessitent un ordinateur au travers de
> toutes les séquences, que ce soit pour Scratch, GeoGebra, le tableur ou
> autre, comme on marque déjà quand la calculatrice est interdite. Ça
> permettrait de le faire apparaître pour l'élève dans le livret d'exercice
> (au niveau de l'entête de l'exercice lui-même), et puis aussi dans le plan
> de travail de la séquence pour l'enseignant, et puis aussi dans l'appli de
> suivi de classe, au niveau du tableau de bord, pour se rappeler qu'il faut
> réserver les ressources (salle info, chariot mobile…). »

Validé : on marque dès maintenant les exercices des séquences principales
(lots S01 à S13). Le tableau de bord de l'appli de classe attend la
construction des progressions : **pas fait**, mais les données sont publiées
et stockées côté classe pour le brancher simplement.

## Données

Deux colonnes de `exercices`, migration idempotente
`services/marqueurs_exercices.migrer` (appelée au démarrage, après le DDL, et
par l'outil d'import) :

- `ordinateur` : `''` (aucun) | `scratch` | `geogebra` | `tableur` | `autre` ;
- `calculatrice` : `''` (non précisé) | `autorisee` | `interdite`.

## Décisions

- **M1 Le marquage porte sur l'énoncé principal ; la remédiation et le sujet B
  suivent** (pas de champ propre). C'est la solution la plus simple : une
  remédiation ou un sujet B reprend la consigne de l'exercice. Dans le livret
  6e, l'en-tête de la remédiation porte donc les mêmes marqueurs ; dans le
  plan de travail, la mention n'est écrite qu'une fois (exercice principal).
- **M2 Valeurs fermées** (`services/marqueurs_exercices.py`) : l'atelier refuse
  une valeur inconnue (400), l'import la signale en anomalie et l'ignore.
- **M3 Liste de l'atelier** (`services/atomes_liste.py`) : la clé `marqueurs`
  n'est ajoutée qu'à un exercice marqué ; le contrat de la liste reste celui
  des 7 clés pour tous les autres atomes. Indicateur discret dans la liste
  (« ⌨ Scratch · calc. interdite », détail en infobulle).
- **M4 Cycle 4 (modèle « Notions et méthodes »)** — audit : le paquet construit
  la boîte de titre de `seqExercice` (et les en-têtes du corrigé et de la
  remédiation, écrits par `\write` avec `\eue`) à partir des options `obj=`,
  `nom=`, `remediation=`. Ajouter une clé au paquet du cycle 4 aurait changé
  `seqenseigne-core-exos` ; la mention est donc ajoutée **en texte** à la
  valeur de `nom=` (ligne 2 de la boîte, poussée à droite :
  `\hfill{\small\upshape (ordinateur~: GeoGebra ; calculatrice autorisée)}`),
  **seulement si l'exercice est marqué** (`latex_rendu_atome.generer_corps_exercice`,
  `livret_recap_exos._generer_corps_exercice_continu`). Aucun changement du
  paquet du cycle 4 ; évaluations du cycle 4 inchangées. Risque faible : le
  texte passe par `\write` sans macro nouvelle (compilé : atome, livret de
  séquence N10/S01, plan de travail).
- **M5 Format d'échange 1.3** : `partie.materiel` (facultatif), liste des
  exercices marqués de la partie (objectif, série, code, séquence, titre,
  marqueurs) ; **absent** quand rien n'est marqué. Un document déclare la plus
  petite version qui décrit son contenu (F2) : sans marqueur, 1.1 ou 1.2 et
  même empreinte qu'en v0.52.6. Côté classe : table
  `referentiel_materiel_publie` (classée dans `TABLES_CLASSE`), remplie à
  l'import d'une publication, lue par `import_publication.materiel_publie(conn,
  referentiel_id, seq_code, partie_numero)`.
- **M6 Figeage** (`referentiel_figeage`, trace JSON) : `ordinateur` /
  `calculatrice` ajoutés aux exercices de la trace seulement s'ils sont posés.
- **M7 Import des lots** (`outils/import_lot6e.py`) : clés facultatives
  `ordinateur` et `calculatrice` de chaque exercice F, A, E, activité AE,
  document TP, AC, AT ; pour une évaluation, sur l'entrée d'évaluation (sujet
  A, sinon B), appliquées à tous ses exercices EV. Écrites comme le reste du
  contenu : **clé absente = non marqué** (le lot fait foi), mise à jour
  idempotente, exercice validé non touché (anomalie habituelle). Les
  marqueurs n'entrent **pas** dans la comparaison de contenu de R2 (un EV
  validé de même contenu garde son numéro). Le rapport donne par séquence une
  ligne « marqueurs : … ». Les colonnes sont ajoutées par l'outil si la base
  n'a pas encore été ouverte par la v0.52.7.
- **M8 Plans de travail** : 6e (`plan_travail_6e`) et cycle 4
  (`livret_plans_de_travail`), mention dans la ligne de l'exercice
  (« 3 (ordinateur : Scratch) ») et encadré « Matériel à prévoir » (6e : en
  tête du plan ; cycle 4 : en tête de chaque page de partie), une ligne par
  outil puis la calculatrice autorisée. La calculatrice interdite n'est pas du
  matériel : elle reste dans la ligne. Rien n'est émis sans marqueur.

## Rendus 6e — module `seqenseigne-style6e` v0.7

`\seqMaterielSix{outil}{calculatrice}` (écran + « Ordinateur --- Scratch »,
calculatrice + « calculatrice autorisée » ou calculatrice barrée +
« calculatrice interdite » ; police droite, petits caractères gris foncé),
`\seqOrdinateurSix`, `\seqCalculatriceSix`, `\seqPictoOrdinateurSix`,
`\seqPictoCalculatriceSix(*)` : documentées, `\changes{v0.7}`, `.sty`
régénéré par `tex seqenseigne.ins`, liste `services/style6e.MACROS`. Émis par
`livret_sequence_6e._titre_exo` (exercices, activités, remédiations : livret,
corrigés, rendu d'atome 6e) entre le titre et le code. « Autre » s'écrit
« autre logiciel ».

## Évaluations

L'option « Calculatrice » du document évaluation 6e (catalogue, défaut
`interdite`) est inchangée et ne lit pas les marqueurs. **Incohérence
signalée** : une évaluation marquée « calculatrice autorisée » dans le lot
(S11 « Probabilité », S12 « Proportionnalité » dans les lots du 20 octobre)
sort « calculatrice interdite » tant que l'option du document n'est pas
réglée ; l'import le rappelle dans ses informations. À trancher : faire
suivre le défaut de l'option au marquage de l'évaluation.

## Code

Nouveau : `services/marqueurs_exercices.py`, `tests/test_v0_52_7_marqueurs.py`
(21 tests), `tests_js/marqueurs_exercice.test.js`, ce fichier. Modifiés :
`persistence/sqlite_store.py`, `services/atomes.py`, `services/atomes_liste.py`,
`templates/index.html`, `static/atelier_exercice.js`,
`services/livret_sequence_6e.py`, `services/rendu_atome_6e.py`,
`services/latex_rendu_atome.py`, `services/livret_recap_exos.py`,
`services/plan_travail_6e.py`, `services/livret_plans_de_travail.py`,
`services/referentiel_figeage.py`, `services/format_referentiel.py`,
`schemas/referentiel-1.json`, `doc/format_referentiel.md`,
`services/import_publication.py`, `services/repartition.py`,
`services/style6e.py`, `paquet/seqenseigne-style6e.dtx` et `.sty`,
`paquet/CHANGELOG.md`, `outils/import_lot6e.py`, `doc/ETAT_COURANT.md`.
Tests existants adaptés au changement de version (seulement l'assertion de
version) : `test_v0_52_4_modeles` (module v0.7), `test_v0_52_5_objectifs_s05`
(module v0.7), `test_v0_52_1_gabarits_documents` (format 1.3). Une table
nouvelle côté classe, aucune route nouvelle.

## Vérifications

- Cycle 4 : 403 sorties identiques au caractère près entre v0.52.6 et
  v0.52.7 sur la base atelier migrée (aucun exercice du cycle 4 marqué) ;
  tests « golden » du cycle 4 verts.
- Exercices du cycle 4 marqués sur une copie : atome, livret de séquence
  N10/S01 et plan de travail compilés.
- Import S01 à S13 sur la copie migrée de la v0.52.6 : essai à blanc,
  `--apply`, second `--apply` sans changement (voir `apercu_import.txt` de la
  livraison).

## Pour le tableau de bord (à faire avec les progressions)

`import_publication.materiel_publie(conn, referentiel_id, seq_code,
partie_numero)` donne les exercices marqués d'une partie publiée ; il reste à
le croiser avec la progression (séances de la partie / de l'objectif à venir)
et à afficher une tuile « Matériel à réserver » (outil, séance, exercices).
Une publication figée avant la v0.52.7 n'a pas `materiel` : republier le
référentiel (ou attendre le référentiel suivant).

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et
   `reference\lot6e\S01\` à `S13\`.
2. Module 6e v0.7 : copier `appli\paquet\seqenseigne-style6e.dtx` dans
   `reference\paquet\`, puis dans `reference\paquet\` : `tex seqenseigne.ins`.
3. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py`
   (essai à blanc : lignes « marqueurs : »), puis
   `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.
