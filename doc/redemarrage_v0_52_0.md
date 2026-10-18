# Redémarrage v0.52.0 — Import des séquences de 6e dans l'atelier

## Besoin

Le référentiel de 6e est refait pour le nouveau programme : dix séquences
numérotées par thème (S01 Nombres… S10 Pensée informatique), contenus de
l'équipe de 6e repris en LaTeX et fusionnés avec les 411 exercices de 6e de
la base (lots `S01\S01.json`, `S02\S02.json`, `S03\S03.json`). v0.52.0 livre
l'outil d'import et le nouveau découpage du cycle 3 ; le livret au style de
l'équipe viendra en v0.52.1.

## Décisions validées (18 octobre)

Cible N09 de l'atelier interne (comme le cycle 4) ; X2026_N09 et M2026_N09
non touchés ; C03 remplacé par 10 séquences / 6 thèmes ; anciens N09
recodés avant import ; .tex pour les documents hors base.

## Décisions prises à l'audit (option non destructive)

- **D1 Archivage dans la base, par recodage.** Anciennes séquences du
  cycle 3 : `S01…S16` → `X01…X16`, numéro + 100, nom suivi de « (archive) » ;
  anciens thèmes `A, B, C` → `XA, XB, XC` (le nom « Grandeurs et mesures »
  est repris par le nouveau B : contrainte d'unicité). Rien n'est supprimé,
  les identifiants ne changent pas : objectifs, évaluations et révisions qui
  pointent vers les anciens exercices suivent. Fait **une seule fois** :
  la présence d'une séquence `Xnn` en C03 marque l'archivage (sinon une
  deuxième exécution archiverait les nouveaux S01…). Sauvegarde `.db` et
  journal JSON (ancien → nouveau code, pour revenir en arrière) dans
  `<dossier de la base>\sauvegardes\`.
- **D2 Périmètre.** Tout ce qui est rattaché aux anciens codes en CM1, CM2 et
  6e est archivé : séquences-niveaux, exercices, notions, méthodes, fiches,
  cartes, et les précédences portées par des séquences du cycle 3. **Le
  cycle 4 n'est jamais modifié** : ses précédences vers `N09/Snn` gardent
  l'ancien code (qui désigne désormais la nouvelle séquence) ; l'outil les
  liste en anomalies, à revoir dans l'atelier. Les référentiels figés
  (`referentiel_*`) ne sont pas touchés.
- **D3 CSV `data\C03_*.csv` inchangés** (graine d'installation neuve,
  partagée avec CM1 et CM2). Le modèle « programme du cycle »
  (`services/modeles_referentiel.py`) n'utilise plus les objectifs du CSV
  que pour la séquence du CSV (même code et même nom) et ignore les
  archives `X…` : S04 « Pré-algèbre » ne reçoit pas les objectifs de
  l'ancienne S04 « Calcul mental ».
- **D4 Noms** des séquences et des thèmes : titres de `col6/ref6e_v2.md`
  (S01 « Nombres entiers et décimaux, fractions », S08 « Probabilité »),
  figés dans `outils/objectifs_6e.json` (généré une fois, versionné).
- **D5 Objectif « Cours »** dans chaque partie (01, 11, 21, 31), libellé et
  critères du cycle 4 (« Connaître les notions et les méthodes. »). Critère
  E des capacités : « Utilise ce savoir-faire pour résoudre un problème. »
- **D6 Activités d'introduction** : exercices de série approche (`AE`),
  rattachés à la partie (`partie_exos_revision_approche`, rôle `EA`), dans
  l'ordre objectif puis numéro — modèle de l'atelier, seul lu par le livret
  et le plan de travail (`numerotation_livret` ignore `objectif_exos` AE).
  L'objectif d'origine est dans le journal.
- **D7 Fiches de résumé** : une par objectif (`fiches_resume.objectif_id`),
  attachée au « Cours » de la partie (`objectif_fiches`) ; chaque
  `\seqSectionFicheSix{titre}` devient une section de l'atelier Fiche.
- **D8 Évaluations en `.tex`, pas dans le module Évaluations.** Le module
  génère le gabarit du cycle 4 (`\seqTitreEval`, barème par exercice,
  exercices de la banque rangés dans une série) ; le gabarit 2026 de
  l'équipe (barème par compétence, `\seqExoEval`) n'y entre pas sans
  créer des exercices parasites dans les séries de la séquence. Barèmes et
  objectifs évalués sont dans `documents.json`.
- **D9** Un élément **validé** dans l'atelier n'est jamais écrasé (signalé).
- **D10 Lots livrés hors `appli\`** (`reference\lot6e\`) : contenus de
  l'équipe et captures de manuels, non poussés sur GitHub.
- **D11 Couleur `proportionnalite`** (thème E, Canard / Orange) ajoutée au
  sélecteur des thèmes, aux couleurs valides du rendu et des référentiels
  externes.
- **D12** Essai à blanc = exécution complète sur une copie en mémoire de la
  base : l'aperçu est exactement ce que fera `--apply`.
- **D13** Base par défaut = celle du profil atelier (`data_atelier\` après
  la bascule, `data\` sinon) ; une base « classe » est refusée.

## Code

- `outils/import_lot6e.py` (nouveau), `outils/objectifs_6e.json` (nouveau).
- `services/modeles_referentiel.py` (D3), `services/couleurs_themes.py`,
  `services/latex_rendu_atome.py`, `services/referentiel_principal_externe.py`,
  `static/referentiel_pe.js`, `static/ateliers_seqniv_v2_edit.js` (D11).
- Tests : `tests/test_v0_52_0_import_lot6e.py` (27) ;
  `tests/test_R2_themes_routes.py` (7 familles de couleurs).

## Dépendance paquet

Les `.tex` hors base et les futurs livrets chargent
`\usepackage[sixieme,geometrie]{seqenseigne}` sans `local.tex` : il faut
`seqenseigne-style6e` v0.4 (macros `\seqLoc…` intégrées), l'option `sixieme`
et la couleur `proportionnalite` de `seqenseigne-theme`, livrés à part dans
`paquet\`.

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et `reference\lot6e\…`.
2. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py`
   (essai à blanc : lire les anomalies).
3. `..\outils\python\python.exe .\outils\import_lot6e.py --apply`
4. Documents hors base : `..\reference\lot6e\documents_tex\Snn\` (compiler
   deux fois les versions élève et corrigée).

## Correctif du 18 octobre (soir) — clés étrangères restées sur `objectifs_v2`

Symptôme chez Laurent : l'essai à blanc s'arrête sur
`sqlite3.IntegrityError: FOREIGN KEY constraint failed` en posant le premier
lien objectif ↔ exercice.

Cause : dans les bases créées avant v0.14.7, le renommage
`objectifs_v2` → `objectifs` n'avait pas réécrit les clés étrangères de sept
tables (`objectif_exos`, `objectif_notions`, `objectif_fiches`,
`objectif_cartes`, `fiches_resume`, `evaluation_objectifs`,
`ui_etat_atelier_sequence`), qui visaient encore `objectifs_v2`. La
réconciliation objectifs ← objectifs_v2 masquait le problème ; depuis son
retrait (v0.51.13), tout lien vers un objectif créé après coup échoue — dans
l'outil comme dans l'appli. `retraits.retirer_residus` gardait
`objectifs_v2` parce qu'elle était encore référencée.

Correction (`services/retraits.py`, `rediriger_objectifs_v2`) : pour ces sept
tables seulement, réécriture de la contrainte dans `sqlite_master`
(procédure SQLite pour un changement de contrainte seule, schema_version
incrémenté, quick_check ensuite). Les liens qui ne visent aucun objectif de
`objectifs` sont sauvegardés en JSON (`sauvegardes\retrait_liens_objectifs_v2_*.json`)
puis retirés (mis à NULL pour `ui_etat_atelier_sequence`). Appelée au
démarrage de l'appli (avant `retirer_residus`, qui retire alors
`objectifs_v2`) et en tête de l'import 6e (validée à part, avant l'import).
Une table inconnue qui viserait `objectifs_v2` n'est pas touchée.

Vérifié sur une copie de la base atelier de Laurent : 0 lien orphelin,
essai à blanc puis `--apply` deux fois sans erreur, `foreign_key_check` vide,
`integrity_check` ok ; au démarrage suivant, `objectifs_v2` est retirée.
