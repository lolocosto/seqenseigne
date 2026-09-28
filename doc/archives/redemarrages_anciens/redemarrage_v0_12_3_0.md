# Redémarrage seqenseigne — v0.12.3.0 (chantier 4/5 série v0.12, étape 1/2)

## Synthèse

**Port des fonctionnalités essentielles d'editv2 dans l'atelier d'assemblage**,
préalable à la suppression d'editv2 prévue en v0.12.3.1.

Le toggle « Assemblage / Édition avancée » et le rappel niveau/séquence sur
la toolbar **restent en place** dans cette livraison. Ils seront retirés
en v0.12.3.1, après que tu aies validé en conditions réelles que
l'assemblage couvre tous tes besoins.

## Trois fonctionnalités portées

### 1. Réordonnancement d'objectifs (drag-and-drop intra-partie)

Les objectifs d'une partie peuvent désormais être réordonnés en glissant
l'un sur l'autre. Au drop :
- Si la souris est dans la **moitié haute** de l'objectif cible : insertion
  avant
- Si la souris est dans la **moitié basse** : insertion après

Indicateur visuel : une barre colorée apparaît au-dessus ou en dessous de
l'objectif cible (classes `.drag-over-obj-above` / `.drag-over-obj-below`).

**L'objectif Connaître/Cours (codes 01, 11, 21…) n'est pas déplaçable** :
- sa balise est `draggable="false"`
- sa poignée `⋮⋮` est invisible (`.asm-obj-handle--fixe`, `visibility:
  hidden`, mais conserve la largeur pour aligner les codes verticalement)
- on ne peut pas non plus le **survoler** par-dessus (l'insertion en
  position 0 est refusée tant qu'un Cours est en place dans la partie
  cible) — au-dessus du Cours : pas d'indicateur visuel, le drop est ignoré

### 2. Réassignation à une autre partie (drag-and-drop inter-partie)

Le même drag, en glissant un objectif sur un objectif d'une **autre**
partie de la même séquence-niveau, déclenche un déplacement inter-partie
avec **recalcul automatique des codes** des deux parties.

Exemple : dans pt_A1 = [01 Cours, 02 Calculer, 03 Représenter], on glisse
ob_03 sur ob_12 de pt_A2 (qui contient [11 Cours, 12 Modéliser]).
Résultat :
- pt_A1 : [01 Cours, 02 Calculer]            (ex-03 retiré)
- pt_A2 : [11 Cours, 12 Représenter, 13 Modéliser] (ex-03 reçoit le code 12)

Atomicité côté backend (cf. plus bas).

### 3. Toggle « Fin de cycle » (attribut booléen)

Une checkbox `Fin de cycle` apparaît dans le bandeau d'objectif **ouvert**,
juste après le contrôle Séances. Cochée si `o.fin_cycle === 'O'`.

**N'apparaît PAS sur l'objectif Cours** (codes 01, 11, 21…) — l'attribut
fin-de-cycle est sémantiquement réservé aux attendus d'apprentissage
(objectifs exo). Le champ BDD `fin_cycle` reste défini sur tous les
objectifs (avec valeur par défaut 'N' pour le Cours), pas de migration.

Pas placé dans le bandeau **fermé** pour ne pas surcharger la liste avec
un contrôle peu fréquent. Pour basculer la fin-de-cycle, on ouvre
l'objectif et on coche.

API utilisée : `PATCH /api/v2/objectifs/<id>/fin-cycle` (existait déjà,
utilisée auparavant par editv2).

## Backend — Nouveau service `deplacer_objectif_avec_position`

### Signature

```python
deplacer_objectif_avec_position(
    conn,
    objectif_id: str,
    partie_cible_id: str,
    position_dans_cible: int,  # 0 à nb_objs_cible inclus
) -> dict
```

### Comportement

Déplace atomiquement un objectif vers une partie cible à une position
précise, en recalculant les codes des **deux parties** (source ET cible).

