# Redémarrage v0.13.6.6.1

**Session du 14 mai 2026 — 2 fixes UI post-v0.13.6.6**

---

## Périmètre

Deux remarques après ton test de v0.13.6.6 :

1. **Bouton « atelier actif » pas mis en évidence** dans le second
   bandeau (sous celui des portées Séquence/Niveau/Cycle).
2. **Colonne d'édition pas vidée** au changement de filtre
   niveau/séquence — la sidebar à gauche se rafraîchit mais le panneau
   central reste sur l'ancien item, créant un état incohérent.

---

## Fixes

### Fix 1 — Bandeau atelier actif visible

**Diagnostic** : les deux bandeaux utilisent les mêmes classes CSS
`.vbtn.active`, qui applique `background: var(--primary-bg)` =
`#e8eef7` (bleu très pâle). Mais le second bandeau a en plus
`background: var(--bg-soft, #fafafa)` sur son conteneur — soit
`#fafafa` (gris quasi blanc) puisque `--bg-soft` n'est pas définie.

Résultat : le contraste entre le fond `#fafafa` du bandeau et le
`#e8eef7` du bouton actif est trop faible pour qu'on voie une
différence à l'œil nu.

**Fix** : retirer le fond du second bandeau, comme c'est le cas du
premier. Le bouton actif ressort maintenant nettement (bleu pâle sur
fond blanc).

Fichier modifié : `appli/templates/index.html` ligne 453.

### Fix 2 — Vider l'éditeur au changement de niveau/séquence

**Diagnostic** : quand l'utilisateur change le filtre niveau/séquence
en haut de l'écran, `atelAppliquerSelectionsPortee()` dans app.js
appelle l'init de l'atelier visible (ici `atelCarteCharger` qui
délègue à `ATELIER_CARTE.chargerListe()`). La sidebar se recharge avec
les cartes de la nouvelle séquence. Mais le panneau d'édition central
reste sur l'ancienne carte — état incohérent.

**Fix** : nouvelle méthode `AtelierEditeur._synchroniserItemActifAvecListe()`.
Appelée après chaque `chargerListe()`, elle vérifie que l'item actif
est toujours dans la nouvelle liste rechargée. Si non, l'éditeur est
fermé (passage à l'état vide).

Les modifications en cours sont abandonnées silencieusement — c'est
cohérent avec le fait que l'utilisateur a délibérément changé de
contexte (changement de filtre = changement de séquence/niveau).

Comme la méthode est dans `AtelierEditeur` (classe parente), elle est
disponible **automatiquement** dans tous les ateliers atomiques quand
ils seront migrés (notion, méthode, fiche, exercice — v0.13.6.7+).
Pour le pilote v0.13.6.6, seul `AtelierCarte` en bénéficie ; sa
surcharge `chargerListe()` (3 fetch parallèles) appelle aussi
`_synchroniserItemActifAvecListe()`.

Fichiers modifiés :
- `appli/static/atelier_editeur.js` (+ méthode)
- `appli/static/atelier_carte_automatisme.js` (appel dans la surcharge)

---

## Validation chez toi

### Test fix 1

1. Recharger la page
2. Regarder le second bandeau : le bouton de l'atelier sélectionné
   (par défaut Exercice) doit avoir un fond bleu pâle distinct des
   autres
3. Cliquer sur "Carte d'automatisme" : le fond bleu pâle doit suivre
   sur ce bouton
4. Idem pour la portée Niveau : le bouton Référentiel ou Évaluation
   doit avoir son fond actif visible

### Test fix 2

1. Sélectionner Niveau N10, Séquence S01
2. Ouvrir l'atelier Carte d'automatisme
3. Cliquer sur une carte → l'éditeur s'ouvre dans le panneau central
4. Changer la séquence en haut de l'écran : passer à S02
5. **Attendu** : la sidebar à gauche affiche les cartes de S02, le
   panneau central revient à l'état vide ("Sélectionner une carte ou
   créer une nouvelle")
6. Cliquer sur une carte de S02 → l'éditeur s'ouvre sur la nouvelle

7. Cas limite : ouvrir une carte de S02, modifier un champ (badge
   "modifié" apparaît), puis re-changer la séquence vers S01. **Attendu** :
   l'éditeur se vide, les modifications sont perdues (cohérent avec la
   décision de l'utilisateur de changer de contexte). Pas de confirm()
   intempestif.

### En cas d'anomalie

Si le bouton actif ne ressort pas après le fix 1, vérifier dans les
outils dev du navigateur que le `style="background:var(--bg-soft, #fafafa)"`
a bien été retiré de la `<div class="toolbar">` ligne 2 du bandeau
des ateliers (autour de la ligne 453 d'index.html).

Si l'éditeur ne se vide pas après le fix 2, c'est probablement
qu'`atelCarteCharger` est appelée mais ne passe pas par
`ATELIER_CARTE.chargerListe()`. Vérifier dans le pont rétrocompat de
`atelier_carte_automatisme.js` que la ligne :
```js
window.atelCarteCharger = () => ATELIER_CARTE.chargerListe();
```
est bien présente.

---

## Fichiers livrés

| Fichier | Changement |
|---|---|
| `appli/static/atelier_editeur.js` | + méthode `_synchroniserItemActifAvecListe()` appelée dans `chargerListe()` |
| `appli/static/atelier_carte_automatisme.js` | Appel de `_synchroniserItemActifAvecListe()` dans la surcharge `chargerListe()` |
| `appli/templates/index.html` | Fond gris retiré du second bandeau (ligne 453) |

---

## Suite

Les 2 fixes sont indépendants des autres chantiers. La roadmap
continue comme prévu :

- v0.13.6.7 : migration exercice + notion + méthode + fiche +
  évaluation (le fix 2 leur bénéficiera automatiquement dès qu'ils
  hériteront de `AtelierEditeur`)
- v0.13.6.8 : multi-sélection + menu contextuel
