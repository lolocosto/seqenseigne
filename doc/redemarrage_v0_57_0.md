# Redémarrage v0.57.0 — thèmes et codes A1, livraison 1 : code tolérant, aucune donnée migrée

> Base de comparaison : 0a27337 « v0.56.3 » (déployée). **Aucune migration, aucune
> donnée modifiée, aucune table, aucune route nouvelle.** Un `.dtx` modifié
> (`paquet/seqenseigne-data.dtx`, module data v1.1). Une table de correspondance
> ajoutée (`outils/correspondance_codes_2027.json`), lue par les outils de lots.

## Besoin

Plan de migration des thèmes et des codes (`plan_migration_themes_codes.md`, § 3,
« Livraison 1 »), validé par Laurent le 15 novembre 2026 (22 h 41 : « J'ai verrouillé et
publié le référentiel N11. Tu peux continuer »). Décisions 6 à 9 du cycle 4 : thèmes A à
F communs aux deux cycles, codes de séquences A1 (lettre du thème + rang dans le thème).
Réponses par défaut acceptées : lettre F « Grandeurs et mesures » (cycle 3), D1
Fonctions avant D2 Proportionnalité, Cercles (B2) avant Angles (B3) en 6e, deux
livraisons.

L'appli doit accepter les codes A1 **sans rien changer** tant que les codes sont S… : la
migration des données est la v0.58.0.

## D1 — `services/codes_sequence.py`, source unique

Familles : code de thème `^[A-F][1-9]$`, ancien code `^S\d{2}$`, mise en route
`^M\d{2}$`, archive `^X\d{2}$` (S, M, X réservées). Fonctions : `famille`,
`est_code_sequence` (option `ancien_large` : S + 1 à 3 chiffres, tolérance d'avant des
routes), `chercher_code` (nom de fichier libre : S d'abord, puis un code de thème isolé —
« 5E2 » ne contient pas E2), `libelle_numero` (« Séquence A1 », jamais « Séquence 11 »),
`cle_tri`, table de correspondance (`charger_correspondance`, `convention_codes`). Aucune
base lue ni écrite.

## Les 14 endroits (synthèse du cycle 4, § 5) et deux de plus

| N° | Où | v0.57.0 |
| --- | --- | --- |
| 1, 2 | `routes/livret_sequence.py`, `routes/plans_de_travail.py` | A1…F9 acceptés (D2) |
| 3 | `services/v2_edition.py` (précédences) | A1…F9 acceptés |
| 4 | `scanner_latex.py` (7 expressions) | `N10A1F01.tex`, `N10_A1_Notion_01.tex`, `N10A1_param.tex`, `N10_A1_Livret.tex` reconnus ; S… comme avant |
| 5 | `importer_arborescence.py` | `N10A1Objectifs.csv` reconnu |
| 6 | `services/fiches_import.py` | `\seqSetCodeSequence{A1}` |
| 7 | `outils/verifier_referentiels.py` et sa copie `importers/outils/` | code lu par `chercher_code` (PDF figés `livret_sequence__N10__A1.pdf`) ; créneaux A1 gardés, DC1… toujours écartés ; lancement par chemin |
| 8 | `scripts/peuplement_14_verif_couverture.py` | fichiers A1 |
| 9 | `static/app.js` | listes « séquence » de la compilation par lot et de la recherche **lues en base** (cycles 3 et 4, sans Mnn ni Xnn) ; repli S01…S14 si l'API ne répond pas ; même liste qu'avant pour la base actuelle |
| 10 | `static/atelier_referentiel.js` | code de thème affiché tel quel (A1, pas « S11 ») |
| 11 | `services/livret_sequence.py` | boîte de titre et prérequis : « Séquence A1 — … » (D3) |
| 12 | `paquet/seqenseigne-data.dtx` | D5 |
| 13 | `outils/import_lot6e.py` (et, par lui, `import_lot6e_mer.py`) | D6 |
| 14 | tris par code | D7 |
| 15 | `services/compilation_batch.py` (`sequence_valide`, filtre de la compilation par lot) | A1…F9 acceptés |
| 16 | `services/render_evaluation.py`, `services/plan_travail_6e.py` | « Séquence A1 » (sujets d'évaluation et plans de travail de 6e) |

Laissés tels quels : importeurs historiques (`importers/sequencesdb.py`,
`importers/referentiel_builder.py`, `outils/import_historique_*.py` : anciens dossiers de
classe, toujours en S…) ; `services/referentiel_principal_externe.py` (codes propres aux
référentiels externes). Le scanner réel de l'appli (`importers/scanner_latex.py`)
réutilise `scanner_niveau` de la racine : corrigé par le point 4.

## D5 — Paquet : module `seqenseigne-data` v1.1

Bases d'objectifs par séquence nommées par le **code entier** (`seq@objectifs@S03`,
`seq@objectifs@A1`), créées à la demande (`\seq@basesequence@assure`, `\DTLgnewdb`) et
retenues dans `\seq@var@codesbases` ; borne `\seq@maxsequences` retirée ;
`\seq@seqcode@tonumber` gardée (obsolète). `\changes{v1.1}{2026/11/15}`. Seules les
macros de suivi (`\seqSuiviAnnuelParEleve`, `\seqSuiviAnnuelParSequence`,
`\seqSuiviPeriodiqueParSequence`) passaient par ces bases ; les livrets filtrent par le
code entier et n'étaient pas touchés. Constat : avec A1, l'ancien code ne se contentait
pas de confondre A1 et B1, il produisait des noms `seq@objectifs@s0A1` et des erreurs
datatool. Commandes datatool communes aux versions 2 et 3.

