# Redémarrage v0.14.3 — HTML statique + auto-compile (étape 3/4)

## Position dans le workstream unification

| | Statut |
|---|---|
| **v0.14.1** : Renommage `exo` → `exercice` | ✓ Déployé |
| **v0.14.2** : Backend unifié (route /info, dispatch carte) | ✓ Déployé |
| **v0.14.3** : HTML statique + auto-compile (cette livraison) | ⏳ |
| **v0.14.4** : Descente dans AtelierEditeur + suppressions + spinner | À venir |

## Cadrage validé

| Question | Réponse |
|---|---|
| Périmètre v0.14.3 | HTML statique + adaptation client + préférence (pas de no-op intermédiaire) |
| Stockage de la préférence | localStorage (par PC, cohérent avec pref-mode-split) |
| Valeur par défaut | Cochée (auto-compile = comportement de base) |
| Définition « atome périmé » | `cache_valide=false` via hash (route /info de v0.14.2) |
| Périmètre de la préférence | 5 ateliers |
| Sauvegarde silencieuse avant compilation | Activée pour les 5 ateliers (uniformisation vers le haut) |

## Architecture v0.14.3

### Avant (état v0.14.2)

```
Carte    : HTML statique #atl-carte-* | AtelierAtomique.compilerRendu | /api/cartes/<id>/rendu-pdf
Exercice : <div vide>                 | rendu_atome.js (innerHTML)    | /api/atomes/exercice/<id>/rendu-pdf
Notion   : <div vide>                 | rendu_atome.js (innerHTML)    | /api/atomes/notion/<id>/rendu-pdf
Methode  : <div vide>                 | rendu_atome.js (innerHTML)    | /api/atomes/methode/<id>/rendu-pdf
Fiche    : <div vide>                 | rendu_atome.js (innerHTML)    | /api/atomes/fiche/<id>/rendu-pdf
```

### Après (état v0.14.3)

```
Carte    : HTML statique #atl-carte-*    | AtelierAtomique.compilerRendu | /api/cartes/<id>/rendu-pdf
Exercice : HTML statique #atl-exercice-* | AtelierAtomique.compilerRendu | /api/atomes/exercice/<id>/rendu-pdf
Notion   : HTML statique #atl-notion-*   | AtelierAtomique.compilerRendu | /api/atomes/notion/<id>/rendu-pdf
Methode  : HTML statique #atl-methode-*  | AtelierAtomique.compilerRendu | /api/atomes/methode/<id>/rendu-pdf
Fiche    : HTML statique #atl-fiche-*    | AtelierAtomique.compilerRendu | /api/atomes/fiche/<id>/rendu-pdf

+ Préférence localStorage : auto-compile si cache invalide
+ Sauvegarde silencieuse avant compilation (5 ateliers)
+ rendu_atome.js marqué obsolète (suppression v0.14.4)
```

**100% des 5 ateliers utilisent maintenant le même mécanisme** côté
client. Reste à descendre la logique de AtelierAtomique vers AtelierEditeur
en v0.14.4 (et supprimer AtelierAtomique).

## Modifications

### 1. HTML statique pour les 4 ateliers

Avant, dans `index.html`, les 4 ateliers exercice/notion/methode/fiche
avaient juste :

```html
<div id="atl-exercice-rendu" style="display:none;flex:1;..."></div>
```

`rendu_atome.js` peuplait ce conteneur par `innerHTML` à chaque appel à
`rendreAtomeTab(type)`.

Maintenant, le bloc est statique et identique à celui de la carte :

```html
<div id="atl-exercice-rendu" style="display:none;...">
  <div style="...toolbar..."> <!-- bouton Compiler + status --> </div>
  <iframe id="atl-exercice-pdf-iframe" ...></iframe>
  <div id="atl-exercice-rendu-erreur" ...></div>
  <div id="atl-exercice-rendu-placeholder" ...></div>
</div>
```

**Matrice DOM 100% remplie** (vérifiée par 30 tests paramétrés) :

| | rendu | pdf-iframe | btn-compiler | rendu-status | rendu-erreur | rendu-placeholder |
|---|---|---|---|---|---|---|
| atl-exercice | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| atl-notion   | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| atl-methode  | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| atl-fiche    | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| atl-carte    | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Les boutons « Compiler le rendu » appellent maintenant
`ATELIER_<TYPE>.compilerRendu()` (héritée de AtelierAtomique).

### 2. Configuration `endpointRenduPdf` dans les 4 ateliers

`AtelierAtomique` gagne une nouvelle config `endpointRenduPdf`,
distincte de `endpointBase` (utilisé pour le CRUD des items).

- Par défaut : `endpointRenduPdf = endpointBase` (rétrocompatible
  pour la carte qui utilise les deux URL via /api/cartes).
