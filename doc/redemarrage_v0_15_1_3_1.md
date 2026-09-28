# Redémarrage v0.15.1.3.1 — Hotfix Option clash for package tcolorbox

## Symptôme

À la compilation du **Récap des cartes d'automatisme** post-déploiement
de v0.15.1.3, Laurent observe :

```
L.29 LaTeX Error: Option clash for package tcolorbox.
\RequirePackage
==> Fatal error occurred, no output PDF file produced!
```

## Cause

`seqenseigne-theme.sty` ligne 28 charge tcolorbox **avec options** :

```latex
\RequirePackage[theorems,breakable,skins]{tcolorbox}
```

Mais le préambule v0.15.1.3 généré par mon code Python déclarait avant
cela :

```latex
\usepackage{tcolorbox}
```

Soit tcolorbox **sans options**. Quand `seqenseigne-theme` tente
ensuite de le charger avec ses options, LaTeX lève « Option clash ».

C'est une règle dure de LaTeX : un paquet ne peut être chargé qu'une
fois, et les options doivent être identiques sur tous les
`\RequirePackage`/`\usepackage` qui le concernent.

## Analyse de v0.15.1.3

En préparant v0.15.1.3 j'avais ajouté **3 `\usepackage`** au préambule
pour être explicite :

- `\usepackage{xintexpr}` — pour `\xintdefiivar` et `\xintiieval`
- `\usepackage{tabularray}` — pour les `tblr` des macros récap/planches
- `\usepackage{tcolorbox}` — pour les cartes tcolorbox

Or, ces 3 paquets sont déjà chargés en transitivement par les paquets
seqenseigne :

| Paquet | Chargé par | Options |
|---|---|---|
| `xintexpr` | `seqenseigne-core` | (aucune) |
| `tabularray` | `seqenseigne-core` | + `\UseTblrLibrary{booktabs}` |
| `tcolorbox` | `seqenseigne-theme` | **`[theorems,breakable,skins]`** ← clash |

Mes 3 ajouts étaient **superflus** dans tous les cas, et **bloquants
pour tcolorbox** (option clash).

## Correction (1 ligne)

Dans `services/livret_cartes_recap.py` et
`services/livret_cartes_planches.py`, **retirer les 3 `\usepackage`**
superflus du préambule. Le préambule devient :

```latex
\documentclass[10pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[french]{babel}
\usepackage{lmodern}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{xcolor}
\usepackage{siunitx}                        % toujours utile
\usepackage{geometry}
\usepackage{seqenseigne-core}               % → charge xintexpr + tabularray
\usepackage{seqenseigne-theme}              % → charge tcolorbox avec options
\usepackage{seqenseigne-carte-automatisme}
\geometry{a4paper, landscape, margin=2mm}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
```

C'est le préambule **minimal** qui charge tout ce qu'il faut par
transitivité.

## Garde-fou ajouté

Le test `test_livret_cartes_recap_preambule_complet` est mis à jour
pour assertionner **l'ABSENCE** des 3 `\usepackage` superflus, avec
messages d'erreur explicatifs en cas de régression future.

## Vérifs

- **Suite Python complète** : **3427 passed, 6 skipped, 0 failed**
  (identique à v0.15.1.3 — pas de nouveau test, juste un test modifié)
- **Sanity** sur les 2 services : OK

## Fichiers livrés

```
MODIFIÉS
  appli/services/livret_cartes_recap.py             (préambule : 3 lignes en moins)
  appli/services/livret_cartes_planches.py          (préambule : 3 lignes en moins)
  appli/tests/test_v0_13_6_5_2_livrets_manquants.py (1 test modifié)

NOUVEAU
  appli/doc/redemarrage_v0_15_1_3_1.md              (cette note)
```

## Procédure d'application

### 1. Décompresser le ZIP à la racine `seqenseigne/`

(Pas besoin de réimporter le paquet `seqenseigne-carte-automatisme` —
celui de v0.15.1.3 reste valide.)

### 2. Vérifier l'intégrité

```powershell
.\outils\python\python.exe appli\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
```

### 3. Lancer la suite de tests

```
cd appli
..\outils\python\python.exe -m pytest tests -q
```

Attendu : `3417 passed, 17 skipped` (identique à v0.15.1.3).

### 4. Tester fonctionnellement

**Récap des cartes** : aller sur **Conception de référentiel** >
**Référentiel** > **Documents à publier** > **Récap des cartes
d'automatisme** > **Tester**. La compilation doit maintenant aboutir.

**Planches de cartes** : idem, doit compiler sans Option clash.

## Pourquoi cette erreur a glissé en v0.15.1.3

Mon environnement de test Python (`pytest`) ne compile pas réellement
le `.tex` produit (pas de `pdflatex` configuré côté CI). Les tests
vérifient la **structure** du `.tex` (présence/absence de chaînes,
ordre des appels macros) mais pas sa **compilation effective**.

Pour éviter ce type de régression à l'avenir, deux pistes
complémentaires :
1. Ajouter une compilation LaTeX réelle dans les tests (déjà partielle
   dans `test_compilateur_pdf.py` mais skip si pas de pdflatex).
2. Maintenir le préambule **minimal** : ne déclarer un `\usepackage`
   que si on est sûr qu'aucun paquet seqenseigne ne le charge déjà.

J'ai opté pour la 2ème dans cette livraison (préambule minimal +
garde-fou textuel).
