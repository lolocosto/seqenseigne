# Redémarrage v0.15.1 — Cleanup atelier Ateliers : OO restauré + 3 ateliers supprimés + module manquant chargé

## Contexte

Après v0.15.0.2.a (restauration des onglets Référentiel), tests
fonctionnels chez Laurent : l'atelier Évaluation fonctionne, le
panneau « Documents à publier » du Référentiel est revenu. **Mais**
en testant la compilation du livret de corrigés d'exos depuis ce
panneau, Laurent constate une erreur :

> Module compilation_erreurs.js non chargé.

Diagnostic immédiat : le fichier `static/compilation_erreurs.js`
(16 ko, 330 lignes) existe sur disque depuis v0.13.6.5.1.1 mais n'est
**jamais** chargé par `index.html` via un `<script>`. La fonction
`compErreursAfficher` qu'il expose est appelée par
`atelier_referentiel.js` sans précaution, qui a juste un fallback
« Module non chargé ». Régression silencieuse classique : code prêt,
fichier sur disque, mais oubli du `<script>` dans le template.

À cette occasion, plusieurs autres chantiers se sont précisés et
ont été regroupés dans cette livraison :
- Suppression définitive des 3 ateliers obsolètes Récap cours,
  Récap exos, Plans de travail (remplacés par le Référentiel >
  Documents à publier qui les couvre tous via les types
  `livret_cours`, `livret_exercices`, `livret_plans`).
- Renommage du bouton « Ateliers » du bandeau supérieur en
  « Conception de référentiel », en prévision d'un futur bouton
  « Ateliers » côté Suivi de classe.
- **Surtout** : correction d'une **régression involontaire de
  v0.15.0.2.a** qui avait écrasé le `index.html` v0.15 par une
  version basée sur v0.14.8, supprimant les `<script>` pour
  `atelier_assemblage.js` et `atelier_evaluation_oo.js`. L'atelier
  Évaluation fonctionnait encore chez Laurent uniquement parce que
  l'ancien `static/atelier_evaluation.js` (filet de sécurité B1=γ)
  était toujours chargé. Toute la migration OO de v0.15 était de
  facto annulée.

## Périmètre — Chantiers F0+F1+F2+F5

| # | Chantier | Description |
|---|---|---|
| **F0** | Restauration des scripts OO Évaluation | Recharger `atelier_assemblage.js` et `atelier_evaluation_oo.js`, supprimer définitivement `atelier_evaluation.js` (ancien). Restaure ce que v0.15.0.2.a avait perdu. |
| **F1** | Charger `compilation_erreurs.js` | Ajout du `<script>` manquant dans index.html, AVANT `atelier_referentiel.js` qui l'appelle. |
| **F2** | Supprimer Récap cours / Récap exos / Plans de travail | 3 fichiers JS supprimés + 3 routes backend supprimées + 3 panneaux HTML supprimés + 3 boutons d'onglets supprimés + nettoyage `ATL_INITS` / `ATL_PORTEES` dans app.js + nettoyage imports/registres dans app.py. Les services Python sous-jacents (`services/livret_recap_*.py`, `services/livret_plans_de_travail.py`) sont CONSERVÉS car réutilisés par `referentiels.py`, `orchestrateur_compilation.py`, `livret_sequence.py`, `livret_fiches.py` et `latex_rendu_atome.py`. |
| **F5** | Renommer « Ateliers » → « Conception de référentiel » | Texte du bouton dans le bandeau supérieur. L'attribut `data-tab="ateliers"` reste inchangé (identifiant interne lu par app.js). |

| # | Reporté | Raison |
|---|---|---|
| **F4** | Déplacement de l'atelier Séquence de portée Séquence à portée Niveau | Nécessite changement architectural important (sidebar pluriel des séquences-dans-niveau). Plus pertinent à coupler avec la migration OO Livret. Programmé en v0.15.2. |

## Cadrage validé (G1-G3)

| Question | Réponse |
|---|---|
| G1 — Suppression des routes backend de Recap/Plans | (a) Oui, en même temps que le frontend |
| G2 — Tests garde-fou | (a) Ciblés sur les fichiers concernés en v0.15.1 |
| G3 — Suppression effective des fichiers JS | (a) Oui, propre et net |
| F4 — Déplacement Séquence portée Niveau | Reporté à v0.15.2 conjointement avec la migration OO Livret |

## Ce qui change

