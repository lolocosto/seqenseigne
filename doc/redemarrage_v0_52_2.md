# Redémarrage v0.52.2 — Documents de 6e hors livret, dans les ateliers existants

## Besoin

Cadrage « Cadrage — documents et mise en forme par référentiel », décisions
validées le 19 octobre : les évaluations, travaux personnels, activités
complémentaires et séances d'atelier de 6e, écrits en `.tex` hors base par
la v0.52.0, entrent dans les ateliers existants (atelier d'exercices, module
Évaluations) et dans le catalogue du gabarit `sixieme`. Le cycle 4 produit
exactement le même `.tex` qu'avant.

## Décisions

- **S1 Séries « documents »** de l'atelier d'exercices
  (`services/atomes.SERIES_DOCUMENTS`) : `EV` évaluation, `TP` travail
  personnel, `AC` activité complémentaire, `AT` séance d'atelier. Un atome =
  un document (EV : un exercice d'évaluation). Reliés aux objectifs visés
  par `objectif_exos`, avec leur série, comme F/A/E. Aucune nouvelle table.
- **S2 Liste fermée de séries (audit)** : livret de séquence cycle 4
  (`numerotation_livret`, `v2_lecture`), livret 6e (`TITRES_SERIES`),
  recueil d'exercices, corrigés, plans de travail, numérotation : déjà
  fermés. Corrigés : trace de figeage du format d'échange
  (`referentiel_figeage._trace_exos_de_objectif`, lisait toutes les
  séries), exercices proposés en révision
  (`v2_edition.lister_exos_disponibles_pour_revision`), tuile « atomes non
  rattachés » du tableau de bord (le bonus EV, sans objectif, n'est pas à
  rattacher). Fiches : sans exercices.
- **I1 Interface** : boutons et choix de création des séries documents
  proposés en 6e (N09) seulement, ou pour un atome qui en porte déjà une.
  Série EV : le cadre « Remédiation » s'intitule « Sujet B » ; TP, AC, AT :
  pas de remédiation (cadre masqué, comme E).
- **V1 Validation** d'un atome EV/TP/AC/AT : énoncé exigé, corrigé
  facultatif (la version corrigée vient des macros de réponse via
  `\seqVersionCorrigee`) ; EV : sujet B exigé.
- **E1 Évaluation 6e** (`render_evaluation.generer_tex_evaluation_6e`) :
  un exercice vise l'objectif de l'évaluation auquel il est relié
  (`objectif_exos`, série EV d'abord) ; barème par compétence = somme des
  points par objectif ; tableau des objectifs = `evaluation_objectifs`.
  Gabarit de l'équipe (`\seqIdentEleve`, `\seqTitreEvalSix`,
  `\seqBaremeCompetences`, `\seqExoEval`), une seule géométrie (celle du
  livret 6e, L5). Options : `sujet` A|B, `version` eleve|corrigee.
- **B1 Bonus** = exercice sans objectif de l'évaluation : colonne « Bonus »
  du barème, étiquette « N pts --- bonus », hors total ; légende « Le bonus
  s'ajoute dans la limite de N » (comme les évaluations de l'équipe).
  Validation du module inchangée (le bonus a ses points).
- **E2 Calculatrice** : option `calculatrice` (interdite par défaut, comme
  les 7 évaluations des lots ; autorisée ; non précisée).
- **E3 Sujet B** = `remed_enonce` / `remed_corrige` ; une première ligne
  `% titre B : …` donne un titre propre au sujet B (un seul cas dans les
  lots : S01, « Le rang des chiffres dans … »).
- **R1 partagé** (`gabarits_documents.gabarit_atelier_du_niveau`) : le
  module Évaluations rend au gabarit du référentiel interne principal en
  cours du niveau, sinon N09 → 6e ; cycle 4 inchangé. Sélecteurs sujet /
  version dans la barre du rendu pour une évaluation N09.
- **C2 Catalogue `sixieme`** : `evaluation_6e` (une cible par évaluation du
  niveau), `travaux_personnels_6e`, `activites_complementaires_6e`,
  `seances_atelier_6e` (une cible par atome, option `version`). Cible
  `EV01/N09/S01`, `TP01/N09/S01`… : elle finit par la séquence, donc elle
  est proposée côté classe avec la séquence ; le titre du document
  (`titre_doc`) complète le libellé (côté classe et export).
