# CHANGELOG — seqenseigne

Toutes les modifications notables sont documentées ici.  
Format : [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/)  
Versionnement : [Semantic Versioning](https://semver.org/lang/fr/)

---

## [Unreleased] — En cours de développement

### À faire (feuille de route)

- **C1** — Flashcards imprimables (`seqFlashcard`, recto notion / verso exemple)
- **C2** — Fiche de différenciation (colonnes F/A/E par objectif, générée depuis les bases)
- **C3** — Document d'auto-évaluation élève (can-do statements depuis les objectifs CSV)
- **D1** — Script CLI Python : génère un `.tex` prérempli à partir de questions interactives
- **D2** — Templates annotés avec commentaires `% ← MODIFIER ICI` pour utilisateurs non-LaTeX
- Synchronisation des dates de version entre `seqenseigne.sty` (2025-01-11) et les modules `.dtx` (2025-10-24)
- Rendre le paquet utilisable hors mathématiques (option de discipline)
- Documenter les nouvelles macros de remédiation et le cadre de réponse dans `seqenseigne-doc.dtx`

---

## seqenseigne-style6e v0.11 — 2026-10-25

### Ajouté

- `\seqTableauConversionSix[options]{lignes}` et `\seqLigneConversionSix[note]{nombre}{unité}`
  (forme étoilée : réponse) : tableau de conversion commun, pour une mise en forme homogène
  de tous les tableaux de conversion (décision de Laurent du 25 octobre 2026). Grandeurs
  `longueur` (par défaut), `masse`, `contenance`, `aire` (deux colonnes par unité, filet gris
  entre elles ; ligne ha, a, ca avec `hectares` ou `hectares=ha-a-ca`) ; lignes `prefixes` et
  `valeurs` ; colonne de commentaire `note` ; `compact` (exercice au quart d'A4) ; largeur `colonne` (0,8 cm par défaut, tient dans
  un exercice au quart d'A4) ou `largeur`. Le nombre est placé un chiffre par colonne, le
  chiffre des unités dans la colonne de l'unité donnée ; chiffres donnés (noirs, dans les
  deux versions) ou réponse (cases vides en version élève, rouge gras en version corrigée,
  comme `\seqLocCellule`). Pas de tableau de durées (aucun lot n'en a besoin).
- `.sty` régénéré par `tex seqenseigne.ins` (seqenseigne v0.53.3).

---

## seqenseigne-style6e v0.10 — 2026-10-22

### Ajouté

- `\seqDefinirTitreCM{titre}` : titre du bandeau des fiches `seqCalculMental` suivantes
  (`\seqTitreCM`, « CALCUL MENTAL » par défaut) ; l'appli émet `\seqDefinirTitreCM{MISE EN
  ROUTE}` en tête des planches des mises en route autres que M01 (seqenseigne v0.53.1).
- `\seqLocItemGeo{contenu}` : item numéroté sans ligne de recherche (figure, tracé, mot à
  compléter), même compteur et mêmes colonnes que `\seqItemCM` ; macro locale du lot M05
  « Géométrie » versée dans le module. Les lots M01 à M04, M06 et M07 n'ont pas de macro
  locale nouvelle.
- `.sty` régénéré par `tex seqenseigne.ins` (seqenseigne v0.53.1).

---

## seqenseigne-style6e v0.9 — 2026-10-21

### Ajouté

- `\seqLocItemCM{contenu}` : item de calcul mental sans « = … » final (calcul à trou
  `68 + … = 100`, `… × 7 = 56`, arrondi `3,581 ≈ …`), même numérotation, mêmes colonnes et
  même ligne de recherche que `\seqItemCM` ; macro locale du lot M01 « Calcul mental »
  versée dans le module (les `macros_locales` d'un lot ne sont pas importées par l'appli).
- `.sty` régénéré par `tex seqenseigne.ins` (seqenseigne v0.53.0).

---

## seqenseigne-style6e v0.8 — 2026-10-20

### Ajouté

- `\seqAstuceSix{texte}` : astuce à la fin d'un énoncé (consigne habituelle de Laurent :
  « Pour mieux comprendre ce que fait le programme, tu peux le construire dans Scratch et
  le tester. ») ; paragraphe à part, ampoule au trait, « Astuce. » en gras, texte en
  `\small`, retrait suspendu, sans cadre ; identique en version élève et corrigée.
- `\seqPictoAstuceSix` : l'ampoule seule, lisible en noir et blanc.
- Documentation et `\changes` dans le `.dtx` ; `.sty` régénéré par `tex seqenseigne.ins`
  (seqenseigne v0.52.8).

---

## seqenseigne-style6e v0.7 — 2026-10-20

### Ajouté

- Marqueurs de l'exercice, dans le titre de `seqExoSix` ou de `seqActiviteSix`, avant le code :
  - `\seqMaterielSix{outil}{calculatrice}` : « Ordinateur --- outil » puis « calculatrice
    autorisée » ou « calculatrice interdite » ; un argument vide n'affiche rien ; police droite
    et normale, petits caractères gris foncé, lisible en noir et blanc ;
  - `\seqOrdinateurSix{outil}` (écran sur son pied, « Ordinateur --- Scratch ») et
    `\seqCalculatriceSix{autorisee|interdite}` (calculatrice, barrée si interdite) ;
  - pictogrammes seuls : `\seqPictoOrdinateurSix`, `\seqPictoCalculatriceSix` (étoilée : barrée).
- Documentation et `\changes` dans le `.dtx` ; `.sty` régénéré par `tex seqenseigne.ins`
  (seqenseigne v0.52.7).

---

## seqenseigne-style6e v0.6 — 2026-10-19

### Ajouté

- Macros de géométrie plane du lot S05 (noms gardés : les énoncés du lot les utilisent tels quels) :
  - `\seqLocCadreTrace[hauteur]{figure}` : zone de tracé, vide en version élève, avec la figure
    en version corrigée, même hauteur dans les deux versions (5 cm par défaut) ;
  - `\seqLocAngle{ABC}` : angle géométrique avec chapeau, en texte ou en maths ;
  - `\seqLocRapporteur[rayon]{centre}{orientation}` : demi-rapporteur semi-transparent à double
    graduation, dans un `tikzpicture` (remplace `\tkzProtractor`) ;
  - style TikZ `seqLocCorr` : tracés du corrigé (rouge, 0,8 pt).
- Macros de pré-algèbre du lot S04 (noms gardés) :
  - styles TikZ `seqLocBarre` (bleu), `seqLocBarreR` (rouge), `seqLocBarreV` (vert),
    `seqLocBarreQ` (pointillé : quantité cherchée) des schémas en barres ;
  - `\seqLocBloc[style]{x}{y}{longueur}{étiquette}` : bloc de barre ;
  - `\seqLocAccolade[below|above]{x1}{x2}{y}{étiquette}` : accolade horizontale ;
  - `\seqLocBalance[demi-largeur]{gauche}{droite}` : balance de Roberval en équilibre ;
  - `\seqLocSac{nom}`, `\seqLocMasse{valeur}`, `\seqLocObjet[couleur]{texte}` : objets de la balance.
  Bibliothèque TikZ `decorations.pathreplacing` chargée par le module.
- Page de garde du livret par partie : forme étoilée `\seqCouvertureLivretSix*{titre}{parties}`,
  où chaque partie est un `\seqPartieCouvertureSix{titre de la partie}{liste}` (titre de partie, puis
  ses objectifs avec un trait vertical de la couleur `seqSixTheme`, bleu du module par défaut,
  redéfinie par l'appli avec la couleur du thème). La forme sans étoile est inchangée.
- Documentation et `\changes` dans le `.dtx` ; `.sty` régénéré par `tex seqenseigne.ins`
  (seqenseigne v0.52.5).

---

## seqenseigne-style6e v0.5 — 2026-10-19

### Modifié

- Niveau paramétrable : `\seqNiveauCourt` (`6e`) et `\seqNiveauExposant` (`6\textsuperscript{e}`)
  remplacent « 6e » écrit en dur dans `\seqCouvertureLivretSix`, `\seqIdentEleve`,
  `\seqTitreTravailSix` et `\seqTitreComplementSix`. L'appli les redéfinit avec le nom court
  du niveau du référentiel (seqenseigne v0.52.4). Rendu inchangé en 6e.

---

## [1.0.5-dev] — 2026-05-04 — Module CORE-EXOS et remédiation

### Ajouté

- **`seqenseigne-core-exos.dtx`** — nouveau module dédié aux exercices et à la remédiation, chargé par `seqenseigne.sty` après `core` et avant `legacy`
- **Mécanisme de remédiation** — pour chaque exercice (typiquement en série fondamentale), possibilité d'attacher un énoncé et un corrigé de remédiation qui sortiront dans deux sections distinctes en fin de livret
  - `\seqInitRemediation` : ouvre les flux d'écriture pour les fichiers `RemedEnonceList.tex` et `RemedCorrigeList.tex`
  - `\seqRemediation{énoncé}{corrigé}` : se place dans un `seqExercice`, à la suite de `\seqCorrige`. Le numéro de l'exercice principal est repris automatiquement. Les exercices sans `\seqRemediation` n'apparaissent pas dans la sortie de remédiation (trous autorisés dans la numérotation).
  - `\seqAfficheRemediations` : produit la section « Exercices de remédiation »
  - `\seqAfficheCorrigesRemediation` : produit la section « Corrigés des exercices de remédiation »
  - Si `\seqInitRemediation` n'est pas appelée, les macros d'affichage et `\seqRemediation` sont silencieuses (compilation possible avec ou sans remédiation depuis le même source)
- **Cadre de réponse pour l'élève** — `\seqCadreReponse{N}` produit un cadre `boiteVariableTitre` avec titre « Réponse » et hauteur de N lignes, à placer après l'énoncé d'un exercice quand on veut que l'élève réponde directement dans le livret imprimé

### Modifié

- **`seqenseigne-core.dtx`** allégé — les macros et environnements suivants ont été déplacés vers `seqenseigne-core-exos.dtx` (refacto sans changement de comportement, les macros restent accessibles à l'identique pour l'utilisateur final) :
  - environnements `seqSerieExos`, `seqExercice`
  - macros `\seqCorrige`, `\seqInitCorriges`, `\seqAfficheCorriges`, `\seqCorrigesExos`
  - helpers internes `\seq@ecrit@corrige@serieExos`, `\seq@ecrit@corrige@Exo`
- **Patch des sauts de page entre séries de corrigés** — `\seq@ecrit@corrige@serieExos` écrit désormais `\clearpage` au lieu de `\newpage` avant le titre de chaque section de corrigés. Cela force la sortie des flottants en attente et garantit qu'une nouvelle série de corrigés démarre sur une page propre, sans superposition possible avec la fin de la série précédente (correctif d'un comportement gênant observé en présence de figures TikZ ou tableaux flottants)

### Compatibilité

- **Aucun changement de syntaxe pour l'utilisateur** — les macros déplacées conservent leur nom et leur comportement. Tous les livrets existants compilent sans modification.
- **Modules supplémentaires à installer** — `seqenseigne-core-exos.sty` doit être présent dans l'arbre TeX au même titre que les autres modules (cf. `seqenseigne.ins`)

---

## [1.0-dev] — 2025-10-24 — Refactoring modulaire

Version de développement actuelle. Architecture interne entièrement restructurée.

### Ajouté

- **Architecture modulaire** : `seqenseigne.sty` agit comme coordinateur et charge quatre sous-modules dans l'ordre `data` → `theme` → `core` → `legacy`
- **`seqenseigne-data.dtx`** : nouveau module dédié au chargement, filtrage et accès aux données pédagogiques
  - `\seqLoadData` : chargement des bases `.dbtex` pour les cycles 3 et 4
  - `\seqLoadDataSuivi{codeNiveau}` : chargement combiné bases + CSV pour les documents de suivi
  - `\seqSetDataPath{chemin/}` : configuration du chemin vers les bases
  - Famille de macros d'accès : `\seqSequenceGetNom`, `\seqSequenceGetNumero`, `\seqSequenceGetTheme`, `\seqObjectifGetNom`, `\seqObjectifGetMaitriseTB/S/F`, `\seqConnaissanceGetNom`, `\seqNiveauGetNomCourt`, `\seqNiveauGetNomLong`, `\seqNiveauGetCodeCycle`, `\seqThemeGetNom`, `\seqThemeGetCodeCouleur`
  - `\seqTableauObjectifs[niveau=, sequence=]` : tableau des critères de maîtrise généré depuis les bases
  - `\seqTableauPrerequis[niveau=, sequence=]` : tableau de prérequis adapté au niveau
  - `\seqSuiviAnnuelParEleve`, `\seqSuiviAnnuelParSequence`, `\seqSuiviPeriodiqueParSequence` : tableaux de suivi utilisant `longtblr`
  - `\seqSetColors{niv}{seq}` : règle le thème de couleur automatiquement depuis les bases
  - `\seq@maxsequences` : constante configurable (défaut : 16) pour le nombre de séquences par an
- **`seqenseigne-core.dtx`** : séparation claire entre logique structurelle et présentation
  - `\seqTitreLivret[codeNiveau=, codeSequence=, corriges=]` : titre de livret utilisant les bases
  - `\seqBoiteTitrePlan[titre=, afficheSeq=, affichePlan=]` : titre de plan automatique
  - `\seqPlanObjectif{niv}{seq}{obj}{notions}{F}{A}{E}` : bloc plan par objectif
  - `\seqSuiviSequence{niv}{seq}` : raccourci suivi + saut de page
  - `\seqTitreSuivi{classe}{titre}{annee}` : configuration en-têtes pour documents de suivi
  - Environnements sémantiques : `seqNotion`, `seqDefinition`, `seqPropriete`, `seqMethode` (numérotés automatiquement)
  - `seqBilanQCM` : QCM pour évaluations bilan (utilise `longtblr` et `expand=\repCodes`)
  - `seqBilanExo`, `seqBilanObjectifs` : exercices et tableau de maîtrise pour bilans de compétences
- **`seqenseigne-theme.dtx`** : module de présentation
  - Palette de 6 thèmes de couleur (`nombres`, `donnees`, `grandeurs`, `geometrie`, `algorithmique`, `gris`)
  - `\seqBoiteTitreFlashcard{niv}{seq}{obj}{complément}` : titre de flashcard avec données des bases
  - `\seqBoiteFlashcardVide` : flashcard vide pour impression recto-verso
  - Environnements `seqBoiteContenuFlashcard`, `seqBoiteFillContenuFlashcard`
  - Option `ltxdoc` : géométrie alternative pour la compilation de la documentation
- **`seqenseigne-legacy.dtx`** : module de compatibilité ascendante
  - Alias `\codeSequence` → `\seqCodeSequence`
  - Alias `\colEnum` → `\seqColEnum`, `\colItem` → `\seqColItem`
  - Alias `prerequisN2` → `seqPrerequisN2`, `objectifsN2` → `seqObjectifsN2`
  - `titreFiche` et `\seq@ligne@eleve` : fiche de suivi de classe imprimable
  - `\seqBilanPeriodiqueParEleve` : bilan périodique par élève avec colorisation
  - `\seqDecodeSerie` : décode les codes de séries (AE/F/A/E) en texte lisible

### Modifié

- **Séparation data/core/theme** : les macros qui accèdent aux données ne sont plus mélangées avec les macros de présentation
- **Chargement des modules** : l'ordre `data` → `theme` → `core` → `legacy` remplace le chargement monolithique
- Les tableaux de suivi utilisent désormais `longtblr` (bibliothèque `longtable` de `tabularray`) en remplacement de `longtabu`

### Technique interne (invisible pour l'utilisateur)

- `\seq@maxsequences` : constante remplaçant les 16 bases `seq@objectifs@sequenceun…seize` explicites
- `\seq@seqcode@tonumber` + `\seq@seqcode@tobasename` : conversion S01→1→`seq@objectifs@s1` par `\number` + `\csname`, suppression de la cascade de 16 `\DTLifstringeq`
- `\seq@bases@filter@cycle`, `\seq@bases@filter@sequence`, `\seq@bases@filter` : système de cache à trois niveaux (cycle / niveau / séquence) pour les filtres datatool
- `\seq@basesobjectifs@filter@niveau` : reconstruction des bases par séquence en boucle `\forloop`

---

## [0.x] — 2018–2024 — Phase pré-modulaire

### Contexte

Le code de cette période est conservé dans `seqenseigne-legacy.dtx` sous forme d'alias et dans certaines macros non préfixées encore présentes dans `seqenseigne-core.dtx`. Aucun numéro de version formel n'a été attribué à cette période.

### Repères chronologiques reconstitués depuis les sources

**2018-05-02** — Première version identifiable dans les sources (`\changes{v1.0}{2018/05/02}` dans `seqenseigne-theme.dtx`)
- Macros TikZ de base : `\seqOrigine`, `\seqAxeX`, `\seqAxeY`
- Premier système de séries d'exercices

**2017–2018** — Apparition des plans de travail
- Environnement `titrePlan` avec colonnes libres
- Exemples datés 2017/2018 dans `seqenseigne-doc.dtx`

**2021–2023** — Extension aux documents de suivi
- Tableaux de suivi de classe avec `longtabu`
- Intégration de `datatool` pour le chargement des bases CSV

**2024** — Préparation de la modularisation
- Identification des couches data / theme / core
- Création du module `legacy` pour préserver la compatibilité

---

## Anciens noms — Table de correspondance

Pour faciliter la migration des documents existants :

| Ancien nom | Nouveau nom | Module |
|-----------|-------------|--------|
| `\codeSequence` | `\seqCodeSequence` | variable globale (core) |
| `\colEnum` | `\seqColEnum` | theme |
| `\colItem` | `\seqColItem` | theme |
| `prerequisN2` | `seqPrerequisN2` | data |
| `objectifsN2` | `seqObjectifsN2` | core |
| `longtabu` | `longtblr` (tabularray) | — (migration A3) |
| `\tabucline{-}` | `\hline` dans longtblr | — (migration A3) |
| `\tabulinesep=Npt` | `rowsep=Npt` (option longtblr) | — (migration A3) |
| `\multicolumn{N}{c}{...}` dans QCM | `\SetCell[c=N]{c}{...}` | — (migration A3) |

Les alias sont maintenus dans `seqenseigne-legacy.dtx` et seront supprimés à partir de la version 2.0.

---

## Corrections de bugs notables (chantiers A1–A3)

Ces corrections ont été apportées lors de la refactorisation et ne correspondaient pas à un comportement intentionnel.

**A1 — `\newif\ifdocstd` déclaré quatre fois**  
Dans la version pré-refactoring, `\newif\ifdocstd\docstdtrue` était présent dans `seqenseigne.sty`, `seqenseigne-core.dtx`, `seqenseigne-theme.dtx` et `seqenseigne-legacy.dtx`. Chaque redéclaration réinitialisait silencieusement le flag à `false`, écrasant la valeur fixée par le coordinateur. En pratique : l'option `ltxdoc` était ignorée pour la géométrie dans `theme` et les sauts de page dans `core`. Corrigé : `\newif` uniquement dans `seqenseigne.sty`, les sous-modules déclarent `\DeclareOption{ltxdoc}{}` vide pour éviter l'avertissement « option inconnue ».

**A1 — `\RequirePackage{datatool}` chargé deux fois**  
Double chargement ligne 29–30 de `seqenseigne-data.dtx`. Aucun effet de bord grâce à la déduplication de `\RequirePackage`, mais indicateur d'un copier-coller résiduel. Corrigé.

**A1 — `\PassOptionsToPackage` manquant pour `seqenseigne-data`**  
L'option `ltxdoc` était passée à `theme`, `core` et `legacy` mais pas à `data`. Corrigé.

**A2 — `\DTLcleardb` incomplet dans `\seq@basesobjectifs@filter@niveau`**  
La fonction vidait les bases S01 à S14 explicitement mais oubliait S15 et S16. Lors d'un changement de niveau (ex. N11 → N07), les bases S15 et S16 conservaient les données du niveau précédent, ce qui pouvait produire des tableaux de suivi incorrects. Corrigé par la boucle `\forloop` sur `\seq@maxsequences`.

**A3 — `longtabu` obsolète**  
`longtabu` (paquet `tabu`) est absent de nombreuses distributions récentes. Les environnements `titreFiche` (legacy) et `seqEvalQCM` (core) ont été migrés vers `longtblr` et `tblr` de `tabularray`.
