# seqenseigne

Paquet LaTeX pour la production de documents pédagogiques en mathématiques (collège).

Développé et maintenu par **Laurent Coste**.  
Version actuelle : **1.0-dev**

---

## Présentation

`seqenseigne` structure la production des documents d'une pédagogie de type **classe inversée** :

- **Livrets de séquence** — prérequis, objectifs, révisions, carte mentale, méthodes, trois séries d'exercices (fondamentale / avancée / exploration), corrigés
- **Évaluations sommatives** — QCM, exercices classiques, barème, corrigés
- **Plans de travail** — version libre (saisie manuelle) ou automatique (depuis les bases de données)
- **Suivi de classe** — tableaux de maîtrise par élève, par séquence et par période

Le paquet couvre les cycles 3 et 4 du collège français (niveaux N07 à N12).

---

## Installation

### Option 1 — Répertoire local (recommandé pour usage personnel)

Copier tous les fichiers `.sty` dans le répertoire de l'utilisateur TeX :

```
~/.texlive/texmf-local/tex/latex/seqenseigne/
```

Puis mettre à jour la base de données TeX :

```bash
mktexlsr
```

### Option 2 — Même répertoire que le document

Copier `seqenseigne.sty` et les quatre modules dans le répertoire du fichier `.tex` à compiler.

### Fichiers à déployer

```
seqenseigne.sty          ← coordinateur principal
seqenseigne-core.dtx     ← macros structurelles
seqenseigne-data.dtx     ← chargement et accès aux données
seqenseigne-theme.dtx    ← couleurs, boîtes, styles
seqenseigne-legacy.dtx   ← compatibilité ascendante
```

---

## Compilation

Tous les documents utilisent `pdflatex` (LuaLaTeX et XeLaTeX non testés).

### Documents sans données CSV

```bash
pdflatex mon-document.tex
```

Pour les livrets et évaluations qui génèrent des corrigés, **deux passes** sont nécessaires et les sous-répertoires doivent être créés au préalable :

```bash
mkdir -p Corriges Annexes
pdflatex mon-livret.tex
pdflatex mon-livret.tex
```

### Documents avec données CSV

Ces documents chargent des bases `.dbtex` précompilées via `datatooltk-gui` :

```bash
pdflatex mon-suivi.tex
```

Voir la section [Données pédagogiques](#données-pédagogiques) pour la structure attendue.

---

## Démarrage rapide

### Livret de séquence (sans données CSV)

```latex
\documentclass[a4paper,11pt]{article}
\usepackage{seqenseigne}

\begin{document}

\seq@setColors{geometrie}
\seqCreeCompteurs
\seqInitCorriges
\seqInitAnnexes

\begin{seqPrerequis}
  \item Carré et racine carrée
\end{seqPrerequis}

\begin{seqObjectifs}
  \item Utiliser le théorème de Pythagore
\end{seqObjectifs}

\begin{seqSerieExos}{1}
  \begin{seqExercice}[nom=Hypoténuse]
    Le triangle $ABC$ est rectangle en $A$, $AB=3$, $AC=4$. Calculer $BC$.
    \seqCorrige{$BC^2 = 9+16 = 25$, donc $BC=5$.}
  \end{seqExercice}
\end{seqSerieExos}

\seqAfficheAnnexes
\seqAfficheCorriges

\end{document}
```

### Évaluation

```latex
\documentclass[a4paper,11pt]{article}
\usepackage{seqenseigne}

\begin{document}

\titreEval[
  numSeq=1, titreSeq=Pythagore,
  niveauDiff=fondamental,
  etab=Collège Exemple, classe={4\ieme{}A}
]

\begin{seqEvalExercice}[nom=Calcul]
  Calculer $BC$ dans un triangle rectangle en $A$ avec $AB=5$, $AC=12$.
  \corrigeExoEval{$BC^2 = 25+144 = 169$, donc $BC=13$.}
\end{seqEvalExercice}

\seqEvalAfficheCorriges

\end{document}
```

Des exemples complets compilables sont disponibles dans le répertoire [`examples/`](examples/).

---

## Données pédagogiques

Les macros d'accès automatique (`\seqSequenceGetNom`, tableaux d'objectifs, plans de travail automatiques, suivi de classe) nécessitent des fichiers de données précompilés.

### Bases `.dbtex`

Générées par **datatooltk-gui** à partir de fichiers CSV, puis placées dans un répertoire accessible :

