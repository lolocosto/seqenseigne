# Cadrage — Étape 2 : Consolidation de la base (v0.16.2)

> **Statut** : cadrage à valider avant codage. Découpage décidé : **2a** puis
> **2b**, deux livraisons.
>
> **Objectif** : faire converger `AtelierEvaluation` sur la base
> `AtelierEditeur`/`AtelierAssemblage` (réutiliser au lieu de dupliquer), puis
> introduire le régime de persistance mixte.

## 0. Rappel de la hiérarchie et du helper central

```
Atelier            ($(suffixe) = getElementById(this.prefixe + '-' + suffixe))
 └── AtelierEditeur (compilerRendu, _afficherErreurCompilation, toggleTexBrut,
      │              _afficherPdfDansViewer, cycle modifie/snapshot, majToolbar,
      │              garde-sortie…)  — utilise this.$('pdf-iframe') etc.
      └── AtelierAssemblage (estPluriel, persistanceImmediate, ajouter/retirer/
           │                 deplacerElement, rendreContenuPrincipal)
           └── AtelierEvaluation (prefixe='atl-eval')
```

Le helper `this.$('xxx')` résout `atl-eval-xxx`. **Toute la convergence repose
sur ce mécanisme** : si les IDs du template suivent `atl-eval-<suffixe>` avec
les suffixes attendus par la base, l'évaluation hérite des méthodes sans les
redéfinir.

## 1. Découvertes d'audit (v0.16.2, à l'ouverture du chantier)

- **`endpointRenduPdf` (risque n°1) : RÉSOLU.** L'éval appelle aujourd'hui
  `/api/evaluations/<id>/rendu-pdf`. La base construit
  `${endpointRenduPdf}/${id}/rendu-pdf`. Il suffit de configurer
  `endpointRenduPdf: '/api/evaluations'` → URL identique. Aucun changement
  backend pour le rendu.
- **`compilerRendu`/`_afficherErreurCompilation` de l'éval = copie de la base**
  avec IDs en dur + ancien `iframe.src = url` (pas le viewer). Aucune logique
  métier spécifique → remontée sûre. Bonus : l'éval gagne le viewer pdf.js.
- **Pas de `<form id="atl-eval-form">` dans le template** (confirmé : n'existe
  que dans un commentaire JS). C'est pourquoi l'éval redéfinit `modifie` avec un
  flag manuel. **Conséquence sur le découpage** : 2a (rendu PDF + IDs) ne dépend
  PAS du form → faisable maintenant. 2b (snapshot/régime mixte) devra **ajouter
  un `<form id="atl-eval-form">`** englobant les champs → changement de structure
  HTML, isolé dans 2b. Le découpage 2a/2b tombe donc juste.

## 2a — Alignement des IDs + remontée des méthodes (livraison 1)

**But** : supprimer la duplication, SANS changer le comportement utilisateur.

### 2a.1 Diagnostic des IDs

L'évaluation adresse ses éléments par `getElementById('atl-eval-xxx')` (47
occurrences) au lieu de `this.$('xxx')`. La plupart des IDs correspondent déjà
aux suffixes attendus par la base. Divergences à réconcilier :

| Attendu par la base (`this.$`) | État dans l'évaluation | Action |
|---|---|---|
| `pdf-iframe` | template a `rendu-iframe` (+ un `pdf-iframe` héritée inutilisée ?) | Renommer l'iframe du template en `atl-eval-pdf-iframe` ; supprimer le doublon |
| `rendu-status` | `rendu-message` | Renommer en `atl-eval-rendu-status` (ou ajouter alias) |
| `rendu-loading` | absent (spinner via `rendu-message`) | Ajouter un élément `atl-eval-rendu-loading` |
| `rendu-placeholder` | absent | Ajouter `atl-eval-rendu-placeholder` |
| `rendu-erreur` | `erreurs-validation` (sémantique ≠) | **Distinguer** : `rendu-erreur` = erreurs de COMPILATION (base) ; `erreurs-validation` = erreurs de VALIDATION métier (spécifique éval, conservé) |
| `rendu-tex`, `rendu-tex-label` | présents | OK |
| `btn-compiler/-save/-suppr/-valider/-latex` | présents | OK (passer à `this.$`) |
| `badge-modifie`, `etat-badge`, `toolbar-title` | présents | OK |
| `tab-btn-edition/-rendu`, `form`, `list` | présents | OK |
| `selection-toolbar` | géré autrement | À vérifier (peut rester spécifique) |

Suffixes **spécifiques à l'éval** (à garder tels quels, hors convention base) :
`add-exo-btn/-id/-seq`, `add-obj-id`, `afficher-bareme`, `couverture-zone/-cadre`,
`empty`, `erreurs-validation`, `exos-liste`, `langue-points`, `mode`,
`objs-liste`, `tab-edition/-rendu`, `tabs`, `titre`.

### 2a.2 Méthodes à remonter / cesser de dupliquer

L'évaluation réimplémente, avec des IDs en dur, ce que la base fait déjà via
`this.$`. Une fois les IDs alignés, **supprimer les versions de l'évaluation**
et hériter :

