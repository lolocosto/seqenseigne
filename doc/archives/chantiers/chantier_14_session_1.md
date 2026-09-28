# Chantier 14 — Rendu LaTeX d'un atome isolé

## Session 1 — Schéma + peuplement + vérification de couverture

### Objectif de la session

Mettre en place la brique de base du rendu atomique : extraire les définitions du
paquet `seqenseigne` dans la BDD avec leur statut de rendu (réutilisable /
réécrite / ignorée), et vérifier que tous les atomes (1 124) utilisent bien des
macros dont on sait rendre compte.

### Ce qui est livré

#### 1. Service `services/paquet_parseur.py`

Parseur custom des fichiers `.sty` du paquet, sans dépendance externe.

Reconnaît les 7 primitives utilisées par le paquet :
`\newcommand`, `\renewcommand`, `\providecommand`, `\DeclareRobustCommand`,
`\newenvironment`, `\renewenvironment`, `\NewEnviron`, `\newtcolorbox`,
`\newcounter`, `\newcolumntype`, `\newif`, et la forme particulière
`\define@cmdkey[prefix]{famille}{cle}[default]{body}`.

Extrait aussi les `\RequirePackage` avec options.

**Pourquoi un parseur custom :** TexSoup plante systématiquement sur
`\begin{...}` dans les corps de `\newenvironment` (cherche un `\end` au
niveau racine qui n'existe pas). pylatexenc dépasse 30 s sur
`seqenseigne-core.sty` (complexité non-linéaire). plasTeX n'a pas été testé.

Parseur : 400 lignes de Python, 0 dépendance, robuste sur les 4 `.sty`
(338 définitions extraites sans erreur).

#### 2. Module `services/paquet_regles_atome.py`

Définit les règles de rendu pour chaque macro. Trois statuts :

- **`reutilise`** : la définition du paquet est réemployée telle quelle.
- **`reecrit`** : une définition alternative est fournie. Concerne notamment
  `\seqCorrige` qui écrit dans `Corriges/c<s>e<n>.tex` (infaisable pour un
  atome isolé) et qu'on remplace par un affichage inline dans une boîte
  colorée.
- **`ignore`** : rien n'est émis. Concerne les macros CSV-dépendantes
  (`\seqObjectifGetNom`, etc.), les macros de livret, les macros de
  plan/bilan/suivi/PPRE.

77 règles explicites, défaut = `reutilise`.

#### 3. Table SQLite `paquet_definitions` (+ `paquet_requirepackage`)

Créée par le DDL idempotent du script de peuplement. Une ligne par
définition extraite du paquet, avec son statut de rendu atomique et son
contenu de remplacement éventuel.

Index sur `fichier_source`, `type_latex`, `statut_rendu_atome`.

Contrainte CHECK sur `statut_rendu_atome IN ('reutilise','reecrit','ignore')`.

#### 4. Script `scripts/peuplement_14_paquet_vers_base.py`

CLI qui :

1. Crée les tables si absentes (DDL idempotent).
2. Vide les tables (rescan complet).
3. Parse les 4 fichiers `.sty` et insère les définitions avec leur statut.
4. Détecte les règles orphelines (nom de règle sans définition correspondante).

Usage :

    cd appli
    ..\outils\python\python.exe scripts\peuplement_14_paquet_vers_base.py \
        --paquet ../reference/seqenseigne/paquet

#### 5. Script `scripts/peuplement_14_verif_couverture.py`

CLI qui analyse les 1 124 atomes (notions, items_texte, méthodes, exercices)
et vérifie que tous les noms utilisés sont couverts.

Classe chaque nom en 3 catégories :

- **couvert paquet** : présent dans `paquet_definitions`
- **couvert externe** : présent dans `MACROS_PAQUETS_EXTERNES`
  (tkz-euclide, scratch3, amsmath, etc.)
- **non couvert** : à investiguer

Exclut de l'analyse les macros définies localement par l'atome (via
`\newcommand`, `\def`, `\foreach \x/\y/\z in`, `\tkzGetLength{nom}`).

### Résultats du peuplement

```
seqenseigne-core.sty    133 defs, 30 paquets      → 92 reutilise, 8 reecrit, 33 ignore
seqenseigne-theme.sty   108 defs, 15 paquets      → 108 reutilise
seqenseigne-data.sty     81 defs,  4 paquets      → 47 reutilise, 34 ignore
seqenseigne-legacy.sty   18 defs,  0 paquets      → 18 reutilise

TOTAL                   340 definitions
Statut global            265 reutilise, 8 reecrit, 67 ignore
Doublons écrasés          2  (\ifdocstd défini 2x dans le paquet, délibéré)
Règles orphelines         0
```

Remontées dans le paquet pendant cette session :

- `\boiteJauneModere` ajoutée dans `seqenseigne-theme.sty` ligne 181
  (à côté de `\seqBoiteJaune` dont elle est quasi-identique).
- `\seqTitreTabV` ajoutée dans `seqenseigne-theme.sty` ligne 539
  (titre vertical de colonne, section tabularray).

### Résultats de la vérification de couverture

Sur les 1 124 atomes :

```
228 noms distincts utilisés
 19 couverts par paquet_definitions
204 couverts par paquets TeX externes connus
  5 NON couverts
```

#### Non couverts résiduels (5)

Après remontée de `\boiteJauneModere` et `\seqTitreTabV`, il reste :

**Catégorie 1 — dette de cohérence (2 macros, 45 appels)** : définies dans
les `variables` d'exercices, réutilisées par d'autres exercices.

| Macro | Appels | Définie dans |
|---|---|---|
| `\tkzFExoVII` | 23 | les 21 exercices de N12-S11 (copié-collé dans chaque `variables`) |
| `\tkzFExoI` | 22 | idem |

Deux exercices de N11 (`N11S11F08`, `N11S11F03`) appellent ces macros
**sans les redéfinir** — probablement cassés (à compiler pour vérifier).

**Catégorie 2 — bugs dormants (3 macros, 4 appels)** : utilisées mais
jamais définies nulle part.

| Macro | Appels | Fichiers |
|---|---|---|
| `\touche` | 2 | `N10S03E03.tex` (touches de calculatrice : `\touche{2} \touche{+}...`) |
| `\myDef` | 1 | `N10S12AE02.tex` |
| `\rb` | 1 | `N10S10E05.tex` |

Ces 3 atomes ne compilent probablement pas en livret non plus.

Voir `doc/chantier_14_dette_coherence.md` pour le détail des 43 fichiers
impactés.

### Conclusion

La vérification de couverture a permis de :

1. Valider que le parseur custom couvre correctement les 228 noms LaTeX
   utilisés par les 1 124 atomes (après filtrage des macros locales).
2. Identifier et corriger 2 macros qui auraient dû être dans le paquet
   (`\boiteJauneModere`, `\seqTitreTabV`).
3. Mettre en évidence une dette de cohérence structurelle (macros
   répliquées dans tous les `variables` d'une séquence).
4. Détecter 3 bugs dormants (macros jamais définies).

### Tests

`tests/test_paquet_parseur.py` — 25 tests :

- Commentaires LaTeX (%, \\%)
- Extraction d'arguments balancés (imbrication, échappement)
- Chaque primitive reconnue (newcommand, newenvironment, newtcolorbox,
  newcounter, newif, define@cmdkey)
- Le cas critique `\newenvironment{monenv}{\begin{center}}{\end{center}}`
- Analyse des dépendances (filtrage des primitives LaTeX)
- Extraction des `\RequirePackage`
- Intégration contre le vrai paquet (si disponible)

`tests/test_paquet_peuplement.py` — 15 tests :

- DDL idempotent et contrainte CHECK
- Insertion avec application des règles
- Doublons écrasés
- Pipeline complet sur mini-paquet factice
- Idempotence du peuplement
- Détection de règles orphelines

`tests/test_paquet_verification.py` — 17 tests :

- Filtrage du `\\` de saut de ligne (bug historique corrigé)
- Détection des macros locales : `\newcommand`, `\def`, `\foreach`,
  `\tkzGetLength`
- Classification des 3 catégories de couverture
- Cohérence du dictionnaire des paquets externes

**Total** : 57 nouveaux tests, tous verts.

### Fichiers créés

```
services/paquet_parseur.py                      (module pur, 0 dépendance)
services/paquet_regles_atome.py                 (77 règles explicites)
scripts/peuplement_14_paquet_vers_base.py
scripts/peuplement_14_verif_couverture.py
scripts/peuplement_14_rapport_dette.py          (rapport Markdown de dette)
tests/test_paquet_parseur.py                    (25 tests)
tests/test_paquet_peuplement.py                 (15 tests)
tests/test_paquet_verification.py               (17 tests)
doc/chantier_14_session_1.md                    (ce fichier)
doc/chantier_14_dette_coherence.md              (rapport détaillé)
```

### Fichiers modifiés (paquet)

```
reference/seqenseigne/paquet/seqenseigne-theme.sty :
  + \boiteJauneModere  (ligne ~181)
  + \seqTitreTabV      (ligne ~539)
```

Aucun autre fichier existant modifié.

### Prochaines sessions

- **Session 2** : `services/latex_rendu_atome.py` — génération du `.tex`
  d'un atome isolé à partir de la BDD (préambule minimal + macros
  `reecrit` + corps de l'atome). Résolution du problème des macros
  partagées intra-séquence.

- **Session 3** : `services/compilateur_pdf.py` — compilation avec
  `pdflatex` dans `/tmp` et cache PDF par hash(tex). Route Flask
  `POST /api/atomes/<id>/rendu-pdf`.

- **Session 4** : UI bouton « Voir le rendu » dans ateliers.
