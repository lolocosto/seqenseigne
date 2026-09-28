# Patch v0.9.1 — Trois fixes après le batch méthodes du 27/04/26

**Date** : 27 avril 2026 (soir)

## Vue d'ensemble

Le run batch méthodes du 27/04/26 a produit **144 OK + 12 échecs** sur
156 atomes. Sur ces 12 échecs, 7 viennent de bugs de l'appli, 5 viennent
du contenu BDD ou de l'environnement (`data/images/` vide). Ce patch
corrige les 7 bugs appli en 3 fixes structurels.

## Fix 1 — `\seqInitAnnexes` pour notion et méthode

### Symptôme
3 méthodes plantaient avec « Undefined control sequence » sur `\annfile` :
- N11/S04/Méthode 01 « Déterminer si un nombre entier est premier »
- N11/S04/Méthode 02 « Décomposer en produit de facteurs premiers »
- N12/S04/Méthode 02 « Modéliser et résoudre des problèmes faisant intervenir la divisibilité »

### Cause
Ces 3 méthodes utilisent `\seqAnnexe{...}` pour insérer un algorithme en
annexe. La macro `\seqAnnexe` fait `\immediate\write\annfile{...}`, où
`\annfile` est un descripteur de fichier ouvert par `\seqInitAnnexes`
(qui fait `\newwrite\annfile` puis `\openout\annfile=AnnList.tex`).

Or, dans le pipeline atomique, `\seqInitAnnexes` n'était appelé **que
pour les exercices** (`generer_corps_exercice`, ligne 669). Pour les
notions et les méthodes, `\seqInitAnnexes` n'était jamais émis, donc
`\annfile` n'était pas un descripteur valide quand `\seqAnnexe`
essayait d'écrire dedans.

### Fix
`generer_corps_notion` et `generer_corps_methode` encadrent désormais
le corps par `\seqInitAnnexes` / `\seqAfficheAnnexes` — exactement comme
`generer_corps_exercice` le fait depuis l'origine.

**Effet visuel pour les atomes sans `\seqAnnexe` : zéro.**
`\seqAfficheAnnexes` inclut `AnnList.tex` uniquement si `AnnexeNum > 0`
(`\ifnumcomp{\theAnnexeNum}{=}{0}{}{...}`, voir la définition de
`\seqAfficheAnnexes` dans seqenseigne-core). Coût : un fichier
`AnnList.tex` créé puis non inclus.

### Fichier modifié
`services/latex_rendu_atome.py` — fonctions `generer_corps_notion` et
`generer_corps_methode`.

## Fix 2 — `\wideparen` est dans `yhmath`, pas dans `wideparen`

### Symptôme
3 méthodes plantaient avec `LaTeX Error: File 'wideparen.sty' not found.` :
- N11/S11/Méthode 02 « Transformer une figure par une translation »
- N11/S11/Méthode 04 « Transformer une figure par une rotation »
- N12/S11/Méthode 02 « Transformer une figure par une homothétie »

