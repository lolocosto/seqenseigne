# Redémarrage v0.55.0 — cartes mentales de partie et fiches de cours plus graphiques (6e)

## Besoin (Laurent, 12 novembre 2026)

> « Modifier les fiches de cours de toutes les séquences de 6e pour avoir plus de graphiques,
> de tableaux, etc. et moins de texte […]. Et ajouter une carte mentale à chaque partie de
> séquence. »

Décisions de Laurent (format commun `reference\lot6e\FORMAT_CARTE_MENTALE.md` côté lots) : une
carte mentale par **partie de séquence principale** (S01–S13, pas les mises en route), dans le
livret **en fin de partie** (après les exercices), **à compléter** dans le livret élève,
**complète** dans le livret corrigé, compilable seule (« Rendu PDF », « Tout compiler »).

## Audit (état de la v0.54.3)

- Livret 6e : `services/livret_sequence_6e.py` (`lire_sequence_6e` → `corps_livret`), une page
  par objectif, fiches de résumé par objectif ; aucune notion de « carte » de partie.
- Fiches : `fiches_resume` (une par objectif) + `objectif_fiches` ; la fiche de cours d'une
  mise en route est une fiche sans objectif attachée aux objectifs de sa partie. Tout ce qui
  énumère les fiches (livret, fiches de cours, plan de travail, synthèse Pronote, format
  d'échange, contrôle « fiche exigée ») les prend toutes.
- Import : `outils/import_lot6e.py` met déjà à jour les fiches **non validées** (comparaison
  titre + sections), laisse les validées et le signale (anomalie) ; idem pour les fiches de
  cours des mises en route (`import_lot6e_mer.py`).
- « Tout compiler » (v0.54.2) : une table par modèle rattachée au catalogue
  (`services/sequence_tout_compiler.py`), un test exige que tout type du catalogue y soit rangé.

## Décisions

- **CM-MODULE** — Module `seqenseigne-style6e` **v0.13** : environnement
  `seqCarteMentaleSix`[sous-titre]{titre} et `\seqCMBranche{titre}{contenu}` (API du format).
  Bulle centrale (ellipse, couleur du thème `seqSixTheme`) ; branches en deux colonnes, sens
  anti-horaire (gauche 1…⌈n/2⌉ de haut en bas, droite de bas en haut) ; 5 mm au moins entre
  deux branches d'une colonne, branches réparties sur toute la hauteur (CM-TAILLE) ; trait de la
  bulle à chaque branche ; palette `seqSixCM1`…`seqSixCM8` (bord épais 1,6 pt, fond à 10 %,
  titre sur bandeau à 32 %). Dessin sur 20 cm de large, réduit (jamais agrandi) à la largeur de
  ligne et à la hauteur restante (nouvelle page si moins de la moitié reste) : une page A4 au
  plus. Branches composées en boîte avant le dessin : `\seqACompleter`, tableaux, formules,
  TikZ / tkz-euclide sans `tikzpicture` imbriqué. Corps des branches `\small` (10 pt dans les
  documents 11 pt), soit environ 9,2 pt après réduction dans le livret.
  Retour des lots S09–S13 : la bulle (texte de 2,9 cm) prend la largeur du mot le plus long
  du titre, sans césure, et la gouttière (4 cm au moins) s'élargit d'autant (« Proportionnalité »
  sur une ligne) ; les coupures manuelles déjà écrites dans les lots restent valables. Le
  `\foreach` signalé comme cassé dans une branche n'a pas été reproduit : avec babel français
  (`;` actif), boucle sans accolades, dans `\seqACompleter`, dans `\seqLocCadreTrace`, dans le
  préambule du livret, tout compile ; aucun changement de lecture des arguments (une relecture
  avec `;` ordinaire cassait au contraire les boucles sans accolades).
- **CM-TABLE** — Table dédiée `cartes_mentales` (une ligne par partie : `partie_id` UNIQUE,
  cascade ; titre, source LaTeX unique, `etat_code`, `mtime`, `niveau`/`sequence` dénormalisés),
  migration idempotente (`services/cartes_mentales.migrer`, appelée au démarrage et par
  l'import), classée « atelier » (`services/repartition.py`). Écartée : une fiche de résumé
  d'un type `carte_mentale` (il aurait fallu l'exclure partout où l'on énumère les fiches).
- **CM-CONTROLE** — Source acceptée si un seul environnement `seqCarteMentaleSix`, 1 à 16
  branches, seulement des macros `\seq…` connues du module (`services/style6e.py`) ;
  avertissement hors 4 à 8 branches. Même contrôle à l'import et dans l'atelier.
- **CM-LIVRET** — Carte émise après les exercices de la partie (et ses remédiations), sur une
  nouvelle page titrée « Carte mentale — Partie n » ; élève : à compléter ; corrigé (et corrigés
  enseignant) : complète. Partie sans carte : rien (même `.tex` — comparaison des 1589 sorties
  de la v0.54.3 sur la même base : identiques).
- **CM-DOC** — Document « Cartes mentales » (générateur commun à tous les modèles). Type de
  catalogue `cartes_mentales_6e` au modèle Fiches seulement : le catalogue Notions et méthodes
  reste celui des 9 types historiques (clés figées, G3) ; au cycle 4 les cartes sont dans le
  livret et se compilent seules depuis l'atelier. Au modèle Fiches : (« Cartes mentales », modèle Fiches :
  version élève/complète, découpage par séquence / annuel), producteur de l'orchestrateur,
  péremption (`cartes_mentales`, aussi pour le livret et les corrigés 6e) ; « Tout compiler » :
  `S03_cartes_mentales_eleve.pdf` et `…_complete.pdf` si la séquence a des cartes.
- **CM-ATELIER** (révisée le 12 novembre à 15 h 31, demande de Laurent) — Atelier dédié
  « Carte mentale » dans la portée Séquence, à côté de « Carte d'automatisme »
  (`static/atelier_carte_mentale.js`, panneau `atl-carte_mentale`, bouton
  `atl-btn-carte_mentale`) : niveau et séquence par les sélecteurs de la portée, liste des
  parties avec l'état de la carte et son nombre de branches, éditeur LaTeX (titre, état,
  source ; modèle proposé pour une partie sans carte), « Enregistrer », « Enregistrer et voir »
  (aperçu à compléter ou complet), « Supprimer », « Compiler » (la carte de la partie ou toutes
  celles de la séquence). Tous modèles (Fiches et Notions et méthodes). Routes
  `GET/PUT/DELETE /api/v2/livret-sequence/<niveau>/<séquence>/cartes-mentales[/<n>]`
  (blueprint `livret_sequence`, catégorie atelier) ; PDF par la route du livret
  (`?document=cartes_mentales&version=…&partie=…`, tout modèle). Séquence validée : lecture
  seule (409). L'onglet « Rendu PDF » d'une séquence principale ne garde que la compilation
  (partie, version) et un lien « Modifier dans l'atelier Carte mentale ».