### 1. Refonte du bloc `<script>` dans `index.html`

```html
<!-- AVANT (v0.15.0.2.a — état réel chez Laurent) -->
<script src="/static/atelier_recapcours.js"></script>
<script src="/static/atelier_recapexos.js"></script>
<script src="/static/atelier_plansdetravail.js"></script>
<script src="/static/atelier_evaluation.js"></script>            <!-- ancien procédural -->
...
<script src="/static/atelier_editeur.js"></script>
...
<script src="/static/atelier_referentiel.js"></script>

<!-- APRÈS (v0.15.1) -->
<!-- 3 scripts Recap/Plans : SUPPRIMÉS -->
<!-- 1 script atelier_evaluation.js (ancien) : SUPPRIMÉ -->
...
<script src="/static/atelier_editeur.js"></script>
<script src="/static/atelier_assemblage.js"></script>           <!-- AJOUTÉ -->
<script src="/static/atelier_carte_automatisme.js"></script>
<script src="/static/atelier_notion.js"></script>
<script src="/static/atelier_methode.js"></script>
<script src="/static/atelier_fiche.js"></script>
<script src="/static/atelier_exercice.js"></script>
<script src="/static/atelier_evaluation_oo.js"></script>        <!-- AJOUTÉ -->
<script src="/static/compilation_erreurs.js"></script>          <!-- AJOUTÉ -->
<script src="/static/atelier_referentiel.js"></script>
```

L'ordre respecte les dépendances : `Atelier` → `AtelierEditeur` →
`AtelierAssemblage` → `AtelierEvaluation` (chaîne d'héritage OO),
puis `compilation_erreurs.js` avant `atelier_referentiel.js` (qui
l'utilise).

### 2. Suppression des 3 panneaux HTML

Lignes 1607-1783 de l'ancien `index.html` (177 lignes HTML)
remplacées par un commentaire explicatif de 12 lignes. Les `id`
des panneaux supprimés : `#atl-recapcours`, `#atl-recapexos`,
`#atl-plantravail`.

### 3. Suppression des 3 boutons d'onglets

Lignes 465-467 de l'ancien `index.html` (boutons `#atl-btn-recapcours`,
`#atl-btn-recapexos`, `#atl-btn-plantravail`) supprimées. La portée
Niveau ne contient plus que les boutons `Évaluation` et `Référentiel`.

### 4. Renommage du bouton « Ateliers »

```html
<!-- AVANT -->
<button class="tab" data-tab="ateliers">Ateliers</button>

<!-- APRÈS -->
<button class="tab" data-tab="ateliers">Conception de référentiel</button>
```

L'attribut `data-tab="ateliers"` est conservé (utilisé par app.js
lignes 105 et 5577) — seul le label visible change. Cela prépare
l'introduction d'un futur bouton « Ateliers » dans la partie
Suivi de classe.

### 5. Nettoyage `app.js`

- `ATL_INITS` (ligne 2323) : suppression des 3 entrées
  `recapcours`, `recapexos`, `plantravail`.
- `ATL_PORTEES.niveau.ateliers` (ligne 1798) : ne contient plus que
  `['evaluation', 'referentiel']`.
- 4 commentaires obsolètes mis à jour.

### 6. Nettoyage `app.py`

- Suppression des `import` `bp_recap_cours`, `bp_recap_exos`,
  `bp_plans_de_travail`.
- Suppression de ces 3 blueprints du tuple d'enregistrement.

### 7. Suppression effective de fichiers

```
appli/static/atelier_recapcours.js          (225 lignes)
appli/static/atelier_recapexos.js           (203 lignes)
appli/static/atelier_plansdetravail.js      (209 lignes)
appli/static/atelier_evaluation.js          (1235 lignes — ancien procédural)
appli/routes/recap_cours.py                 (176 lignes)
appli/routes/recap_exos.py                  (165 lignes)
appli/routes/plans_de_travail.py            (315 lignes)
```

Total : **7 fichiers, ~2528 lignes** supprimées en net.

### 8. Adaptation des tests

`tests/test_v0_12_1_livret_plans_de_travail.py` :
- Suppression de `TestRouteTex` (2 tests) — testait `/api/plans-de-travail/<niveau>/{tex,pdf}`.
- Suppression de `TestRoutePdf` (1 test).
- Suppression de `TestRouteScopeSequence` (4 tests) — testait `/api/plans-de-travail/<niveau>/<seq>/{tex,pdf}`.
- Le reste du fichier (tests du service `livret_plans_de_travail`,
  ~26 tests) est conservé — le service Python reste utilisé.

