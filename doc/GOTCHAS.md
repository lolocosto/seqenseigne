# Pièges connus et leurs résolutions

> v0.15.4 — refonte complète. Recense les pièges rencontrés et leur résolution.

## LaTeX / paquet seqenseigne

### Compilation en 2-3 passes obligatoire

`pdflatex` doit tourner **2 passes minimum** pour que `CorrList.tex` (corrigés des exercices) soit correctement inclus. Sur Windows USB, on fait **3 passes** systématiquement (pas de Perl → pas de `latexmk` pour décider).

### `\makeatletter` / `\makeatother` requis autour des `\seq@…`

Les macros internes du paquet contiennent `@`. Toute manipulation côté `.tex` doit être encadrée :

```latex
\makeatletter
\renewcommand{\seq@machin}{...}
\makeatother
```

### `\renewcommand` vs `\newcommand`

Pour les macros DÉJÀ définies par le paquet chargé : `\renewcommand`. Sinon on double-définit et `pdflatex` plante.

### `\seqCreeCompteurs` explicite si pas de `\seqTitreLivret`

Quand on n'appelle pas `\seqTitreLivret` (cas du `boiteTitreGen` maison), il faut appeler `\seqCreeCompteurs` explicitement avant `seqSerieExos`. Sinon les compteurs sont indéfinis.

### `\renewcommand{\seqCorrigesExos}{oui}` requis pour séries avancée/exploration

Sans cette directive, `CorrList.tex` reste vide pour ces deux séries. Les corrigés de la série fondamentale sont OK par défaut.

### `Corriges/` et `Annexes/` à pré-créer

Avant le premier `pdflatex`, les dossiers `Corriges/` et `Annexes/` doivent exister dans le workdir. Si absents, `\write` échoue.

### `\num` → siunitx (PAS numprint)

`\num{42}` mappe sur le paquet `siunitx`. Le paquet `numprint` n'est PAS utilisé. Détection auto + injection dans le préambule.

### `datatool` et `siunitx` injectés conditionnellement

Pas chargés par défaut dans le paquet. Le service de génération les détecte dans le `.tex` à compiler et les ajoute au préambule si besoin.

### Items qui commencent par `\newline`

`\item \newline foo` → erreur LaTeX « There's no line here to end ». Nettoyage côté parser : supprimer le `\newline` initial.

### Items syntaxiquement cassés

Plutôt que de faire échouer la compilation, on remplace par un placeholder visible : `\texttt{[item corrompu : <hash>]}`. L'enseignant repère le problème dans le PDF généré sans bloquer le reste.

### `\gdef` vs `\xdef`

`\xdef` quand la valeur expansée doit être stockée (pas la macro référence). `\gdef` quand on veut garder la macro telle quelle.

### `\DTLifeq` cassé dans datatool v3 avec arguments littéraux

Workaround : `\edef` pré-expansion. Toujours.

### tcolorbox titre avec virgule → doubles braces

```latex
\begin{tcolorbox}[title={{Foo, bar}}]   % ← correct, gérer la virgule
```

Sinon tcolorbox interprète la virgule comme séparateur de clés.

### `STATUT_IGNORE` dans `paquet_definitions`

Les macros marquées `statut_rendu_atome='ignore'` (par exemple `\seqTitreLivret`) doivent être **inlinées manuellement** dans le `.tex` généré (entre `\makeatletter…\makeatother` si elles utilisent du `@`). Le service de génération du livret livret_sequence est en charge.

### `\usetikzlibrary{babel}` incompatible avec `babel-french`

Via `tkz-euclide` qui charge `calc`. Gestion explicite (chargement conditionnel).

### `\wideparen` → paquet `yhmath`

Pas de paquet `wideparen` standard. Mapping côté détection.

### vwcol [lines=N] crash en compilation agrégée

