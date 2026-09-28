# Livraison v0.6.4 — Préambule sur mesure pour les atomes

**Date :** 25 avril 2026
**Périmètre :** performance compilation atomes (objectif : < 3 s)

---

## Ce qui change

Le `.tex` généré pour un atome ne fait plus `\usepackage{seqenseigne}`.
À la place, on calcule la **fermeture transitive** des macros et environnements
effectivement utilisés par l'atome, on inline ces définitions dans le préambule
entre `\makeatletter` et `\makeatother`, et on charge **uniquement** les paquets
LaTeX externes nécessaires.

### Gain mesuré (échantillon 30 atomes BDD)

|                          | Avant                 | Après             |
|--------------------------|-----------------------|-------------------|
| Paquets LaTeX chargés    | ~110 (cascade depuis seqenseigne) | ~25-29 |
| Définitions du paquet utilisées | 271 (toutes celles 'reutilise') | 46-67 |
| Paquets lourds éliminés  | datatool, hyperref, datetime, fmtcount, lastpage, fancyhdr, longtable, xltabular, eurosym, tracklang | — |

### Ce que ça donne sur un .tex concret

Pour `N10S01A01.tex` (exercice avec `\seqFrac`, `\xint*`, `\num`) :

```
%% Préambule sur mesure : 67 définitions inlinées, 26 paquets externes

\documentclass[11pt,a4paper]{article}

%% ── Paquets externes (noyau pour atome) ───────────────
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[french]{babel}
... (24 paquets noyau)
\usepackage[theorems,breakable,skins]{tcolorbox}
\usepackage{pifont}

%% ── Paquets externes additionnels (selon l'atome) ─────
\usepackage{siunitx}
\usepackage{xintexpr}

%% ── Définitions du paquet seqenseigne (inlinées) ─────
\makeatletter
\newcommand{\seqCouleurRougeVif}{red!85!black}
... (67 définitions)
\makeatother
```

---

## Fichiers livrés

À copier vers leurs emplacements respectifs dans `appli/` :

| Fichier | Destination |
|---------|-------------|
| `preambule_atome.py` | `appli/services/` (NOUVEAU) |
| `latex_rendu_atome.py` | `appli/services/` (modifié — `generer_tex_atome` refondu) |
| `test_preambule_atome.py` | `appli/tests/` (NOUVEAU — 33 tests) |
| `test_latex_rendu_atome.py` | `appli/tests/` (modifié — 3 tests adaptés au nouveau comportement) |

Aucune migration de schéma. Aucun changement côté UI ou routes Flask.

---

## Architecture

### Module `services/preambule_atome.py`

Pièce centrale, **autonome**. Une seule fonction publique :

```python
def construire_preambule(
    conn,
    type_atome,                          # 'exercice' | 'notion' | 'methode'
    macros_atome,                        # set des \\macros utilisées par l'atome
    envs_atome,                          # set des environnements utilisés
    options_atome=None,                  # ['geometrie'] et/ou ['scratch']
    paquets_tex_supplementaires=None,    # ['siunitx', 'xint', ...]
) -> Preambule
```

Retourne un `Preambule` dataclass avec :
- `texte` : le bloc à insérer dans le `.tex` (entre `\documentclass` et `\begin{document}`)
- `paquets_externes` : liste finale des `\usepackage`
- `definitions_emises` : noms des définitions inlinées (pour debug)
- `nb_definitions_*` : compteurs de diagnostic

### Algorithme

