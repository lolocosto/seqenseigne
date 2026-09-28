# Redémarrage v0.17.6 — Scroll à l'ouverture/fermeture d'un objectif

Complément direct du correctif scroll de v0.17.5.

## Symptôme (signalé par Laurent)

Exemple : N10 S12 en trois parties. En ouvrant l'objectif 23 (en bas de page),
on est renvoyé tout en haut du panneau. v0.17.5 préservait le scroll pour les
opérations de structure (drag d'un atome, etc.) mais avait volontairement
exclu `ouvrirObj`/`fermerObj` (classés « changement de contexte »). À l'usage,
ce renvoi en haut est gênant.

## Décision (Laurent)

À l'ouverture ET à la fermeture d'un objectif, **défiler jusqu'à cet objectif**
(il apparaît près du haut du panneau) plutôt que restaurer une position absolue
— car le contenu change (l'objectif se déplie/replie), une position absolue ne
tomberait pas juste.

## Correctif

- `static/atelier_assemblage.js` — nouveau helper
  `_scrollVersObjectif(objId, marge=12)` : amène l'élément
  `[data-obj-id="<objId>"]` près du haut de la zone visible du conteneur
  scrollable, via `getBoundingClientRect` (robuste quel que soit l'offsetParent)
  + `scrollTop` courant. Échappe l'id avec `CSS.escape`. No-op si conteneur ou
  élément absent.
- `static/atelier_seqniv_assemblage.js` :
  - `ouvrirObj(objId)` → après `rafraichir()`, `requestAnimationFrame(() =>
    this._scrollVersObjectif(objId))`.
  - `fermerObj()` → mémorise l'id de l'objectif fermé AVANT
    `_setObjOuvert(null)`, puis défile vers lui après le rendu.

  Le `requestAnimationFrame` garantit que le layout du nouveau DOM est calculé
  avant de positionner le scroll.

Les blocs objectif (ouvert et fermé) portent déjà `data-obj-id="<id>"` dans le
rendu — sélecteur stable réutilisé ici.

## Tests

- **Vitest** : 94 passed (92 + 2 nouveaux).
  - `tests_js/scroll_et_etat_atomes.test.js` : `_scrollVersObjectif` positionne
    le conteneur sur l'objectif (calcul scrollTop + delta géométrique) ; no-op
    si l'objectif est absent.
- **pytest** : inchangé (3794/7/0) — v0.17.6 est du JS pur, aucun changement
  backend.
- **Syntaxe** : node --check OK.

## À vérifier côté Windows

1. N10 S12 (3 parties) : scroller vers le bas, ouvrir l'objectif 23 → il reste
   visible (amené près du haut du panneau), plus de retour tout en haut.
2. Fermer cet objectif → on revient sur lui (il redevient visible à sa place),
   pas en haut de page.
3. Les opérations de structure (v0.17.5) conservent leur comportement
   (préservation de la position).

## Suite — v0.18

Outil de recherche globale + compilation globale.
