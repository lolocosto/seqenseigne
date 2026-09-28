# Redémarrage v0.13.7.3 — Wrapping de sélection + générateurs QCM/Liste

## Périmètre

Reprise du chantier éditeur LaTeX après les deux hotfixes v0.13.7.2.2/.3
sur le parseur. Cette livraison couvre quatre items du cadrage Phase 2
sur cinq (le navigateur d'images est différé en v0.13.7.4, le
générateur de tableau en v0.13.7.5) :

1. **Wrapping de sélection** avec marqueur `•` (BULLET, U+2022)
   convention héritée de Texmaker
2. **Commandes additionnelles** : `\newline`, `\smallskip`, `\ldots`
3. **Générateur de QCM** avec mini-modale paramétrable
4. **Générateur de liste** avec palette `\ding`

## Wrapping de sélection (marqueur •)

### Convention

Le caractère `•` (U+2022) dans un snippet indique l'emplacement où le
texte sélectionné par l'utilisateur sera inséré.

- **Sélection présente** : `•` est remplacé par la sélection, curseur
  positionné juste après le snippet inséré.
- **Sélection vide** : `•` est retiré, curseur positionné à sa place
  (l'utilisateur peut taper directement à l'emplacement attendu).
- **Plusieurs `•` dans un snippet** : seul le PREMIER reçoit la
  sélection ; les suivants sont remplacés par chaîne vide (sécurité).

### Exemples

| Sélection | Snippet | Résultat |
|---|---|---|
| `abc` | `\textbf{•}` | `\textbf{abc}` curseur après `}` |
| (vide) | `\textbf{•}` | `\textbf{}` curseur entre `{}` |
| `x` | `$•$` | `$x$` |
| `pi` | `\frac{•}{}` | `\frac{pi}{}` curseur en fin |

### Snippets concernés

21 snippets sur 53 ont reçu le marqueur dans cette livraison :

- **Maths** : `$..$`, `$$..$$`, `\frac`, `\seqFrac`, `\sqrt`, `^`, `_`
- **Mise en page** : `\centerline`, **Gras**, **Italique**
- **Compléter** : `\acompleter`
- **Boîtes pédago** : `seqDefinition`, `seqPropriete` (corps entoure la sélection)
- **Boîtes titrées** : `boiteTitreGen`, `\seqBoiteJaune`, `\boiteJauneModere`
- **Mise en évidence** : Gras, Italique, `\cellVert`, `\acompleter`
- **Annexe** : `\seqAnnexe`

Les snippets multi-lignes (environnements `itemize`, `enumerate`,
`align`, `cases`, `seqColEnum`, `seqColItem`) **ne** portent **pas** de
marqueur : la sélection est écrasée par le snippet (cf. cadrage Q2 —
le besoin de transformer une sélection multi-ligne en items est couvert
par le générateur de liste).

### Comportement après wrapping : reliquat noté

Pour les snippets comme `\frac{•}{}`, après wrapping le curseur est en
**fin** du snippet, pas dans le `{}` vide du dénominateur. Pédagogiquement
plus utile serait : curseur au premier `{}` vide rencontré APRÈS le
marqueur (si présent). À considérer en v0.13.7.x si l'usage le justifie.

## Commandes additionnelles

Ajout de :
- `\newline` dans le groupe `mise_en_page` (saut de ligne forcé sans
  nouveau paragraphe — utile dans les éléments inline comme un cadre
  de réponse)
- `\smallskip` dans `mise_en_page` (petit espace vertical, en
  complément de `\medskip` et `\bigskip` déjà présents)
- `\ldots` dans `maths_inline` (points de suspension bas en ligne —
  utile dans les énoncés mathématiques)

## Générateur de QCM

Bouton « ⊞ QCM » dans la rangée de générateurs en tête du panneau
Outils. Au clic, ouvre une mini-modale avec :

- **Nombre de questions** (1-20, défaut 3)
- **Nombre de réponses (colonnes)** : 2, 3, 4 ou 5 (défaut 3)
- **Bloc d'explication** : afficher (texte standard du paquet) ou
  masquer (défaut)
- **Scoring** en bloc dépliable optionnel :
  - `ptOK` : barème toutes bonnes réponses (ex. "1 point")
  - `ptPartiel` : barème partiellement bon (ex. "0,5 point")
  - `ptKO` : barème au moins une mauvaise (ex. "0,5 point")

Le scoring est inséré dans `\begin{seqQcm}[…]` **uniquement si les
trois champs sont remplis** (cohérent avec la logique tout-ou-rien du
paquet `.dtx`).

### Squelette généré

```latex
\begin{seqQcm}[nbReps=3,explication=non]
    \midrule \seqQcmQuestion{} &  &  &  \\
    \midrule \seqQcmQuestion{} &  &  &  \\
    \midrule \seqQcmQuestion{} &  &  &  \\
            \bottomrule
\end{seqQcm}
```

Avec scoring rempli :

```latex
\begin{seqQcm}[nbReps=3,explication=non,ptOK=1 point,ptPartiel=0,5 point,ptKO=0,5 point]
    \midrule \seqQcmQuestion{} &  &  &  \\
    ...
\end{seqQcm}
```

