# Redémarrage v0.13.7.0d.1 — Patch carte : méthode HTTP de sauvegarde

## Périmètre

**Patch ciblé** post-v0.13.7.0d. Corrige un bug latent sur la carte
d'automatisme qui s'est manifesté après l'unification de la garde de
sortie.

## Bug corrigé

### Symptôme

Pour la carte d'automatisme :
- Cliquer « Sauvegarder » dans la modale 3 boutons → échoue silencieusement, l'utilisateur reste sur la carte sans que la sauvegarde se fasse.
- Le bouton « Enregistrer » dans la toolbar de la carte semble lui aussi cassé (à confirmer).

Identique en intra-atelier (changement d'item dans la sidebar) et inter-atelier (menu du haut).

### Cause racine

Méthode HTTP incorrecte. La méthode parente `AtelierEditeur.sauvegarder()`
envoie un **PUT** sur `/api/cartes/<id>`. Or la route serveur n'accepte
que **PATCH** (cf. `routes/cartes_automatisme.py` L191).

Conséquence : le serveur retourne 405 Method Not Allowed, le `if
(!resp.ok)` à L570 d'`atelier_editeur.js` affiche un toast d'erreur,
puis `return` sans avoir posé `this.modifie = false`. Avec la nouvelle
architecture de garde de v0.13.7.0d (getter calculé), `modifie` reste
`true`, la garde détecte l'échec et bloque la transition.

Tous les autres ateliers atomiques (notion, méthode, exercice, fiche)
ont leurs routes serveur en PUT, c'est cohérent. Seule la carte est en
PATCH.

C'était un bug latent : sans doute existait depuis la migration OO de
la carte (v0.13.6.6) ou un changement ultérieur de la route. Il était
peu visible parce que (1) le toast d'erreur peut passer inaperçu, (2)
l'ancien pipeline `atelier_garde_sortie.js` ne détectait pas l'échec
de sauvegarde (snapshots vides). v0.13.7.0d, en faisant fonctionner
proprement la garde, expose ce bug.

### Fix

Ajout d'une option de configuration `methodeUpdate` dans
`AtelierEditeur`. Par défaut `'PUT'` (comportement actuel pour les 4
ateliers REST classiques). La carte déclare `methodeUpdate: 'PATCH'`
dans son constructeur.

```js
// AtelierEditeur.sauvegarder()
const methodeUpdate = this.config.methodeUpdate || 'PUT';
const method = this.itemActif ? methodeUpdate : 'POST';
```

```js
// AtelierCarte constructor
super({
  // ...
  methodeUpdate: 'PATCH',
  // ...
});
```

## Fichiers livrés

```
appli/static/atelier_editeur.js              [MOD]   méthode HTTP configurable
appli/static/atelier_carte_automatisme.js    [MOD]   declare methodeUpdate: 'PATCH'
appli/doc/redemarrage_v0_13_7_0d_1.md        [NEW]
```

Bilan : 6 lignes ajoutées en tout.

## Vérifications

- Suite pytest : **3238 passed, 5 skipped, 0 failed** (identique)
- Sanity JS sur les 2 fichiers modifiés : OK

## À tester chez toi

### Scénario A — Sauvegarde directe d'une carte

1. Ouvrir une carte existante.
2. Modifier un champ.
3. Cliquer le bouton « Enregistrer » dans la toolbar de la carte.
4. **La carte doit se sauvegarder, le toast « Carte enregistrée » s'affiche, le badge s'éteint.**

### Scénario B — Sauvegarde via la modale (intra-atelier)

1. Ouvrir une carte, modifier.
2. Cliquer sur une autre carte dans la sidebar.
3. Modale 3 boutons → « Sauvegarder ».
4. **La carte initiale doit se sauvegarder, puis la deuxième carte s'ouvre.**

### Scénario C — Sauvegarde via la modale (inter-atelier)

1. Ouvrir une carte, modifier.
2. Cliquer sur l'onglet « Notion » du menu du haut.
3. Modale 3 boutons → « Sauvegarder ».
4. **La carte se sauvegarde, l'atelier Notion s'ouvre.**

### Tester aussi que rien n'a régressé sur les 4 autres ateliers

Pour Exercice, Notion, Méthode, Fiche : refaire les scénarios A/B/C de
v0.13.7.0d. Tout doit fonctionner identiquement (ils utilisent toujours
PUT par défaut).

## Limitations / observations

1. **Si Laurent confirme que le bouton « Enregistrer » de la carte
   marchait avant v0.13.7.0d.1**, alors mon diagnostic ci-dessus est
   incorrect ou incomplet. Investigation supplémentaire nécessaire.
   Possibles autres causes : middleware Flask, override de méthode HTTP
   côté serveur, ou autre. À me signaler.

2. **Pour la création d'une carte (POST)** : pas de changement.
   `methodeUpdate` ne s'applique qu'à l'update d'un item existant.

3. **Le bouton « Enregistrer » de la carte** : il appelle
   `ATELIER_CARTE.sauvegarder()`, donc utilise désormais PATCH après
   v0.13.7.0d.1.

## Prochaines étapes (rappel)

- **Tests par toi** → si OK, on enchaîne sur v0.13.7.0e (factorisation
  sections notion/méthode dans `AtelierAtomique`).
- **Puis v0.13.7.1** : squelette éditeur LaTeX.