- Exercice : `endpointRenduPdf: '/api/atomes/exercice'`
- Notion : `endpointRenduPdf: '/api/atomes/notion'`
- Méthode : `endpointRenduPdf: '/api/atomes/methode'`
- Fiche : `endpointRenduPdf: '/api/atomes/fiche'`

Toutes les routes de rendu (`/info`, `/rendu-pdf`, `/rendu-tex`)
utilisent désormais `endpointRenduPdf` dans `AtelierAtomique`.

### 3. Surcharges `basculerOnglet` supprimées

Les 4 ateliers avaient une surcharge qui appelait
`window.rendreAtomeTab(type)`. Cette surcharge est supprimée :
l'héritage de `AtelierAtomique` (via `AtelierEditeur.basculerOnglet`
→ `verifierCacheEtAfficher`) prend le relais et utilise le HTML
statique nouvellement aligné.

Pour Exercice, un hack DOM supplémentaire (gérer manuellement
l'affichage de `#atl-exercice-rendu` parce que le préfixe court de la
classe pointait vers un id inexistant) disparaît aussi : depuis v0.14.1
le préfixe est `atl-exercice` partout, la parente trouve la zone toute
seule.

### 4. Sauvegarde silencieuse avant compilation

`AtelierEditeur.sauvegarder()` accepte maintenant un paramètre
`options.silencieuse` (booléen, default false) :
- `false` (comportement historique) : toast de succès + rechargement
  de la liste après PUT/POST réussi
- `true` : pas de toast de succès, pas de chargerListe. Les **erreurs**
  sont toujours signalées (la sauvegarde silencieuse ne masque pas
  les problèmes).

La méthode retourne maintenant un booléen (`true` = succès, `false` =
échec). Rétrocompatible avec les appelants historiques qui ignoraient
le retour.

`AtelierAtomique.compilerRendu()` appelle `sauvegarder({silencieuse:
true})` en amont, **sous deux conditions** :
- `this.modifie === true` : éviter un round-trip serveur inutile
  quand l'item n'a pas de modifications en attente (cas le plus
  fréquent quand on navigue dans la liste)
- `!this._chargementAuto` : en mode auto-cache, on lit juste un PDF
  existant, l'état BdD n'a aucune influence

Si la sauvegarde échoue, la compilation est annulée (toast d'erreur
déjà émis par `sauvegarder`, on évite de générer un PDF qui ne
refléterait pas l'intention de l'utilisateur).

### 5. Préférence auto-compile

Nouvelle préférence localStorage `seqenseigne_pref_auto_compile` :
- Clé absente OU `'1'` → préférence active (auto-compile)
- Clé `'0'` → préférence désactivée (placeholder)

Cochée par défaut : par défaut, basculer sur l'onglet Rendu PDF d'un
atome modifié déclenche automatiquement sa compilation au lieu
d'afficher juste le placeholder.

Fonctions exposées sur window :
- `prefAutoCompileEstActive()` : booléen
- `prefAutoCompileToggle()` : appelée par le `onchange` du toggle UI

Toggle HTML dans Préférences > Affichage des ateliers, juste après
le toggle « Mode côte-à-côte ».

`AtelierAtomique.verifierCacheEtAfficher()` consulte cette préférence
quand `cache_valide=false` :
- Si pref active → appelle `compilerRendu()` (en mode
  `_chargementAuto=true` pour cohérence du statut affiché)
- Si pref désactivée → appelle `_remettrePlaceholderRendu()` comme avant

### 6. `prefSplitAppliquer` adapté

Quand on active le mode côte-à-côte, l'ancien code appelait
`rendreAtomeTab(type)` pour les ateliers visibles. Bascule sur le
nouveau mécanisme : `ATELIER_<TYPE>.basculerOnglet('rendu')` qui
déclenche `verifierCacheEtAfficher` (et donc l'auto-compile si la
préférence est active). Ajout aussi de `ATELIER_CARTE` à la liste
des ateliers concernés (pas dans la version v0.13.7.6.1).

### 7. `rendu_atome.js` marqué obsolète

Le fichier reste présent (suppression définitive en v0.14.4) mais son
en-tête indique clairement qu'il n'est plus utilisé. Aucun appel actif
ne référence ses fonctions globales `rendreAtomeTab/Lancer/Toggle/
ScrollTo` :
- Les 4 ateliers ont vu leurs surcharges supprimées
- `prefSplitAppliquer` (app.js) a basculé sur le nouveau mécanisme
- `atelier_evaluation.js` ne contient que des commentaires de référence

## Fichiers livrés