- **CM-DONNEES-C4** — Toutes les séquences-niveaux, cycle 4 compris, ont des parties
  (`sequence_parties` : N10 14 séquences / 18 parties, N11 14 / 19, N12 14 / 18, N09 20 / 42
  dans la base de test ; aucune séquence sans partie) : on garde `partie_id` NOT NULL, pas de
  carte « de séquence entière » ; aucune migration de plus.
- **CM-LIVRET-C4** — Décision de Laurent : au modèle Notions et méthodes, la carte est la
  synthèse du cours, après le bloc notions/méthodes et avant les exercices, sur une nouvelle
  page, à compléter ; le livret du cycle 4 n'ayant qu'un bloc de cours pour toute la séquence,
  les cartes de ses parties s'y suivent, une par page, dans l'ordre des parties ; leur version
  complète suit les corrigés du livret (le livret du cycle 4 contient ses corrigés). Seulement
  quand le cours est inclus (livret, « Notions et méthodes ») ; sans carte : même `.tex`.
  Modèle Fiches : inchangé (fin de partie, après les exercices).
- **CM-TAILLE** — Retour du lot S01–S03 : réduite à la largeur, la carte n'occupait que le haut
  de la page. Elle est maintenant étirée en hauteur jusqu'à la place disponible (les branches
  de chaque colonne se répartissent sur toute la hauteur ; plus de plafond de 2 cm entre
  branches) ; elle n'est jamais agrandie en largeur ni ne dépasse la page.
