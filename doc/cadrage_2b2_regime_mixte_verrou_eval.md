# Cadrage — v0.16.5 (2b-2) : régime de persistance mixte + verrou UI de l'évaluation

> **Statut** : cadrage à valider avant codage. Chantier JS dense, sans tests JS
> dans le dépôt → on s'appuie sur des tests structurels Python + validation
> visuelle de Laurent.

## 1. Objectif

Deux chantiers qui convergent (ils dépendent tous deux du `<form>` +
`collecterFormulaire`) :

1. **Régime de persistance mixte** (cf. `cadrage_etape2_consolidation_base.md`
   §2b et `cadrage_unification_ateliers_assemblage.md` §5ter) :
   - **Champs de saisie** (titre, mode, afficher-barème, langue-points, **barème
     par exo**) → régime snapshot : badge « modifié » + bouton Enregistrer actif
     + garde à la sortie. Comme les atomes.
   - **Opérations de structure** (ajout/retrait/réordo d'exo & d'objectif) →
     sauvegarde auto immédiate (déjà le cas), PAS de badge.
2. **Verrou UI lecture seule de l'évaluation** (suite de v0.16.4, où seul le
   backend protégeait l'éval) : quand l'éval est validée, griser les champs ET
   masquer/désactiver les actions de structure.

## 2. État actuel

- L'éval a un `modifie` **surchargé** par un flag manuel `_modifieFlag` (≈12
  points d'accroche) car il n'y avait pas de `<form id="atl-eval-form">`.
- Les barèmes se sauvent **immédiatement** via `sauverBareme` (PATCH par champ,
  `onchange`).
- L'endpoint **barèmes groupés** `PATCH /api/evaluations/<id>/baremes` existe
  (v0.16.3) mais n'est pas encore consommé.
- Le verrou backend (409) couvre déjà l'éval (v0.16.4) ; l'UI éval reste
  éditable et affiche un toast sur 409.

## 3. Conception

### 3.1 Le `<form id="atl-eval-form">`

Envelopper le contenu de `atl-eval-tab-edition` (titre, mode, afficher-barème,
langue-points, liste d'exos avec leurs barèmes, liste d'objectifs) dans un
`<form id="atl-eval-form" onsubmit="return false">`. Cela permet à
`_installerListenerForm` (base) de capter les `input`/`change` et de mettre à
jour la toolbar (badge + bouton save) automatiquement.

### 3.2 `collecterFormulaire()` — CONCEPTION Y (retenue)

**Décision (la plus sûre)** : `collecterFormulaire()` capture UNIQUEMENT les
champs **stables**, indépendants de la structure :

```
{ titre, mode_notation, afficher_bareme_dans_exos, item_langue_francaise }
```

Les **barèmes ne sont PAS dans le snapshot**. Ils sont traités par un marquage
« modifié » explicite (cf. 3.5). Raison : un barème est attaché à un exo dont la
PRÉSENCE relève de la structure (ajout/retrait persiste immédiatement). Si les
barèmes étaient dans le snapshot, ajouter/retirer un exo ferait diverger le
snapshot et il faudrait le « re-snapshoter » — ce qui effacerait la trace d'un
champ (titre…) modifié avant l'opération de structure. Conception Y rend ce bug
**structurellement impossible** : les deux sources de « modifié » (snapshot des
champs stables + drapeau barèmes) sont indépendantes et additives.

### 3.3 Suppression du flag manuel _modifieFlag