```
param_niveaux.dbtex
C03_themes.dbtex    C03_sequences.dbtex
C03_connaissances.dbtex    C03_objectifs.dbtex
C04_themes.dbtex    C04_sequences.dbtex
C04_attendus_fin_C03.dbtex
C04_connaissances.dbtex    C04_objectifs.dbtex
```

Chargement dans le document :

```latex
\seqSetDataPath{../../../}   % chemin vers les .dbtex (défaut)
\seqLoadData
```

### CSV de suivi (pour les documents de suivi de classe)

```
liste_eleves.csv          Numero, Nom, Prenom
periodes.csv              Periode
P1-sequences.csv          Code, Nom, Debut, Fin
P1bilan.csv               Numero, S01, S02, ...
S01Suivi.csv              Numero, 01, 02, ...
```

Codes de maîtrise utilisés dans les CSV :

| Code | Signification | Couleur |
|------|--------------|---------|
| `I`  | Insuffisant | Rouge |
| `F`  | À consolider | Jaune |
| `A`  | Satisfaisant | Vert clair |
| `E`  | Très bon | Vert foncé |
| `NE` | Non évalué | — |
| `-`  | Absent / non concerné | — |

---

## Architecture du paquet

```
seqenseigne.sty
├── seqenseigne-data.dtx    Chargement et filtrage des données (.dbtex, CSV)
├── seqenseigne-theme.dtx   Couleurs, boîtes tcolorbox, styles visuels
├── seqenseigne-core.dtx    Macros structurelles (livret, éval, suivi, plan)
└── seqenseigne-legacy.dtx  Alias de compatibilité (anciens noms sans préfixe)
```

L'ordre de chargement est imposé par `seqenseigne.sty` : `data` → `theme` → `core` → `legacy`.

### Thèmes de couleur

Chaque thème correspond à un domaine mathématique :

| Valeur | Domaine | Couleurs |
|--------|---------|---------|
| `nombres` | Nombres et calcul | Rouge / Jaune |
| `donnees` | Organisation des données | Bleu / Canard |
| `grandeurs` | Grandeurs et mesures | Marron / Orange |
| `geometrie` | Espace et géométrie | Violet / Vert |
| `algorithmique` | Algorithmique | Rose / Lime |
| `gris` | Neutre (défaut) | Gris |

### Conventions de nommage

- Macros publiques : `\seqNomDeLaMacro`
- Macros internes : `\seq@NomDeLaMacro`
- Variables de couleur : `\seqCouleurNomDeLaCouleur`
- Environnements : `seqNomDeLEnvironnement`
- Alias legacy (anciens noms) : définis dans `seqenseigne-legacy.dtx`

---

## Référence rapide des macros principales

### Livret de séquence

| Macro / Environnement | Rôle |
|----------------------|------|
| `\seqTitreLivret[codeNiveau=, codeSequence=]` | Titre, en-têtes, init compteurs |
| `\begin{seqPrerequis}` | Boîte prérequis |
| `\begin{seqObjectifs}` | Boîte objectifs de fin de séquence |
| `\begin{seqSerieExos}{N}` | Série d'exercices (0=révision, 1=F, 2=A, 3=E) |
| `\begin{seqExercice}[nom=, obj=]` | Exercice numéroté |
| `\seqCorrige{texte}` | Corrigé d'un exercice (écrit dans `Corriges/`) |
| `\begin{seqMethode}{titre}{énoncé}` | Méthode clé numérotée |
| `\begin{seqNotion}{titre}{intro}` | Notion numérotée |
| `\begin{seqDefinition}{titre}{intro}` | Définition numérotée |
| `\begin{seqPropriete}{titre}{intro}` | Propriété numérotée |
| `\begin{seqCarteMentale}` | Boîte carte mentale TikZ |
| `\seqAfficheCorriges` | Affiche les corrigés regroupés en fin de document |
| `\seqAfficheAnnexes` | Affiche les annexes en fin de document |

### Évaluation

| Macro / Environnement | Rôle |
|----------------------|------|
| `\titreEval[numSeq=, titreSeq=, niveauDiff=, etab=, classe=]` | Titre, barème auto, init |
| `\begin{seqEvalBareme}` | Tableau de barème |
| `\seqEvalBaremeItem{nom}{points}` | Ligne de barème |
| `\begin{qcm}[ptOK=, ptPartiel=, ptKO=, nbReps=]` | QCM avec tableau automatique |
| `\seqEvalQCMItem{question & repA & repB & repC}` | Ligne de QCM |
| `\begin{seqEvalExercice}[nom=]` | Exercice classique numéroté |
| `\corrigeExoEval{texte}` | Corrigé (écrit dans `Corriges/`) |
| `\seqEvalAfficheCorriges` | Affiche les corrigés sur page impaire |

