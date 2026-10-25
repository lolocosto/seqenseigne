# Redémarrage v0.53.2 — π dans le plan, dossier enseignant, activités complémentaires des mises en route

## Besoins (Laurent, 25 octobre 2026)

1. M04, onglet « Rendu PDF », partie 3 — Périmètre d'un cercle, « Plan de séquence
   (enseignant) » : `LaTeX Error: Unicode character π (U+03C0)`.
2. « On pourrait fusionner fiches de corrigés et plan de travail en un seul doc enseignant
   pour chaque partie de séquence. »
3. Garder, refaites en LaTeX, deux activités de l'équipe sur le cercle (M04, partie 3) :
   activités complémentaires dans une mise en route.
4. Référentiel du 25 octobre (`col6/ref6e_v2.md`).
5. Tests courts : bonus de 1 point.

## 1. Décisions

- **E1 — Échappement LaTeX commun** (`services/latex_texte.py`, nouveau). Cause : le
  critère F de M04-22 (« … avec π ≈ 3,14 », table `objectifs`) inséré tel quel dans le
  plan (`mises_en_route_6e._plan_partie`, qui n'échappait ni les critères ni l'intitulé).
  Choix : **convertir à l'insertion** plutôt que `\newunicodechar` dans le préambule
  commun — le préambule de tous les documents aurait changé, alors que le cycle 4 et le
  principal de 6e doivent produire le même `.tex` qu'en v0.53.1.
  - `unicode_latex(s)` : caractères que pdfLaTeX (inputenc utf8) ne connaît pas → commandes
    sûres en texte comme en formule (`π` → `\ensuremath{\pi}`, `≈`, `≤`, `≥`, `≠`, `−`, `∞`,
    `√`, `⊥`, `∥`, `∠`, `↔`, `⇒`, `⅓`, exposants et indices ⁴ ₂, lettres grecques…). Les
    caractères que le noyau LaTeX convertit déjà lui-même (`× ÷ ° ² ³ ½ ¼ ¾ ± · µ € … ’ « »
    → ← ‰` : `\texttimes`, `\textdegree`, `\texttwosuperior`…) restent tels quels. Une chaîne
    qui compilait est donc rendue à l'identique.
  - `texte_latex(s)` : en plus, `& % # _` échappés hors des formules `$…$` (texte simple).
  - Branchements : **tout le corps** de chaque document de 6e passe par `unicode_latex` dans
    `livret_sequence_6e.document` (point de passage de tous les documents 6e : livret,
    fiches, corrigés, évaluations et tests courts, plans de travail, documents TP/AC/AT,
    atomes, mises en route) — couvre aussi un π brut dans un énoncé ; les fonctions
    d'échappement des générateurs du cycle 4 (`livret_sequence._echapper_simple`,
    `livret_fiches`, `livret_corriges`, `livret_recap_cours`, `livret_recap_exos`,
    `livret_plans_de_travail`, `latex_rendu_atome._echapper_titre_latex`) appellent
    `unicode_latex` ; le plan (et le dossier) des mises en route passe intitulés, critères,
    titres, libellés et messages du contrôle par `texte_latex` (un « 10 % » dans un critère
    cassait aussi la ligne).
- **D-DOS — Dossier enseignant** : nouveau document `dossier` de l'onglet « Rendu PDF » d'une
  Mnn (option `partie` ; vide : toute la séquence, partie par partie). Un seul A4, tout en
  version corrigée, en-tête « Mise en route n --- nom -- dossier enseignant -- page n »,
  chaque bloc sur une nouvelle page : (1) plan de la partie, (2) fiche de cours complète,
  (3) corrigés rédigés des exercices de séance dans l'ordre des séances (pour M05 : textes
  des figures dictées et de la géométrie mentale, qui sont dans les corrigés ; un exercice
  sans corrigé rédigé le dit : « réponses sur la planche corrigée »), (4) tests courts
  corrigés, sujet A puis sujet B, (5) activités complémentaires corrigées. Les documents
  existants (fiche, planche, test, plan) restent.
