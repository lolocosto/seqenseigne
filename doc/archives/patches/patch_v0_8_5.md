# seqenseigne — Patch v0.8.5

**Date** : 26 avril 2026
**Type** : suite de v0.8.4 — fix structurel sur la détection des paquets
manquants + paramétrabilité des bibliothèques tikz.

---

## Audit préalable demandé

Avant de patcher, audit complet de toutes les macros et environnements
LaTeX utilisés dans le contenu des atomes (notions, méthodes, exercices)
de la BDD réelle, pour identifier ceux qui ne sont pas mappés vers un
paquet ou définis par seqenseigne :

- **Environnements inconnus : 0**. La table `MACROS_PAQUETS_EXTERNES` du
  parseur connaît tous les environnements rencontrés (y compris
  `xltabular`, `tblr`, `seqColItem`, etc.).

- **Macros inconnues : 22**, mais toutes des macros utilisateur
  légitimes :
  - macros locales définies dans des fichiers `NXX_SYY_params.tex` de
    séquence (`\tkzFExoI`, `\denomTexte`, `\cerclePlein`, `\rAB`, `\fmt`,
    `\touche`, etc.) ;
  - variables internes `\tkzCalcLength`/`\pgfmathsetmacro`/`\tkzGetLength`
    aux tikzpicture (`\lAB`, `\lBC`, `\total`, etc.) ;
  - une seule vraie incongruité : `\seqObjectifGetNom` — macro de
    seqenseigne qui devrait être dans `paquet_definitions` (à voir
    plus tard, sans urgence).

L'audit conclut que `MACROS_PAQUETS_EXTERNES` **est correcte** sur tous
les paquets utilisés en pratique.

**Mais l'audit a mis en lumière un autre bug structurel** (point 1
ci-dessous) qui explique pourquoi `xltabular` n'était pas chargé alors
qu'il y figure pourtant.

---

## 1. Fix structurel : détection des paquets « déjà chargés »

**Symptôme (S10/Notion 03 et S10/Notion 06)** :

```
! LaTeX Error: Environment xltabular undefined.
```

… alors que :

- le contenu utilise bien `\begin{xltabular}` ;
- `xltabular` **est** mappé dans `MACROS_PAQUETS_EXTERNES` ;
- `_analyser_paquets_utilises()` détecte bien que l'atome utilise le
  paquet ;
- … mais il n'est jamais ajouté au préambule.

**Cause** : la fonction `_paquets_deja_charges_par_seqenseigne()` se
basait sur la table `paquet_requirepackage` pour construire l'ensemble
des paquets « déjà chargés » et donc filtrables des « paquets manquants ».

Or **cette table reflète ce que `\usepackage{seqenseigne}` charge en
entier** (~35 paquets), pas ce que **notre préambule reconstruit** charge
réellement (~28 paquets : `PAQUETS_NOYAU + _PAQUETS_GEOMETRIE +
_PAQUETS_SCRATCH`). Les **11 paquets de différence** étaient à tort
considérés comme déjà chargés et n'étaient jamais ajoutés.

Les 11 concernés : `booktabs`, `datatool`, `datetime`, `eurosym`,
`fancyhdr`, `graphics`, `hyperref`, `lastpage`, `pgf`, `xintexpr`,
**`xltabular`**.

`xltabular` étant le seul effectivement utilisé dans des contenus
d'atomes, c'est le seul qui a remonté un échec en pratique. Les 10
autres étaient des bugs latents qui auraient fini par exploser dès
qu'un atome aurait utilisé une macro de l'un d'eux.

