# Rapport de dette de cohérence — macros non-couvertes

**Total macros non-couvertes** : 5

- Définies dans un atome (dette à remonter) : **2**
- Sans définition trouvée : **3**

## Catégorie 1 — Macros définies dans un atome (à remonter)

Ces macros ont été définies directement dans un livret ou dans les `variables` d'un exercice, puis réutilisées depuis d'autres atomes de la même séquence. Deux chemins de résolution :

1. **Remontée dans le paquet** si la macro est d'intérêt général (cas type : `\boiteJauneModere`, `\seqTitreTabV`).
2. **Fichier de variables de séquence partagé** si la macro est spécifique à une séquence (cas type : figures tkz construites par un exercice et réutilisées par les suivants).

### `\tkzFExoVII`

**23 appel(s)** — **21 définition(s) trouvée(s)**

**Définitions :**

| Table | Fichier | Champ | Type |
|---|---|---|---|
| exercices | `N12S11A01.tex` | variables | newcommand |
| exercices | `N12S11A02.tex` | variables | newcommand |
| exercices | `N12S11A03.tex` | variables | newcommand |
| exercices | `N12S11A04.tex` | variables | newcommand |
| exercices | `N12S11A05.tex` | variables | newcommand |
| exercices | `N12S11A06.tex` | variables | newcommand |
| exercices | `N12S11A07.tex` | variables | newcommand |
| exercices | `N12S11E01.tex` | variables | newcommand |
| exercices | `N12S11E02.tex` | variables | newcommand |
| exercices | `N12S11E03.tex` | variables | newcommand |
| exercices | `N12S11E04.tex` | variables | newcommand |
| exercices | `N12S11E05.tex` | variables | newcommand |
| exercices | `N12S11E06.tex` | variables | newcommand |
| exercices | `N12S11F01.tex` | variables | newcommand |
| exercices | `N12S11F02.tex` | variables | newcommand |
| exercices | `N12S11F03.tex` | variables | newcommand |
| exercices | `N12S11F04.tex` | variables | newcommand |
| exercices | `N12S11F05.tex` | variables | newcommand |
| exercices | `N12S11F06.tex` | variables | newcommand |
| exercices | `N12S11F07.tex` | variables | newcommand |
| exercices | `N12S11F08.tex` | variables | newcommand |

**Appels :**

| Table | Fichier | Champ |
|---|---|---|
| exercices | `N11S11F08.tex` | corrige |
| exercices | `N11S11F08.tex` | enonce |
| exercices | `N12S11A01.tex` | variables |
| exercices | `N12S11A02.tex` | variables |
| exercices | `N12S11A03.tex` | variables |
| exercices | `N12S11A04.tex` | variables |
| exercices | `N12S11A05.tex` | variables |
| exercices | `N12S11A06.tex` | variables |
| exercices | `N12S11A07.tex` | variables |
| exercices | `N12S11E01.tex` | variables |
| exercices | `N12S11E02.tex` | variables |
| exercices | `N12S11E03.tex` | variables |
| exercices | `N12S11E04.tex` | variables |
| exercices | `N12S11E05.tex` | variables |
| exercices | `N12S11E06.tex` | variables |
| … | … et 8 autres | … |

### `\tkzFExoI`

**22 appel(s)** — **21 définition(s) trouvée(s)**

**Définitions :**

| Table | Fichier | Champ | Type |
|---|---|---|---|
| exercices | `N12S11A01.tex` | variables | newcommand |
| exercices | `N12S11A02.tex` | variables | newcommand |
| exercices | `N12S11A03.tex` | variables | newcommand |
| exercices | `N12S11A04.tex` | variables | newcommand |
| exercices | `N12S11A05.tex` | variables | newcommand |
| exercices | `N12S11A06.tex` | variables | newcommand |
| exercices | `N12S11A07.tex` | variables | newcommand |
| exercices | `N12S11E01.tex` | variables | newcommand |
| exercices | `N12S11E02.tex` | variables | newcommand |
| exercices | `N12S11E03.tex` | variables | newcommand |
| exercices | `N12S11E04.tex` | variables | newcommand |
| exercices | `N12S11E05.tex` | variables | newcommand |
| exercices | `N12S11E06.tex` | variables | newcommand |
| exercices | `N12S11F01.tex` | variables | newcommand |
| exercices | `N12S11F02.tex` | variables | newcommand |
| exercices | `N12S11F03.tex` | variables | newcommand |
| exercices | `N12S11F04.tex` | variables | newcommand |
| exercices | `N12S11F05.tex` | variables | newcommand |
| exercices | `N12S11F06.tex` | variables | newcommand |
| exercices | `N12S11F07.tex` | variables | newcommand |
| exercices | `N12S11F08.tex` | variables | newcommand |

**Appels :**

| Table | Fichier | Champ |
|---|---|---|
| exercices | `N11S11F03.tex` | enonce |
| exercices | `N12S11A01.tex` | variables |
| exercices | `N12S11A02.tex` | variables |
| exercices | `N12S11A03.tex` | variables |
| exercices | `N12S11A04.tex` | variables |
| exercices | `N12S11A05.tex` | variables |
| exercices | `N12S11A06.tex` | variables |
| exercices | `N12S11A07.tex` | variables |
| exercices | `N12S11E01.tex` | variables |
| exercices | `N12S11E02.tex` | variables |
| exercices | `N12S11E03.tex` | variables |
| exercices | `N12S11E04.tex` | variables |
| exercices | `N12S11E05.tex` | variables |
| exercices | `N12S11E06.tex` | variables |
| exercices | `N12S11F01.tex` | variables |
| … | … et 7 autres | … |

## Catégorie 2 — Macros sans définition trouvée

Aucune définition détectée dans les atomes ni dans le paquet. Probables bugs dormants (les atomes concernés ne doivent pas compiler en isolation, et peut-être pas en livret non plus si la macro n'est définie nulle part).

### `\touche`

**2 appel(s)**

**Appels :**

| Table | Fichier | Champ |
|---|---|---|
| exercices | `N10S03E03.tex` | corrige |
| exercices | `N10S03E03.tex` | enonce |

### `\myDef`

**1 appel(s)**

**Appels :**

| Table | Fichier | Champ |
|---|---|---|
| exercices | `N10S12AE02.tex` | corrige |

### `\rb`

**1 appel(s)**

**Appels :**

| Table | Fichier | Champ |
|---|---|---|
| exercices | `N10S10E05.tex` | enonce |
