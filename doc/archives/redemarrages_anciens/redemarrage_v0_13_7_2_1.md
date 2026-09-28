# Redémarrage v0.13.7.2.1 — Tri pédagogique de la barre d'outils

## Périmètre

Patch correctif de v0.13.7.2 suite à ta remarque pertinente :

> « Un certain nombre d'environnements et de commandes du paquet sont
> sans objet dans l'éditeur parce qu'ils englobent le texte saisi pour
> produire les documents. »

Cette livraison applique le **principe de tri** suivant à toute l'UI
de l'éditeur LaTeX :

> **Distinction structurel vs. contenu** : ne sont exposées dans
> l'éditeur que les macros que l'enseignant **insère DANS** son
> contenu. Les macros que l'app **ajoute AUTOUR du** contenu
> (structurelles) sont par défaut cachées, et n'apparaissent dans
> l'onglet « Tout le paquet » que via une case à cocher explicite
> « Afficher les macros structurelles ».

## Inventaire des macros structurelles

Source : analyse de `services/latex_rendu_atome.py`, `services/render_carte.py`,
et `services/preambule_atome.py` (constantes `WRAPPER_COMMUN` et
`WRAPPER_PAR_TYPE`).

### Setup commun à tous les atomes

```
\seqSetColorsTheme    \seqCreeCompteurs
\seqSetCodeNiveau     \seqRAZCompteurs
\seqSetCodeSequence
```

### Wrapper exercice

L'app émet automatiquement :

```
\begin{seqSerieExos}{N}
  \begin{seqExercice}[nom=titre, obj=..., remediation=oui]
    <énoncé saisi par l'enseignant>
    \seqCadreReponse{N}        ← piloté par la case à cocher de l'atelier
    \seqCorrige{<corrigé saisi>}
    \seqRemediation{<remed_enonce>}{<remed_corrige>}  ← champs dédiés
  \end{seqExercice}
\end{seqSerieExos}
\seqAfficheAnnexes
\seqAfficheCorriges
\seqAfficheRemediations
\seqAfficheCorrigesRemediation
```

Avec en setup amont : `\seqInitCorriges`, `\seqInitAnnexes`,
`\seqInitRemediation`, `\renewcommand{\seqCorrigesExos}{oui}`.

→ **Toutes ces macros sont structurelles** et exclues par défaut.

### Wrapper notion / méthode

```
\seqInitAnnexes
\begin{seqNotion}{<titre>}{<corps>}
  <sections "exemples"/"remarques">
\end{seqNotion}
\seqAfficheAnnexes
```

Idem pour `seqMethode`.

→ `seqNotion`, `seqMethode` sont **structurelles**. En revanche,
`seqColItem` (utilisé pour les sections) reste **non-structurelle** car
elle est aussi librement utilisable par l'enseignant dans son contenu
pour faire des listes multi-colonnes.

### Wrapper fiche de résumé

```
\seqTitreSection{<titre>}
\begin{seqBoiteContenuFlashcard}[titre=<sec1>]
  <items de la section 1>
\end{seqBoiteContenuFlashcard}
...
\begin{seqBoiteFillContenuFlashcard}\end{seqBoiteFillContenuFlashcard}
```

→ `\seqTitreSection`, `seqBoiteContenuFlashcard`, `seqBoiteFillContenuFlashcard`
sont **structurelles**.

### Wrapper carte d'automatisme

```
\seqCarteAuto[niveau=..., sequence=..., num=..., typepedagolibelle=...]
  {<recto>}
  {<verso>}
```

→ `\seqCarteAuto` est **structurelle**.

### Wrapper évaluation

```
\seqInitCorrigesEval
\seqTitreEval{...}
\begin{seqEvalBareme} ... \end{seqEvalBareme}
\begin{seqEvalObjectifs} ... \end{seqEvalObjectifs}
\begin{seqEvalExercice} ... \seqEvalCorrigeExo{...} \end{seqEvalExercice}
\seqEvalAfficheCorriges
```

→ Toutes structurelles.

### Macros de livret (sans objet dans un atome)

```
\seqTitreLivret \seqTitreLivretAuto
```

## Modifications côté backend

### `services/paquet_expose.py`

Ajout d'une constante exportée `MACROS_STRUCTURELLES` (30 entrées) et
d'un paramètre `inclure_structurelles=False` à `lister_definitions`.
Par défaut, le filtre est actif (les macros structurelles sont exclues).

La docstring du module documente le **lien et la différence** avec
`services/preambule_atome.WRAPPER_*` qui sert une finalité différente
(fermeture transitive des dépendances vs. filtrage UI).

### `routes/paquet.py`

Ajout du paramètre query `?inclure_structurelles=1` (acceptée aussi
sous `true`, `oui`, `yes`). Tout autre valeur ou absence → filtre actif.

