# Redémarrage v0.19.1.13 — Import historique 5ᵉ1 2023-24

Import de la structure historique de la 5ᵉ1 2023-24 (Hautes Ourmes). Livraison
**outillage uniquement** : un script à usage unique, aucun changement
d'application.

> Prérequis : v0.19.1.4 (modèle `mode_seances`) déployée.

## Particularités 2023-24 (différences avec les imports précédents)

- **Référentiel `en_cours`, pas `verrouille`.** `N10_v2023` avait été
  déverrouillé manuellement pour le repasser `utilise` ; le déverrouillage a
  re-lié la structure de parties au modèle actif (2025) au lieu de 2023. La
  structure des objectifs (codes + noms) est néanmoins restée **intacte**
  (vérifié vs ZIP 2023). Le script refige les parties **directement depuis les
  codes 2023** (sans repasser par `peupler_snapshot_parties`, qui relirait le
  modèle 2025), puis force l'état à `utilise`.
- **Découpage objectif → partie déduit des CODES.** En 2023-24, le code encode
  la partie : `0x`→P1, `1x`→P2, `2x`→P3 (01/11/21 = cours de chaque partie).
  Aucun découpage manuel nécessaire.
- **Suivi déjà réparti par partie** (codes par partie saisis directement) →
  **aucune redistribution** (contrairement aux années précédentes).
- **Semestres** : périodes `Sem1`/`Sem2` (et non T1/T2/T3).

## Script — `outils/import_historique_5e1_2023.py`

Dry-run par défaut, `--apply` + `'OUI'` (ou `--yes`), transactionnel,
**idempotent**, vérification post-import. Cible : `N10_v2023` + `pg_ceb1735e`
(classes 5e1 `cl_2e1073a8` + 5e3 `cl_58d60527`).

Opérations (transaction unique) :
1. **Parties** (mode `par_objectif`) : S10→2, S12→3, S14→2 ; `partie_numero` de
   chaque objectif **déduit de son code** ; `nb_seances_R_AE` depuis la ligne
   « Révision » des plans.
2. **`nb_seances` par objectif** depuis les plans (présentation → cours de la
   partie). Pour **S12**, remapping des codes locaux des plans vers les codes
   base : `03→12`, `04→22`, `05→23` (le Plan_3 a aussi un titre erroné « 2ème
   partie » au lieu de « 3ème »). Valeurs décimales conservées.
3. **Créneaux** corrigés en place (IDs préservés) : ordre/dates/période
   Sem1-Sem2/libellés de partie.
4. **État** : `N10_v2023` forcé à `utilise`.

Validé sur copie de la base : 18 parties, 22 objectifs des séquences scindées
avec `partie_numero` déduit des codes, 56 objectifs avec nb_seances, 18 créneaux
datés/ordonnés en Sem1/Sem2, état `utilise` ; idempotent ; objectifs des
créneaux résolus conformément aux codes (S12 P1={01,02}/P2={11,12}/P3={21,22,23}
etc.) ; suivi inchangé (déjà correct).

## Changements (fichiers)

- `outils/import_historique_5e1_2023.py` (nouveau).
- `tests/test_v0_19_1_13_partie_du_code.py` (nouveau, 1 cas) : déduction
  `partie_numero` depuis le code (0x/1x/2x).

## Déploiement

1. Déployer ce delta ; `python -m outils.verifier_md5`.
2. Dry-run :

       python -m outils.import_historique_5e1_2023

3. Appliquer :

       python -m outils.import_historique_5e1_2023 --apply

   `N10_v2023` passe à `utilise` ; S10/S12/S14 en parties avec objectifs
   résolus ; périodes en semestres.

## Suite

- Import 4e3 2023-24 (niveau N11) — seconde classe de 2023-24.
- Audit d'alignement des référentiels 2023-24 + complétion des livrets, et
  livraison « modèle plan par séquence » (déjà identifiée).
