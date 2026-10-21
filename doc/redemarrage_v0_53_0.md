# Redémarrage v0.53.0 — Rendu par lot en 6e ; mises en route de 6e (début)

## 1. Anomalie du 21 octobre : rendu par lot en 6e

Atelier › Conception de référentiel › Outils généraux › Rendu par lot, Niveau « N09 (6e) »,
« Aperçu (compter) » → `Erreur : niveau invalide : 'N09'`.

- Cause : `routes/admin.py` (`_filtre_depuis_query`) n'acceptait que `('N10', 'N11', 'N12')` et
  les séquences `S` + deux chiffres (liste antérieure à la 6e ; l'interface proposait N09).
- **B1** : niveaux acceptés = N09 à N12 et ceux de `param_niveaux`
  (`compilation_batch.niveaux_valides`) ; séquences `Snn`, `Mnn` (mises en route), `Xnn`
  (archives) (`sequence_valide`) ; le filtre « Séquence » propose aussi M01 à M07.
- **B2** : une fiche de résumé d'un niveau au modèle « Fiches » se rend au format de l'équipe
  (`seqFicheResumeSix`, version complète par défaut, `?version=eleve` : à compléter) — dans le
  rendu par lot comme dans l'atelier Fiche (`rendu_atome_6e.generer_tex_fiche_6e_si_gabarit`) ;
  modèle « Notions » : même `.tex` qu'avant. Exercices de toutes séries (F, A, E, AE, EV, TP,
  AC, AT, MR) : rendu 6e déjà en place (v0.52.3), MR ajouté.
