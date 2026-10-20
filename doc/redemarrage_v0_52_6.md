# Redémarrage v0.52.6 — Référentiel principal de 6e complet (lots S01 à S13), retrait d'évaluations par l'import

## Besoin

Les treize lots de 6e sont prêts. Décision de Laurent (19 octobre 2026) :
**une évaluation sur 20 par séquence**, plus les travaux personnels notés ;
les tests courts sont réservés aux mises en route. Les lots S01 à S03, déjà
importés avec leurs anciennes évaluations, ont été recomposés et portent une
clé `evaluations_retirees` (titres à retirer) :

- S01 : « Évaluation --- Nombres entiers et décimaux », « Test court --- Les fractions » ;
- S02 : « Test court --- Repérer et comparer des fractions » ;
- S03 : « Évaluation --- Divisions », « Test court --- Problèmes avec des fractions ».

## Audit de la numérotation EV (import v0.52.2)

`importer_evaluations` numérote les exercices EV **en continu dans la
séquence, dans l'ordre du lot** (EV01… sur toutes les évaluations) ; la clé
est (N09, séquence, EV, num) et `_exercice` réécrit sur place l'atome qui
porte ce numéro. Les évaluations recomposées **réutilisent les numéros des
anciennes avec un autre contenu** : en S01, EV05 passait de « Écrire les
nombres en lettres » à « La fraction, un quotient », EV07 à EV08 changeaient
aussi ; en S03, EV12 passait du bonus « le libraire » à « Problèmes avec des
fractions ». Sans précaution : lien objectif EV périmé (l'atome réécrit
restait relié à son ancien objectif), atome d'une évaluation validée gardée
réécrit sous elle, atome validé (ancien contenu) injecté dans la nouvelle
évaluation.

## Décisions

- **R1 Retirer avant d'importer** (`import_lot6e.retirer_evaluations`,
  appelé en tête de `importer_evaluations`) : chaque évaluation N09 listée
  est retirée si elle n'est pas validée (`evaluation_objectifs`,
  `evaluation_exercices`, puis `evaluations`) ; validée, elle est gardée et
  signalée en anomalie ; absente, le rapport dit « déjà retirée »
  (idempotence). Puis les **exercices EV devenus orphelins** : ceux de la
  séquence qui étaient dans une évaluation retirée, qui ne sont plus utilisés
  par aucune évaluation et qui ne sont plus dans le lot (le lot ne pose pas,
  à leur numéro, un exercice de même contenu). Non validés : retirés avec
  leurs liens (`objectif_exos`, `partie_exos_revision_approche`) ; validés :
  gardés, anomalie. Un exercice d'une autre séquence ou d'une autre série,
  ajouté par l'auteur à une évaluation retirée, n'est jamais touché. Un
  titre à la fois retiré et présent dans le lot n'est pas retiré (anomalie).
- **R2 Un numéro EV occupé n'est jamais réattribué**
  (`_choisir_numero_ev`) : la numérotation naturelle reste celle de la
  v0.52.2 ; un atome existant n'est réutilisé que s'il est « libre ou à
  nous » (utilisé par aucune autre évaluation, et pas validé avec un autre
  contenu). Sinon l'exercice prend le **numéro de queue** (plus grand numéro
  EV de la séquence + 1), signalé dans les informations du rapport. Pour
  l'idempotence, un exercice déjà placé est retrouvé par sa position dans
  l'évaluation en base. C'est la règle la plus sûre : aucune clé
  (N09, séquence, EV, num) ne peut désigner deux contenus, aucun atome d'une
  évaluation gardée n'est réécrit.
