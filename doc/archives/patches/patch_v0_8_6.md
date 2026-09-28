# seqenseigne — Patch v0.8.6

**Date** : 26 avril 2026
**Type** : alignement de la mise en page sur les livrets + correctif vwcol.

---

## Contexte

Sur les notions N11 fraîchement compilées via le batch v0.8.5, 3 cas
résistaient (S12/Notion 01, 02 et 03 — Pythagore, Thalès, trigonométrie).
Tous trois utilisent le paquet `vwcol` (variable-width columns) qui
échouait avec :

```
! Package vwcol Error: Not enough lines to fit the entire text;
some text has been truncated. Increase [lines=5] to fit more.
```

Diagnostic en deux temps.

---

## 1. Marges alignées sur les livrets

**Cause première** : `vwcol` calcule la largeur de chaque colonne à
partir de `\linewidth`. En isolation (rendu d'atome), les marges article
par défaut donnent une `\linewidth` d'environ **345 pt**. Dans un livret,
la commande `\seqTitreSection` du paquet seqenseigne applique
`\newgeometry{left=35pt,right=35pt,top=65pt,bottom=70pt}`, ce qui élargit
`\linewidth` à environ **528 pt**. La différence (53 %) suffit à faire
basculer les figures vwcol entre « ça tient » et « ça déborde ».

**Fix** : émettre `\newgeometry{left=35pt,right=35pt,top=65pt,bottom=70pt}`
dans le préambule reconstruit de chaque atome, juste après les
`\usepackage` du noyau (donc avant les inits de bibliothèques et avant
les définitions inlinées de seqenseigne). Valeur identique à celle de
`seqenseigne-core.sty::\seqTitreSection`.

**Effet de bord positif** : la mise en page de tous les atomes (notions,
méthodes, exercices) s'aligne sur celle des livrets. Un PDF d'atome est
désormais plus représentatif de ce qu'il sera dans le livret final —
intéressant pour la prévisualisation pédagogique.

**Implémentation** :

- Nouvelle constante `GEOMETRY_NEWGEOMETRY` dans
  `services/preambule_atome.py`, avec doc-string explicative.
- Émission dans `construire_preambule()` après les paquets noyau.

---

## 2. Initialisation préventive de vwcol

Avec les marges corrigées, les 3 cas N11/S12 produisent désormais un PDF,
mais avec des messages `! Undefined control sequence` autour de
`\vwcol@widths`. Sur TeX Live (Linux) ces erreurs sont tolérées (PDF
quand même produit), sur **MiKTeX (Windows) elles sont fatales** — donc
côté Laurent, l'appli les classe en `echec_compilation`.

**Cause** : `vwcol` ne fournit aucune valeur par défaut pour la clé
`widths`. Si le contenu d'un atome écrit `\begin{vwcol}[lines=N]` sans
`widths=`, dans un scope où aucun `\vwcolsetup{widths=...}` antérieur
n'a été exécuté (cas typique : `\vwcolsetup{...}` dans un précédent
`seqColItem`, dont le `\begin{itemize}` interne a refermé le scope),
alors `\vwcol@widths` est undefined et l'expansion de
`\expandafter\vwcol@process@widths\expandafter{\vwcol@widths}` lève
l'erreur.

**Fix** : initialiser `\vwcol@widths` à une valeur neutre `{0.5,0.5}`
dans le préambule, dès que `vwcol` est chargé. Cette valeur par défaut
est ignorée si le contenu surcharge `widths=` localement (mécanisme
normal de `\setkeys`).

**Implémentation** :

- Nouvelle entrée `'vwcol': [r'\vwcolsetup{widths={0.5,0.5}}']` dans le
  dictionnaire `INITIALISATIONS_BIBLIOTHEQUES` de `preambule_atome.py`.
- L'init n'est émise que si `vwcol` figure parmi les paquets chargés
  (cas standard du mécanisme `INITIALISATIONS_BIBLIOTHEQUES`).

---

## Vérification BDD réelle

| Atome | État avant v0.8.6 | État après v0.8.6 |
|---|---|---|
| N11/S12/Notion 01 (Pythagore) | `vwcol Error: Not enough lines` (fatal MiKTeX) | ✓ PDF, 0 erreur |
| N11/S12/Notion 02 (Thalès) | `vwcol Error: Not enough lines` (fatal MiKTeX) | ✓ PDF, 0 erreur |
| N11/S12/Notion 03 (trigonométrie) | `Undefined control sequence` (fatal MiKTeX) | ✓ PDF, 0 erreur |

Régression vérifiée sur un échantillon N10 : aucun changement de
comportement pour les atomes qui n'utilisent pas vwcol (l'init préventive
n'est émise que si vwcol est chargé). Les cas particuliers v0.8.5
(xltabular, shapes.geometric, tikz babel) compilent toujours sans erreur.

---

## Fichiers modifiés

- `services/preambule_atome.py` :
  - Constante `GEOMETRY_NEWGEOMETRY` ajoutée.
  - `construire_preambule()` émet `\newgeometry` après les paquets
    noyau, avant les inits de bibliothèques.
  - Nouvelle entrée `'vwcol'` dans `INITIALISATIONS_BIBLIOTHEQUES`.

- `tests/test_preambule_atome.py` :
  - 4 nouveaux tests dans `class TestNewGeometry` (présence,
    position relative à `\usepackage{geometry}`, position relative
    aux définitions seqenseigne, export de la constante).
  - 4 nouveaux tests dans `class TestVwcolInitialisation` (pas
    d'init si vwcol absent, init si vwcol chargé, position correcte,
    présence dans le dictionnaire exporté).

---

## Tests

**Suite complète** : 945 tests verts + 4 skipped sur le périmètre testé
(routes, services, persistence, parseurs, rendu, compilation batch).
Aucune régression.

---

## Bilan attendu sur N11

Les 3 cas vwcol résolus, les notions N11 devraient maintenant compiler
à **39/39** (les autres échecs identifiés dans les runs précédents —
images manquantes en S10/N01, S13/N03, et `\columnbreak` dans
`seqColItem[nbCols=1]` en S13/N02 — étaient des problèmes de contenu
côté BDD, et tu les as déjà corrigés vu ton dernier rapport à 36/39).

---

## Notes pour la suite (non bloquantes)

**Bug latent identifié** dans `services/preambule_atome.py::
_paquets_externes_optionnels` : la fonction reçoit `envs_atome` en
paramètre mais ne l'utilise pas (seul `macros_atome` est consulté pour
construire le set des paquets externes). En pratique, ça ne cause aucun
problème en prod parce que le pipeline complet compense via
`detecter_paquets_tex_manquants` dans `latex_rendu_atome.py`, qui
détecte les environnements et les passe via `paquets_tex_supplementaires`.
Mais cette duplication de logique mérite d'être nettoyée à terme — peut-être
en v0.9 lors d'un refactoring du pipeline.

---

## Comment tester chez toi

1. Déployer le ZIP, redémarrer le serveur.
2. Le cache PDF est automatiquement invalidé (le préambule a changé,
   les hashes aussi).
3. Relancer la compilation batch sur N11/S12 (ou tout N11) — les
   3 cas devraient passer.
4. Pour vérifier l'effet positif des marges, regarder un PDF d'atome
   généré par le batch vs ce qui était produit avant : les marges sont
   désormais celles du livret.
