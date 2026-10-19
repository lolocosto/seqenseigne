# Redémarrage v0.52.5 — Objectifs S01 à S13 (géométrie découpée), module 6e v0.6, lots S04 à S09, page de garde par partie

## Besoin

Le lot S05 « Géométrie plane » (13 objectifs en 5 parties, 130 exercices,
14 activités, 2 TP, 2 AC, 4 évaluations A/B) est prêt. Deux obstacles :
`outils/objectifs_6e.json` ne contenait que S01 à S03 (l'import aurait
refusé le lot : « séquence absente de objectifs_6e.json »), et les énoncés
du lot appellent des macros écrites pendant la conversion (`local.tex`) que
le module `seqenseigne-style6e` ne fournissait pas.

## Décisions

- **O1 Référentiel S01 à S10** (puis S01 à S13 : voir « Découpage de la géométrie ») (`outils/objectifs_6e.json`) : parties,
  objectifs (code, intitulé, critères F, A, E) de toutes les séquences
  S01 à S10, transcrits de `col6/ref6e_v2.md` par la même méthode que S01 à
  S03 en v0.52.0 (critère E commun « Utilise ce savoir-faire pour résoudre
  un problème. », objectif Cours `(n-1)1` « Connaître le cours », M6). S01
  à S03 ressortent identiques ; le fragment `referentiel_S05.json` du lot a
  été contrôlé : identique au markdown. Les échappements Markdown (`\[AB\]`)
  sont retirés. 52 objectifs. Mises en route M01 à M07 : pas ici
  (livraison à part).
- **O2 Séquence sans partie déclarée** (S04, S06, S07, S08, S10 : pas de
  « ### Partie » dans le markdown) : une seule partie, numéro 1, libellé =
  nom de la séquence. Les codes 02, 03… restent en partie 1 ; l'objectif
  Cours est 01.
- **O3 Source versionnée** : copie du référentiel validé dans
  `outils/ref6e_v2.md` (identique à `col6/ref6e_v2.md`, md5
  a5f69c059f4ce99fec7f5216ecb15d1c après le découpage de la géométrie). Un test relit le markdown de façon
  indépendante et exige que le JSON en soit la transcription exacte : si
  le référentiel change, il faut régénérer le JSON (et inversement).
- **S1 Style TikZ `seqLocCorr`** : versé dans le module mais pas dans
  `style6e.MACROS` (un style s'écrit `[seqLocCorr]`, jamais
  `\seqLocCorr` : aucun usage ne serait détecté). Il est listé dans
  `style6e.STYLES_TIKZ`. Les documents du modèle « Fiches de résumé par
  objectif » chargent le module en entier.
- **S2 Module v0.6** (`paquet/seqenseigne-style6e.dtx`) : `\seqLocCadreTrace`,
  `\seqLocAngle`, `\seqLocRapporteur` et `seqLocCorr`, noms gardés (les
  énoncés du lot les appellent), code identique à `local.tex`,
  documentation (section « Géométrie plane (v0.6) ») et un `\changes` par
  macro ; `.sty` régénéré par `tex seqenseigne.ins` (seule différence :
  version et ajouts). `local.tex` n'est donc plus utile : il n'est pas
  livré avec le lot.
- **S3 Macros du lot S04** (même module v0.6, ajout demandé le 19 octobre) :
  styles TikZ `seqLocBarre`, `seqLocBarreR`, `seqLocBarreV`, `seqLocBarreQ`
  (schémas en barres, dans `STYLES_TIKZ`), `\seqLocBloc`, `\seqLocAccolade`,
  `\seqLocBalance`, `\seqLocSac`, `\seqLocMasse`, `\seqLocObjet` (dans
  `MACROS`) ; code identique à `lot6e/S04/local.tex` ; bibliothèque TikZ
  `decorations.pathreplacing` chargée par le module. Le `local.tex` de S06
  ne contient que les macros de S05. Aucun `local.tex` n'est livré.
- **B1 inchangée** : exercices bonus des évaluations selon la règle de
  l'importeur (v0.52.2), suivie par la conversion de S04 à S06.
- **I1 Macro locale absente du module** : l'import (`import_lot6e.py`)
  signale en anomalie toute macro `\seqLoc…` d'un lot que le module ne
  fournit pas (sinon tous les documents de la séquence échoueraient à la
  compilation). Le message d'information cite le module v0.6.

- **C1 Libellé des parties** (`livret_sequence_6e.libelles_parties`) :
  l'atelier ne stocke pas de libellé de partie (`sequence_parties` n'a que
  le numéro) ; le livret le lit dans `outils/objectifs_6e.json`, pour le
  niveau de ce fichier (N09) seulement. Ailleurs : « Partie n ».