- **R3 Liens EV périmés** : un atome EV réécrit par la recomposition perd ses
  liens EV vers un autre objectif que le sien (le bonus n'en a aucun).
- **R4 Évaluation validée** : ni l'évaluation ni ses exercices EV ne sont
  touchés (avant : seuls l'évaluation et ses objectifs étaient protégés).
- **Journal de restauration** : le journal JSON de `--apply`
  (`sauvegardes\journal_import_lot6e_*.json`) contient une liste `retraits` :
  pour chaque évaluation retirée, ses lignes `evaluations`,
  `evaluation_exercices` et `evaluation_objectifs` ; pour chaque exercice
  retiré, sa ligne `exercices` et ses liens. Des INSERT suffisent à
  restaurer. La sauvegarde `.db` d'avant l'import reste faite comme avant.
- **Noms de sauvegarde uniques** : deux `--apply` dans la même seconde
  écrasaient la sauvegarde et le journal du premier (donc la trace des
  retraits) ; un suffixe `_2`, `_3`… les distingue désormais.
- **Référentiel** (`outils/ref6e_v2.md` = `col6/ref6e_v2.md`, md5
  8ae6aaec141581907846522ab8207bc7) : la précision S06-03 → S07-04
  (exercice 7 de l'évaluation « Cercles et triangles ») et 34 dépendances
  entre objectifs tirées des rapports des lots (S06, S10 à S13 ; S04, S05,
  S07, S08, S09 n'en ajoutent pas) dans « Contraintes de progression », une
  ligne par dépendance « objectif → objectif : raison (lot) ». Objectifs,
  intitulés et critères inchangés (`objectifs_6e.json` inchangé, test de
  transcription vert). Les propositions de modification des rapports ne sont
  pas appliquées.
- **Lots** : `reference/lot6e/S01` à `S13`, `Snn.json` et `figures/`
  seulement (ni sauvegardes `*.avant_*`, ni `work/`, aperçus, rapports, `.sty`,
  `local.tex`). Aucune macro `\seqLoc…` hors du module v0.6 (vérifié ; l'import
  le signale, décision I1).
- **`doc/doublons_6e_5e.md`** : exercices de 5e copiés en 6e (S04, S11), à
  retirer des séries F/A/E de 5e lors de la migration du référentiel de 5e.

## Code

Modifié : `outils/import_lot6e.py`, `outils/ref6e_v2.md`,
`doc/ETAT_COURANT.md`. Nouveaux : `tests/test_v0_52_6_retrait_evaluations.py`
(9 tests), `doc/doublons_6e_5e.md`, ce fichier. Aucune migration, aucune
table, aucune route, aucun changement de rendu.

## Vérifications

- Cycle 4 : 403 sorties identiques au caractère près entre v0.52.5 et
  v0.52.6 sur la base atelier migrée.
- Base de test : copie migrée par l'appli de la base atelier v0.52.2 après
  import (S01 à S03 avec leurs 7 anciennes évaluations N09). Retrait seul
  (lots S01 à S03) : essai à blanc, `--apply`, deux `--apply` de plus : base
  identique ; 5 évaluations retirées, 25 lignes au journal. Cas validé
  (test court « Les fractions » validé, S03/EV13 validé) : gardés, signalés,
  exercices de la nouvelle évaluation en numéros de queue (EV10, EV11 ;
  EV14, EV15), idempotent.
- Import S01 à S13 : essai à blanc (3 anomalies « cycle 4 inchangé » déjà
  connues), `--apply`, second `--apply` : base identique (9 425 lignes).
- Compilés par les routes de l'appli : livrets élève S10 (17 p.), S11
  (12 p.), S12 (15 p.), S13 (11 p., `scratch3` chargé, blocs Scratch
  rendus), évaluation « Nombres entiers et décimaux, fractions » sujet A
  élève (2 p.), plan de travail S12 (2 p.).

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et
   `reference\lot6e\S01\` à `S13\` (remplacent les lots présents).
2. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py`
   (essai à blanc : lire « Documents et évaluations », les retraits y sont
   listés), puis `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.

Aucun `tex seqenseigne.ins` à relancer (module inchangé depuis v0.52.5).
