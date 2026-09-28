# Cadrage — Unification OO des ateliers d'assemblage

> **Statut** : document de cadrage, à relire/annoter avant toute décision de
> codage. Aucune ligne de code ne sera écrite avant validation des choix
> marqués ❓ ci-dessous.
>
> **Principe directeur (donné par Laurent)** : ce sont conceptuellement DEUX
> ateliers d'assemblage. On part de la base commune comme objectif, on
> identifie les divergences, et on les résout pour permettre cette base — pas
> l'inverse.

## 1. Point de départ (état vérifié du code)

| Atelier | Fichier | Style | Hiérarchie |
|---|---|---|---|
| Assemblage évaluation | `atelier_evaluation_oo.js` (53 Ko) | **OO** | `AtelierEvaluation extends AtelierAssemblage extends AtelierEditeur` |
| Assemblage séquence-niveau | `atelier_seqniv_assemblage.js` (105 Ko) | **Procédural** (IIFE) | aucune — totalement indépendant |
| Base d'assemblage | `atelier_assemblage.js` (192 lignes) | OO, mince | `extends AtelierEditeur` |
| Ancien éval (mort) | `atelier_evaluation.js` (51 Ko) | Procédural | non chargé |

**Fait majeur** : `AtelierAssemblage` a **déjà été conçu pour les deux**. Sa
docstring de constructeur cite explicitement « Cas : Évaluation » ET « Cas :
Livret » (= seqniv) pour ses flags `estPluriel` et `persistanceImmediate`. La
base commune n'est donc pas à inventer : elle est esquissée et attend que le
seqniv la rejoigne. Aujourd'hui elle ne sert qu'à l'évaluation.

## 2. Ce qui est déjà commun (dans `AtelierAssemblage`)

La base mince expose 4 hooks pensés pour les deux :

- `ajouterElement(type, payload)` — ajouter un composant à l'item actif.
- `retirerElement(type, id)` — retirer un composant.
- `deplacerElement(type, id, delta)` — réordonner (flèches, alternative au DnD).
- `rendreContenuPrincipal(item)` — rendre le panneau central (abstrait).

Plus deux axes de configuration déjà prévus :

- `estPluriel` : sidebar avec liste de N items (éval) **vs** un seul item par
  scope déterminé par les filtres (seqniv/livret).
- `persistanceImmediate` : chaque opération persiste atomiquement, pas de bouton
  Enregistrer, `this.modifie` toujours `false` (seqniv) **vs** snapshot +
  bouton Enregistrer (éval).

C'est exactement l'axe de divergence principal entre les deux ateliers, et il
est **déjà paramétré**. Bon signe pour l'unification.

## 3. Inventaire des divergences à résoudre

### 3.1 Modèle de persistance ⭐ (divergence structurante)

| | Évaluation | Seqniv |
|---|---|---|
| Persistance | Snapshot + bouton Enregistrer (`persistanceImmediate=false`) | Immédiate par opération (DnD = PATCH direct) |
| `this.modifie` | suit le snapshot | toujours false |
| Pluralité | `estPluriel=true` (liste d'évals) | un seul item (séquence courante via filtres) |

→ La base gère déjà les deux modes. **À vérifier** : que le seqniv, une fois en
OO, configure bien `persistanceImmediate=true` + `estPluriel=false` et que le
comportement résultant soit correct (pas de bouton Enregistrer fantôme, pas de
snapshot inutile).

### 3.2 Complexité du drag-and-drop ⭐ (divergence majeure)

C'est **LA** vraie divergence. Le DnD du seqniv est d'un autre ordre de
grandeur :

- **Évaluation** : DnD simple — ajouter/retirer/réordonner des exos dans une
  liste plate. Couvert par `ajouterElement/retirerElement/deplacerElement`.
- **Seqniv** : DnD **multi-source × multi-cible** avec 43 hooks `window.seqnivAsm*`
  et ~96 fonctions internes. Sources : parties, objectifs, méthodes, exos
  (catalogue / RA / par série), fiches, notions. Cibles : zones R/EA de partie,
  séries F/A/E d'objectif, objectif Connaître. Plus **3 modes de sidebar** selon
  l'état (aucun objectif ouvert / objectif « exo » ouvert / objectif Connaître
  ouvert) et un système de **précédences** (popover, validation).