### 9. Garde-fous v0.15.1 — nouveau fichier de test

`tests/test_v0_15_1_chantiers.py` : 30 nouveaux tests qui parsent
`index.html`, `app.js` et `app.py` pour vérifier la conformité de
F0, F1, F2 et F5. Organisés en 4 classes :

- **`TestF0ScriptsOOEvaluation`** (4 tests) : présence
  d'`atelier_assemblage.js` et `atelier_evaluation_oo.js`, absence
  de l'ancien `atelier_evaluation.js`, ordre correct de la chaîne
  d'héritage OO.
- **`TestF1CompilationErreurs`** (3 tests) : fichier présent sur
  disque, `<script>` dans HTML, chargé avant `atelier_referentiel.js`.
- **`TestF2SuppressionRecapPlans`** (20 tests) : 3 fichiers JS
  absents, 3 routes backend absentes, 3 services Python conservés,
  3 `<script>` absents, 3 panneaux HTML absents, 3 boutons d'onglets
  absents, nettoyage `ATL_INITS`, `ATL_PORTEES.niveau`,
  imports et blueprints d'app.py.
- **`TestF5RenommageBandeau`** (3 tests) : nouveau label présent,
  ancien label absent du bouton du bandeau, `data-tab="ateliers"`
  inchangé.

## Vérifs

- **Suite Python complète** : **3422 passed, 6 skipped, 0 failed**
  (était 3399 ; +30 nouveaux tests, -7 tests des routes HTTP
  supprimées = +23 ; 3399 + 23 = 3422 ✓)
- **Tests garde-fou v0.15.1** : 30/30 passent
- **Sanity Python** sur `app.py` modifié : OK
- **Aucune référence orpheline** à `recapcours`/`recapexos`/`plantravail`
  dans le code actif (recherche grep confirmée).

## Fichiers livrés

### Modifiés

```
appli/templates/index.html         (suppressions + restauration OO + compilation_erreurs)
appli/static/app.js                (nettoyage ATL_INITS, ATL_PORTEES, commentaires)
appli/static/atelier_filtres_hook.js  (1 commentaire nettoyé)
appli/app.py                       (imports + blueprints)
appli/tests/test_v0_12_1_livret_plans_de_travail.py  (-7 tests des routes)
appli/doc/DETTE_TECHNIQUE.md       (dettes résolues déplacées dans Historique)
```

### Nouveaux

```
appli/tests/test_v0_15_1_chantiers.py    (30 garde-fous F0+F1+F2+F5)
appli/doc/redemarrage_v0_15_1.md         (cette note)
```

### Présents dans le ZIP par sécurité (déjà chez Laurent depuis v0.15)

```
appli/static/atelier.js                 (commentaire de tête mis à jour en v0.15)
appli/static/atelier_editeur.js         (commentaire de tête mis à jour en v0.15)
appli/static/atelier_assemblage.js      (classe parente OO créée en v0.15)
appli/static/atelier_evaluation_oo.js   (sous-classe OO créée en v0.15)
```

