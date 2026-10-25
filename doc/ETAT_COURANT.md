# ÉTAT COURANT — seqenseigne

> Fichier de synthèse pour retrouver rapidement l'état du projet au début d'une
> session. À lire en premier. Mis à jour à chaque livraison.

## Version déployée

**v0.53.2** (dernière livrée). Historique complet : `doc/redemarrage_v0_*.md`.

## Chantier en cours : référentiel de 6e (v0.52)

Cadrage : `doc/redemarrage_v0_52_0.md`. Les séquences de 6e (nouveau
programme, contenus de l'équipe de 6e repris en LaTeX, lots S01, S02, S03…)
sont importées dans l'atelier interne (N09) ; le découpage du cycle 3 est
remplacé par 10 séquences groupées en 6 thèmes (A à F).
- v0.52.0 livrée : outil `outils/import_lot6e.py` (essai à blanc / --apply,
  sauvegarde, idempotent), référentiel `outils/objectifs_6e.json`, archivage
  réversible de l'ancien cycle 3 (codes X01…X16, thèmes XA…XC, 411 anciens
  exercices de 6e recodés Snn → Xnn), couleur de thème `proportionnalite` ;
  travaux personnels, activités complémentaires, séances d'atelier et
  évaluations écrits en `.tex` (hors base). Exige `seqenseigne-style6e` v0.4
  et l'option `sixieme` du paquet (livrés à part dans `paquet/`).
- Correctif v0.52.0 (18 octobre, soir) : `services/retraits.py`
  (`rediriger_objectifs_v2`) redirige vers `objectifs` les clés étrangères de
  7 tables de liens restées sur `objectifs_v2` dans les bases d'avant v0.14.7
  (cause du « FOREIGN KEY constraint failed » de l'import 6e, et de tout lien
  vers un objectif créé depuis v0.51.13) ; `objectifs_v2` est ensuite retirée
  au démarrage. Détails : `doc/redemarrage_v0_52_0.md`.