## D6 — Lots de 6e : S… ou A1, toujours aux codes de la base

`outils/correspondance_codes_2027.json` (D8) est lue par `import_lot6e.py` :

- la **convention de la base** est celle des séquences principales du cycle 3 (S…
  avant la migration, A1… après ; Mnn et Xnn ne comptent pas) ; une base qui mêle les
  deux est **refusée** ;
- `objectifs_6e.json` (codes, numéros, thèmes et leur ordre, clés de `parties`), la
  section « Mises en route » de `ref6e_v2.md` (lettre de thème, par code : M03 B ↔ F)
  et **chaque lot** (clés `sequence`, `code`, `objectif`, `objectifs`, `bareme`,
  étiquettes `N pts --- S01-02` des évaluations ; texte libre et `ancien_code`
  intacts) sont ramenés à cette convention ;
- conséquence : après la migration, un lot `S01` est importé en A1 et **aucune séquence
  S01… n'est recréée** ; avant, un lot écrit en A1 est importé en S01 (même résultat que
  le lot S01) ; un lot de code inconnu n'est pas importé (anomalie) ; garde-fou : base en
  codes de thème et référentiel qui garderait des S… → import refusé ;
- dossiers de lots `A1/A1.json` acceptés ; le rapport dit « lot S01 lu en A1 (table de
  correspondance) ».

## D7 — Tris

Aucun tri SQL ne mêle, dans une même liste, un instantané figé (S…) et les tables
vivantes : les `ORDER BY sequence_code` restent tels quels (sorties identiques).
`cle_tri` garantit l'ordre d'avant pour toute liste sans code de thème et range les
codes de thème juste après les anciens codes ; elle sert aux listes de l'interface.

## D8 — Table de correspondance `outils/correspondance_codes_2027.json` (v1)

- Cycle 3 : 13 séquences (S01 → A1 … S13 → E1, numéros 11 à 51), 6 thèmes permutés
  (B → F, C → B, D → C, E → D, F → E ; noms et couleurs inchangés), 7 mises en route
  (codes inchangés, lettre de thème), archives X01 à X16 inchangées.
- Cycle 4 : 12 séquences (S03 → A1, S15 → A2 (nouvelle), S01 → A3, S05 → A4, S11 → B1,
  S12 → B2, S13 → B3, S06 → C1, S07 → C2, S09 → D1, S08 → D2, S14 → E1), archives S02,
  S04, S10 → X02, X04, X10 (102, 104, 110) ; 6 thèmes (A renommé, D → B, B → C renommé,
  D « Proportionnalité, fonctions » créé, E renommé, C → F).

## Contrôles

- pytest : 4892 réussis avant (après installation de `texlive-lang-french` dans le
  conteneur), **4939 réussis, 8 sautés, 0 échec** après (47 tests ajoutés,
  `tests/test_v0_57_0_codes_sequence.py`) ; vitest : 381 → **386** (5 ajoutés,
  `tests_js/codes_sequence_v0_57_0.test.js`).
- **Même `.tex`** : sur une copie de la base d'atelier du 15 novembre (22 h 38), 3 794
  sorties produites avec 0a27337 puis avec v0.57.0 — toutes les cibles des documents des
  référentiels (410), le `.tex` de chaque atome (2 922), livrets et plans de travail du
  cycle 4 par séquence (84), documents de 6e et des mises en route (223), exports au
  format d'échange de chaque référentiel, instantanés `referentiel_*` : **identiques
  octet pour octet** (même empreinte SHA-256). N11_v2025 et 2025_N11b : export et
  instantané identiques.
- **Même PDF** : échantillon N10, N11, N12, N09 (livrets du cycle 4, plan de travail,
  livrets de 6e, test court de mise en route) compilé avec l'ancien et le nouveau
  paquet, dates et graine aléatoire figées : **7 PDF identiques octet pour octet** ; 3
  ne compilent pas dans le conteneur (TeX Live 2023 : `\theHDefinitionNum`,
  tkz-euclide), à l'identique avant et après.
- Aperçus : livrets de test N10/A1 et N10/B1 (chacun ses objectifs, prérequis de B1
  « Séquence A1 — … »), livret N10/S03 inchangé, page de démonstration du module data
  (A1, B1, S03, C1).

## Installation (Windows)

1. Dézipper `seqenseigne_v0_57_0_delta.zip` à la racine (à côté de `appli\`), en
   remplaçant les fichiers.
2. Paquet LaTeX (le `.dtx` change) :
   `copy /Y appli\paquet\seqenseigne-data.dtx reference\paquet\` puis, dans
   `reference\paquet`, `tex seqenseigne.ins`.
3. Aucune migration, aucun outil à lancer.

## Ce qui reste pour la v0.58.0

Outil `outils/migrer_themes_codes_2027.py` (essai à blanc, `--apply`, `--annuler`,
idempotent, une transaction par cycle) d'après la table de correspondance ; tables
vivantes, fichiers LaTeX du cycle 4 (renommage, `\seqSetCodeSequence`), reclassement de
S02, S04, S10, données de départ (`data/C03_*`, `data/C04_*`, `N1x_sequences.yaml`,
`outils/objectifs_6e.json`, `outils/ref6e_v2.md`), libellé de `proportionnalite`,
`.dbtex` régénérés. Avant la v0.58.0 : 1 à 2 semaines d'usage normal de la v0.57.0
(scanner, compilation de livrets S…, import d'un lot de 6e en essai à blanc).
