# Redémarrage v0.15.2.2 — Refonte récap + planches sur nouvelle API du paquet

## Objectif

Deuxième et dernière étape de la refonte (C1) des cartes d'automatisme,
cadrée pour v0.15.2. Tire profit de la **nouvelle API du paquet
`seqenseigne-carte-automatisme` v0.15.2.2** (livrée par Laurent en
amont de cette version) qui unifie fixe/paramétré et expose des macros
publiques simples.

v0.15.2.2 couvre **récap + planches** simultanément (au lieu de
v0.15.2.2 récap puis v0.15.2.3 planches comme initialement planifié) :
la nouvelle API `\seqCartePlanche` unifie fixe et paramétré côté LaTeX,
ce qui rend la refonte des planches triviale et permet de tout livrer
d'un coup.

## Pré-requis côté Laurent — Réimport du paquet

**Important.** Avant de tester, il faut **réimporter** le `.sty` compilé
depuis le nouveau `.dtx` v0.15.2.2 dans la BDD (les macros publiques
sont renommées par rapport à la v0.13.6.2 actuellement en BDD).

```powershell
# Depuis la racine seqenseigne (USB)
.\outils\python\python.exe -m appli.outils.paquet_peupler
```

Macros publiques de la nouvelle API (à vérifier en BDD via
`paquet_definitions` après import) :

| Macro publique | Rôle |
|---|---|
| `\seqInitCartes` | À appeler après `\begin{document}`. Crée 4 flux d'écriture (recaprecto, recapverso, plancherecto, plancheverso) et `\shorthandoff{:;?!}` pour babel-french compatible avec xintexpr. |
| `\seqCarteAutomatisme[opts]{recto}{verso}` | 1 carte complète recto+verso, pour atelier isolé. |
| `\seqCarteRecto[opts]{recto}` | 1 recto seul (utilisé en interne par les flux). |
| `\seqCarteVerso[opts]{verso}` | 1 verso seul (utilisé en interne par les flux). |
| `seqCarteRecap` (env) | Ouvre 2 flux d'écriture vers `recaprecto.tex` et `recapverso.tex`, émet `\input` des deux fichiers en fin. |
| `\seqCarteRecapAjouteCarte[opts]{vars}{recto}{verso}` | Ajoute 1 carte au récap. Émet recto et verso dans les 2 flux. Option `finLigne=oui` insère `\\` (sinon `&`). |
| `\seqCartePlanche[opts]{vars}{recto}{verso}` | 1 planche complète (2 pages = 16 rectos + 16 versos). Unifié fixe et paramétré : `vars` peut être vide. |

Macros **disparues** (anciennement présentes en v0.13.6.2) :
`\seqCarteAuto`, `\seqCartePageRecto`, `\seqCartePageVerso`,
`seqCartePageRecap`, `\seqCarteRectoRecap`, `\seqCarteVersoRecap`.

## Décisions de cadrage tranchées en v0.15.2.2

| # | Question | Décision |
|---|---|---|
| Q1 | Groupement des cartes dans `seqCarteRecap` | **A** — 1 seul env pour tout le niveau, toutes séquences mélangées, triées par séquence puis numéro. |
| Q2 | Périmètre v0.15.2.2 | Récap + planches (gracieux grâce à la nouvelle API unifiée). |
| Q3 | Chantier F2 (suppressions atelier_recap*, plansdetravail) | Dans scope : 6 fichiers + 1 orphelin supprimés. |
| Q4 | Trace de version du paquet | En commentaire en tête du `.tex` généré. |
| Q5 | Tri des cartes | Sequence puis num puis ordre. |
| Q6 | Page de garde | Conservée, format minimal. |
| Q7 | Bug CA13 (`float()` en BDD) | Non corrigé par script ; à faire manuellement (cf. § suivant). |

## Changements v0.15.2.2

### 1. Refonte `services/render_carte_centralise.py`

Refonte complète. **3 wrappers** au lieu de 4 (fusion `planche_fixe` et
`planche_parametree` en `rendre_carte_planche` unique) :

```python
rendre_carte_isole(conn, carte)
    → {'corps': str}
       # corps inclut le groupe { variables + appel } si carte paramétrée
       # appel = \seqCarteAutomatisme[...]{recto}{verso}

rendre_carte_recap(conn, carte, *, fin_ligne=False)
    → {'appel': str}
       # appel = \seqCarteRecapAjouteCarte[..., finLigne=oui?]{vars}{recto}{verso}

rendre_carte_planche(conn, carte)
    → {'appel': str}
       # appel = \seqCartePlanche[...]{vars}{recto}{verso}
       # vars vide si fixe, peuplé si paramétré
```

**Changements de comportement** :

