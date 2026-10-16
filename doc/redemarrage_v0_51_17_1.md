# Redémarrage v0.51.17.1 — Correctif : \seqContenuAvantSerie non définie dans le livret

## Symptôme

Livret de séquence avec prérequis et exos de révision : « Undefined control
sequence \seqContenuAvantSerie », alors que les `.sty` à jour sont dans
MiKTeX et que le paquet a été réindexé.

## Cause

Le livret ne charge pas `seqenseigne.sty` : son préambule est reconstruit
par `construire_preambule`, qui recopie seulement les définitions de
`paquet_definitions` atteintes depuis le texte analysé (corps des atomes +
liste des macros émises par le squelette du livret). v0.51.17 émettait
`\seqContenuAvantSerie` sans l'ajouter à cette liste. Les tests ne l'ont
pas vu : leur `paquet_definitions` est vide.

## Correctif

- `services/livret_sequence.py` : la liste devient la constante de module
  `FRAGMENT_SQUELETTE_LIVRET`, avec `\seqContenuAvantSerie{X}`.
- `tests/test_livret_sequence.py` : `TestSqueletteLivret` (3 tests) simule
  un paquet indexé (une définition factice par macro ou environnement
  `seq…`/`boite…` présent dans le document) et vérifie que chacune est
  recopiée dans le préambule, sur les branches du squelette (objectifs à
  plusieurs parties, prérequis par le crochet, prérequis sans série 0).
  Vérifié : le test échoue sans le correctif en nommant la macro.

## Déploiement

Rien côté paquet ni MiKTeX (déjà à jour). Remplacer les deux fichiers,
recompiler le livret.
