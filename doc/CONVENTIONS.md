# Conventions de code et de livraison

> v0.15.4 — refonte complète. Précédente : v0.13.5.1.6 (mai 2026).

## Livraison

### ZIP unique par version

- Une livraison = un ZIP nommé `seqenseigne_v0_X_Y_Z.zip` (et éventuellement `_data_demo.zip` pour les données associées).
- Une livraison contient **uniquement la diff** par rapport à la version précédente (pas le dépôt entier).
- Si plusieurs ZIPs (code + data demo), nommer explicitement.

### MANIFEST.md5 obligatoire

À la racine de chaque ZIP, un fichier `MANIFEST.md5` au format **trois colonnes** (espaces simples, jamais de tabulations) :

```
<md5sum>  <taille_en_octets>  appli/chemin/relatif.py
```

Encodage **CRLF** (Windows). L'outil `appli/outils/verifier_md5.py` vérifie l'intégrité du ZIP après dézippage :

```powershell
..\outils\python\python.exe outils\verifier_md5.py --racine . --manifest MANIFEST.md5
```

Le manifeste doit lister **TOUS les fichiers nouveaux ou modifiés** par la livraison. Un fichier oublié bloque le déploiement → tests qui échouent (cf. hotfix v0.15.2.12.1).

### Versionnement

Convention `vMAJOR.MINOR.PATCH[.PATCHSUFFIX]` :

- Saut MINOR : nouveau chantier, modèle d'état modifié, restructure majeure (ex. v0.15.3)
- Saut PATCH : ajout incrémental dans un chantier (ex. v0.15.2.10)
- Saut PATCHSUFFIX : hotfix critique post-déploiement (ex. v0.15.2.12.1)

### Note de redémarrage

À chaque livraison, un fichier `doc/redemarrage_v0_X_Y_Z.md` qui documente :

- Contexte / motivation (lien avec le retour utilisateur si applicable)
- Liste des changements (sections par fichier modifié)
- Décisions techniques clés et leurs raisons
- Migration éventuelle (BDD, dossiers, …)
- Nombre de tests `pytest -q` (`N passed, M skipped, 0 failed`)
- Liste des fichiers livrés
- Vérification post-déploiement (commandes à lancer chez l'utilisateur)
- Roadmap : ce qui reste à faire

## Style de code

### Python

- **PEP 8** souple. Lignes ≤ 88 caractères en général, mais OK de dépasser si ça aide la lisibilité.
- **Docstrings** : toute fonction publique a un docstring qui dit *quoi* et *pourquoi*, pas seulement *comment*.
- **Pas de Flask dans `services/`** : Flask est confiné à `routes/`. Les services manipulent `conn` (sqlite3.Connection) en argument, jamais `g.db` ou `current_app`.
- **Imports** : `from __future__ import annotations` en tête, puis stdlib, puis tiers (Flask), puis local.
- **Type hints** : oui pour les signatures publiques, optionnel à l'intérieur.

### SQL

- Mots-clés en `MAJUSCULES`, identifiants en `snake_case`.
- `LEFT JOIN` plutôt que `JOIN` quand la jointure peut échouer (ex. méthode non liée à un objectif).
- `?` placeholders, jamais d'interpolation Python pour les valeurs.
- Migrations : `_migrer_schema` (avant DDL) ou `_migrer_schema_post_ddl` (après). Idempotentes obligatoirement.

### JavaScript

- **Pas de framework, pas de build**. Vanilla JS qui tourne tel quel dans le navigateur.
- **Pas de `let` top-level attaché à `window`** : `let X = 1` au top du script n'est PAS accessible via `window.X`. Pour exposer : `window.X = 1` explicite.
- **`escHtml`/`escAttr` toujours** quand on insère des valeurs utilisateur dans du HTML.
- **`async/await`** pour les appels API. Wrapper `api(url, opts)` fait le `fetch` + gestion d'erreur.

### LaTeX

- **`@`-macros internes** restent dans `.dtx`/`.sty`. À exposer via un wrapper public nommé.
- **Pas de `\makeatletter` dans le `.tex` généré.**
- **`\renewcommand`** (pas `\newcommand`) pour les macros déjà définies par le paquet chargé.
- **Forced packages pour livret** : `datetime` (pour `\newdateformat`), `tblr_libraries=['booktabs','varwidth']`, `\graphicspath{{data/images/}{./images/}{./}}`.

Voir `GOTCHAS.md` pour les pièges spécifiques (datatool, tcolorbox, vwcol, …).

## Tests

### Discipline

- **Zéro régression** : `pytest -q` doit passer (0 failed) avant chaque livraison.
- **Test-driven** : toute décision non évidente est encodée dans un test nommé. Le nom du test explique le « pourquoi » qui sera violé si on casse la règle.
- Exemple : `test_lazy_ne_touche_pas_verrouille` documente l'invariant que `maj_etat_lazy` ne doit jamais modifier un référentiel à l'état terminal.

### Nomenclature

- `tests/test_v0_X_Y_Z_<theme>.py` pour les tests qui couvrent une livraison.
- `tests/test_<module>.py` pour les tests permanents (test_routes.py, test_referentiels.py, …).
- Test names en français : `test_objectif_cours_porte_fiches_de_la_partie_pas_atomes`.

### Skipped sur Windows

Certains tests sont conditionnés à la présence de `pdflatex` accessible (compilation réelle). Sur Linux CI, ils passent ; sur Windows USB MiKTeX, ils peuvent skipper selon la configuration. C'est attendu.

## Stockage des données

### BDD = source unique de vérité

- Pas de `.dbtex`, pas de `\seqLoadData{...}` côté `.tex` généré.
- Les variables qui pilotent le rendu (titres, niveaux, séquences) sont inlinées dans le préambule du `.tex` au moment de la compilation.
- `_params.tex` est obsolète depuis v0.13.5.

### Images

- Stockage **plat** dans `data/images/`.
- Nommage : `<tex_basename>[_<free_suffix>].png`.
- Détection de collision par SHA256.

### Référentiels verrouillés

- `data/referentiels/<ref_id>/_verrouille/trace.json` : structure pédagogique gelée.
- `data/referentiels/<ref_id>/_verrouille/pdfs/` : PDFs gelés.
- Anciennement `_fige/` (≤ v0.15.2). Migration auto au boot.

## Communication

- **Direct, technique**. Pas d'enrobage.
- **Sans emoji** sauf 🎉 pour les milestones (test count > précédent, livraison validée bout-en-bout, …).
- **En français**. Variables et fonctions internes peuvent être en français aussi (`verrouiller_minimal`, `_charger_objectifs`) : c'est cohérent avec le domaine pédagogique français.
- **Pas de surinterprétation** : si l'utilisateur dit X, on fait X. Si X est ambigu, on demande UNE question de scoping puis on agit.
