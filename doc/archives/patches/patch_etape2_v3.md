# Patch v3 — Paquet LaTeX v0.13.5.2 étape 2

> Livraison du 9 mai 2026, finalisation de l'étape 2 après retour terrain.
> Cette livraison consolide ce qui a marché chez Laurent dans son test
> avec les commandes `*Local` et le remplace dans le paquet définitif.

## Évolutions par rapport au patch v2

### API utilisateur révisée

L'environnement `seqQcm` a une API simplifiée et adaptée aux contraintes
réelles de tabularray.

**Côté utilisateur** :
```latex
\begin{seqEvalExercice}[nom=QCM sur les puissances]
    \begin{seqQcm}[ptOK=un point, ptPartiel=un demi-point, ptKO=un quart de point]
        \midrule \seqQcmQuestion{Texte de la question} & rep A & rep B & rep C \\
        \midrule \seqQcmQuestion{Question suivante} & rep A & rep B & rep C \\
        \midrule \seqQcmQuestion{Encore une} & rep A & rep B & rep C \\
        \bottomrule
    \end{seqQcm}
    \seqEvalCorrigeExo{Corrigé...}
\end{seqEvalExercice}
```

**Points importants** :
- Les `\midrule` séparateurs entre questions, le `\\` final et le
  `\bottomrule` doivent être **écrits en clair** par l'utilisateur.
  Ce n'est pas un choix de design : tabularray refuse les macros qui
  contiennent ces éléments structurels (séparateurs `&`, fins de
  ligne `\\`, règles `\midrule`).
- `\seqQcmQuestion{texte}` produit uniquement le numéro de la question
  (en gras, suivi d'un point, suivi d'un `\quad`) puis le texte.
  Aucun élément structurel.
- Le numéro est calculé via `\therownum` (compteur fourni par
  tabularray, robuste face aux passes multiples du moteur), avec
  décalage de `-2` pour les 2 lignes d'en-tête.

### Macro `\seqQcmItem` supprimée

À la livraison étape 2 initiale, la macro `\seqQcmItem` était définie
ainsi :
```latex
\newcommand{\seqQcmItem}[1] {
    \midrule \seq@Qcm@ItemNum #1 \\
}
```

Elle est **supprimée** : tabularray refuse de la voir s'expanser dans
son corps. Remplacée par `\seqQcmQuestion` qui ne contient ni `\midrule`
ni `\\`.

### Compteur `seqQcmItemNum` supprimé

À la livraison étape 2 initiale, on avait centralisé le compteur
`seqQcmItemNum` dans `core.dtx` pour la numérotation des items du QCM.

Mais ce compteur n'est plus utilisable :
- tabularray fait plusieurs passes pour stabiliser sa mise en page
- chaque passe appelle `\stepcounter{seqQcmItemNum}` au moment de
  rencontrer chaque ligne
- résultat : le compteur saute (1, 2 puis 4, 5 puis 8, 9 ... selon le
  nombre de passes)

Le compteur est donc **supprimé** de `core.dtx`. La numérotation se fait
exclusivement via `\therownum` dans `\seqQcmQuestion`.

Le helper interne `\seq@Qcm@ItemNum` est aussi supprimé (il s'appuyait
sur `seqQcmItemNum`).

### Configuration tabularray globale

Au chargement de `core-exos`, deux templates caption de tabularray
sont désactivés globalement :
```latex
\DefTblrTemplate{caption}{default}{}
\DefTblrTemplate{capcont}{default}{}
```

**Conséquence** : tous les `longtblr` du document n'auront plus la
caption automatique « Table 1 : ... » au-dessus. Concerne tout le
paquet et tous les documents qui l'utilisent. Décision validée par
Laurent : « ça me va si c'est général ».

Note : ceci ne supprime pas le « Suite page suivante » qui apparaît
quand un tableau long est coupé entre deux pages — celui-ci est géré
séparément par tabularray.

### `colspec` figé

Le `colspec` du `seqQcm` est figé à `X[5,c,m]*{5}{X[2,c,m]}` (5 colonnes
de réponses maximum, dimensions 5 pour la question / 2 pour chaque
réponse). Tabularray refuse les macros à l'intérieur du `colspec`.

