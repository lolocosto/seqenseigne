# seqenseigne — Patch v0.8.2

**Date** : 26 avril 2026
**Type** : correctif sur v0.8 (suite à v0.8.1)

---

## Bug corrigé

### Notions et méthodes utilisant tkz-euclide ne compilent pas en rendu individuel

**Symptôme observé** : sur les rapports de compilation batch, plusieurs notions
plantent avec des erreurs LaTeX qui semblent incohérentes — la même notion
compile sans problème quand elle est incluse dans son livret de séquence.
Cas concret : `N10/S01/Notion 06` et `N10/S01/Notion 07` (« Repère d'une
droite », « Repère d'un plan »).

L'erreur affichée dans le rapport (`Undefined control sequence`) est tronquée
au premier mot ; en consultant directement le `.log` de pdflatex, l'erreur
réelle apparaît : `\tkzLabelX` n'est pas défini.

**Cause** : dans les versions récentes de `tkz-euclide` (≥ 5.x, fin 2022+),
`\usepackage{tkz-euclide}` seul ne définit plus la machinerie d'axes
(`\tkzLabelX`, `\tkzLabelY`, `\tkzDrawX`, `\tkzDrawXY`, `\tkzInit`...). Il
faut explicitement `\usepackage{tkz-base}` chargé **avant** `tkz-euclide`
pour disposer de ces commandes.

L'appli connaît cette contrainte : `services/preambule_atome.py` contient bien
une liste `_PAQUETS_GEOMETRIE = ['tkz-base', 'tkz-euclide', 'tkz-tab']` qui
est censée être ajoutée au préambule quand l'option `[geometrie]` est
détectée pour l'atome.

**Mais l'option `[geometrie]` n'était jamais détectée pour les notions et
méthodes**. La fonction `_analyser_paquets_utilises()` dans
`services/latex_rendu_atome.py` ne regardait que les champs scalaires
`corps`, `corrige`, `variables` :

```python
texte_complet = '\n'.join([
    atome.corps or '', atome.corrige or '', atome.variables or '',
])
```

Or pour les notions et méthodes (modèle universel à 2 niveaux introduit en
v0.6.4), le contenu LaTeX réel vit dans `atome.sections[].items[]`, pas
dans `corps`. Donc `texte_complet` était essentiellement vide, l'analyse de
macros retournait un ensemble vide, l'option `[geometrie]` n'était pas
activée, `tkz-base` n'était pas chargé, et `\tkzLabelX` plantait.

Pourquoi le livret entier passe : `\usepackage{seqenseigne}` charge
inconditionnellement les paquets `tkz-*` via ses options par défaut,
sans dépendre d'une analyse fine des macros effectivement utilisées.

---

## Correction

`services/latex_rendu_atome.py` :

- Nouvelle fonction `_aplatir_textes(noeud, profondeur=0)` : aplatit
  récursivement un nœud d'item de section en liste de chaînes LaTeX.
  Gère strings, listes, dicts, et types inattendus (ignorés). Lève
  `RecursionError` au-delà de `_PROFONDEUR_MAX_ITEMS = 4` — garde-fou
  contre une éventuelle évolution du format qui passerait silencieusement
  inaperçue (et causerait à nouveau ce type de régression).
- Nouvelle fonction `_texte_complet_atome(atome)` : concatène tout le
  contenu LaTeX d'un atome — titre, corps, corrigé, variables, **plus le
  titre et les items de chaque section**.
- `_analyser_paquets_utilises()` modifiée pour utiliser
  `_texte_complet_atome()` au lieu de la concaténation manuelle restreinte
  aux champs scalaires.

Profondeur max fixée à 4 conformément au cadrage : aujourd'hui les items
sont tous des chaînes plates (profondeur 0 dans la BDD réelle, vérifié
sur les 1124 atomes), mais le commentaire historique du dataclass `Atome`
évoque la possibilité de structures plus riches (multicols, sous-listes
imbriquées). 4 niveaux laissent une marge confortable, et au-delà la
RecursionError force à examiner le changement de format plutôt que
laisser le bug se reproduire.

---

## Atomes que ce correctif débloque

Sur ton dernier rapport (`Compilation_atomes_2026-04-26_15-34-14.md`), les
**Notions 06 et 07 de N10/S01** sont les premières à bénéficier directement
du fix (elles utilisent `\tkzInit`, `\tkzDrawX`, `\tkzLabelX`, `\tkzDrawXY`
dans leurs sections « Exemples »).

Les 17 autres erreurs `Package tikz Error: + or - expected` et
`Package pgfkeys Error: I do not know the key '/tikz/diamond'` sur S10–S14
sont d'une autre nature (probablement un problème de virgule décimale
française dans des coordonnées TikZ, ou une bibliothèque TikZ manquante
pour le `diamond`). Le fix v0.8.2 ne les corrige pas directement, mais
maintenant que `tkz-base` est chargé pour ces notions, les vraies erreurs
LaTeX deviendront plus lisibles dans le rapport (au lieu d'être masquées
par d'éventuelles erreurs en cascade dues à `tkz-base` manquant).

---

## Fichiers modifiés

- `services/latex_rendu_atome.py` : `_analyser_paquets_utilises()` étendu,
  ajout de `_aplatir_textes()` et `_texte_complet_atome()`.
- `tests/test_latex_rendu_atome.py` : 12 nouveaux tests
  (4 dans `TestPaquetsDetectesDansSections`, 8 dans `TestAplatirTextes`).

---

## Tests

```
python -m pytest tests/test_latex_rendu_atome.py -v
```

→ 77 tests, dont 12 nouveaux, tous verts.

Suite complète : 1312 verts + 4 skipped (les mêmes 4 que le baseline v0.7).
Aucune régression.

---

## Comment vérifier après déploiement

1. Décompresser le ZIP par-dessus l'appli.
2. Avant de relancer la compilation : **vider le cache** pour que les
   atomes problématiques soient effectivement recompilés (sinon ils
   resteront en statut « cache » avec leur ancien hash) :
   ```
   rm appli/data/cache_rendus/*.pdf appli/data/cache_rendus/*.log
   ```
3. Relancer Admin > Compilation > Notions N10. Les notions 06 et 07 de S01
   doivent passer en « Succès » au lieu de « Échec LaTeX ».
