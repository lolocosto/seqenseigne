# Redémarrage v0.53.1 — Mises en route en parties ; lots M01 à M07

## Besoin (Laurent, 22 octobre 2026)

> « M01 comporte ses 4 objectifs dans une seule partie, ce qui oblige à les traiter sur un seul
> créneau dans la progression. Or ils ne sont pas logiquement liés : il faut pouvoir les traiter
> à des moments différents de l'année ⇒ 4 parties avec chacune son objectif. »

Décisions et format : `FORMAT_LOT_MER_v2.md` (lots) ; `outils/ref6e_v2.md` (recopie à
l'identique de `col6/ref6e_v2.md`, section « Mises en route » : codes renumérotés,
« — partie n » en fin de ligne d'objectif, paragraphe « Décision du 22 octobre 2026 »).

## 1. Décisions

- **MR1 révisé** — Une séquence `Mnn` a autant de parties que ref6e\_v2 ; une partie par
  objectif, sauf les paires liées (M02 proportion → pourcentage, M03 durées → horaires, M05
  solides → perspective et patron). Codes de la règle du principal : partie p à partir de
  (p − 1) × 10 + 2 (M01-02, M01-12, M01-22, M01-32 ; le chiffre 1 reste réservé au « Cours »,
  toujours absent d'une Mnn, MR1b). `import_lot6e_mer.referentiel_mer` lit la partie
  (« — partie n » ; sans marque : partie 1).
- **P1 — Libellé de partie** : colonne `sequence_parties.libelle` (TEXT, '' par défaut ;
  migration idempotente `mises_en_route_6e.migrer`, au démarrage et dans l'import), remplie
  par `parties[].titre` du lot. Aucune table nouvelle (`repartition.py` inchangé) ; rien ne
  change pour les séquences existantes (libellés des parties du principal : toujours
  `objectifs_6e.json`).
- **MR3 révisé (P2) — Une fiche de cours par partie** : fiche de résumé sans objectif de la
  séquence, attachée (`objectif_fiches`) aux objectifs de sa partie — comme la fiche de cours
  du principal l'est au « Cours ». Version complète (MR4) : par partie. Une fiche sans
  objectif attachée à aucun objectif est une ancienne fiche de séquence (v0.53.0) : retirée
  par l'import si elle n'est pas validée, signalée par la validation sinon.
- **P3 — Un test court par partie** : la partie d'un test est celle de ses objectifs évalués
  (`evaluation_objectifs`) ; la clé `partie` du lot est contrôlée (écart, test sur deux
  parties, partie sans test : signalés). Sous-titre du test : « Mise en route n, partie p ».
- **MR5 révisé — Documents par partie** (onglet « Rendu PDF » de la séquence Mnn, liste
  « Partie », option `partie` de la route du livret ; vide : toute la séquence) : fiche de
  cours (toutes les fiches à la suite, une par page, sans partie), planche des exercices de
  séance 2/3/4 par A4, test court (choisi par partie, sujet A/B), plan de séquence (par partie,
  ou toute la séquence partie par partie).
- **MR6 révisé — Validation par partie** : exigés : fiche de cours de chaque partie, au moins
  un exercice MR par objectif, chaque MR relié à un objectif de la séquence ; avertissements :
  exercices ≠ séances (séquence, partie, objectif), partie sans test court, ancienne fiche de
  séquence. **Affichée dans l'atelier** : onglet « Rendu PDF » d'une Mnn (contrôle par partie),
  lu sur la nouvelle route `GET /api/v2/livret-sequence/<niveau>/<Mnn>/mer` (blueprint
  `livret_sequence`, catégorie « atelier » de `services/profils.py`).
- **I-MR7 — Restructuration des séquences importées avec l'ancienne structure** (cas de
  Laurent : M01 importé en v0.53.0 en une partie, rien de validé). Choix : **dans l'import**
  (`import_lot6e_mer.restructurer_anciennes_mer`, appelée par `import_lot6e.py` avant les
  lots, pour **toute** séquence N09/Mnn de la base, qu'un lot l'accompagne ou non) plutôt
  qu'une migration au démarrage : elle a besoin de ref6e\_v2, se voit à l'essai à blanc, a sa
  sauvegarde et son journal. Une séquence dont les objectifs sont exactement 01…0k alors que
  ref6e\_v2 en donne k reçoit ses parties et ses codes **au rang** (M01-01 → 02, 02 → 12,
  03 → 22, 04 → 32 ; la table « Anciens codes » de ref6e\_v2 dit la même chose, un test le
  vérifie) : **mêmes objectifs** (identifiants), donc exercices MR, liens, fiche et tests
  gardés, aucun numéro changé (R2). Élément validé (séquence-niveau, MR, EV, fiche, test
  court) : rien n'est touché, signalé. Correspondances dans le journal (`restructuration`).
  Structure ni ancienne ni nouvelle : signalée, non touchée. Idempotente.
- **F1 — Format d'un exercice de séance** (demande du 22 octobre, lots M04, M05, M06, M07 :
  exercices à figure en demi-A4) : colonne `exercices.format_planche` ('' = quart d'A4,
  'demi' ; migration idempotente `mises_en_route_6e.migrer`). **Clé de lot `format`**
  (« quart » | « demi », facultative) ; à défaut, « demi-A4 » dans `notes` donne « demi »
  (information dans le compte rendu), sinon « quart » ; valeur inconnue : signalée, quart. La
  planche place les quarts à 2, 3 ou 4 par A4 (choix de l'onglet), puis les demi-A4 à 2 par
  A4, chacun sur ses propres feuilles (jamais deux formats sur une feuille), dans l'ordre des
  séances, pour une partie ou toute la séquence.
- **P5 — Titre du bandeau** : macro `\seqDefinirTitreCM{titre}` (module v0.10) ; la planche
  émet `\seqDefinirTitreCM{MISE EN ROUTE}` pour toute Mnn sauf M01 (« CALCUL MENTAL »). Les
  lots n'ont rien à écrire ; un `\renewcommand{\seqTitreCM}` local dans un groupe garde la
  priorité (M06 « GESTION DE DONNÉES »).
- **Tests courts : bonus hors total, dans la limite de 10** : l'import signale un barème hors
  bonus ≠ 10 (anomalie) et note un bonus de plus d'un point (information, pas un écart) ; un exercice dont le corps
  ouvre ou ferme un environnement hors de lui (minipage à cheval sur deux `\seqExoEval`) est
  signalé : chaque exercice est rendu seul, la compilation échouerait.
- **Lot au format de la v0.53.0** (fiche de cours au premier niveau) : refusé (signalé).
- **Numérotation 201+** (audit) : l'arbre du niveau de l'atelier des référentiels affichait
  « S201 » pour M01 et « S101 » pour une archive X01 (`atelier_referentiel.js`, deux
  endroits) : il affiche désormais le code `Mnn` / `Xnn` (`atelRefCodeSequence`, inchangé pour
  les Snn et le cycle 4). Ailleurs : listes de l'atelier par code (séquences du cycle,
  séquences-niveaux, rendu par lot) ; test court « Mise en route n » (v0.53.0) ; plans de
  travail et livret du cycle 4 réservés aux Snn — rien d'autre n'affiche le numéro.

## 2. Import

Même commande ; les lots `Mnn` au format v2 (`FORMAT_LOT_MER_v2.md`, docstring de
`outils/import_lot6e_mer.py`). L'essai à blanc montre, section « == M01 == », la
restructuration puis l'import (parties, libellés, fiches par partie, ancienne fiche retirée,
exercices, tests, contrôle par partie) ; « == Documents… » : anciens tests courts retirés
(`evaluations_retirees`), leurs EV orphelins retirés, nouveaux tests.