Retirer la surcharge `get/set modifie`. **MAIS** on garde un drapeau dédié aux
barèmes : `_baremesModifies` (booléen). Le getter `modifie` effectif de l'éval
devient : `super.modifie || this._baremesModifies`. (On surcharge le getter pour
combiner les deux sources, sans réintroduire le flag global d'antan.)

- `marquerModifie()` → `this._baremesModifies = true; this.majToolbar()` (utilisé
  par l'oninput des barèmes).
- Après sauvegarde réussie / chargement : `this.modifie = false` (snapshot
  propre) ET `this._baremesModifies = false`.
- `_majToolbar` lit `this.modifie` (getter combiné).
- Garde-sortie lit `this.modifie` (donc couvre champs ET barèmes).

### 3.4 Opérations de structure — NE TOUCHENT PAS l'état modifié

**Règle (décision Laurent)** : une opération de structure (ajout/retrait/réordo
d'exo ou d'objectif) :
- persiste immédiatement (déjà le cas) ;
- **ne reprend PAS de snapshot** et **ne réinitialise PAS** `_baremesModifies`.

Conséquence voulue : si des champs/barèmes étaient modifiés avant l'opération,
ils le restent après → **la garde de sortie se déclenche toujours**. Une
opération de structure sur une éval « propre » ne crée aucun badge parasite
(snapshot des champs inchangé, drapeau barèmes inchangé).

> C'est l'inverse de la première version du cadrage (« reprendre un snapshot
> après structure »), qui aurait effacé une modif de champ en cours. Corrigé
> suite à la remarque de Laurent.

### 3.5 Barème : oninput explicite + Enregistrer groupé

- Le rendu des inputs barème (`_rendreExos`) reçoit `data-exo-id` +
  `data-bareme-champ`, et `oninput="atelEvalMarquerModifie()"` (marque
  `_baremesModifies = true`). On NE sauve plus à la frappe.
- `sauverBareme` (PATCH immédiat) **supprimé** ; le wrapper
  `window.atelEvalSauverBareme` aussi.
- À l'**Enregistrer** (`sauvegarder`) : après le PATCH des champs simples,
  pousser **TOUS** les barèmes présents (décision Laurent : tous, idempotent)
  via `PATCH /api/evaluations/<id>/baremes`, puis `this.modifie = false` +
  `this._baremesModifies = false`.
- Lecture des barèmes pour le push : `querySelectorAll('[data-exo-id]')`.

### 3.6 Verrou UI lecture seule

Voir §3.6 ci-dessous (inchangé).

### 3.6 Verrou UI lecture seule

Maintenant que le `<form id="atl-eval-form">` existe, le verrou peut réutiliser
la même approche que les atomes (`_appliquerVerrouLectureSeule` de la base) :
griser les champs du form quand `etat_code === 'valide'`. MAIS l'éval a aussi
des **actions de structure** (boutons ajouter/retirer exo & objectif) qui, si
dans le form, seront grisées aussi — c'est souhaitable (on ne modifie pas la
structure d'une éval validée). À vérifier : le bouton « Repasser en cours », les
onglets et « Compiler » doivent rester HORS du form (donc actifs).

→ Idéalement, l'éval **hérite** `_appliquerVerrouLectureSeule` de la base et
   l'appelle dans son équivalent d'`afficherEditeur`/rendu. À vérifier que
   l'éval a un point d'appel équivalent (elle a son propre rendu).

## 4. Risques & vigilance

- **Pas de tests JS** : tout repose sur tests structurels + validation visuelle.
  Points à tester manuellement par Laurent (cf. note de redémarrage).
- **Snapshot ↔ structure** (3.4) : le piège principal. Si on oublie de reprendre
  le snapshot après une opération de structure, le badge « modifié »
  s'allumerait à tort.
- **Garde-sortie** : doit se déclencher pour des champs non enregistrés, pas
  après une opération de structure seule.
- **Barèmes groupés à l'Enregistrer** : bien pousser TOUS les barèmes (ou
  seulement ceux modifiés ? — pousser tous est plus simple et idempotent).
- **Verrou + régime mixte se combinent** : un item validé est grisé ; repasser
  en cours réactive ; le snapshot doit être cohérent à la bascule.

## 5. Questions ouvertes — DÉCISIONS (Laurent)

1. **Marquage modifié des barèmes** → conception Y : `oninput` explicite sur les
   inputs barème (`atelEvalMarquerModifie`), barèmes HORS snapshot. Pas de
   redondance : snapshot (champs stables) et drapeau (barèmes) couvrent des
   choses distinctes.
2. **Barèmes poussés à l'Enregistrer** → **TOUS** les barèmes présents (endpoint
   groupé idempotent).
3. **Découpage** → **tout ensemble** (régime mixte + verrou UI éval) dans
   v0.16.5, car même `<form>`.
4. **Règle structure/garde (remarque Laurent)** → une opération de structure ne
   nettoie jamais l'état modifié : si des champs/barèmes étaient en attente, la
   garde de sortie reste active (cf. 3.4).
5. **Saisie non enregistrée + opération de structure** → **BLOQUER**. Une
   opération de structure (ajout/retrait/réordo d'exo ou d'objectif) recharge
   l'éval depuis la BDD et re-remplit le formulaire, ce qui écraserait une
   saisie de champ non enregistrée. Garde `_garderAvantStructure()` : si
   `this.modifie`, on refuse l'opération avec un toast « Enregistrez vos
   modifications avant de modifier la structure ». L'utilisateur enregistre
   d'abord, puis modifie la structure.
