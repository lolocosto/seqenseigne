# Redémarrage v0.16.7 — Migration OO du seqniv (classe AtelierSeqnivAssemblage)

## Contexte

Second et dernier pas du chantier de migration OO de l'atelier d'assemblage
séquence-niveau (seqniv). Le découpage en deux pas sûrs (décision Laurent) :

- **v0.16.6** : introduction de Vitest (filet JS) + extraction de la logique
  **pure** dans `static/seqniv_pur.js` (module testé), que le seqniv procédural
  *utilisait* désormais. Comportement strictement identique.
- **v0.16.7 (ce document)** : migration OO **structurelle**. L'IIFE procédural
  (état module `DATA/OBJ_OUVERT/DRAG/…`, ~30 fonctions internes, 43 hooks
  `window.seqnivAsm*`) devient une classe `AtelierSeqnivAssemblage extends
  AtelierAssemblage`, instance unique `window.ATELIER_SEQNIV`. Réutilise le
  module pur déjà testé. **Comportement strictement identique.**

Cf. `cadrage_v0_16_6_vitest_migration_seqniv.md`. La cible OO y était spécifiée
(« AtelierSeqnivAssemblage extends AtelierAssemblage », migration à comportement
constant, appareil verrou/mixte reporté à APRÈS).

## Décisions actées (questions de cadrage)

- **P1** — Variable globale d'instance : `window.ATELIER_SEQNIV` (cohérent avec
  `window.ATELIER_EVALUATION`).
- **P2** — Wrappers globaux renommés `window.atelSeqniv*` (style `atelEval*`).
- **P3** — Le HTML généré (et les 2 boutons d'onglet statiques) appelle
  `ATELIER_SEQNIV.methode(...)` directement, plus de nom nu.
- **P4** — Périmètre = « le moins risqué pour les régressions ». Tranché :
  migration **complète et mécanique en un seul ZIP** (pas de demi-portage, qui
  créerait une frontière fragile entre `this.data` et `DATA`). Filet : pytest
  inchangé + Vitest étendu + validation visuelle Laurent.

## Ce qui est livré

### La classe AtelierSeqnivAssemblage

- `static/atelier_seqniv_assemblage.js` — entièrement réécrit en classe OO
  (≈ 2520 lignes). `class AtelierSeqnivAssemblage extends AtelierAssemblage`,
  config `super()` : `id:'seqniv'`, `prefixe:'liv-atl'`, `estPluriel:false`,
  `persistanceImmediate:true`.
  - **État module → champs d'instance** : `DATA→this.data`,
    `OBJ_OUVERT→this.objOuvert`, `DRAG→this._drag`,
    `CHARGEMENT→this._chargement`, `CRIT_DEFAUTS→this._critDefauts`,
    `ASM_ONGLET→this._onglet`, `LIVRET_SEQ_BLOB_URL→this._livretBlobUrl`,
    `LIVRET_SEQ_DERNIER_LOG→this._livretDernierLog`.
  - **Fonctions internes `_*` → méthodes privées** (mêmes noms).
  - **Hooks `window.seqnivAsm*` → méthodes** (préfixe `seqnivAsm` retiré :
    `seqnivAsmOuvrirObj` → `ouvrirObj`, etc.) + **wrappers globaux
    `window.atelSeqniv*`** en bas de fichier, délégant à l'instance.
  - **Helper réseau `apiJson`** : fonction module-level (sans état), partagée
    par les méthodes.
  - **Logique pure** : toujours déléguée à `window.SeqnivPur` via la constante
    module `_PUR` (capturée à l'exécution de l'IIFE — seqniv_pur.js chargé
    avant).
  - **DnD des parties** : les listeners (attachés via `addEventListener` dans
    `_brancherDragParties`) passent désormais par des fonctions fléchées
    capturant `this`, avec la carte de partie passée en argument (au lieu de
    `this`=élément DOM dans le procédural). Comportement identique.

### Hook public conservé (compat app.js)

- `window.seqnivAssemblageRafraichir()` — appelé par `app.js` (≈ ligne 2990) à
  chaque ouverture / changement de séquence. **Conservé tel quel**, délègue à
  `ATELIER_SEQNIV.rafraichir()`. `app.js` n'a PAS été modifié.

### Ordre des scripts (index.html)

- `seqniv_pur.js` et `atelier_seqniv_assemblage.js` **déplacés** : ils étaient
  chargés AVANT `atelier_editeur.js`/`atelier_assemblage.js` (OK en procédural,
  KO en OO car `extends AtelierAssemblage` exige la parente d'abord). Désormais
  chargés juste APRÈS `atelier_assemblage.js`, dans l'ordre
  `seqniv_pur.js` → `atelier_seqniv_assemblage.js`.
- Les 2 boutons d'onglet statiques (`#asm-tab-btn-edition`/`-rendu`) appellent
  désormais `ATELIER_SEQNIV.basculerOnglet(...)` (étaient
  `seqnivAsmBasculerOnglet(...)`).

### Garde de sortie : inchangée (rien à protéger)

Le seqniv est en **persistance immédiate** (`persistanceImmediate:true`) : son
getter `modifie` reste toujours `false`. Comme le code procédural historique,
il **ne s'enregistre PAS** dans `window.ATELIER_REGISTRE` (garde de sortie). Le
branchement de l'appareil verrou/mixte (comme l'évaluation) est reporté à une
version dédiée ultérieure, maintenant que la classe est en place.

### Tests JS étendus

- `tests_js/atelier_seqniv_assemblage.test.js` — **nouveau** (27 tests). Charge
  toute la chaîne d'héritage (atelier.js → atelier_editeur.js →
  atelier_assemblage.js → seqniv_pur.js → atelier_seqniv_assemblage.js) dans
  jsdom, instancie la classe, et couvre les zones à risque de la migration :
  - contrat OO (héritage, `persistanceImmediate`, `modifie===false`, hook
    `seqnivAssemblageRafraichir` conservé, wrappers `atelSeqniv*`) ;
  - **registre DnD** (`this._drag`) : armement par chaque `dragStart*`, lecture
    du payload JSON de la sidebar, réinitialisation par `dragEnd` ;
  - **filtre d'autorisation `dragOver`** (couples type-de-drag / type-de-zone) ;
  - **aiguillage des 3 modes de sidebar** (objets fermés / objectif exo /
    objectif Connaître, + repli sur mode 1 si id inconnu) ;
  - délégation à `SeqnivPur` sur `this.data`.