Spécifier `[lines=N]` sur `\begin{vwcol}` peut crasher avec « Undefined control sequence \vwcol@widths » lors d'une compilation agrégée (récap cours, livret) même si l'atome compile en isolation. Workaround : retirer `[lines=N]` (laisser `lines=auto`).

Cas rencontrés : récap cours N11 et N12. NE PAS toucher au `\vwcolsetup{widths={0.5,0.5}}` du préambule — il est nécessaire pour la compilation isolée d'atomes N11/S12/01-02-03 sur MiKTeX.

## Flask / Python

### Pas de Flask dans `services/`

Les services prennent `conn` (sqlite3.Connection) en argument explicite. Pas de `g.db` ni `current_app`. Cela rend les services testables sans contexte Flask.

### Blueprint Flask dans les fixtures de tests

```python
if "xxx" not in app.blueprints:
    app.register_blueprint(bp_xxx)
```

Sinon Flask râle lors de l'enregistrement multiple en test.

### Scans séquentiels pour multi-niveaux

Pas de `Promise.all` côté JS ni de `concurrent.futures` côté Python pour les opérations multi-niveaux qui touchent SQLite en écriture : SQLite n'aime pas les écritures concurrentes. Itérer séquentiellement.

### Diff-based INSERT/UPDATE/DELETE pour les tables avec FK

Quand on met à jour une table référencée par d'autres (via FK), un `DELETE+INSERT` casse les FK enfants. Préférer un diff : `UPDATE` les changements, `INSERT` les nouveaux, `DELETE` les disparus, en respectant l'ordre des FK.

### `_echapper_texte` est l'identité

`services.atomes._echapper_texte` retourne son input tel quel. C'est volontaire : préserver le LaTeX intentionnel que l'enseignant a écrit. Pas d'échappement défensif des `\`, `{`, `}`, …

### `construire_preambule` transitive closure

Quand on ajoute une macro qui appelle d'autres macros, mettre à jour `fragment_squelette_livret` pour lister toutes les macros effectivement émises dans le préambule du livret. Une dépendance manquante = compilation cassée.

## SQLite

### CHECK constraint ne peut pas être modifié par ALTER

Pour changer la liste autorisée d'une colonne avec CHECK, il faut **recréer la table** : `CREATE _new + INSERT SELECT + DROP old + RENAME new`. Pattern utilisé dans `persistence.sqlite_store._migrer_schema` pour les états de référentiel.

### FK désactivées pendant la recréation

`PRAGMA foreign_keys = OFF` avant la recréation, `PRAGMA foreign_key_check` pour vérifier l'intégrité après, puis `PRAGMA foreign_keys = ON`. Voir doc SQLite « Making Other Kinds Of Table Schema Changes ».

### Idempotence des migrations

Toute migration doit avoir un test idempotent : « est-ce déjà appliqué ? » (typiquement détection de signature dans le DDL via `sqlite_master.sql`). Sinon on plante au 2e démarrage.

### Le default `CURRENT_TIMESTAMP` n'est pas autorisé sur `ALTER TABLE ADD COLUMN`

Workaround : ajouter la colonne nullable d'abord, puis `UPDATE table SET col = CURRENT_TIMESTAMP WHERE col IS NULL`.

## MiKTeX portable

### Pas de Perl, donc pas de latexmk

`pdflatex` en 3 passes manuel. Cf. `services.compilateur_pdf`.

### Cache PDF côté SHA-256

`services.compilateur_pdf` calcule un SHA-256 du `.tex` final + des images référencées. Si inchangé, on sert le PDF mis en cache plutôt que de relancer `pdflatex`. Le cache est invalidé sur sauvegarde/suppression d'atome, pas à l'ouverture.

### Workdirs orphelins

Les compilations utilisent `tempfile.gettempdir()/seqenseigne_workdir/<hash>`. Si Python plante avant nettoyage, des workdirs traînent. À nettoyer manuellement de temps en temps.

## JavaScript