- **CM-VALID** — Valider une séquence : une partie sans carte donne un avertissement (affiché
  dans le message de validation), jamais un blocage. Rien pour une mise en route ni au modèle
  Notions et méthodes.
- **CM-FORMAT** — Format d'échange **1.5** : `partie.carte_mentale` = `{id, titre}` (comme les
  fiches, tout modèle, référentiel interne), absent sans carte (document et empreinte inchangés ; les autres versions gardent
  leur règle « la plus petite version qui décrit le contenu »). Schéma et
  `doc/format_referentiel.md` à jour. La carte suit donc la séquence à la publication ; ses PDF
  sont publiés par le type `cartes_mentales_6e` (inactif par défaut) et par le livret.
- **CM-IMPORT** — Clé de lot `cartes_mentales` (format) : partie existante, contrôles
  CM-CONTROLE, idempotent, jamais sur une carte validée (anomalie) ; parties sans carte
  signalées ; essai à blanc : section « Fiches de résumé et cartes mentales » (fiches S et M
  mises à jour / inchangées / validées non modifiées, cartes par séquence).

## Appli

- Nouveaux : `services/cartes_mentales.py`, `static/atelier_carte_mentale.js`,
  `tests/test_v0_55_0_cartes_mentales.py` (26), `tests_js/cartes_mentales_atelier.test.js` (8),
  `doc/redemarrage_v0_55_0.md`.
- Modifiés : `paquet/seqenseigne-style6e.dtx` / `.sty` (v0.13), `paquet/CHANGELOG.md`,
  `services/style6e.py`, `services/livret_sequence_6e.py`, `services/livret_sequence.py`
  (cycle 4, seulement avec une carte), `services/gabarits_documents.py`,
  `services/orchestrateur_compilation.py`, `services/referentiel_documents_compilation.py`,
  `services/sequence_tout_compiler.py`, `services/peremption_atomes.py`,
  `services/repartition.py`, `services/v2_edition.py`, `services/format_referentiel.py`,
  `schemas/referentiel-1.json`, `doc/format_referentiel.md`, `persistence/sqlite_store.py`,
  `routes/livret_sequence.py`, `templates/index.html`, `static/app.js`,
  `static/atelier_filtres_hook.js`, `static/atelier_seqniv_assemblage.js`,
  `static/seqniv_pur.js`, `outils/import_lot6e.py`, `outils/import_lot6e_mer.py`,
  `doc/ETAT_COURANT.md`, 12 tests qui fixaient la version du module (v0.12), du format (1.4)
  ou une liste fermée (catalogue 6e, péremption).
- Migration : table `cartes_mentales` (idempotente). Même `.tex` sans carte : 1589 sorties de la
  v0.54.3 (cycle 4, 6e, mises en route, export de N11_v2025) comparées sur la même base,
  identiques. N11_v2025 : rien d'écrit, aucune carte.

## Déploiement (Windows, appli fermée)

1. Sauvegarder `data\seqenseigne.db`.
2. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et `reference\lot6e\…`.
3. Module LaTeX v0.13, depuis la racine : `copy /Y appli\paquet\seqenseigne-style6e.dtx
   reference\paquet\`, puis `cd reference\paquet`, `tex seqenseigne.ins` et `cd ..\..`.
4. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py` (essai à blanc :
   section « Fiches de résumé et cartes mentales » : 52 fiches S et 22 fiches M mises à jour,
   20 cartes créées), puis `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.
5. Lancer l'appli ; Atelier › portée Séquence › « Carte mentale » ; « Rendu PDF » d'une
   séquence : livret (carte en fin de partie), « Compiler les cartes mentales », « Tout compiler ».

## Risque

Une fiche ou une carte **validée** dans l'atelier n'est jamais mise à jour par l'import
(signalée en anomalie et dans le résumé de l'essai à blanc) : la repasser « en cours » avant
l'import si l'on veut la nouvelle version.
