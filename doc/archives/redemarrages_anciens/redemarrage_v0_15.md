# Redémarrage v0.15 — Classe `AtelierAssemblage` + migration `AtelierEvaluation`

## Position dans la roadmap

| Étape | Statut |
|---|---|
| v0.14.7 : Chantier v1 cosmétiquement clos | ✓ Déployé |
| v0.14.8 : Remédiation optionnelle dans l'UI Exercice | ✓ Déployé |
| **v0.15 : Classe `AtelierAssemblage` + migration Évaluation** (cette livraison) | ⏳ |
| v0.15.1 : Migration de l'atelier Livret (`atelier_seqniv_assemblage.js`) | À venir |
| v0.17+ : Atelier Progression (utilisera `AtelierAssemblage`) | Plus loin |

## Cadrage validé (Q1-Q5 + B1-B5)

| Question | Réponse |
|---|---|
| Q1 — Stratégie de bascule | (a) Cohabitation (sur disque) |
| Q2 — Périmètre v0.15 | (b) Classe `AtelierAssemblage` + migration Évaluation |
| Q3 — Wrappers `window.atelEval*` | (a) Gardés pour compat HTML |
| Q4 — Nom de la classe | (a) `AtelierAssemblage` |
| Q5 — Doc commentaires de tête | (a) Mise à jour `atelier.js` + `atelier_editeur.js` |
| B1 — Bascule HTML | (γ) Livrer en une fois, ancien fichier gardé sur disque |
| B2 — Compilation PDF | Pas de placeholder à conserver (déjà opérationnelle) ; on garde la machinerie locale |
| B3 — Tests | Pas de nouveaux tests Python (3389 existants couvrent les routes) |
| B4 — Cible de réduction | Soft (pas de cible mesurable) |
| B5 — Renommer "drag-and-drop" → "composition" dans les commentaires | OK |

## Ce qui change dans cette livraison

### 1. Nouveau fichier `static/atelier_assemblage.js` (192 lignes)

Classe parente des ateliers de **type Assemblage** (par opposition aux
ateliers d'atomes, qui éditent un objet unique via formulaire).

Note sémantique : la dimension « type d'atelier » (Atomique / Assemblage)
décrit la **structure technique JavaScript**. Elle est **indépendante**
de la dimension « portée » (Séquence / Niveau / Cycle), qui décrit la
place dans l'UI et le filtre métier appliqué.

| Atelier | Type | Portée |
|---|---|---|
| Exercice, Notion, Méthode, Fiche, Carte | Atomique | Séquence |
| Évaluation | **Assemblage** | Niveau |
| Livret (séquence d'assemblage) | Assemblage | Séquence |
| Progression (à venir) | Assemblage | Niveau |

`AtelierAssemblage extends AtelierEditeur` et ajoute :

- **Flag `estPluriel`** (config, défaut `true`) : `true` quand un scope
  contient plusieurs items (Évaluation, Progression : sidebar avec liste),
  `false` quand un scope contient un seul item déterminé par les filtres
  (Livret).
- **Flag `persistanceImmediate`** (config, défaut `false`) : `true`
  quand chaque op (ajout/retrait/PATCH champ) persiste atomiquement
  (Livret : drag-drop = PATCH immédiat), `false` quand il y a un bouton
  Enregistrer explicite (Évaluation). En mode immédiat, le getter
  `this.modifie` retourne toujours `false`.
- **Hooks d'action** : `ajouterElement(type, payload)`,
  `retirerElement(type, id)`, `deplacerElement(type, id, delta)`.
  Implémentations vides par défaut, à surcharger.
- **Hook abstrait** : `rendreContenuPrincipal(item)` pour rendre le
  panneau central.

La classe est **volontairement légère** : on ne factorise QUE ce qui est
utile à `AtelierEvaluation` aujourd'hui. Le drag-and-drop, le filtrage
multi-niveau, et la logique de composition spécifique au Livret seront
remontés ici lors de la migration v0.15.1.

### 2. Nouveau fichier `static/atelier_evaluation_oo.js` (1374 lignes)

Remplace l'ancien `static/atelier_evaluation.js` (1235 lignes
historiques avec variables globales `ATL_EVAL_*` et fonctions
`atelEval*`).

`AtelierEvaluation extends AtelierAssemblage` avec :

- **État local** sur l'instance : `this.liste`, `this.itemActif`,
  `this.exos`, `this.objs`, `this.couverture`, `this.exosDispo`,
  `this.objsDispo`, `this.filtreEtat`, `this._modifieFlag`,
  `this.tabCourant`, `this.lignesFautives` (remplacent les variables
  `ATL_EVAL_*`).
- **Méthodes d'instance** pour toutes les anciennes fonctions
  `atelEval*` et `_eval*`.
- **20 wrappers globaux** `window.atelEval*` qui délèguent à l'instance
  unique `window.ATELIER_EVALUATION`. Aucune modification du HTML
  nécessaire — les `onclick="atelEvalXxx()"` dans `index.html`
  continuent de fonctionner exactement comme avant.

### 3. Modifications mineures

#### a) `static/atelier.js` (commentaire de tête réécrit)

Le commentaire de tête datait de v0.13.6.6 et décrivait la hiérarchie
**prévue** (avec `AtelierAtomique` et `AtelierRecap`). Mis à jour
pour refléter la hiérarchie **réelle** au 21 mai 2026, plus l'historique
des principaux jalons (v0.13.6.6 → v0.14.4 → v0.15).

Aucun changement de code.

#### b) `static/atelier_editeur.js` (commentaire de tête mis à jour)

La liste des enfants mentionnait `AtelierAssemblage (composition par
drag-and-drop)` au futur. Mise à jour pour pointer le fichier
`atelier_assemblage.js` désormais existant.

Aucun changement de code.

#### c) `templates/index.html` (ordre des `<script>`)

- L'ancien `<script src="/static/atelier_evaluation.js">` (chargé AVANT
  `atelier.js` et `atelier_editeur.js`, donc incompatible avec un
  héritage OO) est **retiré** de la liste des chargements.
