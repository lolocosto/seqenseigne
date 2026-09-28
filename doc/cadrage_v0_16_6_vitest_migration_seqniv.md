# Cadrage — v0.16.6 : Vitest + migration OO de l'atelier séquence (seqniv)

> **Statut** : cadrage à valider avant codage. Plus gros chantier technique du
> projet à ce jour. On introduit un filet de tests JS (Vitest) AVANT/PENDANT la
> migration des 2498 lignes procédurales.

## 1. Objectif et contexte

L'atelier d'assemblage **séquence-niveau** (`atelier_seqniv_assemblage.js`,
2498 lignes, procédural, 41 hooks `window.seqnivAsm*`) doit rejoindre la
hiérarchie OO `AtelierSeqnivAssemblage extends AtelierAssemblage extends
AtelierEditeur` — comme l'évaluation l'a fait.

**But final (demandé par Laurent)** : que la séquence ait le même appareil que
l'évaluation (badge modifié + enregistrer + garde + verrou validé = lecture
seule). Ces mécanismes vivent dans la base → la séquence doit en **hériter**,
d'où la migration OO comme préalable.

**Périmètre v0.16.6** : Vitest + migration OO **structurelle** (passer de
procédural à classe, sans changer le comportement). Le modèle mixte (snapshot
des champs critères/séances) et l'état validé de la séquence viendront APRÈS
(versions suivantes), une fois la classe en place et testée.

> Découpage volontaire : on ne mélange pas « migrer en OO » (changement
> structurel, comportement identique) et « ajouter l'appareil mixte/verrou »
> (changement de comportement). D'abord la fondation testée, puis les couches.

## 2. Champs vs structure (audit)

