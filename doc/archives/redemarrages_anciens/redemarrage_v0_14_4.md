# Redémarrage v0.14.4 — Unification finale du rendu PDF

## Position dans le workstream unification

| | Statut |
|---|---|
| **v0.14.1** : Renommage `exo` → `exercice` | ✓ Déployé |
| **v0.14.2** : Backend unifié (route /info, dispatch carte) | ✓ Déployé |
| **v0.14.3** : HTML statique + auto-compile | ✓ Déployé |
| **v0.14.4** : Descente AtelierEditeur + suppressions + spinner | ⏳ Cette livraison |

C'est la **dernière étape** du chantier d'unification rendu PDF.

## Cadrage validé

| Question | Réponse |
|---|---|
| Spinner visuel | (a) Gros spinner au centre à la place du placeholder |
| Bascule client carte | Déclaration explicite `endpointRenduPdf: '/api/atomes/carte'` dans AtelierCarte |
| Suppression AtelierAtomique | (a) Suppression complète |
| Ordre client/backend | Client d'abord, backend ensuite, dans la même livraison |

## Architecture cible

### Avant (v0.14.3)

```
Hiérarchie OO :
  Atelier
    └─ AtelierEditeur (modif/sauvegarde/onglets)
         └─ AtelierAtomique (rendu PDF)
              ├─ AtelierExercice
              ├─ AtelierNotion
              ├─ AtelierMethode
              ├─ AtelierFiche
              └─ AtelierCarte

Fichiers JS pour le rendu PDF :
  - atelier_atomique.js  (classe AtelierAtomique)
  - rendu_atome.js       (helpers globaux historiques, obsolète)

Routes pour la carte :
  - /api/cartes/<id>/rendu-pdf       (alias temporaire)
  - /api/cartes/<id>/rendu-pdf/info  (alias temporaire)
  - /api/cartes/<id>/rendu-tex       (alias temporaire)
  - /api/atomes/carte/<id>/rendu-pdf       (cible, v0.14.2)
  - /api/atomes/carte/<id>/rendu-pdf/info  (cible, v0.14.2)
  - /api/atomes/carte/<id>/rendu-tex       (cible, v0.14.2)
```

### Après (v0.14.4)

```
Hiérarchie OO simplifiée :
  Atelier
    └─ AtelierEditeur (modif/sauvegarde/onglets + RENDU PDF)
         ├─ AtelierExercice
         ├─ AtelierNotion
         ├─ AtelierMethode
         ├─ AtelierFiche
         └─ AtelierCarte

Fichiers JS pour le rendu PDF :
  (aucun fichier dédié — tout dans atelier_editeur.js)
  - atelier_atomique.js → stub explicatif (≈25 lignes de commentaire)
  - rendu_atome.js      → stub explicatif (≈20 lignes de commentaire)

Routes pour la carte :
  (les 3 alias /api/cartes/<id>/rendu-* sont SUPPRIMÉS)
  - /api/atomes/carte/<id>/rendu-pdf       (seul endpoint)
  - /api/atomes/carte/<id>/rendu-pdf/info  (seul endpoint)
  - /api/atomes/carte/<id>/rendu-tex       (seul endpoint)
```

Plus aucun reliquat des développements indépendants par atelier.

## Modifications

### 1. Descente de la machinerie de rendu PDF dans AtelierEditeur

**`atelier_editeur.js`** :
- Constructeur enrichi :
  - `this.lignesFautives = []` (pour highlight dans le .tex brut)
  - `this._genRendu = 0` (compteur pour la race condition)
  - `this.config.endpointRenduPdf` (fallback sur `endpointBase` si non précisé)
- Méthode `basculerOnglet` enrichie : appelle `verifierCacheEtAfficher()`
  quand on bascule sur l'onglet 'rendu' avec un item actif (ce qui
  faisait l'objet d'une surcharge dans AtelierAtomique avant v0.14.4)
- 8 méthodes descendues telles quelles :
  - `verifierCacheEtAfficher()`
  - `_remettrePlaceholderRendu()`
  - `compilerRendu()`
  - `_afficherErreurCompilation(status, data)`
  - `toggleTexBrut()`
  - `_afficherTexBrut(tex)`
  - `scrollVersLigneTex(ligne)`
  - `voirLatex()`

