# Redémarrage v0.56.0 — séries Entraînement / Approfondissement / Expertise, mention O / F, page de garde de suivi, fiche insécable, cartes demi-page, séparation des colonnes, corrigés en phrases (6e)

> Version refaite le 13 novembre (Laurent n'avait pas déployé la première : même
> numéro, même base de comparaison 231e401). Décisions de 12 h 12 : SERIES, MENTION,
> page de garde renommée (SUIVI).

## Besoin (Laurent, 13 novembre 2026)

> « Les collègues trouvent la page de garde vide. » — choix : **suivi par objectif**.
> « Le cadre de la fiche de résumé doit être insécable, quitte à perdre le bas de la page.
> Par exemple celui de S01-12. »
> « [Les cartes mentales] on les laisse sur 1/2 page car le rendu est trop étiré. »
> « Quand l'énoncé d'un exercice est sur plusieurs colonnes, mets une séparation, sinon
> c'est très compliqué à suivre. Par exemple S06/A05. »
> « Dans les corrigés, fais des phrases complètes : on se "bat" avec les élèves pour qu'ils
> le fassent alors il faut leur donner l'exemple ! »

Décisions de 12 h 12 :

> 1. Séries renommées (modèle Fiches 6e) : F → « Entraînement », A → « Approfondissement »,
>    E → « Expertise » ; codes affichés EN06 / AP05 / EX02 dans les documents et dans
>    l'interface ; codes internes F / A / E inchangés.
> 2. Mentions dans chaque série : O (obligatoire), R (remédiation), F (facultatif :
>    exercice qui fait travailler la même procédure qu'un R juste avant).
> 3. Page de garde : « Je me suis entraîné », « J'ai approfondi », « Je suis expert »,
>    « Test court … / 10 » ; consigne « Coche une case seulement quand tu as fini toute la
>    série. »

## Audit (état de la v0.55.0)

- Page de garde : `services/livret_sequence_6e.couverture` émet
  `\seqCouvertureLivretSix*{nom}{\seqPartieCouvertureSix{partie}{C/{texte},…}…}` (module
  v0.6) ; appelée seulement par `corps_livret` (livret élève, livret corrigé, corrigés
  enseignant, recueil annuel). Les documents des mises en route (`mises_en_route_6e`) et le
  cycle 4 (`livret_sequence`) ne l'utilisent pas.
- Fiche de résumé : `seqFicheResumeSix` (tcolorbox `breakable`) ; carte mentale étirée à la
  hauteur disponible (CM-TAILLE de la v0.55.0).
- Import des évaluations (`outils/import_lot6e.py`, `import_lot6e_mer.py`) : l'évaluation est
  découpée en atomes EV à partir de son `latex` ; le corrigé rendu est celui du `latex`
  (`\seqReponse`, `\seqACompleter`, `\seqLocSiCorrige`…). Le champ `corrige` d'une évaluation
  (résumé de correction) n'est **pas importé** ; celui des exercices, remédiations, travaux
  personnels, activités complémentaires et séances d'atelier l'est.

## Décisions

- **SUIVI** — Module `seqenseigne-style6e` **v0.14** : `\seqSuiviObjectifsSix{parties}` et
  `\seqPartieSuiviSix{titre de partie}{C/{texte},…}` (même liste que l'ancienne forme).
  Tableau : une ligne par objectif (code à la couleur du thème + intitulé), trois cases à
  cocher « Je découvre », « Je m'entraîne », « Je sais faire », une case « Test court »
  (« … / 10 ») ; en-têtes de colonnes une seule fois en haut ; ligne de titre de chaque partie
  sur fond `seqSixTheme` à 14 % ; en-tête sur fond `seqSixTheme`. Lignes construites dans une
  liste de lexèmes (expl3) puis tableau composé en boîte : s'il dépasse la place restante,
  interligne 2,0 → 1,6 → `\footnotesize` 1,1 → réduction de la boîte : **jamais deux pages**
  (S03 : 10 objectifs, 4 parties, tient à l'interligne 2,0 ; test avec 40 objectifs : une
  page). Aucune dépendance à la version : même page en livret élève et corrigé (cases vides).
  `\seqPartieCouvertureSix` reste dans le module (aperçus et documents déjà produits).
- **SUIVI** (révisée à 12 h 12) — colonnes « Je me suis entraîné », « J'ai approfondi »,
  « Je suis expert » (une par série), « Test court … / 10 » ; consigne en italique sous
  « Objectifs du chapitre » ; légende « O : obligatoire — R : remédiation — F : facultatif »
  sous le tableau (choisie plutôt qu'au début de chaque série : une seule fois, là où l'élève
  coche). Colonnes de 1,85 cm ; trois lignes réservées pour la consigne et la légende dans le
  calcul de la place restante (toujours une page).
- **SERIES** — `services/series_fiches.py` : `CODES_AFFICHES` {F: EN, A: AP, E: EX},
  `TITRES`, `code_affiche`. Documents du modèle Fiches (tous produits par
  `livret_sequence_6e` et `rendu_atome_6e`) : titres de série « Entraînement »,
  « Approfondissement », « Expertise » (`TITRES_SERIES`), code à droite de l'en-tête EN06…
  (livret élève et corrigé, corrigés enseignant, rendu d'un exercice) ; légende du plan de
  travail 6e « entraînement (EN) — approfondissement (AP) — remédiation (R) — expertise
  (EX) » ; message de validation d'une séquence au modèle Fiches « … dans la série
  Approfondissement (AP) ». Interface (`static/gabarits_atelier.js` :
  `atlCodeExercice`, `atlPrefixeSerie`, `atlLibelleSerie`) : atelier Exercice (sections
  « Entraînement (EN) »…, badges, identifiants N09/S06/EN04, boutons de série de l'éditeur et
  de la modale de création), assemblage de séquence (« Série EN — Entraînement », chips
  EN04, « (F) » pour un facultatif), sélecteur d'exercice de révision, résultats de la
  recherche, liste historique de `app.js`. Codes internes inchangés partout ailleurs (base,
  API, lots, format d'échange, empreintes, `data-serie`, glisser-déposer). Cycle 4, AE, EV,
  TP, AC, AT, MR : inchangés. Les critères F / A / E des objectifs (niveaux de maîtrise) ne
  sont pas renommés.
- **MENTION** — colonne `exercices.mention` TEXT NOT NULL DEFAULT 'O' (O ou F ; migration
  idempotente `series_fiches.migrer`, au démarrage, dans `ecrire_exercices` et par l'import).
  Atelier : champ « Mention » (O — obligatoire / F — facultatif) à côté d'Ordinateur et
  Calculatrice, visible au modèle Fiches pour les séries F, A, E (niveau de l'exercice
  ouvert) ; `services/atomes.py` valide (O, F ; refus 400 sinon) ; un enregistrement sans la
  clé garde la valeur (COALESCE). Livret : `\begin{seqExoSix}[O|F]` dans les trois séries à la
  place de O / A / E, `[R]` pour la remédiation (inchangé). Import : clé de lot `"mention":
  "F"` (absente = O) pour les exercices F, A, E, comparée comme le contenu (idempotente),
  jamais appliquée à un exercice validé (anomalie habituelle), valeur inconnue signalée et
  lue O ; essai à blanc : ligne « mentions (séries F, A, E) : obligatoire n, facultatif m » par
  séquence. Format d'échange **1.6** : `partie.facultatifs` = [{objectif, serie, exercice,
  titre}] (codes internes), absent quand tout est O (document, version et empreinte
  inchangés) ; schéma et `doc/format_referentiel.md` à jour. Lots : 24 exercices F validés
  par Laurent (13 novembre, 12 h 41), tous les autres à O.
- **INSECABLE** (Laurent, dans le .dtx) — `seqFicheResumeSix` : `unbreakable`.
- **CM-NATUREL** (Laurent, dans le .dtx) — la carte mentale n'est plus étirée à la hauteur
  de la page (retour sur CM-TAILLE) : taille naturelle, toujours réduite (jamais agrandie) à
  la largeur et à la hauteur disponible.
- **SEP** (Laurent, dans le .dtx) — `\seqSepColonnesSix` : `\hfill` trait gris 0,6 pt
  `\hfill`, à la place du `\hfill` entre deux minipages d'un énoncé (lots). Pour `multicols`,
  `seqenseigne-theme` définit `\columnseprule` comme une **macro** (`\renewcommand`, 0pt) :
  les lots écrivent `\renewcommand{\columnseprule}{0.6pt}` dans un groupe local (multicol lit
  `\columnseprule` comme une dimension, la macro convient) ; le paquet n'est pas modifié
  (cycle 4 inchangé).
- **LISTE** — `services/style6e.py` : `VERSION = "v0.14"`, `MACROS` + `seqSuiviObjectifsSix`,
  `seqPartieSuiviSix`, `seqSepColonnesSix` (sinon l'import signale « macros absentes du
  module » et l'analyse des paquets ne charge pas le module pour un atome).
- **CORRIGES** (lots) — corrigés en phrases complètes et 172 séparations de colonnes
  (`\seqSepColonnesSix`) dans `reference\lot6e\S01…S13`, `M01…M07` ; bloc 2 de la fiche
  S01-03 remplacé par le texte de Laurent. Aucun changement de code d'import : le champ
  `corrige` des évaluations reste ignoré (voir Risques) ; les lots M ont donc aussi écrit les
  phrases des tests dans le `latex`, entre `\seqLocSiCorrige` (version corrigée seulement,
  vérifié sur PDF).
- **CONTROLES** — import sur une copie de la base de test : essai à blanc sans écriture,
  `--apply`, second `--apply` sans aucun changement (contenu de la base comparé) ; 352 atomes
  mis à jour, 1 fiche (S01-03), 24 exercices F (validés par Laurent à 12 h 41 : S01 3, S02 2,
  S03 5, S04 1, S06 2, S07 3, S08 1, S09 3, S11 1, S12 3) lus à l'essai et écrits par
  `--apply`, 3 anomalies (prérequis du cycle 4, déjà présentes). Compilation : 68 documents
  (livrets S01–S13 élève et corrigé, fiches M01–M07, cartes), 0 erreur, aucune fiche de
  résumé de plus d'une page ; (F) affiché pour les 24 (par exemple S03 EN09 « Les baguettes
  du pique-nique »). Même `.tex` : 1590 sorties de la v0.55.0 comparées sur la même base ;
  253 changent, toutes attendues (173 rendus d'exercice 6e : code EN/AP/EX ; 40 livrets et
  20 corrigés 6e : page de garde, titres de série, codes, en-têtes (O) ; 20 plans de travail
  6e : légende) ; cycle 4, mises en route (140) et export de N11_v2025 identiques.

## Appli

- Nouveaux : `services/series_fiches.py`, `tests/test_v0_56_0_suivi_objectifs.py`,
  `tests/test_v0_56_0_series_mention.py`, `tests_js/series_fiches_mention.test.js`,
  `doc/redemarrage_v0_56_0.md`.
- Modifiés : `paquet/seqenseigne-style6e.dtx` / `.sty` (v0.14), `paquet/CHANGELOG.md`,
  `services/style6e.py`, `services/livret_sequence_6e.py`, `services/rendu_atome_6e.py`,
  `services/plan_travail_6e.py`, `services/v2_edition.py`, `services/v2_lecture.py`
  (mention dans l'assemblage), `services/atomes.py`, `services/format_referentiel.py`,
  `persistence/sqlite_store.py`, `outils/import_lot6e.py`, `schemas/referentiel-1.json`,
  `doc/format_referentiel.md`, `doc/ETAT_COURANT.md`, `templates/index.html`,
  `static/gabarits_atelier.js`, `static/atelier_exercice.js`,
  `static/atelier_seqniv_assemblage.js`, `static/ateliers_seqniv_v2_edit.js`, `static/app.js` ;
  tests adaptés : versions du module (6), `test_v0_55_0_cartes_mentales` (version, étirement,
  format 1.5 → constante `FORMAT_VERSION_CARTES`), `test_v0_52_1_gabarits_documents` et
  `test_v0_52_5_objectifs_s05` (page de garde, en-têtes (O)), `test_v0_52_3_retours`
  (codes EN/AP/EX).
- Migration : colonne `exercices.mention` (idempotente). Aucune route, aucune table.
- Même `.tex` : voir « Contrôles » (cycle 4, mises en route, export de N11_v2025 identiques).

## Déploiement (Windows, appli fermée)

1. Sauvegarder `data\seqenseigne.db`.
2. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et `reference\lot6e\…`.
3. Module LaTeX v0.14, depuis la racine : `copy /Y appli\paquet\seqenseigne-style6e.dtx
   reference\paquet\`, puis `cd reference\paquet`, `tex seqenseigne.ins` (répondre `y` aux
   questions d'écrasement) et `cd ..\..`.
4. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py` (essai à blanc :
   « mentions (séries F, A, E) » par séquence, 24 facultatifs en tout ; la colonne `mention` est
   ajoutée par l'import ou au démarrage de l'appli),
   puis `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.
5. Lancer l'appli ; « Rendu PDF » d'un livret 6e : page de garde de suivi, fiches d'un seul
   tenant, cartes à demi-page.

## Risques

- Un exercice, une fiche, une évaluation ou une carte **validé** dans l'atelier n'est jamais
  mis à jour par l'import (anomalie « validé dans l'atelier ») : les corrigés en phrases ne
  l'atteignent pas ; le repasser « en cours » avant l'import.
- Champ `corrige` des évaluations (tests courts S et M) : non importé ; seules les phrases
  écrites dans le `latex` (`\seqReponse`, `\seqLocSiCorrige`…) apparaissent dans le corrigé.
- Une fiche de résumé plus haute qu'une page déborderait en bas de page (insécable) : aucune
  aujourd'hui ; à surveiller quand une fiche s'allonge.