C'est différent de la route préexistante `/api/v2/objectifs/<id>/partie`
qui préserve le code et peut donc échouer en `conflit_code_dans_partie_
cible` si la cible a déjà un objectif avec le même code. Ici on
réordonne les deux parties, ce qui exclut tout conflit de code.

### Cas particuliers

- **Cours non déplaçable** : si on tente de déplacer l'objectif Connaître
  (code finissant par '1' avec convention respectée), refus avec
  `ReordonnancementInvalide` motif "code_connaitre".
- **Cours en position 0 protégé** : si la partie cible a déjà un Cours
  en position 0, on refuse `position_dans_cible=0`.
- **Hors séquence** : refus avec `ReassignationImpossible` code
  "partie_hors_sequence" si les deux parties ne sont pas dans la même
  séquence-niveau.
- **Position hors bornes** : refus si `position < 0` ou
  `position > nb_objectifs_cible`.
- **Cas dégénéré intra-partie** : si partie_source = partie_cible, on
  délègue à `reordonner_objectifs_dans_partie` (pure réécriture des codes).

### Atomicité

Tout passe en une seule transaction (`with _store_conn() as conn`).
Phase intermédiaire avec codes temporaires `~mig` puis `~tmp1`, `~tmp2`…
pour éviter les collisions sur l'index `UNIQUE(partie_id, code)`.

### Route HTTP

```
PATCH /api/v2/objectifs/<objectif_id>/deplacer
Body : { "partie_cible_id": str, "position_dans_cible": int }
```

Codes :
- 200 + JSON détail (cf. signature service)
- 400 `partie_cible_id_manquant` / `position_invalide`
- 404 `objectif_introuvable` / `partie_introuvable`
- 409 `partie_hors_sequence` / `code_connaitre` / position 0 avec Cours

## Tests

**Total : 1907 tests** (vs 1888 baseline v0.12.2) → **+19 tests v0.12.3.0**.

Nouveau fichier `tests/test_v0_12_3_0_deplacer_objectif.py`, 19 tests
organisés en 6 sections :

1. **TestDeplacementInterPartie** (4 tests) : déplacement standard avec
   recalcul des codes des deux parties, insertion en queue, vers partie
   vide, renumérotation source après retrait.
2. **TestDeplacementIntraPartie** (2 tests) : descente et remontée d'un
   objectif dans sa propre partie (cas dégénéré, délégation à
   `reordonner_objectifs_dans_partie`).
3. **TestRefusCours** (4 tests) : refus de déplacer le Cours code 01,
   code 11 ; refus de placer un objectif en position 0 si Cours présent ;
   acceptation en position 0 si pas de Cours.
4. **TestRefusHorsSequence** (1 test) : refus pour `partie_hors_sequence`.
5. **TestPositionInvalide** (2 tests) : position négative, position trop
   grande.
6. **TestEntitesIntrouvables** (2 tests) : objectif inconnu, partie cible
   inconnue.
7. **TestRouteDeplacer** (4 tests) : intégration HTTP — 400 sans
   partie_cible_id, 400 sans position, 400 position non entière, 404
   objectif inconnu.

## Frontend — Détails d'implémentation

### Drag-and-drop

Les objectifs ont désormais sur leur balise `<div class="asm-obj">` :
- `draggable="${estConnaitre ? 'false' : 'true'}"` — le Cours n'est pas
  glissable
- `ondragover/dragleave/drop` qui déclenchent les handlers
  `seqnivAsmDragOverObj/DragLeaveObj/DropObj`

Le handler `DragOverObj` calcule la position d'insertion (avant/après)
en comparant `ev.clientY` à la moitié verticale du rectangle de l'objectif
cible. Refus immédiat si la cible est le Cours et qu'on tente d'insérer
en position 0.

`DropObj` calcule la position finale en tenant compte du décalage
d'index intra-partie (si l'objectif glissé était avant la cible dans
la même partie, son retrait fait baisser tous les indices suivants
de 1).

### Désactivation editv2 ?

Non, editv2 reste pleinement fonctionnel dans cette livraison. Il
sera supprimé en v0.12.3.1 après validation côté production que
l'assemblage couvre tous les usages.

