# Redémarrage v0.13.7.0d — Garde de sortie : architecture unifiée par la classe parente

## Périmètre

Refonte de la détection « modifié » et de la restauration sur « Ne pas
sauvegarder », **entièrement dans la classe parente `AtelierEditeur`**.
Les sous-classes n'ont plus aucune logique liée au dirty-flag à gérer.

Cette livraison fait suite à v0.13.7.0c, dont les tests en production
ont mis en évidence des comportements résiduels hétérogènes :

- **Carte** : « ne pas sauvegarder » dans la modale sauvegardait
  réellement (effet inverse) ; « sauvegarder » échouait silencieusement.
- **Autres ateliers** : « ne pas sauvegarder » fonctionnait pour la
  garde, mais le DOM gardait les modifs en cours. Au retour dans
  l'atelier, l'utilisateur retrouvait son texte affiché.

La cause racine de ces deux symptômes était la même : **chaque atelier
gérait son propre état de modification et sa propre restauration**, avec
des implémentations légèrement différentes. v0.13.7.0c avait unifié la
modale mais pas le pilotage en amont.

v0.13.7.0d ramène **toute** la logique dans `AtelierEditeur`. Les
sous-classes implémentent juste `collecterFormulaire()` et
`remplirFormulaire()` — ce qu'elles faisaient déjà.

## Nouvelle architecture

### Source de vérité unique : snapshot JSON

Dans `AtelierEditeur` :

```js
this._snapshotForm = null;          // JSON.stringify(collecterFormulaire())
                                     // au dernier état « propre »
this._snapshotInvalide = false;     // si vrai, modifie = true forcé
```

### `this.modifie` devient un getter/setter

```js
get modifie() {
  if (this._snapshotInvalide) return true;
  if (this._snapshotForm === null) return false;
  return JSON.stringify(this.collecterFormulaire()) !== this._snapshotForm;
}

set modifie(val) {
  if (val) {
    this._snapshotInvalide = true;   // force "modifié"
  } else {
    this._snapshotInvalide = false;
    this._snapshotForm = JSON.stringify(this.collecterFormulaire());
  }
  this.majToolbar();
}
```

- `this.modifie` (lecture) retourne `true` ssi la signature actuelle du
  formulaire diffère du snapshot.
- `this.modifie = false` (écriture) **prend un nouveau snapshot** depuis
  l'état actuel du DOM. C'est l'état « propre ».
- `this.modifie = true` (écriture) invalide le snapshot.

L'API préserve la sémantique des assignations historiques
(`this.modifie = false` après `sauvegarder`, etc.).

### Listener délégué unique

Un seul `addEventListener('input' + 'change')` est installé sur le
conteneur `#atl-<prefixe>-form`. À chaque event, il recalcule
`this.modifie` et appelle `majToolbar()` si l'état change. Anti-flicker :
le badge ne se met à jour que si l'état réel change.

L'installation est idempotente (drapeau `_listenerInstalle`).

### `_restaurerForm()` — méthode parent

Appelée par la garde sur « Ne pas sauvegarder » :

```js
_restaurerForm() {
  if (this.itemActif) {
    this.remplirFormulaire(this.itemActif);  // ré-écrit le DOM
    this.modifie = false;                    // reprise du snapshot
  } else {
    this.afficherVide();
    this._snapshotForm = null;
    // ...
  }
}
```

`remplirFormulaire(itemActif)` est ce qui était utilisé pour ouvrir
l'item au départ. En l'appelant à nouveau, on **réécrit** le DOM avec
les valeurs initiales (celles de la BdD). Les modifs en cours
disparaissent visuellement. C'est exactement le comportement attendu.

### Conséquence sur les sous-classes

**Rien à faire dans les sous-classes.** Plus de `oninput` dans le HTML.
Plus de `formChange()` à câbler. Les méthodes `formChange()` existantes
peuvent rester (elles ne nuisent pas), `marquerModifie()` et
`marquerEnregistre()` aussi.

## Bugs corrigés

### Bug 1 — Carte : « Ne pas sauvegarder » sauvegardait