### `let` top-level NE PAS attaché à `window`

```javascript
let ATL_REF_SELECTION = null;
// ⚠ window.ATL_REF_SELECTION → undefined
```

Pour exposer une variable globale lisible depuis d'autres scripts ou la console : `window.X = …` explicite, ou utiliser `var` (mais préférer `window.X`).

### Pas de framework, pas de build

Vanilla JS direct dans le navigateur. Pas de bundler, pas de transpilation. Donc :
- Pas d'imports ES modules (sauf si on configure `type="module"`).
- Tout vit dans le scope global ou IIFE.
- Compatible navigateurs récents.

### Tests JS

Aucun aujourd'hui. Validation visuelle. Quand la couche JS deviendra plus complexe, candidats : Vitest (ESM-natif) ou Jest. Installation dans `appli/`, ajout de `npm test` au workflow de validation.

## Référentiels (v0.15.3)

### États : `en_cours → valide → verrouille → utilise`

`fige` (≤ v0.15.2) a été fusionné dans `verrouille`. Migration auto au boot.

### Dossier `_verrouille/` (ex `_fige/`)

Trace JSON + PDFs. Renommage auto au boot si l'ancien existe.

### Anciens aliases conservés (rétrocompat)

- `services.referentiels.figer_minimal` → `verrouiller_minimal`
- `services.referentiel_figeage.figer_complet` → `verrouiller_complet`
- Route `POST /api/referentiels/<id>/figer` → alias de `/verrouiller`

À retirer en v0.16+ quand plus aucun appelant externe ne les référence.

## Outils CLI

### `outils/verifier_md5.py`

Format à 3 colonnes (jamais inventer un autre format) : `md5  taille  chemin`. CRLF. Voir CONVENTIONS.md.

### `outils/purger_fiches.py`

CLI dry-run par défaut, confirmation 'OUI' requise, FK cascade. v0.11.1.x.

### `outils/importer_referentiel_externe.py`

Reconstitue rétroactivement `<ref>/_verrouille/` pour un référentiel utilisé hors-système. Regex `[^/]*?S(\d{2})_Livret\.pdf$` tolère espace/tiret/underscore comme séparateur.

### `outils/archiver_docs.py`

D�place les notes obsolètes dans `doc/archives/<categorie>/`. Idempotent. Mode `--dry-run`.

## Conventions implicites du domaine

### Trois séries d'exercices : F / A / E

- **F** ou `fondamental` : à consolider, niveau de base
- **A** ou `avancé` : satisfaisant, niveau attendu
- **E** ou `exploration` : très bon, niveau d'extension

Codes BDD : `F`, `A`, `E`. Labels métier : `fondamental`, `avancé`, `exploration`. Traduction dans `services.referentiel_figeage._serie_label`.

### Objectif « Cours » par partie

Code `01` (partie 1), `11` (partie 2), `21` (partie 3) : ce sont les objectifs « Connaître les notions et les méthodes (Xère partie) ». Ils n'ont pas de méthode/notion/exercice spécifique liés ; les fiches de résumé de la partie y sont rattachées.

### Sigles niveaux

`N09` = 6ème, `N10` = 5ème, `N11` = 4ème, `N12` = 3ème. Stockés en BDD. Le code, pas le numéro affiché.

### 14 séquences par niveau

Convention cycle 4. Chaque séquence a un numéro (1-14) et un code (S01-S14).

## Documentation

### Notes de redémarrage figées

Une fois livrée, une note `redemarrage_v0_X_Y_Z.md` n'est **jamais modifiée**. Si on doit corriger quelque chose, on livre un hotfix `v0_X_Y_Z_1_hotfix.md`.

### `archives/` = lecture seule

Aucun fichier dans `doc/archives/` n'est modifié. C'est de l'historique factuel. Pour comprendre l'évolution d'un sujet : `grep -r mot doc/archives/`.
