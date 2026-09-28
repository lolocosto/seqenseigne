# Finalisation paquet — v0.13.5.2

> Livraison du 9 mai 2026.
> Deux corrections de mise en forme suite à validation visuelle de
> l'étape 4. Le paquet est désormais fonctionnellement complet pour
> v0.13.5.2 ; place au versant appli.

## Corrections de mise en forme

### `seqEvalBareme` : alignement des points à droite

**Avant** : les points apparaissaient juste après le libellé, sans
alignement particulier (`Exercice I 4 points`).

**Cible** : les points alignés à droite (`Exercice I              4 points`).

**Solution** : suppression de la macro `\seqEvalBaremeItem` (qui était
elle aussi sujette à la limite tabularray "pas de macro avec & ou \\")
et passage à un colspec `X[5,l,m] X[r,m]` qui aligne automatiquement
chaque colonne. L'utilisateur écrit :

```latex
\begin{seqEvalBareme}
    Exercice I & 4 points \\
    Exercice II & 4 points \\
    Présentation et usage de la langue française & 1 point \\
\end{seqEvalBareme}
```

Plus besoin de `\hfill` explicite : tabularray gère l'alignement via
la spec de colonne.

### `seqEvalObjectifs` : libellés des niveaux à la verticale

**Avant** : les libellés `Insuffisant / À consolider / Satisfaisant /
Très bon` occupaient horizontalement une grande partie du tableau,
réduisant l'espace disponible pour l'intitulé des objectifs.

**Cible** : libellés tournés à 90° en en-tête de colonne.

**Solution** : `\rotatebox{90}{\textit{...}}` du paquet `graphicx`
(déjà chargé via `tcolorbox`). Pas de nouvelle dépendance.

## Cohérence d'usage

Avec ces corrections, les **trois environnements de tableau** du
modèle eval (`seqEvalBareme`, `seqEvalObjectifs`, `seqQcm`) suivent
désormais le même pattern :

- Pas de macro `*Item` qui produit toute une ligne
- L'utilisateur (ou l'appli génératrice) écrit chaque ligne en clair
  avec ses `&` et son `\\`
- Les contraintes tabularray sont respectées de bout en bout

C'est un compromis assumé : la verbosité côté `.tex` est sans
importance pratique puisque l'appli génère ce code, pas l'enseignant.

## Récap : API publique du module core-eval (v0.13.5.2 finalisé)

### Macros
- `\seqTitreEval[titre, theme, etab, classe]` — page de titre
- `\seqEvalCorrigeExo{corrigé}` — corrigé d'exercice (différé)
- `\seqEvalAfficheCorriges` — affichage des corrigés en fin

### Environnements
- `seqEvalBareme` — barème en début d'éval (lignes : `libellé & points \\`)
- `seqEvalObjectifs` — grille des critères de maîtrise (lignes :
  `code & intitulé & 4 \ding{113} \\`)
- `seqEvalExercice[titre, bareme]` — cartouche d'un exercice

### Module core-exos (compagnon)
- `seqQcm[ptOK, ptPartiel, ptKO, nbReps, explication]` — environnement
  enfant pour QCM (à utiliser dans seqEvalExercice ou seqExercice)
- `\seqQcmQuestion{texte}` — numéro auto + texte de la question

## Vérifications côté Linux (sandbox)

- Génération `.sty` depuis `.dtx` via `tex seqenseigne.ins` : OK.
- `\seqEvalBaremeItem` bien retiré du `.sty` généré.
- `\rotatebox{90}` bien intégré dans le code de `seqEvalObjectifs`.
- Validation visuelle du `\rotatebox` dans tabularray : test isolé
  produisant un PDF correct.

## À tester côté Windows / MiKTeX portable

Le `test_finalisation.tex` livré dans le ZIP teste l'ensemble de l'API
finalisée. Points à vérifier visuellement :
- Dans le barème : « 4 points » alignés à droite sur la même ligne
  que « Exercice I »
- Dans le tableau d'objectifs : libellés des 4 niveaux orientés à 90°
- L'intitulé d'objectif a plus de place horizontale qu'avant
- Le reste du paquet fonctionne identiquement (QCM, exercices, corrigés)

## Plan suivant

Côté paquet, **v0.13.5.2 est terminé**. Prochaines étapes :

1. **Versant appli** : atome Évaluation, schéma BDD, atelier UI
   (v0.13.5.2 puis v0.13.5.3 pour la génération `.tex` depuis BDD)

2. **Sous-version paquet `core-exos` distincte** (à planifier
   ultérieurement) : passage à 4 flags indépendants R/AE, F, A, E
   pour les corrigés. Nécessaire avant le « Livret de corrigés
   d'exos » (v0.13.5.6 dans la roadmap d'implémentation).

## Fichier modifié

- `seqenseigne-core-eval.dtx` : suppression de `\seqEvalBaremeItem`,
  ajustement du `colspec` de `seqEvalBareme`, ajout des `\rotatebox`
  dans `seqEvalObjectifs`.

Aucun autre fichier modifié.
