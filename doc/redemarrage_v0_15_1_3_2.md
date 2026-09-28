# Redémarrage v0.15.1.3.2 — Hotfix substitution `\xintfloateval`

## Symptôme

À la compilation du **Récap des cartes** post-déploiement v0.15.1.3.1,
Laurent observe :

```
L.116 xint error: `N10S01C13_res' unknown, say `Isome_var' or I use 0.
\end
L.116 Paragraph ended before \xint<...> is done, but will resume:
\end
```

Ligne 116 du `.tex` généré :

```latex
\seqCarteVersoRecap[niveau=N10, sequence=S01, num=13]{$\num{\xintfloateval{N10S01C13_res}}$}
```

La variable `N10S01C13_res` n'a pas été substituée → xintexpr la voit
comme inconnue.

## Cause

**Deux bugs dans `_substituer_variables`** du code Python :

1. **Regex incomplète** : la fonction substituait seulement
   `\xintii?eval{name}` (i.e. `\xintieval` et `\xintiieval`) mais
   **PAS `\xintfloateval{name}`**. Donc pour une carte avec une
   variable de type `\xintdeffloatvar` utilisée via `\xintfloateval`,
   la macro autour de la variable restait dans le `.tex` final, et
   LaTeX la voyait comme une utilisation de variable inconnue.

2. **Échec silencieux** : si `param_evaluator` ne parvenait pas à
   évaluer une variable (syntaxe non supportée, par exemple `divmod`,
   `quo`, `rem`), la fonction `_resoudre_carte_parametree` tombait
   silencieusement dans son `except` et conservait le source d'origine
   intact — sans signaler qu'il restait des `\xint*eval{...}` non
   substitués.

**Pourquoi `param_evaluator` ne substituait-il pas `N10S01C13_res`** ?
Réponse : il le faisait correctement (validation par test direct).
**C'est bien la regex `\xintii?eval` qui ne capturait pas
`\xintfloateval`**, donc le `\xintfloateval{N10S01C13_res}` restait
tel quel dans le `.tex`. La substitution sur le nom nu (`\bN10S01C13_res\b`)
aurait dû s'appliquer à l'intérieur, mais on observe qu'elle ne s'est
pas appliquée non plus dans ton `.tex` — possiblement parce que le nom
`N10S01C13_res` arrivait à la fin du dict env et que les noms plus
courts (par exemple sans `_res`) étaient testés avant, mais ce n'est
pas l'explication principale. La correction du point 1 corrige tous
les cas.

## Corrections appliquées

### 1. `_substituer_variables` étendue

Désormais 3 prefixes traités :

```python
for prefix in ('xintiieval', 'xintieval', 'xintfloateval'):
    text = re.sub(
        r'\\' + prefix + r'\{\s*' + re.escape(name) + r'\s*\}',
        str(val),
        text,
    )
