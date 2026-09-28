# Redémarrage v0.15.1.3.3 — Détection des variables incompatibles xintexpr

## Symptôme

Après déploiement de v0.15.1.3.2 (qui a corrigé la substitution
`\xintfloateval`), Laurent observe une nouvelle erreur sur la
compilation du récap :

```
L.124 Argument of \XINT_expr_fetch_to_semicolon_a has an extra }.
\end
==> Fatal error occurred, no output PDF file produced!
```

Le `.tex` ligne 124 :

```latex
\xintdeffloatvar N10S01C13_res := float(N10S01C13_n / 100,2);
```

## Cause

La variable BDD pour la carte N10/S01/CA13 utilise `float(x, 2)`, une
syntaxe qui n'est **ni Python ni xintexpr** valide :

- **Python** : `float()` accepte un seul argument. `float(x, 2)` lève
  `TypeError`.
- **xintexpr** : la fonction `float(...)` n'existe pas. `\xintdeffloatvar`
  gère la précision flottante en interne, pas besoin d'arrondi explicite.

Conséquence : `param_evaluator` lève une exception silencieuse →
fallback déclenché → variables ré-émises dans le `.tex` → `xintexpr` se
plaint que `float(x, 2)` n'est pas une expression valide.

## Cause profonde du problème

Le **mode fallback** introduit en v0.15.1.3.2 supposait que les
variables BDD étaient toujours du **xintexpr valide**. Or rien ne le
garantit : `param_evaluator` est plus tolérant que xintexpr (il accepte
Python pur), donc un utilisateur peut écrire en BDD du code qui marche
côté Python mais pas côté LaTeX.

## Correction (v0.15.1.3.3)

Ajout d'un check `_variables_xint_compatibles_latex` qui détecte
les patterns manifestement Python-only AVANT de basculer en fallback.
Patterns détectés :

- `float(x, ...)` — `float()` Python à 2 args
- `int(...)` — pas en xintexpr
- `round(x, n)` — `round()` xintexpr est à 1 arg

Logique de décision :

```
Si param_evaluator évalue OK :
    Substitution Python en dur → recto/verso avec valeurs
Sinon (substitution incomplète) :
    Si syntaxe xintexpr compatible :
        Fallback LaTeX (variables ré-émises dans `{...}`)
    Sinon (syntaxe Python-only détectée) :
        Message d'erreur explicite dans la cellule
        ("Erreur carte CA13 : float(...) non disponible en xintexpr.
          À corriger en BDD.")
```

Le PDF compile alors **toujours**, avec :
- soit la valeur correcte (cas nominal)
- soit le fallback LaTeX (cas intermédiaire — tirage indépendant)
- soit un message d'erreur visible (cas incompatible — à corriger en BDD)

## Tests garde-fou ajoutés (2 nouveaux)

- `test_livret_cartes_recap_variables_python_only_message_erreur` :
  vérifie qu'une carte avec `float(x, 2)` produit un message d'erreur
  visible plutôt qu'un fallback LaTeX qui planterait.
- `test_livret_cartes_planches_variables_python_only_message_erreur` :
  idem pour les planches.

## Vérifs

- **Suite Python complète** : **3431 passed, 6 skipped, 0 failed**
  (était 3429 ; +2 nouveaux tests = 3431).

## Action attendue côté Laurent

### Corrections BDD recommandées

**1. Carte N10/S01/CA13** : remplacer

```latex
\xintdeffloatvar N10S01C13_res := float(N10S01C13_n / 100,2);
```

par

```latex
\xintdeffloatvar N10S01C13_res := N10S01C13_n / 100;
```

`\xintdeffloatvar` gère la précision flottante en interne (cf.
`\xintDigits := 4;` pour contrôler globalement). Pas besoin de
`float(x, 2)`.

**2. Carte N10/S10/CA13** : la syntaxe `\xintdefiivar A, B := divmod(...);`
devrait fonctionner côté xintexpr (assignation parallèle). À vérifier
en pratique au prochain test de compilation.

## Limitation toujours présente

`param_evaluator.py` ne supporte toujours pas `divmod`, `quo`, `rem`
côté Python. Pour ces cartes, le mode fallback LaTeX se déclenche
(variables ré-émises dans `{...}` côté LaTeX). xintexpr les évalue
nativement → compilation OK, **mais** :

- Récap : recto et verso d'une carte ont des tirages différents
- Planches : 16 cellules ont 16 tirages indépendants (pas de partage
  recto/verso entre les 2 faces d'une même copie)

C'est une dégradation acceptable. Extension de `param_evaluator` à
prévoir si tu veux le partage recto/verso pour ces cartes (chantier
~30 lignes).

## Fichiers livrés

```
MODIFIÉS
  appli/services/livret_cartes_recap.py             (+ _variables_xint_compatibles_latex)
  appli/services/livret_cartes_planches.py          (+ idem)
  appli/tests/test_v0_13_6_5_2_livrets_manquants.py (+ 2 tests)

NOUVEAU
  appli/doc/redemarrage_v0_15_1_3_3.md              (cette note)
```

## Procédure d'application

### 1. Décompresser le ZIP à la racine `seqenseigne/`

### 2. Corriger la carte N10/S01/CA13 en BDD

Via l'atelier des cartes, ouvre N10/S01/CA13 et remplace
`float(N10S01C13_n / 100,2)` par `N10S01C13_n / 100` dans le champ
« variables ».

### 3. Vérifier l'intégrité

```powershell
.\outils\python\python.exe appli\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
```

### 4. Lancer la suite de tests

```
cd appli
..\outils\python\python.exe -m pytest tests -q
```

Attendu : `3421 passed, 17 skipped` (3419 précédent + 2 nouveaux tests).

### 5. Recompiler le récap

Compilation doit passer. Si une autre carte présente une incompatibilité
similaire, elle apparaîtra avec un message « Erreur carte CAxx : ... À
corriger en BDD » directement dans le PDF — pas d'erreur de compilation
fatale.