- `rendre_carte_isole` ne renvoie plus `preambule_variables` séparé : les
  variables xint sont placées dans un groupe `{...}` **dans le corps**
  (à l'intérieur de `\begin{document}`), à côté de l'appel à
  `\seqCarteAutomatisme`. Pattern « variables avant l'environnement »
  appliqué localement.
- `rendre_carte_recap` ne renvoie plus de `cellule_recto`/`cellule_verso`
  séparées : la macro `\seqCarteRecapAjouteCarte` côté `.dtx` gère
  elle-même les 2 flux d'écriture. Côté Python, un seul appel suffit.
- `rendre_carte_planche` est unifié : la macro `\seqCartePlanche` gère
  fixe (vars vide) et paramétré (vars peuplé) dans un seul appel. Plus
  d'`AssertionError` côté Python si on passe une carte du mauvais type.
- Toutes les macros publiques portent maintenant `codecouleur` dans
  leurs options (l'environnement parent ne la porte plus).

### 2. Refonte `services/livret_cartes_recap.py`

Refonte complète. **Suppression** d'environ 100 lignes : tout le code
de substitution Python (`_substituer_variables`, `_detecter_variables_non_substituees`,
`_variables_xint_compatibles_latex`, `_resoudre_carte_parametree`)
disparaît.

Structure du `.tex` généré :

```latex
%% Récap des cartes d'automatisme — vue enseignant.
%% Niveau : N10
%% 119 cartes — grille 4 colonnes, rectos puis versos.
%% API paquet seqenseigne-carte-automatisme : 2026/05/26 v0.15.2.2

\documentclass[10pt]{article}
\usepackage[utf8]{inputenc}
... (paquets standards) ...
\usepackage{seqenseigne-core}
\usepackage{seqenseigne-theme}
\usepackage{seqenseigne-carte-automatisme}

\pagestyle{empty}

\begin{document}

\seqInitCartes        % nouvelle macro v0.15.2.2 : crée les flux + shorthandoff

\thispagestyle{empty}
\begin{center}
... page de garde minimale ...
\end{center}
\clearpage

\begin{seqCarteRecap}   % 1 seul env pour tout le niveau (Q1=A)
  \seqCarteRecapAjouteCarte[niveau=N10, sequence=S01, num=1, ..., codecouleur={nombres}]{}{recto_1}{verso_1}
  \seqCarteRecapAjouteCarte[niveau=N10, sequence=S01, num=2, ..., codecouleur={nombres}]{}{recto_2}{verso_2}
  ...
  \seqCarteRecapAjouteCarte[niveau=N10, sequence=S01, num=4, ..., finLigne=oui]{}{recto_4}{verso_4}
  ...
  \seqCarteRecapAjouteCarte[niveau=N10, sequence=S01, num=4, ..., codecouleur={nombres}]{\xintdefiivar N10S01C04_p := randrange(5,95);}{Combien font $\xintiieval{N10S01C04_p}\,\%$ de $100$?}{$\xintiieval{N10S01C04_p}$}
  ...
  \seqCarteRecapAjouteCarte[..., finLigne=oui]{...}{...}{...}  % dernière carte
\end{seqCarteRecap}

\end{document}
```

`finLigne=oui` est positionné toutes les 4 cartes ET sur la dernière
carte (pour garantir le `\\` final dans le tblr).

### 3. Refonte `services/livret_cartes_planches.py`

Refonte complète. **Suppression** d'environ 200 lignes (tout le code
de tirage Python, miroir horizontal, fallback).

Structure du `.tex` généré :

```latex
%% Planches de cartes d'automatisme — vue élève.
%% Niveau : N10
%% 119 planches — 1 planche par carte (16 copies recto + 16 versos).
%% API paquet seqenseigne-carte-automatisme : 2026/05/26 v0.15.2.2

... préambule identique au récap ...

\begin{document}

\seqInitCartes

... page de garde minimale ...

%% Planche N10/S01/CA01
\seqCartePlanche[niveau=N10, sequence=S01, num=1, ..., codecouleur={nombres}]
{}
{Donner la fraction égale à 5 et de numérateur 20}
{$\seqFrac{20}{4}$}

%% Planche N10/S01/CA04
\seqCartePlanche[niveau=N10, sequence=S01, num=4, ..., codecouleur={nombres}]
{\xintdefiivar N10S01C04_p := randrange(5,95);}
{Combien font $\xintiieval{N10S01C04_p}\,\%$ de $100$?}
{$\xintiieval{N10S01C04_p}$}

...

\end{document}
```

Chaque appel `\seqCartePlanche` produit 2 pages (1 recto + 1 verso),
avec `\clearpage` interne. Pour 119 cartes : 238 pages de planches
+ 1 page de garde = 239 pages.

### 4. Adaptation `services/render_carte.py`

Mineure : le service délègue toujours à `rendre_carte_isole`, mais le
préambule du `.tex` n'inclut plus la section "Variables xint en
préambule" (les variables sont désormais dans le corps, dans un
groupe). Ajout de `\seqInitCartes` juste après `\begin{document}`.