### Cause
La macro `\wideparen{AB}` (notation française pour l'arc de cercle AB)
était mappée sur le paquet `wideparen` dans `services/paquet_parseur.py`,
ligne 669 :
```python
'\\wideparen': 'wideparen',  # ❌ paquet inexistant
```
Aucun paquet `wideparen.sty` n'existe sur CTAN. La macro vient en
réalité du paquet `yhmath` (Yannis Haralambous, ctan.org/pkg/yhmath),
qui définit aussi `\widetilde`, `\widetriangle`, `\widering`.

### Fix
```python
'\\wideparen': 'yhmath',  # ✓ paquet réel sur CTAN
```

### Fichier modifié
`services/paquet_parseur.py`, dictionnaire `MACROS_PAQUETS_EXTERNES`.

## Fix 3 — Bibliothèque tabularray `varwidth` configurable

### Symptôme
1 méthode plantait avec `Package tabularray Error: Unknown inner key
name 'measure'.` :
- N11/S11/Méthode 05 « Reconnaître et construire des triangles égaux »

### Cause
Cette méthode utilise `\begin{tblr}{colspec={XX[2,c]},measure=vbox}`.
Depuis tabularray v2025A (CTAN 2025-03-11), la clé `measure=vbox` /
`measure=vstore` requiert le chargement explicite de la bibliothèque
`varwidth` via `\UseTblrLibrary{varwidth}`. Sans cette ligne, la clé
n'est pas reconnue.

Auparavant, le préambule reconstruit n'émettait que
`\UseTblrLibrary{booktabs}` (codé en dur dans
`INITIALISATIONS_BIBLIOTHEQUES['tabularray']`).

### Fix
Migration de `booktabs` hors de `INITIALISATIONS_BIBLIOTHEQUES` vers
une nouvelle liste paramétrable `tblr_libraries` (sur le modèle exact
de `tikz_libraries` v0.8.5).

**Différence syntaxique notable :** `\UseTblrLibrary` n'accepte qu'**une
bibliothèque par appel**, contrairement à `\usetikzlibrary` qui prend une
liste séparée par virgules. Le préambule émet donc une commande
`\UseTblrLibrary{lib}` par bibliothèque listée.

**Défaut : `'booktabs,varwidth'`**, qui couvre :
- `booktabs` : `\toprule`, `\midrule`, `\bottomrule` dans `\begin{tblr}`
- `varwidth` : clé `measure=vbox` (cas N11/S11/M05)

### Architecture du fix

```
config (data/configuration.json)
    "tblr_libraries": "booktabs,varwidth"
        ↓
Configuration.tblr_libraries() → list[str]
        ↓
routes/admin.py → iter_compilation(tblr_libraries=...)
routes/rendu_atome.py → generer_tex_atome(tblr_libraries=...)
        ↓
services/compilation_batch.py → compiler_un_atome(...)
services/latex_rendu_atome.py → generer_tex_atome(...)
        ↓
services/preambule_atome.py → construire_preambule(tblr_libraries=...)
        ↓
émission \UseTblrLibrary{lib} pour chaque lib si tabularray chargé
```

### UI

Onglet **Ateliers > Rendu par lot** : nouveau champ texte
« Bibliothèques tabularray à charger systématiquement » (CSV) à côté
du champ tikz, avec `booktabs,varwidth` pré-rempli. Persistance dans
`configuration.json` via la query string de `/run`, comme `tikz_libraries`.

### Fichiers modifiés
- `services/configuration.py` — `CLES_DEFAUT['tblr_libraries']`, helper `tblr_libraries()`
- `services/preambule_atome.py` — paramètre `tblr_libraries` dans `construire_preambule`, application après `\usepackage{tabularray}`. Retrait de `'tabularray'` d'`INITIALISATIONS_BIBLIOTHEQUES`.
- `services/latex_rendu_atome.py` — paramètre `tblr_libraries` dans `generer_tex_atome`, transmission à `construire_preambule`.
- `services/compilation_batch.py` — paramètre `tblr_libraries` dans `compiler_un_atome` et `iter_compilation`, transmission à `generer_tex_atome`.
- `routes/admin.py` — exposition dans GET preview, persistance dans POST run, lecture via `config.tblr_libraries()`.
- `routes/rendu_atome.py` — 3 appels à `generer_tex_atome` ajoutent `tblr_libraries=config.tblr_libraries()`.
- `templates/index.html` — nouveau champ `rdl-tblr-libs` à côté de `rdl-tikz-libs`.
- `static/app.js` — chargement de la valeur dans `compilBatchInit`, lecture dans `_compilLireParams`, passage en QS dans `compilBatchRun`.

## Tests

Total : **+25 tests v0.9.1**, **0 régression** sur la suite complète.

- `tests/test_latex_rendu_atome.py` : +8 tests dans `TestInitAnnexesV091`
  (vérification que `\seqInitAnnexes` et `\seqAfficheAnnexes` encadrent
  bien le corps des notions et des méthodes, dans le bon ordre).
- `tests/test_paquet_parseur.py` : +2 tests dans `TestMacrosPaquetsExternesV091`
  (mapping `\wideparen` → `yhmath` ; aucune macro mappée vers `wideparen`).
- `tests/test_configuration.py` : +7 tests dans `TestTblrLibrariesV091`
  (défaut, persistance CSV, dédup, trim, chaîne vide, robustesse aux
  valeurs non string, indépendance vs `tikz_libraries`).
- `tests/test_preambule_atome.py` : +6 tests dans `TestTblrLibrariesV091`
  (émission `\UseTblrLibrary` par lib, ordre après `\usepackage{tabularray}`,
  dédup, filtre des vides, liste vide, vérification que les libs ne sont
  pas concaténées comme avec tikz). 4 tests préexistants
  (`test_tabularray_charge_use_tblr_library_booktabs` etc.) supprimés
  car ils figeaient l'ancien comportement avant migration. Remplacés
  par `test_pas_de_use_tblr_library_sans_liste` et
  `test_dictionnaire_initialisations_n_inclut_plus_tabularray` qui
  figent le nouveau comportement.

## Suite complète

**1403 tests passants, 4 skipped** (tests d'intégration paquet réel
nécessitant l'arborescence de dev), **0 régression**.

Tests préexistants cassés depuis v0.8.5 (`test_route_compilation_batch.py`,
4 échecs sur mocks sans `**kw`) toujours cassés à l'identique — hors
scope v0.9.1.

## Périmètre des 12 échecs du batch 27/04/26 — récapitulatif

| Famille | Atomes | Cause | Statut |
|---|---|---|---|
| Annexes (Undefined `\annfile`) | 3 | `\seqInitAnnexes` jamais émis | ✅ Fix v0.9.1 |
| `wideparen.sty` introuvable | 3 | Mauvais mapping macro→paquet | ✅ Fix v0.9.1 |
| tabularray `measure` inconnu | 1 | Lib `varwidth` non chargée | ✅ Fix v0.9.1 |
| Image manquante | 1 | `data/images/` vidé volontairement | Hors scope (à régénérer) |
| `seqColItem` sans `\item` | 2 | Méthodes à compléter | Hors scope (contenu BDD) |
| Atome vide | 2 | Méthodes pas encore rédigées | Déjà signalé proprement par v0.8.4 |

**Couverture v0.9.1 : 7/12 échecs corrigés au niveau de l'appli.** Les
5 échecs restants sont hors scope appli (contenu BDD, images à
réimporter).

## À faire après déploiement

1. Re-importer le dossier images via Admin > Images pour faire revenir
   `pavage_tomettes.jpg` dans `data/images/`.
2. Compléter le contenu des méthodes N12/S13/M03-04 (les `seqColItem`
   sans `\item` qui plantent).
3. Relancer un batch méthodes — viser **154/156** (les 2 atomes vides
   restants étant cohérents avec le workflow « pas encore rédigé »).
4. Compiler les **exercices** (~800).

## Sur l'horizon (rappel)

- Bug latent `_paquets_externes_optionnels` qui ignore `envs_atome`
  (signalé v0.8.6, non bloquant en prod).
- Item de roadmap dormant : option dyslexie (xeLaTeX + OpenDyslexic + A3).
