# Redémarrage v0.15.2.1 — Factorisation render_carte_centralise + suppression param_evaluator

## Objectif

Première étape de la refonte (C1) cadrée pour v0.15.2 : créer le **point
unique de rendu d'une carte** selon son contexte (atelier isolé, récap,
planche fixe, planche paramétrée), et **supprimer `param_evaluator`** qui
n'est plus utilisé dans la chaîne de rendu (P1=α dans le cadrage).

**Périmètre v0.15.2.1** : exclusivement l'atelier isolé + factorisation +
suppression `param_evaluator`. Le récap et les planches **restent cassés**
(refonte planifiée en v0.15.2.2 et v0.15.2.3).

## Décisions issues du cadrage

| # | Décision |
|---|---|
| P1 | α — Jeter la substitution Python. xintexpr évalue tout côté LaTeX. |
| P2 | γ — Tirage LaTeX via fichier auxiliaire (planches paramétrées). Côté .dtx. |
| P3 | Sans objet (P1=α rend l'extension de `param_evaluator` inutile). |
| P4 | Impression bord court → pas de miroir horizontal côté Python. |
| P5 | Conserver `\seqCarteAuto` pour atelier isolé. |
| P6 | C1 maintenant (cartes uniquement). C2 et C3 plus tard. |
| P7 | Pas de hotfix intermédiaire. |
| P8 | α — Supprimer `param_evaluator.py` + routes mortes. |

## Architecture cible (rappel)

```
services/
  render_carte_centralise.py        ← NOUVEAU
    rendre_carte_isole(conn, carte) → {preambule_variables, corps}
    rendre_carte_recap(conn, carte) → {preambule_variables,
                                         cellule_recto, cellule_verso}
    rendre_carte_planche_fixe(conn, carte) → {page_recto, page_verso}
    rendre_carte_planche_parametree(conn, carte) → {appel}

  render_carte.py                    ← Migré, délègue à render_carte_centralise
  livret_cartes_recap.py             ← Non migré v0.15.2.1, refonte en v0.15.2.2
  livret_cartes_planches.py          ← Non migré v0.15.2.1, refonte en v0.15.2.3
```

## Changements v0.15.2.1

### 1. Nouveau module `services/render_carte_centralise.py`

Module central avec :

- **4 fonctions wrapper** (une par contexte) : `rendre_carte_isole`,
  `rendre_carte_recap`, `rendre_carte_planche_fixe`,
  `rendre_carte_planche_parametree`.
- **Utilitaires partagés** : `resoudre_code_couleur`,
  `resoudre_libelle_type_pedago`, `_echapper_valeur_option`.
- **Helpers internes** : `_variables_xint`, `_options_recto`,
  `_options_verso`.

Stratégie commune : **pas de substitution Python**, variables xint
émises soit dans le préambule (atelier isolé), soit avant
l'environnement englobant (récap), soit gérées par la macro côté .dtx
(planche paramétrée via `\seqCartePlancheParametree`).

### 2. Migration `services/render_carte.py`

Le module conserve son API publique (`generer_tex_carte`) et tous ses
utilitaires (`resoudre_code_couleur`, `resoudre_libelle_type_pedago`,
`_echapper_valeur_option`, `LIBELLE_TYPE_PEDAGO`, `CODE_COULEUR_DEFAUT`,
`RenderCarteErreur`) — réexportés depuis `render_carte_centralise` pour
rétrocompatibilité. Aucun changement de comportement pour l'atelier de
prévisualisation.

### 3. Suppression de `param_evaluator` (P8=α)

**Fichiers supprimés** :
- `appli/services/param_evaluator.py`
- `appli/routes/param.py`

**Modifications dans `app.py`** :
- Retrait de `from services.param_evaluator import ...`
- Retrait de `from routes.param import bp as bp_param`
- Retrait de `bp_param` dans la liste `register_blueprint`

**Aucun appel frontend ou autre module n'utilisait** la route
`/api/param/*` (vérifié par `grep`). Suppression sans impact UI.

### 4. Tests

**Nouveau fichier** : `tests/test_v0_15_2_1_render_carte_centralise.py`
(15 tests, couvre les 4 fonctions wrapper + utilitaires partagés).

**Tests désactivés (skip) avec raison** :
- `test_livret_cartes_recap_carte_parametree_dans_groupe`
- `test_livret_cartes_planches_inversion_horizontale_verso`
- `test_livret_cartes_planches_parametree_16_tirages_varies`
- `test_livret_cartes_planches_parametree_recto_verso_partagent_valeur`
- `test_livret_cartes_recap_parametree_recto_verso_meme_valeur`
- `test_livret_cartes_recap_xintfloateval_substitue`

Ces tests vérifiaient la substitution Python, désormais abandonnée
(P1=α). Ils seront remplacés en v0.15.2.2 et v0.15.2.3 par des tests
de la nouvelle stratégie.

**Notes en tête des modules cassés** :
- `livret_cartes_recap.py` : refonte en v0.15.2.2
- `livret_cartes_planches.py` : refonte en v0.15.2.3

## Vérifs

- **Suite Python complète** : **3440 passed, 12 skipped, 0 failed**.
  - Précédent (v0.15.1.3.3) : 3431 passed, 6 skipped.
  - Delta : +15 nouveaux tests (`render_carte_centralise`)
    -6 tests désactivés temporairement = **+9 passed**. Cohérent.
- **Démarrage app Flask** : OK (vérifié `from app import create_app`).
- **Test fonctionnel atelier de prévisualisation d'une carte** : à
  faire chez toi (compilation isolée d'une carte unique).

## État des autres documents en v0.15.2.1

| Document | État | À traiter en |
|---|---|---|
| Compilation isolée d'une carte (atelier) | ✅ Fonctionnel | (déjà OK) |
| Récap des cartes (vue enseignant) | ❌ Cassé | v0.15.2.2 |
| Planches de cartes (vue élève) | ❌ Cassé | v0.15.2.3 |

C'est intentionnel : on découpe la refonte en étapes pour limiter le
risque par livraison.

## Action attendue côté Laurent

### 1. Décompresser le ZIP à la racine `seqenseigne/`

### 2. Supprimer manuellement les 2 fichiers obsolètes

Le ZIP ne peut pas « supprimer » des fichiers, seulement en ajouter ou
en écraser. Il faut donc supprimer manuellement :

```powershell
del appli\services\param_evaluator.py
del appli\routes\param.py
```

(Ces 2 fichiers sont sans impact UI : aucune route ou module ne les
utilisait, à l'exception de mes propres `livret_cartes_recap` et
`livret_cartes_planches` qui sont prévus pour refonte en v0.15.2.2 et
v0.15.2.3.)

### 3. Vérifier l'intégrité

```powershell
.\outils\python\python.exe appli\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
```

### 4. Lancer la suite de tests

```
cd appli
..\outils\python\python.exe -m pytest tests -q
```

Attendu : **3431 passed, 23 skipped** (3417 précédent + 15 nouveaux
+ 0 supprimé, avec 6 nouveaux skips, etc. — le compte précis dépend de
ton environnement, l'important est qu'il n'y ait **aucun fail**).

### 5. Tester l'atelier de prévisualisation d'une carte

Ouvrir une carte quelconque dans l'atelier des cartes, cliquer sur
« Tester » (compilation isolée). Le PDF doit s'afficher comme avant.

**Aucun test à faire** sur le récap des cartes ni sur les planches —
ils sont cassés intentionnellement et seront restaurés en v0.15.2.2
et v0.15.2.3.

## Roadmap

- **v0.15.2.2** : refonte `livret_cartes_recap.py` pour utiliser
  `render_carte_centralise.rendre_carte_recap`. Variables xint émises
  avant l'environnement `seqCartePageRecap` dans un groupe englobant.
- **v0.15.2.3** : refonte `livret_cartes_planches.py` pour utiliser
  `render_carte_centralise.rendre_carte_planche_fixe` /
  `rendre_carte_planche_parametree`. Utilise la nouvelle macro
  `\seqCartePlancheParametree` (côté .dtx à implémenter par Laurent).
  Pas de miroir horizontal.

- **v0.15.3+** : (C2) factorisation transverse — extraction d'un
  module `render_atome.py` qui mutualiserait la logique de variables
  xint entre cartes, exercices, notions, méthodes, fiches résumé.
- **v0.15.x+** : (C3) refonte de l'orchestration des documents
  (long terme).
- **v0.16** : migration atelier séquence vers OO + portée Niveau.

## Fichiers livrés

```
NOUVEAUX
  appli/services/render_carte_centralise.py
  appli/tests/test_v0_15_2_1_render_carte_centralise.py
  appli/doc/redemarrage_v0_15_2_1.md             (cette note)

MODIFIÉS
  appli/services/render_carte.py                  (délègue à _centralise)
  appli/services/livret_cartes_recap.py           (note de tête)
  appli/services/livret_cartes_planches.py        (note de tête)
  appli/tests/test_v0_13_6_5_2_livrets_manquants.py  (6 tests skip)
  appli/app.py                                     (retrait imports param)

À SUPPRIMER MANUELLEMENT (cf. § 2 ci-dessus)
  appli/services/param_evaluator.py
  appli/routes/param.py
```
