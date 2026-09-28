# Cadrage — Verrouillage « validé = lecture seule » (tous les ateliers)

> **Statut** : cadrage à valider avant codage.
>
> **Décisions prises (Laurent)** :
> - **Périmètre** : TOUS les ateliers (notion, méthode, exercice, fiche, carte,
>   évaluation) — règle uniforme « validé = figé ».
> - **Mécanisme** : UI grisée **+** backend qui refuse (défense en profondeur).

## 1. Problème

La validation (`etat_code = 'valide'`) a changé de nature. À l'origine, simple
marqueur de confort (« ce travail me convient »). Depuis qu'on y attache des
invariants (barèmes valides, exos notés — v0.16.3), elle est devenue une
**garantie de cohérence**. Or aujourd'hui on peut encore éditer après
validation → on peut casser l'invariant que la validation certifie (ex. passer
un barème d'exo à 0 après avoir validé).

**Solution** : un item validé est en **lecture seule**. Pour le modifier, il
faut explicitement le **repasser en cours** (puis revalider). Cycle
« figé ↔ brouillon » qui rend la validation honnête.

## 2. État actuel (audit)

- **Stockage de l'état** : colonne `etat_code` par item.
  - Atomes : table BDD par type ; lu via `services.etats_edition.lire_etat_atome`.
  - Évaluation : colonne `etat_code` dans sa table.
- **Bascule** : `changer_etat_atome` (atomes) / `valider/devalider` (éval). Des
  hooks refusent déjà le passage EN `valide` si incomplet. Ce qu'on ajoute,
  c'est l'inverse : refuser la MODIFICATION quand DÉJÀ `valide`.
- **Routes de modification** (hétérogènes) :
  - notion/méthode/exercice : helper commun `_enregistrer_routes_atome`
    (`_update` PATCH, `_delete`) dans `routes/atomes.py`.
  - fiche : route propre `routes/fiches_resume.py`.
  - carte : route propre `routes/cartes_automatisme.py`.
  - éval : routes propres (`routes/evaluations.py`) — PATCH éval, PATCH/POST/
    DELETE exos, objectifs, barèmes groupés, etc.
- **UI** : aucune mise en lecture seule aujourd'hui. `basculerValidation`
  (base + éval) ne fait que changer `etat_code`.

## 3. Backend — refuser la modification d'un item validé

**Principe** : toute route qui modifie le CONTENU d'un item (PATCH champ,
ajout/retrait/réordo de composant, suppression ?) vérifie d'abord l'état. Si
`valide` → 409 Conflict avec un code `item_verrouille` (et message clair).

**Exception** : la route de changement d'état elle-même (`/etat`,
`/valider`, `/devalider`) DOIT rester ouverte — c'est elle qui permet de
revenir en cours.

### 3.1 Questions de design

- ❓ **Suppression d'un item validé** : on refuse aussi (cohérent : figé = rien
  ne bouge) ou on tolère (supprimer ≠ modifier le contenu certifié) ?
  Recommandation : **refuser** (uniformité ; pour supprimer, dévalider d'abord).
- ❓ **Opérations de structure de l'éval** (ajout/retrait/réordo d'exos et
  d'objectifs) sur une éval validée : refuser aussi (sinon on contourne le
  verrou). Recommandation : **refuser** toutes les routes de contenu, garder
  seulement valider/devalider.
- ❓ **Code HTTP** : 409 Conflict (l'état rend l'opération impossible) semble le
  plus juste. Alternative : 403. Recommandation : **409** + `code:
  'item_verrouille'`.

### 3.2 Implémentation pressentie

- Atomes (notion/méthode/exercice) : garde dans `_update`/`_delete` du helper
  `_enregistrer_routes_atome` → lit `lire_etat_atome`, refuse si `valide`.
  Couvre les 3 d'un coup.
- Fiche, carte : même garde dans leurs routes PATCH/DELETE propres.
- Éval : garde dans les routes de contenu (PATCH éval, exos *, objectifs *,
  barèmes). Helper interne `_refuser_si_valide(conn, eval_id)` pour factoriser.
