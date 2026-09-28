# Redémarrage v0.19.1.7 — Import historique 5ᵉ2 2021-22

Import de la structure historique de la 5ᵉ2 2021-22 (Collège des Hautes
Ourmes), sur le même modèle que la 4e3 (v0.19.1.5). Cette livraison ne contient
qu'un **script à usage unique** : aucun changement d'application.

> Prérequis : v0.19.1.4 (modèle `mode_seances` + `referentiel_parties_seances`)
> et v0.19.1.5 (résolution des objectifs par `partie_debut`) déployées. Le
> script vérifie le modèle et refuse de tourner sinon.

## Script — `outils/import_historique_5e2_2021.py`

Dry-run par défaut, `--apply` + `'OUI'` (ou `--yes`), transactionnel,
**idempotent**, avec vérification post-import et compte-rendu avant/après.

Cible : référentiel `N10_v2021` + progression `pg_85a0bf3a` + classe
`cl_e4005346` (5E2). Contrairement à la 4e3 (3 classes partageant la
progression), **une seule classe** est concernée ici.

Données figées dans le script, lues des fichiers d'archives les plus récents
(la vérité est dans les fichiers récents).

Opérations, en une transaction :

1. **Référentiel — parties + mode.** `mode_seances='par_serie'` ;
   `referentiel_parties` : **trois** séquences scindées (S10, S12, S14 → 2
   parties ; les autres → 1) ; `referentiel_objectifs.partie_numero` selon le
   découpage validé :
   - S10 : P1={01,04,05,07}, P2={02,03,06,08}
   - S12 : P1={01,04}, P2={02,03}
   - S14 : P1={01,02}, P2={03,04}
2. **Référentiel — séances par série.** On n'insère que les matrices présentes
   dans les plans autoritaires : S01, S02, S03, S07, S08, S11, S12 (P1+P2),
   S14 (P1) — soit 8 séquences. S04, S05, S06, S09, S10, S13 et S14 P2 n'ont
   pas de matrice (plans récents en ancien format). À noter : la matrice **S02**
   a des valeurs atypiques (TB : F=0,5 / A=1,5 / E=1,5), reprises telles quelles
   du plan.
3. **Progression — créneaux.** **Création du créneau S10 partie 2** (absent en
   base, contrairement à S12 P2 et S14 P2 déjà présents), puis correction de
   tous les créneaux **en place** (IDs préservés car le suivi y est rattaché) :
   ordre chronologique, `date_debut`/`date_fin`, période T1/T2/T3 (dérivée des
   dates), libellés de partie pour S10/S12/S14.
4. **Suivi — redistribution sur les parties 2.** Les lignes `niveaux` des
   objectifs de la partie 2 sont déplacées vers le créneau P2 :
   - S12 : {02,03} → `cr_1aa33a7b`
   - S14 : {03,04} → `cr_1a3ae909`
   - S10 : {02,03,06,08} → nouveau créneau S10 P2

Hors périmètre : bilans de fin de trimestre.

Validé sur copie de la base réelle : 17 parties, 63 cellules de matrice, créneau
S10 P2 créé, 17 créneaux datés/ordonnés, 200 lignes de suivi redistribuées
(S12 50 + S14 50 + S10 100) sans perte ; ré-exécution idempotente (réutilise le
créneau S10 P2 existant, déplace 0 ligne la 2ᵉ fois) ; objectifs des créneaux
correctement résolus par partie, suivi S10 réparti P1={01,04,05,07} /
P2={02,03,06,08}.

## Changements (fichiers)

- `outils/import_historique_5e2_2021.py` (nouveau) : script d'import.

Aucun code d'application modifié.

## Déploiement

1. Déployer ce delta ; `python -m outils.verifier_md5`.
2. S'assurer que la base a les migrations v0.19.1.4/.5 (lancer l'appli une fois).
3. Dry-run pour contrôler le compte-rendu :

       python -m outils.import_historique_5e2_2021

4. Appliquer :

       python -m outils.import_historique_5e2_2021 --apply

5. Dans « Suivi de classe » > Progression, sélectionner 2021-2022 / Hautes
   Ourmes / N10 / N10_v2021 : créneaux datés et ordonnés ; S10, S12 et S14
   apparaissent en 2 parties avec leurs objectifs ; matrices de séances par
   série dans le détail d'un créneau ; suivi réparti sur les deux parties.

## Suite

Reste du cœur v0.19.1 : drag-drop parties → calendrier ; changement de
référentiel support. Et, sur le même modèle, l'import des autres classes/années
historiques au fil de l'eau.
