# seqenseigne — Documentation technique

**Version 0.6.3e — avril 2026 · Laurent Coste**

---

## 1. Vision et périmètre

### 1.1 Objectif général

seqenseigne est un système pédagogique en trois parties complémentaires :

- **Partie 1 — Suivi de classe** (implémentée, chantier Progression annuelle finalisé en v0.6.3c).
- **Partie 2 — Conception des atomes pédagogiques** (en cours : socle BDD finalisé en v0.6.3e, ateliers opérationnels).
- **Partie 3 — Conception de livrets et progressions** (à venir).

### 1.2 Contexte technique

| Élément                | Choix                                                     |
|------------------------|-----------------------------------------------------------|
| Backend                | Python 3.12 + Flask (serveur local, port 5000)           |
| Frontend               | HTML/CSS/JS vanilla (pas de framework)                    |
| Persistance principale | SQLite (`seqenseigne.db`) via `SqliteStore`              |
| Identifiants           | UUID opaques préfixés (`cl_`, `el_`, `pg_`, `et_`, `ref_`, `cr_`, `obj_`, `pt_`, `sn_`, `liv_`, `ver_`) |
| Référentiels CSV       | `C03_*.csv`, `C04_*.csv` (niveaux, thèmes, séquences, connaissances, objectifs) |
| Référentiels R1–R4     | Tables `referentiel_*` (cycles, niveaux, thèmes, séquences, objectifs) — migrés en BDD |
| API externes           | data.education.gouv.fr (vacances, annuaire EN), calendrier.api.gouv.fr (fériés) |
| Documents LaTeX        | MiKTeX Portable x64 26.2 + paquet `seqenseigne`           |
| Lancement              | `lancer.bat` (Windows, port 5000)                         |

### 1.3 Conventions de niveau

| Code | Niveau scolaire | Cycle | Remarque                  |
|------|-----------------|-------|---------------------------|
| N09  | 6ème            | C03   | Données à migrer          |
| N10  | 5ème            | C04   | Référence — entièrement migré |
| N11  | 4ème            | C04   | Migration terminée        |
| N12  | 3ème            | C04   | Migration terminée        |

Table en dur `PARAM_NIVEAUX_FALLBACK` couvre aussi N07 (CM1) et N08 (CM2) pour la résolution de macros, sans pour autant déployer le flux complet sur ces niveaux.

---

## 2. Modèle pédagogique

### 2.1 Hiérarchie des atomes

Chaque séquence est composée d'atomes pédagogiques indépendants, assemblés dans l'atelier Livret :

- **Notion** (= Connaissance) : un concept autonome, identifié par son titre, avec corps + exemples + remarques.
- **Méthode** : un savoir-faire, même structure que la Notion, plus les critères d'évaluation F/A/E et les notions associées.
- **Exercice** : lié à un ou plusieurs objectifs, avec énoncé paramétré + corrigé toujours présent.
- **Objectif** : créé implicitement lors de l'affectation d'une méthode à une séquence. L'objectif 01 (Connaître le cours) est automatique dans chaque séquence.

### 2.2 Niveaux de maîtrise et barème

Le barème est fixe pour tous les objectifs :

| Code | Signification                  | Points /20 | Critère                          |
|------|--------------------------------|------------|----------------------------------|
| I    | Insuffisant                    | 4          | Fixe pour tous les objectifs     |
| F    | Fondamental — à consolider     | 10         | Spécifique à chaque objectif     |
| A    | Satisfaisant                   | 16         | Spécifique à chaque objectif     |
| E    | Excellent                      | 20         | Spécifique à chaque objectif     |
| NE   | Non évalué                     | —          | Aucun exercice déclaré           |

Source de vérité : `services/niveaux.py` (`NIVEAUX`, `CODES_NOTES`, `CODES_SANS_NOTE`, `migrer_ancien_code`).

### 2.3 Séries d'exercices

| Lettre | Libellé              | Description                                     |
|--------|----------------------|-------------------------------------------------|
| F      | Fondamental          | Avec corrigé, vérification en autonomie — 10 pts |
| A      | Avancé               | Sans corrigé, validation par l'enseignant — 16 pts |
| E      | Exploration          | Approfondissement, pour aller plus loin — 20 pts |
| AE     | Activité/Exploration | Activité de découverte (objectif nouveau)        |