- Le nouveau `<script src="/static/atelier_assemblage.js">` est ajouté
  juste après `atelier_editeur.js`.
- Le nouveau `<script src="/static/atelier_evaluation_oo.js">` est ajouté
  après les 5 atomes (Carte, Notion, Méthode, Fiche, Exercice).
- Commentaires explicatifs étoffés.

### 4. Aucun changement BDD

Pas de migration. Pas de schéma touché. Pas de nouveau test Python.
La suite de tests reste **3389 passed, 6 skipped, 0 failed**.

### 5. Cohabitation : l'ancien fichier reste sur disque

Pour faciliter un éventuel retour arrière en cas de bug constaté en
production locale, `static/atelier_evaluation.js` (ancien fichier
historique) **reste sur disque** mais n'est plus chargé par
`index.html`.

**En cas de bug critique** :
1. Ouvrir `appli/templates/index.html`
2. Retirer la ligne 3243 :
   `<script src="/static/atelier_evaluation_oo.js"></script>`
3. Ajouter dans la zone des scripts d'ateliers historiques
   (vers la ligne 3216, après `atelier_plansdetravail.js`) :
   `<script src="/static/atelier_evaluation.js"></script>`
4. Rafraîchir le navigateur. Le comportement de v0.14.8 est restauré.

Suppression définitive de `atelier_evaluation.js` planifiée en v0.15.0.1
après stabilisation de v0.15 chez toi (généralement 1-2 semaines
d'usage réel).

## Comment c'est structuré côté JS

### Hiérarchie OO (état final v0.15)

```
Atelier
└── AtelierEditeur
    ├── AtelierExercice          (inchangé)
    ├── AtelierNotion            (inchangé)
    ├── AtelierMethode           (inchangé)
    ├── AtelierFiche             (inchangé)
    ├── AtelierCarte             (inchangé)
    └── AtelierAssemblage        (NOUVEAU)
        └── AtelierEvaluation    (NOUVEAU — replace atelier_evaluation.js)
```

### Ordre de chargement dans `index.html`

```
<!-- ateliers historiques non-OO encore présents -->
<script src="atelier_seqniv_assemblage.js"></script>  (à migrer v0.15.1)
<script src="atelier_recapcours.js"></script>
<script src="atelier_recapexos.js"></script>
<script src="atelier_plansdetravail.js"></script>

<!-- chaîne OO -->
<script src="atelier.js"></script>
<script src="atelier_editeur.js"></script>
<script src="atelier_assemblage.js"></script>          (NOUVEAU)
<script src="atelier_carte_automatisme.js"></script>
<script src="atelier_notion.js"></script>
<script src="atelier_methode.js"></script>
<script src="atelier_fiche.js"></script>
<script src="atelier_exercice.js"></script>
<script src="atelier_evaluation_oo.js"></script>       (NOUVEAU)
<script src="atelier_referentiel.js"></script>
```

### Pourquoi pas `this.$('list')` etc. dans `AtelierEvaluation` ?

`AtelierEditeur` fournit des helpers de DOM basés sur la convention
`{prefixe}-suffixe` (ex. `this.$('list')` → `document.getElementById('atl-eval-list')`).
Or l'évaluation utilise déjà ces IDs et c'est compatible — mais le
HTML de l'éval n'a pas TOUS les IDs attendus par `AtelierEditeur`
(notamment dans la zone Rendu PDF : pas de `atl-eval-rendu-status`,
pas de `atl-eval-rendu-placeholder`, pas de `atl-eval-pdf-iframe` —
l'éval a `atl-eval-rendu-message`, `atl-eval-rendu-iframe`,
`atl-eval-rendu-tex`).

Conséquence pratique : la machinerie de compilation héritée de
`AtelierEditeur` (`compilerRendu`, `verifierCacheEtAfficher`,
`_afficherErreurCompilation`, etc.) **n'est pas réutilisable telle
quelle** pour l'éval. On garde donc la machinerie locale de
`atelier_evaluation.js`, portée dans `AtelierEvaluation` sans
changement fonctionnel.

Une éventuelle factorisation viendra plus tard, conjointement à une
refonte du HTML de l'éval pour aligner les IDs (chantier UI
séparé — pas v0.15).