### 5. Suppression de code mort résiduel v0.15.2.1

**6 fichiers F2 du chantier suppressions atelier_recap* :**

- `static/atelier_recapcours.js`
- `static/atelier_recapexos.js`
- `static/atelier_plansdetravail.js`
- `routes/recap_cours.py`
- `routes/recap_exos.py`
- `routes/plans_de_travail.py`

**Plus 2 fichiers v0.15.2.1 mort (déjà annoncés à supprimer manuellement
dans la livraison v0.15.2.1) :**

- `services/param_evaluator.py`
- `routes/param.py`

**Plus 1 orphelin v0.15.0.1 :**

- `scripts/renommer_objectifs_v2.py`

Les services Python `livret_recap_cours.py`, `livret_recap_exos.py`,
`livret_plans_de_travail.py` (correspondant aux routes supprimées) sont
**conservés** car ils sont utilisés par l'orchestrateur de compilation et
par `livret_sequence.py`. Seuls les fronts (routes + JS) disparaissent.

### 6. Refonte massive des tests cartes

Fichier `tests/test_v0_13_6_5_2_livrets_manquants.py` :

- 6 tests précédemment skippés en v0.15.2.1 (raisons `P1=α`, `P4`) sont
  **réactivés et réécrits** pour valider la nouvelle stratégie.
- 10 tests qui vérifiaient les anciennes macros (`\seqCartePageRecto`,
  `\seqCartePageVerso`, environnement `seqCartePageRecap`, etc.) sont
  mis à jour pour la nouvelle API.