### 2.4 Objectif 01 — Connaître le cours

Présent automatiquement dans chaque séquence, avec critères fixes identiques pour toutes les séquences :

| Case       | Libellé         | Correspond à                         |
|------------|-----------------|--------------------------------------|
| F (10 pts) | Notes cahier    | Trace écrite notée en classe         |
| A (16 pts) | Fiches résumé   | Fiches de résumé complétées          |
| E (20 pts) | Oral prof       | Présentation orale à l'enseignant    |

### 2.5 Nomenclature des fichiers LaTeX

| Type                   | Exemple                     |
|------------------------|-----------------------------|
| Exercice fondamental   | `N11S01F01.tex`             |
| Exercice avancé        | `N11S01A01.tex`             |
| Exercice exploration   | `N11S01E01.tex`             |
| Activité de découverte | `N11S01AE01.tex`            |
| Notion                 | `N11_S01_Notion_01.tex`     |
| Méthode                | `N11_S01_Methode_01.tex`    |
| Paramètres exercices   | `N11S01_param.tex`          |
| Livret (généré)        | `N11_S01_Livret.tex`        |

---

## 3. Architecture du système

### 3.1 Structure des fichiers

```
D:\Enseignement\seqenseigne\
  seqenseigne\
    appli\               ← Application web Flask
      app.py
      clean_cache.py     ← Vidage cache API
      lancer.bat
      templates\index.html
      static\
        app.js / app.css
        ateliers_theme.js
        ateliers_seqcycle.js
        ateliers_seqniv_v2_edit.js
      data\
        seqenseigne.db
        C03_themes.csv, C04_themes.csv
        C03_sequences.csv, C04_sequences.csv
        C03_connaissances.csv, C04_connaissances.csv
        C03_objectifs.csv, C04_objectifs.csv
        param_niveaux.csv
      persistence\       ← schema.sql, sqlite_store.py, csv_store.py, ids.py
      services\          ← niveaux, progression, calendrier_scolaire,
                           etablissements, resoudre_macros, scanner_vers_v2
      routes\            ← classes, suivi, progression, calendrier,
                           etablissements, scanner, admin
      importers\         ← scanner_latex, sequencesdb, csv_legacy
      tests\             ← pytest (992 tests verts en v0.6.3e)
    reference\           ← Sources LaTeX maîtres
    outils\              ← make.exe, MiKTeX portable, Python portable
```

### 3.2 Paquet LaTeX seqenseigne

#### Options disponibles

| Option                 | Paquets chargés             | Usage                                                |
|------------------------|-----------------------------|------------------------------------------------------|
| (aucune)               | Base complète               | Séquences sans figure géométrique                    |
| `[geometrie]`          | tkz-euclide, tkz-base, tkz-tab | Séquences avec figures tkz (S10-S13 typiquement)  |
| `[scratch]`            | scratch3                    | Séquences d'algorithmique (S09 typiquement)          |
| `[geometrie,scratch]`  | Les deux                    | Si les deux sont nécessaires                         |

#### Séquences nécessitant `[geometrie]`

| Niveau | Séquences                          |
|--------|------------------------------------|
| N10    | S01, S05, S07, S10, S11, S12, S13  |
| N11    | S03, S09, S10, S11, S12, S13       |
| N12    | S07, S09, S11, S12                 |

#### Formats précompilés (`.fmt`)

Les formats précompilés réduisent le temps de chargement des paquets de ~30 sec à ~2-3 sec.

Procédure (après `make install`) :

```bash
make -f Makefile.win install
make -f Makefile.win fmt
make -f Makefile.win N10-S03   # test sans géométrie
make -f Makefile.win N10-S12   # test avec géométrie
```

---

## 4. Application Flask

### 4.1 Architecture des ateliers

#### Gestion de classe (Partie 1)

| Module                            | Description                                                               |
|-----------------------------------|---------------------------------------------------------------------------|
| Paramétrage — Classes             | Années scolaires, classes, élèves. Import CSV Pronote.                   |
| Paramétrage — Établissements      | CRUD + validation par UAI (annuaire EN) + fusion des doublons.           |
| Progression annuelle              | Calendrier visuel semainier sept→août, créneaux posés sur la grille, vacances + jours fériés selon l'académie, états `en_cours`/`valide`/`verrouille`. |
| Suivi des séquences               | Classe × progression × objectif × élève. Niveaux I/F/A/E, bulletins.      |