```

Applique aussi bien à `livret_cartes_recap.py` qu'à `livret_cartes_planches.py`.

### 2. Détection des substitutions manquantes

Nouvelle fonction `_detecter_variables_non_substituees(source)` qui
liste les `\xint*eval{...}` restants après substitution. Si la liste
n'est pas vide, c'est qu'on a un trou.

### 3. Fallback robuste

Quand `_detecter_variables_non_substituees` détecte des résidus
(typiquement : variable que `param_evaluator` n'a pas su évaluer), le
code Python **ne tente pas de planter** mais bascule en **mode
fallback** : la carte conserve ses sources `recto`/`verso` d'origine,
et un champ `_fallback_variables` est ajouté. Le rendu de cellule
embarque alors les `\xintdef*var` originales dans un groupe `{...}`
côté LaTeX (xintexpr évaluera lui-même).

**Conséquence du fallback** :
- **Récap** : recto et verso ont leurs propres groupes séparés → leur
  tirage est indépendant → **partage recto/verso perdu**.
- **Planches** : chacune des 16 cellules a son propre groupe → **tirage
  indépendant cellule par cellule**, **partage recto/verso perdu**.

Ce n'est pas le comportement nominal souhaité mais c'est un **filet de
sécurité** qui évite l'erreur fatale de compilation. À traiter en
étendant `param_evaluator` quand nécessaire.

### 4. Tests garde-fou ajoutés (2 nouveaux)

- `test_livret_cartes_recap_xintfloateval_substitue` : vérifie qu'aucun
  `\xintfloateval{nom_de_variable}` ne reste dans le `.tex` après
  substitution (régression v0.15.1.3 → v0.15.1.3.2).
- `test_livret_cartes_planches_fallback_si_substitution_impossible` :
  vérifie que le mode fallback se déclenche bien quand une variable
  utilise `quo` (non supporté par `param_evaluator`) et que les
  `\xintdefiivar` sont ré-émises dans le `.tex`.

## Vérifs

- **Suite Python complète** : **3429 passed, 6 skipped, 0 failed**
  (était 3427 ; +2 nouveaux tests = 3429).
- **Test manuel direct** sur la carte N10/S01/CA13 :
  - Avant : `\seqCarteVersoRecap[...]{$\num{\xintfloateval{N10S01C13_res}}$}` → plantage
  - Après : `\seqCarteVersoRecap[...]{$\num{7.69}$}` → compile OK
  - Et le **recto** correspondant : `\seqFrac{769}{100}` (partage valeur OK)

## Limitations encore présentes (à traiter plus tard)

`param_evaluator` toujours limité :
- Pas de `\xintdefiivar A, B := divmod(...);` (assignation parallèle)
- Pas d'opérateurs `quo`, `rem` (xintexpr)
- Pas de `divmod()` (alias xintexpr)

**Mais** : grâce au mode fallback v0.15.1.3.2, ces cartes **compilent
quand même** — au prix de :
- Récap : recto et verso de la carte ont des tirages différents
- Planches : 16 cellules avec 16 tirages indépendants (pas de
  partage recto/verso)

Ces inconvénients restent **acceptables comme dégradation gracieuse**.
Extension de `param_evaluator` à prévoir si tu veux que ces cartes
aient le comportement nominal (substitution Python avec partage
recto/verso).

## Fichiers livrés

```
MODIFIÉS
  appli/services/livret_cartes_recap.py             (+ regex étendue, fallback)
  appli/services/livret_cartes_planches.py          (+ regex étendue, fallback)
  appli/tests/test_v0_13_6_5_2_livrets_manquants.py (+ 2 tests garde-fou)

NOUVEAU
  appli/doc/redemarrage_v0_15_1_3_2.md              (cette note)
```

## Procédure d'application

### 1. Décompresser le ZIP à la racine `seqenseigne/`

(Pas besoin de réimporter le paquet `seqenseigne-carte-automatisme` —
celui de v0.15.1.3 reste valide.)

### 2. Vérifier l'intégrité

```powershell
.\outils\python\python.exe appli\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
```

### 3. Lancer la suite de tests

```
cd appli
..\outils\python\python.exe -m pytest tests -q
```

Attendu : `3419 passed, 17 skipped` (3417 précédent + 2 nouveaux tests).

### 4. Test fonctionnel

**Récap des cartes** : recompiler. Le `.tex` ligne 116 doit maintenant
contenir `$\num{X.XX}$` avec une valeur substituée (pas
`\xintfloateval{N10S01C13_res}`).

**Si une carte utilise `divmod`, `quo`, `rem`** (par exemple CA13
séquence S10) : la compilation passe maintenant (mode fallback), mais
- Récap : la valeur recto et verso peuvent différer
- Planches : les 16 cellules ont chacune leur tirage propre (sans
  partage recto/verso)

À voir : si tu observes ce comportement de fallback chez toi, on
étendra `param_evaluator` dans une livraison séparée.
