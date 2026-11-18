# Redémarrage v0.60.0 — version 2 du modèle Fiches (rituels, tests courts, durées) et correctifs d'import

> Base de comparaison : 2846878 « v0.59.3 » (origin/main). Brief : `col4/BRIEF_V0600.md`.
> Schéma : 2 colonnes (`evaluations.type_evaluation`, `evaluations.duree`) et 1 table
> (`progression_rituels`), ajoutées au démarrage, valeurs neutres. Paquet LaTeX inchangé.

## Découpage

Le périmètre (12 points) est trop gros pour une livraison : **v0.60.0** = A1 à A3 (rituels
selon la progression, tests courts, durées et séances d'évaluation) + B6 à B10 (correctifs
d'import) + essai de l'archivage de N10 (A5). **v0.60.1** = A4 (cartes dans le plan de
travail, saisie du titre court, avertissement « objectif sans carte »), documents « séance
d'évaluation » et « Tests courts » au catalogue, C11 et C12, F4 (voir `doc/ROADMAP.md`).
Ajoutés en cours de route (coordinateur, étape 3 de la 5e) : F1 à F3 et le point 5 sont dans
la v0.60.0.

## Ce qui change pour Laurent

1. **Atelier Référentiel › Documents à publier** d'un référentiel principal au modèle Fiches
   (2027_N11, 2026_N09…) : nouveau cadre **« Rituels d'automatismes et séances
   d'évaluation (progression) »**. On y écrit l'**ordre des parties** dans l'année, une par
   ligne : `A1-P1`, `B1-P1`, `A2-P1`… (`A2-P2 1` impose 1 semaine ; sinon séances de la
   partie ÷ 3). « Enregistrer l'ordre » contrôle la saisie (partie inconnue, en double :
   rien n'est écrit) et affiche le calendrier semaine par semaine : parties, cartes
   nouvelles, réactivées, à revoir, séance d'évaluation. « Compiler le PDF » produit le
   document (un tableau de la progression, puis une page par semaine avec les listes et
   la grille des cartes recto/verso). Jour d'évaluation et cartes du document
   (nouvelles et réactivées / toutes / aucune) réglables.
2. **Module Évaluations** (modèle Fiches) : **Type** (évaluation / test court) et **Durée**
   (vide = automatique : 10 min par objectif évalué, 10 min pour un test court). Les
   évaluations « Test court --- … » déjà importées sont reconnues comme tests courts au
   premier démarrage (N09 : 25, N11 : 16 sur la copie), sans qu'aucun document devienne
   périmé.
3. **Sujets en deux parties** : la partie sans calculatrice dure la part de la durée de
   l'évaluation qui revient à ses objectifs : 4e A3 « Puissances et racine carrée »
   45 → **40 min** (+ 10), 4e A4 « Équations » 40 → **20 min** (+ 10), 6e A3 « Ordre de
   grandeur et multiplication » 40 → **30 min** (+ 10). La durée réglée à la main prime.
4. **Import des lots** :
   - clé `tests_courts` (même format que `evaluations`) ; un titre « Test court --- … »
     dans `evaluations` est aussi un test court ;
   - activités de découverte **sous l'objectif « Cours »** : `{"code": "A1-01",
     "activites": [...]}` (ou `{"code": "Cours", "partie": 1, ...}`) ; le livret les place
     en ouverture de partie, avant le premier objectif ;
   - clé `variables` des exercices, activités et TP/AC/AT (bloc `\xintdef…var`, comme
     les exercices paramétrés de la base ; absente : valeur en base gardée) ;
   - nouvelle section **« Avertissements (non bloquants) »** : bonus d'une évaluation
     différent de 1 point (hors 6e), test court qui n'est pas sur 10 ou dont le bonus
     n'est pas 1, partie sans test court ou avec plusieurs, variable déclarée par deux
     exercices.
5. **Outil `outils/migrer_ae_cours.py`** : range sous « Cours » les 16 activités de
   découverte des lots de 4e (une par partie, mises sous le premier objectif faute de
   mieux).
6. Titres d'exercices du livret Fiches échappés (`%`, `&`, `#`, `_` hors `$…$`).
7. **5e** (étape 3 de la 5e, `col4/5e/besoins_appli_5e.md`) :
   - `import_lot6e.py --niveau N10` (lots dans `..\reference\lot5e`, référentiel
     `outils/objectifs_5e.json`) ;
   - l'archivage (`archiver_structure_niveau.py`) affiche un **avertissement** pour chaque
     référentiel interne du niveau « en cours » ou « validé » (sans instantané, il lit la
     structure vivante) : 2025_N10 et 2025_N12 sur la copie.
8. **Niveau de création des cartes** corrigible : atelier Carte d'automatisme, liste
   « Niveau de création » (enregistrée tout de suite, **même sur une carte validée**) ; par
   l'import, une carte validée dont seul ce champ change est corrigée (avertissement). Le
   rendu de la carte ne change pas : aucun document périmé. Une carte de 6e (N09) écrite en
   5e est **réactivée**, jamais « nouvelle », dans les rituels.