#### Ateliers de conception (Partie 2)

| Atelier                    | Description                                                                                                    |
|----------------------------|----------------------------------------------------------------------------------------------------------------|
| Thèmes (cycle)             | CRUD des thèmes de chaque cycle. Liste avec pastille couleur + hover ombré cohérent.                          |
| Séquences de cycle         | CRUD des séquences de cycle, rattachement aux thèmes. Liste avec hover ombré cohérent.                        |
| Séquence (niveau)          | Édition d'une séquence pour un niveau donné : parties, objectifs, liaisons aux méthodes et exercices.         |
| Notion                     | Titre + corps LaTeX + exemples + remarques (permutables). Sidebar : identification `N11/S01/C01` + titre.     |
| Méthode                    | Même structure + notions associées + fin de cycle O/N + critères F/A/E. Sidebar : `N11/S01/O02` + titre + badge FC. |
| Exercice                   | Niveau F/A/E + objectif(s) + variables `_param.tex` + énoncé + corrigé. Sidebar : `N11/S01/F01` + titre. Testeur de variables intégré. |
| Livret                     | Assemblage des atomes par séquence. Génère le fichier `N1X_S01_Livret.tex`. *(à venir)*                      |

Toutes les sidebars d'ateliers utilisent la classe CSS `.atl-item` pour un rendu uniforme (hover ombré, état actif surligné).

### 4.2 Module `services/resoudre_macros.py`

Résout les macros nommantes LaTeX (`\seqObjectifGetNom{02}`, `\seqConnaissanceGetNom{01}`, etc.) à l'import.

- Contexte chargé intégralement depuis les CSV de référence : `param_niveaux.csv`, `C0X_sequences.csv`, `C0X_themes.csv`, `C0X_connaissances.csv`, `C0X_objectifs.csv`.
- 17 macros nommantes supportées : `\seqNiveauGet{NomCourt,NomLong,CodeCycle}`, `\seqThemeGet{Nom,CodeCouleur,Description}`, `\seqSequenceGet{Nom,NomOf,Numero,Theme}`, `\seqObjectifGet{Nom,FinCycle,MaitriseTB,MaitriseS,MaitriseF}`, `\seqConnaissanceGetNom`, `\seqMaitriseGetNom`.
- Macros non résolues → remplacement par `[à saisir]` + incident au rapport (fichier + champ + macro + raison).
- Les champs libres (corps, exemples, remarques, énoncés, corrigés) ne sont **jamais** touchés.
- Symétrie C03 / C04 : clés composites `(niveau, sequence, code)` pour objectifs et connaissances → pas de collision.

### 4.3 Module `services/scanner_vers_v2.py`

Peuple les tables v2 (`sequences_par_niveau`, `sequence_parties`, `objectifs_v2`, `objectif_exos`, `partie_precedences`) à partir des tables legacy (`objectifs`, `methodes`, `exercices`, `livrets_de_sequence`).

- Appelé automatiquement par `scanner_vers_bdd` après la persistance des atomes.
- Déduction du numéro de partie depuis le premier chiffre du code objectif (convention canonique : `02` → partie 1, `12` → partie 2, `22` → partie 3).
- Fallback parser sur le plan de travail (`N1X_Plan_de_travail.tex`) pour les codes non-numériques.

### 4.4 Module `services/calendrier_scolaire.py`

Fournit les vacances et jours fériés à partir d'APIs officielles, avec mise en cache en base.

- Mapping `ACADEMIE_ZONE` : 25 académies métropolitaines → Zone A/B/C.
- `vacances(annee_scolaire, zone, store, force_refresh=False, academie=None)` — appelle data.education.gouv.fr, dédoublonne, complète Pont Ascension et Vacances d'été depuis tables officielles, cache en base.
- `jours_feries_annee_scolaire(annee_scolaire, store)` — agrège 2 années civiles via calendrier.api.gouv.fr, filtre sept→août, tolérant aux pannes d'API.
- Dates retournées en heure locale Paris (conversion UTC+2 pour gérer l'offset `+00:00` renvoyé par l'API).
- Tables dures : `VACANCES_ETE_DEBUT` (zones × années scolaires), `PONT_ASCENSION` (par année scolaire). Fallback algorithmique : 1er samedi ≥ 4 juillet.

