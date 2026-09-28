# Redémarrage — Paquet LaTeX v0.13.5.2 étape 2

> Livraison du 8 mai 2026.
> Renommages systématiques avec préfixage `seq`, refactorisation de
> l'environnement QCM en environnement enfant utilisable hors-éval,
> centralisation des compteurs dans `core`.
>
> **Étape 2 sur 5** du plan de refonte. Rupture API par rapport à
> l'étape 1. Les `.tex` qui utilisaient les anciens noms (par exemple
> `\titreEval`, environnement `qcm`) ne compileront plus avec ce paquet.
> C'est cohérent avec le scoping §1.4 — les `.tex` historiques sont
> archivés, les PDF font foi.

## Périmètre de cette livraison

### Renommages publics

| Ancien nom | Nouveau nom | Module |
|---|---|---|
| `\titreEval` | `\seqTitreEval` | core-eval |
| `\corrigeExoEval` | `\seqEvalCorrigeExo` | core-eval |
| `\seqEvalQCMItem` | `\seqQcmItem` | core-exos (déplacé) |
| environnement `qcm` | environnement `seqQcm` | core-exos |
| compteur `ExoEvalNum` | compteur `seqExoEvalNum` | core (centralisé) |
| compteur `QcmItemNumCnt` | compteur `seqQcmItemNum` | core (centralisé) |

### Renommages internes (cosmétiques)

| Ancien nom | Nouveau nom | Module |
|---|---|---|
| `\seq@Eval@QcmItemNum` | `\seq@Qcm@ItemNum` | core-exos (déplacé) |
| compteur `i` | compteur `seq@qcm@iter` | core (centralisé) |
| compteur `AlphCode` | compteur `seq@qcm@alphcode` | core (centralisé) |
| commande `\repCodes` | commande `\seq@qcm@repCodes` | core-exos |

### Compteurs centralisés dans `core.dtx`

Tous les `\newcounter` du paquet sont désormais dans `core.dtx`,
indépendamment du module qui les utilise. Avantage : visibilité
globale, pas de dépendance croisée entre modules. Inconvénient :
`core` connaît des compteurs qu'il n'utilise pas lui-même (couplage
faible mais explicite).

Liste finale des compteurs dans `core.dtx` :
- `seqExoEvalNum` (utilisé par `seqEvalExercice` dans core-eval)
- `seqQcmItemNum` (utilisé par `seqQcm` dans core-exos)
- `seq@qcm@iter`, `seq@qcm@alphcode` (helpers internes QCM, utilisés par
  `seqQcm` dans core-exos et `seqBilanQCM` dans legacy)
- `seqBilanExoNum` (utilisé par `seqBilanQCM` et `seqBilanExo` dans
  legacy)
- `flashcardnb` (utilisé par flashcard, déjà là précédemment)

Plus les compteurs du livret de séquence (`SerieExosNum`, `ExoNum`,
`NotionNum`, etc.) qui étaient déjà dans `core` à la base.

### Refactorisation `seqQcm` en environnement enfant

C'est le changement le plus structurant de l'étape 2.

**Avant (modèle 2019)** : l'environnement `qcm` était de premier
niveau et faisait tout en lui-même : numérotation d'exercice,
cartouche `Exercice I : QCM`, écriture du corrigé différé, texte
explicatif, règles de scoring, et tableau QCM. C'était de fait un
doublon de `seqEvalExercice` avec un rendu différent.

**Après (modèle B v0.13.5.2)** : l'environnement `seqQcm` est un
environnement **enfant**. Il ne produit que le contenu spécifique
QCM : texte explicatif (optionnel), règles de scoring (uniquement si
scoring défini), et tableau lui-même. Le cartouche, le numéro
d'exercice et l'écriture du corrigé différé sont délégués à
l'environnement parent.

Conséquence sur l'usage côté `.tex` :

```latex
% Avant
\begin{qcm}[ptOK=un point, ptPartiel=un demi-point, ptKO=un quart de point, nbReps=3]
    \seqEvalQCMItem{...} & ... \\
\end{qcm}
\corrigeExoEval{Corrigé...}

% Après
\begin{seqEvalExercice}[nom=QCM sur les puissances]
    \begin{seqQcm}[ptOK=un point, ptPartiel=un demi-point, ptKO=un quart de point, nbReps=3]
        \seqQcmItem{
            $10^1$ est une autre écriture de &
            10 & 1 & $1 \times 1 \times \ldots \times 1$
        }
        ... autres items ...
    \end{seqQcm}
    \seqEvalCorrigeExo{Corrigé...}
\end{seqEvalExercice}
```

Le QCM peut désormais aussi s'utiliser dans un livret de séquence,
imbriqué dans un `seqExercice`, ce qui n'était pas possible avant.

### Scoring optionnel sur `seqQcm`

Les paramètres `ptOK`, `ptPartiel`, `ptKO` deviennent **optionnels**.
Si aucun n'est défini, le bloc des règles de scoring (« Donner toutes
les bonnes réponses rapporte X. Ne pas donner... ») n'est pas
affiché. Cas d'usage : un QCM en livret de séquence (révision AE) n'a
pas de scoring.

Si l'un au moins des trois paramètres est défini, le bloc est
affiché. Les paramètres non définis prennent leurs valeurs par
défaut (« un point », « un demi-point », « un quart de point »).

### Nouvelle option `explication` sur `seqQcm`

