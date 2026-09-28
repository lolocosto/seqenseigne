# Redémarrage v0.15.1.3 — Refonte Récap + Planches de cartes avec nouvelles macros

## Contexte

Le paquet `seqenseigne-carte-automatisme` a évolué pour offrir des
**macros publiques de plus haut niveau** :

- `\seqCartePageRecto[opts]{recto}` / `\seqCartePageVerso[opts]{verso}` :
  émettent 16 copies d'une même carte dans une grille 4×4 (utile pour
  les **planches de cartes fixes**).
- `\seqCarteRecto[opts]{recto}` / `\seqCarteVerso[opts]{verso}` :
  cellules unitaires utilisables dans un `tblr{*{4}{X[c]}}` pour mixer
  des cartes différentes (utile pour les **planches paramétrées** et
  pour la **page de récap**).
- Environnement `seqCartePageRecap[codecouleur=...]` : page complète
  de récap, contenant un `tblr` à 4 colonnes et `\clearpage` final.
- `\seqCarteRectoRecap[opts]{recto}` / `\seqCarteVersoRecap[opts]{verso}` :
  cellules pour le récap.

Les cartes font désormais **69×48mm** (au lieu de 74×52mm) pour faire
tenir une grille 4×4 dans A4 paysage sans débordement.

`\ignorespaces` a été ajouté à la fin de chaque macro publique pour
absorber les espaces parasites des sauts de ligne du source. Le
préambule peut être lu dans le paquet `seqenseigne-carte-automatisme`
fraîchement importé.

Cette livraison **refond les deux services Python** pour utiliser ces
nouvelles macros, et **remplace l'aléatoire LaTeX** par un tirage
Python via `param_evaluator`.

## Changements

### 1. `services/livret_cartes_recap.py` — refonte complète

**Layout** :
- **8 cartes par page** : 4 rectos / 4 versos / 4 rectos / 4 versos
- **1 codecouleur par page** (couleur du thème de la séquence)
- **1 page minimum par séquence** ; pages successives si > 8 cartes

**Cartes paramétrées** : pour le récap, on **fait 1 tirage Python**
(via `param_evaluator.parse_one`) et on substitue les valeurs **en
dur** dans les sources recto ET verso. Pourquoi :
- Le récap est un document de référence : valeurs stables, pas de
  random à chaque compile.
- Le recto et le verso d'une même carte **doivent partager les mêmes
  valeurs** (sinon question et réponse ne correspondraient plus).
- Avec l'environnement `seqCartePageRecap` (basé sur `tblr`), on ne
  peut pas mettre un groupe LaTeX `{...}` englobant 2 cellules (recto
  et verso sont sur des lignes différentes du `tblr` séparées par `\\`).
  Donc impossible de scoper un même `\xintdefiivar` aux deux cellules
  côté LaTeX.

**Code émis** (carte paramétrée) :
```latex
\begin{seqCartePageRecap}[codecouleur=nombres]
    \seqCarteRectoRecap[niveau=N10, sequence=S01, num=4, ...]{Question : $47$} &%
    ...
    \seqCarteVersoRecap[niveau=N10, sequence=S01, num=4]{Réponse : $47$} &%
    ...
\end{seqCartePageRecap}
```
Le `47` est tiré et substitué côté Python.

### 2. `services/livret_cartes_planches.py` — refonte complète