### 4.5 Module `services/etablissements.py`

Gestion des établissements, validation par UAI et fusion :

- CRUD standard (`creer`, `lister`, `lire`, `mettre_a_jour`).
- `valider_par_uai(store, etab_id, uai)` — appelle fr-en-annuaire-education, remplit nom/académie/ville/adresse, bascule l'état à `valide`. Lève `DoublonEtablissement` si le nom officiel est déjà porté par un autre établissement.
- `fusionner(store, source_id, cible_id)` — migre atomiquement classes + progressions de source vers cible, puis supprime source. Interdite si `source.etat == 'valide'`. Refusée si conflit de progression sur `(niveau, annee)`.
- Exceptions structurées `DoublonEtablissement` et `ConflitFusion`.

### 4.6 Routes Flask principales

| Route                                       | Méthode     | Description                                                |
|---------------------------------------------|-------------|------------------------------------------------------------|
| `/api/classes`                              | GET/POST    | Liste ou crée une classe. Filtre `?annee=` / `?etablissement=` |
| `/api/classes/<cid>`                        | PUT/DELETE  | Modifier / supprimer une classe                            |
| `/api/classes/<cid>/eleves`                 | POST        | Ajouter un élève                                           |
| `/api/classes/<cid>/eleves/import`          | POST        | Import CSV Pronote (multipart)                             |
| `/api/etablissements`                       | GET/POST    | Liste / création d'établissement                           |
| `/api/etablissements/<id>`                  | GET/PATCH/DELETE | Détail / mise à jour / suppression                    |
| `/api/etablissements/<id>/valider`          | POST        | Validation par UAI (409 `doublon_detecte` si conflit)      |
| `/api/etablissements/<id>/fusionner`        | POST        | Fusion vers `cible_id` (409 si refus)                      |
| `/api/calendrier/vacances`                  | GET         | `?annee=2025-2026&academie=Rennes` ou `&zone=B`            |
| `/api/calendrier/jours-feries`              | GET         | `?annee=2024` ou `?annee_scolaire=2021-2022`               |
| `/api/progression/<niveau>`                 | GET         | Lire la progression (`?annee=&etablissement=`)             |
| `/api/progression_id/<id>`                  | GET         | Lire par id opaque                                         |
| `/api/progression_id/<id>/etat`             | POST        | Change l'état (`en_cours` ↔ `valide`)                      |
| `/api/suivi`                                | GET/POST    | Exercices cochés par classe                                |
| `/api/niveaux/set`                          | POST        | Définir un niveau (déclenche verrouillage auto)            |
| `/api/niveaux/calculer`                     | POST        | Recalculer depuis les exercices                            |
| `/api/versions/creer`                       | POST        | Snapshot du YAML courant                                   |
| `/api/classes/<cid>/version`                | POST        | Affecter une version à une classe                          |
| `/api/export`                               | GET         | Export JSON (classe ou global)                             |
| `/api/param/tester`                         | POST        | Tester les variables xintexpr (atelier Exercice)           |
| `/api/scanner/apercu`                       | GET         | Prévisualisation d'un niveau à scanner                     |
| `/api/scanner/detail`                       | GET         | Détail atomes d'un niveau                                  |
| `/api/scanner/lancer`                       | POST        | Import BDD depuis les sources LaTeX scannées               |
| `/api/admin/reset/reference`                | POST        | Vide la référence (atomes + tables v2, préserve suivi et référentiels stables) |

---

## 5. Modèle de données SQLite

### 5.1 Entités principales

