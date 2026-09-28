# Redémarrage v0.19.2.1 — Cartes d'automatisme 4e, LOT 2 (S04–S06) + correctifs LOT 1

Deuxième lot de cartes d'automatisme 4e (N11), + les deux correctifs demandés
sur le lot 1.

## Correctifs LOT 1 (à réappliquer)

`outils/cartes_n11_lot1_data.py` mis à jour :
- **S01 C6** (Puissance de 10 négative) — verso : « Le chiffre $0,0\\ldots01$
  avec $n$ zéros en tout. $10^{-n}$ est l'inverse de $10^{n}$. Ex.
  $10^{-3} = 1/1000 = 0{,}001$. »
- **S01 C12** (Carrés parfaits) — verso : liste complète
  $1, 4, 9, 16, 25, 36, 49, 64, 81, 100, 121, 144$.

Réappliquer le lot 1 met à jour ces deux cartes (idempotent) :
```
python -m outils.import_cartes_n11_lot1 --apply
```

## LOT 2 — 18 cartes (S04–S06)

- **S04** (6, Nombres premiers / fractions) : définition premier, liste < 30,
  « 1 n'est pas premier », simplifier une fraction (+ paramétrée), décomposer en
  facteurs premiers.
- **S05** (8, Calcul littéral / équations) : équation, distributivité,
  développer/factoriser, développer $k(x+b)$ (paramétrée), réduire, tester une
  solution, résoudre $ax=b$ (paramétrée), réduire $ax+bx$ (paramétrée).
- **S06** (4, Statistiques) : médiane (définition + méthode), angle d'un secteur
  (paramétrée), total = $360^\circ$.

Cartes en état `en_cours` (à valider). Liens vers notions/méthodes sources.

Compilation xint des cartes paramétrées **vérifiée** cette fois (S04C05, S05C07,
S06C03 testées : résultats corrects).

## Déploiement

```
python -m outils.import_cartes_n11_lot1 --apply   # (réapplique les correctifs)
python -m outils.import_cartes_n11_lot2 --apply   # (nouveau lot)
```

## Fichiers

- `outils/cartes_n11_lot1_data.py` (corrigé — S01 C6 et C12).
- `outils/cartes_n11_lot2_data.py` (nouveau).
- `outils/import_cartes_n11_lot2.py` (nouveau).

## Suite

- Lot 3 : S07–S09. Puis S10–S12, S13–S14.
- Rappel objectifs : comportement inchangé (cartes liées à une méthode héritent
  de son objectif ; cartes liées à une notion n'en ont pas) — statu quo décidé.
