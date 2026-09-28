# Redémarrage v0.19.2.2 — Cartes d'automatisme 4e, LOT 3 (S07–S14)

Dernier lot de cartes d'automatisme 4e : les 8 séquences restantes (S07 à S14).
Avec les lots 1 et 2, la 4e (N11) est désormais **entièrement couverte** :
14 séquences, 114 cartes.

## Périmètre du lot 3 — 72 cartes

Calibrage 4 cartes/semaine (plan de charge, progression 4e verrouillée
2025-2026) :

| Séq | Thème | Cartes |
|-----|-------|--------|
| S07 | Probabilités | 6 |
| S08 | Proportionnalité (produit en croix) | 6 |
| S09 | Repérage, dépendance de grandeurs | 6 |
| S10 | Volumes, grandeurs composées, aires | 14 |
| S11 | Translations, rotations, triangles égaux | 8 |
| S12 | Pythagore, Thalès, cosinus | 20 |
| S13 | Espace, patrons, sections | 6 |
| S14 | Algorithmique (Scratch) | 6 |

Format identique aux lots précédents : statiques (`fixe`) pour
définitions/procédures/propriétés/reconnaissances, paramétrées (`parametree`)
pour les calculs. Cartes en état `en_cours` (à valider). Liens vers les
notions/méthodes sources : **toutes** liées.

Les cartes de calcul paramétrées ont été pensées pour rester à **résultat
entier / fraction simple** : par exemple, les cartes Pythagore utilisent des
triplets pythagoriciens (3-4-5 mis à l'échelle) pour garantir une hypoténuse
entière. Compilation xint vérifiée (S12C04, S12C13, S07C05, S07C06, S08C04,
S10C09 testées : résultats corrects).

## Déploiement

```
python -m outils.import_cartes_n11_lot3 --apply
```

Idempotent (identité par niveau/sequence/num). Aucune collision avec les lots
1 et 2 (numérotation par séquence). Tester sur copie d'abord.

## Bilan 4e (3 lots)

- 114 cartes, 14 séquences couvertes, 28 paramétrées, toutes liées à une source.
- À valider/modifier dans l'atelier « Cartes d'automatisme » (4e), puis passer
  en `valide`. C'est aussi une relecture des cours 4e.

## Fichiers

- `outils/cartes_n11_lot3_data.py` (nouveau, 72 cartes).
- `outils/import_cartes_n11_lot3.py` (nouveau).

## Suite

Cartes 4e terminées. Prochain chantier : **v0.20.x — UI de saisie de l'EdT**
(le socle backend grille horaire / EDT / projection / affectation est déjà en
place ; il manque l'interface de saisie).