| Table                   | UUID    | Colonnes clés                                                              | Contraintes                                          |
|-------------------------|---------|----------------------------------------------------------------------------|------------------------------------------------------|
| `etablissements`        | `et_xxx` | nom, uai, academie, ville, adresse, etat                                 | UNIQUE (nom), état `propose`/`valide`                |
| `classes`               | `cl_xxx` | nom, niveau, annee, etablissement_id, progression_id                     | FK etab ON DELETE RESTRICT                           |
| `eleves_classes`        | —       | classe_id, eleve_id, ordre                                                | PK composite                                         |
| `progressions`          | `pg_xxx` | niveau, annee, etablissement_id, etat, referentiel_id                    | État `en_cours`/`valide`/`verrouille`                |
| `creneaux`              | `cr_xxx` | progression_id, sequence, rang_debut, rang_fin, periode, date_debut, date_fin, ordre, partie, livret_version_id | |
| `referentiel_niveaux`   | `ref_xxx`| niveau, version, etat (`en_cours`/`valide`/`verrouille`)                 |                                                      |
| `referentiel_sequences` | —       | referentiel_id, seq_code, nom, ordre                                      | PK composite                                         |
| `referentiel_objectifs` | —       | referentiel_id, seq_code, code, nom, fin_cycle, critere_f/a/e             | PK composite, FK sequences CASCADE                   |
| `notions`               | —       | id, titre, corps, ordre_sections, niveau, sequence, num_connaissance, fichier |                                                   |
| `methodes`              | —       | id, titre, corps, fin_cycle, ordre_sections, niveau, sequence, num_methode, num_objectif, fichier | |
| `exercices`             | —       | id, serie, nom, variables, enonce, corrige, niveau, sequence, num, serie_code, fichier | |
| `objectifs`             | —       | id, methode_id, code, niveau, sequence, nom, critere_F, critere_A, critere_E, est_nouveau, obj_precedent_id | |
| `objectif_exos`         | —       | objectif_id, serie, exercice_id, ordre, origin_niveau/seq/serie/num       | PK composite, FK `objectif_id → objectifs_v2` CASCADE, FK `exercice_id → exercices` **RESTRICT** |
| `sequences_par_niveau`  | `sn_xxx` | niveau, sequence_code, parametres                                        |                                                      |
| `sequence_parties`      | `pt_xxx` | sequence_par_niveau_id, numero                                           |                                                      |
| `objectifs_v2`          | —       | id, partie_id, code, nom, methode_id, critere_F/A/E                       | FK methode_id ON DELETE SET NULL                     |
| `cache_api`             | —       | cle TEXT PK, payload, fetched_at                                          | `vacances:X:AAAA-AAAA:acad`, `feries:AAAA`, `annuaire:UAI` |

### 5.2 Chaîne FK critique (v0.6.3e)

```
exercices ←(RESTRICT)── objectif_exos ──(CASCADE)→ objectifs_v2
                                                         │
                                                         │ SET NULL
                                                         ↓
                                                     methodes
```

La FK **RESTRICT** de `objectif_exos → exercices` protège les liaisons pédagogiques. Toute opération qui voudrait supprimer un exercice doit d'abord supprimer ses lignes dans `objectif_exos`.

C'est pour cette raison que `ecrire_exercices` a été refondue en **diff-based** (v0.6.3e correctif du 23 avril 2026) : elle ne fait plus de `DELETE FROM exercices` brutal, mais calcule la différence entre la base et la liste cible et ne supprime que les exos qui disparaissent (avec leurs liaisons au préalable).

### 5.3 Colonne `progressions.etat`

Trois états avec transitions contrôlées :

| État         | Signification           | Entrée possible depuis               | Sortie possible vers                 |
|--------------|-------------------------|--------------------------------------|--------------------------------------|
| `en_cours`   | Édition libre           | (défaut à la création) ; `valide`    | `valide` ; `verrouille` (auto)       |
| `valide`     | Progression finalisée   | `en_cours`                           | `en_cours` ; `verrouille` (auto)     |
| `verrouille` | Évaluations saisies     | `en_cours` (auto) ; `valide` (auto)  | (aucune en v0.6.3e)                  |

---

## 6. Calendrier scolaire

### 6.1 Sources de données

