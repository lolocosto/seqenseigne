# Redémarrage v0.52.8 — Calculatrice des évaluations, astuces, TP hors « Matériel à prévoir », critères S05-12

## Besoin (Laurent, 20 octobre 2026)

Réponses aux questions laissées ouvertes par la v0.52.7 :

- Q5 : « oui » — la mention « calculatrice … » du sujet d'une évaluation doit
  suivre le marquage, au lieu de rester « interdite » par défaut ;
- Q3 : « les TP sont à faire sur le temps personnel, donc l'enseignant n'a pas
  à réserver de matériel » ;
- Q2 : consigne habituelle « Pour mieux comprendre ce que fait le programme, tu
  peux le construire dans Scratch et le tester. », insérée comme astuce dans
  les exercices concernés (par l'agent des lots) ;
- Q1 : « d'accord » — nouveaux critères de S05-12 (équerre ou compas) ;
- Q4 : règles du bonus (compté seulement si toutes les autres questions ont été
  traitées ; question de niveau A).

## Audit

- **Calculatrice** : l'option n'était **pas** stockée par évaluation. Elle
  venait de l'option « Calculatrice » du document « Évaluations » du catalogue
  6e (`gabarits_documents`, défaut `interdite`, la même pour toutes les
  évaluations du niveau, enregistrée en entier dans
  `referentiel_documents.options` à la création du référentiel) ou du
  paramètre `calculatrice` du rendu de l'atelier. L'import ne la réglait pas
  (simple information « régler l'option du document »).
- **TP** : le plan de travail 6e notait les documents marqués (TP compris) ;
  le plan du cycle 4 ne lit que les séries F, A, E, R et EA (aucun TP : rien
  à exclure) ; la publication (`format_referentiel._materiel`) et la classe
  (`referentiel_materiel_publie`, `materiel_publie`) gardaient les TP.
- **Critères** : l'import met déjà à jour l'intitulé et les critères F, A, E
  d'un objectif existant (état « objectif mis à jour »), sans dire lesquels ;
  une séquence validée n'est jamais importée (les objectifs n'ont pas d'état
  propre : la validation est celle de la séquence-niveau).
- **Astuce** : l'import enregistre le LaTeX tel quel ; seul le contrôle I1
  (macros `\seqLoc…` absentes du module) pouvait bloquer — `\seqAstuceSix`
  n'est pas une `\seqLoc…` : acceptée. Le module est chargé dès qu'une macro de
  `services/style6e.MACROS` est utilisée : la macro y est ajoutée.
- **Bonus** : l'appli ne calcule **aucune note** (pas de saisie de résultats) ;
  le sujet affiche le barème par compétence avec la colonne « Bonus » hors
  total (B1, v0.52.2) et, quand il y a un bonus, la légende « Le bonus
  s'ajoute dans la limite de N. » où N est le **total du barème** (20 pour
  toutes les évaluations des lots), pas 20 écrit en dur. La règle « compté
  seulement si toutes les autres questions ont été traitées » est dans le
  titre du bonus (lots) : `_est_bonus` (titre qui commence par « Bonus »)
  continue de le reconnaître. Rien à coder ; à documenter le jour où l'appli
  de classe saisira des notes (bonus plafonné au total, conditionnel).

## Décisions

- **C1 La calculatrice du sujet suit le marquage**
  (`marqueurs_exercices.calculatrice_selon_exercices`) : une évaluation dont
  un exercice **EV** est marqué `autorisee` sort « calculatrice autorisée » ;
  sinon (un exercice `interdite`, ou rien de marqué) : « calculatrice
  interdite », comme avant. Le réglage est une colonne de l'évaluation,
  `evaluations.calculatrice` : `''` (selon les exercices, défaut) |
  `interdite` | `autorisee` | `non_precisee` (migration idempotente
  `marqueurs_exercices.migrer_evaluations`, au démarrage et par l'import).
  Ordre : valeur explicite de l'option du rendu (atelier, document) >
  réglage de l'évaluation > règle C1 (`calculatrice_evaluation`). L'import
  écrit le réglage depuis la clé `calculatrice` de l'entrée d'évaluation du
  lot (sujet A, sinon B), pour une évaluation non validée ; clé absente =
  `''` (le lot fait foi, comme M7) ; idempotent ; la ligne de l'évaluation
  du rapport se termine par « — calculatrice autorisée / interdite ».
- **C2 Option du document « selon l'évaluation »** : nouvelle valeur
  `selon_evaluation`, nouveau défaut du catalogue (`CALCULATRICE_6E`). Les
  documents déjà créés ont enregistré l'ancien défaut `interdite` : au moment
  où la colonne `evaluations.calculatrice` est ajoutée (une seule fois par
  base, donc jamais sur un choix fait ensuite), l'option restée à
  `interdite` passe à `selon_evaluation`, **pour les référentiels en cours
  seulement** (un référentiel verrouillé ou utilisé garde ses documents).
  Un « interdite » choisi exprès avant la v0.52.8 ne se distingue pas de
  l'ancien défaut : le régler de nouveau s'il était voulu.
- **C3 Avertissement sans écrasement** : liste « Calculatrice (sujet) » dans
  le module Évaluations (6e seulement), avec la valeur que donnent les
  exercices ; si l'enseignant règle une valeur contraire à des exercices
  marqués, un bandeau l'avertit (`calculatrice_avertissement` de
  `GET/PATCH /api/evaluations/<id>`) ; l'atelier ne change jamais le
  réglage. Valeur inconnue : 400 `calculatrice_invalide`. Sans exercice
  marqué, aucun réglage n'est « contraire ».
