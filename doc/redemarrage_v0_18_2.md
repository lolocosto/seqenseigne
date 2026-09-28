# Redémarrage v0.18.2 — Ctrl+clic : ouvrir un atome dans un nouvel onglet

Depuis les résultats de Recherche, le Rendu par lot, et les ateliers
d'assemblage (séquence-dans-niveau, évaluation), un **Ctrl/⌘+clic** (ou
clic-molette) sur un atome référencé l'ouvre dans son atelier **dans un nouvel
onglet**. Le clic simple conserve le comportement classique (ouverture en
place).

## Cadrage (décisions nommées D1–D8)

- **D1 — Mécanisme unique : deeplink URL.** Réutilise l'infrastructure
  existante `_appliquerDeeplink` (app.js) : une URL
  `/?atelier=TYPE&niveau=N&seq=S&atome=ID` ouverte dans un onglet repositionne
  la portée Séquence et ouvre l'atome.
- **D2 — Pattern d'ouverture (lien `<a>`).** Chaque cible ouvrable est un
  `<a href={deeplink} target="_blank">` : clic simple intercepté en JS
  (`preventDefault` + ouverture en place), Ctrl/⌘/Shift+clic et clic-molette
  laissés au navigateur (nouvel onglet natif). Gère ⌘ Mac gratuitement.
- **D3 — Périmètre.** Recherche, Rendu par lot, atelier seqniv, atelier
  évaluation, et toute autre source listant des atomes ouvrables.
- **D4 — seqniv : tout atome référencé** (exercices R/EA/placés, notions,
  méthodes, cartes) devient Ctrl+cliquable.
- **D5 — Correction d'un bug latent.** `_appliquerDeeplink` ne supportait que
  4 types (`exercice/notion/methode/fiche`) et **rejetait `carte_automatisme`**,
  alors que le chip carte de seqniv générait déjà cette URL (deeplink carte
  cassé depuis v0.13.6.3). Désormais supporté. De plus, l'ouverture passe par
  le mécanisme OO unifié `ATELIER_*.ouvrirItem` (cohérence v0.18.1) au lieu des
  anciennes fonctions `atel*Charger`.
- **D6 — Type dans l'URL.** Le `?atelier=` utilise le nom d'atelier de
  `atelSwitch` ; le type court `carte` est mappé vers `carte_automatisme`.
- **D7 — Helpers communs centralisés** (app.js, fonctions top-level donc
  globales) : `deeplinkAtomeURL`, `ouvrirAtomeDepuisEvent`, `lienAtomeHTML`,
  `_nomAtelierPourDeeplink`, `_typeCourtAtome`. Une seule source de vérité,
  réutilisée partout (fin de la duplication du chip carte codé en dur).
- **D8 — Robustesse.** Si niveau/séquence manquent : pas de lien (`<span>`
  inerte), ouverture en place uniquement. Nettoyage d'URL après deeplink
  conservé (F5 ne replonge pas).

## Détail des changements

### `static/app.js`
- Nouveaux helpers (cf. D7).
- `_appliquerDeeplink` étendu (cf. D5) : `carte_automatisme` ajouté aux types
  supportés ; ouverture via `ATELIER_*.ouvrirItem` avec attente que la liste
  de l'atelier soit chargée (async).
- Recherche (`rechercheRendre`) : le bouton « Ouvrir » devient un lien
  `lienAtomeHTML(...)`.
- Rendu par lot (`_compilAjouterLigne`) : `onclick` route clic simple / Ctrl+⌘+
  Shift+clic ; `onauxclick` gère le clic-molette. niveau/séquence viennent
  désormais de l'event backend.

### `services/compilation_batch.py`
- L'event de progression (`base`) porte désormais `niveau` et `sequence`
  (l'`Atome` les avait déjà ; nécessaires au deeplink côté front). Ajout
  purement additif — aucune assertion stricte sur les clés côté tests.

### `static/atelier_seqniv_assemblage.js`
- `editerAtome(type, id, event, niveau, sequence)` : si `event` (Ctrl+clic),
  délègue à `ouvrirAtomeDepuisEvent` (nouvel onglet) ; sinon ouverture en
  place. niveau/séquence par défaut = séquence courante de l'assemblage ;
  surchargeables (les exos de Révision peuvent venir d'une autre séquence).
- Les 9 appels `editerAtome` (onclick/ondblclick méthodes, notions, exercices)
  passent `event`.
- `_rendreChipCarte` aligné sur `lienAtomeHTML` (avant : `<a>` codé en dur qui
  ouvrait TOUJOURS en nouvel onglet ; désormais clic simple = en place,
  cohérent).

### `static/atelier_evaluation_oo.js`
- Le label d'un exercice attaché (« N10/S01/F01 ») devient un lien deeplink
  (`lienAtomeHTML`), niveau/séquence portés par l'objet exo.

## Tests

- **`tests_js/deeplink_nouvel_onglet.test.js`** (13, nouveau) : normalisation
  type/atelier (carte ↔ carte_automatisme), `deeplinkAtomeURL` (URL/encodage,
  null si niveau/seq manquant), `ouvrirAtomeDepuisEvent` (clic simple →
  preventDefault + ouverture en place ; Ctrl/⌘/molette → true sans ouverture
  en place ; mapping type court), `lienAtomeHTML` (`<a>` vs `<span>`,
  échappement apostrophe).
- **`tests_js/recherche_outil.test.js`** : assertions mises à jour (lien `<a>`
  deeplink au lieu du bouton onclick ; entités `&amp;` normalisées par
  innerHTML).

**Zéro régression** : `pytest` → 3832 passed, 7 skipped ; `vitest` → 122
passed (13 fichiers).

## Reste différé (roadmap)

- Sélecteur de sensibilité à la casse dans l'UI Recherche (backend déjà prêt).
- Ouverture d'un *assemblage* (séquence-niveau, évaluation) lui-même dans un
  nouvel onglet — hors périmètre (on n'ouvre que l'atome sélectionné).