## Décisions

- **P0 — Pas de progression ordonnée dans l'atelier** (audit) : les progressions et
  créneaux vivent côté classe (un passage par séquence, des dates, ni partie ni semaine) ;
  `objectifs.nb_seances` et `referentiel_parties_seances` donnent des durées, pas un ordre.
  Le document est calculé depuis un **ordre des parties saisi** (table
  `progression_rituels`, une ligne par référentiel : ordre JSON, paramètres), et rangé
  **hors catalogue** des documents du référentiel : il ne change ni la validation, ni le
  verrouillage, ni la publication (référentiel et progression restent disjoints). Le
  chantier « progressions » côté classe pourra fournir l'ordre plus tard.
- **P1 — Semaines** : semaines saisies, sinon ⌈séances / 3⌉, au moins 1 ; parties
  enchaînées depuis la semaine 1 ; 30 semaines par an (réglable).
- **P2 — Cartes nouvelles** (niveau de création = niveau du référentiel) : rituel la
  semaine qui suit la fin de la partie.
- **P3 — Rappels** : 1 semaine (J+7) et 4 semaines (J+30) après, puis toutes les
  6 semaines jusqu'à la dernière semaine (réglables).
- **P4 — Réactivation** : cartes d'un niveau inférieur (5e en 4e) au début de la partie,
  puis même cycle ; une carte de plusieurs parties compte une fois, à la première.
- **P5 — Séances d'évaluation** : semaines paires, jour fixe affiché ; l'évaluation d'une
  partie va à la première séance au plus tôt la semaine qui suit la fin de la partie ;
  50 min et 5 objectifs au plus, sinon séance suivante (une évaluation trop longue est
  seule, signalée). Une évaluation à cheval sur deux parties va après la dernière. Les
  tests courts ne sont pas placés (à décider : voir Questions).
