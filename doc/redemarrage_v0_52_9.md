# Redémarrage v0.52.9 — Évaluations en deux parties (sans / avec calculatrice), façon DNB

## Besoin (Laurent, 20 octobre 2026)

> « Si certains exercices interdisent explicitement la calculatrice et
> d'autres non, il faut faire comme pour le DNB : 2 sous-sujets. Le premier
> sans calculatrice, à ramasser après une durée en fonction du nombre
> d'exercices à faire, et le second sur une autre feuille qui est donnée en
> échange de la première (+ de la copie avec les réponses le cas échéant). »

## Audit

- Le marquage par exercice existe depuis la v0.52.7
  (`exercices.calculatrice`) ; l'import l'appliquait à tous les EV d'une
  évaluation depuis la clé `calculatrice` de l'entrée du lot. La mention du
  sujet suit la règle C1 de la v0.52.8 (`calculatrice_evaluation`).
- Rendus 6e d'une évaluation : `render_evaluation.corps_evaluation_6e`
  (sujet A ou B — le sujet B est la remédiation de chaque atome EV —, version
  élève ou corrigée), plus le numéro d'exercice du rendu d'un atome
  (`rendu_atome_6e`) et la ligne de l'évaluation du plan de travail 6e.
- Pagination : les documents 6e sont en `article` recto simple (pas de
  `twoside`) ; en-tête « nom -- page N » ; rien ne sait si le sujet est
  imprimé recto-verso.
- Barème : un tableau par compétence (somme des points de chaque objectif),
  légende des exercices par compétence quand il y a un bonus. Un objectif
  évalué dans les deux parties reste une seule colonne : **aucun problème
  d'affichage** ; un rappel des exercices de chaque partie est ajouté sous le
  tableau.
- Le module LaTeX `seqenseigne-style6e` n'a pas besoin de changer (bandeaux
  en LaTeX de base) : **pas de `tex seqenseigne.ins` à relancer**.

## Décisions

- **D1 Déclenchement** (`marqueurs_exercices.deux_parties`) : coupé en deux
  seulement si au moins un exercice **EV** est marqué `interdite` et au moins
  un `autorisee`. Sinon : sujet d'un seul tenant, `.tex` de la v0.52.8 au
  caractère près (mention C1 comprise). Le découpage ne dépend que du
  marquage : ni l'option « Calculatrice » du rendu/document ni le réglage
  `evaluations.calculatrice` ne l'empêchent (ils ne règlent que la mention
  d'un sujet d'un seul tenant). Gabarit 6e seulement : le cycle 4 ne change
  pas.
- **D2 Répartition** (`partie_de`) : partie 1 « Sans calculatrice » = les
  exercices `interdite`, dans leur ordre ; partie 2 « Calculatrice
  autorisée » = tous les autres, dans leur ordre. Le bonus suit son propre
  marquage (non marqué → partie 2). Le sous-titre ne porte plus la mention
  C1 : les bandeaux de partie la remplacent.
- **N1 Numérotation continue** (choix, comme le DNB) : Exercice 1… en partie
  1, la suite en partie 2 ; un numéro désigne un seul exercice sur les deux
  feuilles, ce qui garde sans ambiguïté la légende du barème (« S03-14 :
  ex. 5 ») et le rendu d'un atome (`exercices_affiches_6e`).
- **D3 / F1 Feuilles séparées** (`SAUT_FEUILLE_PARTIE2`) : la partie 2
  commence sur une page **impaire** (le sujet est supposé photocopié
  recto-verso ; si la partie 1 finit sur un recto, son verso reste blanc
  avec la mention « Page laissée blanche : la partie 2 est sur une autre
  feuille. »), repart à la page 1 (en-tête « … --- partie 2 -- page 1 »),
  avec son propre `\seqIdentEleve`, le titre et le bandeau « Partie 2 ---
  calculatrice autorisée ». La partie 1 porte « Partie 1 --- sans
  calculatrice --- à rendre au bout de N min ».
- **Corrigé** (choix) : même découpage et même pagination que le sujet
  élève (même code, `\seqVersionCorrigee` en plus) : l'enseignant compare
  page à page.
