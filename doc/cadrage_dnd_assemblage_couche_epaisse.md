# Cadrage — Couche DnD « épaisse » des ateliers d'assemblage

> **Statut** : cadrage différé. Le chantier d'unification des assemblages
> démarre avec une couche DnD **simple** (cf.
> `cadrage_unification_ateliers_assemblage.md`, décision §8.1). Ce document
> prépare une éventuelle factorisation **poussée** du drag-and-drop, à
> instruire plus tard, une fois le seqniv migré en OO et le DnD riche stabilisé
> en méthodes privées.
>
> **Pourquoi différer** : on ne factorise bien que ce qu'on a sous les yeux,
> stabilisé. Extraire une couche DnD générique AVANT d'avoir porté le DnD du
> seqniv en OO, c'est concevoir l'abstraction à l'aveugle. On code d'abord le
> DnD simple + le DnD seqniv en privé, PUIS on regarde ce qui se factorise.

## 1. Ce qu'est la couche « simple » (point de départ)

La base `AtelierAssemblage` expose 3 hooks neutres :
`ajouterElement(type, payload)`, `retirerElement(type, id)`,
`deplacerElement(type, id, delta)`. L'évaluation les implémente pour un DnD
plat (exos dans une liste). Le seqniv implémente son DnD riche en **méthodes
privées** (`_dragStart*`, `_drop*`, `_dragOver*`), sans rien exposer à la base.

C'est suffisant et correct. La couche épaisse n'est justifiée que si la
duplication de tuyauterie DnD entre les deux ateliers devient gênante — ce qui
reste à prouver après migration.

## 2. Anatomie du DnD seqniv (le candidat à factoriser)

### 2.1 Transport

État unique `DRAG = {kind, ...payload}` où `kind ∈ {methode, exo, partie, obj}`.
Chaque `drop` lit `DRAG.kind` et décide s'il accepte. C'est un transport typé :
la cible filtre par type de source.

### 2.2 Sources (7 `dragStart`)

| Source | `kind` | Payload |
|---|---|---|
| Méthode (sidebar) | `methode` | `methode_id`, `libelle` |
| Exo catalogue | `exo` | `exercice_id`, provenance catalogue |
| Exo RA (révision/approche) | `exo` | `exercice_id`, type R/EA |
| Exo objectif | `exo` | `exercice_id`, série F/A/E |
| Objectif | `obj` | `objectif_id`, partie source |
| Partie | `partie` | `partie_id`, ordre |
| Depuis sidebar (générique) | (selon item) | variable |

### 2.3 Cibles (6 `drop`)

| Cible | Accepte | Effet |
|---|---|---|
| Partie (zone objectif) | `methode` | crée un objectif lié à la méthode |
| Partie (zone R/EA) | `exo` | ajoute exo en révision/approche |
| Objectif (série F/A/E) | `exo` | ajoute exo à la série |
| Objectif (notions) | `notion` | lie une notion |
| Objectif (fiche) | `fiche` | lie une fiche |
| Objectif Connaître | `obj`/`exo` | attachement spécifique |

### 2.4 Règles transverses

- **3 modes de sidebar** selon l'état (aucun objectif ouvert / objectif « exo »
  ouvert / objectif Connaître ouvert) — le contenu draggable change selon le
  mode.
- **Réordonnancement** intra-zone (parties entre elles, objectifs dans une
  partie, exos dans une série) via `dragOver` calculant l'index d'insertion.
- **Précédences** : sous-système à part (popover), pas du DnD pur.

## 3. Forme possible d'une couche générique (hypothèse à valider)

Si factorisation il y a, la forme naturelle serait un **registre déclaratif**
porté par `AtelierAssemblage` :

```
this.enregistrerDnD({
  source: 'methode',
  ciblesAcceptees: ['partie-objectif'],
  surDrop: (cible, payload) => this.ajouterElement('objectif-depuis-methode', …),
});
```

La base gérerait alors `dragstart/dragover/dragleave/drop/dragend` de façon
générique (mise en surbrillance des cibles valides, calcul d'index
d'insertion), et chaque atelier ne déclarerait que ses couples source→cible +
effets. L'évaluation aurait 1-2 déclarations triviales ; le seqniv une dizaine.

**Bénéfice potentiel** : surbrillance/feedback visuel des cibles valides
mutualisé, calcul d'index d'insertion unique, moins de code répétitif.
**Risque** : sur-abstraction. Si les effets de drop du seqniv sont tous
spécifiques, le registre n'économise que le boilerplate `dragover/leave`, pas
la logique métier — gain faible pour une indirection en plus.

## 4. Critère de décision (à appliquer après migration)

Après avoir porté le DnD seqniv en méthodes privées (couche simple), mesurer :

1. **Combien de lignes de tuyauterie DnD pure** (hors logique métier) sont
   identiques entre éval et seqniv ? Si marginal → ne pas factoriser.
2. **Le feedback visuel** (surbrillance cible valide, ligne d'insertion) est-il
   réimplémenté deux fois ? Si oui → candidat solide à la mutualisation.
3. **Les tests JS** (si introduits) seraient-ils plus simples avec un registre
   testable indépendamment ? 

→ Décision GO/NO-GO sur la couche épaisse à prendre à ce moment-là, chiffres en
main, pas avant.

## 5. Annexe — Correspondance des API d'assemblage

Confirme la compatibilité backend (cf. doc unification §3.4). Structurellement
parallèle, différence seulement dimensionnelle.

| Opération | Évaluation | Seqniv |
|---|---|---|
| Item racine | `/api/evaluations/<id>` | `/api/v2/sequences-par-niveau/<sn_id>` |
| Ajouter exo | `POST …/exos` | `POST …/objectifs/<id>/exos` (par série) |
| Retirer exo | `DELETE …/exos/<id>` | `DELETE …/objectifs/<id>/exos/<serie>/<id>` |
| Réordonner exos | `…/exos/reordonner` | `…/objectifs/<id>/exos/<serie>/ordre` |
| Ajouter objectif | `POST …/objectifs` | `POST …/parties/<id>/objectif` |
| Retirer objectif | `DELETE …/objectifs/<id>` | (via objectif) |
| Réordonner objectifs | — | `…/parties/<id>/objectifs/ordre` |
| Item intermédiaire | (aucun — plat) | `parties` (POST/PATCH/DELETE) |

Le seqniv a un niveau intermédiaire (`parties`) absent de l'éval, et des exos
**typés par série** (F/A/E) ou **par zone** (R/EA). C'est la profondeur
hiérarchique, pas une divergence de paradigme.
