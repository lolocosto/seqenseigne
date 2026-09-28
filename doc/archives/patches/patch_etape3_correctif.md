# Patch correctif — Paquet LaTeX v0.13.5.2 étape 3

> Livraison du 9 mai 2026, suite à retour de test.
> Une seule correction sur la livraison étape 3 initiale.

## Correction — argument manquant à `\begin{boiteTitreGen}` dans le `CorrList.tex` généré

**Symptôme** : à la compilation d'une éval, l'erreur suivante apparaît
au moment de `\seqEvalAfficheCorriges` :

```
Runaway argument?
{\begin {minipage}[c][70pt][c]{\linewidth } \vfill \textit {\'Evaluat\ETC.
! File ended while scanning use of \boiteTitreGen.
```

**Cause** : `\begin{boiteTitreGen}` prend un argument obligatoire (le
texte du bandeau supérieur). À l'étape 3, on a supprimé le bandeau
« Séquence NN ». Pour la **page de titre** (énoncé), j'avais bien
remplacé l'ancien `\begin{boiteTitreGen}{Séquence \cmdseq@...@numSeq}`
par `\begin{boiteTitreGen}{}` (argument vide explicite).

Mais pour l'**écriture du corrigé différé** (qui est écrit avec
`\write\corrfileeval` et lu plus tard par `\seqEvalAfficheCorriges`),
j'ai oublié de faire la même substitution. Résultat dans le
`CorrList.tex` produit :

```latex
\begin{boiteTitreGen} {\begin{minipage}[c][70pt][c]{\linewidth}...
```

LaTeX prend le `{\begin{minipage}...}` **comme argument obligatoire**
de `boiteTitreGen`. Le `\end{minipage}` ferme alors l'argument (et
non la minipage), et la suite du tableau de bord part en cascade
jusqu'à fin de fichier.

**Correction** : injection d'un argument vide explicite via
`\unexpanded{{}}` dans le `\write\corrfileeval`, ce qui produit dans
le `CorrList.tex` un `\begin{boiteTitreGen}{}` propre, équivalent à
celui de la page de titre.

## Fichier modifié

- `seqenseigne-core-eval.dtx` : ajout de l'argument vide dans le bloc
  `\immediate\write\corrfileeval` de `\seqTitreEval`.

Aucun autre fichier modifié par rapport à la livraison étape 3 initiale.

## À tester

Le `test_etape3.tex` initial devrait maintenant compiler jusqu'au bout
et produire le PDF complet (énoncé + corrigés en fin).