- **P6 — Dernière séquence non évaluée** : règle de progression seulement (la séquence de
  la dernière partie de l'ordre) ; dans le référentiel, toutes les séquences gardent leur
  évaluation.
- **P7 — Cartes validées seulement** dans le document ; les autres sont comptées dans
  « À vérifier ».
- **T1 — Type d'évaluation** : colonne `type_evaluation` ; reconnaissance par le titre une
  seule fois (à l'ajout de la colonne), sans toucher `mtime` ; ensuite seuls l'import et le
  module écrivent le type.
- **T2 — Durée** : colonne `duree` (NULL = 10 min × objectifs évalués ; test court 10 min).
- **T3 — Partie sans calculatrice (B8)** : chaque objectif pèse 1/n de la durée de
  l'évaluation ; part de ses points en partie 1 ; arrondi aux 5 min, au moins 10, au plus
  la durée. Remplace 55 min × points de la partie 1 / total (v0.52.9, D4).
- **B6 — « Cours »** : activités seulement (exercices, fiche, cartes, encarts sous
  « Cours » : anomalie, ignorés) ; une activité passée sous « Cours » quitte les objectifs
  de la partie et son `mtime` est rafraîchi (livret et corrigés périmés, à recompiler).
- **B6b — Outil de migration** : déplace les activités du **premier objectif** de chaque
  partie vers « Cours » ; 6e exclue (activités rangées sous leur objectif à dessein) ;
  séquence validée jamais touchée ; idempotent ; sauvegarde et journal.
- **B9** : le titre de carte était déjà échappé depuis la v0.59.1 (seul point d'insertion,
  aperçu isolé) — présent sur GitHub depuis la v0.59.3 ; l'échappement commun
  (`latex_texte.speciaux_latex`) est étendu aux titres d'exercices et d'activités du livret
  Fiches (titres sans ces caractères : `.tex` identique).
- **F2** : avertissement, pas refus (consigne du coordinateur) ; référentiels internes du
  niveau en état « en cours » ou « validé ».
- **F3** : `niveau_creation` vide = niveau de la carte ; valeurs N09 à N12 ; route dédiée
  `PUT /api/cartes/<id>/niveau-creation` (hors verrou de la carte validée) ; mtime gardé.
- **F4 (reporté en v0.60.1)** : les exceptions de l'avertissement « objectif sans carte »
  seront une **propriété de l'objectif** lue dans les lots (« sans carte voulue »), pas une
  liste de codes de 4e (A3-04… désignent d'autres objectifs en 5e).
- **B10 / B10b** : bonus ≠ 1 signalé seulement ; **hors 6e** : les 18 évaluations des lots
  de 6e ont un bonus de 2 points (convention de l'équipe ?).

## Marche à suivre (Windows)

1. Fermer l'appli, décompresser `seqenseigne_v0_60_0_delta.zip` à la racine (le dossier
   `appli\` du zip sur `appli\`), puis depuis `appli\` :
   ```
   ..\outils\python\python.exe .\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
   .\lancer.bat atelier
   ```
   Au démarrage : colonnes `type_evaluation`, `duree` et table `progression_rituels`
   ajoutées ; tests courts reconnus. Aucun référentiel ne change d'état.
2. **Rituels de la 4e** : Conception de référentiel › Niveau › 4ème › **Référentiel** ›
   « 4e — 2027-2028 — Principal » › **Documents à publier** › cadre « Rituels… » : écrire
   l'ordre des 16 parties, **Enregistrer l'ordre**, lire le calendrier et « À vérifier »,
   **Compiler le PDF** (compilation de 1 à 2 minutes, document d'environ 50 pages avec les
   cartes nouvelles et réactivées).
3. **Activités sous « Cours »** (4e) : repasser A1…E1 en cours (Séquence › — Toutes les
   séquences — › A1, Maj+clic E1 › ⟲ En cours), puis depuis `appli\` :
   ```
   ..\outils\python\python.exe .\outils\migrer_ae_cours.py --niveau N11
   ..\outils\python\python.exe .\outils\migrer_ae_cours.py --niveau N11 --apply
   ```
   (16 activités attendues), revalider A1…E1, recompiler **Livret de séquence** et
   **Corrigés** de 2027_N11 (périmés).
4. Prochains lots : écrire les activités de découverte sous `"code": "A1-01"` (partie 1),
   `"A2-11"` (partie 2)… ; tests courts dans `tests_courts` ou titrés « Test court --- ».
5. **Corriger les ~15 cartes de 4e au mauvais niveau de création** (inventaire de la 5e,
   § 3) avant de compiler les rituels : atelier Carte d'automatisme › carte › « Niveau de
   création », ou dans les lots puis import.
6. **5e** : annuler ou valider + verrouiller **2025_N10** ; puis depuis `appli\` :
   ```
   ..\outils\python\python.exe .\outils\archiver_structure_niveau.py --niveau N10
   ..\outils\python\python.exe .\outils\archiver_structure_niveau.py --niveau N10 --apply
   ..\outils\python\python.exe .\outils\import_lot6e.py --niveau N10
   ..\outils\python\python.exe .\outils\import_lot6e.py --niveau N10 --apply
   ```
   (archivage essayé sur une copie : 12 séquences, instantanés N10_v2021…v2024 intacts,
   `--annuler` fonctionne ; aucun lot de 5e encore disponible pour l'import).

## Pièges

- **2025_N10** est « en cours » (non figé) : après l'archivage de N10, il suivrait la
  nouvelle structure. Le valider et le verrouiller avant, ou l'annuler.
- Les évaluations **validées** dans le module ne sont pas réimportées (règle R4) : les
  avertissements de barème s'affichent quand même.
- Le document de rituels n'est pas dans « Documents à publier » : il n'est ni verrouillé ni
  publié avec le référentiel (PDF dans `referentiels\<id>\_rituels\`).
- 2026_N09 (verrouillé) : seuls ses sujets **régénérés** auraient 30 min au lieu de 40
  (A3) ; ses PDF figés ne changent pas.
- Les rappels s'accumulent en fin d'année (30 à 40 cartes par semaine avec 16 parties) :
  période réglable (paramètre `periode_rappels`, par l'API pour l'instant).

## Questions à trancher

1. Tests courts dans les séances d'évaluation (10 min chacun) ou dans les rituels ?
2. Bonus de 2 points des évaluations de 6e : voulu (règle propre à la 6e) ?
3. Période des rappels après J+30 : 6 semaines conviennent-elles ?

## Fichiers

Nouveaux : `outils/objectifs_5e.json` (copie de `col4/5e/objectifs_5e.json`),
`services/evaluations_v2.py`, `services/progression_rituels.py`,
`routes/progression_rituels.py`, `outils/migrer_ae_cours.py`,
`tests/test_v0_60_0_version2_fiches.py`, `tests_js/v0_60_0_rituels_type_evaluation.test.js`,
`doc/redemarrage_v0_60_0.md`. Modifiés : `outils/import_lot6e.py`, `services/evaluations.py`,
`routes/evaluations.py`, `services/render_evaluation.py`, `services/livret_sequence_6e.py`,
`services/orchestrateur_compilation.py`, `services/profils.py`, `persistence/sqlite_store.py`,
`app.py`, `services/repartition.py`, `services/cartes_automatisme.py`,
`routes/cartes_automatisme.py`, `outils/archiver_structure_niveau.py`,
`static/atelier_carte_automatisme.js`, `tests/test_v0_52_9_deux_parties.py` (attentes D4 → T3),
`static/atelier_evaluation_oo.js`, `static/atelier_referentiel.js`,
`templates/index.html`, `doc/ROADMAP.md`, `doc/ETAT_COURANT.md`, `paquet/CHANGELOG.md`.
Aucun fichier supprimé.

## Risques

- Durées de partie 1 changées pour les 3 sujets en deux parties (voulu, B8).
- Le calendrier dépend de `objectifs.nb_seances` : une partie sans séances compte
  1 semaine (signalé).
- Pas de lien avec la progression côté classe : l'ordre saisi n'est connu que de l'atelier.
