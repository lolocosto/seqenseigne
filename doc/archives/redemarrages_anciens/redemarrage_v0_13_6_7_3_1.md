# Redémarrage v0.13.6.7.3.1

**Session du 15 mai 2026 — 2 fixes ateliers notion/méthode**

---

## Périmètre

Tu as constaté que pour les ateliers Notion et Méthode :
- Cliquer sur l'onglet « Rendu PDF » garde le trait bleu sous « Édition ».
- Le panneau Rendu PDF affiche le message « Sauvegarder l'atome
  d'abord pour pouvoir générer son rendu PDF », même quand l'atome
  est ouvert et n'a pas été modifié.

Deux causes distinctes — communes aux deux ateliers, conséquences de
la migration OO incomplète :

---

## Cause 1 — IDs manquants sur les onglets

`AtelierEditeur.basculerOnglet(tab)` ajoute la classe `active` sur le
bouton dont l'id est `<préfixe>-tab-btn-<tab>` (ex: `atl-notion-tab-btn-rendu`).

Or les boutons d'onglet notion et méthode dans `index.html`
**n'avaient pas d'id**. Donc la classe `active` n'était jamais
basculée → le trait bleu (indicateur d'onglet actif) restait sur
Édition.

Pour la carte ça marche parce que les boutons d'onglet carte ont
leurs IDs (`atl-carte-tab-btn-edition` et `atl-carte-tab-btn-rendu`),
ce qui suit la convention déjà appliquée pour l'asm, l'éval et la
carte.

**Fix** : ajouter les IDs manquants dans le HTML pour notion et méthode.

### Avant
```html
<div class="atl-tabs" id="atl-notion-tabs">
  <button class="atl-tab active" onclick="ATELIER_NOTION.basculerOnglet('edition')">Édition</button>
  <button class="atl-tab"        onclick="ATELIER_NOTION.basculerOnglet('rendu')">Rendu PDF</button>
</div>
```

### Après
```html
<div class="atl-tabs" id="atl-notion-tabs">
  <button class="atl-tab active" id="atl-notion-tab-btn-edition" onclick="…">Édition</button>
  <button class="atl-tab"        id="atl-notion-tab-btn-rendu"   onclick="…">Rendu PDF</button>
</div>
```

(Idem pour méthode.)

---

## Cause 2 — `rendu_atome.js` lit la mauvaise variable

`rendu_atome.js` est appelé quand on bascule sur l'onglet Rendu PDF
(via `AtelierNotion.basculerOnglet`). Il appelle `rendreAtomeTab(type)`
qui appelle `rendreAtomeGetId(type)`.

`rendreAtomeGetId('notion')` lisait `ATL_NOTION_ACTIF` **directement**
(sans préfixe `window.`). Or :

- Les variables `let` top-level d'app.js (comme `ATL_NOTION_ACTIF`)
  sont dans le scope global lexical mais **pas attachées à window**.
- Ma classe `AtelierNotion` maintient un miroir via :
  ```js
  set itemActif(val) { this._itemActif = val; window.ATL_NOTION_ACTIF = val; }
  ```
  qui écrit sur **window**, mais ne peut pas réassigner la `let` d'app.js.

Donc deux références distinctes pour le même nom :
- `ATL_NOTION_ACTIF` (lecture directe) → `let` d'app.js → reste `null`
  (puisque les onclick passent maintenant par `ATELIER_NOTION` et pas
  par l'ancien `atelNotionCharger` d'app.js)
- `window.ATL_NOTION_ACTIF` → mis à jour par la classe

`rendreAtomeGetId('notion')` lisait la première (toujours `null`), d'où
le message « Sauvegarder l'atome d'abord ».

**Fix** : `rendreAtomeGetId` lit en priorité `window.ATELIER_<TYPE>.itemActif`
si l'instance OO existe (carte, notion, méthode aujourd'hui), sinon
retombe sur le mécanisme historique pour les ateliers non encore
migrés (fiche, exercice).