**`atelier_atomique.js`** : réduit à un stub de ~25 lignes (commentaire
explicatif uniquement, plus aucun code actif).

### 2. Suppression de rendu_atome.js

**`rendu_atome.js`** : réduit à un stub de ~20 lignes. Le fichier ne
contient plus aucune fonction globale (rendreAtomeTab, rendreAtomeLancer,
etc.). En v0.14.3, il était déjà inutilisé (aucun appel actif depuis le
code) mais conservé pour compatibilité ; en v0.14.4 on l'élimine.

**`index.html`** :
- `<script src="/static/atelier_atomique.js">` retiré
- `<script src="/static/rendu_atome.js">` retiré
- Commentaire de hiérarchie OO mis à jour pour refléter la structure
  v0.14.4

### 3. Bascule de la carte sur l'API unifiée

**`atelier_carte_automatisme.js`** :
- Ajout de `endpointRenduPdf: '/api/atomes/carte'` dans la config (les
  4 autres ateliers avaient déjà cette config depuis v0.14.3)

**`routes/cartes_automatisme.py`** :
- 3 routes `/api/cartes/<id>/rendu-pdf*` supprimées :
  - POST /rendu-pdf
  - GET /rendu-pdf/info
  - GET /rendu-tex
- Helpers internes `_configuration`, `_cache_dir`, `_racine_appli`
  (devenus orphelins) supprimés
- Imports `sqlite3`, `Path`, `Response` (orphelins) supprimés
- Les routes CRUD (`GET/POST/PATCH/DELETE /api/cartes`, `/api/cartes/<id>`)
  sont préservées — seules les routes rendu sont retirées

### 4. Spinner visuel pendant la compilation

**`templates/index.html`** : pour les 5 ateliers, ajout dans le bloc
rendu d'une zone :

```html
<div id="atl-<type>-rendu-loading" class="rendu-loading"
     style="display:none;flex:1">
  <div class="rendu-spinner"></div>
  <p>Compilation en cours…</p>
</div>
```

Le CSS `.rendu-loading` et `.rendu-spinner` existait déjà dans `app.css`
(animation `@keyframes rendu-spin`, cercle de 32px qui tourne à 0.8s/tour).

**`atelier_editeur.js`** :
- `compilerRendu()` : au début de la méthode, masque l'iframe et le
  placeholder, affiche le spinner (`loadingEl.style.display = 'flex'`).
  Au succès, à l'échec et en cas d'erreur réseau, le spinner est masqué
  (`loadingEl.style.display = 'none'`). Filet de sécurité dans le
  `finally` pour les cas de race condition.