**Cause supposée** (non confirmée formellement, le diagnostic
v0.13.7.0c utilisait `a.ref.modifie = false` + `majToolbar()` sans
restauration DOM) : la carte avait un mécanisme propre, mais
v0.13.7.0c forçait `modifie = false` sur l'instance. Comme `set
itemActif` posait `window.ATL_CARTE_ACTIF`, et que d'autres hooks
écoutaient... il y avait peut-être une cascade involontaire.

**Fix v0.13.7.0d** : avec la nouvelle architecture, le chemin "ignorer"
appelle `_restaurerForm()` qui appelle `remplirFormulaire(itemActif)`,
puis `this.modifie = false`. Aucune cascade vers `sauvegarder()`. Le
comportement est désormais identique entre carte et autres ateliers
(c'est le même code parent qui pilote).

### Bug 2 — Carte : « Sauvegarder » échouait silencieusement

**Cause supposée** : la carte a un `sauvegarder()` qui peut retourner
sans rejeter de Promise (capture des erreurs en interne). La garde
avait du mal à détecter ces échecs.

**Fix v0.13.7.0d** : `sauvegarder()` du parent fait `this.modifie =
false` en cas de succès uniquement (L578 d'`atelier_editeur.js`).
Avec le getter calculé, `modifie` reflète la réalité (signature DOM vs
snapshot). Si la sauvegarde a échoué (DOM toujours dirty), `modifie`
retourne `true` → la garde détecte l'échec et bloque la transition.

### Bug 3 — Autres ateliers : DOM gardait les modifs au retour

**Cause** : v0.13.7.0c faisait `a.ref.modifie = false` sur "ignorer",
sans toucher au DOM. Le badge s'éteignait, mais l'éditeur affichait
toujours le texte modifié.

**Fix v0.13.7.0d** : `_restaurerForm()` est appelé sur "ignorer". Le
DOM est ré-écrit depuis `itemActif`. Au retour dans l'atelier,
l'utilisateur retrouve l'état d'origine.

### Bug 4 — Badge restait allumé sur retour-en-arrière manuel

**Cause** (pas formellement remonté mais latent) : `marquerModifie()`
posait `this.modifie = true` une fois pour toutes. Même si l'user
revenait manuellement à l'état d'origine (tape "x" puis le supprime),
le badge restait allumé.

**Fix v0.13.7.0d** : comparaison structurelle continue. Si la
signature revient identique au snapshot, le badge s'éteint
automatiquement. (Exception : si `marquerModifie()` est appelé
explicitement par une sous-classe pour des actions hors-event input,
le badge reste allumé jusqu'à un `modifie = false` explicite. C'est
voulu : on protège contre les modifications DOM hors-event.)

## Fichiers livrés

```
appli/static/atelier_editeur.js              [MOD]   getter/setter + listener + _restaurerForm
appli/static/atelier_garde.js                [MOD]   chemin "ignorer" → _restaurerForm
appli/static/atelier_exercice.js             [MOD]   toggle*: retrait marquerModifie redondant
appli/templates/index.html                   [MOD]   retrait des 18 oninput/onchange formChange
appli/doc/redemarrage_v0_13_7_0d.md          [NEW]
```

Bilan : ~50 lignes ajoutées dans `atelier_editeur.js`, ~30 lignes
retirées dans le HTML. Plus simple, plus propre, plus de duplication
de logique entre ateliers.

## Vérifications

- Suite pytest : **3238 passed, 5 skipped, 0 failed** (identique au baseline)
- Sanity JS (`node -c`) sur les 8 fichiers JS pertinents : OK

## À tester chez toi

### Scénarios critiques

#### Scénario A — Cohérence sur les 5 ateliers (carte incluse)

Pour chaque atelier (Exercice, Notion, Méthode, Fiche, Carte) :

1. Ouvrir un item existant.
2. Modifier un champ.
3. **Le badge « modifié » s'affiche immédiatement.**
4. **Défaire la modification manuellement** (ex. : taper "x" puis le supprimer pour revenir à l'état d'origine).
5. **Le badge s'éteint automatiquement** (nouveau comportement v0.13.7.0d).

#### Scénario B — « Ne pas sauvegarder » sur changement d'atelier

1. Modifier un item sans sauvegarder.
2. Cliquer sur un autre onglet d'atelier dans le menu du haut.
3. Cliquer "Ne pas sauvegarder" dans la modale.
4. Aller dans l'autre atelier.
5. Revenir dans le premier atelier.
6. **Le formulaire affiche les valeurs d'origine** (les modifs ont disparu).
7. **Le badge est éteint.**

À tester avec les 5 ateliers, **carte comprise**.

#### Scénario C — « Sauvegarder » qui échoue

1. Modifier un item de manière à provoquer un échec de validation backend
   (par exemple, vider un champ requis si applicable).
2. Cliquer "Sauvegarder" dans la modale.
3. **L'utilisateur reste sur l'atelier** (le toast d'erreur s'affiche, la
   transition est bloquée).

Comportement identique avant/après — vérifier qu'il n'a pas régressé.

#### Scénario D — Modifs cumulées dans plusieurs ateliers

1. Modifier un exercice sans sauvegarder.
2. Naviguer vers une notion via le menu, cliquer "Ne pas sauvegarder".
3. Modifier la notion sans sauvegarder.
4. Naviguer vers un troisième atelier.
5. **La modale liste maintenant Notion + Exercice si les deux sont modifiés.**
6. Cliquer "Ne pas sauvegarder".
7. Aller dans Exercice puis dans Notion.
8. **Les deux affichent leur état d'origine, badges éteints.**

#### Scénario E — Ajout/déplacement de section

(Pour Notion ou Méthode)

1. Ouvrir une notion.
2. Cliquer « + Ajouter une section ».
3. **Badge allumé.**
4. Cliquer le bouton « − » pour supprimer la section juste ajoutée.
5. **Le badge reste allumé** (les appels manuels à `marquerModifie()` invalident le snapshot — décision de design v0.13.7.0d).

C'est un comportement conservateur : tant qu'aucun `sauvegarder` ou
`fermerEditeur` n'a pris un nouveau snapshot, le système ne fait pas
confiance à l'utilisateur pour avoir vraiment annulé. **Acceptable.**

## Limitations connues / réserves

### Subtilités de la comparaison de signature

1. **Champs niveau/sequence ajoutés conditionnellement** par
   `collecterFormulaire` (notion, méthode) : si le filtre global
   change, la signature change. Cas peu fréquent : un changement de
   filtre déclenche `chargerListe` qui ferme l'éditeur. Pas d'impact
   pratique.

2. **Performance** : la comparaison fait un `JSON.stringify` à chaque
   keystroke. Coût pour un form de ~10 champs : <1ms. Négligeable.

3. **Champs hors form** : si une sous-classe stocke de l'état UI dans
   des éléments DOM **hors** de `#atl-<prefixe>-form`, ces events ne
   bulleront pas vers le listener. Mais comme `collecterFormulaire`
   lit ces champs aussi (a priori), la signature est correcte. Le seul
   manque serait la mise à jour en temps réel du badge — qui sera mis
   à jour à la prochaine action déclenchant `majToolbar` (clic sur un
   bouton, save, etc.).

### Restes pour la suite

- **v0.13.7.0e** ou **v0.13.7.1** : factorisation des sections
  notion/méthode dans `AtelierAtomique` (sujet initial de v0.13.7.0b,
  repoussé deux fois).
- **v0.13.7.1** : squelette éditeur LaTeX (cf.
  `cadrage_v0_13_7_1_editeur_latex.md`).

## Diagnostic conseillé en cas de symptôme

Si un atelier ne s'aligne pas sur le comportement attendu :

1. **Ouvrir la console** (F12).
2. Modifier un champ.
3. Vérifier : `ATELIER_X.modifie` doit retourner `true`.
4. Vérifier : `ATELIER_X._snapshotForm` doit être une string non null.
5. Comparer : `JSON.stringify(ATELIER_X.collecterFormulaire())` vs
   `ATELIER_X._snapshotForm` — la différence doit refléter le changement.

Si l'un de ces points cloche, soit `collecterFormulaire` retourne un
objet incohérent (à corriger côté sous-classe), soit le snapshot n'a pas
été pris au bon moment.