- **D-AC / I-MR8 — Activités complémentaires dans une Mnn** : série `AC` comme au principal.
  Clé de lot `activites_complementaires` au niveau du lot, même format que les lots S, avec
  `objectif` (code) ou `objectifs` (liste) ; import commun (`import_lot6e.importer_documents` :
  AC01… dans l'ordre du lot, AC validé jamais réécrit, liens `objectif_exos` série AC). AC
  sans objectif ou d'objectif inconnu : signalée ; `travaux_personnels` / `seances_atelier`
  dans un lot Mnn : signalés, ignorés. Partie d'une AC = celle de son objectif. Affichées
  dans le plan de la partie (« Activités complémentaires — élèves en avance ; hors contrôle »)
  et dans le contrôle de l'onglet, corrigées dans le dossier ; document `activite` (élève ou
  corrigé, rendu du document AC du principal, `documents_6e.corps_document`). **Hors
  contrôle MR6** (série MR seule). Les AC des Mnn ne sont pas proposées par le catalogue du
  principal (`documents_6e.atomes_de_la_serie` écarte les séquences `hors_principal`).
- **Référentiel du 25 octobre** : `outils/ref6e_v2.md` recopié à l'identique de
  `col6/ref6e_v2.md` (critère F de S10-02 « … dans un tableau déjà filtré … », notions « Aire
  et unité d'aire » de M03/M04, dépendances M03-12 → M04-12 et M05-12 → S06-03) ;
  `outils/objectifs_6e.json` : critère F de S10-02 (transcription testée). L'import met à
  jour le critère d'un objectif existant (séquence non validée ; une séquence validée n'est
  pas importée), signalé dès l'essai à blanc (« S10-02 : objectif mis à jour d'après
  objectifs_6e.json (critère F) »). Les notions et dépendances restent du texte du
  référentiel (pas de table).
- **I-MR5 révisé — bonus de 1 point** : un bonus d'une autre valeur (barème du lot ou
  exercices « Bonus… » du sujet) est une **anomalie « à corriger dans le lot »** (v0.53.1 :
  information). Test court : 10 points hors bonus (inchangé).

## 1 bis. Corrections trouvées à l'assemblage

- Titre d'exercice de séance avec « % » (M02 : « Passer par 10 % ou 1 % ») : la planche
  corrigée et le dossier ne compilaient pas (`\seqPartieSix{…` coupé, la suite de la ligne
  en commentaire) → les titres d'exercices des planches, des corrigés rédigés et du dossier
  passent par `texte_latex` (E1).
- `\foreach \x in {…} \fill …;` sans accolades autour du corps dans un **corrigé** (M04,
  activité complémentaire 2) : le corrigé est rendu dans l'argument de `\seqLocExplication`,
  où le « ; » est déjà lu actif (babel français) — « Paragraph ended before \pgffor@next was
  complete » (version corrigée et dossier). L'import le signale désormais (anomalie, tous les
  lots, champs `corrige` et `remed_corrige` : `import_lot6e.foreach_en_argument`) ; lot M04
  corrigé (accolades seulement).

## 2. Import

Même commande. L'essai à blanc montre, section « == Mnn == », la ligne « activités
complémentaires : n (AC01 à ACnn) — AC01 → M04-22 ; hors contrôle de la séquence », et
section « == Documents… » chaque AC.

## 3. Module LaTeX

Inchangé (`seqenseigne-style6e` v0.10) : pas de `tex seqenseigne.ins` à relancer.

## 4. Résultats

Voir le compte rendu de livraison (`SP/livraison_v0532/`) : import S01–S13 + M01–M07 (essai,
`--apply`, second `--apply` sans changement), compilation de tous les documents de toutes
les parties M01–M07, rendu par lot N09, non-régression (cycle 4 et principal 6e identiques
au caractère près), pytest, vitest.

Tests : `tests/test_v0_53_2_dossier_ac.py`, `tests_js/mer_dossier.test.js` ; adapté (changement
voulu) : `tests/test_v0_53_1_mer_parties.py` (bonus de 2 : anomalie et non plus information).

## 5. Reste à faire

- Côté classe : publication d'une mise en route comme référentiel « mer ».
- Atelier : saisie du format (quart/demi) d'un exercice MR et du libellé de partie dans
  l'interface (aujourd'hui par le lot).

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et `reference\lot6e\…`.
2. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py` (essai à blanc),
   puis `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.
3. Lancer l'appli ; Atelier › séquence N09/M04 › onglet « Rendu PDF » : Partie 3, Document
   « Dossier enseignant ».