- `_remettrePlaceholderRendu()` : masque aussi le spinner par sécurité
  (évite qu'un spinner « orphelin » reste affiché après une remise à
  l'état initial pendant une compilation).

## Adaptations des tests existants

4 fichiers de tests obsolètes mis à jour pour pointer vers les nouveaux
emplacements :

- **`test_v0_13_6_2_render_carte.py::TestRouteRenduTex`** : test sur
  l'ancienne URL `/api/cartes/<id>/rendu-tex` → adapté vers la nouvelle
  URL `/api/atomes/carte/<id>/rendu-tex`. Le payload d'erreur 404 a
  changé : on accepte maintenant `{'error': str}` au lieu du code métier
  `'carte_introuvable'`.

- **`test_v0_13_7_6_1_stepper_et_info.py`** :
  - Fixture `CHEMIN_JS_AT` pointe maintenant vers `atelier_editeur.js`
    (au lieu d'`atelier_atomique.js`)
  - Fixture `CHEMIN_ROUTE` pointe maintenant vers `routes/rendu_atome.py`
    (au lieu de `cartes_automatisme.py`)
  - Tests adaptés pour chercher avec une regex `@bp.route(...)` plutôt
    qu'avec une recherche textuelle de la première occurrence (qui
    matchait un docstring d'en-tête)
  - Test `test_basculer_onglet_surcharge` : la « surcharge » n'existe
    plus (la logique est directement dans AtelierEditeur.basculerOnglet)
    → on vérifie juste la présence du branchement vers
    `verifierCacheEtAfficher`

- **`test_v0_14_2_backend_unifie.py::TestAncienneRouteCartesConservee`** :
  sémantique inversée → devient `TestAncienneRouteCartesSupprimee`.
  Vérifie maintenant que les anciennes routes répondent 404 (preuve de
  leur suppression). +1 test (rendu-tex aussi vérifié).

- **`test_v0_14_3_html_unifie_et_auto_compile.py`** : la fixture
  `atel_atomique` pointe maintenant vers `atelier_editeur.js` (puisque
  c'est là que la logique a migré). Les assertions sur les patterns du
  code sont inchangées et continuent de passer.

## Tests v0.14.4 ajoutés

Nouveau fichier `tests/test_v0_14_4_unification_finale.py` (44 tests) :

- **TestSuppressionAtelierAtomique** (2 tests) — fichier réduit à un
  stub, plus de balise `<script>` dans le HTML
- **TestSuppressionRenduAtome** (2 tests) — idem pour rendu_atome.js
- **TestMethodesDansEditeur** (10 tests paramétrés) — chacune des 8
  méthodes rendu PDF présente dans AtelierEditeur, branchement
  basculerOnglet→verifierCacheEtAfficher, init du constructeur
- **TestHeritageDirect** (5 tests paramétrés) — les 5 ateliers étendent
  `AtelierEditeur` directement
- **TestCarteMigree** (6 tests) — `endpointRenduPdf` côté client,
  routes supprimées côté serveur, routes CRUD préservées, HTTP 404
- **TestSpinnerVisuel** (15 tests dont 10 paramétrés) — zones HTML
  présentes pour les 5 ateliers, CSS, compilerRendu manipule loadingEl
- **TestImportsNettoyes** (3 tests) — imports orphelins retirés de
  cartes_automatisme.py

## Fichiers livrés

```
MODIFIÉS
  appli/templates/index.html                       (HTML statique spinner + scripts retirés)
  appli/static/atelier_editeur.js                  (descente complète d'AtelierAtomique + spinner)
  appli/static/atelier_carte_automatisme.js        (endpointRenduPdf API unifiée)
  appli/static/atelier_atomique.js                 (réduit à un stub)
  appli/static/rendu_atome.js                      (réduit à un stub)
  appli/routes/cartes_automatisme.py               (routes rendu supprimées + nettoyage imports)
  appli/tests/test_v0_13_6_2_render_carte.py       (adapté à la nouvelle URL)
  appli/tests/test_v0_13_7_6_1_stepper_et_info.py  (adapté aux nouveaux emplacements)
  appli/tests/test_v0_14_2_backend_unifie.py       (sémantique inversée)
  appli/tests/test_v0_14_3_html_unifie_et_auto_compile.py (fixture redirigée)

NOUVEAUX
  appli/tests/test_v0_14_4_unification_finale.py   (44 tests)
  appli/doc/redemarrage_v0_14_4.md                 (ce document)
```

## Note sur le déploiement des stubs

Les fichiers `atelier_atomique.js` et `rendu_atome.js` sont **livrés
en tant que stubs** (≈20-25 lignes de commentaires seulement). C'est
volontaire : un déploiement par déballage du zip écrasera les versions
précédentes par les stubs vides. Aucune script ne référence ces fichiers
dans `index.html` après v0.14.4.

Tu peux supprimer ces deux fichiers manuellement après déploiement si
tu veux un dossier `appli/static/` totalement propre. Aucun code ne
les charge plus.

## Vérifs

- pytest : **3496 passed, 5 skipped, 0 failed**
  (3451 baseline v0.14.3 - 1 ancien obsolète + 1 nouveau dans v0.14.2
   + 44 nouveaux dans v0.14.4 + qq adaptations = +45 net)
- `node --check` sur tous les JS modifiés : OK
- `ast.parse` sur les fichiers Python modifiés : OK

## À tester chez toi

### A — Aucune régression sur les 5 ateliers (test prioritaire)

1. Déployer le zip et hard reload (Ctrl+Shift+R).
2. Ouvrir chaque atelier (Exercice, Notion, Méthode, Fiche, Carte) :
   - Cliquer un item dans la liste → le formulaire se remplit
   - Basculer sur Rendu PDF
   - **Vérifier le spinner** : un cercle bleu tourne pendant la
     compilation, avec « Compilation en cours… » en dessous, au
     centre de la zone
   - Le PDF s'affiche à la fin
3. **Modification + bascule rendu** : modifier un titre sans
   enregistrer, basculer sur Rendu PDF → la sauvegarde silencieuse
   s'opère (badge « modifié » disparaît), puis le spinner tourne,
   puis le nouveau PDF apparaît
4. **Race condition** : cliquer rapidement entre 2 cartes (A avec
   cache, B sans cache) → le PDF de A ne réapparaît jamais sur B
   (mécanisme v0.13.7.6.1.1.2 préservé)
5. **Préférence auto-compile** : la décocher dans Préférences →
   basculer sur Rendu d'un atome modifié → placeholder visible (pas
   d'auto-compile). La recocher → idem sur un autre atome → spinner
   puis PDF (auto-compile actif)

### B — Vérification réseau (DevTools)

Onglet Réseau dans F12 :
1. Ouvrir une carte avec cache, onglet Rendu PDF
2. **Vérifier** : `GET /api/atomes/carte/<id>/rendu-pdf/info` (et plus
   `/api/cartes/<id>/rendu-pdf/info`)
3. **Vérifier** : `POST /api/atomes/carte/<id>/rendu-pdf` (et plus
   `/api/cartes/<id>/rendu-pdf`)
4. Si tu vois encore des appels à `/api/cartes/<id>/rendu-*`, c'est
   que le cache navigateur n'a pas été vidé → faire un hard reload

### C — Vérification manuelle avec curl

```bash
# L'ancienne route doit répondre 404 (supprimée)
curl -i http://localhost:5000/api/cartes/crt_756ac269b576/rendu-pdf/info
# Attendu : 404 NOT FOUND

# La nouvelle route doit répondre 200 (carte existante avec cache)
curl -i http://localhost:5000/api/atomes/carte/crt_756ac269b576/rendu-pdf/info
# Attendu : 200 {"cache_valide": true|false}
```

### D — Tests automatisés

```
cd appli
python -m pytest tests/test_v0_14_4_unification_finale.py -v
```

Attendu : 44 passed.

```
python -m pytest -q
```

Attendu : 3496 passed, 5 skipped, 0 failed.

## Récap chantier d'unification rendu PDF (v0.14.1 → v0.14.4)

| Étape | Livraison | Périmètre | Tests cumulés |
|---|---|---|---|
| Renommage | v0.14.1 | `exo` → `exercice` partout | +18 |
| Backend | v0.14.2 | Route /info pour les 5 ateliers, dispatch carte | +18 |
| HTML+pref | v0.14.3 | HTML statique unifié, auto-compile pref | +55 |
| Cleanup | v0.14.4 | Descente AtelierEditeur, suppressions, spinner | +44 |

**Résultat final** :
- 1 seule classe (`AtelierEditeur`) pour le rendu PDF des 5 ateliers
- 1 seul endpoint unifié (`/api/atomes/<type>/<id>/...`)
- 1 seul mécanisme (HTML statique + héritage + spinner)
- 0 fonction globale `rendreAtome*`
- 0 alias `/api/cartes/<id>/rendu-*`

## Workstream v0.14 — état d'avancement

Le préfixe v0.14 a été ouvert pour le **cleanup général** (cf. roadmap).
Le sous-workstream « Unification rendu PDF » se termine ici avec v0.14.4.

Autres sous-workstreams **encore ouverts** dans v0.14 :
- **Migration v1→v2 + suppression v1** : retirer la table `objectifs`
  (v1) du schéma, après réécriture des 5+ fichiers de service qui la
  lisent encore. Documenté dans v0.13.7.6.1.1. À planifier comme un
  chantier dédié.
- **Refactor admin** : extension de `purger_fiches.py` à d'autres types,
  intégration des diagnostics d'atomes orphelins (v0.10.7) dans l'UI
  admin.
- **Nettoyage divers** : `atelier_atome_generique.js` legacy, table
  `exercice_objectifs` (avec `services/edition_progression.py`, JS
  `ATL_OBJ_CAT`, route `/api/objectifs`, table `objectifs`), suppression
  des stubs `atelier_atomique.js` / `rendu_atome.js`.

À traiter dans des livraisons v0.14.5+ ou v0.15.