**Layout** :
- **1 planche (page double recto+verso) par carte**
- **16 copies de la même carte par planche** (4×4)
- Pour les **cartes fixes** : 1 appel à `\seqCartePageRecto` + 1 à
  `\seqCartePageVerso` ; les 16 copies sont produites par les macros
  LaTeX (le paquet fait le `tblr` interne et l'inversion miroir).
- Pour les **cartes paramétrées** : 16 tirages Python indépendants
  (via `param_evaluator.tirage_multiple(variables, n=16)`), chaque
  tirage substitué dans recto ET verso (mêmes valeurs des 2 côtés
  pour chaque copie). Émission d'un `tblr` 4×4 avec 16 cellules
  `\seqCarteRecto` puis 16 cellules `\seqCarteVerso` (page verso avec
  inversion miroir par ligne pour correspondance après pliage).

**Sémantique changée par rapport à v0.15.1.2** : auparavant, plusieurs
cartes différentes étaient regroupées sur la même planche (16 cartes
≠ par page). Maintenant, **chaque carte a sa propre planche** avec 16
copies (de la même carte fixe, ou 16 tirages d'une carte paramétrée).
C'est plus aligné avec l'usage pédagogique : on imprime une planche
pour distribuer 16 exemplaires d'une carte donnée à un groupe d'élèves.

### 3. Nouveaux paquets requis dans le préambule

```latex
\usepackage{xintexpr}        % (au lieu de xint)
\usepackage{tabularray}      % pour tblr
\usepackage{tcolorbox}       % explicite (déjà transitif)
```

`xintexpr` charge `xint` automatiquement, plus `\xintdefiivar`, etc.

### 4. Plus de `\seq@*` / `\seqca@*` / `\makeatletter` côté Python

L'ancien code appelait directement les sous-macros internes du paquet
(`\seq@setColors`, `\seqca@recto`, `\seqca@verso`, `\seqca@applytheme`)
ce qui nécessitait des paires `\makeatletter`/`\makeatother`. Maintenant
on utilise **uniquement les macros publiques** (sans `@`), et le `.tex`
généré n'a plus besoin de `\makeatletter`.

C'est plus propre et c'est la pratique recommandée pour utiliser un
paquet LaTeX.

### 5. Marges réduites

`\geometry{a4paper, landscape, margin=2mm}` (au lieu de `hmargin=0.5mm,
vmargin=1mm` qui était à la limite). Avec les cartes 69×48mm, on a
maintenant 297-4×69 = 21mm de marge horizontale totale, donc 10.5mm
par côté avec 2mm de marge geometry — confortable.

## Tests

### Tests existants adaptés (8)

Tous adaptés pour refléter le nouveau comportement :

- `test_livret_cartes_recap_preambule_complet` : vérifie le chargement
  de `xintexpr`, `tabularray`, `tcolorbox` (au lieu de `xint` seul).
- `test_livret_cartes_recap_carte_fixe` : vérifie l'usage des
  nouvelles macros (`\seqCarteRectoRecap`, `\seqCarteVersoRecap`,
  `\begin{seqCartePageRecap}`).
- `test_livret_cartes_recap_carte_fixe_seqCarteAuto_pas_commente` :
  hérite du garde-fou v0.15.1.2 (le bug `'{%' →  '{%\n'`) — adapté
  pour vérifier que les nouvelles macros ne sont jamais accidentellement
  commentées par un `%` sur la même ligne.
- `test_livret_cartes_recap_carte_parametree_dans_groupe` : vérifie
  qu'il n'y a plus de `\xintdefiivar` dans le récap (substitution
  côté Python) et que recto et verso partagent la même valeur.
- `test_livret_cartes_recap_groupe_par_sequence` : vérifie qu'on a au
  moins 2 environnements `seqCartePageRecap` pour 2 séquences.
- `test_livret_cartes_planches_macros_publiques` (renommé) : vérifie
  qu'on n'a plus aucun `\seq@`, `\seqca@`, `\makeatletter` dans le
  corps, et qu'on utilise bien `\seqCartePageRecto`/`\seqCartePageVerso`.
- `test_livret_cartes_planches_inversion_horizontale_verso` : adapté
  pour les cartes paramétrées (l'inversion fixe est désormais cachée
  dans la macro LaTeX `\seqCartePageVerso`).
- `test_livret_cartes_planches_16_cartes_une_page` et `17_cartes...` :
  adaptés à la nouvelle sémantique (1 planche par carte).

### Nouveaux tests garde-fou (3)

1. `test_livret_cartes_planches_parametree_16_tirages_varies` :
   vérifie que les 16 tirages sont variés (au moins 5 valeurs
   distinctes parmi 16, sur `randrange(0,1000)` ; statistiquement
   garanti).
2. `test_livret_cartes_planches_parametree_recto_verso_partagent_valeur` :
   garde-fou **critique** — vérifie que pour les 16 paires de la
   planche, le verso après inversion miroir correspond bien au recto
   en termes de valeur. Sans ce garde-fou, on pourrait avoir 16 tirages
   recto et 16 autres tirages verso → question N et réponse N qui ne
   correspondent pas (bug pédagogique grave).
3. `test_livret_cartes_recap_parametree_recto_verso_meme_valeur` :
   même garde-fou mais pour le récap (1 tirage par carte, partagé
   recto/verso).

### Vérifs

- **Suite Python complète** : **3427 passed, 6 skipped, 0 failed**
  (était 3424 ; +3 nouveaux tests = 3427).
- **Sanity Python** sur les 2 services modifiés : OK
- **Compatibilité** : la signature publique des fonctions
  `generer_livret_cartes_recap(conn, niveau, options, ...)` et
  `generer_livret_cartes_planches(...)` est inchangée. Les options
  ne sont pas utilisées (préambule statique) mais acceptées pour
  compatibilité de signature avec les autres producteurs.

## Limitations connues (à traiter plus tard)

### Évaluateur `param_evaluator` actuellement limité

`param_evaluator.py` supporte :
- `\xintdefiivar NAME := EXPR;` (entier)
- `\xintdeffloatvar NAME := EXPR;` (flottant)
- `\xintdefvar NAME := EXPR;` (auto)
- `randrange(a, b)` — entier dans `[a, b)`
- expressions ternaires Python `(cond) ? {vrai} : {faux}`
- `\ifnumequal{a}{b}{vrai}{faux}` (xint)
- `\newcommand\foo{...}` / `\renewcommand\foo{...}` côté commandes

**Non supporté** :
- `\xintdefiivar A, B := divmod(...);` (assignation parallèle)
- `quo`, `rem` (opérateurs xintexpr divisor/modulo)
- `divmod()` (alias xintexpr)

En cas de variable non supportée : `param_evaluator` lève une exception
et le code Python **conserve le source d'origine** (les `\xintdefiivar`
restent dans le `.tex` final). La compilation LaTeX émettra alors ses
propres valeurs aléatoires via xintexpr — résultat fonctionnel mais
non testé sur ces cas.

**Extension future** prévue si Laurent crée des cartes paramétrées
avec ces syntaxes (notamment CA13 calcul de durée qui utilise
`divmod`). Petite extension propre (~30 lignes).

### Cartes paramétrées du récap : 1 seul tirage stable

Le récap est conçu comme un document de référence pour l'enseignant :
**1 tirage par carte** (recto et verso partagent les mêmes valeurs).
Pour avoir un nouveau tirage, il faut recompiler depuis Python (qui
re-évaluera les variables).

C'est intentionnel : le récap est destiné à être imprimé une fois et
consulté souvent, pas régénéré à chaque cours. Les **planches**, elles,
ont 16 tirages différents (pour 16 élèves).

## Fichiers livrés

```
MODIFIÉS
  appli/services/livret_cartes_recap.py             (refonte complète)
  appli/services/livret_cartes_planches.py          (refonte complète)
  appli/tests/test_v0_13_6_5_2_livrets_manquants.py (8 tests adaptés
                                                     + 3 nouveaux)

NOUVEAU
  appli/doc/redemarrage_v0_15_1_3.md                (cette note)
```

**Non livré** : le paquet `seqenseigne-carte-automatisme.sty` mis à
jour (gestion séparée par Laurent — import en BDD via le mécanisme
habituel `paquet_definitions`).

## Procédure d'application

### 1. Import du paquet en BDD

Si pas encore fait, importer le nouveau `seqenseigne-carte-automatisme.sty`
dans `paquet_definitions` via les outils habituels. Les 7 macros
attendues en BDD :

- `\seqCarteRecto` (signature `[2][]`)
- `\seqCarteVerso` (signature `[2][]`)
- `\seqCartePageRecto` (signature `[2][]`)
- `\seqCartePageVerso` (signature `[2][]`)
- `seqCartePageRecap` (environnement `[1][]`)
- `\seqCarteRectoRecap` (signature `[2][]`)
- `\seqCarteVersoRecap` (signature `[2][]`)

L'ancienne `\seqCarteAuto` reste utilisable pour la compilation
isolée d'une carte dans l'atelier de prévisualisation. Pas de
suppression nécessaire.

### 2. Sauvegarde de la BDD (par habitude)

```powershell
cd D:\Enseignement\seqenseigne\appli\data
copy seqenseigne.db seqenseigne.db.avant_v0_15_1_3
```

### 3. Décompresser le ZIP à la racine `seqenseigne/`

### 4. Vérifier l'intégrité

```powershell
.\outils\python\python.exe appli\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
```

### 5. Lancer la suite de tests

```
cd appli
..\outils\python\python.exe -m pytest tests -q
```

Attendu : `3417 passed, 17 skipped` (3414 précédent + 3 nouveaux tests).

### 6. Lancer l'app

```
lancer.bat
```

### 7. Tests fonctionnels manuels

**A) Récap des cartes (toutes les cartes fixes)**