## Fichiers livrés

```
NOUVEAU
  appli/static/atelier_assemblage.js
  appli/static/atelier_evaluation_oo.js
  appli/doc/redemarrage_v0_15.md

MODIFIÉS
  appli/static/atelier.js                  (commentaire de tête)
  appli/static/atelier_editeur.js          (commentaire de tête)
  appli/templates/index.html               (ordre des <script>)

CONSERVÉ SUR DISQUE (mais non chargé)
  appli/static/atelier_evaluation.js       (filet de sécurité B1=γ)
```

## Vérifs

- **Suite Python complète** : 3389 passed, 6 skipped, 0 failed
  (identique à v0.14.8)
- **Sanity JS** : `node --check` OK sur tous les fichiers modifiés
- **Sanity OO** : test d'instanciation hors navigateur (avec stubs
  document/window) :
  - Chaîne d'héritage : `AtelierEvaluation` → `AtelierAssemblage`
    → `AtelierEditeur` → `Atelier` ✓
  - Wrappers `window.atelEval*` : 20/20 présents (couverture
    exhaustive de l'ancien fichier) ✓
  - Mode `persistanceImmediate = true` : `this.modifie` reste toujours
    `false` même après `set modifie = true` ✓

## Procédure d'application

### 1. Décompresser le ZIP dans le répertoire racine `seqenseigne/`

Aucun fichier à supprimer manuellement (l'ancien `atelier_evaluation.js`
reste sur disque comme filet de sécurité).

### 2. Vérifier l'intégrité

```powershell
.\outils\python\python.exe appli\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
```

Attendu : ✅ aucune divergence.

### 3. Lancer la suite de tests Python

```
cd appli
python -m pytest -q
```

Attendu : `3389 passed, 6 skipped, 0 failed`.

### 4. Tests fonctionnels manuels (atelier Évaluation)

À tester sur un niveau qui contient des évaluations existantes (ou en
en créant une) :

#### a) Ouverture de l'atelier

- Sélectionner un niveau, basculer sur l'atelier **Évaluation**.
- La sidebar de gauche doit afficher la liste des évaluations du niveau,
  avec leur badge "Validé" pour celles qui le sont.
- Si pas d'évaluation : message "Aucune évaluation pour ce niveau" +
  bouton "+ Créer" actif.

#### b) Création d'une évaluation

- Cliquer "+ Créer". Une nouvelle évaluation apparaît dans la sidebar
  avec un titre "Nouvelle évaluation".
- Le titre est focus + sélectionné dans le champ d'édition.

#### c) Modification des champs d'en-tête

- Modifier le titre → le badge "modifié" apparaît dans la toolbar.
- Idem mode de notation, case "Afficher le barème", item langue
  française.
- Cliquer "Enregistrer" → toast "Évaluation enregistrée.", badge
  "modifié" disparaît.

#### d) Sélection d'une autre évaluation avec modifs en cours

- Modifier un champ sans enregistrer.
- Cliquer une autre évaluation dans la sidebar.
- Une confirmation "Des modifications non enregistrées seront perdues"
  s'affiche.

#### e) Ajout / retrait d'un exercice

- Dans le cadre "Exercices", sélectionner une séquence → la liste
  d'exos disponibles apparaît.
- Sélectionner un exo, cliquer "Ajouter". L'exo apparaît dans la liste.
- Modifier son barème (Pts ou OK/Partiel/KO pour les QCM). Le PATCH
  est immédiat (pas de bouton Enregistrer).
- Cliquer ↑ ou ↓ → l'exo monte/descend.
- Cliquer ✕ → confirmation puis retrait.

#### f) Ajout / retrait d'un objectif déclaré

- Dans le cadre "Objectifs couverts", sélectionner un objectif dans
  le menu déroulant, cliquer "Ajouter".
- L'objectif apparaît dans la liste et la matrice de couverture se
  met à jour.
- Cliquer ✕ → retrait après confirmation.

#### g) Bascule de validation

- Cliquer "Valider".
- Si OK : passage en état "Validé", badge change, le bouton devient
  "Repasser en cours".
- Si erreur de validation pédagogique (ex : aucun exo, ou barème
  manquant) : bandeau rouge affiche les raisons typées
  ("Aucun exercice attaché", "Exercice N10/S01/F01 : barème en
  points manquant"…). L'évaluation reste en édition (PAS d'écran
  zombi — protection v0.13.5.2.4 conservée).

#### h) Compilation PDF

- Onglet "Rendu PDF" → cliquer "Compiler le rendu".
- Indicateur "Compilation en cours…", puis le PDF s'affiche dans
  l'iframe.
- En cas d'erreur LaTeX (422) : liste cliquable des lignes fautives,
  bouton "Voir le .tex brut" pour inspecter le code.
- Bouton "LaTeX généré" en toolbar pour afficher le .tex dans la
  modale standard.

#### i) Suppression

- Cliquer "Supprimer" → confirmation → l'éval disparaît de la sidebar
  et l'état vide reprend.

#### j) Filtre par état

- Dans la sidebar, cliquer sur "En cours" / "Validé" / "Tous" → la
  liste se filtre côté UI sans re-fetcher le backend.

### 5. Validation de la chaîne d'héritage côté DevTools

Ouvrir la console du navigateur après avoir basculé sur l'atelier
Évaluation :

```javascript
> window.ATELIER_EVALUATION
  AtelierEvaluation {config: {...}, id: "evaluation", prefixe: "atl-eval", ...}

> window.ATELIER_EVALUATION instanceof AtelierAssemblage
  true

> window.ATELIER_EVALUATION instanceof AtelierEditeur
  true

> window.ATELIER_EVALUATION instanceof Atelier
  true

> typeof window.atelEvalInit
  "function"
```

## Métriques

- 1 classe parente créée (`AtelierAssemblage`, 192 lignes)
- 1 sous-classe créée (`AtelierEvaluation`, 1374 lignes — légèrement
  plus que les 1235 originales à cause des wrappers + docstrings,
  cf. décision B4=soft)
- 1 fichier historique conservé sur disque (`atelier_evaluation.js`)
- 0 nouveau test Python (les 3389 existants couvrent les routes
  backend que l'atelier appelle, et la migration JS ne change pas
  les contrats)
- 0 régression : suite Python à 3389 passed, 6 skipped, 0 failed

## Risques connus

### Risque 1 — Pas de tests JS automatisés

Validation manuelle obligatoire de tous les workflows (cf. section 4
ci-dessus). C'est le risque principal — la migration ne change pas
le comportement attendu mais la structure du code change beaucoup.

**Mitigation** : si tu constates un bug, le filet de sécurité
(cohabitation B1=γ) permet de revenir à l'ancien fichier en
2 modifications de `index.html` (cf. § "Cohabitation").

### Risque 2 — Race condition au chargement

L'instance `window.ATELIER_EVALUATION` est créée lors de
l'évaluation du script `atelier_evaluation_oo.js`. Si quelque chose
appelait `window.atelEvalInit` AVANT le chargement du script,
ça planterait avec "atelEvalInit is not a function".

Pas de risque en pratique : `atelEvalInit` est appelée par
`atelInvoquerInit` (dans app.js) qui est elle-même appelée sur clic
utilisateur (basculer d'atelier), donc bien après le chargement
initial.

## Prochaine étape

**v0.15.1 — Migration de l'atelier Livret**
(`static/atelier_seqniv_assemblage.js`, 2642 lignes, IIFE, drag-and-drop
spécifique).

C'est le gros morceau qui ferme la dette historique de la refonte OO.
Une fois ce chantier terminé, tous les ateliers du système seront en OO.
Livraison plus lourde — à scoper à part.

L'ordre suggéré ensuite (sans changement par rapport à v0.14.8) :
- **v0.16** : refactor Préférences en onglets + fusion Thème/Découpage
- **v0.17+** : atelier Progression (utilisera `AtelierAssemblage`)
