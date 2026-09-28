# Redémarrage v0.19.1.5 — Import historique 4ᵉ 2021-22 + correctif résolution par partie

Seconde livraison du chantier d'import historique. Elle fournit le **script
ad hoc** d'import de la structure 4ᵉ 2021-22 (classes 4E3/4E4/4E6, Hautes
Ourmes) et corrige un **bug de résolution des objectifs par partie** exposé par
cet import.

> Prérequis : la v0.19.1.4 (modèle `mode_seances` + table
> `referentiel_parties_seances`) doit être déployée. Le script le vérifie et
> refuse de tourner sinon.

## 1. Correctif — résolution des objectifs d'un créneau par `partie_debut`

`lire_progression_par_id` résolvait les objectifs d'un créneau avec
`partie_creneau = (partie OR partie_debut OR 1)`. Or `creneaux.partie` est un
**libellé texte** optionnel (ex. « 1ère partie : Pythagore ») tandis que la
partie numérique est `creneaux.partie_debut`. Dès qu'un créneau portait un
libellé (cas de S12 après import), la requête devenait
`WHERE partie_numero = '1ère partie…'` → **aucun objectif résolu**.

Corrigé : la résolution utilise désormais **uniquement `partie_debut`**
(entier). Le champ `partie` reste un libellé d'affichage.

## 2. Script d'import — `outils/import_historique_4e3_2021.py`

Script à **usage unique**, dry-run par défaut, `--apply` + confirmation `'OUI'`
(ou `--yes`), transactionnel, **idempotent**, avec vérification post-import et
compte-rendu avant/après. Cible : référentiel `N11_v2021` + progression
`pg_e011c733` (partagée par les 3 classes de 4ᵉ 2021-22).

Données figées dans le script, lues des fichiers d'archives **les plus
récents** (la vérité est dans les fichiers récents : les plans ont été retouchés
en cours d'année sans répercussion dans la progression de septembre).

Opérations, en une transaction :

1. **Référentiel — parties.** `mode_seances='par_serie'` ;
   `referentiel_parties` (S12 → 2 parties, autres → 1) ;
   `referentiel_objectifs.partie_numero` de S12 : {01,02,03}→1, {04,05,06}→2
   (l'objectif « cours » 01 reste en partie 1, conformément au suivi
   historique qui ne le liste qu'une fois).
2. **Référentiel — séances par série** (`referentiel_parties_seances`) : on
   n'insère que les matrices réellement présentes dans les plans autoritaires.
   9 séquences ont une matrice (S01/S02 sans série « révisions » ; les 7 autres
   complètes R/F/A/E) ; S04, S07, S09, S10 et S12 n'en ont pas (leurs plans les
   plus récents sont en ancien format, sans matrice par série) → aucune cellule.
3. **Progression — créneaux corrigés EN PLACE** (IDs préservés, car le suivi de
   classe `niveaux` y est rattaché) : ordre chronologique, `date_debut` /
   `date_fin`, période T1/T2/T3 (dérivée des dates ; les `Txbilan.csv`,
   incohérents, sont ignorés), libellés de partie pour S12.
4. **Suivi — redistribution S12** : les lignes `niveaux` des objectifs 04, 05,
   06 de S12 sont déplacées du créneau partie-1 (`cr_4063001c`) vers le
   créneau partie-2 (`cr_f13f3e81`), pour les 3 classes. Les objectifs 01, 02,
   03 restent sur la partie 1.

Hors périmètre : les bilans de fin de trimestre (le modèle de créneau ne les
porte pas).

Validé sur copie de la base réelle : 15 parties, 59 cellules de matrice, 15
créneaux datés/ordonnés, 216 lignes de suivi S12 (3×24×3) redistribuées ;
ré-exécution idempotente (0 ligne déplacée la 2ᵉ fois) ; objectifs des créneaux
S12 correctement résolus (P1→{01,02,03}, P2→{04,05,06}).

## Changements (fichiers)

- `persistence/sqlite_store.py` : résolution des objectifs de créneau par
  `partie_debut` (et non plus le libellé `partie`).
- `outils/import_historique_4e3_2021.py` (nouveau) : script d'import.
- `tests/test_v0_19_1_5_resolution_partie_libelle.py` (nouveau) : régression du
  correctif (un libellé texte dans `partie` ne casse plus la résolution).

## Tests

**Zéro régression** : pytest (progression/referentiel/figeage/livret/suivi) →
386 + 281 passed ; vitest → 187 passed.

## Déploiement

1. Déployer ce delta sur D:/E: ; `python -m outils.verifier_md5`.
2. S'assurer que la base a bien la migration v0.19.1.4 (lancer l'appli une
   fois, ou vérifier que la colonne `mode_seances` existe).
3. Lancer le script en dry-run pour contrôler le compte-rendu :

       python -m outils.import_historique_4e3_2021

4. Appliquer :

       python -m outils.import_historique_4e3_2021 --apply

   (confirmation `'OUI'`). Le script est idempotent et vérifie l'état après.

5. Dans « Suivi de classe » > Progression, sélectionner 2021-2022 / Hautes
   Ourmes / N11 / N11_v2021 : les créneaux sont datés et ordonnés, S12 apparaît
   en 2 parties avec leurs objectifs, et les matrices de séances par série
   s'affichent dans le détail d'un créneau. Le suivi S12 est réparti sur les
   deux parties.

## Suite

Reste du cœur v0.19.1 : drag-drop parties → calendrier ; changement de
référentiel support (purge des créneaux, confirmation, restreint à
`en_cours`, rétrogradation de l'ancien référentiel). Et, à terme : import des
autres classes/années historiques sur le même modèle.