### Plan de travail

| Macro / Environnement | Rôle |
|----------------------|------|
| `\begin{titrePlan}[numSeq=, titreSeq=, etab=, classe=, theme=]` | Plan libre (2 colonnes) |
| `\begin{seqBloc}{titre}` | Bloc de premier niveau |
| `\begin{blocN2}` | Sous-liste imbriquée |
| `\seqBoiteTitrePlan[titre=, afficheSeq=, affichePlan=]` | Titre plan automatique |
| `\seqPlanObjectif{niv}{seq}{obj}{notions}{F}{A}{E}` | Bloc objectif avec exercices |
| `\seqPlanReperesNiveaux[codeNiveau=, codeSequence=, ...]` | Repères temporels |

### Suivi de classe

| Macro | Rôle |
|-------|------|
| `\seqLoadDataSuivi{codeNiveau}` | Charge bases + CSV de suivi |
| `\seqTitreSuivi{classe}{titre}{annee}` | En-têtes/pieds de page |
| `\seqSuiviAnnuelParEleve[niveau=]` | Tableau par élève, toute l'année |
| `\seqSuiviAnnuelParSequence[niveau=, sequence=]` | Tableau par séquence |
| `\seqSuiviSequence{niv}{seq}` | Raccourci + saut de page |
| `\seqSuiviPeriodiqueParSequence[niveau=, periode=]` | Bilan de période par séquence |
| `\seqBilanPeriodiqueParEleve[periode=, annee=, niveau=, nomClasse=]` | Bilan par élève |

### Fiche de suivi de classe (legacy)

| Macro / Environnement | Rôle |
|----------------------|------|
| `\begin{titreFiche}[numSeq=, titreSeq=, etab=, classe=]` | Tableau de suivi imprimable |
| `\seq@ligne@eleve{Nom Prénom}` | Ligne élève dans le tableau |

### Accès aux données

| Macro | Rôle |
|-------|------|
| `\seqLoadData` | Charge toutes les bases .dbtex |
| `\seqSetDataPath{chemin/}` | Définit le chemin vers les .dbtex |
| `\seqSequenceGetNom{niv}{seq}` | Titre d'une séquence |
| `\seqSequenceGetNumero{niv}{seq}` | Numéro dans la progression |
| `\seqObjectifGetNom{niv}{seq}{obj}` | Libellé d'un objectif |
| `\seqConnaissanceGetNom{niv}{seq}{conn}` | Libellé d'une connaissance |
| `\seqNiveauGetNomCourt{niv}` | Nom court du niveau (ex. « quatrième ») |
| `\seqTableauObjectifs[niveau=, sequence=]` | Tableau des critères de maîtrise |
| `\seqTableauPrerequis[niveau=, sequence=]` | Tableau des prérequis |
| `\seqSetColors{niv}{seq}` | Thème couleur depuis les bases |

---

## Dépendances

Le paquet charge automatiquement les paquets suivants. Ils doivent être disponibles dans la distribution TeX (TeX Live 2022+ recommandé) :

`inputenc`, `fontenc`, `lmodern`, `babel` (french), `geometry`, `fancyhdr`, `lastpage`, `multicol`, `multirow`, `amsmath`, `amsfonts`, `amssymb`, `tcolorbox` (theorems, breakable, skins), `tabularray` (booktabs, longtable), `tabularx`, `xltabular`, `booktabs`, `xcolor`, `colortbl`, `xkeyval`, `xifthen`, `etoolbox`, `kvoptions`, `forloop`, `datatool`, `tikz` (babel, intersections, mindmap), `tkz-tab`, `tkz-base`, `tkz-euclide`, `hyperref`, `scratch3`, `eurosym`, `pifont`, `enumitem` (inline), `datetime`, `environ`, `xintexpr`, `adjustbox`

---

## Documentation

- **Manuel utilisateur** : `seqenseigne-doc.dtx` (compilerait comme document `.dtx` via `ltxdoc`)
- **Documentation développeur** : `seqenseigne_devdoc.tex`
- **Exemples compilables** : répertoire `examples/`

---

## Licence

Usage personnel et éducatif.  
Contacter l'auteur pour toute diffusion ou réutilisation.