- **D4 Durée** (`duree_partie1_auto`) : N = 55 min × points de la partie 1
  hors bonus / total du barème hors bonus, arrondi aux 5 min (moitié vers le
  haut), au moins 10 min, au plus 55. Colonne `evaluations.duree_partie1`
  (minutes, NULL = calcul automatique ; migration idempotente
  `migrer_duree_partie1`, au démarrage et par l'import) ; champ « Durée de la
  partie 1 » du module Évaluations (vide = automatique, valeur calculée en
  indication ; 1 à 240 min entières, sinon 400 `duree_partie1_invalide`).
- **D5 Barème** : tableau unique en tête de la partie 1, puis le rappel
  « Partie 1 : ex. 1, 2, 3 et 5 (15 pts + bonus) ; partie 2 : ex. 4 (5 pts) ».
  Sujets A et B : même découpage (paires par position : le sujet B est sur
  le même atome).
- **C3 revu** : un sujet en deux parties n'a pas d'avertissement « réglage
  contraire aux exercices » (les deux mentions sont imposées par D2).
- **I3 Import** : clé facultative `calculatrice_exercices` de l'entrée
  d'évaluation, `{"<position 1-based>": "interdite" | "autorisee"}` ; positions
  non listées : clé `calculatrice` ; même table pour A et B (sujet A, sinon
  B ; tables différentes signalées) ; position hors sujet ou valeur inconnue
  signalées et ignorées. Marquage écrit sur chaque exercice EV (idempotent,
  jamais sur validé). Une évaluation coupée en deux reçoit
  `evaluations.calculatrice = ''`. L'essai à blanc termine sa ligne par
  « — en deux parties : partie 1 sans calculatrice ex. … (N pts, M min),
  partie 2 calculatrice autorisée ex. … ».
- **Plan de travail 6e** : la ligne de l'évaluation dit « en deux parties :
  sans calculatrice, ramassée au bout de N min, puis calculatrice
  autorisée ».

## Code

Nouveau : `tests/test_v0_52_9_deux_parties.py` (53 tests),
`tests/donnees_v0_52_9/` (25 `.tex` de référence produits par le code de la
v0.52.8), `tests_js/deux_parties_evaluation.test.js` (4 tests), ce fichier.
Modifiés : `services/marqueurs_exercices.py`, `services/render_evaluation.py`,
`services/rendu_atome_6e.py`, `services/evaluations.py`,
`routes/evaluations.py`, `services/plan_travail_6e.py`,
`outils/import_lot6e.py`, `templates/index.html`,
`static/atelier_evaluation_oo.js`, `doc/ETAT_COURANT.md`. Une colonne
nouvelle (`evaluations.duree_partie1`), aucune table, aucune route nouvelle.
`structure_evaluation_6e` lit le titre et le niveau directement (le
découpage, ajouté à la lecture d'une évaluation par la route, relit cette
structure).

## Vérifications

- Sujets d'un seul tenant : 24 `.tex` (6 marquages × A/B × élève/corrigé) et
  un rendu cycle 4 marqué mixte identiques à la v0.52.8 (tests) ; sur la
  base migrée et importée de la v0.52.8, 488 sorties identiques (403 du
  cycle 4, 72 rendus des évaluations 6e, 13 plans de travail 6e).
- Import S01 à S13 : essai à blanc (base intacte), `--apply`, second
  `--apply` sans changement. Seule S03 « Ordre de grandeur et
  multiplication » est coupée : partie 1 ex. 1, 2, 3 et 5 (15 pts + bonus,
  40 min), partie 2 ex. 4 (5 pts).
- PDF : S03 sujet A élève et corrigé (3 pages : partie 1 sur 2 pages, partie
  2 en page 3), S11 sujet A élève (`.tex` identique à la v0.52.8).

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et
   `reference\lot6e\S01\` à `S13\`.
2. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py`
   (essai à blanc : ligne S03 « — en deux parties : … 40 min »), puis
   `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.
3. Lancer l'appli : la colonne `evaluations.duree_partie1` est ajoutée au
   démarrage si l'import ne l'a pas déjà fait. Module LaTeX inchangé.