- `package.json` : version bumpée à 0.16.7.
- **Les tests JS ne sont PAS requis au déploiement** (clé USB sans Node).
  `node_modules/` et `package-lock.json` NE sont PAS dans le ZIP. Pour lancer :
  `npm install` puis `npm test` (ou `npx vitest run`).

## Tests

- **pytest** : 3774 passed, 7 skipped, 0 failed (backend non touché — baseline
  v0.16.6 intacte).
- **Vitest** : 47 passed (2 smoke + 18 seqniv_pur + 27 nouveaux).
- **Syntaxe** : `node --check static/atelier_seqniv_assemblage.js` OK.

## Vérifié

- Les 46 hooks/comportements de l'original ont leur méthode équivalente dans la
  classe (mapping nom complet vérifié programmatiquement).
- Aucun résidu d'ancien nom nu (`seqnivAsm`, accès direct à `DATA`/`OBJ_OUVERT`/
  `DRAG`/…) dans le code de la classe (les seules occurrences restantes sont
  dans des commentaires descriptifs).
- Aucun appelant externe (grep dans tout `static/` + `templates/`) n'utilise
  encore `seqnivAsm*` après mise à jour des 2 boutons statiques.
- Le HTML généré appelle `ATELIER_SEQNIV.*` partout (75 appels).

## À déployer / vérifier côté Windows (validation visuelle)

Le DnD multi-cible (méthode→partie, exo→zone R/EA/série, notion→objectif,
fiche→Connaître, réordonnancement objectifs et parties) n'est validé que
visuellement. Points à re-tester sur l'infra réelle :

1. Ouverture de l'atelier sur une séquence peuplée (N10/N11/N12) → rendu centre
   + sidebar mode 1.
2. Glisser une méthode sur une partie → création d'objectif + ouverture +
   sidebar mode 2.
3. Ouvrir/fermer un objectif exo (sidebar mode 2) et l'objectif Connaître
   (sidebar mode 3, zone fiches).
4. Glisser exos F/A/E, notions, fiches ; retirer ; réordonner objectifs
   (intra + inter-partie) ; réordonner parties.
5. Précédences : popover, ajout, retrait ; zone Révision activée.
6. Onglet Rendu PDF : compiler livret, voir .tex, compiler plan de travail.
7. Changer de séquence → l'onglet Rendu PDF est bien réinitialisé.

## Suite (roadmap)

- Appareil verrou/mixte du seqniv (enregistrement dans la garde, comme
  l'évaluation) — désormais possible puisque la classe est en place.
- Reste de la roadmap v0.15+ inchangé.
