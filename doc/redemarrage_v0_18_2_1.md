# Redémarrage v0.18.2.1 — Correctif Ctrl+clic dans les séquences (seqniv)

Correctif de la v0.18.2. Symptôme rapporté après déploiement : le Ctrl+clic
ouvrait bien un nouvel onglet dans le Référentiel (tous types) et dans les
évaluations (exercices), mais **uniquement pour les cartes d'automatisme**
dans l'atelier séquence-dans-niveau — pas pour les notions, méthodes,
exercices, ni fiches.

## Cause

Dans le Référentiel et l'évaluation, les atomes sont rendus comme de vrais
liens `<a href={deeplink}>` : le navigateur ouvre nativement le nouvel onglet
au Ctrl+clic. Dans seqniv, en revanche, les notions/méthodes/exercices/fiches
sont rendus comme des `<span>`/`<div>` avec un handler `onclick`/`ondblclick`
appelant `editerAtome(...)`. Or `editerAtome` déléguait à
`ouvrirAtomeDepuisEvent`, conçu pour des `<a>` : sur un Ctrl+clic, ce helper
**retourne `true` en comptant sur le navigateur pour suivre le lien** — mais il
n'y a pas de lien sur un `<span>`, donc rien ne s'ouvrait. Les cartes
marchaient parce que `_rendreChipCarte` produit, lui, un vrai `<a>` (via
`lienAtomeHTML`).

## Correctif

`static/atelier_seqniv_assemblage.js` :

- **`editerAtome(type, id, event, niveau, sequence)`** : sur un clic « nouvel
  onglet » (Ctrl / ⌘ / Shift / clic-molette), ouvre désormais explicitement le
  nouvel onglet via `window.open(deeplinkAtomeURL(...), '_blank', 'noopener')`
  au lieu de déléguer à `ouvrirAtomeDepuisEvent` (qui supposait un `<a>`). Clic
  simple et appel programmatique : ouverture en place inchangée. Si niveau/seq
  ne sont pas dérivables (URL nulle), repli sur l'ouverture en place.

- **`editerFiche(ficheId, event)`** : ré-implémenté pour router via
  `editerAtome('fiche', ficheId, event)` — il appelait auparavant directement
  `atelSwitch` + `atelFicheCharger` sans support du nouvel onglet ni du couple
  niveau/séquence. Les 2 appels (`dblclickHandler` du tableau central et
  `ondblclick` de la liste) passent maintenant `event`.

### Note d'ergonomie (inchangée, pas un bug)

Dans seqniv, l'ouverture d'un atome suit l'ergonomie existante de chaque chip :
- **méthode** (chip objectif) : `onclick` → Ctrl+**simple**-clic ;
- **notion / exercice / fiche** : `ondblclick` (« Double-clic pour éditer ») →
  Ctrl+**double**-clic.

Le correctif fait fonctionner le nouvel onglet dans les deux cas ; il ne change
pas le simple-vs-double-clic, qui reste tel quel (le simple-clic sur ces chips
est réservé à la sélection / au drag-and-drop).

## Tests

`tests_js/atelier_seqniv_assemblage.test.js` : +8 cas sur `editerAtome` /
`editerFiche` — clic simple → ouverture en place ; Ctrl/⌘+clic et clic-molette
→ `window.open` ; niveau/séquence explicites prioritaires (exo de Révision
d'une autre séquence) ; appel programmatique sans event → en place ; Ctrl+clic
sans niveau/seq dérivable → repli en place.

**Zéro régression** : `vitest` → 130 passed (13 fichiers). Aucun fichier Python
modifié (pytest inchangé, 3832 passed à la v0.18.2).