- **T1 Travaux personnels hors « Matériel à prévoir »**
  (`marqueurs_exercices.hors_materiel`, `SERIES_HORS_MATERIEL = ("TP",)`) :
  un TP garde son marqueur (fiche élève, ligne « (à la maison) (…) » du plan),
  mais n'entre plus dans l'encadré du plan de travail 6e, ni dans
  `partie.materiel` du format d'échange (version inchangée, 1.3 ; un TP seul
  marqué ne fait plus passer le document en 1.3), ni dans
  `referentiel_materiel_publie` à l'import d'une publication ;
  `materiel_publie` filtre les lignes TP déjà stockées par la v0.52.7. Les
  autres séries restent comptées. Cycle 4 : rien à changer (aucun TP).
- **A1 Astuce `\seqAstuceSix{texte}`** (module `seqenseigne-style6e` v0.8) :
  paragraphe à part à la fin de l'énoncé, ampoule au trait
  (`\seqPictoAstuceSix`), « Astuce. » en gras, texte en `\small`, retrait
  suspendu, sans cadre ; rien ne dépend de la version : visible élève et
  corrigé. Un exercice qui porte une astuce **n'est pas** marqué
  « ordinateur » (aucune déduction, ni par l'import ni par l'atelier).
- **I2 Macros du module dans les lots** : l'import signale en anomalie une
  macro `\seq…Six` absente du module (comme I1 pour `\seqLoc…`) et compte les
  astuces par séquence (« S13 : 9 astuce(s) \seqAstuceSix »).
- **O1 Critères d'un objectif existant** : `outils/ref6e_v2.md` recopié à
  l'identique de `col6/ref6e_v2.md` (lignes 387 et 389), `objectifs_6e.json`
  transcrit (critères F et A de S05-12), test de transcription vert. L'import
  met à jour l'objectif (inchangé : idempotent, jamais sur une séquence
  validée) et le signale désormais dès l'essai à blanc :
  « S05-12 : objectif mis à jour d'après objectifs_6e.json (critère F,
  critère A) ».
- **B2 Bonus** : rien côté appli (voir l'audit).

## Code

Nouveau : `tests/test_v0_52_8_calculatrice_tp_astuce.py` (29 tests),
`tests_js/calculatrice_evaluation.test.js` (4 tests), ce fichier.
Modifiés : `services/marqueurs_exercices.py`, `services/evaluations.py`,
`routes/evaluations.py`, `services/render_evaluation.py`,
`services/gabarits_documents.py`, `services/plan_travail_6e.py`,
`services/format_referentiel.py`, `services/import_publication.py`,
`services/style6e.py`, `templates/index.html`,
`static/atelier_evaluation_oo.js`, `outils/import_lot6e.py`,
`outils/ref6e_v2.md`, `outils/objectifs_6e.json`,
`paquet/seqenseigne-style6e.dtx` et `.sty`, `paquet/CHANGELOG.md`,
`doc/format_referentiel.md`, `doc/ETAT_COURANT.md`. Tests existants adaptés
(seulement l'assertion qui change) : version du module v0.7 → v0.8
(`test_v0_52_4_modeles`, `test_v0_52_5_objectifs_s05`,
`test_v0_52_7_marqueurs`), défaut de l'option du catalogue
(`test_v0_52_2_documents_6e`), critère F de S05-12
(`test_v0_52_5_objectifs_s05`). Une colonne nouvelle
(`evaluations.calculatrice`), aucune table nouvelle, aucune route nouvelle.

## Vérifications

- Cycle 4 : 403 sorties identiques au caractère près entre v0.52.7 et
  v0.52.8 (documents des référentiels N10 à N12 dont évaluations, atomes,
  plans, format d'échange, éligibilité ; livrets 6e S01 à S03) sur la base
  migrée et importée de la v0.52.7.
- Import S01 à S13 sur la copie de cette base : essai à blanc (base
  intacte), `--apply`, second `--apply` sans changement (voir
  `apercu_import.txt` de la livraison).
- PDF : évaluation S11 sujet A élève (« calculatrice autorisée »), livret
  S13 élève (astuces), plan de travail S11 (TP marqué absent de l'encadré).

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et
   `reference\lot6e\S01\` à `S13\`.
2. Module 6e v0.8 : copier `appli\paquet\seqenseigne-style6e.dtx` dans
   `reference\paquet\`, puis dans `reference\paquet\` : `tex seqenseigne.ins`.
3. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py`
   (essai à blanc : lignes « objectif mis à jour », « astuce(s) »,
   « — calculatrice autorisée »), puis
   `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.
4. Lancer l'appli : la colonne `evaluations.calculatrice` est ajoutée au
   démarrage si l'import ne l'a pas déjà fait.