1. **Charger l'index** des 338 lignes de `paquet_definitions` en mémoire (1 requête).
2. **Frontière initiale** = (macros + envs de l'atome ∩ index) ∪ wrapper systématique.
   - Wrapper commun : `\seqCreeCompteurs`, `\seqSetColorsTheme`, `\seqSetCodeNiveau`, `\seqSetCodeSequence`
   - Wrapper exercice : ajoute `seqExercice`, `seqSerieExos`, `\seqInit*`, `\seqAffiche*`, `\seqCorrige`, `\seqCorrigesExos`
   - Wrapper notion : ajoute `seqNotion`, `seqColItem`
   - Wrapper méthode : ajoute `seqMethode`, `seqColItem`
3. **Fermeture transitive** sur `macros_appelees` et `environnements_utilises`.
4. **Filtrer** les définitions au statut `'ignore'` (67 macros : `\seqLoadData`, `\seqTitreLivret`, `\seqBilan*`, etc.).
5. **Détecter les paquets externes** :
   - via `MACROS_PAQUETS_EXTERNES` (siunitx, xint, hyperref…) sur les macros de l'atome ET sur les corps des définitions retenues
   - + paquets noyau toujours chargés (24 : encodage, polices, math, tcolorbox, tikz, etc.)
   - + tkz-* si option `[geometrie]`, scratch3 si option `[scratch]`
6. **Émission** dans l'ordre `theme.sty → data.sty → core.sty → legacy.sty`,
   puis `ligne_debut` croissante intra-fichier (préserve les dépendances).

### Cas particulier : statut `'reecrit'`

Si une définition est en statut `'reecrit'`, on émet son `contenu_atome`
(la version réécrite par les règles de `paquet_regles_atome.py`) au lieu
de son `texte_complet` (la version d'origine du paquet).

À ce jour, aucune règle n'est en `'reecrit'` (toutes ont été nettoyées en
v0.6.3d), mais le mécanisme est en place pour quand le besoin réapparaîtra.

---

## Tests

### Couverture

`test_preambule_atome.py` — **33 tests** :

- `TestChargerIndex` (3) : chargement et parsing JSON de l'index
- `TestFermetureTransitive` (6) : chaînes de dépendances, cycles évités, set vide
- `TestWrapperParType` (5) : wrapper exercice/notion/méthode/inconnu
- `TestConstruirePreambule` (8) : préambule nominal, statut `ignore`, statut `reecrit`
- `TestOrdreEmission` (2) : ordre theme→core, ligne croissante
- `TestMakeatletter` (1) : encadrement des définitions
- `TestPaquetsExternes` (5) : paquets supp., dédoublonnage, options [geometrie]/[scratch], pseudo-paquets
- `TestPreambuleStats` (2) : compteurs de diagnostic, paquets dans le résultat

### Régression

`test_latex_rendu_atome.py` — 64 tests, dont 3 adaptés au nouveau comportement :

| Test | Ancienne assertion | Nouvelle assertion |
|------|--------------------|--------------------|
| `test_exercice_simple_compilable` | `\usepackage{seqenseigne}` | aucun `\usepackage{seqenseigne}` actif (commentaires ignorés) |
| `test_exercice_avec_options` | `\usepackage[geometrie]{seqenseigne}` | `\usepackage{tkz-base}` + `\usepackage{tkz-euclide}` + `\usepackage{tkz-tab}` |
| `test_aucun_paquet_externe_si_pas_necessaire` | exactement 1 `\usepackage` | aucun paquet optionnel (`siunitx`, `scratch3`, `tkz-*`) |
| `test_reecritures_entourees_par_makeatletter` | injection d'une règle reecrit | injection d'une dépendance réutilisée |

### Exécution chez vous

```bat
cd appli
python -m pytest tests/test_preambule_atome.py tests/test_latex_rendu_atome.py -v
```

Attendu : 97 passed.

---

## Validation côté compilation (à faire chez vous)

Le moyen rapide de mesurer le gain :

1. **Avant déploiement.** Sur un atome représentatif (ex. `N10S01A01`),
   noter le temps de la 1re compilation depuis le cache vidé :

   ```bat
   cd appli
   del data\cache_rendus\*.pdf
   :: lancer un rendu PDF dans l'UI et noter X-Seq-Duree-Ms dans la réponse
   ```

2. **Après déploiement.** Refaire la même mesure. Le ratio devrait être
   d'environ **0.4 à 0.5** (gain factor ~2-2.5).

Si le résultat est décevant (ex. seulement 0.7×), creuser piste suivante :
- vérifier que `\usepackage{seqenseigne}` n'apparaît plus dans le `.tex` généré
  (route `GET /api/atomes/<type>/<id>/rendu-tex`)
- vérifier le log pdflatex : `grep "Package:" data/cache_rendus/<hash>.log | wc -l`
  doit donner ~30 (vs ~110 avant).

---

## Points d'attention pour la suite

- **Le `.tex` généré est plus gros** (~15 ko vs ~5 ko avant) parce qu'on inline
  les définitions du paquet. C'est attendu et ce n'est pas un problème pour
  pdflatex, qui se moque de la taille du `.tex` source — ce qui le ralentit
  c'est le nombre et la complexité des paquets chargés.

- **Si une compilation échoue après déploiement** sur un atome qui passait
  avant : la cause la plus probable est qu'une dépendance manque dans le graphe
  `paquet_definitions.macros_appelees`. Diagnostic :
  - récupérer le `.tex` via `/rendu-tex`
  - lire le message d'erreur pdflatex
  - identifier la macro non définie (ex. `\seq@xxx`)
  - vérifier en BDD : `SELECT * FROM paquet_definitions WHERE nom = '\\seq@xxx'`
  - et chercher qui aurait dû la tirer mais ne le fait pas.
  Le scanner des `.dtx` (qui peuple `macros_appelees`) peut avoir un bord cassé
  sur certaines constructions ; un re-scan complet (`Admin → Import référence`)
  peut corriger.

- **Aucune action requise sur les `.dtx`** du paquet : ce travail est purement
  côté appli Python.

---

## À venir (livraisons 3 et 4 — UX)

À faire après validation perf :

3. **UX onglets** :
   - suppression de l'onglet « LaTeX généré » dans les 3 ateliers
   - ajout d'un bouton « LaTeX généré » dans la toolbar qui ouvre une modale
   - autosize des `<textarea>` (énoncé, corrigé, items, etc.)

4. **Onglet Préférences + vue split** :
   - nouvel onglet « Préférences » en barre principale
   - toggle « Vue côte-à-côte édition + PDF » persisté dans `configuration.json`
   - mode split CSS flex 50/50 dans les 3 ateliers
