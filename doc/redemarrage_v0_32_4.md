# Redémarrage v0.32.4 — Récap des cartes : recto/verso aligné (macro ligne)

Corrige l'alignement recto/verso du récap de cartes (vue enseignant, 1
exemplaire par carte), via la nouvelle macro LaTeX
`\seqCarteRecapAjouteLigneCartes` du paquet.

## Contexte

Les planches élèves (16 exemplaires) avaient été réalignées en v0.29 (miroir des
colonnes du verso, côté Python). Le récap enseignant était généré carte par
carte (`\seqCarteRecapAjouteCarte`), et la macro écrivait les versos dans le même
ordre que les rectos → désalignement en recto-verso « bord court ».

La nouvelle macro `\seqCarteRecapAjouteLigneCartes` (paquet) prend une **ligne de
4 cartes** et écrit les 4 rectos dans l'ordre, les 4 versos en miroir. Toutes les
options sont particularisées **par carte** : `sequence`, `num`,
`typepedagolibelle`, `codecouleur`, `recto`, `verso` (suffixes
Un/Deux/Trois/Quatre) ; seul `niveau` est commun à la ligne.

## Correctif (côté appli)

`livret_cartes_recap.py` appelle désormais `\seqCarteRecapAjouteLigneCartes` une
fois par ligne de 4 cartes. Nouvelle fonction
`render_carte_centralise.rendre_ligne_recap(conn, cartes)` : construit l'appel de
ligne avec toutes les options particularisées par carte (chaque carte garde sa
couleur et son libellé pédagogique — plus de compromis « couleur de la 1ʳᵉ
carte »), concatène les variables xint des cartes paramétrées, et complète une
ligne incomplète par des positions vides.

## Fichiers

- `services/render_carte_centralise.py` : `rendre_ligne_recap` (options par
  carte).
- `services/livret_cartes_recap.py` : génération par lignes de 4.
- `tests/test_v0_13_6_5_2_livrets_manquants.py` : tests adaptés à la nouvelle
  macro (+ test de découpage en lignes).

## Tests

- pytest : 3905 passed, 7 skipped. vitest : 192 passed.
- Vérifié sur la base réelle : N11 (114 cartes) → 29 appels de ligne ;
  `typepedagolibelle`/`codecouleur` particularisés par carte (ex. Définition vs
  Calcul sur une même ligne).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Nécessite le
paquet `seqenseigne-carte-automatisme` avec la macro
`\seqCarteRecapAjouteLigneCartes` à options par carte (installée côté
utilisateur). Recompiler le récap et vérifier l'alignement recto/verso en
impression bord court.