### Mécanisme avant
```js
function rendreAtomeGetId(type) {
  let actif = null;
  try {
    if      (type === 'exercice') actif = ATL_EXO_ACTIF;
    else if (type === 'notion')   actif = ATL_NOTION_ACTIF;
    else if (type === 'methode')  actif = ATL_METHODE_ACTIF;
    else if (type === 'fiche')    actif = window.ATL_FICHE_ACTIF;
  } catch (_) { actif = null; }
  return actif && actif.id ? actif.id : null;
}
```

### Mécanisme après
```js
function rendreAtomeGetId(type) {
  // 1. Source OO en priorité
  const atelier = window['ATELIER_' + type.toUpperCase()];
  if (atelier && atelier.itemActif && atelier.itemActif.id) {
    return atelier.itemActif.id;
  }
  // 2. Fallback historique pour les ateliers non encore migrés
  let actif = null;
  try {
    if      (type === 'exercice') actif = ATL_EXO_ACTIF;
    else if (type === 'notion')   actif = ATL_NOTION_ACTIF;
    else if (type === 'methode')  actif = ATL_METHODE_ACTIF;
    else if (type === 'fiche')    actif = window.ATL_FICHE_ACTIF;
  } catch (_) { actif = null; }
  return actif && actif.id ? actif.id : null;
}
```

Le fallback reste utile pour la fiche (v0.13.6.7.4) et l'exercice
(v0.13.6.7.5) en attendant leur migration.

---

## Leçon pour les migrations futures

Le miroir `window.ATL_<TYPE>_ACTIF` ne suffit **pas** : tout code
historique qui lit `ATL_<TYPE>_ACTIF` directement (sans préfixe
`window.`) ne verra pas la valeur posée par la classe. Pour bien
faire, il faut soit :
- modifier le code lecteur pour utiliser `window.ATELIER_<TYPE>.itemActif`
  (approche OO propre)
- déclarer la globale legacy avec `var` au lieu de `let` dans app.js
  pour qu'elle soit attachée à window (approche par compat — fragile)

Pour cette livraison, j'ai pris l'approche OO. Pour les prochaines
migrations (fiche, exercice), il faudra appliquer le même raisonnement :
chercher tout le code qui lit `ATL_<TYPE>_ACTIF` directement et le
migrer vers `window.ATELIER_<TYPE>.itemActif`.

Recherche pour la fiche / exercice :
- `rendu_atome.js` : déjà corrigé
- `atelier_etat_edition.js` : passe `atome` en paramètre, pas concerné
- `app.js` (callbacks `ATL_ATOME_CONFIG.<type>`) : code mort (jamais
  appelé après migration), pas besoin de changer

---

## Validation chez toi

### Test fix 1 — Trait bleu sur onglet actif (notion et méthode)

1. Ouvrir l'atelier Notion, cliquer sur une notion
2. Cliquer sur l'onglet « Rendu PDF » → le trait bleu doit passer
   de « Édition » à « Rendu PDF »
3. Re-cliquer sur « Édition » → le trait bleu revient
4. Idem pour l'atelier Méthode

### Test fix 2 — Bouton Compiler au lieu du message d'erreur

1. Ouvrir l'atelier Notion, cliquer sur une notion (sans modifier)
2. Cliquer sur « Rendu PDF » → le panneau doit afficher le bouton
   « 📄 Compiler le rendu », pas le message « Sauvegarder l'atome
   d'abord »
3. Cliquer sur « Compiler le rendu » → la compilation se déclenche,
   le PDF s'affiche
4. Idem pour méthode

### Test transverse — Régression carte

1. Carte d'automatisme : tout doit fonctionner comme avant
   (onglet bascule, compilation OK)

---

## Fichiers livrés

| Fichier | Statut |
|---|---|
| `appli/static/rendu_atome.js` | modifié (fix 2) |
| `appli/templates/index.html` | modifié (fix 1 : IDs onglets notion + méthode) |

Décompresser à la racine de `seqenseigne/`. F5.

---

## Suite

Pas de changement dans la roadmap :
- v0.13.6.7.4 : migration fiche
- v0.13.6.7.5 : migration exercice
- v0.13.6.8 : multi-sélection
- v0.13.6.9+ : chantiers A à F de cohérence
