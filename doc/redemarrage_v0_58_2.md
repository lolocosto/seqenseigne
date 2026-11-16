# Redémarrage v0.58.2 — le scanner et les données de départ après la migration des codes

> Base de comparaison : f442c1a « v0.58.1 » (déployée, poussée, migration appliquée chez
> Laurent). **Aucune table, aucune route, aucun écran nouveau, aucun fichier de données
> réécrit.** Quatre services corrigés, l'outil de migration complété (séquences-niveaux
> A2, point Q1, à relancer chez Laurent), un fichier de tests. Paquet LaTeX inchangé.

## Constat de départ (v0.58.1)

Le scanner résolvait les titres-macros des `.tex` (`\seqObjectifGetNom{06}`,
`\seqConnaissanceGetNom{02}`…) avec les seuls CSV de départ (`C0X_objectifs.csv`,
`C0X_connaissances.csv`, copies de `data_atelier\`), restés en codes S… (décision M8 de
la v0.58.0) : une nouvelle notion ou méthode de A1 était importée « [à saisir] ».

## Ce que l'audit a trouvé en plus (copie migrée de la base du 16 novembre)

Un scan complet (bouton « Scanner » de l'atelier, N10 à N12) **sur la base migrée**, avec
le code v0.58.1, même sans aucun nouveau fichier :

1. **recrée N11/S01…S14** (14 séquences-niveaux, 19 parties, 89 objectifs) dans
   l'atelier : `ecrire_objectifs` « réhydrate » les objectifs depuis l'instantané de tout
   référentiel `verrouille` — 2025_N11b, en S… ;
2. **détache ou intervertit 26 liens méthode ↔ objectif** : `ecrire_methodes` réécrit
   toutes les méthodes et refait les liens d'après (niveau, séquence, num_objectif) ; les
   méthodes reclassées vers A1, A2, B1, B3, D2… sont liées par identifiant à leur
   objectif d'archive (X02, X04, X10) — 23 objectifs perdent leur méthode, 3 en
   reçoivent une autre (N11/A3/03, avec les critères de l'objectif d'archive ;
   N11/D2/03 et 04) ;
3. **efface les 77 liens objectif ↔ notion** (`objectif_notions`) : `ecrire_notions` fait
   DELETE + INSERT de toutes les notions (cascade). Ce défaut existait **avant** la
   migration (même résultat sur la base non migrée) ; les sections des notions et des
   méthodes sont aussi recréées avec de nouveaux identifiants.

Sur la base non migrée, 1 et 2 ne se produisent pas (l'instantané et les liens suivent
encore les codes S…).

**Diagnostic chez Laurent** : l'outil de migration relancé en essai à blanc signale
l'effet 1 (« sequences_par_niveau : 14 ligne(s) du cycle 4 encore en ancien code… »).
L'effet 3 se voit au compte de `objectif_notions` (77 dans la base du 16 novembre ; 0
après un scan). Commandes : section « Commandes Windows ».

## Décisions

- **P1 — Titres : tables vivantes d'abord** (`services/resoudre_macros.py`,
  `completer_depuis_base`, appelé par `importers/scanner_latex.py`). Ordre :
  1. `objectifs` (via `sequence_parties` / `sequences_par_niveau`), titres des `notions`
     (connaissances), `sequences_du_cycle`, `themes` — la source du rendu des atomes
     (`latex_rendu_atome.resoudre_macros_csv`) et des livrets ;
  2. CSV de départ sous leur propre code (base neuve, base non migrée) **et** sous le
     code vivant donné par `outils/correspondance_codes_2027.json`, **seulement si la
     séquence vivante porte le même nom** que celle du CSV (C04 S03 « Calcul numérique »
     → A1 ; jamais le CSV du cycle 3, qui décrit l'ancien découpage : S07
     « Proportionnalité » n'est pas la B3 « Angles ») ;
  3. sinon « [à saisir] » et un incident au rapport (inchangé).
  `\seqSequenceGetNumero` d'une séquence A1 rend « A1 » (règle L1). Sur une base non
  migrée, un objectif prend désormais son nom vivant au lieu de celui du CSV (c'est celui
  que l'atelier affiche) ; les connaissances absentes de la base viennent du CSV comme
  avant.
- **P2 — Réhydratation des objectifs bornée aux séquences du cycle**
  (`SqliteStore.ecrire_objectifs(seulement_sequences_du_cycle=True)`, utilisé par le
  scanner) : un objectif d'instantané dont la séquence n'existe pas dans les séquences du
  cycle du niveau est ignoré (`objectifs_ignores`). Base non migrée, base neuve, reset +
  scan : comportement inchangé.
- **P3 — Scan additif** (`SqliteStore.ajouter_notions`, `ajouter_methodes`) : le scanner
  n'insère que les notions et méthodes dont le `fichier` est absent de la base ; aucune
  ligne existante n'est touchée (liens, sections, états). Une nouvelle méthode n'est liée
  à l'objectif (niveau, séquence, num_objectif) que s'il n'a pas encore de méthode, et ne
  remplit que ses critères vides. Les exercices gardent l'écriture précédente (vérifiée
  sans effet sur l'existant : `objectif_exos`, `exercices` identiques après scan).
  `ecrire_notions` / `ecrire_methodes` restent pour les autres usages (tests).
- **P4 — Libellés des parties de 6e** (`livret_sequence_6e.libelles_parties`, aussi lu par
  les cartes mentales) : `outils/objectifs_6e.json` reste en S… (M8) ; une séquence A1 lit
  la ligne de son ancien code par la table de correspondance (cycle du fichier, C03).
  Depuis la migration, couvertures des livrets et des corrigés de 6e affichaient
  « Partie 2 » au lieu de « Partie 2 --- Médiatrice » (12 libellés sur 6 séquences).
- **P5 — Modèle « Programme du cycle »** (`modeles_referentiel._cycle`) : les critères
  manquants en base étaient complétés par `C0X_objectifs.csv` sous le même code ; après
  la migration, plus rien (N11 : 52 critères perdus, N12 : 13). La séquence vivante lit
  son ancien code, à la même condition de nom qu'avant (v0.52.0). Modèle identique à
  celui d'avant migration pour les 33 séquences communes.
- **P6 — Données de départ non réécrites.** Les lecteurs passent par les tables vivantes
  (voie préférée du brief) ; réécrire `C0X_*.csv`, `N1x_sequences.yaml`,
  `objectifs_6e.json` casserait la chaîne d'une base neuve (M8) et ne servirait plus à
  rien. La partie fichiers de l'outil de migration n'a rien de nouveau à faire. Les
  `.dbtex` ne sont pas produits par l'appli (aucun générateur) : non régénérés
  (inchangé, v0.58.0).

## Q1 — Séquence-niveau A2 manquante (signalé pendant la v0.58.2)

**Constat** (copie migrée de la base du 16 novembre, client de test de l'appli) : le
reclassement a rangé en A2 « Nombres rationnels et arithmétique » des contenus de N10
(3 notions, 6 méthodes, 30 exercices, 6 fiches, 14 cartes), N11 (3 méthodes, 11
exercices, 3 fiches, 3 cartes) et N12 (3 notions, 4 méthodes, 33 exercices, 4 fiches,
4 cartes), mais la v0.58.0 n'a créé la séquence-niveau A2 dans aucun de ces niveaux
(M6 : « elle sera créée avec les nouveaux référentiels »). Or **l'atelier n'a aucun
moyen de créer une séquence-niveau** (seuls l'import de 6e et la réhydratation du scan en
créent). Effets : les ateliers d'atomes listent et modifient bien ces contenus (filtre
A2 et « toutes les séquences » : la liste des séquences vient de `sequences_du_cycle`,
qui a A2), mais l'atelier Séquence répond 404 « Séquence par niveau introuvable » :
impossible d'y créer une partie, un objectif, de lier méthodes, fiches et exercices ;
A2 n'apparaît ni dans les livrets, ni dans les plans, ni dans les documents des
référentiels en conception (2025_N10, 2025_N12). Le scan n'est pas gêné (fichiers déjà
en base).

**Décision Q1 — l'outil de migration crée la séquence-niveau manquante**
(`creer_sequences_niveau_manquantes`, `outils/migrer_themes_codes_2027.py`, version
0.58.2) : pour chaque niveau du cycle et chaque séquence **en code de thème** du cycle
qui a des contenus (notions, méthodes, exercices, fiches, cartes) sans séquence-niveau,
une ligne `sequences_par_niveau` en état « en cours », sans partie ni objectif ni
paramètres. Journalisée comme le reste (sauvegarde, journal, `--annuler`) ; idempotente ;
appliquée aussi quand le cycle est déjà migré (le reste dit « rien à faire ») : c'est le
cas de la base de Laurent. Jamais pour une archive (X…), une mise en route (M…) ou un
ancien code. `--annuler` refuse de retirer une séquence-niveau dans laquelle une partie a
été créée depuis (la suppression l'emporterait en cascade). Sur la base du 16 novembre :
exactement N10/A2, N11/A2, N12/A2.

Écarté : faire montrer par l'interface une séquence du cycle sans séquence-niveau
(l'atelier Séquence, les livrets, les référentiels en conception et les documents
supposent tous la ligne `sequences_par_niveau` ; plusieurs écrans à changer pour un
cas né de la migration).

Conséquence visible : A2 (vide) apparaît dans l'atelier Séquence de N10, N11, N12, dans
la liste des livrets et plans du cycle 4 et parmi les cibles « livret de séquence » des
référentiels de ces niveaux dans l'atelier — y compris les figés, dont les documents
recompilés dans l'atelier suivent déjà les tables vivantes depuis la v0.58.0 (la classe
lit les PDF de `_verrouille\`, inchangés).

## Audit des lecteurs de données de départ

| Lecteur | Lit | Après migration | Suite |
| --- | --- | --- | --- |
| `importers/scanner_latex.py` + `services/resoudre_macros.py` | CSV `C0X_*` (data_atelier) | titres « [à saisir] » en A1 | **P1** |
| `persistence/sqlite_store.ecrire_objectifs` (appelé par le scan) | instantanés `referentiel_objectifs` verrouillés | recrée N11/S01…S14 | **P2** |
| `sqlite_store.ecrire_notions` / `ecrire_methodes` (scan) | base (réécriture complète) | 26 liens méthode ↔ objectif cassés, 77 liens objectif ↔ notion effacés | **P3** |
| `services/livret_sequence_6e.libelles_parties`, `cartes_mentales` | `outils/objectifs_6e.json` (S…) | libellés de parties perdus en 6e | **P4** |
| `services/modeles_referentiel._objectifs_csv` / `_cycle_csv` | CSV `C0X_*` | critères du CSV perdus | **P5** |
| `services/livret_sequence._lire_objectifs_prerequis_depuis_csv` | CSV, en repli des tables vivantes | prérequis lus en base (précédences recodées) | sans effet |
| `services/latex_rendu_atome.resoudre_macros_csv` | tables vivantes | déjà vivant (v0.58.1) | — |
| `services/fiches_import.py` (admin) | objectifs vivants | un fichier encore en S… : fiche ignorée avec erreur, rien de créé | sans effet |
| `services/cycle_auto_import.py` | `C0X_themes/sequences.csv` | seulement si le cycle est absent de la base | sans effet |
| `services/cycle_import.py`, route `/api/admin/cycle/importer` (pas dans l'interface) | `C0X_themes/sequences.csv` | réimporterait les anciens thèmes et S… par-dessus | **risque signalé** |
| `outils/import_lot6e.py` | `objectifs_6e.json`, lots | traduits vers la convention de la base (D6, v0.57.0) | — |
| `persistence/yaml_store`, `services/sequences.build_sequences`, `routes/progression` (reset), `routes/suivi`, `routes/classes` | `N1x_sequences.yaml`, `C04_sequences.csv` | partie classe (base de classe non migrée, historiques en S…) | sans effet |
| `importer_arborescence.py`, `importers/sequencesdb.py` | dossiers de suivi des années passées | historiques en S… (voulu) | sans effet |
| `services/latex_gen.py` (`routes/sequences`, écran Composer sans gabarit) | YAML | non utilisé dans l'atelier | sans effet |
| livrets compilés à la main (`\seqLoadData`, `.dbtex`) | `.dbtex` | hors appli ; à régénérer avec datatooltk s'ils servent encore | inchangé |

## Autres traces de codes S… côté atelier vivant (signalées, non modifiées)

- **Référentiel externe** (`referentiel_principal_externe._recoder_sequences`,
  `ajouter_sequence`) : un référentiel externe en conception numérote ses séquences
  **S01, S02…** (M01… pour la MER). Un nouvel externe créé après la migration aura donc
  des codes S… à côté des A1 de l'interne. À trancher par Laurent (codes de thème pour
  les externes ?).
- **Interface** : valeurs de repli `S01…S14` si `/api/cycles/<code>/sequences` ne répond
  pas (`static/app.js`, `ATL_SEQUENCES_OPTIONS`), sélection par défaut `S01` (remplacée
  par la première séquence de la liste au premier affichage) ; textes d'exemple « S01 »
  des champs Code (nouvelle séquence du cycle, `templates/index.html`), séquence
  précédente et ajout de révision (`static/ateliers_seqniv_v2_edit.js`) — la saisie
  « A1 » y est acceptée (v0.57.0). Commentaire « Options S01..S14 » du filtre de
  compilation (les options viennent de la base).
- `\seqSetCodeSequence{S00}` dans le livret annuel des plans de travail
  (`livret_plans_de_travail.py`) : code neutre, sans lecture de données.
- `config/liaisons_objectifs.yaml` (S…) : aucun lecteur.
- Gabarits de nouveaux atomes : aucun code en dur (niveau et séquence viennent de la
  sélection) ; aucun modèle de `.tex` de l'appli n'écrit `\seqSetCodeSequence` en S….

## Contrôles

- `tests/test_v0_58_2_scanner_apres_migration.py` (15 tests, base des tests v0.58
  migrée) : méthode A1 au titre `\seqObjectifGetNom{02}` → nom vivant ; notion A1 → CSV de
  S03 rattaché ; introuvable → « [à saisir] » + incident ; getters de séquence (« B1 ») ;
  CSV du cycle 3 jamais rattaché ; CSV non réécrits ; base non migrée ; second scan sans
  doublon, base identique table par table ; aucune séquence S… recréée depuis un
  instantané verrouillé ; réhydratation intacte pour les séquences du cycle ; liens
  objectif ↔ notion et méthode ↔ objectif gardés ; objectif déjà lié non pris ;
  référentiels figés et PDF intacts ; libellés de 6e ; modèle « programme du cycle ».
  **12 échouent sur le code v0.58.1.**
- Copie migrée de la base du 16 novembre : scan complet (N10–N12) sur la base migrée et
  sur la base non migrée → **base identique table par table** (54 tables) ; six nouveaux
  `.tex` (titres-macros) : 5 titres justes, 1 « [à saisir] » attendu ; second scan : rien.
- Q1 (4 tests) : A2 créée en N10 et N11 dans la base de test (contenus), vide et en
  cours, rien pour les archives ; base déjà migrée (comme la v0.58.0) : essai à blanc
  sans écriture, `--apply` crée A2, relance « Rien à faire » et base identique ;
  `--annuler` la retire, mais refuse s'il y a une partie ; atelier : méthodes A2 listées,
  atelier Séquence N10/A2 ouvert (200, 404 avant), création d'une partie (201). **Les 4
  échouent sur le code v0.58.1.** Copie de la base du 16 novembre déjà migrée : essai à
  blanc (base inchangée), `--apply` (3 séquences-niveaux), second `--apply` « Rien à
  faire », `--annuler` (base identique, 54 tables) ; migration complète d'une base non
  migrée avec arborescence : A2 créées dans la même transaction, `--annuler` rend base et
  fichiers d'origine. Banc après Q1 : seules apparaissent les cibles A2 (livrets et plans
  de N10, N11, N12 ; cible A2 des documents « livret de séquence » des référentiels).
- Banc « mêmes sorties » (3 822 / 3 825 fichiers : documents des référentiels, atomes,
  livrets, plans, documents 6e, exports, instantanés, modèles, libellés) : base non
  migrée, **identique** ; base migrée, 26 différences, toutes voulues (libellés de parties
  de 6e retrouvés, critères du modèle N11 retrouvés).

## Commandes Windows

Depuis `appli\` (Python portable), après le déploiement, appli arrêtée :

```
..\outils\python\python.exe .\outils\migrer_themes_codes_2027.py --sans-fichiers
..\outils\SQLite\sqlite3.exe data_atelier\seqenseigne.db "SELECT count(*) FROM objectif_notions;"
..\outils\python\python.exe .\outils\migrer_themes_codes_2027.py --sans-fichiers --apply
..\outils\python\python.exe .\outils\migrer_themes_codes_2027.py --sans-fichiers
```

1. Essai à blanc (n'écrit rien) : attendu « Cycle 4 — séquences-niveaux créées » avec
   N10/A2, N11/A2, N12/A2 et « Anomalies : aucune ». S'il signale « sequences_par_niveau :
   N ligne(s) du cycle 4 encore en ancien code », ou si le compte de `objectif_notions`
   (2e commande) est 0, un scan a déjà eu lieu après la migration avec l'ancien code :
   **s'arrêter, ne rien corriger à la main, le signaler** (les liens se retrouvent dans
   `sauvegardes\avant_migration_2027_*.db`, identifiants inchangés).
2. `--apply` (confirmation « o ») : sauvegarde, journal, création des trois
   séquences-niveaux A2. Retour arrière : `--annuler`.
3. Relance : « Rien à faire ». La partie fichiers n'a rien à faire (`--sans-fichiers`
   évite seulement de chercher l'arborescence).