| Méthode dupliquée dans l'éval | Action |
|---|---|
| `compilerRendu` | Supprimer → hériter d'`AtelierEditeur`. Bénéfice : l'éval passe au **viewer pdf.js** (v0.16) gratuitement. |
| `_afficherErreurCompilation` | Supprimer → hériter. (Distinct de l'affichage des erreurs de *validation* métier, qui reste.) |
| `toggleTexBrut`, `_afficherTexBrut`, `scrollToLigneTex`/`scrollVersLigneTex`, `voirLatex` | Supprimer → hériter. Attention au renommage `scrollToLigneTex` (éval) vs `scrollVersLigneTex` (base) : aligner sur le nom de la base. |
| `_api`, `_toast`, `_esc` | Vérifier s'ils existent dans la base/un util commun ; sinon les y remonter. |
| `marquerModifie`, `basculerValidation`, `basculerOnglet` | Vérifier équivalence puis hériter. |

### 2a.3 Endpoints

L'éval a `endpointBase='/api/evaluations'`. La base utilise
`this.config.endpointRenduPdf` pour le rendu. **Vérifier** que l'éval configure
bien `endpointRenduPdf` (ou que la base le dérive d'`endpointBase`), sinon le
`compilerRendu` hérité taperait la mauvaise URL. Point critique de 2a.

### 2a.4 Critère de fin 2a

- Aucun `getElementById('atl-eval-…')` résiduel pour les éléments couverts par
  `this.$`.
- Les méthodes dupliquées supprimées de `AtelierEvaluation`.
- Comportement utilisateur **identique** (sauf bonus : rendu PDF via viewer).
- Zéro régression pytest. Test ajouté : vérifier que l'éval n'a plus de
  `compilerRendu`/`_afficherErreurCompilation` propres (hérite bien).

## 2b — Régime de persistance mixte (livraison 2)

**But** : introduire le double régime décidé (cf.
`cadrage_unification_ateliers_assemblage.md` §5ter).

| Nature | Régime | Comportement |
|---|---|---|
| Champ de saisie (titre, mode, afficher-barème, langue-points, **barème par exo**, à terme nb séances/critères côté seqniv) | Snapshot | Badge « modifié » + bouton Enregistrer actif + garde-sortie |
| Opération de structure (ajout/retrait/réordo d'exo ou d'objectif) | Immédiat | PATCH atomique, pas de badge |

### 2b.1 Mécanisme (s'appuie sur la base)

`AtelierEditeur` a déjà : `modifie` (getter basé sur snapshot de
`collecterFormulaire()`), `majToolbar()`, garde-sortie. Il suffit que l'éval :
1. **implémente `collecterFormulaire()`** retournant l'état des champs
   (titre, mode, afficher_bareme, item_langue_francaise, et le barème de chaque
   exo). C'est la signature comparée au snapshot.
2. **câble les `oninput`/`onchange`** des champs sur le mécanisme de la base
   (formChange/marquerModifie) au lieu d'un PATCH immédiat.
3. **garde les opérations de structure en PATCH immédiat** (ajouter/retirer/
   réordonner restent hors `collecterFormulaire`).
4. **`sauvegarder()`** envoie en un PATCH l'ensemble des champs (y compris les
   barèmes modifiés).

### 2b.2 Conséquence sur le barème (décidée)

`sauverBareme` (PATCH immédiat actuel) est **supprimé** au profit du cycle
snapshot : la frappe d'un barème marque modifié ; la persistance se fait à
l'Enregistrer. Le barème entre donc dans `collecterFormulaire()`.

→ ❓ **Point à valider** : le barème est une propriété *par exo* (potentiellement
   plusieurs dizaines d'exos). `collecterFormulaire()` doit sérialiser tous les
   barèmes. À confirmer : un seul Enregistrer pousse-t-il tous les barèmes
   modifiés en un PATCH groupé, ou un PATCH par exo modifié ? (Le backend a
   `PATCH .../exos/<id>` par exo ; un endpoint groupé n'existe pas aujourd'hui.)
   Option simple : à l'Enregistrer, itérer les exos dont le barème a changé et
   faire un PATCH chacun. Option propre : ajouter un endpoint barèmes groupé.

### 2b.3 Distinction garde-sortie

La garde ne se déclenche que pour les **champs** non enregistrés. Les opérations
de structure étant déjà persistées, elles ne doivent pas déclencher la garde.
Comme `modifie` repose sur le snapshot des champs (pas sur la structure), c'est
naturellement le cas — à vérifier par test.

### 2b.4 Critère de fin 2b

- Modifier un champ (dont un barème) → badge + bouton save actif + garde.
- Ajouter/retirer/réordonner → sauvé immédiatement, pas de badge.
- Quitter avec un champ non enregistré → confirmation ; quitter après une
  opération de structure seule → pas de confirmation.
- Zéro régression. Tests sur `collecterFormulaire` et le double régime.

## 3. Risques & vigilance

- **`endpointRenduPdf`** (2a.3) : si mal configuré, le `compilerRendu` hérité
  casse le rendu. À traiter en premier dans 2a.
- **Doublon d'iframe** (`pdf-iframe` vs `rendu-iframe`) : s'assurer qu'on n'en
  laisse qu'une, branchée sur le viewer.
- **Pas de tests JS** : 2a/2b sont du JS pur. Validation visuelle + tests HTTP
  backend. Les tests JS (Vitest) restent prévus à l'étape 4 (DnD). Pour 2a/2b,
  on s'appuie sur des tests Python « structurels » (absence de méthodes
  dupliquées, IDs présents dans le template) + la validation manuelle de Laurent.
- **Barèmes groupés** (2b.2) : décision à prendre (PATCH par exo vs endpoint
  groupé).

## 4. Questions ouvertes pour Laurent — DÉCISIONS

1. **Barème à l'Enregistrer** (2b.2) → **endpoint barèmes groupés** : on ajoute
   une route backend `PATCH .../exos/baremes` (ou équivalent) qui reçoit tous
   les barèmes modifiés en un appel. Plus propre qu'un PATCH par exo.
2. **`rendu-status` vs `rendu-message`** → **renommer** le template (cohérence,
   pas d'alias). Idem pour les autres divergences d'IDs.
3. **Ordre des livraisons** → **2a livrée et validée séparément, puis 2b**.
   v0.16.2 = 2a ; v0.16.3 = 2b.