Aller sur **Conception de référentiel** > **Référentiel** > **Documents
à publier** > **Récap des cartes d'automatisme** > **Tester**.

Vérifier :
- Le PDF compile sans erreur
- 8 cartes par page (4 rectos en haut, 4 versos en dessous, puis
  4 rectos, 4 versos)
- Toutes les cartes ont un cadre avec bandeau coloré (plus de cartes
  en texte brut comme en v0.15.1.1)
- Couleur de page cohérente avec le thème de la séquence (toutes les
  cartes d'une séquence partagent la même couleur)
- Saut de page entre séquences

**B) Récap des cartes (avec au moins une carte paramétrée)**

Si tu as une carte paramétrée comme N10/S01/CA04 (« Combien font X %
de 100 ? ») :
- Vérifier que la valeur X dans la question correspond bien à la
  valeur dans la réponse (même nombre côté recto et côté verso)
- Vérifier qu'il n'y a plus de `\xintdefiivar` ni de `\xintiieval`
  dans le `.tex` (visible en cliquant « Voir le .tex »)

**C) Planches de cartes fixes**

Aller sur **Planches de cartes d'automatisme** > **Tester**.

Vérifier :
- 1 planche (= 2 pages) **par carte** du niveau
- Chaque planche montre **16 copies** de la même carte (4×4)
- Page verso : ordre miroir par ligne (la carte qui était colonne 1
  du recto se retrouve colonne 4 du verso)
- Plus de débordement à droite (cartes 69mm × 4 = 276mm dans 297mm)

**D) Planches de cartes paramétrées** (si tu en as)

Vérifier :
- 16 valeurs **différentes** sur la planche recto (pas 16 copies
  identiques)
- Sur le verso, **chaque réponse correspond au recto correspondant
  après inversion miroir**

## Bug en passant à noter

Pendant l'analyse du code j'ai revu le bug `_cycle_du_niveau` dans
`services/livret_corriges.py` ligne 72 (déjà signalé en v0.15.1.1) :
le JOIN sur `sequence_code = sdc.code` sans filtre cycle peut retourner
le mauvais cycle pour N10/N12. **Hors scope de cette livraison**, mais
toujours dans la dette.

## Prochaine étape

v0.15.2 — migration de l'atelier Séquence (livret) vers le modèle OO
+ déplacement portée Séquence → Niveau. Gros chantier à cadrer en
début de session prochaine.
