# Redémarrage v0.59.0 — version 1 « 4e au modèle Fiches » (avant le premier lot de 4e)

> Base de comparaison : 79fb6eb « v0.58.2 » (déployée et poussée, migration complète chez
> Laurent). Besoins : `col4/besoins_appli_fiches_4e.md`, « Version 1 » (E1 à E5), avec les
> décisions de Laurent du 16 novembre 2026 (`col4/DECISIONS_CYCLE4.md`, point 10) :
> réponses par défaut des 20 points de l'inventaire de l'étape 3 acceptées, **sauf les
> cartes d'automatisme**, rattachées aux objectifs et absentes du livret de séquence.
> Paquet LaTeX inchangé.

## Ce qui change pour Laurent

1. **Archiver la structure de 2025 de la 4e** (nouvel outil, une fois) : les séquences
   A1…E1 de l'atelier N11 (et A2) deviennent les archives X01…X15, avec leurs parties,
   objectifs, liens et contenus. Rien n'est supprimé, tout est réversible.
2. **Importer les lots de 4e** avec l'outil des lots de 6e : `--niveau N11`. L'import
   **refuse** de s'appliquer tant que l'archivage n'est pas fait (message et commande).
3. **Créer le référentiel « 4e — 2027-2028 — Principal »** dans l'onglet Référentiel :
   liste « Année » (année en cours ou suivante), modèle « Fiches de résumé par objectif »,
   case « Cartes d'automatisme rattachées aux objectifs ».
4. Les cartes d'automatisme des lots sont rattachées à leur objectif ; elles **n'entrent
   pas** dans le livret de séquence. Le document de rituels (cartes nouvelles, cartes à
   revoir, selon la progression) est pour la v0.60.

## Décisions