**Fix** : `services/latex_rendu_atome.py::_paquets_deja_charges_par_seqenseigne`
réécrite pour se baser sur `PAQUETS_NOYAU + _PAQUETS_GEOMETRIE +
_PAQUETS_SCRATCH` (importés depuis `services/preambule_atome.py` qui
en est l'autorité), avec les équivalences classiques :

- graphicx ⇆ graphics (mêmes paquet LaTeX) ;
- tikz tire automatiquement pgf, graphics, graphicx, xcolor.

**Vérifié sur la BDD réelle** : S10/Notion 03 et S10/Notion 06 (qui
utilisent `xltabular`) compilent désormais sans erreur. La fonction ne
lit plus du tout `paquet_requirepackage`, c'est pourquoi le test
`test_pas_de_dependance_a_paquet_requirepackage` passe en lui passant
une connexion qui n'a même pas la table.

---

## 2. Bibliothèques tikz paramétrables (suite Q2 v0.8.4)

**Symptôme (S14/Notion 01)** :

```
! Package pgfkeys Error: I do not know the key '/tikz/diamond' and
I am going to ignore it. Perhaps you misspelled it.
```

L'erreur survient sur `\node [decision]` : le style `decision` est défini
avec `shape=diamond`, mais `diamond` requiert la bibliothèque tikz
`shapes.geometric` qui n'était pas chargée.

**Approche v0.8.5** : généraliser le mécanisme initié en v0.8.4 (qui
chargeait `\usetikzlibrary{babel}` en dur dans
`INITIALISATIONS_BIBLIOTHEQUES`) pour rendre la liste **paramétrable**
depuis l'UI.

### Justification du choix « paramétrable »

Certaines bibliothèques tikz sont utilisées via :
- des **styles tikz** (`\node[decision]` → `shapes.geometric`),
- des **clés tikz** (`>=Latex` → `arrows.meta`),
- des **comportements implicites** (babel-french shorthands → `babel`),

… ce que l'analyse de macros ne sait pas détecter. Plutôt que de
maintenir un mapping symbole → bibliothèque, on charge inconditionnellement
un set de bibliothèques courantes, et on laisse l'utilisateur étendre
la liste à la demande.

### Implémentation

- **Configuration** : nouvelle clé `tikz_libraries` dans
  `services/configuration.py::CLES_DEFAUT`, valeur par défaut :
  `'babel,shapes.geometric,arrows.meta,positioning,calc'`.

- **Accesseur typé** : `Configuration.tikz_libraries() -> list[str]` qui
  parse la chaîne CSV en liste, déduplique en préservant l'ordre,
  élimine les vides et les espaces parasites.

- **Préambule** : `services/preambule_atome.py::construire_preambule`
  reçoit un nouveau paramètre `tikz_libraries: list[str] | None = None`
  et émet une **seule ligne** `\usetikzlibrary{lib1,lib2,...}` après
  les inits classiques (`\UseTblrLibrary{booktabs}`), conditionnée à
  la présence de `tikz` dans les paquets chargés. Ordre préservé,
  doublons éliminés.

- **Migration depuis v0.8.4** : l'entrée `'tikz'` dans
  `INITIALISATIONS_BIBLIOTHEQUES` (qui contenait `\usetikzlibrary{babel}`)
  est **retirée** — la valeur par défaut de `tikz_libraries` la contient,
  donc `babel` reste chargée par défaut. Une seule source de vérité
  pour les libs tikz.

- **Propagation** : `generer_tex_atome`, `compiler_un_atome`,
  `iter_compilation` reçoivent tous le paramètre `tikz_libraries` et le
  propagent. Les routes `routes/admin.py::/run` et
  `routes/rendu_atome.py` (3 endroits) lisent `Configuration.tikz_libraries()`
  et passent la valeur.

- **UI** : nouveau champ texte « Bibliothèques tikz à charger
  systématiquement » dans le sous-onglet Admin > Compilation, à côté
  des paramètres timeout et max_erreurs. Pré-rempli à l'ouverture
  depuis la config, persisté à chaque clic sur « Lancer la compilation »
  comme les autres paramètres.

### Avantages

- **Robustesse** : une nouvelle notion utilisant `\node[ellipse]` ne
  plantera pas (couvert par `shapes.geometric` du défaut).

- **Évolutivité** : si demain un atome utilise `decorations.pathmorphing`
  ou `mindmap`, l'utilisateur peut juste ajouter `decorations.pathmorphing`
  dans le champ et relancer — pas besoin de patcher Python.

- **Coût négligeable** : le chargement de ces 5 bibliothèques ajoute
  moins de 100 ms à un run pdflatex.

---

## Fichiers modifiés

- `services/latex_rendu_atome.py` :
  - `_paquets_deja_charges_par_seqenseigne()` réécrite (import depuis
    `preambule_atome`, plus de dépendance à `paquet_requirepackage`).
  - `generer_tex_atome()` : nouveau paramètre `tikz_libraries`,
    propagé à `construire_preambule()`.

- `services/preambule_atome.py` :
  - Entrée `'tikz'` retirée de `INITIALISATIONS_BIBLIOTHEQUES`
    (migrée vers liste paramétrable).
  - `construire_preambule()` : nouveau paramètre `tikz_libraries`,
    émission d'une ligne `\usetikzlibrary{...}` après les inits
    classiques.

- `services/configuration.py` :
  - Clé `tikz_libraries` dans `CLES_DEFAUT` (avec commentaire
    explicatif).
  - Accesseur typé `Configuration.tikz_libraries() -> list[str]`.

- `services/compilation_batch.py` :
  - `compiler_un_atome()` et `iter_compilation()` reçoivent
    `tikz_libraries` et le propagent.

- `routes/admin.py` :
  - `/preview` retourne `tikz_libraries` dans `config`.
  - `/run` lit la querystring `tikz_libraries`, persiste, lit la
    config, passe à `iter_compilation`.

- `routes/rendu_atome.py` :
  - 3 appels à `generer_tex_atome` passent
    `tikz_libraries=config.tikz_libraries()`.

- `templates/index.html` :
  - Nouveau champ texte « Bibliothèques tikz à charger
    systématiquement » dans le sous-onglet Admin > Compilation.

- `static/app.js` :
  - Pré-remplissage du champ depuis la config au chargement.
  - Envoi de la valeur dans la querystring de `/run`.

- `tests/test_v085.py` (nouveau, 19 tests) :
  - 9 tests sur `Configuration.tikz_libraries()` (parsing CSV, dédup,
    espaces, vides, valeurs corrompues).
  - 6 tests sur `_paquets_deja_charges_par_seqenseigne()` (xltabular
    pas dans le set, paquets noyau dedans, équivalences,
    indépendance à `paquet_requirepackage`, paquets externes pas
    marqués chargés).
  - 4 tests sur `CLES_DEFAUT['tikz_libraries']` (présence, type,
    contenu attendu).

- `tests/test_preambule_atome.py` :
  - 3 anciens tests v0.8.4 (codés en dur sur
    `INITIALISATIONS_BIBLIOTHEQUES['tikz']`) **remplacés** par 7
    nouveaux tests sur la liste paramétrable :
    - sans liste, pas d'émission ;
    - avec liste, émission d'une seule ligne ;
    - position correcte (après `\usepackage{tikz}`) ;
    - dédup avec ordre préservé ;
    - filtrage des entrées vides ;
    - liste vide après filtrage → rien d'émis ;
    - régression : `tabularray` reste codé en dur.

- `tests/test_compilation_batch.py` :
  - Mocks de `generer_tex_atome` mis à jour (`**kw` ajoutés à toutes
    les signatures lambda) pour tolérer le nouveau kwarg
    `tikz_libraries`.

---

## Tests

**Nouveau pack v0.8.5** : 19 tests dédiés (`tests/test_v085.py`) +
7 tests adaptés dans `tests/test_preambule_atome.py`.

**Suite complète** : 937 tests verts + 4 skipped (les habituels). Aucune
régression.

---

## Vérification BDD réelle

| Atome | Erreur d'origine | État après v0.8.5 |
|---|---|---|
| N10/S10/Notion 01 | `+ or - expected` (tikz/calc + babel-french) | ✓ Compile, 0 erreur |
| N10/S10/Notion 03 | `Environment xltabular undefined` | ✓ Compile, 0 erreur |
| N10/S10/Notion 06 | `Environment xltabular undefined` | ✓ Compile, 0 erreur |
| N10/S14/Notion 01 | `pgfkeys: tikz/diamond` | ✓ Compile, 0 erreur |

Les 4 cas confirmés.

---

## Effet attendu après déploiement

Sur les 64 notions N10 :

- **Avant v0.8.4** : 43 réussites
- **Après v0.8.4** : 60 réussites (+ 17 fix tikz babel)
- **Après v0.8.5** : ~62-63 réussites (+ S10/03, S10/06 xltabular,
  + S14/01 shapes.geometric)
- Les 1-2 cas restants sont les images manquantes que tu as identifiées
  (à corriger côté BDD/dossier d'images, hors scope appli).

---

## Migration de la config

À la première ouverture de l'appli après déploiement de v0.8.5, la clé
`tikz_libraries` n'existera pas dans `data/configuration.json`. Le
fallback charge la valeur par défaut
`'babel,shapes.geometric,arrows.meta,positioning,calc'` — donc tout
fonctionne directement sans intervention. La clé est créée dans le
fichier dès qu'on clique sur « Lancer la compilation » (la route
persiste tous les paramètres saisis).

---

## Comment tester chez toi

1. Déployer le ZIP, redémarrer le serveur.
2. Aller dans **Admin > Compilation**. Le nouveau champ
   « Bibliothèques tikz à charger systématiquement » est pré-rempli
   avec la valeur par défaut.
3. Lancer une compilation batch sur N10/S10 et N10/S14 (ou tout) — les
   3 notions cibles devraient passer.

Le cache PDF est automatiquement invalidé (le préambule a changé →
hash SHA256 différent → recompilation forcée).

Si tu veux ajouter une bibliothèque (par exemple `decorations.text` pour
des annotations sur chemins courbes), il suffit de la rajouter à la
liste dans le champ et de relancer.
