# Redémarrage seqenseigne — v0.13.2

## Synthèse

**Refonte de la présentation des sections « Prérequis » et « Objectifs »
dans le livret de séquence.** Les deux blocs sont désormais émis via
deux nouvelles **commandes paquet** : `\seqRenduTableauPrerequis{...}` et
`\seqRenduTableauObjectifs{...}`, déclarées dans `seqenseigne-theme.dtx`.

> **Note sur le nommage** : les noms `\seqTableauPrerequis` et
> `\seqTableauObjectifs` (sans le préfixe `\seqRendu`) **existent déjà**
> dans `seqenseigne-data.dtx` pour le mécanisme historique CSV-driven
> (lecture via DTLforeach, paquet legacy). Pour éviter le conflit de
> définition, les nouvelles commandes BDD-driven prennent le préfixe
> `\seqRendu`. Le mot « Rendu » signale que ces commandes servent au
> rendu généré par le code Python (qui lit la BDD et émet le LaTeX),
> par opposition aux commandes legacy qui font tout en LaTeX depuis
> les CSV.

Pour Objectifs, c'est un changement profond :
- Le tableau est désormais **intégré dans la boîte tcolorbox** via la
  clé `tabularx*={}{X|X|X|X}` du paquet (plus de `\begin{tblr}...
  \end{tblr}` séparé).
- L'**en-tête à 2 niveaux est fixe côté paquet** : ligne 1 = cellule
  vide + « Niveau de maîtrise » couvrant les 3 colonnes critères
  (`\multirow` + `\multicolumn`) ; ligne 2 = « À consolider |
  Satisfaisant | Très bien ». Côté Python, on n'émet plus que les
  **lignes de données**.
- Les libellés des colonnes critères changent côté affichage :
  « Très bien » remplace « Très bon » (alignement avec le standard
  pédagogique).

Pour Prérequis, le contenu (subsection* + itemize) reste le même, mais
il est maintenant passé en argument à `\seqRenduTableauPrerequis{...}` au
lieu d'être encadré par `\seqTitreSection{Prérequis}`.

C'est la **première livraison de la série v0.13 qui modifie le paquet
LaTeX** en plus du code Python. Elle nécessite une coordination de
déploiement (cf. plus bas).

**Note de numérotation** : la roadmap initiale prévoyait v0.13.2 pour
l'activation des tables `referentiel_*`. Ce chantier de présentation a
été inséré entre v0.13.1 et le travail référentiel, qui devient v0.13.3
(et au-delà).

## Avant / après

### Avant (v0.13.1 et antérieur)

```latex
\seqTitreSection{Prérequis}

\subsection*{Séquence 01 — Représentations d'un nombre \hfill {\normalsize\itshape 5\ieme}}
\begin{itemize}[leftmargin=*,nosep]
  \item \textbf{01.} ...
\end{itemize}

\seqTitreSection{Objectifs}

\noindent\begin{tblr}{
  width=\linewidth,
  colspec={X[2.4,l] X[1.4,l] X[1.4,l] X[1.4,l]},
  rowhead=1, hlines, vlines,
  ...
}
  \seqStyleObjectifsHeader{Objectif} & \seqStyleObjectifsHeader{À consolider} & ... \\
  \textbf{01.} Connaître ... & critère F & critère A & critère E \\
  ...
\end{tblr}
```

Rendu : deux titres de section style classique, suivis de leur contenu,
sans encadrement visuel particulier. Le tableau d'objectifs utilisait
`tabularray` avec en-têtes émis depuis Python.

### Après (v0.13.2)

```latex
\seqRenduTableauPrerequis{%
\subsection*{Séquence 01 — Représentations d'un nombre \hfill {\normalsize\itshape 5\ieme}}
\begin{itemize}[leftmargin=*,nosep]
  \item \textbf{01.} ...
\end{itemize}

}

\seqRenduTableauObjectifs{%
  \textbf{01.} Connaître ... & critère F & critère A & critère E \\\hline
  \textbf{02.} Reconnaître ... & ... & ... & ... \\\hline
  \textbf{03.} Comparer ... & ... & ... & ...
}
```