| Source                     | URL                                    | Contenu                                           |
|----------------------------|----------------------------------------|---------------------------------------------------|
| data.education.gouv.fr     | fr-en-calendrier-scolaire              | Toussaint, Noël, Hiver, Printemps                 |
| Table officielle embarquée | `VACANCES_ETE_DEBUT`                   | Début des vacances d'été (2023-2024 → 2026-2027)  |
| Table officielle embarquée | `PONT_ASCENSION`                       | Jeudi Ascension → lundi reprise                    |
| calendrier.api.gouv.fr     | `/jours-feries/metropole/<annee>.json` | 11 jours fériés nationaux                          |
| data.education.gouv.fr     | fr-en-annuaire-education               | Annuaire par UAI                                   |

### 6.2 Pourquoi des tables officielles en dur ?

- L'API `fr-en-calendrier-scolaire` ne renvoie **PAS** les vacances d'été (pas de date de fin).
- Elle ne renvoie **PAS** non plus le pont de l'Ascension.
- Ces dates sont publiées annuellement au Journal Officiel par arrêté du Ministère — elles sont stables et valent mieux qu'une tentative de déduction.
- Quand les dates 2027-2028 seront publiées (octobre 2026), il suffira d'ajouter une ligne dans `VACANCES_ETE_DEBUT` et `PONT_ASCENSION`.

### 6.3 Pièges timezone traités

- L'API renvoie `2026-05-13T22:00:00+00:00` pour représenter le 14 mai 00h heure de Paris. Sans conversion, on obtenait un décalage d'un jour.
- **Fix backend** : `_iso_date()` applique +2h avant de formater en `AAAA-MM-JJ`.
- **Fix frontend** : `_dateToISO(d)` remplace `toISOString().slice(0,10)` pour générer les lundis en heure locale.
- **Rendu du calendrier** : `_vacancesDeLaSemaine()` teste le chevauchement avec la semaine de classe lundi-vendredi, pas la semaine complète. Les vacances dont le premier ou dernier jour tombe un samedi/dimanche ne colorent pas la semaine précédente ou suivante par effet de bord.

---

## 7. Import LaTeX → Base (v0.6.3e)

### 7.1 Pipeline

`scanner_vers_bdd(data, json_store, csv_store, plans_dir)` orchestre 4 étapes :

1. **Résolution des macros** — contexte chargé depuis les CSV via `construire_contexte_global(csv_store)`. Seuls les titres de notions et de méthodes sont résolus. Les champs libres restent intacts.

2. **Persistance des atomes** — dans l'ordre imposé par les dépendances :
   - `ecrire_notions` (indépendant)
   - **`ecrire_objectifs()`** — réhydrate `objectifs` depuis `referentiel_objectifs`
   - `ecrire_methodes` (pose `methode_id` sur les objectifs par `(niveau, sequence, code)`)
   - `ecrire_exercices` (diff-based, résout les `objectifs_codes` via `(niveau, sequence, code)`)
   - `ecrire_livrets_importes`

3. **Peuplement v2** — `peupler_v2_depuis_base(conn, niveau, plans_dir)` crée les `sequences_par_niveau`, `sequence_parties`, `objectifs_v2` et `objectif_exos` pour le niveau scanné.

4. **Rapport** — `{notions, methodes, exercices, livrets, erreurs, incidents_macros, v2}` retourné à l'UI.

### 7.2 Déduplication par `fichier`

Chaque atome scanné porte un champ `fichier` (ex. `N11_S01_Notion_01.tex`). Les `ecrire_*` utilisent ce champ pour distinguer :

- **Nouveaux** : fichier absent de la base → INSERT (UUID frais)
- **Existants** : fichier déjà en base → préservation de l'ID, UPDATE in-place

Cette stabilité des IDs est **critique** pour préserver les liaisons `objectif_exos` entre scans successifs (voir §5.2).

### 7.3 Concurrence

Les 3 scans (N10, N11, N12) sont lancés **séquentiellement** côté JS (`for ... of` avec `await`) — jamais en parallèle. Un `Promise.all` provoquait des `IntegrityError FK` sur les écritures concurrentes en `exercices` / `objectif_exos`.

### 7.4 Reset de la référence

`SqliteStore.reset_reference()` vide les atomes pédagogiques tout en préservant :

- Les référentiels stables (`referentiel_niveaux`, `referentiel_sequences`, `referentiel_objectifs`)
- Les données de suivi (`classes`, `eleves`, `niveaux`, `progressions`, `creneaux`)
- Les cycles et thèmes

