# Redémarrage v0.19.1.12 — Cohérence des états de référentiel (verrouille → utilise)

Outil de mise en cohérence de l'état des référentiels avec les progressions qui
s'appuient dessus.

## Contexte

Le cycle de vie d'un référentiel est `en_cours → valide → verrouille → utilise`.
L'état `utilise` signifie « référentiel verrouillé sur lequel au moins une
progression s'appuie » ; en usage normal, l'app fait cette transition
automatiquement (v0.19.0) au moment où une progression est liée à un référentiel
verrouillé.

Or les **imports historiques ad hoc** écrivent la structure et le suivi
directement en SQL, **sans** passer par cette sauvegarde de progression — donc
sans déclencher la promotion. Résultat : des référentiels restaient `verrouille`
alors qu'une progression les utilisait (ex. `N10_v2021`), au contraire de
`N11_v2021` qui, lui, était passé `utilise` par le flux applicatif normal.

## Correctif

`outils/coherence_etats_referentiels.py` applique la règle de l'app : tout
référentiel `verrouille` lié à ≥ 1 progression passe à `utilise`. Idempotent ;
ne promeut pas un référentiel `en_cours`/`valide`, ni un référentiel
`verrouille` sans progression.

La logique est exposée comme fonction réutilisable
`promouvoir_referentiels_utilises(conn)` : les futurs scripts d'import (2023-24
et au-delà) l'appelleront en fin de transaction pour ne plus jamais laisser
d'incohérence.

Sur la base actuelle, 5 référentiels sont concernés : N10_v2021, N10_v2022,
N12_v2022, N11_v2023, N12_v2024.

## Changements (fichiers)

- `outils/coherence_etats_referentiels.py` (nouveau) : outil + fonction
  `promouvoir_referentiels_utilises`.
- `tests/test_v0_19_1_12_coherence_etats.py` (nouveau, 4 cas) : promotion d'un
  verrouillé avec progression ; pas de promotion sans progression ; pas de
  promotion si `valide` ; idempotence.

## Tests

`tests/test_v0_19_1_12_coherence_etats.py` → 4 passed.

## Déploiement & utilisation

1. Déployer ce delta ; `python -m outils.verifier_md5`.
2. Contrôler (dry-run) :

       python -m outils.coherence_etats_referentiels

3. Appliquer :

       python -m outils.coherence_etats_referentiels --apply

   Les 5 référentiels concernés passent à `utilise`. Idempotent.

## Suite

- Les scripts d'import 2023-24 (4e3, 5e1) intégreront l'appel à
  `promouvoir_referentiels_utilises` en fin de transaction.
- Pas besoin des archives des classes « jumelles » (4e4/4e6, 3e8/5e4) : elles
  partagent la progression et le référentiel de leur classe de référence, déjà
  traités (suivi inclus).
