# Redémarrage v0.52.1 — Gabarit de documents par référentiel, livret 6e

## Besoin

Cadrage validé le 19 octobre (« Cadrage — documents et mise en forme par
référentiel ») : chaque référentiel porte un **gabarit de documents** qui fixe
la liste des documents qu'il publie et leur mise en forme. `cycle4` = les 9
documents historiques, inchangés ; `sixieme` = documents au style de l'équipe
de 6e : livret de séquence, fiches de cours, corrigés enseignant. Les séries
TP, AC, AT, EV, les évaluations au rendu 6e et le sujet B en remédiation
viendront en v0.52.2.

## Décisions

- **G1** Colonne `referentiel_niveaux.gabarit_documents` (`cycle4` |
  `sixieme`, défaut `cycle4` pour tous les référentiels existants, dont
  N11_v2025). À la création (interne ou externe), liste « Documents : … »
  préremplie selon le niveau : N09 → `sixieme`, N10 à N12 → `cycle4` ; sans
  valeur envoyée, le serveur applique la même règle.
- **G2** Modifiable tant que le référentiel est « en_cours » (sélecteur en
  tête de « Documents à publier », route `PUT /api/referentiels/<id>/gabarit-documents`,
  409 sinon) ; figé ensuite.
- **G3** Catalogue `services/gabarits_documents.py` : par gabarit, types
  ordonnés, libellé, options par défaut, valeurs permises, générateur. Les 9
  clés du cycle 4 ne sont pas renommées. Clés 6e : `livret_sequence_6e`,
  `fiches_cours_6e`, `corriges_6e`.
- **G4** La contrainte CHECK des 9 types sur `referentiel_documents` est
  levée par **une** reconstruction (détectée par la présence de la
  contrainte), après sauvegarde JSON `data\sauvegardes\retrait_contrainte_referentiel_documents_*.json` ;
  la validation des options se fait en Python d'après le catalogue.
- **G5** Changer de gabarit ne supprime rien : les lignes de l'autre gabarit
  restent en base (options gardées), ni listées, ni compilées (refus
  `hors_gabarit`), ni proposées. La case « actif » reste l'exclusion par type.
- **C1** La compilation passe `referentiel_id` et `gabarit` au producteur
  (copie de la cible) ; les producteurs du cycle 4 les ignorent.
- **L1** Activités d'introduction : l'import 6e (v0.52.0, D6) les rattache
  à la **partie** ; le livret les place en tête de partie, avant le premier
  objectif. Une activité rattachée dans l'atelier à un objectif
  (`objectif_exos`, série AE) s'affiche sous son bandeau, comme dans
  l'aperçu validé. Le lien activité → objectif n'est que dans le journal
  d'import (pas en base).
- **L2** Fiche d'un objectif = `fiches_resume.objectif_id` ; une fiche du
  « Cours » sans objectif de la partie s'affiche en tête de partie.
- **L3** Objectif « Cours » (`01`, `11`, `21`…) : ni bandeau ni ligne de
  couverture. **L4** Un exercice lié à plusieurs objectifs n'est émis qu'une fois.
- **L5** Une seule géométrie : celle que `seqenseigne-theme` pose pour les
  documents de l'équipe (`left=35pt,right=35pt,top=50pt,bottom=70pt,head=30pt,foot=10pt`),
  passée à `construire_preambule(…, marges=…)` à la place de son
  `\newgeometry` ; aucun second `\geometry`. Sans `marges`, rien ne change.
- **L6** Titre : nom de la séquence **dans le cycle du niveau**
  (`param_niveaux`) ; « Partie n » sans libellé (pas de libellé de partie
  dans l'atelier interne). **L7** Séquences d'archive `Xnn` jamais générées.
- **R1** Route de l'atelier (`/api/v2/livret-sequence/…`) : gabarit =
  paramètre `gabarit` s'il est donné, sinon celui du référentiel interne
  principal « en cours » le plus récent du niveau, sinon celui du niveau
  (N09 → livret 6e). `?version=corrigee` pour le corrigé.
- **F1** Format d'échange 1.1 : `referentiel.gabarit_documents` facultatif ;
  un fichier 1.0 sans le champ est lu `cycle4` ; stocké à l'import (classe).
- **P1** Côté classe (`progression_doc`) : référentiel **de la progression**
  (`prog_ref`), documents **actifs** et **du gabarit** seulement. Sans
  progression (appels historiques) : le plus récent du niveau, comme avant.
- **P2 (prudence)** Un référentiel verrouillé / utilisé propose ses documents
  comme avant, sans filtre « actif » : N11_v2025 a été importé avec toutes
  ses cases « actif » décochées (PDF figés, v0.32.7) ; le filtre l'aurait vidé.

## Code

Nouveaux : `services/gabarits_documents.py`, `services/livret_sequence_6e.py`,
`tests/test_v0_52_1_gabarits_documents.py` (+ `tests/donnees_v0_52_1/`, .tex
de référence produits par c412a70), `tests_js/gabarit_documents.test.js`.
Modifiés : `services/referentiel_documents.py`, `referentiel_documents_compilation.py`,
`orchestrateur_compilation.py`, `preambule_atome.py`, `peremption_atomes.py`,
`progression_doc.py`, `format_referentiel.py`, `import_publication.py`,
`referentiels.py`, `profils.py` ; `persistence/schema.sql`, `sqlite_store.py` ;
routes `livret_sequence`, `referentiels`, `referentiel_principal_externe`,
`referentiel_documents`, `progression_doc` ; `schemas/referentiel-1.json` ;
`static/atelier_referentiel.js`, `referentiel_unifie.js`, `progression_doc.js` ;
`templates/index.html` ; `doc/format_referentiel.md`.

## Vérifications

- Cycle 4 : 128 .tex (tous les documents des référentiels N10–N12 de la base
  atelier de démonstration) identiques au caractère près entre c412a70 et
  v0.52.1 ; test permanent sur livret de séquence, livret de fiches, évaluation.
- Livrets N09 S01, S02, S03 (élève 33/21/38 p., corrigé 36/23/40 p.) et
  fiches de cours S01 (3 p.) compilés sans erreur ; marges identiques aux
  aperçus du lot S01.

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`).
2. Lancer l'appli : la migration tourne au démarrage (colonne, puis
   reconstruction unique de `referentiel_documents`, sauvegarde JSON).
3. Conception › Référentiel : créer le référentiel interne 6e (« Documents :
   6e »), cocher les documents 6e, Tester.