Rendu : deux boîtes encadrées avec un titre dans un onglet en haut à
gauche, fond pâle dans la couleur du thème, cadre dans la couleur vive
du thème. Pour Objectifs, l'en-tête à 2 niveaux (« Niveau de maîtrise »
+ critères) est fixe côté paquet.

## Modifications du paquet LaTeX

Dans `seqenseigne-theme.dtx`, deux nouvelles commandes ajoutées juste
après `boitePaleNoBreakHeightNoTitle` :

### `\seqRenduTableauPrerequis{contenu}`

```latex
\newtcolorbox{seq@boite@prerequis}{
    title=Prérequis,
    colback=\seq@couleurii@pale,
    colframe=\seq@couleuri@vif,
    colbacktitle=\seq@couleuri@vif,
    breakable,
    fonttitle=\bfseries,
    enhanced,
    attach boxed title to top left={yshift=-5pt,xshift=20pt},
    pad after break=20pt
}
\newcommand{\seqRenduTableauPrerequis}[1]{%
    \begin{seq@boite@prerequis}%
        #1%
    \end{seq@boite@prerequis}%
}
```

L'environnement interne `seq@boite@prerequis` est privé du paquet
(préfixe `seq@`), seule la commande publique `\seqRenduTableauPrerequis`
est exposée à l'extérieur.

### `\seqRenduTableauObjectifs{contenu}`

```latex
\newtcolorbox{seq@boite@objectifs}{
    title=Objectifs,
    colback=\seq@couleurii@pale,
    colframe=\seq@couleuri@vif,
    colbacktitle=\seq@couleuri@vif,
    breakable,
    fonttitle=\bfseries,
    enhanced,
    attach boxed title to top left={yshift=-5pt,xshift=20pt},
    pad after break=20pt,
    tabularx*={}{X|X|X|X}
}
\newcommand{\seqRenduTableauObjectifs}[1]{%
    \begingroup
    \newcolumntype{C}{>{\raggedright\arraybackslash}X}%
    \begin{seq@boite@objectifs}
        \multirow{2}{\hsize}{} & \multicolumn{3}{|>{\hsize=3\hsize}C|}{Niveau de maîtrise} \\\cline{2-4}
        & \`A consolider & Satisfaisant & Très bien \\\hline
        #1
    \end{seq@boite@objectifs}%
    \endgroup
}
```

Points techniques :

- **`tabularx*={}{X|X|X|X}` (clé tcolorbox)** : crée un environnement
  tabularx automatiquement à l'intérieur de la boîte. Pas besoin de
  `\begin{tabularx}...\end{tabularx}` à l'intérieur du contenu — le
  paquet tcolorbox gère lui-même l'ouverture et la fermeture.
- **`\newcolumntype{C}` local** : nécessaire pour que le `\multicolumn`
  de la première ligne d'en-tête puisse spécifier `\hsize=3\hsize` et
  occuper proprement les 3 colonnes critères. Défini dans un
  `\begingroup`/`\endgroup` pour rester local à la commande (pas de
  pollution du namespace global).
- **En-tête à 2 niveaux fixe** :
  - Ligne 1 : `\multirow{2}{\hsize}{}` réserve la première colonne sur
    2 lignes en cellule vide ; `\multicolumn{3}{|>{\hsize=3\hsize}C|}
    {Niveau de maîtrise}` crée le bandeau couvrant les 3 colonnes
    critères. `\cline{2-4}` pose un trait sous « Niveau de maîtrise »
    (mais pas sous la cellule vide).
  - Ligne 2 : cellule vide (déjà couverte par multirow) puis « À
    consolider | Satisfaisant | Très bien ».

### Couleurs héritées du thème

Comme dans la version intermédiaire, les couleurs (`\seq@couleurii@pale`
fond, `\seq@couleuri@vif` cadre+titre) sont définies dynamiquement par
`\seqSetColorsTheme{<code_couleur>}` appelée en début de livret. Le
rendu suit donc automatiquement la charte du thème de la séquence.