- **D1 / D2 Documents TP, AC, AT** (`services/documents_6e.py`) : l'énoncé
  contient tout le document ; préambule du livret 6e. D2 : une activité
  complémentaire garde son numéro (`\seqComplSix` positionné, AC02 →
  « Activité complémentaire 2 »).
- **P3 Côté classe** : délai (≈ 7 jours) réglé sur l'association
  (`progression_doc` : retour « à rendre », délai en jours) ; aucune table.
- **L1 (v0.52.2) Activités d'introduction** : l'import garde le lien à la
  partie (`partie_exos_revision_approche`, EA : numérotation, plan de
  travail) et ajoute le lien à l'objectif (`objectif_exos`, AE) ; le livret
  6e n'affiche une activité reliée à un objectif que sous son bandeau.
- **O1 Import** : les documents vont en base ; plus aucun `.tex` écrit ;
  `--sortie` et `--documents-seulement` retirés (les `.tex` v0.52.0 restent
  sur le disque, non touchés). Évaluation repérée par (N09, titre), créée
  « note et critères » ; atomes EV numérotés EV01… dans l'ordre du lot ;
  sujets A/B mis en correspondance par position (points et objectif
  identiques) et barème du lot contrôlé ; sinon anomalie, évaluation non
  importée. Élément validé jamais modifié ; exercices ajoutés par l'auteur
  à une évaluation gardés (après ceux du lot).

## Code

Nouveaux : `services/documents_6e.py`, `tests/test_v0_52_2_documents_6e.py`
(+ `tests/donnees_v0_52_2/`, .tex de référence produits par b22206a),
`tests_js/series_documents_6e.test.js`.
Modifiés : `services/atomes.py`, `gabarits_documents.py`,
`render_evaluation.py`, `livret_sequence_6e.py`,
`orchestrateur_compilation.py`, `referentiel_documents_compilation.py`,
`peremption_atomes.py`, `progression_doc.py`, `format_referentiel.py`,
`referentiel_figeage.py`, `tableau_bord.py`, `v2_edition.py` ; routes
`evaluations`, `livret_sequence` ; `outils/import_lot6e.py` ;
`static/atelier_exercice.js`, `atelier_editeur.js`,
`atelier_evaluation_oo.js`, `app.css` ; `templates/index.html`.
Tests adaptés (comportement changé volontairement) :
`test_v0_52_0_import_lot6e.py` (O1, L1, comptes limités aux séries du
livret), `test_v0_52_1_gabarits_documents.py` (catalogue 6e complété),
`test_v0_15_2_6_peremption_atomes.py` (mapping des 4 nouveaux types).
Aucune migration, aucune table, aucune route nouvelles.

## Vérifications

- Cycle 4 : 128 .tex (documents N10–N12 de la base atelier de
  démonstration) identiques au caractère près entre b22206a (base propre)
  et v0.52.2 (même base + 108 atomes EV/TP/AC/AT reliés à des objectifs du
  cycle 4) ; test permanent sur 7 documents (livret de séquence aux options
  larges, recueil, corrigés, cours, fiches, évaluation) avec atomes
  documents injectés.
- Import sur une copie de la base atelier migrée : 7 évaluations (33 EV),
  5 TP, 6 AC, 1 AT, 0 anomalie nouvelle ; seconde exécution : tout
  inchangé ; `foreign_key_check` vide, `integrity_check` ok.
- Compilés sans erreur : évaluation S01 sujets A/B élève et corrigé, test
  court, TP n°1, AC, séance d'atelier S02, livret S01 (activités sous leur
  objectif, aucune en double).

## Limites connues

- Liens objectif ↔ EV/TP/AC/AT : posés par l'import (ou l'API
  `objectif_exos`), pas de zone dans l'assemblage.
- Aperçu d'un atome sans corrigé dans l'atelier d'exercices : échec
  antérieur à v0.52.2 (« Corriges/cNeM.tex not found », déjà le cas des F
  de 6e) ; compiler par « Documents à publier » ou le module Évaluations.
- Évaluation de l'import repérée par son titre ; numérotation EV dans
  l'ordre du lot.

## Déploiement (Windows)

1. Appli fermée : dézipper à la racine (à côté d'`appli\`).
2. Depuis `appli\` : `.\lancer.bat atelier` puis fermer l'appli (aucune
   migration nouvelle ; celle de v0.52.1 est déjà passée).
3. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py`
   (essai à blanc), puis
   `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.
4. Conception › Référentiel 6e › Documents à publier : cocher Évaluations,
   Travaux personnels… (6e) ; côté classe, régler le délai des TP.
