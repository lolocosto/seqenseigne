# Correctif — session 2 — `ModuleNotFoundError: scripts.peuplement_14_verif_couverture`

## Problème

Chez Laurent, à l'exécution de `pytest`, 10 tests échouaient sur :

```
ModuleNotFoundError: No module named 'scripts.peuplement_14_verif_couverture'
```

## Cause

`services/latex_rendu_atome.py` importait (en local, dans `detecter_options_paquet`)
depuis `scripts.peuplement_14_verif_couverture` :

```python
from scripts.peuplement_14_verif_couverture import (
    MACROS_PAQUETS_EXTERNES, extraire_utilisations,
)
```

C'était une **violation architecturale** : un service ne doit pas dépendre
d'un script. Les services sont du code réutilisable (importé par Flask et
par les scripts) ; les scripts sont des outils de ligne de commande qui
peuvent dépendre des services, pas l'inverse.

Chez moi le test passait artificiellement parce que les scripts contenaient
`sys.path.insert` qui ajoutait la racine au path, ce qui rendait l'import
réversible — mais ça ne devait pas. Chez Laurent, configuration plus propre,
`scripts/` n'est pas un package ni dans `sys.path` → import impossible.

## Correctif

Déplacé de `scripts/peuplement_14_verif_couverture.py` vers
`services/paquet_parseur.py` :

- le dictionnaire `MACROS_PAQUETS_EXTERNES` (293 entrées)
- la fonction `extraire_utilisations(texte)`
- la fonction `extraire_macros_definies_localement(texte)`

Leur place naturelle était là dès le départ : ce sont des outils d'analyse
de texte LaTeX, au même titre que `strip_comments`, `extract_balanced`, etc.

## Fichiers modifiés

- `services/paquet_parseur.py` : ajout du bloc déplacé en fin de fichier.
- `scripts/peuplement_14_verif_couverture.py` : suppression du bloc
  dupliqué, import depuis `services/paquet_parseur`.
- `services/latex_rendu_atome.py` : import corrigé vers
  `services/paquet_parseur` (plus de dépendance vers `scripts/`).

## Vérification

109 tests du chantier 14 verts après refactor. Peuplement et vérification
de couverture produisent des résultats identiques à avant.

## Leçon retenue

Une dépendance `service → script` doit toujours déclencher une alerte
architecturale. Quand ça arrive, c'est que le code dans le script devait
vivre dans un service.