Ces 4 fichiers sont inclus dans le ZIP **par sécurité** : si jamais
le déploiement chez Laurent perd à nouveau l'état post-v0.15
(comme c'est arrivé en v0.15.0.2.a), le ZIP v0.15.1 le restitue.

### À supprimer à la main avant décompression (cf. MANIFEST_SUPPRESSIONS.md)

```
appli/static/atelier_recapcours.js
appli/static/atelier_recapexos.js
appli/static/atelier_plansdetravail.js
appli/static/atelier_evaluation.js
appli/routes/recap_cours.py
appli/routes/recap_exos.py
appli/routes/plans_de_travail.py
```

## Procédure d'application

### 1. Sauvegarde de la BDD (par habitude)

```powershell
cd D:\Enseignement\seqenseigne\appli\data
copy seqenseigne.db seqenseigne.db.avant_v0_15_1
```

### 2. Suppressions manuelles AVANT décompression

Cf. `MANIFEST_SUPPRESSIONS.md`. 7 fichiers à supprimer à la main.
Sans cela, ils restent sur disque (sans causer de bug, mais ils
pollueront `appli_inventaire.txt` et tu auras des fichiers morts).

### 3. Décompression du ZIP v0.15.1 à la racine `seqenseigne/`

Aucun fichier à supprimer côté projet (les suppressions sont
les 7 ci-dessus, à faire avant).

### 4. Vérifier l'intégrité

```powershell
.\outils\python\python.exe appli\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
```

### 5. Lancer la suite de tests

```
cd appli
python -m pytest -q
```

Attendu : `3422 passed, 6 skipped, 0 failed`.

### 6. Lancer l'app

```
lancer.bat
```

### 7. Tests fonctionnels manuels

Ordre recommandé :

#### a) Atelier Évaluation (vérifier que v0.15 OO est bien remontée)

Aller sur **Conception de référentiel** > onglet **Évaluation** :
- Sélectionner un niveau → la sidebar d'évaluations apparaît.
- Cliquer une éval existante ou « + Créer ».
- Vérifier : titre éditable, mode de notation, sélecteur exos
  (avec séquence puis exo), sélecteur objectifs, matrice de
  couverture, badge état, bouton « Valider »/« Repasser en
  cours », compilation PDF.
- Si tout fonctionne comme avant la livraison : v0.15 OO est
  remontée correctement.

Dans la console DevTools tu peux vérifier la chaîne d'héritage :
```javascript
window.ATELIER_EVALUATION.constructor.name
// → "AtelierEvaluation"

window.ATELIER_EVALUATION instanceof AtelierAssemblage
// → true
```

#### b) Référentiel — Documents à publier (vérifier F1)

Aller sur **Conception de référentiel** > onglet **Référentiel** :
- Sélectionner un niveau, sélectionner un référentiel.
- Cliquer « Documents à publier ».
- Cliquer « Tester » sur un type de document, par ex. « Livret
  des corrigés d'exos ». Si la compilation réussit : OK.
- Si elle échoue (LaTeX) : tu dois maintenant voir la liste des
  erreurs LaTeX avec cibles cliquables (au lieu du message
  « Module compilation_erreurs.js non chargé »).

#### c) Bandeau supérieur (vérifier F5)

Le bouton du bandeau doit afficher **« Conception de référentiel »**
(au lieu d'« Ateliers »).

#### d) Atelier Niveau (vérifier F2)

Sélectionner la portée Niveau dans la barre verticale de gauche :
- Tu dois voir UNIQUEMENT les boutons **« Évaluation »** et
  **« Référentiel »**.
- Les anciens boutons « Récap cours », « Récap exos » et
  « Plans de travail » ont disparu.

#### e) Vérifier que les services métiers fonctionnent encore

Aller sur **Conception de référentiel** > **Référentiel** >
**Documents à publier**, et compiler un document de type
`livret_cours`, `livret_exercices` ou `livret_plans` (qui
utilisent les services Python correspondants). Si la compilation
réussit, c'est que les services Python sont toujours actifs malgré
la suppression des routes HTTP.

## Prochaine étape — v0.15.2

**Objectif** : migration de l'atelier Livret (Séquence-niveau) vers
le modèle OO (AtelierLivret extends AtelierAssemblage), couplée
avec :

- F4 : déplacement de portée Séquence à portée Niveau (avec sidebar
  pluriel listant les séquences d'un niveau).
- Suppression du cadre « Éléments à inclure » côté Séquence-niveau
  (décision E1 : la compilation force « tout inclus »).
- Adaptation de la route `/api/v2/livret-sequence/.../rendu-pdf`
  pour ne plus accepter d'options dans le body (décision E2).

Périmètre : gros chantier (atelier_seqniv_assemblage.js fait
2642 lignes en style IIFE non-OO). À cadrer sérieusement en début
de session.

## Dette technique

### Résolue en v0.15.1

- ✅ `static/atelier_evaluation.js` (cohabitation v0.15) — supprimé
- ✅ `compilation_erreurs.js` non chargé — corrigé

### Restante

Cf. `appli/doc/DETTE_TECHNIQUE.md`. Notamment :

- `objectifs_v2` (à supprimer une fois usage stabilisé)
- `ATL_ATOME_CONFIG is not defined` dans `app.js:2589`
- Couverture HTML générale pour les autres ateliers (40 garde-fous
  cumulés v0.15.0.2.a + v0.15.1, reste à étendre)
- Maintenir un état de référence d'index.html entre sessions (nouveau
  protocole : Laurent transmet son index.html à chaque session ou
  avant chaque livraison HTML)
