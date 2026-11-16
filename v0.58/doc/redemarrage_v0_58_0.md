# Redémarrage v0.58.0 — thèmes et codes A1, livraison 2 : outil de migration

> Base de comparaison : cb8fb0e « v0.57 » (déployée et poussée). **Aucune table, aucune
> route, aucun écran nouveau.** Un outil de migration (`outils/migrer_themes_codes_2027.py`),
> une table de reclassement (`outils/reclassement_2027.json`), un correctif des outils de
> lots de 6e, un libellé de couleur. Paquet LaTeX inchangé.

## Besoin

Plan de migration des thèmes et des codes (`plan_migration_themes_codes.md`, § 3
« Livraison 2 », § « Ce qui n'est jamais touché », § 4). Feu vert de Laurent le
16 novembre (7 h 36) : « Version 0.57 déployée et poussée. Les livrets compilent
correctement. On peut passer directement à la suite » — pas de période d'essai de la
v0.57 : la migration se fait maintenant. Les référentiels de cette année sont figés et
publiés ; leurs PDF sont disponibles.

## L'outil

`..\outils\python\python.exe .\outils\migrer_themes_codes_2027.py` (depuis `appli\`) :

| Mode | Ce qui se passe |
| --- | --- |
| (rien) | **essai à blanc** sur une copie en mémoire de la base : le rapport est exactement celui de `--apply`, rien n'est écrit |
| `--apply` | contrôles, confirmation, **sauvegarde** `data_atelier\sauvegardes\avant_migration_2027_<date>.db`, migration en base (une transaction), fichiers LaTeX ; journal `journal_migration_2027_<date>.json` et rapport `.txt` dans `sauvegardes\` |
| `--annuler [JOURNAL]` | retour arrière d'après le journal (le dernier par défaut) : base puis fichiers ; **refusé** si une donnée migrée a été modifiée depuis (restaurer alors la sauvegarde) |

Options : `--db`, `--cycle C03|C04`, `--latex DOSSIER` (répétable), `--sans-fichiers`,
`--sans-publication`, `--reclassement`, `--yes`. Codes de sortie : 0 succès, essai ou
rien à faire ; 1 abandon ; 2 refus (rôle `classe`, codes mêlés, référentiel figé sans
publication, contenu à reclasser introuvable, conflit de fichier, conflit au retour
arrière) ; 3 erreur (rien n'est écrit).

## Ce que fait la migration

- **Cycle 3** : thèmes B → F, C → B, D → C, E → D, F → E (noms et couleurs inchangés, ordre
  et descriptions réécrits) ; S01…S13 → A1…E1 (11…51) ; M01…M07 inchangées (leur thème
  suit) ; X01…X16 et XA…XC intacts.
- **Cycle 4** : A renommé, D → B, B → C renommé, **D « Proportionnalité, fonctions »
  créé**, E renommé, C → F ; S03 → A1, **A2 « Nombres rationnels et arithmétique »
  créée**, S01 → A3, S05 → A4, S11 → B1, S12 → B2, S13 → B3, S06 → C1, S07 → C2,
  S09 → D1, S08 → D2, S14 → E1 ; S02, S04, S10 → X02, X04, X10 (102, 104, 110,
  « (archive) », hors du principal).
- **Tables vivantes** des niveaux du cycle : `sequences_par_niveau`, précédences (y
  compris de 5e vers la 6e), `notions`, `methodes`, `exercices`, `fiches_resume`,
  `cartes_automatisme`, `cartes_mentales`, `origin_seq` des liens d'exercices ; colonne
  `fichier` du cycle 4. Identifiants inchangés : liens, évaluations, fiches suivent.
  **Les contenus ne sont jamais réécrits** (variables xint `N10S03A01_…`, noms d'images).
- **Reclassement** de S02, S04, S10 (synthèse § 3, `outils/reclassement_2027.json`).
- **Fichiers LaTeX du cycle 4**.

## Décisions

- **M1 — Outil** sur le modèle d'`import_lot6e.py` (lancement par chemin, essai à blanc
  par défaut, sauvegarde, journal).
- **M2 — Une transaction par exécution** (les deux cycles, ou un seul avec `--cycle`) :
  un échec au cycle 4 ne laisse jamais un cycle 3 migré sans journal. Migration séparée :
  `--cycle C03` puis `--cycle C04`.
- **M3 — Journal élémentaire** : chaque écriture (valeurs avant / après, lignes créées) ;
  le retour arrière rejoue à l'envers et vérifie chaque ligne. Fichiers : renommages,
  copies, dossiers créés, réécritures (originaux gardés dans
  `sauvegardes\migration_2027_<date>_tex_originaux\`).
- **M4 — Jamais touché, vérifié par l'outil** : empreinte SHA-256 de toutes les tables
  autres que les tables vivantes, des archives X01–X16 du cycle 3 et des fichiers
  `referentiels\` (dont `_verrouille\`, `_publication\`) et `referentiels_fichiers\`,
  avant et après chaque cycle ; une différence annule tout. Refus d'une base de rôle
  `classe`, d'une base aux codes mêlés et d'un référentiel interne figé sans première
  publication ou à publication périmée (`--sans-publication` pour passer outre, risque 4
  du plan).
- **M5 — 2025_N10 et 2025_N12 (en conception)** : laissés. Sans instantané, ils lisent
  les tables vivantes et passent d'eux-mêmes aux codes A1 ; leurs documents compilés
  deviennent périmés. Un interne non figé qui aurait un instantané serait refusé (cas
  absent de la base).
- **M6 — Reclassement** atome par atome : contenus repris renumérotés à la suite dans la
  séquence d'arrivée (y compris d'un niveau à l'autre, N11/S04 → N12/A2) ; copie de
  N11/S04 M3, FR3 et de ses trois exercices en N12/A2 (nouvel identifiant, sections
  comprises) ; le reste en X02, X04, X10. Liens objectifs et évaluations gardés par
  identifiant ; l'origine notée dans les révisions suit l'exercice. **A2 n'a pas encore
  de séquence-niveau** : elle naîtra avec les nouveaux référentiels ; ses contenus
  attendent dans les ateliers d'atomes. « 9 exercices » sans nom dans la synthèse = les
  exercices des objectifs des méthodes citées (les nombres tombent juste), écrits en
  clair dans la table.
- **M7 — Fichiers LaTeX** : arborescences N10\, N11\, N12\ trouvées d'après
  `configuration.json` (`chemin_reference_sequences`, `chemin_sources_livrets`), puis
  `..\reference\sequences` et `..\sequences`, ou `--latex`. Renommés : `.tex`
  (notions, méthodes, exercices, `_enonce`, `_param`, livrets), `Objectifs.csv`, dossiers
  `Snn` ; réécrits : `\seqSetCodeSequence{…}` et `\input{…}` vers un fichier renommé
  (fins de ligne et encodage gardés). Un fichier qui ne porte qu'un contenu le suit (dans
  le dossier du niveau d'arrivée s'il change de niveau) ; un fichier partagé (une notion
  `_00` par séquence en 4e) prend le nom d'archive. Images jamais renommées. Les fichiers
  d'archive (`N10X02F02.tex`) ne sont pas lus par le scanner : jamais réimportés. La
  colonne `fichier` est recodée même sans arborescence trouvée : **aucun doublon au scan
  suivant**.
- **M8 — Données de départ non réécrites** (`data\C03_*.csv`, `data\C04_*.csv`,
  `N1x_sequences.yaml`, `outils\objectifs_6e.json`) : l'atelier lit ses copies de
  `data_atelier\` (faites à la bascule), pas `appli\data\` ; ces fichiers sont le point
  de départ d'une base neuve, que `import_lot6e` (archivage X01–X16 d'après
  `C03_sequences.csv`) puis cet outil amènent aux codes A1 ; `C04_objectifs.csv` et
  `C04_connaissances.csv` résolvent les macros des `.tex` existants, écrits en S… ; les
  outils de lots traduisent `objectifs_6e.json` et les lots (D6, v0.57.0). Table de
  correspondance ajoutée en tête de `outils\ref6e_v2.md`.
- **M9 — Couleurs** : aucune famille nouvelle ; libellé de `proportionnalite` :
  « Proportionnalité, fonctions ». Les `.dbtex` ne servent qu'aux livrets compilés à la
  main hors de l'appli (`\seqLoadData`) ; l'appli ne les lit pas : non régénérés.
- **M10 — Descriptions des thèmes** d'après les préambules des programmes (cycle 3 de
  2025, annexe 2 de 2026) ; F au cycle 4 garde la sienne.
- **C1 — Correctif des outils de lots** (`outils/import_lot6e.py`) : la traduction des
  étiquettes ne vise plus que « N pts --- S01-02 » (évaluations). Avant, le texte libre
  « --- S01-02 » d'un titre de document était traduit à moitié : après migration,
  12 documents AC/AT des lots auraient été « mis à jour ».

## Contrôles

- pytest : 4939 réussis avant (cb8fb0e) ; **4974 réussis, 8 sautés, 0 échec** après
  (35 tests ajoutés, `tests/test_v0_58_0_migration_themes_codes.py`) ; vitest : **386**
  (41 fichiers, inchangé).
- **Copie de la base d'atelier du 16 novembre** (avec les premières publications figées,
  arborescence LaTeX reconstruite d'après la base) : essai à blanc (base inchangée,
  comparaison octet pour octet) ; `--apply` (rapport identique à l'essai) ; second
  `--apply` : « rien à faire » ; scan : 988 fichiers reconnus, tous déjà en base, 76
  archives ignorées ; `--annuler` : **54 tables identiques** à l'origine, arborescence
  identique ; `--apply` à nouveau. Exports au format d'échange des 15 référentiels
  **identiques** avant / après (publications figées resservies) ; instantanés et
  `referentiels\` identiques.
- **Lots de 6e** (`reference\lot6e` du 16 novembre) importés sur la base migrée : lus en
  A1, 0 créé, 0 mis à jour, base identique après deux `--apply` ; aucune séquence S…
  recréée. Aperçu de création du référentiel de 6e : 13 séquences A1…E1, 20 parties,
  52 objectifs (+ 20) ; mises en route : 7, 22, 25, 131 séances (comme avant).
- **Livrets compilés** après migration (N10/A1, N11/A3, N12/A4, plan N11/A4, livret de
  6e N09/A1) : titres « Séquence A1 », objectifs A1-02 en 6e, mêmes erreurs
  d'environnement du conteneur qu'avant migration (TeX Live 2023).
- Aperçu chiffré de ce qui changera chez Laurent : `apercu_migration.txt` (livraison).

## Jour de migration — ce que fait Laurent (PowerShell, depuis `appli\`)

1. **Fermer** l'appli (atelier et classe) et tout éditeur LaTeX (un `.tex` ouvert bloque son
   renommage : l'outil remet alors tout en place, code 3).
2. **Sauvegardes** (P5), hors du dossier de l'appli :
   `$s = "..\..\sauvegarde_migration_2027_$(Get-Date -Format yyyy-MM-dd_HHmm)"; New-Item -ItemType Directory $s`
   puis `Copy-Item -Recurse .\data_atelier "$s\data_atelier"`, idem `.\data_classe` et `..\reference`.
3. **Installer** le zip delta comme d'habitude ; vérifier :
   `..\outils\python\python.exe .\outils\verifier_md5.py --racine . --manifest MANIFEST.md5`.
4. **Essai à blanc** : `..\outils\python\python.exe .\outils\migrer_themes_codes_2027.py > "$s\essai.txt"` ;
   lire `essai.txt` : ligne « arborescence : …\reference\sequences » (sinon ajouter
   `--latex ..\reference\sequences`), chiffres proches de `apercu_migration.txt`,
   « Anomalies : aucune ».
5. **(Facultatif) essai sur une copie** : `Copy-Item -Recurse .\data_atelier .\data_essai_migration`,
   `Copy-Item -Recurse ..\reference\sequences "$s\sequences_essai"`, puis
   `..\outils\python\python.exe .\outils\migrer_themes_codes_2027.py --db .\data_essai_migration\seqenseigne.db --latex "$s\sequences_essai" --apply --yes` ;
   ouvrir l'appli sur la copie : `$env:SEQ_PROFIL="atelier"; $env:SEQ_DATA="data_essai_migration"; ..\outils\python\python.exe app.py`
   (http://localhost:5000 ; Ctrl+C pour fermer ; supprimer ensuite `data_essai_migration`).
6. **Migration** : `..\outils\python\python.exe .\outils\migrer_themes_codes_2027.py --apply`
   (répondre « o ») ; relancer sans `--apply` : « Rien à faire ».
7. **Contrôles** (`.\lancer.bat atelier`) : 6e en A1…E1 (M01…M07 inchangées) ; 5e, 4e, 3e en
   A1…E1 et X02, X04, X10 ; contenus repris visibles dans les ateliers d'atomes (A2 en 5e,
   4e, 3e) ; Import référence › scanner N10, N11, N12 : tout « existant », rien de
   « nouveau » ; recompiler un livret par niveau (N10/A1, N11/A4, N12/B2) ; Référentiels :
   N11_v2025 et 2025_N11b inchangés (état, synchronisation) ; `.\lancer.bat classe` :
   rien n'a changé.
8. **Retour arrière** si besoin : `..\outils\python\python.exe .\outils\migrer_themes_codes_2027.py --annuler`.
   Refusé si quelque chose a été modifié depuis : appli fermée, recopier
   `data_atelier\sauvegardes\avant_migration_2027_<date>.db` sur `data_atelier\seqenseigne.db`
   et `$s\reference` sur `..\reference`.

## Risques et parades

- Les livrets vivants des séquences d'arrivée (N10/A1, N10/B1, N10/B3, N11/A3, N11/D2,
  N11/B3, N12/B3…) incluent les notions et méthodes reclassées : voulu (matière des
  nouveaux référentiels) ; 2025_N10 et 2025_N12 changent donc aussi (documents à
  recompiler s'ils servent).
- Scanner une **ancienne** copie de l'arborescence (non migrée) recréerait des atomes en
  S… : ne scanner que l'arborescence migrée.
- Livrets compilés à la main hors de l'appli (`\seqLoadData`, `.dbtex`) : `.dbtex` à
  régénérer avec datatooltk.
- Les cartes et PDF de 2026-2027 gardent leurs couleurs (PDF figés) ; S08, S09 (D) et
  S11 (B) changent de couleur dans les nouveaux documents.

## Après la migration (pour l'assistant)

- Les codes A1 sont la règle dans les tables vivantes ; les instantanés figés, les
  publications et les référentiels externes gardent leurs codes S….
- Un document recompilé dans l'atelier pour un référentiel figé suit les tables vivantes
  (codes A1, contenus reclassés) : la partie classe ne s'en sert pas (PDF figés de
  `_verrouille\`).
- Nouveaux référentiels 2027 : créés après la migration, en codes A1 (marche à suivre de
  6e v0.58).