Le bloc d'explication standard (« Cet exercice est un questionnaire à
choix multiples : pour chaque question, il y a une ou plusieurs... »)
est désormais contrôlable :
- `explication=oui` (défaut) : affichage classique
- `explication=non` : pas d'affichage, l'utilisateur rédige son propre
  texte d'introduction si besoin

## Vérifications côté Linux (sandbox)

- Génération `.sty` depuis `.dtx` via `tex seqenseigne.ins` : OK,
  8 fichiers générés, 6115 lignes traitées sans erreur.
- Pas de doublon de `\newcounter` ou `\newwrite` (vérification par
  `grep` sur les `.sty` générés).
- Pas de référence morte aux anciens noms (`ExoEvalNum`, `QcmItemNumCnt`,
  `\titreEval`, `\corrigeExoEval`, `\seqEvalQCMItem`, `\seq@Eval@QcmItemNum`,
  environnement `qcm`, `\repCodes` non préfixé) : vérifié par `grep`.
- Test de chargement minimal bloqué côté Linux par `lmodern.sty`
  indisponible (idem étape 1, dépendance externe sans rapport avec la
  refonte). Mais aucun conflit interne au paquet n'a été détecté.

## À tester côté Windows / MiKTeX portable

L'étape 2 introduit des **ruptures**. Voici les points de test :

### Test 1 — Compilation d'un livret de séquence existant

Aucune macro de livret de séquence n'a été touchée. Compiler un livret
de séquence pour vérifier qu'il n'y a pas de régression de la
centralisation des compteurs.

### Test 2 — Générer une éval test minimale

Le format des `.tex` 2019 ne compile plus (cf. test 3 ci-dessous).
Pour valider l'étape 2, il faut écrire un `.tex` de test avec les
nouveaux noms :

```latex
\documentclass[a4paper,11pt]{article}
\usepackage{seqenseigne}

\begin{document}
\seqTitreEval[
    theme=geometrie,
    numSeq=02,
    titreSeq=Test,
    niveauDiff=fondamental,
    etab=Collège Test,
    classe=3eB
]
\begin{seqEvalBareme}
    \seqEvalBaremeItem{Exercice I}{5 points}
    \seqEvalBaremeItem{Exercice II}{5 points}
\end{seqEvalBareme}

\begin{seqEvalExercice}[nom=QCM]
    \begin{seqQcm}[ptOK=un point, ptPartiel=un demi-point, ptKO=un quart de point]
        \seqQcmItem{
            Question test &
            réponse A & réponse B & réponse C
        }
    \end{seqQcm}
    \seqEvalCorrigeExo{Corrigé du QCM}
\end{seqEvalExercice}

\begin{seqEvalExercice}[nom=Exercice classique]
    Énoncé...
    \seqEvalCorrigeExo{Corrigé...}
\end{seqEvalExercice}

\seqEvalAfficheCorriges
\end{document}
```

Vérifier en particulier :
- La page de titre s'affiche (le rendu peut être à ajuster en étape 3
  car on supprimera `numSeq`/`titreSeq`/`niveauDiff` à ce moment-là)
- Les exercices sont numérotés `Exercice I`, `Exercice II` correctement
- Le QCM s'affiche dans le cartouche de l'exercice (sans son propre
  cartouche additionnel)
- Les corrigés différés s'affichent à la fin via
  `\seqEvalAfficheCorriges`

### Test 3 — Vérifier la rupture annoncée

Un `.tex` qui utiliserait les anciens noms (`\titreEval`, `\corrigeExoEval`,
environnement `qcm`, etc.) doit produire une erreur `Undefined control
sequence`. C'est le comportement attendu — les `.tex` historiques 2019
sont conservés pour archivage uniquement.

## Plan de la suite (étapes 3 à 5)

- **Étape 3 (anciennement étape 4)** : refonte fonctionnelle de
  `\seqTitreEval` (suppression `numSeq`/`titreSeq`/`niveauDiff`, titre
  libre), ajout `bareme=` sur `seqEvalExercice`, paramètre `nom=` →
  `titre=` sur `seqEvalExercice`. Suppression du bloc
  « Mise en pratique : ce sujet permet d'obtenir X points ».
- **Étape 4 (anciennement étape 5)** : nouveaux environnements
  `seqEvalObjectifs`, `seqEvalCriteres`, item langue française
  intégrable au `seqEvalBareme`.

L'ordre des étapes 3 et 4 a été inversé par rapport à la planification
initiale du redémarrage étape 1, parce qu'il vaut mieux faire les
renommages mécaniques avant les modifications fonctionnelles (cf.
discussion en début de session étape 2).

## Fichiers livrés

```
paquet/
├── seqenseigne.sty                   (modifié : commentaires actualisés)
├── seqenseigne.ins                   (inchangé)
├── seqenseigne-core.dtx              (modifié : centralisation compteurs)
├── seqenseigne-core-exos.dtx         (modifié : seqQcm enfant + scoring optionnel)
├── seqenseigne-core-eval.dtx         (modifié : renommages \seqTitreEval, etc.)
├── seqenseigne-legacy.dtx            (modifié : références aux helpers QCM préfixés)
├── seqenseigne-data.dtx              (inchangé)
├── seqenseigne-theme.dtx             (inchangé)
├── seqenseigne-flashcard.dtx         (inchangé)
└── seqenseigne-doc.dtx               (inchangé)
```

Plus les `.sty` correspondants, regénérés depuis les `.dtx` par
`docstrip`.

---

*Fin du redémarrage étape 2.*
