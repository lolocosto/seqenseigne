# Redémarrage v0.19.1.10 — Import historique 3ᵉ3 2022-23

Import de la structure historique de la 3ᵉ3 2022-23 (Hautes Ourmes). Seconde
livraison du couple 2022-23 (après la 5e2). Livraison **outillage uniquement** :
un script à usage unique, aucun changement d'application.

> Prérequis : v0.19.1.4 (modèle `mode_seances`) déployée. Le script vérifie le
> modèle et refuse de tourner sinon.

## Script — `outils/import_historique_3e3_2022.py`

Dry-run par défaut, `--apply` + `'OUI'` (ou `--yes`), transactionnel,
**idempotent**, vérification post-import, compte-rendu avant/après. Mode
**`par_objectif`** (comme la 5e2 2022-23).

Cible : référentiel `N12_v2022` + progression `pg_ed218842` + classes
`cl_9ee1805d` (3E3) **et** `cl_3fbda8f5` (3E8) — progression partagée.

Spécificités vs la 5e2 2022-23 :
- **Trois séquences scindées** en 2 parties : S05, S09, S12. Leurs **deux
  créneaux existent déjà** en base → aucune création ni suppression, on corrige
  tout **en place** (IDs préservés).
- Le niveau N12 a des créneaux **DC1/DC2/DC3** (devoirs communs) : **hors
  périmètre** (comme les bilans), non touchés.
- **S13 n'a pas de plan** dans les archives → aucune séance récupérable pour
  S13 (reste à 0).

Opérations (transaction unique) :

1. **Référentiel — parties** (mode `par_objectif`) : S05→2, S09→2, S12→2 ;
   `referentiel_objectifs.partie_numero` selon le découpage validé :
   - S05 : P1={01,02}, P2={03,04,05}
   - S09 : P1={01,02,03}, P2={04,05,06}
   - S12 : P1={01,02,03}, P2={04,05}
   `referentiel_parties.nb_seances_R_AE` = auto-évaluation de chaque partie.
2. **Référentiel — séances par objectif** : `nb_seances` depuis les « Repères
   temporels » (présentation → obj 01 ; objectif compté dans sa partie
   d'appartenance). Détail par série non récupéré.
3. **Progression — créneaux corrigés en place** : ordre/dates/période T1-T3/
   libellés pour S05/S09/S12. DC1/DC2/DC3 et bilans non touchés.
4. **Suivi — redistribution** des objectifs de partie 2 (les 2 classes) :
   S05 {03,04,05}→P2, S09 {04,05,06}→P2, S12 {04,05}→P2.

Hors périmètre : bilans de fin de trimestre et devoirs communs.

Validé sur copie de la base réelle : 17 parties, 17 créneaux séquences
datés/ordonnés (DC intacts, sans date), objectifs avec nb_seances renseignés,
376 lignes de suivi redistribuées sans perte (totaux préservés : S05 235,
S09 282, S12 235) ; ré-exécution idempotente ; objectifs des créneaux résolus
conformément aux découpages pour les deux classes ; DC1/DC2/DC3 préservés.

## Changements (fichiers)

- `outils/import_historique_3e3_2022.py` (nouveau).

Aucun code d'application modifié.

## Déploiement

1. Déployer ce delta ; `python -m outils.verifier_md5`.
2. S'assurer que la migration v0.19.1.4 est en base.
3. Dry-run :

       python -m outils.import_historique_3e3_2022

4. Appliquer :

       python -m outils.import_historique_3e3_2022 --apply

5. Dans « Suivi de classe » > Progression (2022-2023 / Hautes Ourmes / N12 /
   N12_v2022) : créneaux datés/ordonnés ; S05, S09, S12 en 2 parties avec leurs
   objectifs ; séances par objectif renseignées ; suivi réparti sur les parties ;
   DC1/DC2/DC3 inchangés.

## Suite

Les quatre progressions historiques (4e3, 5e2 2021-22, 5e2 et 3e3 2022-23) sont
désormais importées. Reste, sur le même modèle, les autres classes/années au fil
de l'eau ; et les chantiers déjà identifiés (modèle « plan de travail par
séquence » pour copier les plans PDF ; cœur v0.19.1 : drag-drop parties →
calendrier, changement de référentiel support).