- **C2 Page de garde par partie** (demande de Laurent, 19 octobre) :
  `\seqCouvertureLivretSix*{titre}{parties}` (forme étoilée, module v0.6),
  chaque partie en `\seqPartieCouvertureSix{Partie n --- libellé}{liste}` :
  titre de partie, puis ses objectifs avec un trait vertical à gauche de la
  couleur du thème de la séquence (`seqSixTheme`, d'après
  `themes.code_couleur` et `couleurs_themes` ; bleu du module si inconnue).
  Une partie sans objectif de capacité n'apparaît pas. La forme sans étoile
  est inchangée (anciens `.tex`). Le corps du livret ne change pas.
- **C3 Titre de partie** : « Partie n » quand le libellé manque ou répète
  le nom de la séquence (séquence à partie unique, O2).

## Code

Nouveaux : `outils/ref6e_v2.md`, `tests/test_v0_52_5_objectifs_s05.py`
(20 tests), `tests/test_v0_52_5_renumerotation_cycle3.py` (5 tests,
découpage de la géométrie).
Modifiés : `outils/objectifs_6e.json`, `outils/import_lot6e.py`,
`services/style6e.py`, `services/livret_sequence_6e.py`, `paquet/seqenseigne-style6e.dtx`, `.sty`
(régénéré), `paquet/CHANGELOG.md`, `doc/ETAT_COURANT.md`.
Tests adaptés (changement voulu) : `test_v0_52_0_import_lot6e.py`
(22 → 52 objectifs), `test_v0_52_4_modeles.py` (module en v0.6),
`test_v0_52_1_gabarits_documents.py` (page de garde par partie).
Lots : `reference/lot6e/S04/` à `S09/` (`Snn.json` et `figures/`,
vides : toutes les figures sont en TikZ). Aucune migration, aucune table, aucune route.

## Vérifications

- Cycle 4 : 397 sorties identiques au caractère près entre v0.52.4 et
  v0.52.5 sur la base atelier v0.52.2 migrée (documents des référentiels
  N10–N12, rendus d'atomes, plans de travail, format d'échange,
  éligibilité). Seuls changent, volontairement, les 6 livrets 6e S01–S03
  (élève, corrigé), et seulement sur la page de garde (C2).
- Import sur une copie migrée de la base (lots S01 à S06, comme dans
  `reference\lot6e`) : essai à blanc (3 anomalies, toutes « cycle 4
  inchangé : N10/S01 a pour prérequis N09/S0x », déjà connues), `--apply`,
  second `--apply` : base identique au second passage.