→ **DÉCISION (Laurent)** : **couche DnD SIMPLE d'abord** — Option A. La base
   reste mince (`ajouterElement/retirerElement/deplacerElement`), le DnD riche
   du seqniv est porté en méthodes privées dans `AtelierSeqnivAssemblage`. La
   couche « épaisse » (factorisation poussée du DnD) fait l'objet d'un cadrage
   séparé : `cadrage_dnd_assemblage_couche_epaisse.md`, à instruire plus tard.

### 3.3 Duplication éval ↔ base (dette à résorber au passage)

`AtelierEvaluation` réimplémente en propre des choses qui existent (ou
devraient exister) plus haut : `_api`, `_toast`, `_esc`, `compilerRendu`,
`_afficherErreurCompilation`, `toggleTexBrut`, `_afficherTexBrut`,
`scrollToLigneTex`, `voirLatex`. Plusieurs ont un équivalent dans
`AtelierEditeur`.

→ ❓ À décider : profiter de la refonte pour **remonter** ces helpers
   (rendu PDF, toast, échappement, API) dans `AtelierEditeur`/`AtelierAssemblage`
   et supprimer les copies de l'évaluation. C'est la vraie réduction de dette.

### 3.4 API backend (pas un obstacle)

- Seqniv : `/api/v2/sequences-par-niveau/<niveau>/<seq>` (PATCH granulaires).
- Éval : `/api/evaluations` + `/<id>` + `/<id>/rendu-pdf`.

Formes différentes mais **structurellement parallèles** (mêmes verbes, même
découpage item → composants → ordre). Compatibles avec le contrat
`endpointBase` + `endpointRenduPdf` de la base.
→ **VERDICT (analyse v0.16)** : aucune refonte backend nécessaire. La seule
   différence est dimensionnelle : le seqniv a une hiérarchie plus profonde
   (séquence → parties → objectifs → exos par série + précédences) là où l'éval
   est plat (évaluation → exos). Les sous-chemins profonds du seqniv
   s'expriment via ses méthodes privées (et la couche épaisse), sans contrarier
   le contrat commun. Table de correspondance des API dans le doc couche épaisse.

### 3.5 Hooks `window.*` vs méthodes de classe

Le seqniv expose 43 `window.seqnivAsm*` (appelés depuis le HTML via `onclick`/
`ondrag*`). En OO, ces handlers deviennent des méthodes, mais le HTML statique
(`templates/index.html`) les appelle par nom global.

→ ❓ Choix de transition : (a) un shim `window.seqnivAsmX = () => instance.X()`
   pour ne pas toucher le HTML, ou (b) réécrire les `onclick` du template vers
   `varGlobale.X(...)` comme les ateliers d'atomes. (b) est plus propre mais
   touche beaucoup de HTML. Recommandation : (a) en transition, (b) à terme.

## 4. Cible d'architecture proposée

```
AtelierEditeur  (rendu PDF + viewer pdf.js, cache, save/delete, toolbar…)
   └── AtelierAssemblage  (estPluriel, persistanceImmediate, 3 hooks composants)
          ├── AtelierEvaluation        (existe — à alléger des duplications)
          └── AtelierSeqnivAssemblage  (À CRÉER — migration du procédural)
```

Le viewer pdf.js (v0.16) vit dans `AtelierEditeur._afficherPdfDansViewer`. Une
fois les deux assemblages en OO et héritant proprement du rendu, **les deux
bénéficient automatiquement du viewer** — c'est l'occasion de brancher le PDF
inline forcé sur les assemblages (cf. §6).

## 5. Plan de migration proposé (séquencé, réversible)

Chaque étape = livraison validable, zéro régression.

1. **Nettoyage préalable** ✅ **FAIT (v0.16.1)** : `atelier_evaluation.js` (mort,
   51 Ko) supprimé. Garde-fou de test verrouillant son absence sur disque.
2. **Consolidation de la base** : remonter dans `AtelierEditeur`/`AtelierAssemblage`
   les helpers que l'évaluation duplique (rendu PDF d'abord — celui qui ouvre le
   viewer ; puis toast/esc/api). Alléger `AtelierEvaluation`. **Prérequis** :
   aligner les IDs HTML de l'évaluation sur la convention `<prefixe>-<suffixe>`
   et remplacer ses 48 `getElementById` par `this.$()`. Tests OO garde-fou.
   **Inclut le modèle de persistance mixte** (cf. §5ter). *(Touche JS +
   template ; périmètre dédié — cf. redemarrage_v0_16_1.md.)*
