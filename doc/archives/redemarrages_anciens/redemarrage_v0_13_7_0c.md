# Redémarrage v0.13.7.0c — Garde de sortie unifiée

## Périmètre

Livraison **préparatoire** au chantier éditeur LaTeX (v0.13.7.1+). Cette
livraison fait trois choses, étroitement liées et qui n'ont de sens
qu'ensemble :

1. **Répare la garde de sortie** des 4 ateliers atomiques cassés
   (notion, méthode, exercice, fiche) — perte silencieuse de
   modifications corrigée.
2. **Unifie l'UX** : une seule modale 3 boutons (Sauvegarder / Ne pas
   sauvegarder / Annuler) partout, en remplacement de l'ancien double
   système (confirm() natif pour intra-atelier + modale custom pour
   inter-atelier).
3. **Nettoie le code mort** des ateliers Notion et Méthode dans
   `app.js` (~700 lignes orphelines depuis la migration OO v0.13.6.7+).

Au passage, deux fichiers legacy sont supprimés en franc-bord
(`atelier_garde_sortie.js` et `atelier_atome_generique.js`), tous deux
court-circuités depuis la migration OO et donc inutiles.

## Bugs réparés

### Bug 1 — Badge « modifié » ne s'allumait jamais (notion, méthode, exercice, fiche)

**Cause** : Les champs HTML de ces 4 ateliers n'avaient pas
`oninput="ATELIER_X.formChange()"`. Le mécanisme moderne hérité de
`AtelierEditeur` (`this.modifie = true` + badge piloté par
`majToolbar()`) n'était donc jamais déclenché.

L'ancien pipeline `atelier_garde_sortie.js` qui aurait dû prendre le
relais a été court-circuité par les alias OO : `atelSnapshotInstaller`
n'était plus appelé nulle part, donc `_SNAPSHOTS[type]` restait à
`null` en permanence, et `atelSnapshotEstModifie` retournait toujours
`false`.