## 3. Module LaTeX

`seqenseigne-style6e` **v0.10** (`paquet/`, `.sty` régénéré, `CHANGELOG.md`,
`services/style6e.py`) : `\seqDefinirTitreCM{titre}` (P5) et `\seqLocItemGeo{contenu}`
(macro locale du lot M05, item numéroté sans ligne de recherche, argument long comme le
`\providecommand` du lot). Les lots M01–M04, M06 et M07 n'ont pas de macro locale nouvelle.
**`tex seqenseigne.ins` à relancer dans `reference\paquet`.**

## 4. Corrections trouvées à l'assemblage

- Ligne de référence d'un exercice de séance sans marqueur calculatrice (géométrie) :
  « `\hfillMR07` », macro inconnue (planches M04 et M05 non compilées ; bug de la v0.53.0,
  invisible avec M01 dont tous les exercices sont marqués) → `\hfill{}`.
- Deux tests courts au même titre dans deux séquences (« Test court --- Aires », M03 et M04) :
  une évaluation étant retrouvée par son titre, chaque import réécrivait celle de l'autre
  (second `--apply` non idempotent) → l'import refuse un test court dont le titre est celui
  d'une évaluation d'une autre séquence, et ne retire jamais (`evaluations_retirees`)
  l'évaluation d'une autre séquence (signalé : renommer dans le lot). Lot M04 corrigé.