2bis. **Aperçu PDF au survol** (livraison dédiée, après l'étape 2) : dans
   `AtelierAssemblage`, afficher le rendu PDF d'un atome compilé dans une modale
   au survol, après un délai de latence (1-2 s). **Stratégie hybride** : au
   survol on interroge `GET .../rendu-pdf/info` (cache-check, sans compiler) ;
   si en cache → affichage immédiat dans la modale (viewer pdf.js) ; sinon →
   indicateur « non compilé » + bouton « générer l'aperçu » (déclenche
   `POST .../rendu-pdf`). Réutilise `_afficherPdfDansViewer` (v0.16). Gestion de
   l'annulation au `mouseleave` et anti-empilement via le compteur de génération
   `_genRendu` existant. L'évaluation en bénéficie dès cette livraison ; le
   seqniv automatiquement après sa migration (étapes 3-4). Détail §6bis.
3. **Migration seqniv en OO — squelette** : créer `AtelierSeqnivAssemblage extends
   AtelierAssemblage` avec `estPluriel=false`, `persistanceImmediate=true`,
   `rendreContenuPrincipal` qui reprend le rendu central existant. État
   (`DATA/OBJ_OUVERT/DRAG`) devient des champs d'instance. **Réécriture HTML (b)
   décidée** : les `onclick`/`ondrag*` du template passent à
   `varGlobale.methode(...)`, pas de shim de transition.
4. **Migration seqniv — DnD** : porter les handlers drag/drop (le gros morceau)
   en méthodes privées (couche simple, décision §3.2). **Tests JS (Vitest)
   introduits ici** (décision validée) pour sécuriser la migration DnD.
5. **Branchement viewer PDF** sur les deux assemblages (cf. §6).
6. **Nettoyage final** : factoriser ce qui s'est révélé réellement commun
   pendant la migration. Évaluer le GO/NO-GO de la couche DnD épaisse
   (cf. `cadrage_dnd_assemblage_couche_epaisse.md`).

## 5bis. Aperçu PDF au survol — détail (étape 2bis)

**Déclencheur** : `mouseenter` sur une ligne d'atome (`.atl-item-row` ou
équivalent), portant `data-atome-type` + `data-atome-id` (à ajouter au rendu).
Listener **délégué** sur le conteneur (un seul listener, robuste au
re-render).

**Séquence** :
1. `mouseenter` → arme un `setTimeout(délai)`. Délai configurable
   (`config.delaiApercuMs`, défaut 1500 ms ?).