```
MODIFIÉS
  appli/templates/index.html             (4 zones rendu standardisées + toggle pref)
  appli/static/atelier_atomique.js       (endpointRenduPdf + save silencieuse + pref auto-compile)
  appli/static/atelier_editeur.js        (sauvegarder({silencieuse}) + retour bool)
  appli/static/atelier_exercice.js       (endpointRenduPdf + surcharge supprimée)
  appli/static/atelier_notion.js         (idem)
  appli/static/atelier_methode.js        (idem)
  appli/static/atelier_fiche.js          (idem)
  appli/static/app.js                    (pref auto-compile + prefSplitAppliquer adapté)
  appli/static/rendu_atome.js            (marqué obsolète, fonctions intactes pour compat)

NOUVEAUX
  appli/tests/test_v0_14_3_html_unifie_et_auto_compile.py  (55 tests)
  appli/doc/redemarrage_v0_14_3.md                         (ce document)
```

## Vérifs

- pytest : **3451 passed, 5 skipped, 0 failed**
  (3396 baseline v0.14.2 + 55 nouveaux v0.14.3)
- `node --check` sur tous les JS modifiés : OK

## À tester chez toi

### A — Aucune régression (test prioritaire)

1. Déployer le zip et hard reload (Ctrl+Shift+R).
2. Ouvrir chacun des **5 ateliers** :
   - Cliquer un item dans la liste → le formulaire se remplit
   - Basculer sur l'onglet Rendu PDF
   - **Vérifier** : le PDF s'affiche (cache valide) OU le placeholder
     « Cliquez sur Compiler » apparaît OU la compilation se déclenche
     automatiquement (si pref auto-compile active = défaut)
   - Cliquer « Compiler le rendu » manuellement → PDF généré

### B — Nouvelle préférence auto-compile

1. Ouvrir l'onglet **Préférences**.
2. Vérifier la présence du toggle « Compiler automatiquement à
   l'ouverture du Rendu PDF » (juste sous Mode côte-à-côte).
3. **Vérifier** qu'il est coché par défaut au premier déploiement.
4. **Tester** :
   - Décocher → ouvrir l'onglet Rendu d'un atome modifié sans cache
     valide → placeholder visible
   - Recocher → ouvrir l'onglet Rendu d'un autre atome dans la même
     condition → compilation se déclenche automatiquement
5. Recharger la page (F5) → le toggle conserve son état (localStorage
   persistant).

### C — Sauvegarde silencieuse en amont

1. Atelier Exercice. Cliquer un exercice, modifier le titre (le badge
   « ⚠ modifications non enregistrées » apparaît).
2. Basculer sur l'onglet Rendu PDF (sans cliquer Enregistrer).
3. **Vérifier** : la sauvegarde s'opère silencieusement (le badge
   disparaît), puis la compilation se déclenche, puis le PDF
   apparaît avec le nouveau titre.
4. **Pas de toast** « Exercice enregistré. » — c'est le mode silencieux.

### D — Race condition toujours OK

1. Atelier Carte. Cliquer une carte A avec cache → PDF s'affiche.
2. **Aussitôt** cliquer carte B sans cache (ni dans la liste, ni
   double-clic — un clic rapide).
3. **Vérifier** : si pref auto-compile active, B se compile et son
   PDF s'affiche. Si pref désactivée, placeholder de B. Dans les
   deux cas, **jamais le PDF de A ne réapparaît**.
4. Bonus : enchaîner 5 cartes rapidement → l'état final correspond
   à la dernière carte.

### E — Suite automatique

```
cd appli
python -m pytest tests/test_v0_14_3_html_unifie_et_auto_compile.py -v
```

Attendu : 55 passed.

```
python -m pytest -q
```

Attendu : 3451 passed, 5 skipped, 0 failed.

## Prochaine étape : v0.14.4

Dernière étape du workstream cleanup rendu PDF :

1. **Descendre la logique de rendu PDF de `AtelierAtomique` vers
   `AtelierEditeur`** — il n'y a plus de différence comportementale
   entre les deux maintenant que les 5 ateliers utilisent le même
   mécanisme.

2. **Supprimer `AtelierAtomique`** — les 5 ateliers héritent
   directement de `AtelierEditeur`.

3. **Supprimer `rendu_atome.js`** — fichier devenu inutile.

4. **Supprimer les alias `/api/cartes/<id>/...`** côté backend (la
   carte utilisera `/api/atomes/carte/<id>/...` une fois son client
   migré sur la nouvelle URL).

5. **Ajouter le spinner visuel** pendant la compilation (à la place
   du seul texte « Compilation en cours… ») pour les 5 ateliers.
   CSS `.rendu-loading` et `.rendu-spinner` existent déjà.

À la fin de v0.14.4, l'architecture sera :
- 1 seule classe `AtelierEditeur` qui gère tout
- 1 seul endpoint unifié `/api/atomes/<type>/<id>/...` pour les 5
  ateliers
- 1 seul mécanisme de rendu PDF (HTML statique + heritage)
- 1 spinner visuel commun
- 0 fonction globale `rendreAtome*`
- 0 alias `/api/cartes/<id>/...`
