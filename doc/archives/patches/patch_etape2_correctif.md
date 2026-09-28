# Patch correctif — Paquet LaTeX v0.13.5.2 étape 2

> Livraison du 8 mai 2026, suite à retour de test.
> Deux corrections sur la livraison étape 2.

## Correction 1 — coquille `\cmdseq@titreLivret@theme`

**Symptôme** : à l'appel de `\seqTitreEval[theme=...]`, la couleur du
thème n'est pas appliquée.

**Cause** : héritage du copier-coller depuis le code original. Dans
`seqenseigne-core-eval.dtx`, la commande `\seqTitreEval` accepte une
option `theme=` qui définit `\cmdseq@titreEval@theme`, mais le code
appelait `\seq@setColors{\cmdseq@titreLivret@theme}` (avec
`titreLivret`, qui est une autre macro de l'écosystème, pas la bonne).

**Correction** : `\cmdseq@titreLivret@theme` → `\cmdseq@titreEval@theme`
dans `seqenseigne-core-eval.dtx`.

Bien repéré côté Laurent dès la première compilation.

## Correction 2 — bug catcode `@` chez tabularray

**Symptôme** : à la compilation d'une éval contenant un QCM, l'erreur
suivante apparaît à la fermeture de l'environnement `seqQcm` :

```
! Undefined control sequence.
\l__tblr_v_tl ->\cmdseq
                       @seqQcm@largeurQuestion
```

**Cause** : `tabularray` (le moteur derrière `longtblr`) stocke les
directives de la clé `colspec` dans un token-list interne et les
expanse plus tard, dans un contexte où le catcode du caractère `@`
peut avoir repris sa valeur 12 (« autre »). Quand l'expansion arrive,
`\cmdseq@seqQcm@largeurQuestion` est lu comme `\cmdseq` suivi du texte
ordinaire `@seqQcm@largeurQuestion`, ce qui produit l'erreur observée.

**Important** : c'est un **bug latent du code original** qui ne se
manifestait pas avec les versions plus anciennes de tabularray.
Laurent n'avait pas testé d'éval depuis 4 ans, donc le bug n'était
jamais apparu. Ma refactorisation étape 2 n'a pas créé le bug, elle a
juste rendu son apparition certaine sur une version récente de
tabularray.

**Correction** : pré-expansion via `\edef` des valeurs avant qu'elles
ne soient passées à tabularray. Le `\edef\seq@qcm@colspec{X[\cmdseq@seqQcm@largeurQuestion,m] ...}`
résout les `\cmdseq@...` immédiatement, avec `@` encore en catcode 11.
Tabularray reçoit ensuite un token-list contenant uniquement
`X[3,m] *{3}{X[1,c,m]}` (sans aucun `@`), qui s'expansera
sans problème quel que soit le catcode courant.

Même correction appliquée pour le `\SetCell[c=\cmdseq@seqQcm@nbReps]{c}`
dans le corps du tableau, par sécurité.

**Note** : le code analogue dans `seqBilanQCM` (legacy) n'est pas
touché par ce bug parce qu'il utilise `\xltabular` (pas tabularray) et
des dimensions en dur dans son préambule.

## À tester côté Windows

Le `.tex` de test fourni dans le redémarrage étape 2 devrait maintenant
compiler sans erreur. Vérifier en particulier :

- La page de titre s'affiche avec le thème (couleur géométrie pour
  `theme=geometrie`)
- Le tableau du QCM est bien produit avec 3 colonnes de réponses
- Les règles de scoring apparaissent (puisque `ptOK` est défini)
- Les exercices sont numérotés `Exercice I` (QCM) et `Exercice II`
  (classique)
- Les corrigés différés s'affichent à la fin

## Fichiers concernés

- `seqenseigne-core-eval.dtx` : correction coquille
- `seqenseigne-core-exos.dtx` : pré-expansion `colspec` et `nbReps`

Les autres fichiers sont inchangés par rapport à la livraison étape 2
initiale.
