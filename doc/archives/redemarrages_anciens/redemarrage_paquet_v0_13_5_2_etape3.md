# Redémarrage — Paquet LaTeX v0.13.5.2 étape 3

> Livraison du 9 mai 2026.
> Refonte fonctionnelle de `\seqTitreEval` et `seqEvalExercice` :
> page de titre libre (suppression de la référence à une séquence
> unique), ajout du barème par exercice, suppression du niveau de
> difficulté qui n'a plus de sens dans le nouveau modèle.
>
> **Étape 3 sur 5** du plan de refonte. Nouvelle rupture API par
> rapport à l'étape 2.

## Périmètre de cette livraison

### Refonte de `\seqTitreEval`

**Avant (étape 2)** :
```latex
\seqTitreEval[
    theme=geometrie,
    numSeq=02,
    titreSeq=Test,
    niveauDiff=fondamental,
    etab=Collège Test,
    classe=3eB
]
```

**Maintenant (étape 3)** :
```latex
\seqTitreEval[
    titre=Bilan T1 - Géométrie et arithmétique,
    theme=geometrie,
    etab=Collège Test,
    classe=3eB
]
```

**Changements** :
- **Suppression** des options `numSeq`, `titreSeq`, `niveauDiff`. Une
  éval peut couvrir plusieurs séquences ou un seul objectif d'une
  séquence — pas d'attache à une séquence unique. Le `niveauDiff`
  qui mappait vers un nombre de points (« Ce sujet permet d'obtenir
  dix points ») n'a plus de sens pour une éval qui mélange
  potentiellement plusieurs séries.
- **Ajout** de l'option `titre` (texte libre) en remplacement de
  `numSeq` + `titreSeq`.
- **Conservation** de `theme`, `etab`, `classe`.

**Changements de rendu** :
- **Bandeau supérieur supprimé** (avant : « Séquence 02 »). Le titre
  est maintenant l'unique élément central.
- **Indication de niveau supprimée** à droite (avant : « Niveau
  fondamental »).
- **Bloc « Ce sujet permet d'obtenir N points » supprimé**.
- **« Mise en pratique » → « Évaluation »** dans la mention
  ajoutée à gauche du titre.
- Les consignes pédagogiques (« Toutes les réponses doivent être
  justifiées... ») sont **conservées**.
- La page de titre du corrigé en fin de document est simplifiée de
  la même manière (« Évaluation : corrigé » au lieu de « Mise en
  pratique : corrigé », plus de niveau, plus de bandeau séquence).

### Refonte de `seqEvalExercice`

**Avant (étape 2)** :
```latex
\begin{seqEvalExercice}[nom=Calcul mental]
    Énoncé...
    \seqEvalCorrigeExo{Corrigé...}
\end{seqEvalExercice}
```

**Maintenant (étape 3)** :
```latex
\begin{seqEvalExercice}[titre=Calcul mental, bareme=4 points]
    Énoncé...
    \seqEvalCorrigeExo{Corrigé...}
\end{seqEvalExercice}
```

**Changements** :
- **Renommage** : option `nom` → `titre` (cohérence avec l'option du
  même nom sur `\seqTitreEval`).
- **Ajout** de l'option `bareme` : si renseignée, affichage en
  italique aligné à droite du cartouche, format `[/ <bareme>]` (ex.
  `[/ 4 points]`).
- L'unité du barème (`points`, `pts`, etc.) est portée par la valeur
  utilisateur — le paquet n'ajoute pas d'unité automatique.
- **Réinitialisation propre des options** à chaque ouverture
  (`\let\cmdseq@... \@undefined`) pour éviter que les valeurs d'un
  appel précédent persistent à l'appel suivant. Robustifie le
  comportement par rapport au code original.

### Pas de changement sur

- `seqEvalBareme` + `\seqEvalBaremeItem` (déjà OK)
- `\seqEvalCorrigeExo` + `\seqEvalAfficheCorriges` (déjà OK)
- `seqQcm` + `\seqQcmQuestion` (réglés en étape 2 patch v3)

## Vérifications côté Linux (sandbox)

- Génération `.sty` depuis `.dtx` via `tex seqenseigne.ins` : OK.
- Plus aucune référence active à `niveauDiff`, `numSeq`, `titreSeq`,
  `nbPoints` dans le module `core-eval` (vérifié par `grep`).
- Les références à `numSeq`/`titreSeq` qui restent dans `core.sty`
  et `legacy.sty` concernent **d'autres macros** (`\titrePlan`,
  `\titreFiche`) qui les utilisent légitimement — ne pas confondre.

## À tester côté Windows / MiKTeX portable

Un fichier `test_etape3.tex` est livré dans le ZIP. Il teste :
- Page de titre avec titre libre
- Barème en cartouche d'exercice (Exercice I, Exercice II)
- Exercice sans titre ni barème (Exercice III)
- QCM imbriqué dans `seqEvalExercice` (vérification que les changements
  étape 3 n'ont pas cassé l'intégration QCM réglée en étape 2)
- Génération du corrigé en fin de document

Points à vérifier visuellement :
- La page de titre n'a plus de bandeau « Séquence... » et plus
  d'indication « Niveau... »
- Le bloc « Ce sujet permet d'obtenir N points » a disparu
- Le mot « Évaluation » apparaît à la place de « Mise en pratique »
- Le barème `[/ 4 points]` apparaît à droite des cartouches d'exercice
  qui en ont un
- L'exercice sans titre s'affiche juste « Exercice III » (sans
  les deux points)

## Plan de la suite

- **Étape 4** : nouveaux environnements `seqEvalObjectifs`,
  `seqEvalCriteres`, item langue française intégrable au `seqEvalBareme`.

## Fichiers livrés

```
paquet/
├── seqenseigne.sty                   (inchangé depuis étape 2)
├── seqenseigne.ins                   (inchangé)
├── seqenseigne-core.dtx              (inchangé depuis étape 2)
├── seqenseigne-core-exos.dtx         (inchangé depuis étape 2)
├── seqenseigne-core-eval.dtx         (modifié : refonte fonctionnelle)
├── seqenseigne-legacy.dtx            (inchangé depuis étape 2)
├── seqenseigne-data.dtx              (inchangé)
├── seqenseigne-theme.dtx             (inchangé)
├── seqenseigne-flashcard.dtx         (inchangé)
└── seqenseigne-doc.dtx               (inchangé)
test_etape3.tex                       (NOUVEAU : fichier de test)
```

Plus les `.sty` correspondants, regénérés depuis les `.dtx` par
`docstrip`.

---

*Fin du redémarrage étape 3.*
