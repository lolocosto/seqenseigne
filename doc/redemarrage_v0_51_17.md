# Redémarrage v0.51.17 — Livret de séquence : objectifs en page 1, prérequis sous « Révisions »

## Décisions (validées)

- **D1 — Ordre du livret** : titre → objectifs (page 1) → Révisions
  (boîte Prérequis puis exos R/AE) → Connaissances → Savoir-faire →
  séries F/A/E → annexes et corrigés → fiches de résumé.
- **D2 — Objectifs par partie** : une boîte `\seqRenduTableauObjectifs`
  par partie, titrée « Objectifs — 1\textsuperscript{re} partie »,
  « … 2\textsuperscript{e} partie »… ; séquence à une seule partie :
  titre par défaut « Objectifs ». Une partie sans objectif n'a pas de
  boîte (les autres gardent leur numéro). Tableaux émis **même sans
  aucun critère F/A/E saisi** (avant : omis).
- **D3 — Paquet `seqenseigne-theme`** : argument optionnel de titre,
  `\seqRenduTableauObjectifs[titre]{lignes}` (défaut « Objectifs ») ;
  la boîte interne `seq@boite@objectifs` prend le titre en argument
  obligatoire (`\begin{seq@boite@objectifs}{#1}`, `title={#1}`).
- **D4 — Paquet `seqenseigne-core-exos`** : crochet
  `\seqContenuAvantSerie{contenu}`, consommé une seule fois par la
  `seqSerieExos` suivante, juste **après** son `\seqTitreSection{…}`
  (`\seq@avant@serie\gdef\seq@avant@serie{}`). Un crochet plutôt qu'un
  argument optionnel : les libellés d'objectifs peuvent contenir des
  crochets (intervalles).
  - Avec exos R/AE : l'appli émet `\seqContenuAvantSerie{\seqRenduTableauPrerequis{…}}`
    juste avant `\begin{seqSerieExos}{0}` (pas de second titre).
  - Sans exos R/AE (ou exercices désactivés) : l'appli émet
    `\seqTitreSection{Révisions}` puis la boîte (même rendu).
  - Ni prérequis ni exos R/AE : pas de section Révisions.
- **D5 — Parseur** : `seqSerieExos` garde sa signature `[1]` ;
  `\seqContenuAvantSerie` reconnu par `paquet_parseur` et ajouté aux
  `MACROS_STRUCTURELLES` (machinerie de livret, absente de l'onglet
  « Tout le paquet » de l'éditeur).

## Code

- `services/livret_sequence.py` : `_generer_tableau_objectifs` (une boîte
  par partie, plus d'omission), `_ordinal_partie`, `_compter_parties` ;
  réordonnancement dans `generer_livret_sequence` (sections « Objectifs »
  et « 5. Révisions »).
- `services/paquet_expose.py` : `\seqContenuAvantSerie` dans
  `MACROS_STRUCTURELLES`.
- Tests (`tests/test_livret_sequence.py`) :
  - réécrits : `test_tableau_objectifs_emis_meme_sans_aucun_critere`
    (remplace `…_omis_si_aucun_critere`),
    `test_objectifs_avant_prerequis_dans_le_livret` (remplace
    `test_prerequis_avant_objectifs_dans_le_livret`) ;
  - nouveaux : `TestV05117ObjectifsParPartie` (3 tests),
    `TestV05117PrerequisSousRevisions` (4 tests).

## Déploiement

1. Paquet : `seqenseigne-theme` et `seqenseigne-core-exos` modifiés par
   l'auteur (sources `.dtx` dans `reference/paquet/`, `.sty` déployés dans
   MiKTeX). **Le livret v0.51.17 exige ces deux `.sty`** : avec l'ancien
   `core-exos`, `\seqContenuAvantSerie` est indéfinie.
2. Réindexer le paquet dans l'appli (scan du paquet) pour que
   `paquet_definitions` connaisse `\seqContenuAvantSerie` et la nouvelle
   signature de `\seqRenduTableauObjectifs` (`[2][Objectifs]`).
3. Recompiler les livrets de séquence.

Validation locale : document minimal compilé avec les trois `.sty` réels
(deux parties, une partie unique, prérequis + série 0 puis série 1) :
boîtes titrées par partie en page 1, Prérequis sous « Révisions », crochet
non réutilisé par la série fondamentale.
