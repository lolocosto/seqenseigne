# Redémarrage v0.18.4 — Réorganisation de l'onglet Préférences

L'onglet Préférences est restructuré en **catégories** (titres de groupe) et
**sections repliables**, et le bloc « Paramètres » de la compilation par lot y
est rapatrié (il disparaît de l'écran Rendu par lot).

## Décisions (D1–D8)

- **D1** — Composant dédié `pref-cat` (sections repliables propres aux
  Préférences ; CSS dédiée ; persistance localStorage
  `seqenseigne.pref.cat.<id>.collapsed`).
- **D2** — Un seul niveau de pliage : les **catégories** sont de simples titres
  de groupe (non pliables) ; seules les **sections** se déplient.
- **D3** — Tout **replié par défaut** (état ensuite mémorisé par section).
- **D4** — Arborescence (dans cet ordre) :
  - **Ateliers d'édition** : Rendu PDF · Éditeur LaTeX · Fiches de résumé
  - **Atelier d'assemblage** : Séquence
  - **Outils** : Rendu par lot
  - **Application** : Chemins
- **D5** — Le bloc « Paramètres » disparaît du panneau Rendu par lot (remplacé
  par une note de renvoi vers Préférences). Ses 5 réglages migrent dans
  Préférences > Outils > Rendu par lot. Le Rendu par lot lit les valeurs
  persistées au lancement.
- **D6** — Persistance inchangée : chaque section conserve ses fonctions
  d'enregistrement existantes. Nouvelle paire pour les params compilation
  (`prefChargerParamsCompilation` / `prefEnregistrerParamsCompilation`) via
  `/api/configuration` (clés `timeout_compilation_court_s`,
  `timeout_compilation_long_s`,
  `compilation_batch_max_erreurs_consecutives`, `tikz_libraries`,
  `tblr_libraries` — déjà connues du backend).
- **D7** — Périmètre strict : réorganisation + déplacement. Aucun réglage
  ajouté/retiré, aucune logique de compilation modifiée.
- **D8** — Tous les `id="pref-*"` existants sont **préservés** (le JS les
  référence) ; ils sont seulement déplacés dans la nouvelle structure.

## Mapping des réglages existants → nouvelle structure

| Réglage | Catégorie → Section |
|---|---|
| Mode côte-à-côte, Auto-compile Rendu PDF | Ateliers d'édition → Rendu PDF |
| Hauteur des zones de saisie LaTeX | Ateliers d'édition → Éditeur LaTeX |
| Titres de zone des fiches | Ateliers d'édition → Fiches de résumé |
| Nom + critères F/A/E objectif Connaître | Atelier d'assemblage → Séquence |
| Délais, seuil d'erreurs, biblios tikz/tabularray | Outils → Rendu par lot |
| Racine + chemins dérivés | Application → Chemins |

## Détail technique

### `static/app.css`
- Composant `.pref-categorie` / `.pref-categorie-titre` (titre de groupe) et
  `.pref-cat` / `.pref-cat-head` / `.pref-cat-body` (section repliable, chevron
  ▾ qui pivote, corps masqué en `.collapsed`).

### `static/app.js`
- Helpers `prefCatEstReplie` / `prefCatBasculer` / `prefCatInitEtats`
  (pliage + persistance ; défaut = replié).
- `prefChargerParamsCompilation` / `prefEnregistrerParamsCompilation`
  (lecture/écriture des 5 clés via `/api/configuration`).
- `_compilLireParams` lit désormais les inputs `pref-rdl-*` (au lieu de
  `rdl-*`) ; ces inputs restent dans le DOM en permanence (onglet masqué via
  `display:none`, pas retiré).
- `compilBatchInit` ne pré-remplit plus d'inputs `rdl-*` (supprimés) ; il
  appelle `prefChargerParamsCompilation()` pour garantir des valeurs à jour au
  lancement d'un batch même si l'onglet Préférences n'a jamais été ouvert.
- Au clic sur l'onglet Préférences : appel de `prefChargerParamsCompilation()`
  et `prefCatInitEtats()`.

### `templates/index.html`
- `<main id="tab-preferences">` entièrement restructuré (4 catégories,
  6 sections repliables), contenus internes repris verbatim (ids préservés).
- Bloc « Paramètres avancés » retiré du panneau Rendu par lot, remplacé par une
  note pointant vers Préférences > Outils > Rendu par lot. Les inputs de
  compilation y sont recréés sous les ids `pref-rdl-*` avec un bouton
  « Enregistrer » dédié.

## Tests

`tests_js/preferences_sections.test.js` (8 cas) : structure attendue
(`_compilLireParams` lit `pref-rdl-*` et plus `rdl-timeout-*` ; helpers et
fonctions présents) ; comportement `pref-cat` (clé de stockage, défaut replié,
respect de la valeur mémorisée, bascule + persistance, `prefCatInitEtats`).

**Zéro régression** : vitest → 153 passed (15 fichiers) ; pytest inchangé
(aucun fichier Python modifié), 3832 passed.

## Déploiement

Purement front (HTML/CSS/JS). Aucune migration de données. Les valeurs des
paramètres de compilation déjà présentes dans `data/configuration.json` sont
relues telles quelles ; l'utilisateur les retrouve dans Préférences > Outils >
Rendu par lot.
