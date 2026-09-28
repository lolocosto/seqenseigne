# Redémarrage v0.17.0 — Bouton « LaTeX généré » : déplacement + factorisation

Premier jalon de la v0.17. Deux chantiers étaient prévus ; celui-ci ne traite
que le **chantier 1** (bouton LaTeX généré). Le chantier 2 (aperçu PDF au survol
dans les ateliers d'assemblage) fera l'objet de **v0.17.1**.

## Objectif

Déplacer le bouton « LaTeX généré » de la toolbar du HAUT des ateliers vers la
mini-toolbar de la zone de rendu, à côté de « Compiler le rendu » (alignement
sur l'atelier Séquence). Demande de Laurent : **factorisation poussée** — la
mini-toolbar de rendu est désormais GÉNÉRÉE par une méthode commune de la base,
au lieu d'être dupliquée en HTML statique dans les 6 ateliers.

## Ce qui change

### Base — `static/atelier_editeur.js`
- Nouvelle méthode **`_assurerToolbarRendu()`** : génère (une seule fois,
  idempotent) dans le conteneur `#<prefixe>-rendu-toolbar` :
  - bouton « Compiler le rendu » (`<prefixe>-btn-compiler`, classe `btn-sm btn-prim`),
  - bouton « LaTeX généré » (`<prefixe>-btn-latex`, classe `btn-sm`, masqué par
    défaut — visibilité pilotée par `majToolbar`),
  - span de statut (`<prefixe>-rendu-status`).
  Les handlers sont câblés par **`addEventListener`** (pas d'`onclick` inline) :
  la base n'a pas à connaître le nom de la variable globale de l'instance.
  Marque `conteneur.dataset.genere='1'` ; no-op si le conteneur est absent
  (rétrocompatibilité). Termine par `this.majToolbar()` pour synchroniser la
  visibilité du bouton LaTeX selon l'état courant.
- Appelée au début de `verifierCacheEtAfficher()` et de `compilerRendu()` (les
  deux points d'entrée du rendu).

### Template — `templates/index.html`
- Pour les **6 ateliers** (exercice, notion, methode, fiche, carte, eval) :
  - le bouton « LaTeX généré » est RETIRÉ de la toolbar du haut ;
  - la mini-toolbar statique de la zone de rendu (bouton compiler + status) est
    remplacée par un **conteneur vide** `#atl-<type>-rendu-toolbar` que la base
    remplit.
  - Cas particulier carte : un doublon « Voir le .tex » qui traînait dans sa
    mini-toolbar a été supprimé (unifié avec le bouton « LaTeX généré » généré).

### `static/app.js`
- **Raccourci Ctrl+L** réécrit : ne détecte plus l'atelier via un bouton
  `btn-latex` visible dans la toolbar du haut (disparu), mais cible directement
  l'INSTANCE de l'atelier dont le panneau est visible (mapping panneau →
  `ATELIER_*`) et appelle sa méthode `voirLatex()` si un item est chargé.
  Ignore le raccourci si le focus est dans un champ de saisie.
- **Mode split** (`prefSplitAppliquer`) : la détection de l'atelier à rendre ne
  s'appuie plus sur un `btn-latex` visible mais sur l'`itemActif` des instances.

## Compatibilité / points d'attention

- L'évaluation conserve sa propre `_majToolbar()` (pilote `atl-eval-btn-latex`
  par id, protégé par `if (btnLatex)`). Le bouton est créé par
  `_assurerToolbarRendu` à l'ouverture de l'onglet Rendu, puis rendu visible par
  `_majToolbar` quand un item est chargé. Pas de conflit.
- Le seqniv (atelier d'assemblage) n'est PAS concerné : il a sa propre chaîne de
  rendu (`_livretSeq*`), pas de conteneur `liv-atl-rendu-toolbar`, donc
  `_assurerToolbarRendu` y est no-op.
- Le bouton « LaTeX généré » n'apparaît désormais que dans l'onglet Rendu (à
  côté de Compiler), plus dans la toolbar du haut — c'est l'effet recherché.

## Tests

- **Vitest** : 73 passed (67 + 6 nouveaux).
  - `tests_js/toolbar_rendu_factorisee.test.js` : génération des 3 éléments,
    bouton LaTeX masqué par défaut, idempotence (pas de doublon), no-op sans
    conteneur, câblage `compilerRendu`/`voirLatex` par addEventListener.
- **pytest** : 3793 passed, 7 skipped, 0 failed.
  - Tests mis à jour pour refléter la factorisation (les boutons ne sont plus
    dans le HTML statique) :
    - `tests/test_v0_14_3_html_unifie_et_auto_compile.py` : `btn-compiler`/
      `rendu-status` retirés des ids statiques attendus ; ajout de
      `rendu-toolbar` ; nouveaux tests `test_conteneur_toolbar_rendu_vide` et
      `test_base_genere_toolbar_rendu`.
    - `tests/test_v0_16_2_consolidation_eval.py` : idem pour l'éval
      (`test_toolbar_rendu_generee_v0_17_0`).
- **Syntaxe** : `node --check` (app.js, atelier_editeur.js) OK.

## À vérifier côté Windows (validation visuelle)

1. Dans chaque atelier (exercice, notion, méthode, fiche, carte, évaluation) :
   ouvrir un atome, aller dans l'onglet Rendu PDF → la barre affiche
   « Compiler le rendu » ET « LaTeX généré » côte à côte.
2. Plus de bouton « LaTeX généré » dans la barre du haut.
3. Cliquer « Compiler le rendu » puis « LaTeX généré » → comportements
   habituels (compilation, ouverture du .tex dans un onglet).
4. Ctrl+L dans un atelier avec un atome chargé → ouvre le LaTeX généré.
5. Mode split (si activé) : le rendu de l'atome chargé s'affiche bien à droite.
6. Carte : plus de doublon « Voir le .tex » / « LaTeX généré ».

## Suite — v0.17.1

Chantier 2 : aperçu PDF au survol des atomes dans les ateliers d'assemblage
(cadrage : `cadrage_unification_ateliers_assemblage.md` §2bis/§5bis ; décisions
A1 tout atome compilable, A2 modale unique large flottante, A3 hybride avec
bouton « Générer l'aperçu », délai 1500 ms). Infrastructure backend déjà
présente (`GET /api/atomes/<type>/<id>/rendu-pdf/info` + `/rendu-pdf` + viewer
pdf.js).