### Aucune mémoire utilisateur ou autre module touché

C'est une livraison purement ciblée sur l'éditeur LaTeX.

## Modifications côté frontend

### `static/data/toolbar_seqenseigne.json`

Retri complet selon le principe acté :

**Avant** (v0.13.7.2 initial) :
- Le groupe `cadre_eleve` contenait `\seqCadreReponse` ❌ structurelle
- Le groupe `correction` contenait `\seqCorrige`, `\seqRemediation` ❌ structurelles
- Le groupe `envs_seqenseigne` contenait `seqNotion`, `seqMethode` ❌ structurelles
- Le groupe `exercice_seq` ne contenait que `\seqQcmQuestion` (item isolé)

**Après** (v0.13.7.2.1) :
- `cadre_eleve` supprimé du contexte `exo-enonce`. `\seqCadreReponse`
  retiré (utiliser la case à cocher de l'atelier).
- `correction` supprimé du contexte `exo-corrige`. `\seqCorrige` et
  `\seqRemediation` retirés (utiliser les champs dédiés).
- `envs_seqenseigne` renommé en `boites_pedago`. `seqNotion` et
  `seqMethode` retirées (structurelles, donc inutilisables). Reste
  `seqDefinition` et `seqPropriete` (légitimement utilisables dans le
  contenu de n'importe quel atome).
- `exercice_seq` renommé en `qcm` et enrichi : ajout de l'environnement
  `seqQcm` complet (utile à l'enseignant, c'est sa présence dans
  l'énoncé qui déclenche la détection « cet exo est un QCM » côté
  Python — cf. `services/atomes.py` L183).
- Nouveau groupe `completer` (pointillés `\dotfill` + `\acompleter`) :
  utilisé dans `exo-enonce` et `fiche-section`.
- Nouveau groupe `annexe` (`\seqAnnexe`) : utilisé dans les contextes
  où l'enseignant peut renvoyer du contenu vers les annexes.

Inventaire final : **15 groupes** (au lieu de 15 d'apparence dans
v0.13.7.2 mais avec un meilleur contenu) répartis comme suit :

| Contexte | Groupes |
|---|---|
| `variables` | xint_definitions, xint_aleatoire, xint_conditionnel |
| `exo-enonce` | maths_inline, listes, mise_en_page, **completer**, **qcm**, boites_pedago, annexe |
| `exo-corrige` | maths_inline, maths_display, listes, mise_en_page, boites_pedago |
| `notion-corps` | maths_inline, boites_pedago, boites_titrees, mise_en_evidence, annexe |
| `methode-corps` | maths_inline, boites_pedago, etapes, boites_titrees, annexe |
| `fiche-section` | maths_inline, listes, **completer**, mise_en_evidence |
| `carte-recto` | maths_inline, image |
| `carte-verso` | maths_inline, image |
| `theme-description` | mise_en_page, boites_titrees |

(En gras = nouveau ou modifié par rapport à v0.13.7.2 initial.)

### `static/editeur_latex.js`

- Cache des définitions devient un dictionnaire indexé par le booléen
  `inclure_structurelles` (deux valeurs possibles, chaque valeur a son
  propre cache pour éviter les re-fetch).
- `_chargerDefinitions(inclureStructurelles)` accepte maintenant le
  flag et l'ajoute en query param `?inclure_structurelles=1` si vrai.
- `_peuplerOngletPaquet()` lit la préférence via `_lireStructurellesPref()`
  (localStorage clé `ed-latex:afficher-structurelles`), affiche une
  case à cocher au bas du panneau de navigation (sous la liste des
  fichiers), et re-render complètement à chaque toggle.
- La préférence est **globale** (pas par contexte) : c'est une
  préférence d'expertise utilisateur, pas une préférence éditoriale
  liée au type d'atome.

### `static/app.css`

+22 lignes pour styler `.ed-latex-paquet-toggle-struct` (case à
cocher au bas du panneau de navigation gauche, séparée par une
bordure pointillée).

## Tests

- **15 tests pytest passent** (9 anciens + 6 nouveaux pour le filtrage
  structurel et le paramètre HTTP `?inclure_structurelles=`)
- Suite voisine (`test_preambule_atome.py` + `test_v0_13_7_1_paquet.py`) :
  78 passed, 0 failed
- Pytest complet non re-lancé en intégral (rien d'autre que des
  fichiers déjà testés n'a changé), mais aucune raison de régression

## Fichiers livrés

```
MODIFIÉS
appli/services/paquet_expose.py             (MACROS_STRUCTURELLES + paramètre)
appli/routes/paquet.py                       (paramètre HTTP ?inclure_structurelles=)
appli/static/editeur_latex.js                (cache + case à cocher + handlers)
appli/static/app.css                          (+22 lignes styles toggle)
appli/static/data/toolbar_seqenseigne.json   (retri pédagogique complet)
appli/tests/test_v0_13_7_1_paquet.py         (+6 tests pour le filtrage)
appli/doc/redemarrage_v0_13_7_2_1.md         (NEW)
```

## À tester chez toi

### Scénario A — Macros structurelles absentes par défaut

1. Ouvrir n'importe quel atelier, n'importe quel textarea.
2. Cliquer « ✎ Éditer ».
3. Onglet « Tout le paquet ».
4. Fichier « Exercices ».
5. **Vérifier** : `seqExercice`, `seqQcm`, `seqSerieExos` ne sont pas
   dans la liste (les deux premiers sont structurels au sens de l'app
   pour exercice ; mais `seqQcm` reste dispo via l'onglet « Outils »
   dans le contexte `exo-enonce`).
6. Fichier « Cœur ». **Vérifier** : `seqNotion`, `seqMethode`,
   `\seqCorrige`, `\seqCadreReponse`, etc. absents.

### Scénario B — Case à cocher fonctionnelle

1. Toujours dans l'onglet « Tout le paquet ».
2. Repérer la case « Afficher les macros structurelles » au bas du
   panneau de navigation (à gauche, sous la liste des fichiers).
3. **Cocher la case**.
4. Re-cliquer sur « Cœur » (le panneau peut s'être réinitialisé sur
   le 1er fichier).
5. **Vérifier** : `seqNotion`, `seqMethode`, `\seqCorrige`, etc.
   réapparaissent.
6. **Décocher la case** → ils disparaissent à nouveau.

### Scénario C — Persistance de la case

1. Cocher la case → fermer la modale (clic ×).
2. Rouvrir l'éditeur sur un autre textarea (même session ou après F5).
3. Onglet « Tout le paquet ».
4. **Vérifier** : la case est toujours cochée (persistance localStorage).

### Scénario D — Onglet « Outils » : disparition des items structurels

1. Ouvrir l'éditeur sur l'énoncé d'un exercice.
2. Onglet « Outils ».
3. **Vérifier** : il n'y a plus de groupe « Réponse élève » (n'existe
   plus, `\seqCadreReponse` était dedans).
4. **Vérifier** : il y a un nouveau groupe « QCM » (avec
   environnement seqQcm + question).
5. Ouvrir l'éditeur sur le corrigé d'un exercice.
6. **Vérifier** : plus de groupe « Correction » (qui contenait
   `\seqCorrige` et `\seqRemediation`).
7. Ouvrir l'éditeur sur le corps d'une notion.
8. **Vérifier** : `seqNotion` n'apparaît plus dans le groupe « Boîtes
   pédagogiques » (qui contient maintenant `seqDefinition` et
   `seqPropriete` seulement).

### Scénario E — Itération sur le JSON (workflow d'amélioration)

1. Ouvrir le fichier `appli/static/data/toolbar_seqenseigne.json`
   dans un éditeur de texte.
2. Modifier un item (ex. ajouter un nouveau snippet dans le groupe
   « Mise en page »).
3. **Sans relancer l'app**, rouvrir l'éditeur LaTeX dans un atelier.
4. **Vérifier** : la modification est visible immédiatement (le JSON
   est rechargé à chaque ouverture de modale).

C'est le workflow recommandé pour corriger/enrichir le contenu
pédagogique au fil de ton usage.

## Prochaine étape

Une fois cette livraison validée, on reprend la roadmap originale :

- **v0.13.7.3** : navigateur d'images depuis un dossier `outils/`
  (questions de cadrage à trancher au début : chemin exact, types
  de fichiers acceptés, chemin inséré dans le snippet).
- **v0.13.7.4** : mini-générateur de tableau `tblr`.
- **v0.13.7.5+** : aides Markdown (Phase 3 originale).

## Note sur la cohérence preambule_atome ↔ paquet_expose

J'ai documenté dans la docstring de `paquet_expose.py` le fait que
les deux modules listent des macros structurelles mais avec une
finalité distincte :

- `preambule_atome.WRAPPER_*` : utilisé pour la fermeture transitive
  des dépendances LaTeX (qui doit être dans le préambule pour que la
  compilation marche)
- `paquet_expose.MACROS_STRUCTURELLES` : utilisé pour le filtrage UI
  (ce que l'enseignant ne doit pas insérer manuellement dans son
  contenu)

Ces deux listes se recouvrent largement mais pas exactement (cf.
`seqColItem` qui est dans la première mais pas la seconde). Quand on
ajoute une macro structurelle dans `preambule_atome.py`, il faut
**réfléchir** si elle doit aussi être ajoutée à `paquet_expose.py`.
La réciproque n'est pas forcément vraie.

C'est une dette de design potentielle : on pourrait à terme dériver
une de l'autre, mais aujourd'hui la duplication est explicite et
documentée.
