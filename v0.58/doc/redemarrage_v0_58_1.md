# Redémarrage v0.58.1 — correctif : atomes compilés en gris après la migration des codes

> Base de comparaison : 520eaf0 « v0.58 » (déployée, poussée, migration appliquée chez
> Laurent). **Aucune table, aucune route, aucun écran nouveau.** Un service corrigé
> (`services/latex_rendu_atome.py`), un fichier de tests. Paquet LaTeX inchangé.

## Signalement (16 novembre, 13 h 50)

« La compilation des atomes exercices, méthodes, notions et fiches ne sont pas rendus avec
le thème de la séquence : ils sont en gris. Les cartes d'automatisme sont OK. Les livrets
de séquence aussi. »

## Cause (confirmée sur une copie migrée de la base du 16 novembre)

`resoudre_theme(conn, niveau, sequence)` cherchait la couleur **uniquement dans les
instantanés des référentiels** (`referentiel_sequences` ⋈ `referentiel_niveaux` ⋈
`referentiel_themes`), « gris » sinon. Depuis la migration, les séquences vivantes sont en
A1… ; les référentiels figés gardent S… (voulu) et les référentiels en conception n'ont
pas d'instantané : une séquence A1 n'est trouvée nulle part → **gris pour 1 651 atomes sur
1 651 rendus en couleur** (1 216 exercices, 157 méthodes, 127 notions, 151 fiches).
Livrets (`v2_lecture`) et cartes (`resoudre_code_couleur`) lisent les tables vivantes :
non touchés.

Avant la migration, la même lecture donnait déjà des couleurs fausses par endroits (elle
prenait la séquence de même code dans n'importe quel référentiel du niveau) : 6e S01
« géométrie » (S01 du référentiel externe X2026_N09), archives X… de 6e en gris…

## Décisions

- **R1 — Couleur d'un atome : tables vivantes d'abord.** `param_niveaux` (niveau → cycle)
  → `sequences_du_cycle` (cycle + code) → `themes.code_couleur`, exactement la source des
  cartes et des livrets (vérifié : même couleur pour les 62 séquences-niveaux de la base).
  Repli sur les instantanés des référentiels **seulement** si la séquence n'est pas dans
  les tables vivantes ou si son thème n'a pas de couleur valide (ex. N11/S03 d'un
  référentiel figé) ; « gris » en dernier recours.
- **R2 — Getters résolus dans le texte d'un atome** (`resoudre_macros_csv`) :
  `\seqSequenceGetNom`, `\seqSequenceGetNumero`, `\seqSequenceGetTheme`,
  `\seqThemeGetNom` suivent le même ordre (vivant, puis instantanés, puis placeholder
  `[SEQ-…]`…). `\seqSequenceGetNumero` d'une séquence en code de thème rend le code
  (« A1 »), comme le titre des livrets (règle L1 de la v0.57.0), jamais « 11 ».
  `\seqObjectifGetNom` et `\seqConnaissanceGetNom` lisaient déjà les tables vivantes.
  Dans la base du 16 novembre, aucun atome n'utilise ces getters de séquence ou de thème
  (seule une méthode utilise `\seqObjectifGetNom`) : aucun rendu actuel ne change par R2.
- **R3 — Rien d'autre n'est modifié** (audit ci-dessous) : instantanés, publications,
  progressions, partie classe, référentiels externes lisent `referentiel_*` à dessein.