## Fichiers touchés

```
services/v2_edition.py                   (+~145 lignes : nouveau service
                                            deplacer_objectif_avec_position
                                            avec gestion atomique inter-partie)
routes/v2_edition.py                     (+~55 lignes : nouvelle route
                                            api_deplacer_objectif + import)
static/atelier_seqniv_assemblage.js      (+~140 lignes :
                                            - 3 handlers DragOverObj/DragLeaveObj/DropObj
                                            - 2 helpers _trouverPartiePourObj/_indexObjDansPartie
                                            - handler ChangerFinCycle
                                            - rendu objectif fermé/ouvert mis à jour
                                              (Cours non draggable, checkbox fin-cycle))
static/app.css                           (+~35 lignes :
                                            - .asm-obj.drag-over-obj-above/below
                                            - .asm-obj-handle--fixe
                                            - .asm-obj-fincycle-label/input/libelle)
tests/test_v0_12_3_0_deplacer_objectif.py (NOUVEAU — 19 tests, ~370 lignes)
doc/redemarrage_v0_12_3_0.md             (NOUVEAU)
```

Aucune migration BDD nécessaire (le champ `fin_cycle` existait déjà,
les routes `/objectifs/{id}/fin-cycle` et `/parties/{id}/objectifs/ordre`
existaient déjà).

## Procédure de déploiement

1. Décompresser le ZIP par-dessus la v0.12.2 actuellement déployée.
2. Relancer l'application — démarrage immédiat (pas de migration).
3. Ctrl+F5 dans le navigateur (rechargement du JS/CSS).

## Points de validation côté Laurent

### Réordonnancement intra-partie
- Ouvrir un assemblage de séquence avec une partie ayant 3+ objectifs
- Glisser un objectif (poignée `⋮⋮` ou n'importe où dans le bandeau fermé)
  au-dessus d'un autre dans la même partie
- Vérifier que :
  - une barre colorée apparaît au-dessus ou en dessous de la cible selon
    la position de la souris
  - au drop, les codes sont recalculés (X2, X3, X4… selon le numéro de
    partie X)
  - l'objectif Cours reste en première position quoi qu'il arrive

### Réassignation inter-partie
- Glisser un objectif d'une partie sur un objectif d'une autre partie
  de la même séquence
- Vérifier le recalcul des codes dans **les deux parties** (source et
  cible)
- Vérifier qu'on ne peut pas glisser un objectif **avant** le Cours de
  la partie cible (au-dessus du Cours : pas d'indicateur, drop ignoré)
- Vérifier qu'on ne peut pas glisser le Cours d'une partie

### Fin de cycle
- Ouvrir un objectif exo (code 02, 03, 12, 13…)
- Vérifier la présence de la checkbox « Fin de cycle » à côté de Séances
- Cocher / décocher : le statut est sauvegardé silencieusement (message
  bref dans la zone de status)
- Ouvrir l'objectif Cours (code 01, 11, 21) : la checkbox **n'apparaît pas**
- Recharger la page : l'état est bien persisté

### Régressions à surveiller
- Le drag-and-drop de **parties** continue de fonctionner (réordonnancement
  par drag de la carte de partie)
- Le drag-and-drop d'**exos depuis la sidebar** vers les zones d'objectif
  continue de fonctionner
- Le mode **Édition avancée v2** reste accessible via le toggle (gardé
  en place jusqu'à v0.12.3.1)

## Prochaine étape

**v0.12.3.1** — Suppression effective :
- Suppression du toggle Assemblage / Édition avancée
- Suppression du fichier `static/ateliers_seqniv_v2_edit.js` (1336 lignes)
- Suppression du conteneur `#liv-atl-content-v2`
- Retrait du rappel niveau/séquence sur la toolbar (`liv-atl-titre`
  passe à un texte statique)
- Cleanup des classes CSS `.atl-mode-toggle`, `.atl-mode-btn*`

À livrer **après** que tu aies confirmé que l'assemblage couvre tous
tes besoins en conditions réelles d'utilisation.