**Conséquence** : limite à 5 réponses maximum. La mise en page s'adapte
visuellement même avec 2, 3 ou 4 réponses effectives (les colonnes
non utilisées restent vides à droite).

### `\cmidrule{2-5}` figé dans l'en-tête

De même, le `\cmidrule{2-5}` qui sépare la ligne « Questions /
Affirmations » de la ligne « A B C D E » est figé. Le trait du
`\cmidrule` s'adapte visuellement à la zone effective du tableau, donc
pas de débordement même si on a moins de réponses.

### Logique de scoring « tout ou rien »

À la livraison étape 2 initiale, on affichait les règles de scoring
si **au moins l'un** des paramètres `ptOK`/`ptPartiel`/`ptKO` était
défini, en complétant les non-définis par des valeurs par défaut.

**Logique révisée** : on affiche les règles uniquement si les **trois**
paramètres sont définis. C'est plus cohérent : si l'enseignant ne
renseigne qu'un sur trois, on ne peut pas inventer les deux autres.
Mieux vaut tout ou rien.

Le helper `\seq@qcm@regles@scoring` est supprimé (devenu inutile, le
bloc des règles est inliné dans l'environnement).

### Options `largeurQuestion` et `largeurRep` supprimées

Ces options étaient prévues pour ajuster les ratios de largeur des
colonnes. Mais comme tabularray refuse les macros dans `colspec`, on
ne peut pas les utiliser. Suppression pure et simple. Les ratios sont
figés à 5 et 2.

## Limitations imposées par tabularray (récapitulatif)

Les contraintes suivantes sont des limitations de tabularray, pas
des choix de design :

1. **Pas de macro dans `colspec`** : impossible de paramétrer
   dynamiquement la spécification de colonnes. D'où le figement à
   5 colonnes maximum.

2. **Pas de macro contenant des `&`, `\\`, ou `\midrule`** dans le
   corps du tableau. D'où l'écriture en clair par l'utilisateur.

3. **`\stepcounter` à l'intérieur du tableau n'est pas fiable** à
   cause des passes multiples. D'où l'utilisation de `\therownum`.

4. **Pas de macro qui s'expanse en `\cmidrule{...}`** dans l'en-tête.
   D'où le figement à `\cmidrule{2-5}`.

## Vérifications côté Linux (sandbox)

- Génération `.sty` depuis `.dtx` via `tex seqenseigne.ins` : OK.
- Plus aucun doublon de `\newcounter` ou `\newwrite`.
- Compteur `seqQcmItemNum` bien retiré.
- Macro `\seqQcmItem` et helper `\seq@Qcm@ItemNum` bien retirés.
- Helper `\seq@qcm@regles@scoring` bien retiré.
- `\DefTblrTemplate{caption}` et `{capcont}` bien dans `core-exos`.

## À tester côté Windows / MiKTeX portable

Le `.tex` de test (avec `\seqQcmQuestion`, `\midrule`, `\\`, `\bottomrule`)
qui marchait avec les commandes `seqQcmLocal` doit maintenant marcher
identiquement avec les commandes natives `seqQcm` du paquet.

À vérifier :
- Numérotation correcte des questions (1, 2, 3...) sans saut
- En-tête répété sur chaque page pour les QCM longs
- Pas de « Table 1 : » indésirable au-dessus des tableaux
- Adaptation visuelle pour 2, 3, 4 ou 5 réponses

## Fichiers modifiés depuis le patch v2

- `seqenseigne-core-exos.dtx` : refonte complète de l'environnement
  `seqQcm`, ajout de `\seqQcmQuestion`, suppression de `\seqQcmItem`,
  suppression de `\seq@Qcm@ItemNum`, suppression de
  `\seq@qcm@regles@scoring`, ajout des deux `\DefTblrTemplate{}` au
  chargement.
- `seqenseigne-core.dtx` : suppression du compteur `seqQcmItemNum` de
  la liste des compteurs centralisés.
- `seqenseigne-legacy.dtx` : retrait du `\setcounter{seqQcmItemNum}{0}`
  dans `seqBilanQCM` (compteur supprimé, et la macro `\QcmItemNum`
  qu'il accompagnait n'a jamais été définie de toute façon).
- `seqenseigne.sty` : commentaires actualisés.