Conformité au paquet : `\midrule` séparateurs, `\\` de fin de ligne et
`\bottomrule` final sont écrits par le générateur exactement comme
attendu par le `.dtx` du paquet.

## Générateur de liste

Bouton « ☰ Liste » dans la rangée de générateurs. Mini-modale avec :

- **Type de liste** :
  - `itemize` : à puces
  - `enumerate` : numérotée
  - `seqColItem` : à puces multi-colonnes
  - `seqColEnum` : numérotée multi-colonnes
- **Nombre d'items** (1-20, défaut 3)
- **Nombre de colonnes** : champ visible uniquement pour les types
  multi-colonnes (`seqCol*`), valeur 2-4 (défaut 2)
- **Puce personnalisée `\ding`** : palette de 8 codes courants en
  pédagogie maths + option champ libre :

| Aperçu | Code | Usage |
|---|---|---|
| ✔ | 52 | Coche pleine (bonne réponse) |
| ✓ | 51 | Coche légère |
| ✘ | 56 | Croix pleine (mauvaise réponse) |
| ✗ | 55 | Croix légère |
| ✏ | 43 | Crayon (à compléter) |
| → | 234 | Flèche droite |
| ▪ | 110 | Carré plein |
| ● | 192 | Disque |

Plus une option « défaut » (puce par défaut LaTeX, sans `\ding`) et
un champ libre pour saisir un code arbitraire.

### Squelette généré

```latex
% Avec ding 52 :
\begin{itemize}[label=\ding{52}]
  \item 
  \item 
  \item 
\end{itemize}

% seqColItem 3 colonnes, ding 234 :
\begin{seqColItem}[nbCols=3,label=\ding{234}]
  \item 
  \item 
\end{seqColItem}
```

## Architecture : mini-modale générique

La mini-modale créée en v0.13.7.2 pour l'engrenage de configuration des
groupes a été **généralisée** pour supporter 4 types via un attribut
`data-type` :

- `config-groupes` : engrenage (v0.13.7.2, comportement inchangé)
- `qcm` : générateur QCM (v0.13.7.3)
- `liste` : générateur Liste (v0.13.7.3)
- `tableau` : placeholder (« disponible en v0.13.7.5 »)

Une seule structure DOM, une seule modale enfant. Le dispatch se fait
dans `_ouvrirMiniModale(type)`, `_validerMiniModale()` et
`_resetMiniModale()` qui regardent le `data-type` courant pour appeler
le bon constructeur de formulaire et le bon handler de validation.

Moins de duplication CSS et de code, et un seul gestionnaire `Esc`
pour fermer la mini-modale.

## Fichiers livrés

```
MODIFIÉS
appli/static/editeur_latex.js                (wrapping + générateurs)
appli/static/app.css                          (+135 lignes : styles générateurs)
appli/static/data/toolbar_seqenseigne.json   (snippets avec • + commandes additionnelles)
appli/doc/redemarrage_v0_13_7_3.md            (NEW)
```

Aucun changement côté backend ni tests. C'est une livraison purement
frontend.

## Vérifications

- Suite pytest : **3267 passed, 5 skipped, 0 failed** (identique à
  v0.13.7.2.3 — pas de modifs Python)
- Sanity JS, JSON, Python : OK
- Test manuel de la logique de wrapping : OK sur 6 cas (sélection
  présente / absente, snippet avec/sans `•`, snippet multi-ligne)

## À tester chez toi

### Scénario A — Wrapping avec sélection

1. Ouvrir l'éditeur LaTeX dans une notion.
2. Taper « le rapport pi sur 4 » dans la zone.
3. Sélectionner « pi sur 4 ».
4. Cliquer le bouton « **Gras** » dans le groupe Mise en évidence.
5. **Vérifier** : la zone contient « le rapport \textbf{pi sur 4} »,
   curseur juste après le `}`.

### Scénario B — Wrapping sans sélection

1. Placer le curseur au milieu d'un texte (sans sélection).
2. Cliquer « **Italique** ».
3. **Vérifier** : `\textit{}` est inséré, **curseur entre les `{}`**
   prêt pour la frappe (pas après le `}`).

### Scénario C — Snippet multi-ligne avec sélection

1. Sélectionner « foo » dans le texte.
2. Cliquer « **itemize** » dans le groupe Listes.
3. **Vérifier** : la sélection est **écrasée** par le snippet (le mot
   « foo » disparaît). Comportement attendu (cf. cadrage Q2).
4. Pour transformer une sélection en items, utiliser le **générateur
   de liste** (scénario E).

### Scénario D — Générateur QCM

1. Sur l'énoncé d'un exercice, ouvrir l'éditeur LaTeX.
2. Cliquer « **⊞ QCM** » dans la rangée Générateurs.
3. **Mini-modale s'ouvre** : 3 champs (questions, réponses, explication)
   et un bloc dépliable « Scoring ».
