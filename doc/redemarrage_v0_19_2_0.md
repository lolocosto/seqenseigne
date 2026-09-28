# Redémarrage v0.19.2.0 — Cartes d'automatisme 4e, LOT 1 (S01–S03)

Premier lot de cartes d'automatisme pour la 4e (N11), à valider/modifier par
l'enseignant. Contenu pédagogique (pas de code applicatif) : un fichier de
données + un script d'insertion idempotent, sur le modèle des imports
historiques.

## Périmètre

- **24 cartes** : S01 (12, Puissances/racine carrée), S02 (4, Ordre/comparaison),
  S03 (8, Inverse/calcul fractionnaire).
- Calibrage : ~4 cartes par semaine de séquence (nb de semaines tiré de la
  progression 4e verrouillée 2025-2026, ref N11_v2024).
- Format aligné sur les cartes 5e validées : statiques (`fixe`) pour
  définitions/procédures/propriétés/reconnaissances, paramétrées (`parametree`)
  pour les calculs (variables `\\xintdefiivar`, affichage
  `\\xinttheiiexpr…\\relax`).
- Chaque carte est **liée** à sa notion/méthode source (lien_type + lien_id).
- Cartes créées en état **`en_cours`** (à valider ; passer à `valide` après
  relecture).

## Fichiers

- `outils/cartes_n11_lot1_data.py` — les 24 cartes (données).
- `outils/import_cartes_n11_lot1.py` — script d'insertion idempotent.

## Déploiement

```
# aperçu (aucune écriture) :
python -m outils.import_cartes_n11_lot1

# insertion :
python -m outils.import_cartes_n11_lot1 --apply
```

Idempotent : une carte est identifiée par (niveau, sequence, num). Ré-exécuter
met à jour sans créer de doublon. Toujours tester sur une copie de la base
d'abord.

## Validation attendue

Après insertion, relire les cartes dans l'atelier « Cartes d'automatisme » (4e),
les compiler, corriger si besoin, puis passer en `valide`. Cette relecture est
aussi l'occasion de repérer d'éventuelles erreurs/incohérences dans les cours
sources.

Point de vigilance signalé : la carte **S02 C3** (encadrement de racine) utilise
`randrange(1, 2*…)` (borne dépendant d'une variable) — syntaxiquement correcte
pour xint, mais à surveiller à la première compilation ; simplifiable si besoin.

La compilation xint réelle n'a pas pu être testée dans l'environnement de
génération (paquet `poormanlog` absent) : le format est identique aux cartes 5e
qui compilent déjà, et la cohérence des variables (définies vs utilisées) a été
vérifiée pour chaque carte paramétrée.

## Suite

- Lots suivants (mêmes standard et format) : S04–S06, S07–S09, S10–S12, S13–S14.
  Total 4e estimé : ~108 cartes sur 14 séquences.
- Puis (v0.20.x) : saisie de l'EdT.