- Compilés par les routes de l'appli (paquet généré par
  `tex seqenseigne.ins` dans `reference\paquet`) : livret S05 élève
  (76 p.) et corrigé (91 p.), plan de travail S05 (6 p.), évaluation « Les
  angles » sujet A élève (2 p.), livret S01 (33 p.), livrets S04 (13 p.)
  et S06 (18 p.) élève. Pages de garde S01
  et S05 par partie, rapporteurs, zones de tracé vides
  (élève) / remplies (corrigé) vérifiés en image.

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et
   `reference\lot6e\S04\` à `S09\`.
2. Module LaTeX : copier `appli\paquet\seqenseigne-style6e.dtx` dans
   `reference\paquet\`, puis dans `reference\paquet\` : `tex seqenseigne.ins`.
3. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py`
   (essai à blanc), puis `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.

## Découpage de la géométrie (décisions de Laurent, 19 octobre 2026)

La séquence S05 « Géométrie plane » (13 objectifs, 5 parties) est découpée
en quatre séquences du thème C ; la numérotation par thème est conservée,
les séquences suivantes sont décalées.

| Nouveau | Séquence | Objectifs (ancien → nouveau) |
|---|---|---|
| S05 | Points, segments, droites | P1 Premiers éléments : S05-02, 03, 04 ; P2 Médiatrice : S05-42 → S05-12, S05-43 → S05-13 |
| S06 | Cercles | S05-12 → S06-02 ; S05-32 → S06-03 (option (b) : construction au compas) |
| S07 | Angles | S05-22 à 25 → S07-02 à 05 |
| S08 | Triangles | P1 Triangles : S05-33 → S08-02 ; P2 Droites remarquables : S05-44 → S08-12 |
| S09 à S13 | Symétrie axiale, Gestion de données, Probabilité, Proportionnalité, Pensée informatique | anciennes S06 à S10, mêmes numéros d'objectif |

Thèmes : S05 à S09 en C, S10 et S11 en D, S12 en E, S13 en F. Les
positions relatives de deux droites restent en révisions (pas de partie).
Objectif Cours : `{n-1}1`, « Connaître le cours ».

- **D1 Référentiel** : `outils/ref6e_v2.md` (= `col6/ref6e_v2.md`, md5
  a5f69c059f4ce99fec7f5216ecb15d1c) mis à jour : sections de séquences,
  ordre de progression, contraintes de progression (S08 après S05, S06 et
  S07 ; série A de S06-03 après S07-04 ; S09 après S05 partie 2), tous les
  renvois `Snn-nn` (notions, couverture, alignement, récapitulatif ; les
  mentions « ancien Sxx-yy » d'avant le 18 octobre ne changent pas), table
  de correspondance en fin de document. 13 séquences, 20 parties, mêmes
  52 objectifs (intitulés et critères identiques, vérifié par
  correspondance).
- **D2 `objectifs_6e.json`** régénéré par la même méthode (O3 : transcription
  exacte du markdown, test inchangé dans son principe) ; libellés de partie
  (page de garde) : S05 « Premiers éléments », « Médiatrice » ; S08
  « Triangles », « Droites remarquables » ; S06, S07 : partie unique (O2).
- **D3 Liste du cycle 3** (`import_lot6e.appliquer_cycle3`) : une base qui a
  déjà les dix séquences de la v0.52.0 est mise à jour **sur place** (mêmes
  identifiants) : S05 à S10 renommées et rattachées à leur thème, S11 à S13
  créées ; rapport « renommée (était « … ») ». Idempotent : le second passage
  dit « inchangée » partout.
- **D4 Changement de sens** : si une séquence-niveau du cycle 3 (N07 à N09)
  existe déjà sous un code dont le nom change (contenu de l'ancien sens,
  validé ou non), la séquence n'est pas renommée, une anomalie le dit et le
  lot de ce code n'est pas importé. Sur la base de test (copie de la base
  atelier, S01 à S03 importés), il n'y en a aucune : seules N09/S01 à S03
  existent (vérifié).
- **Lots** (`reference/lot6e/S04` à `S09`) : S05 à S08 construits depuis
  l'ancien lot S05 (archivé), S09 = ancien S06 recodé ; recodage des
  objectifs, `partie`, numérotation continue des exercices par série dans
  chaque séquence, renvois dans les énoncés et corrigés, en-têtes
  « Séquence n ». Évaluations : S05 « Droites, demi-droites, segments » et
  test court « Médiatrice » /10 (2 créations) ; S06 « Cercles et
  triangles » /20 (test « Cercles » + construction de triangles + 1
  création) ; S07 « Les angles » ; S08 test court « Triangles et cercle
  circonscrit » /10 (1 création) ; S09 « Symétrie axiale ». Travaux
  personnels : S05 3, S06 2 (dont L'île au trésor), S07 2, S08 3.
  Activités complémentaires : S05 « Figures à reproduire » (IREM, équipe),
  S06 Rosace et chouette + Sierpinski, S07 « Étoiles au rapporteur »
  (création), S08 « Pavages de triangles » (création). S04 inchangé (aucun
  renvoi à S05 ou S06).

Vérifications : 52 objectifs inchangés ; import S01 à S09 sur une copie
migrée de la base (essai à blanc : 3 anomalies cycle 4 déjà connues ;
`--apply` deux fois : base identique, 8 977 lignes) ; livrets S05 à S09
compilés par les routes de l'appli (28, 22, 21, 8 et 18 p.), pages de garde
par partie vues en image ; vérifications Python des lots (calculs,
structure, renvois, paires A/B par `preparer_evaluation`, aucune réponse en
version élève). Pytest : 4 527 réussis, 8 ignorés, 0 échec ; vitest :
27 fichiers, 284 tests réussis.

Points à trancher : série A de S06-03 (angle) en S06 après S07 ou ailleurs ;
évaluation S06 /20 ou deux tests courts ; Sierpinski en S06 ; S08 courte
avec 3 travaux personnels.