- 2 tests `*_python_only_message_erreur` sont reconvertis en garde-fous
  « pas de détection Python » (mécanisme de détection abandonné, les
  variables `float(x, n)` partent telles quelles vers xintexpr — c'est
  désormais à l'enseignant de savoir si sa syntaxe est valide xintexpr).

Fichier `tests/test_v0_15_2_1_render_carte_centralise.py` → renommé en
`tests/test_v0_15_2_2_render_carte_centralise.py` avec 16 tests pour
les 3 wrappers et leurs invariants.

Suite complète : **3448 passed, 6 skipped, 0 failed** (vs 3434 passed
en v0.15.2.1 livrée avant nettoyage F2).

## Action manuelle requise — Correction carte N10/S01/CA13

**Bug pédagogique connu** dans la BDD que je n'ai pas corrigé via
script (cf. Q7 : à faire via l'atelier). La carte N10/S01/CA13 contient
dans son champ `variables` :

```latex
\xintdeffloatvar N10S01C13_res := float(N10S01C13_n / 100);
```

L'appel `float(...)` était supporté par l'ancien `param_evaluator`
(Python) mais **n'est pas reconnu par xintexpr**. Avec la nouvelle
stratégie v0.15.2.2 (insertion littérale), xintexpr va planter à la
compilation.

**Procédure de correction** :

1. Ouvrir l'atelier de cartes (interface Flask).
2. Aller sur la carte N10/S01/CA13.
3. Dans le champ `variables`, remplacer :
   ```
   \xintdeffloatvar N10S01C13_res := float(N10S01C13_n / 100);
   ```
   par :
   ```
   \xintdeffloatvar N10S01C13_res := N10S01C13_n / 100;
   ```
   (`\xintdeffloatvar` fait déjà l'évaluation en virgule flottante,
   `float(...)` est redondant et incompatible xintexpr.)
4. Compiler la carte isolément pour confirmer.
5. Recompiler le récap N10 et le livret planches N10 pour valider.

À vérifier après import du nouveau paquet en BDD : faire le tour des
**32 cartes paramétrées N10** pour repérer d'autres usages éventuels
de `float(...)`, `int(...)` ou `round(x, n)` (3 fonctions Python-only).
Une requête SQL utile pour trouver les suspects :

```sql
SELECT niveau, sequence, num, variables
  FROM cartes_automatisme
 WHERE etat_code = 'valide'
   AND (variables LIKE '%float(%' 
        OR variables LIKE '%int(%'
        OR variables LIKE '%round(%,%');
```

## Procédure de déploiement v0.15.2.2

### 1. Pré-déploiement (côté Laurent)

```powershell
# Si pas déjà fait : compiler le .dtx → .sty depuis seqenseigne-carte-automatisme.dtx
cd <USB>\paquet
.\..\outils\miktex\miktex\bin\x64\latex.exe seqenseigne-carte-automatisme.ins

# Vérifier que le .sty a bien la nouvelle API
findstr "\seqCarteAutomatisme\|\seqInitCartes\|seqCarteRecap\|\seqCartePlanche" seqenseigne-carte-automatisme.sty
```

### 2. Déploiement v0.15.2.2

```powershell
# 1. Décompresser le ZIP à la racine seqenseigne\
# 2. Vérifier le MANIFEST
.\outils\python\python.exe appli\outils\verifier_md5.py --racine . --manifest MANIFEST.md5

# 3. Réimporter le paquet dans la BDD (capture les nouvelles macros)
.\outils\python\python.exe -m appli.outils.paquet_peupler

# 4. Lancer la suite de tests
cd appli
..\outils\python\python.exe -m pytest tests -q
# Cible : 3448 passed, 6 skipped (ou comparable)
```

### 3. Validation fonctionnelle

```powershell
# 1. Démarrer Flask
.\lancer.bat

# 2. Dans l'atelier carte : ouvrir N10/S01/CA01 et compiler isolément
# (vérification atelier isolé)

# 3. Corriger N10/S01/CA13 (cf. § "Action manuelle requise" ci-dessus)

# 4. Compiler le Récap N10 :
#    - via l'atelier → portée niveau → livret_cartes_recap
#    - vérifier : 2 pages par séquence environ (recto+verso), grille 4 colonnes,
#      les paramétrées ont des valeurs cohérentes recto/verso

# 5. Compiler les Planches N10 :
#    - via l'atelier → portée niveau → livret_cartes_planches  
#    - vérifier : 1 planche par carte, 16 copies recto + 16 réponses verso,
#      valeurs cohérentes paire par paire pour les paramétrées
```

## Annexe — Pourquoi pas de v0.15.2.3

La roadmap initiale prévoyait :

- v0.15.2.2 : récap
- v0.15.2.3 : planches

La nouvelle API `.dtx` v0.15.2.2 expose `\seqCartePlanche` **unifié**
(fixe et paramétré dans une seule macro). Du coup la refonte côté
Python des planches devient triviale (3 lignes par appel, vs 200 lignes
en v0.15.1.3 avec tirage Python + miroir + fallback). Aucune raison
de séparer ; v0.15.2.2 livre les deux.

Conséquences pour la suite :

- **v0.15.2.3** n'existera pas (numéro sauté). Prochain palier :
  v0.15.3 (C2 — factorisation transverse en `render_atome.py`).
- Le chantier C1 cartes est **clos** avec v0.15.2.2.

## Roadmap post v0.15.2.2

Inchangée par rapport au récap de session :

- **v0.15.3** : (C2) Factorisation transverse `render_atome.py`,
  mutualisant la logique « variables avant l'environnement » entre
  cartes, exercices, notions, méthodes, fiches résumé.
- **v0.15.x** : (C3) Refonte orchestration documents (long terme).
- **v0.16** : Migration atelier séquence vers OO + portée Niveau.

## Récap fichiers livraison v0.15.2.2

### Fichiers nouveaux ou réécrits

- `services/render_carte_centralise.py` — 3 wrappers (refonte complète)
- `services/livret_cartes_recap.py` — refonte complète (~200 lignes → ~180 lignes)
- `services/livret_cartes_planches.py` — refonte complète (~440 lignes → ~150 lignes)
- `services/render_carte.py` — adapté à nouvelle API rendre_carte_isole
- `tests/test_v0_15_2_2_render_carte_centralise.py` — nouveau (remplace test_v0_15_2_1_*)
- `tests/test_v0_13_6_5_2_livrets_manquants.py` — refonte massive (10+ tests adaptés)
- `tests/test_v0_13_6_2_render_carte.py` — 1 test adapté
- `doc/redemarrage_v0_15_2_2.md` — ce document

### Fichiers supprimés

- `services/param_evaluator.py` (v0.15.2.1, déjà mort)
- `routes/param.py` (v0.15.2.1, déjà mort)
- `static/atelier_recapcours.js` (chantier F2)
- `static/atelier_recapexos.js` (chantier F2)
- `static/atelier_plansdetravail.js` (chantier F2)
- `routes/recap_cours.py` (chantier F2)
- `routes/recap_exos.py` (chantier F2)
- `routes/plans_de_travail.py` (chantier F2)
- `scripts/renommer_objectifs_v2.py` (orphelin v0.15.0.1)
- `tests/test_v0_15_2_1_render_carte_centralise.py` (remplacé par v0_15_2_2)

Total : 4 services réécrits, 7 nouveaux tests ou tests refondus,
10 fichiers supprimés.