- Correctif 2 v0.52.0 : `services/style6e.py` — le module
  `seqenseigne-style6e` est chargé en entier par `\usepackage` quand ses
  macros sont utilisées (pas importé par « Import mise en forme ») ;
  `reference\paquet` ajouté au TEXINPUTS ; dossier `Remediation\` créé avant
  pdflatex ; titres de section de fiche avec virgule entre accolades.
- v0.52.1 livrée : gabarit de documents par référentiel
  (`referentiel_niveaux.gabarit_documents` : `cycle4` défaut, `sixieme`
  proposé en 6e ; catalogue `services/gabarits_documents.py` ; CHECK des 9
  types levée) ; livret de séquence 6e, fiches de cours 6e, corrigés 6e
  (`services/livret_sequence_6e.py`) ; format d'échange 1.1 ; côté classe,
  documents du référentiel de la progression, actifs, du gabarit. Cycle 4
  inchangé au caractère près. Détails : `doc/redemarrage_v0_52_1.md`.
- v0.52.2 livrée : documents de 6e hors livret dans les ateliers existants —
  séries EV (sujet A dans l'énoncé, sujet B dans la remédiation, cadre
  « Sujet B »), TP, AC, AT de l'atelier d'exercices (hors de tous les
  livrets : listes fermées, audit), évaluations 6e (module Évaluations,
  barème par compétence, bonus hors total, sujet A/B, version), catalogue
  `sixieme` complété (évaluations, travaux personnels, activités
  complémentaires, séances d'atelier ; proposés côté classe avec leur
  séquence, délai sur l'association) ; import 6e en base (plus de `.tex`,
  activités reliées à leur objectif). Cycle 4 inchangé au caractère près.
  Détails : `doc/redemarrage_v0_52_2.md`.
- v0.52.3 livrée (retours de Laurent sur v0.52.2) : activité d'approche
  enregistrée dans l'atelier qui changeait de code (AE03 → EA01, mapping
  `atomes._SERIE_VERS_CODE`) et disparaissait de la liste — corrigé, outil
  `outils/reparer_series_approche.py` à lancer AVANT tout réimport des lots ;
  onglet « Rendu PDF » du module Évaluations qui restait figé ; rendu
  d'atome des exercices de 6e au format de l'équipe
  (`services/rendu_atome_6e.py`) ; plan de travail de séquence 6e au format
  de l'équipe (`services/plan_travail_6e.py`, type `plans_travail_6e`) ;
  lots S01–S03 complétés de leurs corrigés (`reference\lot6e`). Cycle 4
  inchangé au caractère près. Détails : `doc/redemarrage_v0_52_3.md`.
- v0.52.4 livrée : le gabarit devient un **modèle de référentiel**,
  indépendant du niveau — « Notions et méthodes » (`cycle4`) ou « Fiches de
  résumé par objectif » (`sixieme`), choisi à la création avec sa
  description ; atelier piloté par le modèle du référentiel interne
  principal du niveau quel que soit son état (R1b), plus par « N09 » ;
  série E facultative et fiche exigée au modèle « Fiches » ; synthèse
  Pronote et format d'échange 1.2 (fiches de résumé de la partie) ; objectif
  sans méthode, fiche de l'objectif et séries EV/TP/AC/AT dans
  l'assemblage ; « Connaître le cours » ; module `seqenseigne-style6e` v0.5
  (niveau paramétrable : `tex seqenseigne.ins` à relancer). Cycle 4
  inchangé au caractère près. Détails : `doc/redemarrage_v0_52_4.md`.
- v0.52.5 livrée : `outils/objectifs_6e.json` complété de S01 à S13
  après le découpage de la géométrie (19 octobre 2026 : S05 Points,
  segments, droites ; S06 Cercles ; S07 Angles ; S08 Triangles ; anciennes
  S06 à S10 → S09 à S13 ; l'import renomme sur place les séquences du
  cycle 3 et crée S11 à S13) (52 objectifs, transcription exacte de `outils/ref6e_v2.md`, protégée par
  un test ; séquence sans partie déclarée = une partie « nom de la
  séquence ») ; module `seqenseigne-style6e` v0.6 (macros du lot S05 :
  `\seqLocCadreTrace`, `\seqLocAngle`, `\seqLocRapporteur`, style TikZ
  `seqLocCorr` ; du lot S04 : schémas en barres et balance ;
  `tex seqenseigne.ins` à relancer) ; lots S04 « Pré-algèbre », S05 à S08
  (géométrie découpée) et S09 « Symétrie axiale » dans `reference\lot6e` ; l'import signale une macro `\seqLoc`
  absente du module ; page de garde du livret 6e par partie (titre « Partie
  n — libellé », trait de la couleur du thème). Cycle 4 inchangé au
  caractère près. Détails : `doc/redemarrage_v0_52_5.md`.
- v0.52.6 livrée : référentiel principal de 6e complet — lots S01 à S13
  dans `reference\lot6e` (S01 à S03 recomposés : une évaluation sur 20 par
  séquence, tests courts réservés aux mises en route) ; l'import retire les
  évaluations listées dans `evaluations_retirees` (si non validées) et les
  exercices EV devenus orphelins, avec sauvegarde et journal de restauration
  (décisions R1 à R4 : retirer avant d'importer, numéro EV occupé jamais
  réattribué, liens EV périmés retirés, évaluation validée intouchée) ;
  dépendances entre objectifs des lots S04 à S13 ajoutées aux « Contraintes
  de progression » de `outils/ref6e_v2.md` ; `doc/doublons_6e_5e.md`
  (exercices de 5e copiés en 6e, pour la migration du référentiel de 5e).
  Cycle 4 inchangé au caractère près. Détails : `doc/redemarrage_v0_52_6.md`.
- v0.52.7 livrée : marqueurs « ordinateur » (Scratch, GeoGebra, tableur,
  autre) et « calculatrice » (autorisée, interdite) des exercices
  (`exercices.ordinateur`, `exercices.calculatrice`,
  `services/marqueurs_exercices.py`) : listes dans l'en-tête de l'atelier
  d'exercices et indicateur dans la liste ; pictogrammes dans l'en-tête de
  l'exercice du livret 6e (module `seqenseigne-style6e` v0.7 :
  `tex seqenseigne.ins` à relancer) ; mention dans `nom=` au cycle 4 si
  marqué ; plans de travail 6e et cycle 4 (mention + encadré « Matériel à
  prévoir ») ; format d'échange 1.3 (`partie.materiel`) et table classe
  `referentiel_materiel_publie` pour le futur tableau de bord ; import des
  clés `ordinateur` / `calculatrice` des lots. Remédiation et sujet B
  suivent le marquage de l'exercice. Cycle 4 inchangé au caractère près sans
  marqueur. Détails : `doc/redemarrage_v0_52_7.md`.
- v0.52.8 livrée (décisions de Laurent du 20 octobre) : la mention
  « calculatrice » du sujet d'une évaluation 6e suit le marquage de ses
  exercices EV (un « autorisée » suffit, sinon interdite) sauf réglage de
  l'évaluation (`evaluations.calculatrice`, écrit par l'import, liste
  « Calculatrice » du module Évaluations, avertissement si contraire aux
  exercices) ; option du document « Évaluations » « selon l'évaluation » ;
  travaux personnels hors « Matériel à prévoir » et hors données du tableau
  de bord ; astuce `\seqAstuceSix` (module `seqenseigne-style6e` v0.8 :
  `tex seqenseigne.ins` à relancer) ; critères de S05-12 (référentiel 6e
  du 20 octobre), mise à jour des critères signalée par l'import ; lots
  S01–S13 (astuces, bonus). Cycle 4 inchangé au caractère près. Détails :
  `doc/redemarrage_v0_52_8.md`.
- v0.52.9 livrée (besoin de Laurent du 20 octobre) : évaluation 6e en deux
  parties, façon DNB, quand des exercices EV interdisent la calculatrice et
  d'autres l'autorisent (D1) : partie 1 « sans calculatrice » ramassée au
  bout de N min (55 × points partie 1 / total hors bonus, arrondi aux 5 min,
  au moins 10 ; réglable, `evaluations.duree_partie1`), partie 2
  « calculatrice autorisée » sur une nouvelle feuille (page impaire),
  numérotation continue, barème unique en tête de la partie 1 ; sujets A/B,
  élève/corrigé ; indication et durée dans le module Évaluations ; clé de
  lot `calculatrice_exercices` (marquage par exercice) ; lots S01–S13
  (astuces Scratch avec lien, S03 « Ordre de grandeur et multiplication »
  coupée). Sujet d'un seul tenant et cycle 4 inchangés au caractère près ;
  module LaTeX inchangé. Détails : `doc/redemarrage_v0_52_9.md`.
- v0.53.0 livrée (21 octobre) : rendu par lot en 6e (« niveau invalide :
  'N09' » : niveaux N09 à N12 et de `param_niveaux`, séquences Snn, Mnn, Xnn ;
  fiche de résumé au modèle « Fiches » rendue au format de l'équipe, B2) ;
  mises en route de 6e au modèle « Fiches » (MR1 à MR7) : séquences `Mnn` de
  l'atelier N09 (C03 Mnn n° 200 + n, une partie, objectifs 01… sans objectif
  Cours), série `MR` (exercice de séance, numéro = séance), fiche de cours de
  séquence (fiche sans objectif), tests courts sur 10 (module Évaluations),
  documents par séquence Mnn dans l'onglet « Rendu PDF » de l'assemblage
  (fiche de cours, exercices de séance 2/3/4 par A4, test court, plan de
  séquence ; `services/mises_en_route_6e.py`), validation MR6, hors du
  principal (MR7) ; import des lots `Mnn` par `import_lot6e.py`
  (`outils/import_lot6e_mer.py`, ref6e_v2 « Mises en route » fait foi) ;
  module `seqenseigne-style6e` v0.9 (`\seqLocItemCM`, `tex seqenseigne.ins`
  à relancer) ; lot M01 « Calcul mental » dans `reference\lot6e`. Leitner,
  cartes et cycle 4 inchangés au caractère près. Détails :
  `doc/redemarrage_v0_53_0.md`.
- v0.53.1 livrée (22 octobre) : mises en route **en parties** (décision de
  Laurent : chaque objectif à un moment différent de l'année) — une partie par
  objectif (paires liées en M02, M03, M05), codes de la règle du principal
  (M01-02, M01-12…), libellé de partie (`sequence_parties.libelle`), une
  fiche de cours et un test court par partie (fiche attachée aux objectifs de
  sa partie), documents par partie dans l'onglet « Rendu PDF » et contrôle
  MR6 par partie affiché dans l'atelier (route `…/mer`) ; restructuration à
  l'import des Mnn importées en une partie (I-MR7 : mêmes objectifs, rien de
  supprimé) ; arbre du niveau : code Mnn/Xnn au lieu de « S201 » ; lots
  M01 à M07 au format v2 ; module `seqenseigne-style6e` v0.10. Cycle 4 et
  principal 6e inchangés au caractère près. Détails :
  `doc/redemarrage_v0_53_1.md`.
- v0.53.2 livrée (25 octobre) : π brut (critère F de M04-22) qui cassait le
  plan de M04 partie 3 — échappement LaTeX commun `services/latex_texte.py`
  (E1 : caractères inconnus de pdfLaTeX → `\ensuremath{…}`, sur tout le corps
  des documents 6e et dans les échappements du cycle 4 ; `& % # _` dans le
  plan et le dossier des Mnn) ; **dossier enseignant** par partie (plan,
  fiche complète, corrigés des exercices de séance, tests courts corrigés A
  et B, activités complémentaires) ; **activités complémentaires** (série AC)
  dans les Mnn (clé de lot `activites_complementaires`, `objectif`), hors
  contrôle MR6, document `activite` ; bonus de test court ≠ 1 : anomalie ;
  référentiel du 25 octobre (S10-02 F, dépendances M03-12 → M04-12,
  M05-12 → S06-03). Module LaTeX inchangé. Cycle 4 et principal 6e inchangés
  au caractère près. Détails : `doc/redemarrage_v0_53_2.md`.