Ordre de suppression imposé par les FK (depuis le correctif `fix_reset_reference`) :

```
livret_revisions → livret_exercices → objectif_exos → partie_precedences
  → objectifs_v2 → sequence_parties → sequences_par_niveau
  → exercice_objectifs → exercices
  → methode_notions → objectifs → methodes
  → notions → livrets_de_sequence
```

Après un reset, un scan complet suffit à tout repeupler : `ecrire_objectifs()` rehydrate les `objectifs` depuis `referentiel_objectifs`, et `peupler_v2_depuis_base` reconstruit la chaîne v2.

---

## 8. Conventions de code

### 8.1 Python

- Routes groupées par domaine métier (classes, établissements, calendrier, progressions, suivi, niveaux, versions, scanner).
- Le bloc `if __name__ == "__main__"` est toujours en dernière position du fichier.
- Nommage : `/api/{ressource}` ou `/api/{ressource}/{id}/{action}`.
- Erreurs : `{ "error": "message", "code": "..." }` avec code HTTP approprié. 409 pour conflits résolvables par l'UI.
- Identifiants opaques préfixés via `persistence/ids.py`.

### 8.2 Paquet seqenseigne — `.dtx`

- Pas de caractère `@` dans les fichiers `.tex` utilisateur — uniquement dans les `.dtx`.
- Les wrappers publics (`\seqSetColorsTheme`, `\seqFiltreDonnees`…) évitent les `@` dans les livrets.
- Convention `\theH<compteur>` définie dans `seqCreeCompteurs` pour éviter les warnings hyperref.
- Options `[geometrie]` et `[scratch]` dans `seqenseigne-core.dtx` — transmises via `seqenseigne.sty`.

### 8.3 Fichiers LaTeX utilisateur

- `\seqSetCodeNiveau{N10}\seqSetCodeSequence{S01}` en début de document (après `\begin{document}`).
- `\seqSetDataPath{../../}` et `\seqLoadData` pour les données CSV.
- `\seqDefChemin{{../exercices}{../../N09/exercices}}` pour les chemins des exercices.
- Pas de `\renewcommand{\seqCodeSequence}` (ancienne API — supprimée).

### 8.4 Conventions UI

Convention de nommage des identifiants DOM/CSS : `<section>-<sousSection>[-<élément>][-<modifier>]`, tirets simples, mots composés concaténés (ex. `admin-importsuivi-hist-*`).

Les sidebars d'ateliers utilisent toutes la classe `.atl-item` (hover ombré, état actif surligné), avec les sous-classes `.atl-item-id` (identification en monospace), `.atl-item-titre` (ellipsis) et `.atl-item-fc` (badge fin de cycle).

---

## 9. Tests

**992 tests verts au 23 avril 2026**, répartis ainsi :

| Module                                     | Fichier de tests                                   | Tests |
|--------------------------------------------|----------------------------------------------------|-------|
| Classes + élèves                           | `test_classes.py`, `test_classes_routes.py`       | ≈ 40  |
| Suivi + niveaux                            | `test_suivi.py`, `test_niveaux.py`                | ≈ 50  |
| Progressions + créneaux                    | `test_progression.py`, `test_progression_etat.py`, `test_progression_rechercher.py` | ≈ 60 |
| Établissements + fusion                    | `test_etablissements.py`                          | 18    |
| Calendrier + vacances d'été + pont + TZ    | `test_calendrier_scolaire.py`                     | 19    |
| Référentiels R1–R4                         | `test_R1_*`, `test_R2_*`, `test_R3_*`, `test_R4*` | ≈ 340 |
| Imports CSV + historique                   | `test_importers.py`, `test_import_arborescence.py`, `test_sequencesdb.py` | ≈ 35 |
| Résolution macros (CSV C03+C04)            | `test_resoudre_macros.py`                         | 49    |
| Scanner → BDD (idempotence, FK exercices)  | `test_scanner_vers_bdd_idempotence.py`, `test_ecrire_exercices_fk.py` | 12 |
| Reset de la référence                      | `test_reset_reference_full.py`                    | 5     |
| Peuplement v2                              | `test_peuplement_*.py`, `test_R4b_scanner_vers_v2.py` | ≈ 60 |
| Services (niveaux, cycle, param_evaluator) | `test_services.py`, `test_param_evaluator.py`     | ≈ 50  |
| Autres (ids, store, routes)                | divers                                             | ≈ 130 |