- **Champs de saisie** (→ futur snapshot, versions ultérieures) :
  - critères d'atteinte par objectif : `critere_F`, `critere_A`, `critere_E`
    (textareas, `onblur` → PATCH immédiat aujourd'hui) ;
  - nombre de séances : `nb_seances` (par objectif) et `nb_seances_R_AE` (par
    partie, pour Révisions/Approche) (`onblur` → PATCH immédiat).
- **Structure** (persistance immédiate, conservée) : parties, objectifs,
  placement de méthodes/notions/exos (R/EA et séries F/A/E), fiches, cartes,
  précédences.
- **État validé de la séquence** : N'EXISTE PAS aujourd'hui (pas de route
  `/etat`, pas de colonne). `/etat-ui` ne stocke qu'un état d'AFFICHAGE, pas une
  validation. → à créer dans une version ultérieure (avec le verrou).

En v0.16.6, critères et séances restent en persistance immédiate (comportement
inchangé) ; leur bascule en snapshot est un chantier ultérieur.

## 3. Vitest — introduction du filet JS

### 3.1 Décisions à valider

- ❓ **Où tournent les tests JS ?** Comme pytest : **côté sandbox** (Claude les
  exécute à chaque livraison ; Node 22 + npm 10 dispo). Laurent n'a PAS besoin
  de Node sur sa clé USB. Recommandation : oui, côté sandbox uniquement.
- ❓ **Quoi installer ?** `package.json` + `vitest` + `jsdom` (DOM simulé pour
  tester le rendu/handlers). `node_modules` NON livré dans le ZIP (volumineux) ;
  on livre `package.json` + `package-lock.json`, et on documente
  `npm install` + `npx vitest run`.
- ❓ **Périmètre des premiers tests** : prioriser la couche à risque — le DnD
  (registre source→cible) et les transitions d'état du module. Pas viser 100 %
  d'emblée.

### 3.2 Stratégie

Pour qu'une classe soit testable sous Vitest/jsdom, elle doit être
**importable** (ES module `export`) sans effet de bord au chargement (pas
d'`window.X = ...` exécuté à l'import). La migration OO facilite cela : la
classe est exportée, les hooks `window.*` deviennent de minces wrappers
installés par une fonction d'init explicite.

## 4. Migration OO — stratégie

### 4.1 Cible

```
AtelierEditeur
 └── AtelierAssemblage (estPluriel=false, persistanceImmediate=true, hooks
      │                 ajouter/retirer/deplacerElement, rendreContenuPrincipal)
      └── AtelierSeqnivAssemblage   ← À CRÉER
```

- État module (`DATA, OBJ_OUVERT, DRAG, CHARGEMENT, CRIT_DEFAUTS`) → champs
  d'instance (`this.data`, `this.objOuvert`, `this._drag`, …).
- ~40 fonctions internes → méthodes privées (`_rendreCentre`, `_rendrePartie`,
  `_rendreSidebar…`, handlers DnD…).
- 41 hooks `window.seqnivAsm*` → méthodes + wrappers globaux minces (comme
  `window.atelEval*` pour l'éval).

### 4.2 Réécriture HTML (décision déjà prise, §3.5 du cadrage d'unification)

Les `onclick`/`ondrag*`/`onblur` du rendu (générés en JS) passent à
`varGlobale.methode(...)`. Comme le HTML du seqniv est **généré dans le JS**
(pas dans index.html — sauf le conteneur), la réécriture se fait dans les
fonctions de rendu. Pas de shim de transition (décision Laurent).

### 4.3 Méthodes héritées vs spécifiques

- Hérité d'`AtelierEditeur`/`AtelierAssemblage` : cycle modifie/snapshot,
  majToolbar, garde-sortie, compilerRendu/viewer, basculerOnglet — **branchés
  plus tard** (modèle mixte). En v0.16.6, on conserve le comportement actuel.
- Spécifique seqniv : tout le rendu (centre + 3 modes de sidebar) et le DnD
  multi-source/cible (cf. `cadrage_dnd_assemblage_couche_epaisse.md` — on reste
  en couche SIMPLE : DnD privé au seqniv, pas de couche commune pour l'instant).

### 4.4 Inventaire des hooks (41) par nature

- **Navigation/onglet** : BasculerOnglet, OuvrirObj, FermerObj, EditerAtome,
  EditerFiche, ChargerSeqsPrec, TogglePrecPopover.
- **Champs (persistance immédiate, inchangée)** : ChangerCritere,
  ChangerSeancesObj, ChangerSeancesPartie, ChangerNom, ChangerFinCycle.
- **Structure** : NouvellePartie, SupprimerPartie, SupprimerObj,
  ActiverConnaitre, RetirerExoObj, RetirerExoRA, RetirerFiche, RetirerMethode,
  RetirerNotion, RetirerPrecedence, ValiderPrecedence.
- **DnD (≈18)** : DragStart{ExoCatalogue,ExoObj,ExoRA,FromSidebar,Methode,Obj,
  Partie}, DragOver{,Obj}, DragLeave{,Obj}, DragEnd, Drop{ExoObj,Fiche,Methode,
  Notion,Obj,RA}.

## 5. Découpage interne proposé (commits/étapes, 1 livraison)

Pour limiter le risque sur un fichier de 2498 lignes :
1. Mise en place Vitest (package.json, 1 test trivial qui passe).
2. Squelette `AtelierSeqnivAssemblage` : constructeur, état d'instance, chargement
   (`_rafraichir`/`_sn`), wrappers `window.seqnivAsm*` → instance. Le rendu et
   le DnD délèguent encore aux fonctions internes portées une à une.
3. Portage des fonctions de rendu en méthodes.
4. Portage des handlers (champs, structure, DnD) en méthodes + réécriture HTML
   généré (`varGlobale.X`).
5. Tests Vitest sur les morceaux à risque (DnD registre, transitions sidebar).
6. Nettoyage : suppression du procédural résiduel.

> Comportement INCHANGÉ à la fin : mêmes actions, même persistance immédiate.
> C'est une migration structurelle. Validation : zéro régression pytest +
> tests Vitest verts + validation visuelle de Laurent (le gros risque, faute de
> couverture JS exhaustive).

## 6. Risques & vigilance

- **2498 lignes, DnD multi-cible validé seulement visuellement** : risque
  principal. Vitest réduit le risque sur le DnD mais ne couvrira pas tout
  d'emblée. La validation visuelle de Laurent reste essentielle.
- **3 modes de sidebar** (aucun obj ouvert / obj « exo » ouvert / obj Connaître
  ouvert) : transitions à préserver à l'identique.
- **Précédences** (popover, validation) : sous-système spécifique à ne pas
  casser.
- **`let` top-level non attaché à window** (cf. learnings) : en passant en
  classe, attention aux accès par nom nu dans le HTML généré → tout doit passer
  par `varGlobale`.
- **Import sans effet de bord** pour Vitest : l'installation des `window.*` doit
  être dans une fonction d'init, pas au chargement du module.

## 7. Questions ouvertes pour Laurent

1. **Vitest côté sandbox uniquement** (Laurent n'installe pas Node) — OK ?
2. **`node_modules` hors ZIP** (on livre package.json + lock + doc
   `npm install`) — OK ? (Sinon le ZIP devient énorme.)
3. **Périmètre v0.16.6 = migration OO À COMPORTEMENT CONSTANT** (l'appareil
   mixte/verrou vient APRÈS) — confirmes-tu ce découpage ?
4. **Nom de la variable globale** d'instance : `ATELIER_SEQNIV` (cohérent avec
   `ATELIER_EVALUATION`) ?
