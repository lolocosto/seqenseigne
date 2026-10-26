# Redémarrage v0.54.1 — corrigés manquants de S01 à S03, TP en double, référentiel ref6e_v2 du 25 octobre

## Contexte (25 octobre 2026)

Laurent n'a pas encore créé les référentiels internes de 6e (rien n'est validé dans son
atelier) et va envoyer à ses collègues tous les documents générés des séquences. Cette
version applique trois constats de la passe de cohérence du 25 octobre
(`SP/coherence6e/rapport_coherence.md`, § 7.2 et questions 14, 15, 16), sans aucune décision
pédagogique.

## 1. Lots S01, S02, S03 : 12 corrigés rédigés

Les 5 TP, 6 AC et la séance d'atelier de S01 à S03 n'avaient que la bascule élève/corrigé
(macros de réponse). Leur champ `corrige` est maintenant rédigé, au niveau des corrigés du
principal : réponses justifiées, démarche, calculs posés ; pour les questions de recherche,
réponses attendues. Il s'affiche en version corrigée dans le cadre « Explications » à la fin
du document (`documents_6e.corps_document`), jamais en version élève.

- Chaque calcul et chaque réponse est vérifié en Python (`SP/livraison_v0541/work/corr/verif.py`,
  382 vérifications) et comparé aux réponses déjà inscrites dans l'énoncé : sudokus de S01
  (indices recalculés, unicité de la solution par un solveur), labyrinthe de S02 (chemin
  croissant unique), cartes du poste 4 de l'atelier (énumération), tables à trous de S03.
- Aucune réponse de l'énoncé n'a été trouvée fausse.
- Sauvegardes : `Snn.avant_0541.json` à côté de chaque lot modifié.

## 2. TP en double

Deux TP s'appelaient « La kermesse du collège » (S04 : schémas en barres ; S12 :
proportionnalité). Celui de S12 devient **« Proportionnalité : les achats de la kermesse »**
(titre du lot et `\seqTitreTravailSix`). Aucun autre titre de document n'est en double dans
les 20 lots.

- **D-DOUBLON** — `outils/import_lot6e.py`, `titres_documents_en_double(lots)` : deux
  documents des lots importés (TP, AC, AT, évaluations, tests courts ; lots S et M) qui portent
  le même titre sont signalés en **anomalie** dans l'essai à blanc et le rapport de `--apply`,
  sans bloquer l'import. Les sujets A et B d'une même évaluation (même séquence) ne sont pas
  des doublons ; la casse et les espaces en trop ne comptent pas ; `evaluations_retirees` n'est
  pas un document. Raison : le titre est ce que voient les élèves et les collègues, et une
  évaluation est repérée par son titre dans le niveau.

## 3. Référentiel `ref6e_v2` du 25 octobre

Source de vérité : `SP/col6/ref6e_v2.md` (sauvegarde `ref6e_v2.avant_0541.md`), recopiée à
l'identique dans `outils/ref6e_v2.md`. Diff lisible : `SP/livraison_v0541/diff_ref6e_v2.md`.

- « Contraintes de progression » : les **19 dépendances** relevées dans les lots M et leurs
  fiches (une ligne « objectif → objectif : raison (lot Mnn) », datée du 25 octobre 2026) ;
  le **cycle M06-02 ↔ S10-02** est signalé « à trancher (question 9 du rapport de cohérence
  du 25 octobre 2026) », sans retirer aucune des deux dépendances.
- **3 lignes corrigées** : S12-02 → M03-22 (1 min = 60 s : durées en M03, partie 3, et non
  M04) ; S12-02 « 1 kg = 1 000 g » sans objectif prérequis (masses retirées de M03, CM1) ;
  notion « Pourcentage » de S01-04 expliquée dans sa propre fiche (M02-12 la reprend).
- S12 : « environ 4 séances » → environ 8 séances (estimation du 25 octobre : 7,8) ; code
  « EA » → « AE ».
- « Récapitulatif » : l'état réel recalculé des lots (séquences, objectifs, exercices par
  série, fiches, évaluations, tests courts, TP, AC, AT, mises en route), tableau par séquence ;
  l'inventaire des notions du 18 octobre est gardé pour mémoire.
- Aucun intitulé, aucun critère, aucune partie ne change : `outils/objectifs_6e.json` reste la
  transcription exacte (seule sa clé `source` mentionne la recopie du 25 octobre).

## Appli

- Modifiés : `outils/import_lot6e.py` (D-DOUBLON), `outils/ref6e_v2.md`,
  `outils/objectifs_6e.json` (source), `doc/ETAT_COURANT.md`.
- Tests : `tests/test_v0_54_1_lots_6e.py` (11).
- Aucune migration, aucune route, aucun générateur modifié : cycle 4, principal de 6e et mises
  en route produisent le même `.tex` (comparaison des sorties v0.54.0 / v0.54.1).
- Module LaTeX inchangé.

## Déploiement (Windows, appli fermée)

1. Sauvegarder `data\seqenseigne.db` (l'import en fait aussi une copie dans `sauvegardes\`).
2. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et `reference\lot6e\…`.
3. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py` (essai à blanc :
   13 documents « mis à jour » — les 12 de S01 à S03 et le TP de S12 —, aucune anomalie de
   titre en double), puis `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.
4. Lancer l'appli et regénérer les documents des séquences à envoyer.