> **Contrainte : 0 régression à chaque livraison.** Chaque patch doit être accompagné d'un test nouveau ou d'une adaptation explicite.

---

## 10. Feuille de route

### 10.1 Partie 1 — Suivi de classe

- ✅ Gestion multi-classes, import CSV Pronote, grille de suivi (vue classe + vue élève).
- ✅ Calcul automatique des niveaux, notes équivalentes /20, versions de livrets (snapshots), verrouillage des versions.
- ✅ v0.6.3a : infrastructure établissements (UUID, UAI, académie) + service calendrier scolaire + cache API.
- ✅ v0.6.3b : UI gestion des établissements, validation par UAI, fusion des doublons, badges à 3 états.
- ✅ v0.6.3c : calendrier visuel semainier sept→août, créneaux posés sur la grille, vacances + jours fériés + pont Ascension, badge d'état progression, verrouillage automatique.
- 🔲 v0.6.3d (prévu) : détail créneau enrichi avec liste d'objectifs, suppression vue synthétique redondante.
- 🔲 Périodes d'évaluation (S1/S2), vue bulletin par période, export CSV pour bulletin.
- 🔲 Données N09 (6ème).
- 🔲 Verrouillage granulaire par créneau + par séquence (nécessite changement de schéma — reporté à une version dédiée).

### 10.2 Partie 2 — Conception des atomes

- ✅ Atelier Notion/Connaissance — implémenté (sidebar identification + titre, CRUD complet).
- ✅ Atelier Méthode + critères F/A/E — implémenté (badge FC, notions associées).
- ✅ Atelier Exercice — implémenté (sidebar identification + titre, zone variables, testeur xintexpr, énoncé + corrigé obligatoire).
- ✅ Atelier Thèmes (cycle) — implémenté (sidebar cohérente avec hover ombré).
- ✅ Atelier Séquences de cycle — implémenté (sidebar cohérente avec hover ombré).
- ✅ Atelier Séquence (niveau) — parties, objectifs, liaisons aux méthodes et exercices opérationnels.
- ✅ Import LaTeX → BDD idempotent avec résolution automatique des macros nommantes (CSV C03+C04 comme source de vérité).
- ✅ Module `param_evaluator.py` (évaluateur xintexpr) en backend.
- 🔲 Persistance des modifications d'atomes → regénération des fichiers `.tex` / `.csv`.
- 🔲 Atelier Livret (assemblage, génération `N1X_S01_Livret.tex`).
- 🔲 Atelier Progression — génération du plan de travail annuel depuis le calendrier v0.6.3c.
- 🔲 Génération PDF depuis l'appli (3 passes pdflatex).
- 🔲 Test et mesure des formats précompilés `.fmt`.
- 🔲 Script migration `\usepackage[geometrie]` dans les 17 livrets concernés.

### 10.3 Partie 3 — Progressions et BdD

- 🔲 Peupler `creneau_objectifs_exos` depuis l'UI (table créée mais non encore peuplée).
- 🔲 Interface drag & drop (calendrier scolaire) pour l'édition des créneaux.
- 🔲 Affectation séquences → périodes.
- 🔲 Alertes de dépendances inter-séquences.
- 🔲 Déverrouillage explicite des progressions avec suppression en cascade des évaluations.
- 🔲 Option compilation dyslexie (xeLaTeX + OpenDyslexic + A3 + LetterSpace=20 etc., à activer sur demande).

### 10.4 Dette technique recensée

- 🔲 Refonte diff-based de `ecrire_notions` et `ecrire_methodes` (même motif que `ecrire_exercices`, pas urgent car pas de FK RESTRICT).
- 🔲 Renommage des identifiants `stab-*` de Suivi de classe vers `suivi-*` (cohérence avec la convention adoptée dans Admin).
- 🔲 Suppression de `.atl-item-meta` dans `app.css` (devenue inutilisée après refonte des sidebars).
- 🔲 Ajouter l'année 2027-2028 dans `VACANCES_ETE_DEBUT` et `PONT_ASCENSION` quand les dates sortent au JO en octobre 2026.