- À venir : tuile « Matériel à réserver » du tableau de bord de classe (avec
  les progressions) ; publication d'une mise en
  route comme référentiel « mer » (côté classe, une partie Mnn = un bloc de
  séances placé librement) ; migration du référentiel de 5e
  (doublons) ; dépendances entre objectifs dans l'appli ; outil d'import
  paramétré par niveau. La mise en ligne (prévue en v0.52) prendra le
  numéro suivant.

## Comment reprendre (pour l'assistant)

1. Lire ce fichier + le dernier `doc/redemarrage_v0_*.md`.
2. Le code de l'appli est sous `appli/` dans le zip (racine = `appli/app.py`).
3. Les zips envoyés N'INCLUENT PAS : cache de compilation d'atomes, images, la
   plupart des dossiers de référentiels (dont les PDF figés). Ces éléments
   existent chez l'utilisateur — ne pas conclure « absent » depuis le zip.
4. Protocole : reconstruire, auditer, cadrer, coder, tester (pytest + vitest),
   livrer un ZIP delta + MANIFEST md5. Jamais de .db dans une livraison.
5. Le dépôt GitHub (lolocosto/seqenseigne) contient `appli/` à la racine ; il
   est à jour à chaque livraison poussée : partir d'un `git pull`.

## Chantier en cours : séparation en deux outils (v0.51)