### Pourquoi des commandes plutôt que des environnements ?

Avec une commande à argument (`\seqRenduTableauObjectifs{lignes}`), on peut
intégrer la clé `tabularx*={}{X|X|X|X}` dans la définition même du
tcolorbox. tcolorbox crée alors automatiquement le tabularx et utilise
le contenu de la commande comme contenu du tableau. C'est cette
mécanique qui permet d'avoir un tableau **intégré** dans la boîte plutôt
qu'**imbriqué** (ce qui aurait été le cas avec `\begin{seqBoite}...
\begin{tblr}...\end{tblr}...\end{seqBoite}`).

L'avantage : le rendu visuel est plus propre (pas de marges dupliquées,
gestion de la largeur native). C'est pour cette raison que le code Python
n'émet que les lignes de données et pas le `\begin{tblr}/\end{tblr}`.

## Détail des modifications

### Mise à jour critique de `fragment_squelette_livret`

Le préambule du livret est construit par fermeture transitive depuis
les macros utilisées dans le source LaTeX généré. Cette détection se
fait via `extraire_utilisations(texte_global)`, qui parcourt tout le
source — corps des atomes ET squelette du livret lui-même.

Pour les macros émises par le **squelette** du livret (pas par les
atomes individuels), le service maintient une liste explicite
`fragment_squelette_livret` dans `services/livret_sequence.py` qui
liste les macros à inclure obligatoirement dans le préambule. Cette
liste **doit être tenue à jour** à chaque ajout de macro paquet
utilisée dans le squelette.

v0.13.2 ajoute deux nouvelles macros :

```python
fragment_squelette_livret = r"""
\seqCreeCompteurs
\seqSetCodeNiveau{X}\seqSetCodeSequence{X}\seqSetColorsTheme{X}
...
\seqStyleObjectifsHeader{X}
\seqRenduTableauPrerequis{X}\seqRenduTableauObjectifs{X}    ← AJOUT v0.13.2
\begin{seqSerieExos}{0}\end{seqSerieExos}
\begin{boiteTitreGen}{X}\end{boiteTitreGen}
"""
```

Sans cette ligne, la fermeture transitive **n'inclurait pas** les
définitions de `\seqRenduTableauPrerequis` ni `\seqRenduTableauObjectifs`
dans le préambule, et la compilation planterait avec :
```
! Undefined control sequence.
l.628 \seqRenduTableauObjectifs
```

Cette régression a été détectée et corrigée en cours de livraison.
À l'avenir, **toute nouvelle macro paquet utilisée par le squelette
du livret doit être ajoutée à `fragment_squelette_livret`**.

### Chargement explicite de `tabularx`

La clé tcolorbox `tabularx*={}{X|X|X|X}` utilisée dans la définition
de `\seqRenduTableauObjectifs` (paquet `seqenseigne-theme.dtx`) déclenche
en interne un `\tabularx{...}` à l'intérieur de la boîte. Ce mécanisme
exige que le paquet LaTeX `tabularx` soit chargé.

Or, **`\tabularx` n'apparaît jamais dans le source LaTeX généré par
Python** : c'est tcolorbox qui le crée à l'expansion de la clé.
Conséquence : `extraire_utilisations` ne peut pas détecter cette
dépendance, et la détection automatique des paquets ne charge pas
`tabularx`.

Solution : ajout explicite de `tabularx` à la liste des paquets
supplémentaires passée à `construire_preambule`. Pattern identique à
ce qui était déjà fait pour `datetime` :

```python
paquets_manquants_etendus = list(dict.fromkeys(
    list(paquets_manquants) + ["datetime", "tabularx"]
))
```

Sans ce chargement, la compilation plante avec :
```
! Undefined control sequence.
\kvtcb@before@upper ...b@hack@currenvir \tabularx
                                                  {\linewidth }{X|X|X|X}