2. `mouseleave` (ou survol d'un autre atome) avant la fin → `clearTimeout`,
   rien ne se passe. Anti-empilement : un seul timer actif à la fois.
3. À l'expiration → `GET /api/atomes/<type>/<id>/rendu-pdf/info` :
   - `depuis_cache=1` → ouvrir la modale, charger le PDF via le viewer
     (réutilise `_afficherPdfDansViewer`).
   - sinon → modale avec « Aperçu non généré » + bouton « Générer »
     (`POST .../rendu-pdf` puis affichage).
4. Course : incrémenter `_genRendu` à chaque déclenchement ; ignorer toute
   réponse dont la génération n'est plus la courante (souris déjà repartie).

**Modale** : flottante, positionnée près du curseur ou ancrée à droite du
panneau. Fermeture au `mouseleave` de la zone atome+modale, ou à l'`Escape`.
À décider : modale unique réutilisée (créée une fois dans le DOM) vs recréée.

**Points ouverts** :
- Délai exact (1 s ? 1,5 s ? 2 s) — à régler à l'usage.
- Taille/position de la modale (tooltip compact vs panneau large).
- Faut-il un mode « épinglé » (clic = garder la modale ouverte) ?

## 5ter. Modèle de persistance MIXTE (étape 2)

**Décision (Laurent)** : dans un atelier d'assemblage, deux régimes coexistent
selon la nature de ce qu'on modifie :

| Nature de la modification | Régime | Comportement |
|---|---|---|
| **Champ de saisie** (titre, barème, nb séances, critères, points langue française, nom d'objectif…) | **Snapshot** | Badge « modifié » + activation auto du bouton Enregistrer + garde à la sortie de l'atelier. Comme les ateliers d'atomes. |
| **Opération d'assemblage** (ajout / suppression / réordonnancement d'un élément composant) | **Immédiat** | Sauvegarde auto atomique (PATCH direct), pas de badge. |

C'est une **évolution du modèle actuel** d'`AtelierAssemblage`, où
`persistanceImmediate` est un flag tout-ou-rien par atelier. On passe à une
distinction **par type d'action**, pas par atelier :

- la **structure** (composants ajoutés/retirés/réordonnés) persiste immédiatement ;
- les **champs** entrent dans le cycle snapshot/`marquerModifie`/Enregistrer
  hérité d'`AtelierEditeur`.

**Conséquence sur le barème (décidée)** : aujourd'hui `sauverBareme` fait un
PATCH immédiat. Il doit passer en régime « champ » → ne plus sauver à la frappe,
mais marquer modifié et n'être persisté qu'à l'Enregistrer. Idem pour tous les
`onchange`/`oninput` de champs de l'évaluation et (après migration) du seqniv.

**Implémentation pressentie** : remplacer le flag binaire `persistanceImmediate`
par une distinction au niveau des méthodes — les `ajouter/retirer/deplacerElement`
restent immédiats (ils touchent la structure), tandis que les handlers de champ
appellent `marquerModifie()` et la sauvegarde groupée passe par `sauvegarder()`
hérité. Le getter `modifie` redevient significatif (snapshot des champs), même
si des opérations de structure ont eu lieu entre-temps.

**Point de vigilance** : bien distinguer, à la sortie de l'atelier, « des champs
non enregistrés » (→ garde, confirmation) de « des opérations de structure déjà
persistées » (→ rien à signaler). La garde ne doit se déclencher que pour les
champs en attente.

## 6. Viewer PDF dans les assemblages (rappel v0.16)

État actuel : les assemblages affichent encore le PDF via `iframe.src = blob`
direct, donc **non couverts** par le viewer pdf.js de v0.16 (volontairement
hors périmètre).

- Éval : `atelier_evaluation_oo.js` ~lignes 1104-1106.
- Seqniv : `atelier_seqniv_assemblage.js` ~lignes 2361 (`#zoom=page-width`),
  2417, 2491.

→ Une fois les deux en OO et héritant du rendu d'`AtelierEditeur`, le passage au
viewer se fait « gratuitement » via `_afficherPdfDansViewer`. Le seqniv utilise
`#zoom=page-width` : à reporter en option d'ouverture pdf.js
(`?file=...#zoom=page-width` reste supporté par le viewer).

## 7. Risques & points de vigilance

- **DnD seqniv = cœur du risque.** 105 Ko de logique drag/drop multi-cible,
  validée visuellement (pas de tests JS automatisés aujourd'hui). Une migration
  OO sans filet de test JS est risquée → cf. point suivant.
- **Absence de tests JS** : la roadmap mentionne Vitest/Jest comme candidat. Ce
  chantier est un **bon déclencheur** : au minimum des tests sur la couche DnD
  (registre source/cible, transitions de mode sidebar) avant/pendant la
  migration. ❓ À décider : introduit-on Vitest à cette occasion ?
- **3 modes de sidebar** : transitions d'état à préserver à l'identique.
- **Précédences** (popover, validation) : sous-système spécifique seqniv, à ne
  pas casser.
- **Cartes d'automatisme en lecture seule** dans le rendu de partie (zone
  v0.13.6.3.2) : dépendance à préserver.

## 8. Questions ouvertes — DÉCISIONS (arbitrées par Laurent)

1. **DnD** → **Couche DnD SIMPLE d'abord** (au moins en première intention).
   Un second doc de cadrage couvre la couche « épaisse » (DnD riche du seqniv) :
   voir `cadrage_dnd_assemblage_couche_epaisse.md`.
2. **Duplications éval** → **`AtelierAssemblage` hérite déjà d'`AtelierEditeur`**
   (c'est le cas) et on **exploite à fond cet héritage** : les saisies (barème,
   nombre de séances par objectif, critères…) et les helpers communs (rendu PDF,
   toast, API, échappement) remontent dans la base pour être réutilisés. On
   allège `AtelierEvaluation` de ses copies.
3. **API backend** → compatibles. Les deux API sont structurellement parallèles
   (mêmes verbes, même découpage item→composants→ordre) ; la seule différence
   est dimensionnelle (seqniv = hiérarchie plus profonde séquence→parties→
   objectifs→exos/série ; éval = plat évaluation→exos). Aucune refonte backend
   nécessaire. Le contrat `endpointBase` de la base suffit ; le seqniv aura des
   sous-chemins plus profonds, exprimables via les hooks (et la couche épaisse).
4. **Hooks `window.*`** → **réécriture HTML (b) dès maintenant**, pas de shim de
   transition. Les `onclick`/`ondrag*` du template passent à
   `varGlobale.methode(...)` comme les ateliers d'atomes. Pas de demi-mesure.
5. **Découpage** → **une livraison par étape** du plan §5.

> Les recommandations provisoires antérieures de cette section sont remplacées
> par ces décisions.
```