Pire : un `addEventListener('input', ...)` posé sur tout le form
(L6578 d'app.js, dans le bloc `_brancher`) appelait
`atelGardeMajIndicateur` qui **éteignait** le badge à chaque saisie
parce que le snapshot était vide. Le badge restait donc obstinément
caché.

**Fix** :
- Câblage de `oninput="ATELIER_X.formChange()"` sur 13 champs HTML.
- Patch des deux `toggleCadreReponse*()` de l'exercice pour marquer
  modifié.
- Suppression franche du pipeline historique (cf. Bug 3 et Bug 4).

### Bug 2 — Modifications conservées après « Ne pas sauvegarder » (les 4 ateliers cassés)

**Cause** : Quand l'utilisateur cliquait « Ne pas sauvegarder » dans la
modale 3 boutons de l'ancien pipeline (côté inter-atelier), la
continuation s'exécutait mais les flags `modifie` (côté moderne)
n'étaient **pas** remis à `false`. Conséquence : à la transition
suivante, la modale revenait avec exactement la même liste d'ateliers
modifiés, sans fin.

Pire encore : l'utilisateur pouvait ainsi accumuler des modifications
non sauvegardées dans 5 ateliers, naviguer librement entre eux, et
finir par ne plus savoir où il en était. Si la page se fermait, tout
partait.

**Fix** : Le nouveau `atelGardeAvantTransition` dans `atelier_garde.js`
RESET explicitement `a.ref.modifie = false` pour chaque atelier après
choix « Ne pas sauvegarder », et appelle `majToolbar()` pour cacher le
badge.

### Bug 3 — Pas de garde sur changement d'atelier pour la carte

**Cause** : La carte n'enregistrait pas de handler dans
`_ATL_GARDE_HANDLERS` (système historique), parce qu'elle utilisait
déjà le mécanisme moderne. Donc `atelGardeAvantTransition` ne la
voyait pas, et naviguer vers un autre atelier laissait la carte
modifiée en RAM sans avertissement (perte au prochain rechargement).

**Fix** : Le nouveau système unifié (`atelier_garde.js`) maintient un
**registre** `window.ATELIER_REGISTRE` peuplé par chaque sous-classe
de `AtelierEditeur` au moment de l'instanciation. Les **5** ateliers
(carte incluse) y sont enregistrés. La garde de sortie consulte ce
registre, donc la carte est désormais protégée.

### Bug 4 — UX hétérogène (intra-atelier confirm vs inter-atelier modale)

**Cause** : Deux pipelines parallèles avec deux UX différentes.

**Fix** : `AtelierEditeur.ouvrirItem`, `nouvelItem` et `fermerEditeur`
appellent maintenant `atelGardeAvantAction(this)`, qui utilise la
**même** modale 3 boutons que `atelGardeAvantTransition`. UX uniforme
partout.

## Architecture cible (post-v0.13.7.0c)

### Un seul fichier de garde

`static/atelier_garde.js` (NEW, ~210 lignes) expose 4 API :

```js
window.atelGardeEnregistrer(libelle, ref)
  // Appelé par chaque sous-classe à l'instanciation.
  // Ajoute { libelle, ref } à window.ATELIER_REGISTRE.

window.atelGardeDemander({ ateliersModifies, titre?, message? })
  // Affiche la modale 3 boutons. Retourne Promise<'sauvegarder'|'ignorer'|'annuler'>.

window.atelGardeAvantTransition(continuation)
  // Garde universelle pour transitions inter-ateliers.
  // Lit le registre, propose la modale, exécute continuation.

window.atelGardeAvantAction(atelier)
  // Garde locale pour transitions intra-atelier (changement d'item,
  // création, fermeture). Retourne Promise<bool> (true = continuer).
```

### Source de vérité unique

`window.ATELIER_REGISTRE` est la **seule** structure consultée. Elle
contient les 5 singletons OO. Un atelier est « modifié » si et
seulement si `ref.modifie === true`. La sauvegarde passe par
`ref.sauvegarder()`. Plus de snapshots, plus de handlers.

### Code retiré

| Fichier | Action |
|---|---|
| `static/atelier_garde_sortie.js` | **SUPPRIMÉ** (système snapshot obsolète) |
| `static/atelier_atome_generique.js` | **SUPPRIMÉ** (pipeline legacy court-circuité depuis la migration OO) |
| `static/app.js` L2858-L3571 (~700 lignes) | **SUPPRIMÉ** (bloc « Atelier Notion » + « Atelier Méthode », entièrement mort) |
| `static/app.js` L6558-L6616 (~60 lignes) | **SUPPRIMÉ** (DOMContentLoaded de branchement handlers historique) |

Bilan net : ~970 lignes de code et 2 fichiers de moins, pour un système
plus simple à comprendre.

## Fichiers livrés

```
appli/static/atelier_garde.js              [NEW]   210 lignes
appli/static/atelier_editeur.js            [MOD]   3 confirm() → atelGardeAvantAction
appli/static/atelier_carte_automatisme.js  [MOD]   + atelGardeEnregistrer
appli/static/atelier_exercice.js           [MOD]   + atelGardeEnregistrer, + 2 marquerModifie dans toggles
appli/static/atelier_notion.js             [MOD]   + atelGardeEnregistrer
appli/static/atelier_methode.js            [MOD]   + atelGardeEnregistrer
appli/static/atelier_fiche.js              [MOD]   + atelGardeEnregistrer
appli/static/app.js                        [MOD]   -700 lignes code mort notion+méthode, -60 lignes branchement
appli/templates/index.html                 [MOD]   + 13 oninput, scripts mis à jour
appli/doc/redemarrage_v0_13_7_0c.md        [NEW]

SUPPRIMÉS :
appli/static/atelier_garde_sortie.js
appli/static/atelier_atome_generique.js
```

## Vérifications

- Suite pytest : **3238 passed, 5 skipped, 0 failed** (identique au baseline)
- Sanity JS (`node -c`) sur les 8 fichiers JS modifiés : OK
- Audit refs orphelines vers fonctions/variables supprimées :
  - `atelRenderNotionListe`, `atelRenderMethodeListe` : référencés dans
    `atelier_etat_edition.js` mais résolus via `window[nom]` — les
    alias OO continuent de fournir ces noms. OK.
  - `atelNotionSauvegarder`, `atelMethodeSauvegarder` : référencés dans
    `rendu_atome.js` via `typeof X === 'function'`. Alias OO en place. OK.
  - `ATL_NOTION_SECTIONS`, `atelNotionRenderSections` : juste dans un
    commentaire HTML, actualisé.
  - `ATL_ATOME_CONFIG`, `atelAtomeNouveau/Charger/...` : juste dans des
    commentaires JS, actualisés.

## À tester chez toi

### Scénarios à valider sur les 5 ateliers (Exercice, Notion, Méthode, Fiche, Carte)

#### Scénario A — Badge « modifié »

1. Ouvrir un item existant.
2. Modifier un champ.
3. **Le badge « modifié » doit s'afficher dans la toolbar.** (Bug 1 corrigé.)
4. La console permet de vérifier : `ATELIER_NOTION.modifie` doit être `true`.

#### Scénario B — Changement d'item dans la sidebar

1. Modifier un item sans sauvegarder.
2. Cliquer sur un autre item dans la sidebar.
3. **La modale 3 boutons doit apparaître** (au lieu du confirm() natif binaire). (Bug 4 corrigé.)
4. Tester les 3 actions :
   - **Sauvegarder** : enregistre, puis bascule sur l'autre item.
   - **Ne pas sauvegarder** : badge éteint immédiatement, bascule sur l'autre item, **modifications perdues**.
   - **Annuler** : reste sur l'item actuel, badge toujours allumé.

#### Scénario C — Changement d'atelier (menu du haut)

1. Modifier un item sans sauvegarder.
2. Cliquer sur un autre onglet d'atelier dans le menu du haut.
3. La modale 3 boutons apparaît.
4. Tester les 3 actions, **notamment** :
   - **Ne pas sauvegarder** : doit RESET `this.modifie` et NE PAS faire revenir la modale à la transition suivante (Bug 2 corrigé).

#### Scénario D — Plusieurs ateliers modifiés en même temps

1. Modifier un exercice sans sauvegarder.
2. Aller dans l'atelier Notion (cliquer "Ne pas sauvegarder" si la modale apparaît, ou "Annuler" puis Sauvegarder à la main).
3. Modifier une notion sans sauvegarder.
4. Aller dans un troisième atelier.
5. **La modale doit lister Notion + Exercice si les deux sont modifiés** (et non un seul).
6. **« Ne pas sauvegarder » doit reset les flags des DEUX ateliers** (plus de modale infinie).

#### Scénario E — Carte (Bug 3 corrigé)

1. Modifier une carte sans sauvegarder.
2. Cliquer sur l'onglet « Exercice » dans le menu du haut.
3. **La modale 3 boutons doit apparaître** (avant elle n'apparaissait pas pour la carte). (Bug 3 corrigé.)

#### Scénario F — Création d'un nouvel item

1. Modifier un item sans sauvegarder.
2. Cliquer sur « + Nouvelle notion ».
3. La modale 3 boutons doit apparaître.

#### Scénario G — Fermeture éditeur

1. Modifier un item sans sauvegarder.
2. Cliquer sur le bouton « × » de fermeture de l'éditeur (s'il existe).
3. La modale 3 boutons doit apparaître.

## Limitations connues / restes pour la suite

### Côté garde de sortie (mineurs)

1. **Fermeture du navigateur / actualisation** : décision de v0.10.6
   (Q1-B) maintenue, pas de `beforeunload`. Si l'utilisateur ferme
   l'onglet sans sauvegarder, modifications perdues sans
   avertissement. Hors-périmètre.

2. **Wrappers exo morts dans `app.js`** (L2505-2519 environ) :
   `atelExoNouveau`, `atelExoCharger`, `atelExoSauvegarder`,
   `atelExoSupprimer` y restent définies. Elles appellent
   `window.atelAtomeNouveau()` (etc.) qui n'existe plus. **Mais** :
   ces 4 fonctions sont systématiquement écrasées par les alias OO de
   `atelier_exercice.js:643-646` (chargé après `app.js`), donc en
   pratique elles ne sont jamais effectivement appelées.

   Idem pour tout le bloc « Atelier Exercice » dans `app.js` (~600
   lignes mortes estimées, par analogie au bloc notion+méthode qu'on
   vient de supprimer). À nettoyer dans une livraison séparée.

3. **Bloc « Atelier Fiche »** : non audité dans cette livraison.

### Restes pour v0.13.7.0d (préparation à l'éditeur LaTeX)

1. **Factorisation des sections** (notion/méthode) dans `AtelierAtomique`.
   Cible initiale de v0.13.7.0b, repoussée car v0.13.7.0c a déjà
   consommé son quota de refactor.

2. **Nettoyage du bloc Exercice dans `app.js`** : à faire avec
   l'audit similaire au notion+méthode (alias par alias, variables
   globales, etc.).

3. **Nettoyage du bloc Fiche dans `app.js`** (s'il existe).

### Reste pour v0.13.7.1 (squelette éditeur LaTeX)

Cf. `doc/cadrage_v0_13_7_1_editeur_latex.md` (cadrage déjà validé).

## Points d'attention pour la validation

- **Performance** : le registre est consulté à chaque transition.
  Comme il contient 5 entrées, le coût est négligeable.
- **Ordre de chargement** : `atelier_garde.js` est chargé **avant** les
  classes d'ateliers (qui s'y enregistrent à leur instanciation). C'est
  garanti dans `templates/index.html` (modifié en conséquence).
- **Compat USB** : aucune dépendance externe, tout local. Inchangé.
