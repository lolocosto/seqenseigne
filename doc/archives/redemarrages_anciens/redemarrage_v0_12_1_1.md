# Patch v0.12.1.1 — corrections post-déploiement v0.12.1

Trois fixes suite au déploiement de v0.12.1 chez Laurent :

## 1. Bug : duplication des séquences dans le livret PDF

**Symptôme reporté** : « Le PDF de 5e contient toutes les séquences de 5e ET
de 6e ». N10 = 41 pages au lieu de 21.

**Cause** : la jointure SQL dans `_lire_sequences_du_niveau` matchait
`spn.sequence_code = sdc.code` sans filtre sur le cycle. Or le code
`S01` existe à la fois dans `sequences_du_cycle` pour C03 (« Nombres
entiers », cycle 3 / 6e) et pour C04 (« Représentations d'un nombre »,
cycle 4 / 5e-4e-3e). La jointure produisait donc deux lignes par
séquence-niveau, l'une avec le nom C03, l'autre avec le nom C04.

**Fix** : ajout du paramètre `cycle_code` à `_lire_sequences_du_niveau`,
passé depuis `generer_livret_plans_de_travail` qui le résout déjà via
`_cycle_du_niveau`. Filtre `AND sdc.cycle_code = ?` ajouté au JOIN.

**Validation** : N10/N11/N12 produisent désormais 21/21/19 pages (vs
41/41/37 avec le bug). Test de régression
`test_pas_de_duplication_cycle3_cycle4` ajouté.

## 2. Bug : onglets Édition / Rendu PDF disparus dans l'atelier d'assemblage

**Symptôme reporté** : « les 2 onglets ont disparu, il reste juste le
bandeau de titre et les boutons assemblage / édition avancée ». Le
panneau d'édition avancée s'active correctement.

**Cause** : `app.js::initLivret()` faisait `innerHTML = ''` sur le
wrapper `#liv-atl-content-assemblage` quand aucune séquence n'était
sélectionnée. Or ce wrapper contient la **structure statique** des
onglets (`#asm-tabs` + boutons + panneaux `#asm-tab-edition` /
`#asm-tab-rendu`) posée dans le HTML. Une fois détruite, les
`getElementById('asm-tab-edition')` du JS d'assemblage ne trouvent
plus leur cible et le rendu échoue silencieusement.

Bug **préexistant** mais qui passait inaperçu jusqu'ici (le déclenche
sans doute un changement de timing dans l'init avec le nouvel atelier
plans-de-travail v0.12.1).

**Fix** : reset ciblé des sous-conteneurs internes (`#asm-tab-edition`,
`#liv-atl-content-v2`, sidebar, `#asm-tab-rendu`) sans toucher au
wrapper. Force aussi `dataset.initialise = ''` sur `#asm-tab-rendu`
pour relancer la régénération paresseuse au prochain affichage.

## 3. Ajout : bouton « Compiler le plan de travail » dans l'atelier d'assemblage

À côté de « Compiler le livret » et « Voir le .tex » dans l'onglet
Rendu PDF de l'atelier d'assemblage de séquence. Compile le livret
annuel des plans de travail du **niveau de la séquence courante**
(toutes les séquences du niveau), permettant à Laurent de vérifier
rapidement comment la séquence en cours apparaît dans le livret
complet après modification de séances ou de critères.

Affichage dans la même iframe que le livret de séquence (un seul
PDF visible à la fois, le plus récent écrase le précédent).

API utilisée : `POST /api/plans-de-travail/<niveau>/pdf` (déjà livrée
en v0.12.1, pas de changement backend).

## Bug préexistant adouci

`atelChargerObjectifs` produisait 5 erreurs console au démarrage
(`Cannot access property "innerHTML", sel is null` ligne 2088 d'app.js)
parce que le sélecteur `atl-exo-obj-sel` n'existe plus dans le HTML
depuis la refonte v0.10. Ajout d'un guard `if (!sel) return;` pour
faire taire ces erreurs sans toucher à la mécanique. Le retrait
complet de cette fonction est prévu pour v0.14 (cf. nettoyage des
restes legacy `ATL_OBJ_CAT`, `/api/objectifs`, table `objectifs`).

## Tests

**1872 tests** au vert en 1m59 (vs 1871 baseline v0.12.1, +1 test pour
le bug de duplication cycle).

## Fichiers touchés

```
services/livret_plans_de_travail.py        (~10 lignes : signature + WHERE)
static/app.js                              (~25 lignes : reset ciblé +
                                              guard atelChargerObjectifs)
static/atelier_seqniv_assemblage.js        (~50 lignes : nouveau bouton +
                                              handler livretSeqCompilerPlanTravail)
tests/test_v0_12_1_livret_plans_de_travail.py  (~50 lignes :
                                              MAJ signature dans 6 tests +
                                              1 nouveau test régression)
doc/redemarrage_v0_12_1_1.md               (NOUVEAU)
```

Aucune migration BDD nécessaire.

## Procédure de déploiement

Décompresser par-dessus la v0.12.1 actuellement déployée. Relancer
l'application — démarrage immédiat. Régénérer le PDF d'un niveau pour
vérifier le bon nombre de pages (21 pour N10, 21 pour N11, 19 pour N12
avec la BDD actuelle).