- Autres validations du même genre : `routes/livret_sequence.py` et `routes/plans_de_travail.py`
  acceptent N09 (liste N09–N12) ; le livret accepte désormais aussi `Mnn` (documents de mise en
  route) ; les plans de travail restent réservés aux `Snn`. `static/app.js` (scanner de
  l'ancien import par fichiers, « tous » = N10–N12) : outil du cycle 4, laissé tel quel.
- Essai sur la base de test (copie migrée et importée de la v0.52.9) : voir § 5.

## 2. Mises en route de 6e — décisions

Audit complet : `audit_mer.md` (livraison). Code : `services/mises_en_route_6e.py`,
`outils/import_lot6e_mer.py`.

- **MR1** Les mises en route vivent dans l'atelier du niveau comme des séquences `Mnn`
  (`sequences_du_cycle` C03 `Mnn`, numéro 200 + n ; `sequences_par_niveau` N09/Mnn ; une
  partie ; objectifs `01`…). Même niveau, donc même modèle que le principal (R1b) ; tous les
  outils de l'atelier les voient. Elles ne font **pas** partie du référentiel principal (MR7) et
  seront publiées comme un référentiel de type « mer » (suite) ; la classe garde M2026\_N09.
- **MR1b** Pas d'objectif « Cours » dans une séquence Mnn ; la règle (n-1)1 est neutralisée
  (`est_objectif_cours`, assemblage JS `_codeConnaitre`, arbre du niveau, format d'échange).
- **MR2** Série `MR` (« mise en route ») de l'atelier d'exercices, numéro = séance, reliée à
  l'objectif (`objectif_exos` série MR) ; série « documents » (aucun livret) ; bouton « Mise en
  route » dans l'atelier et la modale de création (modèle « Fiches »).
- **MR3** Fiche de cours de séquence = fiche de résumé sans objectif de la séquence.
- **MR4** `latex_corrige` : fiche entière → seconde fiche « … (version complète) » ; note de
  corrigé → dernière section de la fiche dans `\seqLocExplication` (version complète seulement).
- **MR5** Documents (onglet « Rendu PDF » de l'assemblage d'une séquence Mnn ; route du livret,
  option `mer` : `document`, `version`, `par_page`, `exemplaires`, `test`, `sujet`) : fiche de
  cours (1 ou 2 par A4), exercices de séance (2, 3 ou 4 par A4, élève ou corrigé), test court n
  (rendu 6e du module Évaluations, « Mise en route n » en sous-titre, 1 ou 2 par A4), plan de
  séquence (enseignant). Un exercice MR seul se rend à sa taille réelle (quart de A4).
- **MR6** Validation : fiche de cours, ≥ 1 MR par objectif, MR relié à un objectif ; nombre
  d'exercices ≠ séances prévues et absence de test court : avertissements. Compte rendu d'import
  et plan de séquence.
- **MR7** `hors_principal` (Xnn ou Mnn) : hors des livrets, fiches de cours, corrigés, plans et
  évaluations du catalogue du principal, du modèle « programme du cycle » et de la validation du
  principal.
- Leitner et cartes d'automatisme du cycle 4 : aucun changement.

## 3. Import des lots de mise en route

Même outil, même dossier (`reference\lot6e\M01\M01.json` à côté de `S01`…) : les lots `Mnn`
sont lus après les `Snn` (`outils/import_lot6e_mer.py`). Format du lot : `BRIEF_V0530` § 3
(docstring de l'outil). Décisions I-MR1 à I-MR6 :
ref6e\_v2 (« Mises en route ») fait foi pour nom, thème, objectifs et séances (lot retenu si la
séquence y manque) ; critères F et A du lot ; MR = séance ; changement d'objectif d'une séance :
ancien lien MR retiré ; exercice ou fiche validés jamais réécrits ; MR de la base sans séance dans
le lot signalé, jamais supprimé ; tests courts comme les évaluations (R1, R2, R4), total ≠ 10
signalé ; macros de `macros_locales` comparées au module ; étiquettes d'évaluation `Mnn-nn`
reconnues. Le compte rendu se termine par le contrôle MR6 de la séquence.

## 4. Module LaTeX

`seqenseigne-style6e` **v0.9** : `\seqLocItemCM` (item de calcul mental sans « = … » final, lot
M01). **`tex seqenseigne.ins` à relancer dans `reference\paquet`.**

## 5. Vérifications

- **Rendu par lot N09** (base de test v0.52.9, S01–S13) : aperçu 200, 1 186 atomes ; 1 156
  réussis, 30 échecs, tous des archives Xnn au rendu du cycle 4 dont une image PNG est absente de
  la copie de test (`… .png not found`, à vérifier dans `images\` chez Laurent) ; S01–S13 : 0
  échec (723 exercices de toutes séries, 52 fiches). Après import de M01 : N09/M01 31/31.
- **Non-régression** (`cmp_v0530.py`, base v0.52.9) : 1 013 sorties identiques au caractère près
  entre v0.52.9 et v0.53.0 — cycle 4 (documents des référentiels, 201 atomes exercices, 150
  fiches, 79 cartes, 42 plans, format d'échange, éligibilité) et 6e principal (livrets élève et
  corrigé, fiches de cours par séquence et annuelles, corrigés, 72 rendus d'évaluations, 13 plans
  de travail, 241 atomes, cibles du catalogue).
- **Import** S01–S13 + M01 (instantané des lots) : essai à blanc (base intacte), `--apply`,
  second `--apply` sans changement ; M01 : 4 objectifs, fiche de cours (note de corrigé, MR4),
  24 exercices MR, 2 tests courts sur 10 (sujets A et B, bonus), contrôle MR6 « complète ».
- **Tests** : pytest 4 680 réussis, 8 ignorés (`tests/test_v0_53_0_mises_en_route.py` : 41) ;
  vitest 302 (`tests_js/mises_en_route_6e.test.js` : 7). Adaptés (changement voulu) : nombre de
  boutons de séries « documents » masqués (8 → 10, MR) ; version du module (v0.8 → v0.9).

## 6. Suite prévue (M02 à M07 et côté classe)

- Publication d'une mise en route comme référentiel « mer » (instantané depuis l'atelier, format
  d'échange, progression de la classe sur les Mnn), correspondance avec M2026\_N09 (ancien
  découpage : M03 Géométrie → M05…).
- Place des tests courts dans les séances (clé facultative de lot à définir) ; documents de mise
  en route au catalogue d'un référentiel « mer ».
- Assemblage adapté aux Mnn (série MR, séances) ; validation MR6 affichée dans l'atelier.
- Lots M02 à M07 : macros nouvelles éventuelles à verser dans le module (v0.10).

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et `reference\lot6e\…`.
2. Module LaTeX : `cd reference\paquet` puis `tex seqenseigne.ins` (copie le nouveau `.sty`).
3. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py` (essai à blanc :
   section « == M01 == »), puis `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.
4. Lancer l'appli ; Atelier › Rendu par lot, Niveau N09 : « Aperçu (compter) » puis « Lancer ».