```

Un test pytest dédié (`test_paquet_tabularx_charge_dans_le_preambule`)
verrouille cette régression.

### Modifications côté Python

`services/livret_sequence.py`, deux fonctions modifiées :

### `_generer_tableau_prerequis`

Émet maintenant :

```latex
\seqRenduTableauPrerequis{%
  <subsection* + itemize de la 1ère séquence prérequise>
  <subsection* + itemize de la 2e séquence prérequise>
  ...
}
```

au lieu de :

```latex
\seqTitreSection{Prérequis}
<contenu>
```

### `_generer_tableau_objectifs`

Émet maintenant :

```latex
\seqRenduTableauObjectifs{%
  Objectif1 & critère_F & critère_A & critère_E \\\hline
  Objectif2 & critère_F & critère_A & critère_E \\\hline
  ...
  ObjectifN & critère_F & critère_A & critère_E
}
```

au lieu de :

```latex
\seqTitreSection{Objectifs}
\noindent\begin{tblr}{...}
  \seqStyleObjectifsHeader{Objectif} & \seqStyleObjectifsHeader{À consolider} & ... \\
  ligne 1 \\
  ligne 2 \\
  ...
\end{tblr}
```

Différences notables côté Python :

- Plus de `\noindent` : la commande paquet gère sa propre mise en page
- Plus de `\begin{tblr}{...}` : le tableau est intégré dans la commande
  via la clé tcolorbox `tabularx*`
- Plus d'en-tête « Objectif | À consolider | Satisfaisant | Très bon »
  émis depuis Python : l'en-tête à 2 niveaux est fixe côté paquet
- **Dernière ligne sans `\\\hline` final** : sinon trait redondant avec
  la frame de la boîte tcolorbox (visuellement laid)

## Tests

**Total : 1983 tests** (vs 1978 baseline v0.13.1) → **+5 tests v0.13.2**.

### Tests existants adaptés (5 assertions modifiées)

Dans `tests/test_livret_sequence.py`, classe `TestTableauObjectifs` et
`TestTableauPrerequis` : remplacement des matches sur
`\seqTitreSection{...}` par des matches sur `\seqRenduTableauPrerequis{` et
`\seqRenduTableauObjectifs{`.

### Nouveaux tests `TestV0132CommandesPaquet` (5 tests)

1. **`test_seqRenduTableauPrerequis_contient_subsection_et_itemize`** : le
   contenu (subsection* + itemize) est bien dans le bloc commande.
2. **`test_seqRenduTableauObjectifs_emet_lignes_de_donnees`** : les lignes
   de données sont émises ; les en-têtes (« Niveau de maîtrise », « À
   consolider ») n'apparaissent **PAS** dans la sortie Python (ils
   sont fixes côté paquet).
3. **`test_derniere_ligne_objectifs_sans_hline_final`** : la dernière
   ligne ne porte pas de `\\\hline` final (évite le trait redondant
   avec la frame).
4. **`test_prerequis_avant_objectifs_dans_le_livret`** : ordre relatif
   préservé.
5. **`test_aucune_trace_des_anciens_marqueurs`** : régression sur les
   anciens patterns (pas de `\seqTitreSection{Prérequis|Objectifs}`,
   pas de `\begin{seqBoitePrerequis|seqBoiteObjectifs}`).

## Fichiers livrés

```
paquet/seqenseigne-theme.dtx              (~70 lignes ajoutées :
                                              \seqRenduTableauPrerequis +
                                              \seqRenduTableauObjectifs avec doc
                                              \begin{macro})
paquet/seqenseigne-theme.sty              (~40 lignes ajoutées : version
                                              générée des deux commandes)
services/livret_sequence.py               (~30 lignes nettes :
                                              suppression des begin/end
                                              tblr + suppression
                                              en-têtes manuels +
                                              format \seqRenduTableauObjectifs)
tests/test_livret_sequence.py             (~120 lignes : adaptation de 5
                                              tests + nouvelle classe
                                              TestV0132CommandesPaquet)
doc/redemarrage_v0_13_2.md                (NOUVEAU)
```

Aucune migration BDD nécessaire.

## Procédure de déploiement

C'est une livraison à **deux composants** : Python et paquet LaTeX. Tous
les deux doivent être à jour pour que la compilation de livret
fonctionne.

### Étape 1 — Mise à jour du paquet LaTeX

Deux options :

**Option simple** : copier `appli/paquet/seqenseigne-theme.sty` directement
dans ton paquet déployé sur MiKTeX Portable.

**Option propre** : intégrer `appli/paquet/seqenseigne-theme.dtx` dans
ton dépôt forge `seqenseigne`, recompiler via `pdflatex seqenseigne.ins`
pour régénérer le `.sty`, déployer le résultat.

### Étape 2 — Mise à jour de l'application Python

Décompresser le ZIP par-dessus la v0.13.1, relancer l'application.

⚠️ **Ordre important** : si tu fais l'étape 2 avant l'étape 1, les
compilations de livret de séquence vont échouer avec :
```
LaTeX Error: Undefined control sequence \seqRenduTableauObjectifs.
```

L'inverse (étape 1 sans étape 2) ne pose aucun problème : les nouvelles
commandes sont juste inutilisées.

## Validation côté Laurent

### Test LaTeX standalone (paquet seul)

Avant même de toucher Python, tu peux tester le paquet avec un fichier
de test minimal :

```latex
\documentclass{article}
\usepackage{seqenseigne}
\begin{document}
\makeatletter \seq@setColors{nombres} \makeatother

\seqRenduTableauPrerequis{%
\subsection*{Séquence 01 — Test de prérequis \hfill {\normalsize\itshape 5\ieme}}
\begin{itemize}
  \item \textbf{01.} Ligne de prérequis 1
  \item \textbf{02.} Ligne de prérequis 2
\end{itemize}
}

\seqRenduTableauObjectifs{%
01. Premier objectif & À consolider 1 & Satisfaisant 1 & Très bien 1 \\\hline
02. Deuxième objectif & À consolider 2 & Satisfaisant 2 & Très bien 2 \\\hline
03. Troisième objectif & À consolider 3 & Satisfaisant 3 & Très bien 3
}

\end{document}
```

Doit compiler et produire deux boîtes encadrées en bleu (couleur du thème
« nombres »).

### Test bout-en-bout

1. Compiler le livret d'une séquence avec prérequis ET critères F/A/E
   renseignés (par exemple N11/S03)
2. Vérifier dans le PDF :
   - Boîte « Prérequis » avec onglet de titre coloré au thème
   - Boîte « Objectifs » juste en dessous, avec :
     - L'en-tête à 2 niveaux : ligne « | Niveau de maîtrise »
       (fusionnée sur 3 colonnes), puis « | À consolider | Satisfaisant
       | Très bien »
     - Les lignes par objectif, séparées par `\hline`
   - Couleurs cohérentes avec le thème de la séquence
3. Régression : sur une séquence **sans prérequis** (par exemple S01
   d'un niveau), pas de boîte Prérequis. Sur une séquence **sans
   critères F/A/E**, pas de boîte Objectifs.

## Limitations connues

### Caractères spéciaux dans le contenu

Le contenu passé en argument à `\seqRenduTableauPrerequis{...}` ou
`\seqRenduTableauObjectifs{...}` peut être problématique si :

- Il contient des `}` non protégées (cassent l'argument)
- Il contient des paragraphes vides (`\par`) — tcolorbox/pgfkeys
  n'aiment pas. À surveiller pour les libellés très longs avec sauts
  de ligne intentionnels (cas non observé jusqu'ici).

L'échappement actuel via `_echapper_simple` (qui échappe `&`, `#`,
`%`) reste suffisant pour les cas standard. Si tu rencontres un cas
problématique, signale-le pour qu'on adapte l'échappement.

### `LIBELLES_NIVEAUX_LATEX` reste hardcodé

Pas concerné par cette livraison. C'est dans le module
`livret_plans_de_travail.py` et reste géré séparément (mise en forme
LaTeX spécifique aux pages de titre des plans de travail).

## Prochaine étape

**v0.13.3** (anciennement v0.13.2) — Activation des tables
`referentiel_*` (versioning millésimé). Sujet structurel à scoper
séparément, pas mal d'inconnues sur le modèle de données.

À ton signal pour la suite.
