# Redémarrage v0.19.1.9 — Import historique 5ᵉ2 2022-23

Import de la structure historique de la 5ᵉ2 2022-23 (Hautes Ourmes). Livraison
**outillage uniquement** : un script à usage unique, aucun changement
d'application.

> Prérequis : v0.19.1.4 (modèle `mode_seances` + `referentiel_parties_seances`)
> déployée. Le script vérifie le modèle et refuse de tourner sinon.

## Différences notables avec les imports 2021-22

- **Mode `par_objectif`** (modèle courant) : contrairement à 2021-22 (passé en
  `par_serie`), les plans 2022-23 donnent les séances **par objectif** + une
  auto-évaluation par partie, directement exploitables par le modèle natif. On
  **ne bascule pas** en `par_serie`.
- **Trois séquences scindées**, dont une en **trois parties** : S10 (2),
  **S12 (3)**, S14 (2).
- **Réconciliation des créneaux** existants avec la vérité de la progression :
  - **S14** : la base avait 3 parties, la progression en veut 2 → **suppression**
    du créneau S14 partie 3 (sans aucun suivi — vérifié) ;
  - **S10** : la base avait 1 partie, la progression en veut 2 → **création** du
    créneau S10 partie 2.

## Script — `outils/import_historique_5e2_2022.py`

Dry-run par défaut, `--apply` + `'OUI'` (ou `--yes`), transactionnel,
**idempotent**, vérification post-import, compte-rendu avant/après.

Cible : référentiel `N10_v2022` + progression `pg_c8f8d9e1` + classes
`cl_5a37f150` (5E2) **et** `cl_1ab4d097` (5E4) — progression partagée.

Opérations (transaction unique) :

1. **Référentiel — parties** (mode reste `par_objectif`) : S10→2, S12→3,
   S14→2 ; `referentiel_objectifs.partie_numero` selon le découpage validé :
   - S10 : P1={01,04,05,07}, P2={02,03,06,08}
   - S12 : P1={01,02}, P2={03}, P3={04,05}
   - S14 : P1={01,02}, P2={03,04}
   `referentiel_parties.nb_seances_R_AE` = auto-évaluation de chaque partie.
2. **Référentiel — séances par objectif** : `referentiel_objectifs.nb_seances`
   depuis les « Repères temporels » des plans. La « Présentation de la
   séquence » est rattachée à l'objectif « cours » 01 (seule la présentation de
   la partie où vit l'obj 01 est retenue). Un objectif cité dans plusieurs
   parties est compté dans sa partie d'appartenance. Le détail *par série*
   (fondamentale/avancée/exploration) n'est **pas** récupéré (choix
   pédagogique : trop détaillé, abandonné les années suivantes).
3. **Progression — réconciliation des créneaux** (IDs préservés) : suppression
   du créneau S14 P3, création du créneau S10 P2, puis ordre/dates/période
   T1-T3/libellés sur les 18 créneaux.
4. **Suivi — redistribution** sur les parties 2/3 (les deux classes) :
   - S12 : {03}→P2, {04,05}→P3
   - S14 : {03,04}→P2
   - S10 : {02,03,06,08}→ nouveau créneau P2

Hors périmètre : bilans de fin de trimestre et devoirs communs (DC1/DC2/DC3).

Validé sur copie de la base réelle : 18 parties, S14 P3 supprimée, S10 P2 créée,
18 créneaux datés/ordonnés, 54 objectifs avec nb_seances, 423 lignes de suivi
redistribuées sans perte (totaux préservés : S10 376, S12 235, S14 188) ;
ré-exécution idempotente ; objectifs des créneaux résolus conformément aux
découpages, suivi S12 réparti sur les 3 parties pour les deux classes.

## Changements (fichiers)

- `outils/import_historique_5e2_2022.py` (nouveau).

Aucun code d'application modifié.

## Déploiement

1. Déployer ce delta ; `python -m outils.verifier_md5`.
2. S'assurer que la migration v0.19.1.4 est en base (lancer l'appli une fois).
3. Dry-run pour contrôler le compte-rendu :

       python -m outils.import_historique_5e2_2022

4. Appliquer :

       python -m outils.import_historique_5e2_2022 --apply

5. Dans « Suivi de classe » > Progression (2022-2023 / Hautes Ourmes / N10 /
   N10_v2022) : créneaux datés/ordonnés ; S10, S12 (3 parties) et S14 (2
   parties) avec leurs objectifs ; séances par objectif renseignées ; suivi
   réparti sur les parties.

## Suite

- Import 3e3 2022-23 (niveau N12 ; introduit les devoirs communs DC1/DC2/DC3,
  hors périmètre du suivi des parties).
- Livraison « modèle plan par séquence » (déjà identifiée) pour pouvoir copier
  les plans de travail PDF des référentiels.