4. Saisir : 5 questions, 4 réponses, explication=non.
5. Cliquer « Insérer le QCM ».
6. **Vérifier** : le squelette est inséré dans la zone d'édition :
   ```
   \begin{seqQcm}[nbReps=4,explication=non]
       \midrule \seqQcmQuestion{} &  &  &  &  \\
       (5 lignes de \midrule \seqQcmQuestion + 4 cellules)
               \bottomrule
   \end{seqQcm}
   ```
7. Refaire avec scoring rempli (ptOK=1, ptPartiel=0.5, ptKO=0.5).
8. **Vérifier** : les 3 options scoring apparaissent dans
   `\begin{seqQcm}[...]`.

### Scénario E — Générateur de liste

1. Cliquer « **☰ Liste** » dans la rangée Générateurs.
2. Sélectionner type « À puces (itemize) », 5 items, puce ✔.
3. Cliquer « Insérer la liste ».
4. **Vérifier** : le snippet est inséré :
   ```
   \begin{itemize}[label=\ding{52}]
     \item 
     \item 
     \item 
     \item 
     \item 
   \end{itemize}
   ```
5. Refaire avec seqColItem 3 colonnes, puce →.
6. **Vérifier** : `\begin{seqColItem}[nbCols=3,label=\ding{234}]`.

### Scénario F — Générateur tableau (placeholder)

1. Cliquer « **▦ Tableau** ».
2. **Vérifier** : la mini-modale s'ouvre avec le message
   « Le générateur de tableau tblr arrivera en v0.13.7.5 ».
3. Cliquer Annuler ou Esc → la mini-modale se ferme.

### Scénario G — Engrenage toujours opérationnel

1. Cliquer ⚙ dans le header.
2. **Vérifier** : la mini-modale s'ouvre en mode config-groupes
   (comportement v0.13.7.2 inchangé). Masquer un groupe fonctionne
   comme avant.

### Scénario H — Esc dans une mini-modale ferme la mini-modale

Pour chacun des 4 modes (config-groupes, qcm, liste, tableau) :
1. Ouvrir la mini-modale.
2. Appuyer Esc.
3. **Vérifier** : la mini-modale se ferme, la modale principale reste
   ouverte (cohérent avec le comportement établi en v0.13.7.2).

### Scénario I — Commandes additionnelles

1. Dans le groupe `mise_en_page`, vérifier la présence de
   « \newline », « \smallskip » et leur insertion (sans wrapping).
2. Dans le groupe `maths_inline`, vérifier « \ldots ».

## Restes pour la suite

- **v0.13.7.4** : navigateur d'images depuis `appli/data/images/`.
  Questions de cadrage à trancher : structure du dossier (sous-dossiers
  par niveau/séquence ou flat ?), chemin inséré dans `\includegraphics{}`
  (relatif ou absolu ?), miniatures de prévisualisation.

- **v0.13.7.5** : mini-générateur de tableau `tblr`. Le bouton
  « ▦ Tableau » est déjà en place, il suffira de remplir le formulaire.

- **v0.13.7.x** : possible amélioration du curseur post-wrapping (cf.
  reliquat noté plus haut — placer le curseur au prochain `{}` vide
  après le marqueur).

## Note technique : architecture du générateur QCM

J'ai pris en compte le squelette précis que tu m'as donné :

```latex
\begin{seqQcm}[nbReps=3,explication=non]
    \midrule \seqQcmQuestion{Question} & réponse A & ... \\
    ...
            \bottomrule
\end{seqQcm}
```

Trois points méritent d'être consignés pour la mémoire collective :

1. **`\midrule`, `\\` et `\bottomrule` sont écrits par l'utilisateur**
   (commentaire du `.dtx` : « doivent être écrits par l'utilisateur,
   en dehors de toute macro »). Donc le générateur les inclut
   explicitement dans le squelette.

2. **Le nombre de cellules de réponse = nbReps**, pas la valeur maximale
   du `colspec` figé en 5 colonnes côté `.dtx`. Le tableau s'adapte
   visuellement (les colonnes non utilisées restent vides).

3. **Logique tout-ou-rien du scoring** : si l'enseignant remplit 1 ou 2
   champs sur 3, les options scoring sont silencieusement ignorées.
   Cohérent avec le test `\ifx\cmdseq@seqQcm@ptOK\relax\else \ifx... \fi`
   du `.dtx` qui n'affiche le bloc scoring que si les trois sont définies.

## Limite à 7 champs « répondus » par question (PDF de test)

Tu m'as envoyé hier un PDF d'aperçu d'exercice QCM (5646409091d81b37.pdf)
où le tableau apparaît **en bas de la page 1** après l'énoncé, avec
l'en-tête « Questions / Affirmations / A B C » répété. C'est le
comportement attendu de `longtblr[rowhead=2]` : si le tableau ne tient
pas dans l'espace restant, il bascule sur la page suivante avec son
en-tête répété. Pas de bug.

Aussi : sur ce PDF, le squelette a **11 questions** avec **3 réponses**
(« réponse A », « réponse B », « réponse C »). Le générateur sait
gérer ça (nbQuestions=11, nbReps=3).