- **D1 — Archivage** (`outils/archiver_structure_niveau.py`, évolution E3, point 15).
  Pour le niveau demandé (N11 ; N10 et N12 plus tard avec le même outil) : chaque
  séquence-niveau vivante en code de thème devient l'archive « X + numéro de l'ancien
  code » de `outils/correspondance_codes_2027.json` : A1→X03, A2→X15, A3→X01, A4→X05,
  B1→X11, B2→X12, B3→X13, C1→X06, C2→X07, D1→X09, D2→X08, E1→X14. La séquence du cycle
  d'archive est créée si elle manque (numéro 100 + n, nom du cycle suivi de
  « (archive) », thème de la séquence vivante, comme X02/X04/X10) ; elle sert aux trois
  niveaux. Séquence-niveau, parties, objectifs, liens objectif ↔ atome, cartes mentales,
  atomes du niveau (notions, méthodes, exercices, fiches, cartes) passent sous l'archive ;
  **identifiants inchangés**, colonne `fichier` inchangée (les `.tex` ne sont pas
  renommés ; un nouveau scan ne recrée rien : le scanner n'ajoute que les fichiers absents
  de la base). Les précédences et `origin_seq` qui visent N11/<code> visent l'archive (la
  3e de cette année pointe ainsi toujours la 4e de 2025). Marque : table
  `archivages_structure`. Vérifié avant validation : empreinte de toutes les autres tables
  (instantanés `referentiel_*` de N11_v2025 « utilisé » et 2025_N11b « verrouillé »…) et
  des fichiers `referentiels\` (`_verrouille\`, `_publication\`) ; dans les tables
  touchées, seules les lignes du journal changent. Essai à blanc par défaut, `--apply`
  (sauvegarde, journal), `--annuler` (refusé si un lot a été importé depuis : restaurer
  alors la sauvegarde), idempotent (« rien à faire »).
- **D2 — Import des lots ouvert à N11** (`outils/import_lot6e.py --niveau N11`, E1).
  Référentiel `outils/objectifs_4e.json`, transcription de `outils/ref4e_v1.md` (copie de
  `col4/ref4e_v1.md` : 12 séquences, 16 parties, 54 objectifs, titres courts ; objectif
  « Cours » et critère E comme en 6e). Dossier des lots par défaut :
  `..\reference\lot4e\A1\A1.json`… Hors 6e : ni archivage du cycle 3, ni écriture dans les
  thèmes et séquences du cycle 4 (ceux de la base font foi ; séquence absente : lot non
  importé), ni mises en route (un lot Mnn est ignoré, signalé). Le libellé de chaque
  partie va dans `sequence_parties.libelle`, le titre court de la séquence dans
  `sequences_par_niveau.titre_court`. Même module de mise en forme (`seqenseigne-style6e`,
  niveau « 4e », couleur du thème A à E), mêmes séries EN, AP, EX, mêmes contrôles
  (macros, figures, doublons). La 6e est inchangée (`--niveau N09` par défaut) : les
  globaux de l'outil sont posés le temps de l'exécution et rendus.
- **D3 — Cartes d'automatisme dans les lots** (E2, décision du 16 novembre). Clé
  `cartes_automatisme` de chaque objectif d'un lot :
  ```json
  "cartes_automatisme": [
    {"num": 1, "titre": "Signe d'un produit de relatifs", "type_pedago": "procedure",
     "type_tech": "fixe", "recto": "…", "verso": "…", "variables": "",
     "niveau_creation": "N11", "origine": "N11/A1/CA8 (recopiée)"}]
  ```
  Carte repérée par (niveau, séquence, num), créée « en cours », mise à jour si elle a
  changé (jamais une carte validée : signalé), rattachée à l'objectif (`objectif_cartes`,
  en tête, les liens de l'auteur restent). `niveau_creation` (nouvelle colonne
  `cartes_automatisme.niveau_creation`) : N11 = carte de 4e, N10 = automatisme de 5e écrit
  en 4e avant le référentiel de 5e (point 5) ; la partie se déduit de l'objectif. Ce sont
  les données dont le document de rituels de la v0.60 aura besoin. Contrôles : types
  connus (sinon carte refusée), recto/verso non vides et variables d'une carte paramétrée
  (signalés : la carte ne pourrait pas être validée). **Pas de liste dans le livret** et
  pas de document de cartes au catalogue Fiches en v0.59 (les planches par partie vont
  avec les rituels, v0.60).
- **D4 — Référentiel interne de 4e** (E4, E5, points 17 et 18). Année scolaire choisie à
  la création (`creer_coquille(..., annee=)`, route `annee`, liste du formulaire : en
  cours et suivante ; autre année refusée) : « 4e — 2027-2028 — Principal », id `2027_N11`,
  sans concurrence avec un principal 2026. Option « cartes d'automatisme » du modèle
  Fiches (colonne `referentiel_niveaux.cartes_automatisme`, posée à la création, refusée
  au modèle « Notions et méthodes ») : la validation compte alors les cartes **rattachées
  à un objectif du périmètre** (ni les archives, ni les cartes sans objectif) ; l'aperçu
  « Avant de créer » les annonce ; badge « + cartes » dans la liste. Le référentiel 2027
  devient celui de l'atelier N11 (règle R1b) : l'atelier de 4e passe au rendu Fiches.
- **D5 — Titre court** (point 19) : `sequences_par_niveau.titre_court`, écrit par
  l'import, utilisé par tous les documents Fiches (couverture, en-tête, fiches de cours,
  plan de travail) ; repli sur le nom du cycle (6e : rien ne change). Pas de saisie dans
  l'atelier en v0.59 : le lot fait foi.
- **D6 — Libellés des parties** : hors 6e, le livret Fiches lit `sequence_parties.libelle`
  (la 6e garde `objectifs_6e.json`).
- **D7 — Reporté à la v0.60 (version 2)** : tests courts au principal (E6, point 9 : un
  test court par partie, accepté), durée et séance d'évaluation (E7), séances d'évaluation
  dans la progression (E8), cartes dans le plan de travail et document de rituels (E9 et
  décision du 16 novembre).
- **Gardes (point 16)** : un référentiel interne d'une année antérieure ou égale à celle
  de l'archivage (2025_N11b) ne se déverrouille plus (son instantané serait recalculé sur
  la nouvelle structure) ; les documents d'un référentiel figé d'un niveau archivé ne se
  recompilent plus (ses PDF figés font foi ; une recompilation partirait des archives).
- **Correctif lié** : le livret de cours (modèle « Notions et méthodes ») de 5e et de 3e
  listait toutes les séquences du cycle, archives comprises ; il ne liste plus que les
  archives que le niveau possède (X02, X04, X10 restent ; X01…X15 de la 4e n'y entrent pas).

## Marche à suivre (Windows, depuis `appli\`, appli arrêtée)

```
..\outils\python\python.exe .\outils\archiver_structure_niveau.py --niveau N11
..\outils\python\python.exe .\outils\archiver_structure_niveau.py --niveau N11 --apply
..\outils\python\python.exe .\outils\archiver_structure_niveau.py --niveau N11
..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11
..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11 --apply
..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11 --apply
```

1. **Essai à blanc de l'archivage** : la liste « N11/A1 → N11/X03 »… (12 séquences dans la
   base du 16 novembre, environ 530 écritures), « Jamais touché » et « Anomalies : aucune ».
2. **`--apply`** (confirmation « o ») : sauvegarde `sauvegardes\avant_archivage_N11_*.db`,
   journal `sauvegardes\journal_archivage_N11_*.json`. Retour arrière (avant tout import) :
   même commande avec `--annuler`.
3. **Relance** : « déjà archivée … rien à faire ».
4. **Lots** : déposer `A1\A1.json`… dans `..\reference\lot4e\` (ou `--lots DOSSIER`).
   Essai à blanc : « Structure de 2025 de N11 : archivée le … », séquences du cycle lues,
   puis le détail par séquence, cartes comprises. Sans archivage : « Import refusé :
   structure de 2025 de N11 non archivée… » (code 2, rien n'est écrit).
5. **`--apply`**, puis une seconde fois : la seconde ne change rien (tout « inchangé »).
6. **Référentiel** : onglet Référentiel, niveau 4e, « Interne », « Référentiel principal »,
   modèle « Fiches de résumé par objectif », case « Cartes d'automatisme rattachées aux
   objectifs », Année « 2027-2028 », « + Créer », vérifier l'aperçu, « Confirmer la
   création ».

Le lot d'essai `tests\donnees\lot4e_essai\A1\A1.json` sert aux tests et aux aperçus : ne
pas l'importer dans l'atelier réel (sinon `--db` sur une copie).

## Fichiers

Nouveaux : `outils/archiver_structure_niveau.py`, `services/fiches_cycle4.py`,
`outils/objectifs_4e.json`, `outils/ref4e_v1.md`, `tests/test_v0_59_0_ref4e_fiches.py`,
`tests/donnees/lot4e_essai/A1/A1.json`, `tests_js/referentiel_4e_v0_59_0.test.js`,
`doc/redemarrage_v0_59_0.md`. Modifiés : `outils/import_lot6e.py`,
`persistence/sqlite_store.py` (migration de démarrage), `services/referentiels.py`,
`services/referentiel_validation.py`, `services/referentiels_internes.py`,
`services/livret_sequence_6e.py`, `services/livret_recap_cours.py`,
`services/repartition.py` (table `archivages_structure` côté atelier),
`routes/referentiels.py`, `routes/referentiel_documents_compilation.py`,
`static/referentiel_unifie.js`, `templates/index.html`, `doc/ETAT_COURANT.md`,
`doc/ROADMAP.md`, `paquet/CHANGELOG.md` (note : paquet inchangé). Aucun fichier supprimé.

Schéma (migration idempotente au démarrage, valeurs neutres) : colonnes
`referentiel_niveaux.cartes_automatisme` (0), `cartes_automatisme.niveau_creation` (''),
`sequences_par_niveau.titre_court` (''), table `archivages_structure` (vide).

## Contrôles

Voir `ETAT_COURANT.md` (chiffres de la livraison) et le journal de travail. Résumé : base de
test = copie migrée du 16 novembre rejouée avec l'outil v0.58.2 (A2 créées) ; archivage :
essai à blanc, `--apply`, relance, `--annuler` → base identique (53 tables) ; import du
lot d'essai : refus sans archivage, puis `--apply`, second passage nul ; compilation
pdflatex (2 passes) du livret, du corrigé, des fiches de cours et du plan de travail de
la 4e d'essai ; banc « mêmes sorties » (3 844 sorties) : code v0.58.2 = code v0.59.0 sur la
base non archivée ; après archivage, seules des sorties N11 changent (codes A1 → X03… des
atomes et des documents régénérés depuis l'atelier), documents de 6e, exports et
instantanés des référentiels figés identiques.

## Risques

- **Recompiler ou déverrouiller un référentiel figé de 4e** : refusé (gardes) ; les PDF
  figés et les instantanés restent la référence côté classe.
- **Ordre** : importer avant d'archiver est impossible (refus) ; annuler l'archivage après
  un import est refusé (restaurer la sauvegarde `avant_archivage_N11_*.db` si besoin).
- **Contenus repris** : copiés dans les lots (clé `origine`), les originaux restent en
  archive ; une carte reprise est recopiée dans la séquence de son objectif.
- **5e et 3e** : leur structure de 2025 n'est pas archivée (même outil plus tard,
  `--niveau N10`, `--niveau N12`) ; leurs documents ne changent pas.
- `ref4e_v1.md` contient deux gabarits non remplis (« {nobj} objectifs », « {npar}
  parties ») hors des sections transcrites : sans effet.
