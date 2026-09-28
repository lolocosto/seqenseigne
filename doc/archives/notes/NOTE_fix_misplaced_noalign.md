# Fix Récap cours — `Misplaced \noalign`

## Cause

Le service `livret_recap_cours.py` n'a pas transmis les paramètres
`tikz_libraries` et **`tblr_libraries`** à `construire_preambule()`.

Conséquence : l'instruction **`\UseTblrLibrary{booktabs}`** n'était pas
émise dans le préambule. Sans cette instruction, les commandes `\toprule`,
`\midrule` et `\bottomrule` ne sont **pas reconnues à l'intérieur d'un
environnement `tblr`** (paquet `tabularray` v2025A et postérieures), ce
qui produit l'erreur :

```
! Misplaced \noalign.
```

Le premier atome du livret N10 qui contient un `tblr` avec `\toprule`
est la méthode N10/S01/01 — d'où l'arrêt à la ligne 662.

C'est cohérent avec le commentaire en tête de `INITIALISATIONS_BIBLIOTHEQUES`
dans `preambule_atome.py` : la migration v0.9.1 a déplacé l'init en dur
de `\UseTblrLibrary{booktabs}` vers la liste paramétrable
`tblr_libraries`, mais mon code de `livret_recap_cours.py` ne passait
pas cette liste.

## Correction

Deux fichiers modifiés :

1. **`services/livret_recap_cours.py`**
   - `generer_recap_cours()` accepte maintenant les paramètres optionnels
     `tikz_libraries` et `tblr_libraries`
   - Ils sont transmis tels quels à `construire_preambule()`

2. **`routes/recap_cours.py`**
   - Les deux routes (`/tex` et `/pdf`) lisent maintenant
     `config.tikz_libraries()` et `config.tblr_libraries()` depuis la
     `Configuration` utilisateur (mêmes valeurs que pour le rendu d'un
     atome individuel)
   - Elles passent ces listes au service

## Vérification

Le .tex généré contient maintenant juste après `\usepackage{tabularray}` :

```
\UseTblrLibrary{booktabs}
\UseTblrLibrary{varwidth}
```

Tests backend : 103 passent, aucune régression.

## Fichiers livrés

- `services/livret_recap_cours.py` (modifié)
- `routes/recap_cours.py` (modifié)

Aucun changement au frontend.