- Un helper transversal possible : `etats_edition.assert_modifiable(conn,
  type, id)` qui lève une exception `ItemVerrouille` traduite en 409 par les
  routes. À évaluer (les stockages diffèrent : atomes BDD vs éval table propre).

## 4. Frontend — UI en lecture seule

**Principe** : quand `itemActif.etat_code === 'valide'`, l'éditeur passe en
lecture seule : champs `disabled`/`readonly`, boutons d'action de structure
masqués/désactivés, et un bandeau « Validé — repassez en cours pour modifier ».
Le bouton de bascule validation reste actif (c'est la sortie).

### 4.1 Dans la base `AtelierEditeur`

- Une méthode `_appliquerVerrou(estValide)` qui parcourt le form
  (`atl-<prefixe>-form`) et met `disabled` sur inputs/selects/textareas, masque
  les boutons d'ajout/suppression de composants.
- Appelée depuis `remplirFormulaire`/`majToolbar` selon `etat_code`.
- Bandeau d'info réutilisable.

### 4.2 Spécifique éval

L'éval a son propre éditeur multi-panneaux (pas le form unique de la base — cf.
2b). Il faudra appliquer le verrou à ses champs (titre, mode, barèmes, langue)
ET à ses actions de structure (ajout/retrait/réordo exos & objectifs).

→ ❓ **Dépendance avec 2b-2** : le régime mixte (form + collecterFormulaire)
   n'est pas encore livré pour l'éval. Le verrou UI éval sera plus simple à
   poser APRÈS 2b-2 (form en place). Faut-il faire 2b-2 d'abord, puis le
   verrou ? Ou poser le verrou éval « à la main » maintenant sur les
   getElementById existants ?

### 4.3 UX de la bascule

- Sur un item validé : le clic « repasser en cours » déverrouille l'UI.
- Sur un item en cours : « valider » verrouille (après succès du hook).
- Message clair à chaque transition.

## 5. Découpage proposé (livraisons)

Vu l'ampleur (backend transversal + frontend base + éval), découpage possible :

- **A — Backend, tous types** : garde « refuser modif si validé » + tests.
  C'est la VRAIE garantie ; testable sans UI. Faible risque.
- **B — Frontend atomes** : verrou UI dans `AtelierEditeur` (notion, méthode,
  exercice, fiche, carte).
- **C — Frontend éval** : verrou UI éval (dépend de l'état de 2b-2).

→ ❓ Ordre et regroupement à décider. Option simple : A d'abord (sécurise
   l'invariant côté serveur), puis B, puis C. Ou A+B ensemble (atomes complets)
   puis C.

## 6. Questions ouvertes — DÉCISIONS (Laurent)

1. **Suppression d'un item validé** → **autorisée APRÈS CONFIRMATION** (pas un
   refus sec). La confirmation se fait côté UI ; le backend autorise la
   suppression d'un item validé (seules les MODIFICATIONS de contenu sont
   refusées).
2. **Opérations de structure** sur item validé → **refusées** (409).
3. **Code HTTP** → **409 Conflict** + `code: 'item_verrouille'`.
4. **Bandeau UI** → **PAS de bandeau**. L'UI grisée + le bouton « repasser en
   cours » suffisent (seule action possible).
5. **Périmètre v0.16.4** :
   - **Backend (garde 409)** : TOUS types, **y compris l'évaluation**, dès
     maintenant. C'est la vraie garantie, indépendante de l'UI → ferme le trou
     immédiatement partout.
   - **UI lecture seule** : atomes seulement (générique dans `AtelierEditeur` :
     notion, méthode, exercice, fiche, carte). L'UI éval suivra avec 2b-2.
   - **Conséquence assumée** : pendant cette version, une éval validée est
     protégée serveur (409) mais son UI reste éditable. L'UI éval doit gérer
     proprement le 409 (message clair, pas de plantage) en attendant 2b-2.
6. **Retour « en cours »** → libre (pas de hook). La confirmation ne concerne
   que la suppression (point 1).