Cadrage : `doc/redemarrage_v0_51_0.md`. Appli locale « atelier » (conception,
LaTeX) et appli en ligne « classe » (suivi, sans LaTeX), sur un seul code.
- v0.51.0 livrée : profils `complet` (défaut) / `atelier` / `classe`
  (`services/profils.py`, `lancer.bat atelier|classe`).
- v0.51.1 livrée : format d'échange JSON des référentiels
  (`doc/format_referentiel.md`, `schemas/referentiel-1.json`, export et
  vérification dans Conception › Référentiel).
- v0.51.2 livrée : paquet de publication (`doc/format_paquet.md`), tuile
  « Publication » du tableau de bord atelier ; durée d'une partie = somme des
  objectifs ; corrections après le premier export réel.
- v0.51.3 livrée : import des paquets dans le profil classe (Système ›
  Administration › Import référentiels) ; base séparée d'essai
  (`lancer.bat classe --base-classe`).
- v0.51.4 livrée : atelier des référentiels externes et MER — codes de
  séquence recalculés tant que le référentiel est en conception, documents
  déplaçables (sauf distribués), durée de partie calculée en lecture seule.
- v0.51.5 livrée : thèmes dans l'éditeur des référentiels externes et MER
  (séquences regroupées par thème ; thèmes publiés dans le JSON).
- v0.51.6 livrée : création d'un référentiel externe à partir d'une
  structure modèle (programme du cycle, référentiels du même type), aperçu
  dépliable ; contenu identique à un autre référentiel signalé.
- v0.51.7 livrée : protocole d'échange appliqué aux paquets (identité des
  instances, paquets numérotés, réception dans l'ordre, archive et renvoi).
- v0.51.8 livrée : retour d'usage (tuile de l'appli en ligne, import dans la
  tuile Publication de l'atelier), acquittements dans les deux sens, états
  de synchronisation ; verrous de l'atelier = base locale + retours.
- v0.51.9 livrée : boîte aux lettres (dossiers d'entrée et de sortie,
  relève au démarrage et périodique, confirmation / automatique).