- Tests courts M05 et M06 dont des minipage enjambaient deux `\seqExoEval` : signalés par
  l'import (lots corrigés).

## 5. Résultats

- **Import** (base de test : copie de la v0.53.0 migrée et importée, S01–S13 et M01 dans
  l'ancienne structure) S01–S13 + M01–M07 : essai à blanc (base intacte), `--apply`, second
  `--apply` sans changement ; M01 restructurée (mêmes objectifs, 24 MR inchangés, ancienne
  fiche et 2 anciens tests retirés, 6 EV orphelins retirés) ; 7 séquences, 22 parties,
  25 objectifs, 131 exercices MR, 22 tests courts, 22 fiches de cours (+ versions
  complètes) ; contrôle MR6 « complète » pour les 7 ; seules anomalies : les 3 prérequis du
  cycle 4 déjà connus. Détail : `recap_mer.md`, `apercu_import.txt` (livraison).
- **Compilation** (route du livret, module v0.10) : pour chaque Mnn, fiche de cours de la
  partie 1, planche à 4 par A4 élève (demi-A4 à 2 par A4), test court de la partie 1 sujet A ;
  M01 : 4 fiches (élève, complète), planche partie 4 (élève, corrigée), test partie 4 (élève,
  corrigé), plan partie 4 et toute la séquence ; M06 planche à 2 par A4 : 30 PDF, 0 échec.
- **Non-régression** (`cmp_v0531.py`, base de test) : 1 026 sorties identiques au caractère
  près entre v0.53.0 et v0.53.1 (cycle 4 : documents, atomes, fiches, cartes, plans, format
  d'échange, éligibilité ; 6e principal : livrets, fiches de cours, corrigés, évaluations,
  plans de travail, atomes, cibles du catalogue).
- **Tests** : voir le rapport de livraison (pytest, vitest) ; `tests/test_v0_53_1_mer_parties.py`
  (37), `tests_js/mer_parties.test.js` (6). Adaptés (changement voulu) :
  `tests/test_v0_53_0_mises_en_route.py` lit le jeu de test au format v2
  (`tests/donnees_v0_53_1/lot6e/M01/M01.json`) ; version du module v0.9 → v0.10 (5 tests).

## 6. Reste à faire

- Côté classe : publication d'une mise en route comme référentiel « mer » (une partie Mnn =
  un bloc de séances placé librement dans la progression de mise en route) ; correspondance
  avec M2026\_N09.
- Atelier : saisie du format (quart/demi) d'un exercice MR et du libellé de partie dans
  l'interface (aujourd'hui par le lot).

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et `reference\lot6e\…`.
2. Module LaTeX : `cd reference\paquet` puis `tex seqenseigne.ins`.
3. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py` (essai à blanc :
   sections « == M01 == » à « == M07 == »), puis
   `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.
4. Lancer l'appli ; Atelier › séquence N09/M01 › onglet « Rendu PDF » : contrôle par partie,
   liste « Partie ».
