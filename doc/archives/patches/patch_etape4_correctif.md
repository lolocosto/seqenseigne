# Patch correctif — Paquet LaTeX v0.13.5.2 étape 4

> Livraison du 9 mai 2026, suite à retour de test.
> Une seule correction sur la livraison étape 4 initiale.

## Correction — `\seqEvalObjectifsItem` supprimée

**Symptôme** : à la compilation d'une éval avec un tableau d'objectifs,
l'erreur suivante apparaît :

```
! Misplaced alignment tab character &.
\seqEvalObjectifsItem #1#2->#1 &
                                 #2 & \ding {113} & \ding {113} & \ding {113...
```

**Cause** : c'est exactement la même limite tabularray qui nous avait
fait supprimer `\seqQcmItem` à l'étape 2. Tabularray refuse les macros
qui contiennent des `&` (séparateurs de cellules) ou des `\\` (fins
de ligne) dans leur corps. La macro :

```latex
\newcommand{\seqEvalObjectifsItem}[2]{%
    #1 & #2 & \ding{113} & \ding{113} & \ding{113} & \ding{113} \\
}
```

ne fonctionne pas dans un environnement `tblr` parce que tabularray
ne réussit pas à interpréter les `&` qui apparaissent à l'expansion.

J'aurais dû le voir venir (même contrainte que pour `\seqQcmItem`),
mes excuses pour le recyclage de l'erreur.

**Correction** : suppression pure et simple de la macro
`\seqEvalObjectifsItem`. Chaque ligne du tableau d'objectifs est
désormais écrite en clair par l'utilisateur (ou par l'appli
génératrice) :

```latex
\begin{seqEvalObjectifs}
    Obj. 02 & Pour les nombres décimaux\ldots
        & \ding{113} & \ding{113} & \ding{113} & \ding{113} \\
    Obj. 04 & Calculer le PGCD\ldots
        & \ding{113} & \ding{113} & \ding{113} & \ding{113} \\
\end{seqEvalObjectifs}
```

**Impact pratique** : la verbosité des 4 `\ding{113}` répétés est
sans importance. Ce code sera généré par l'appli (côté Python) au
moment de la production du `.tex` d'évaluation, pas saisi à la main
par l'enseignant.

## Fichier modifié

- `seqenseigne-core-eval.dtx` : suppression de la macro
  `\seqEvalObjectifsItem`, mise à jour de la documentation
  d'utilisation dans le commentaire de l'environnement.

Aucun autre fichier modifié par rapport à la livraison étape 4
initiale.

## Mise à jour du `test_etape4.tex`

Le fichier de test a été mis à jour pour utiliser la nouvelle API
(lignes écrites en clair, sans `\seqEvalObjectifsItem`).

## À tester

Le `test_etape4.tex` corrigé doit maintenant compiler de bout en bout
et produire le tableau d'objectifs avec les 4 colonnes de cases à
cocher comme prévu.