- **R4 — Fichiers de la v0.58 à la racine.** Le commit 520eaf0 range la livraison v0.58
  dans un sous-dossier `v0.58\` du dépôt ; à la racine, `outils\migrer_themes_codes_2027.py`,
  `outils\reclassement_2027.json`, les tests v0.58 et les docs v0.58 manquent et quatre
  fichiers sont restés en v0.57 (`outils\import_lot6e.py`,
  `services\referentiel_principal_externe.py`, `outils\ref6e_v2.md`,
  `paquet\CHANGELOG.md`). Le zip v0.58.1 contient donc aussi ces fichiers à la racine
  (octet pour octet ceux de la v0.58, sauf `doc\ETAT_COURANT.md` et `paquet\CHANGELOG.md`
  mis à jour) ; le sous-dossier `v0.58\` est à supprimer (`MANIFEST_SUPPRESSIONS.md`).

## Audit des lectures par code de séquence

**Corrigés (documents vivants)** — `services/latex_rendu_atome.py` : `resoudre_theme` et
les 4 getters ci-dessus (utilisés par le rendu des atomes et, pour les getters, par les
récapitulatifs d'exercices, de cours, de fiches, les corrigés et les évaluations).

**Laissés (instantané voulu ou données propres)** :

| Fichier | Usage | Classement |
| --- | --- | --- |
| `persistence/sqlite_store.py` | lecture d'un référentiel, parties de progression, création | instantané (progression sur référentiel figé) |
| `services/format_referentiel.py` | structure de l'export / publication | instantané (publication) |
| `services/import_publication.py` | import d'une publication | instantané (remplacé en entier) |
| `services/referentiel_figeage.py` | trace JSON du verrouillage, recalcul des parties | instantané |
| `services/referentiels_internes.py` | écriture / purge de l'instantané (RI2) | instantané |
| `services/modeles_referentiel.py` | modèle tiré d'un référentiel, empreinte | instantané / externe |
| `services/referentiel_principal_externe.py` (29) | édition d'un référentiel externe | données propres de l'externe |
| `services/planification_hebdo.py`, `services/seances_resume.py` | nom de séquence de la progression | partie classe (instantané) |
| `services/repartition.py` | liste de tables (bascule) | pas une lecture |
| `routes/sequences.py` | nom de route seulement (CSV, écran Composer sans gabarit) | sans objet |
| outils (`import_historique_*`, `verifier_referentiels`, migration), `scripts/peuplement_11…` | outils ponctuels | sans objet |

## Autres conséquences de la migration repérées (non corrigées)

1. **Import d'un nouveau `.tex` (scanner)** : les titres résolus à l'import
   (`services/resoudre_macros.py`) lisent les CSV de départ (`C04_*.csv`, en S…, M8) :
   une notion ou une méthode **nouvelle** d'une séquence A1 dont le titre est
   `\seqConnaissanceGetNom{01}` ou `\seqSequenceGetNom` sera importée avec le titre
   « [à saisir] » (vérifié : N10/S03 → nom trouvé, N10/A1 → « [à saisir] »). Les atomes
   déjà en base ne sont pas réimportés. Parade : saisir le titre dans l'atelier ;
   correctif à prévoir (lire les tables vivantes, ou traduire par
   `outils/correspondance_codes_2027.json`).
2. **Couleurs différentes d'avant la migration** pour certains atomes : elles suivent
   maintenant le thème vivant, comme les livrets : S08, S09 → D (proportionnalité) au lieu
   de données ; S10, S11 → B (géométrie) au lieu de grandeurs ; 6e M03, M04 → grandeurs,
   M05 → géométrie, M07 → proportionnalité ; archives X… de 6e en couleur.
3. **Exercices et fiches de 6e au gabarit « sixieme »** : mise en forme de l'équipe, sans
   couleur de thème — inchangé (ce n'est pas le gris signalé).
4. **Déverrouiller 2025_N11b** (instantané écrit par l'atelier) purgerait son instantané ;
   au reverrouillage il serait réécrit depuis les tables vivantes, donc en A1. Ne pas
   déverrouiller les référentiels de cette année.
5. Sans changement depuis la v0.58 : documents de 2025_N10 / 2025_N12 périmés (M5),
   `.dbtex` non régénérés (M9).

## Contrôles

- Copie de `atelier_ro_1611.db` (avec premières publications) migrée par l'outil v0.58
  (`--apply`, code 0, aucune anomalie) : avant correctif, un exercice, une méthode, une
  notion, une fiche de N10, N11, N12 et un exercice d'archive X… de N09 → `gris` ; après →
  couleur du thème (nombres, géométrie…). La 6e n'a ni notion ni méthode en base.
- Banc « mêmes sorties » sur la base migrée, code v0.58 / code v0.58.1 (3 797 fichiers :
  408 documents de référentiels, 2 927 atomes, 84 livrets et plans, 223 documents de 6e,
  exports, instantanés) : **seuls 1 651 `.tex` d'atomes changent, et seulement la ligne
  `\seqSetColorsTheme`** ; plus aucun atome en gris ; documents des référentiels, livrets,
  exports et instantanés identiques.
- pytest : voir `ETAT_COURANT.md` ; vitest : 386 (41 fichiers).
- Aperçus compilés (exercice et fiche de 4e, exercice d'archive et fiche de 6e, avant /
  après) dans la livraison.

## Déploiement (PowerShell, depuis `appli\`)

1. Fermer l'appli ; installer le zip ; vérifier :
   `..\outils\python\python.exe .\outils\verifier_md5.py --racine . --manifest MANIFEST.md5`.
2. Supprimer le sous-dossier de la v0.58 (voir `MANIFEST_SUPPRESSIONS.md`).
3. `.\lancer.bat atelier`, recharger la page (F5), ouvrir un exercice de 4e › Rendu PDF :
   couleur du thème. Le cache des PDF est indexé par le contenu du `.tex` : la ligne de
   couleur change, donc **les PDF gris ne sont plus resservis**, pas besoin de vider le
   cache. Pour récupérer la place des anciens PDF gris : Système › « Vider le cache des
   rendus PDF » (facultatif).
4. Aucune commande de base : pas de migration, pas d'outil à lancer.