- v0.51.10 livrée : réglages des échanges dans les Préférences, boîte aux
  lettres seule côté atelier, base partagée signalée.
- v0.51.11 livrée : retrait de l'ancien modèle de MER et des anciens livrets
  (sauvegarde JSON dans `data\sauvegardes\`) ; onglet « Import retours
  d'usage » (atelier).
- v0.51.12 livrée : bascule de la base partagée vers `data_atelier\` et
  `data_classe\` (Système › Administration › Bascule, profil complet ;
  `data\` intact) ; rôle de chaque base, tables de l'autre côté retirées au
  démarrage ; chaque profil ouvre son dossier.
- v0.51.13 livrée : résidus `items_texte` et `objectifs_v2` retirés ;
  écran Système › Administration › Échanges ; tuiles Publication et Retour
  d'usage résumées ; tuiles Journée, Classes, Établissements (classe).
- v0.51.14 livrée : résumé de chaque séance (MER, principale, documents) dans
  la planification hebdo et la tuile Journée ; tuile Journée → Suivi.
- v0.51.15 livrée : ordre des créneaux = position dans la journée (une
  indisponibilité « de M4 à M5 » ne raye plus l'après-midi).
- v0.51.16 livrée : échange automatique par API (l'atelier appelle l'appli
  de classe avec un jeton à expiration ; `doc/api_boite.md`).
- v0.51.17 livrée : livret de séquence — objectifs en page 1, une boîte
  par partie (titrée « 1re partie »…), même sans critères ; prérequis sous
  « Révisions » via le crochet paquet `\seqContenuAvantSerie`
  (`doc/redemarrage_v0_51_17.md` ; exige `seqenseigne-theme` et
  `seqenseigne-core-exos` à jour).
- v0.51.17.1 livrée : correctif — `\seqContenuAvantSerie` recopiée dans le
  préambule du livret (liste `FRAGMENT_SQUELETTE_LIVRET`, test
  `TestSqueletteLivret` avec paquet indexé simulé).
- v0.51.18 livrée : livret de séquence, exercices dans l'ordre des
  objectifs (plus de tri par identifiant) ; plan de travail aux numéros du
  livret — numérotation commune `services/numerotation_livret.py`.
- v0.51.19 livrée : fiches de résumé — zone d'exemple de N lignes sous
  chaque zone de texte (fiche sur plusieurs pages), zone « Exemples » de
  fin de page optionnelle (cochée par défaut).
- À venir : mise en ligne (authentification, HTTPS, VPS ; transport des
  envois : dossier synchronisé ou API réduite à la boîte aux lettres) —
  après le chantier 6e (v0.52).

## Chantier précédent : documents imprimables sans LaTeX (v0.50, terminé)

Hors ateliers, plus de LaTeX : pages HTML + CSS d'impression, imprimées ou
enregistrées en PDF par le navigateur (cadrage : `doc/redemarrage_v0_50_0.md`).
- v0.50.0 livrée : planning des automatismes, planning MER d'une classe,
  aperçu théorique MER (`templates/impression/`, `static/impression.css`,
  routes `/impression/...`) ; anciens PDF LaTeX en lien « ancien PDF ».
  Rendu validé par l'auteur sous Firefox.
- v0.50.1 livrée : plans de classe en HTML + SVG (une page A4 par plan,
  `/impression/plans-classe`). Rendu validé par l'auteur.
- v0.50.2 livrée : générateurs LaTeX hors ateliers et routes `.pdf`
  retirés ; LaTeX ne sert plus qu'aux ateliers de conception.

## Chantier précédent : suivi en séance

Découpage validé dans `doc/ROADMAP.md` (section « Suivi en séance »).
- v0.42.0 livrée : navigation (Paramétrage, Système ; Suivi › Début de
  séance, Observation, Compétences). v0.42.1 : sélecteurs (Suivi : Année,
  Établissement, Niveau, Classe partagée ; Observables : Niveau).
- v0.43.0 livrée : Début de séance (séance en cours / prochaine /
  dernière, mise en route affichée, absents sur le plan ou la liste) ;
  v0.43.1 : séances du jour (toutes classes) toujours affichées ;
  v0.43.2 : début effectif des mises en route, case « MER non faite ».
- v0.44.0 livrée : documents du début de séance (prévus et ajoutés à la
  volée, report, distribution, rattrapage des absents).
- v0.45.0 livrée : observables par niveau (communs / individuels, périodes,
  exceptions masquer / attribuer avec commentaire, copie, aperçu).
- v0.46.0 livrée : observation en séance (même séance que le début de
  séance, plan, liste effective de l'élève, occurrences, compteurs).
- v0.47.0 livrée : Suivi › Travail (à faire / à rendre, échéance
  individualisée depuis la remise, à rattraper, documents à rapporter,
  clôture, retards de la classe) ; v0.47.1 : synthèse pour le cahier de
  textes Pronote ; v0.47.2 : délai « prochaine séance / x jours / x semaines » ;
  v0.47.3–v0.47.4 : liste des classes refiltrée (Progression de MER, Mises en
  route + sélecteur Niveau, établissement affiché).
- v0.48.0 livrée : retour (à faire / à rendre) et délai (dont « fin du
  créneau ») sur les documents associés à la progression principale ;
  conversion en travail à la distribution.
- v0.48.1 livrée : livret de fiches de résumé par séquence (option
  « Découpage »).
- v0.48.2 livrée : référentiel principal externe = référentiel figé de
  source externe (nom calculé, objectifs auto-numérotés, fichiers tous
  formats, utilisable dès sa création, séquence commencée verrouillée).
- v0.48.3 livrée : types des documents attachés (liste extensible dans
  Système › Préférences), un fichier par ligne avec son type.
- v0.48.4 livrée : nom calculé et type principal / MER pour tous les
  référentiels ; écran externe en liste / détail.
- v0.48.5 livrée : fichiers de partie externes portant séance / retour /
  délai, placement automatique (remplacé par une association manuelle) ;
  documents de MER typés.
- v0.48.6 livrée : présentation commune des référentiels externes (modèle
  MER), documents un par ligne, objectifs typés (connaissance en tête,
  capacités), critères repliés.
- Unification des référentiels (plan validé : B, v0.49.1, C, D).
  v0.49.0 livrée (B) : MER externes dans la structure figée (même éditeur
  que les principaux, codes M01…, libellé de partie, documents annuels,
  alerte « au moins une capacité par partie »), Progression de MER sur la
  source `fige` ; ancien modèle de MER en retrait.
- v0.49.1 livrée : documents de MER (séance, retour, délai dont « fin de
  la partie », placement automatique, panneau « documents » d'une partie
  dans la Progression de MER).
- v0.49.2 livrée (C) : onglet unique « Référentiel » dans Conception ›
  Niveau (internes et externes, principaux et MER ; filtres année / type /
  source avec groupage ; création par source et type).
- Prochaines étapes : D — découpage progressif du détail interne en blocs
  communs ; retrait de l'ancien modèle de MER après recréation par l'auteur.

## Derniers chantiers terminés

- **Plans de classe (v0.37 → v0.40)** — cadrage : `doc/cadrage_plans_de_classe.md`.
  Salles et éditeur libre de plan (v0.37), EdT versionné avec salle et AESH
  (v0.38), plans de classe hebdomadaires (v0.39), sexe des élèves, aléatoire
  mixte, places AESH (v0.40). Suites notées dans `doc/ROADMAP.md`.
- **Revue des dettes techniques (v0.41.0 → v0.41.3)** : suite de tests au vert
  et pdf.js versionné (v0.41.0) ; préparation de la projection unique (v0.41.1) ;
  semaine vue par la projection, report MER, sélecteur d'établissement, fusion
  encadrée (v0.41.2) ; nettoyage (v0.41.3).

## Chantier précédent : planification de la distribution de documents

- Modèle + service + route : `progression_doc` (v0.32.5).
- Affichage dans la Planification hebdo : détail de séance → docs prévus (v0.32.6/8).
- Correctif état « verrouillé/utilisé » des référentiels importés (v0.32.7).
- UI de saisie : Suivi → Progression principale → détail du créneau → section
  « Documents à distribuer » (v0.32.8).
- Association posée AU NIVEAU (créneau + rang de séance), pas par classe ; les
  décalages restent gérés par les indisponibilités.
- Sources de docs : référentiel principal interne (dont planches de cartes),
  référentiels externes (principal ET MER). Référentiels MER internes : PAS
  développés (roadmap).

## Prochaines étapes possibles

- Rappels d'impression (todo dérivée, délai 7 j configurable) — cadré, à coder.
- Tuile « Séances de la semaine » cliquable.
- Réorganisation des onglets de 1er niveau : Tableau de bord · Suivi ·
  Planification · Conception · Administration · Configuration (idée à cadrer).
- Suivi « en séance » (observations élèves par pictogrammes, mobile/tablette) —
  gros chantier, cadrage consigné dans reflexion_metier_enseignant_roadmap.md.

## Règles à respecter (acquis de la revue des dettes)

- **Projection** : toute préparation passe par `services/contexte_projection.py`
  (calendrier hors transaction, `projeter_classe`, `seances_de_la_semaine`) ;
  ne jamais recopier la séquence calendrier/EdT/grille/indisponibilités.
- **Palette des niveaux** : source unique = variables `--niv-*` du §20 de
  `app.css` (v0.36.2).
- **Libellés LaTeX des niveaux** : `param_niveaux.LIBELLES_NIVEAUX_LATEX`
  (v0.41.3) ; ne pas recréer de table locale.
- **Outils CLI** qui importent `services`/`persistence` : amorce `sys.path` dans
  le script et lancement par chemin
  (`..\outils\python\python.exe .\outils\x.py`), jamais `python -m` (v0.37.1).
- **Suppressions** : push-to-github.html crée des commits additifs ; tout
  fichier listé dans `MANIFEST_SUPPRESSIONS.md` est aussi à supprimer à la main
  sur GitHub.
- **Tests figés** : `tests/test_v0_41_1_projection_figee.py` ; ne régénérer la
  capture que pour un changement de comportement voulu, et le documenter.
- **Profils** (v0.51) : toute nouvelle route doit avoir une catégorie
  (`services/profils.py` : blueprint ou exception dans `ENDPOINTS`) ; tout
  nouvel élément d'interface propre à un côté porte `data-profils="…"`.
- **Format d'échange** (v0.51.1) : tout changement du format met à jour le
  schéma, la doc et `FORMAT_VERSION` (mineure = champ facultatif ajouté,
  majeure = incompatible) ; textes en ligne via `services/texte_latex.py`.
- **Documents hors ateliers** (v0.50) : HTML + `static/impression.css`
  (gabarits `templates/impression/`, format par `@page`, routes
  `/impression/...`), jamais de LaTeX ;
  tout dessiner en traits et texte (pas de fond, Firefox ne l'imprime pas).
- **Établissements** : création uniquement par sélecteur + « Ajouter un
  collège » (académie dans la liste connue) ; fusion refusée si la source a un
  EdT, des indisponibilités ou une grille personnalisée.
- **Gabarits de documents** (v0.52.1) : tout nouveau type de document
  s'ajoute au catalogue `services/gabarits_documents.py` (et à
  `peremption_atomes`) ; ne jamais renommer une clé de type (chaînes
  `type|cible` enregistrées côté classe).
- **Séries « documents »** (v0.52.2) : EV, TP, AC, AT
  (`services/atomes.SERIES_DOCUMENTS`) ne vont dans aucun livret ; tout
  générateur ou liste qui lit `objectif_exos` ou `exercices.serie_code` lit
  une liste fermée de séries (ou exclut `SERIES_HORS_LIVRET`).
- **Série approche** : code `AE` partout (base, `atomes._SERIE_VERS_CODE`,
  JS) ; `EA` n'est qu'un RÔLE dans `partie_exos_revision_approche`.
  Enregistrer un exercice sans changer sa série ne touche jamais à son code
  ni à son numéro (l'import 6e retrouve un exercice par niveau, séquence,
  code, numéro).
- **Modèle de référentiel** (v0.52.4) : `cycle4` = « Notions et méthodes »,
  `sixieme` = « Fiches de résumé par objectif » ; ne dépend PAS du niveau.
  Ne jamais tester `N09` pour décider d'un rendu ou d'une interface : côté
  serveur `gabarits_documents.gabarit_atelier_du_niveau` (règle R1b :
  référentiel interne principal hors « annulé », le plus récent), côté
  interface `atlModeleFiches(niveau)` (`static/gabarits_atelier.js`). Le
  niveau imprimé vient de `\seqNiveauCourt` / `\seqNiveauExposant`
  (`livret_sequence_6e.macros_niveau`).
- **Rendu 6e** (v0.52.3) : tout rendu de l'atelier pour la 6e suit la règle
  R1 (`gabarit_atelier_du_niveau`, R1b depuis v0.52.4) : livret, évaluations, atomes, plan de
  travail ; les numéros d'exercices et d'activités sont ceux du livret 6e
  (`livret_sequence_6e.numeros_livret`).
- **Archives du cycle 3** (v0.52.0) : codes de séquence `Xnn` et thèmes
  `XA`… = ancien découpage archivé ; ne pas les réutiliser pour du neuf ;
  exclus du modèle « programme du cycle ».
- **Mises en route de 6e** (v0.53.0) : séquences `Mnn` de l'atelier du
  niveau, hors du référentiel principal : tout ce qui énumère les séquences
  du principal passe par `mises_en_route_6e.hors_principal` (Xnn ou Mnn) ;
  pas d'objectif « Cours » dans une Mnn (`est_objectif_cours`) ; série `MR`
  (série « documents », dans aucun livret), numéro = séance ; fiche de cours
  = fiche sans objectif de la séquence. Leitner et cartes du cycle 4 : ne pas
  les mêler aux Mnn. v0.53.1 : une partie par objectif (ref6e\_v2 « — partie
  n »), codes (p − 1) × 10 + 2… ; fiche de cours **par partie** = fiche sans
  objectif attachée (`objectif_fiches`) aux objectifs de sa partie ; partie
  d'un test court = celle de ses objectifs évalués ; ne jamais recréer une
  Mnn pour la restructurer (I-MR7 garde les identifiants). v0.53.2 : série AC
  dans une Mnn (partie = celle de son objectif, hors MR6, hors catalogue du
  principal) ; dossier enseignant (`corps_dossier`).
- **Texte venu de la base dans un document** (v0.53.2, E1) : toujours par
  `services/latex_texte.py` (`texte_latex` pour du texte simple,
  `unicode_latex` quand le LaTeX volontaire doit passer) ; jamais de
  `\newunicodechar` dans le préambule commun (le `.tex` du cycle 4 et du
  principal changerait).

## Dettes restantes (mineures)

- Installation neuve : `param_niveaux` amorce la table `cycles` avant
  l'auto-import des cycles, qui croit alors C03/C04 déjà importés (thèmes et
  séquences du cycle restent vides ; repli CSV dans les modèles). Constaté
  en v0.52.0, sans effet sur une base existante ; non corrigé.
- v0.52.1 : `v2_lecture` joint `sequences_du_cycle` sur le seul code : depuis
  v0.52.0 (S01…S10 en C03 et C04), le livret du cycle 4 d'un niveau N09 prend
  le nom de la séquence du cycle 4 (le livret 6e lit le cycle du niveau).
  Non corrigé pour ne rien changer au cycle 4.
- v0.52.0 : les précédences du cycle 4 vers N09/Snn (anciens codes) ne sont
  pas modifiées par l'import ; l'outil les liste, à revoir dans l'atelier.
- v0.52.2 : les liens objectif ↔ EV/TP/AC/AT ne se voient pas dans
  l'assemblage (posés par l'import, ou par l'API `objectif_exos`) ;
  évaluation de l'import repérée par son titre (la renommer puis relancer
  l'import en créerait une seconde).
- Antérieur (constaté en v0.52.2) : l'aperçu d'un exercice **sans corrigé**
  dans l'atelier d'exercices s'arrête sur « Corriges/cNeM.tex not found ».
  Réglé pour la 6e en v0.52.3 (rendu 6e) ; reste vrai au cycle 4.
- v0.52.3 : notions, méthodes et fiches de 6e gardent le rendu d'atome du
  cycle 4 ; plan de travail 6e sans référence du manuel, pages du livret ni
  déroulé des activités (aucune donnée en base).

- `services/tableau_bord.py` (`_NIVEAU_LABEL`) et
  `services/latex_rendu_atome.py` ont encore leurs propres libellés de niveaux
  (formes différentes : « 4ème », « 4e », « Quatrième ») ; à rapprocher de
  `param_niveaux` à l'occasion.
- `tests/test_paquet_parseur.py::TestIntegration` (5) : cherche le paquet dans
  `../reference/paquet` ; ignoré sur un clone GitHub (seul `appli/` y est).

## Points d'attention récurrents

- Bien vérifier le zip reçu : plusieurs fois une version obsolète a été envoyée
  (vérifier la présence des derniers `doc/redemarrage_*.md`).
- Après chaque str_replace, vérifier le code de sortie ET l'absence de message
  d'erreur (des coquilles JS/py ont été introduites puis corrigées).
