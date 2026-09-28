# Redémarrage v0.29.0 — Planches de cartes : correctif recto-verso (bord court)

Corrige l'appariement recto-verso des planches de cartes d'automatisme à
l'impression, pour les cartes **paramétrées**.

## Le problème

Les planches sont imprimées en recto-verso **bord court** (paysage). Le verso
était généré dans le même ordre de cellules que le recto (« sans miroir »).
Pour les cartes **fixes** (16 copies identiques), l'ordre est indifférent. Mais
pour les cartes **paramétrées**, chaque cellule a un tirage aléatoire
différent (ex. 16 additions de fractions distinctes) : après retournement bord
court (miroir gauche-droite), la réponse d'une cellule ne tombait pas derrière
son énoncé — les réponses au dos ne correspondaient plus aux calculs.

## Le correctif

Le verso est désormais un **miroir gauche-droite** du recto : dans la grille 4×4
remplie ligne par ligne, l'ordre des colonnes de chaque ligne est inversé.

    recto  0  1  2  3      verso  3  2  1  0
           4  5  6  7             7  6  5  4
           8  9 10 11            11 10  9  8
          12 13 14 15            15 14 13 12

Ainsi, après retournement bord court, la réponse de chaque cellule tombe
physiquement derrière son énoncé. Sans effet sur les cartes fixes (cellules
identiques).

## Fichiers

- `services/render_carte_centralise.py` : `_miroir_horizontal_verso` +
  `PLANCHE_NB_COLONNES` ; appliqué au bloc verso dans `rendre_carte_planche`.
- `tests/test_v0_29_0_verso_miroir.py` (nouveau, 3 cas).

## Tests

- `tests/test_v0_29_0_verso_miroir.py` : 3 passed (miroir par ligne, réponse
  derrière énoncé, longueur préservée).
- pytest (cartes/planches/render) : 1017 passed. vitest : 193 passed. Aucune
  régression.
- Ordre du verso vérifié : recto [0..15] → verso
  [3,2,1,0, 7,6,5,4, 11,10,9,8, 15,14,13,12].

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.28.4. Réimprimer une planche paramétrée (ex. S03) en
recto-verso bord court : les réponses tombent maintenant derrière les bons
énoncés.

## Note

Le correctif suppose l'impression **bord court** (miroir gauche-droite),
confirmée par l'utilisateur. Si un jour un tirage « bord long » (miroir
haut-bas) est nécessaire, il faudrait inverser les lignes au lieu des colonnes —
non implémenté (pas le cas d'usage).
