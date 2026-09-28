# seqenseigne — Documentation technique

**Version 0.10.7 — 2 mai 2026 · Laurent Coste**

Document de conception technique : architecture, schéma de données,
modules, chaînes de rendu. Pour la vision pédagogique, voir
`seqenseigne_cdc_v0_10_7.md`. Pour le redémarrage rapide, voir
`redemarrage_v0_10_7.md`.

---

## 1. Vue d'ensemble

### 1.1 Contraintes d'environnement

| Contrainte | Conséquence |
|---|---|
| Clé USB portable, pas d'install | Python portable + MiKTeX portable |
| Pas de Perl sur les PC scolaires | Pas de `latexmk`, 3 passes `pdflatex` |
| Pas d'admin, pas de pip install | Stdlib + Flask + dépendances figées |
| Pas de réseau garanti | Tout local, port 5000 |
| Mono-utilisateur | SQLite (pas de Postgres) |

### 1.2 Stack technique

| Couche | Choix |
|---|---|
| Langage backend | Python 3.12 |
| Framework web | Flask (serveur Werkzeug local) |
| Persistance | SQLite (`seqenseigne.db`) |
| Frontend | HTML + CSS + JS vanilla (pas de framework) |
| Tests | pytest (1687 tests) |
| Build LaTeX | MiKTeX Portable x64 26.2 + paquet `seqenseigne` |
| API externes | data.education.gouv.fr, calendrier.api.gouv.fr |

### 1.3 Lancement

```
appli/
├── lancer.bat       # Windows
├── lancer.sh        # Linux/macOS
└── app.py           # entrée Flask
```

`lancer.bat` configure le PATH (MiKTeX, Python portables) puis
lance `python -m flask run --host=127.0.0.1 --port=5000`.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────┐
│  Frontend (templates/index.html + static/*.js)  │
│  Single page, ateliers en onglets               │
└────────────────┬────────────────────────────────┘
                 │ HTTP/JSON
┌────────────────▼────────────────────────────────┐
│  routes/  — blueprints Flask                    │
│  ├─ atomes.py    notions/méthodes/exos/objectifs│
│  ├─ v2_edition.py CRUD parties+obj+liaisons     │
│  ├─ v2_lecture.py GET séquence-niveau complet   │
│  ├─ fiches_resume.py CRUD fiches               │
│  ├─ preferences.py préférences paramétrables    │
│  ├─ admin.py imports, scanner, BDD              │
│  └─ ...                                         │
└────────────────┬────────────────────────────────┘
                 │ appels services
┌────────────────▼────────────────────────────────┐
│  services/  — logique métier                    │
│  ├─ atomes.py CRUD atomes                       │
│  ├─ v2_edition.py règles métier + erreurs       │
│  ├─ v2_lecture.py construction objet seqniv     │
│  ├─ liaisons_atomes.py NEW v0.10.7 obj_lies     │
│  ├─ scanner_vers_v2.py peuple objectif_exos     │
│  ├─ latex_rendu_atome.py génération LaTeX       │
│  ├─ compilateur_pdf.py pipeline pdflatex        │
│  └─ ...                                         │
└────────────────┬────────────────────────────────┘
                 │ accès BDD
┌────────────────▼────────────────────────────────┐
│  persistence/                                   │
│  ├─ schema.sql (DDL complet)                    │
│  └─ sqlite_store.py (accès BDD, migrations)     │
└─────────────────────────────────────────────────┘
```

---

## 3. Schéma de base de données

Le schéma complet est dans `persistence/schema.sql`. Vue
condensée :

### 3.1 Données de référence

| Table | Rôle |
|---|---|
| `cycles` | Cycles administratifs (C03, C04). |
| `themes` | Thèmes par cycle (cycle_code, code, nom, code_couleur, ordre). |
| `sequences_du_cycle` | Séquences thématiques dans un cycle (theme_id, code, numero, nom). |
| `sequences_par_niveau` | Une séquence pour un niveau donné (N11/S03 = `sn_xxx`). C'est le pivot. |

### 3.2 Atomes pédagogiques

| Table | Colonnes principales | Notes |
|---|---|---|
| `notions` | id, titre, corps, niveau, sequence, num_connaissance, fichier, etat_code | scope niveau/sequence depuis v0.6.3e |
| `methodes` | id, titre, niveau, sequence, num_objectif, fichier, etat_code | idem |
| `exercices` | id, serie, nom, variables, enonce, corrige, niveau, sequence, num, serie_code, fichier, etat_code | |
| `fiches_resume` | id, methode_id, contenu, etat_code | 1-1 avec méthode |
| `atome_sections` | entite_type, entite_id, position, titre | sections du modèle universel |
| `atome_section_items` | section_id, position, texte | items des sections |

### 3.3 Modèle v2 (parties + objectifs)

| Table | Rôle |
|---|---|
| `sequence_parties` | Découpage d'une seqniv en parties (numéro, FK vers sn). |
| `objectifs_v2` | Objectif rattaché à une partie (id, partie_id, code, nom, methode_id, critere_F/A/E, fin_cycle). |
| `objectif_notions` | Liaison N-N notion ↔ objectif (objectif_id, notion_id, ordre). |
| `objectif_exos` | Liaison exo ↔ objectif avec série et ordre (PK objectif_id+série+ordre). |
| `partie_precedences` | Précédences entre parties (legacy, peu utilisé). |
| `sequence_par_niveau_precedences` | Précédences entre seqniv (cible v0.10.2). |

### 3.4 Tables legacy / dépréciées

| Table | Statut |
|---|---|
| `objectifs` | Legacy, conservée pour rétrocompat scanner. À supprimer en v0.14. |
| `exercice_objectifs` | Legacy (remplacée par `objectif_exos`). Peuplée par scanner mais plus utilisée. À supprimer en v0.14. |
| `livrets_de_sequence`, `livret_exercices` | Snapshot YAML legacy, lu par `scanner_vers_v2.py` au peuplement, plus utilisé sinon. |

### 3.5 Suivi de classe (Partie 1)

Tables `classes`, `eleves`, `periodes`, `evaluations`, `progressions_*`,
détaillées dans la doc de v0.6.3c. Hors périmètre v0.10.x.

---

## 4. Modules services

### 4.1 `services/v2_edition.py` (le cœur métier)

Module central de toutes les mutations sur le modèle v2 (parties,
objectifs, liaisons). Implémente :

- CRUD parties (créer, supprimer si vide, renuméroter).
- CRUD objectifs (modifier code, nom, méthode liée, critères, fin
  de cycle, notions liées).
- CRUD précédences (entre seqniv, et legacy entre parties).
- Gestion de la file `objectif_exos` (ajout, retrait, réordonnancement,
  changement d'origine R/EA).

Toutes les erreurs métier sont des sous-classes de `V2EditionErreur`
avec un `code` unique mappé vers un statut HTTP par
`routes/v2_edition.py:_CODE_HTTP`.

#### Erreurs métier ajoutées en v0.10.7

| Erreur | Code HTTP | Sens |
|---|---|---|
| `NotionHorsSequence` | 409 | Notion liée à un obj d'une autre séquence. |
| `MethodeHorsSequence` | 409 | Méthode liée à un obj d'une autre séquence. |
| `MethodeDejaLiee` | 409 | Méthode déjà liée à un autre obj (cardinalité 1-1). |

#### Helper interne v0.10.7

```python
def _lire_niv_seq_objectif(conn, objectif_id):
    """Retourne (niveau, sequence) via la chaîne objectif → partie →
    sequence_par_niveau."""
```

### 4.2 `services/v2_lecture.py`

Construit l'objet « séquence-niveau complet » consommé par
l'atelier d'assemblage. Joint en une seule requête : parties →
objectifs → notions/méthode/exos. Format :

```json
{
  "id": "sn_xxx", "niveau": "N11", "sequence_code": "S03",
  "parties": [
    { "numero": 1, "objectifs": [
      { "id": "ob_yyy", "code": "01", "nom": "Connaître…",
        "methode": null, "notions": [], "exercices": {...} }
    ]}
  ],
  "precedences": [...]
}
```

### 4.3 `services/liaisons_atomes.py` (NEW v0.10.7)

Calcule pour chaque atome la liste des objectifs auxquels il est
lié (champ `obj_lies` au format `["N10·S04·02", ...]`).

API publique :

```python
lister_obj_lies_par_notion(conn)   -> dict[notion_id,   list[str]]
lister_obj_lies_par_methode(conn)  -> dict[methode_id,  list[str]]
lister_obj_lies_par_exercice(conn) -> dict[exercice_id, list[str]]
enrichir_liste_atomes(conn, liste, type_atome) -> liste mutée
```

Une seule requête SQL groupée par type, jointe sur
`objectifs_v2 → sequence_parties → sequences_par_niveau` pour
récupérer le tuple `(niveau, séquence, code)`.

### 4.4 `services/atomes.py`

CRUD des atomes (notion, méthode, exercice). Validation minimale
(titre obligatoire). Depuis v0.10.7 :

- `creer_notion` / `creer_methode` acceptent les champs `niveau` et
  `sequence` (héritage du contexte courant).
- `creer_exercice` ignore le champ `objectifs` au payload (force `[]`).
- `modifier_exercice` retire `objectifs` des champs modifiables.

### 4.5 `services/latex_rendu_atome.py` et `compilateur_pdf.py`

Pipeline de production PDF d'un atome :

1. `latex_rendu_atome.render_atome_complet(type, atome, contexte)`
   → string `.tex` complet (préambule + corps).
2. `compilateur_pdf.compile_pdf(tex_str, working_dir)`
   → 3 passes `pdflatex` séquentielles dans un répertoire temporaire,
   retourne le PDF binaire (bytes).
3. Cache disque par hash du contenu LaTeX
   (`data/cache_rendus/<hash>.pdf`).

Décision technique : pas de `latexmk` (pas de Perl). 3 passes
suffisent pour les références croisées des atomes (qui sont courts).

### 4.6 `services/fiches_import.py` (v0.10.5.2)

Parser de fichiers `.tex` flashcards pour importation. Détecte
les blocs `\begin{flashcard}{titre}…\end{flashcard}` et reconnaît
le format Anki classique. Stdlib only.

### 4.7 `services/preferences.py` (v0.10.5.2)

CRUD des préférences paramétrables :

- Liste de titres prédéfinis pour les zones (Définition,
  Propriété…).
- Critères F/A/E par défaut pour l'objectif Connaître.
- Sélecteurs de styles pour l'assemblage (à venir v0.11).

Stockage : table `preferences` (clé/valeur JSON).

---

## 5. Frontend

### 5.1 Structure générale

`templates/index.html` est une **single page** d'environ 2200 lignes
qui contient toute la structure HTML statique des onglets, ateliers
et modales. Tout le rendu dynamique (listes, contenus) est fait en
JavaScript par construction de chaînes innerHTML.

### 5.2 Modules JavaScript

| Fichier | Rôle | LOC approx |
|---|---|---|
| `static/app.js` | Cœur : ateliers, sidebar, navigation, helpers | 6200 |
| `static/atelier_seqniv_assemblage.js` | Atelier d'assemblage | 1800 |
| `static/atelier_fiche.js` | Atelier fiche de résumé | 700 |
| `static/atelier_garde_sortie.js` | Modale + snapshots (v0.10.6) | 350 |
| `static/atelier_atome_etat.js` | Badges d'état | 200 |
| `static/rendu_atome.js` | Iframe PDF + cache | 250 |
| `static/compilation_batch.js` | Modale de compilation par lot | 400 |

### 5.3 Variables d'état globales

```javascript
// Filtres communs aux 3 ateliers atomiques
let ATL_FILTRE_NIVEAU = '';   // ex. 'N11'
let ATL_FILTRE_SEQ    = '';   // ex. 'S03'

// Ateliers atomiques
let ATL_EXO         = [];     // catalogue chargé
let ATL_EXO_ACTIF   = null;   // exo en édition
let ATL_NOTIONS     = [];
let ATL_NOTION_ACTIF = null;
let ATL_METHODES    = [];
let ATL_METHODE_ACTIF = null;

// Mode atelier d'assemblage
let ATL_SEQNIV_ID   = '';     // seqniv courant
let ATL_SEQNIV_DATA = null;   // objet complet chargé via v2_lecture
```

### 5.4 Conventions JS

- `let` top-level n'est **pas** une propriété de `window` → pour
  qu'un handler `onclick="ma_fct()"` la trouve, il faut soit
  `function ma_fct(...)` (déclaré globalement, hoisté), soit
  exposer explicitement via `window.ma_fct = ma_fct`.
- Pattern courant : tous les helpers `atel*` sont des `function`
  globales pour rester accessibles depuis les attributs HTML.

### 5.5 Sidebar : badges en v0.10.7

Pour chaque atome listé, jusqu'à 4 badges peuvent apparaître :

1. **Badge série** (exo uniquement) : `F`, `A`, `E`, `EA`, `R`.
2. **Badge état** (depuis v0.10.4) : modifié, validé, en cours.
3. **Identifiant** : `N11/S03/A02` ou `C01` ou `O02`.
4. **Badges obj_lies** (NEW v0.10.7) : chips compactes des objectifs
   liés à l'atome. Format `02` (local) ou `N10·S04·02` (externe).
   Maximum 3 chips + `+N` si plus.

Helper unique : `atelObjLiesBadgesHtml(obj_lies, niv, seq)` dans
`app.js`.

CSS dédié : classes `.atl-item-objs`, `.atl-item-objchip`,
`.atl-item-objchip--ext`, `.atl-item-objchip-more`.

---

## 6. API REST

Toutes les routes sont sous `/api/`. Préfixe `/api/v2/` pour les
routes du modèle v2.

### 6.1 Atomes (CRUD direct)

| Méthode | Route | Notes |
|---|---|---|
| GET | `/api/notions` | Enrichi avec `obj_lies` (v0.10.7) |
| POST | `/api/notions` | Accepte `niveau`, `sequence` (v0.10.7) |
| PUT | `/api/notions/<id>` | idem |
| DELETE | `/api/notions/<id>` | |
| GET | `/api/methodes` | Enrichi avec `obj_lies` (v0.10.7) |
| POST | `/api/methodes` | Accepte `niveau`, `sequence` (v0.10.7) |
| PUT | `/api/methodes/<id>` | idem |
| DELETE | `/api/methodes/<id>` | |
| GET | `/api/exercices` | Filtres `serie`, `niveau`. Enrichi `obj_lies` (v0.10.7) |
| POST | `/api/exercices` | Champ `objectifs` ignoré (v0.10.7) |
| PUT | `/api/exercices/<id>` | idem |
| DELETE | `/api/exercices/<id>` | |
| GET | `/api/objectifs` | Legacy, retourne objectifs « legacy » fabriqués depuis méthodes. À supprimer v0.14. |

### 6.2 Modèle v2

| Méthode | Route | Notes |
|---|---|---|
| GET | `/api/v2/sequence-par-niveau/<sn_id>` | Objet seqniv complet |
| POST | `/api/v2/sequence-par-niveau/<sn_id>/parties` | Créer partie |
| DELETE | `/api/v2/parties/<partie_id>` | Refuse si non vide |
| PATCH | `/api/v2/parties/<partie_id>/numero` | Renuméroter |
| PATCH | `/api/v2/objectifs/<id>/code` | |
| PATCH | `/api/v2/objectifs/<id>/nom` | |
| PATCH | `/api/v2/objectifs/<id>/methode` | Body `{methode_id}`. Cardinalité 1-1 + scope (v0.10.7) |
| PATCH | `/api/v2/objectifs/<id>/criteres` | Body partiel `{critere_F?, critere_A?, critere_E?}` |
| PATCH | `/api/v2/objectifs/<id>/fin-cycle` | Body `{fin_cycle: O|N}` |
| POST | `/api/v2/objectifs/<id>/notions` | Body `{notion_id}`. Scope (v0.10.7) |
| DELETE | `/api/v2/objectifs/<id>/notions/<notion_id>` | |
| POST | `/api/v2/objectifs/<id>/exos` | Body `{exercice_id, serie, origin}` |
| DELETE | `/api/v2/objectifs/<id>/exos/<exo_id>?serie=` | |
| PATCH | `/api/v2/objectifs/<id>/exos/<exo_id>/ordre` | |
| GET | `/api/v2/methodes?niveau=&sequence=` | Catalogue scopé |
| GET | `/api/v2/notions-de-sequence?niveau=&sequence=` | Catalogue scopé |

### 6.3 Format d'erreur homogène

```json
{
  "error": "Message lisible",
  "code": "code_machine",
  "...autres détails contextuels..."
}
```

Statut HTTP : 400 (validation), 404 (introuvable), 409 (conflit /
règle métier).

---

## 7. Chaîne de production LaTeX

### 7.1 Pipeline de rendu d'un atome

```
[atome BDD] → render_atome_complet(...)
              ├─ génère le préambule (\usepackage, \input{macros}, \xintdefvar…)
              ├─ génère le corps (\begin{seqXxx}...)
              └─ retourne string .tex complet
            → compile_pdf(tex_str, working_dir)
              ├─ écrit doc.tex
              ├─ pdflatex doc.tex (passe 1) → .aux, .log
              ├─ pdflatex doc.tex (passe 2)
              ├─ pdflatex doc.tex (passe 3)
              └─ retourne doc.pdf
            → cache disque (hash du tex)
            → renvoyé au client en application/pdf inline
```

### 7.2 Filigrane ÉPREUVE

Si l'atome n'a pas l'état `validé`, le préambule injecte :

```latex
\usepackage{draftwatermark}
\SetWatermarkText{ÉPREUVE}
\SetWatermarkScale{4}
\SetWatermarkLightness{0.85}
```

### 7.3 Variables paramétrées

Bloc « Variables » de l'atelier Exercice : LaTeX libre injecté
dans le préambule juste avant l'énoncé. Permet de définir des
variables aléatoires `xint` :

```latex
\xintdefiivar{a}{randrange(2,9)}
\xintdeffloatvar{x}{a/3}
```

Évaluables côté serveur via `services/param_evaluator.py` qui
parse et exécute le sous-ensemble xint supporté (sans appeler
LaTeX).

### 7.4 Compilation par lot

Modale `compilation_batch.js` qui :

1. Liste tous les atomes à compiler (filtre par niveau, séquence,
   type, état).
2. Compile en parallèle (4 workers Python par défaut) avec barre
   de progression.
3. Affiche les erreurs de compilation par atome.
4. Permet d'ouvrir directement l'atelier d'un atome en erreur.

---

## 8. Persistance et migrations

### 8.1 SqliteStore

`persistence/sqlite_store.py` — environ 2000 lignes. Encapsule
toutes les requêtes SQL. Expose des méthodes haut niveau :

```python
js = SqliteStore(path)
js.lire_notions() / ecrire_notions(liste)
js.lire_methodes() / ecrire_methodes(liste)
js.lire_exercices() / ecrire_exercices(liste)
js.lire_livrets_importes()
# + accès direct via js._conn() pour les routes qui en ont besoin
```

### 8.2 Stratégie diff-based pour ecrire_*

À l'écriture d'une liste complète d'atomes (ex. après une
sauvegarde), le store calcule la **différence** avec ce qui est en
base et n'applique que les changements (INSERT, UPDATE, DELETE
ciblés). Évite de casser les liaisons FK RESTRICT (notamment
`objectif_exos`).

### 8.3 Migrations de schéma

Au démarrage de SqliteStore, deux passes :

1. `_migrer_schema()` : ALTER TABLE ADD COLUMN pour les colonnes
   ajoutées rétrospectivement (SQLite ne supporte pas
   IF NOT EXISTS, on détecte via `PRAGMA table_info`).
2. `_migrer_schema_post_ddl()` : appliqué après l'exécution du DDL
   complet pour des migrations de données (peuplement de colonnes
   par défaut).

Les scripts ponctuels de peuplement (changements de modèle)
sont dans `scripts/peuplement_*.py`, exécutés à la main lors d'une
montée de version.

---

## 9. Tests

### 9.1 Suite globale

```
appli/tests/
├── test_v0_10_7_regles_metier.py        (17 tests, scope + cardinalité)
├── test_v0_10_7_badges_et_orphelins.py  (12 tests, obj_lies + script)
├── test_R4e3_edition_objectif.py        (79 tests, mutations objectifs)
├── test_seqniv_completer.py
├── test_atelier_assemblage_*.py
├── test_fiches_resume.py
├── test_param_evaluator.py
├── test_scanner_vers_v2.py
└── ...
```

**Score actuel** : 1687 tests passants + 4 skipped (tests
d'intégration LaTeX qui requièrent MiKTeX, skippés en CI).

### 9.2 Conventions

- Tests unitaires : un fichier par module sous test.
- Fixtures : SQLite `:memory:` avec schéma minimal au cas par
  cas (évite de charger tout le schéma pour un test ciblé).
- Tests routes : `pytest-flask` via `client = app.test_client()`.
- Tests de scripts CLI : `subprocess.run([sys.executable, "-m", ...])`.

---

## 10. Outillage

### 10.1 Script `lister_atomes_orphelins.py` (NEW v0.10.7)

CLI dans `scripts/` qui détecte les atomes potentiellement
orphelins :

- **SANS_SCOPE** : pas de `(niveau, sequence)` renseignés.
- **SANS_LIEN** : aucune liaison vers un objectif_v2.

Usage :

```bash
python3 -m scripts.lister_atomes_orphelins --db data/seqenseigne.db
```

Sortie : tableau texte avec colonnes Statuts / Niveau / Séquence /
ID / Titre / Fichier, séparées en deux sections (notions, méthodes).

Cible : intégration UI dans v0.14 (refonte admin).

### 10.2 Scripts de peuplement

`scripts/peuplement_*.py` — séries de migrations de données
exécutées une seule fois lors d'une montée de version. Préservés
pour traçabilité.

| Script | Rôle |
|---|---|
| `peuplement_01..06_*` | Migration vers le modèle v2 (parties + obj_v2) |
| `peuplement_11..15_*` | Migration cycles + thèmes + sequences_par_niveau |
| `peuplement_v0_10_2_seq_precedences.py` | Précédences entre seqniv |

---

## 11. Décisions techniques structurantes

### 11.1 Pas de framework JS

Vanilla JS + manipulation directe du DOM. Justifications :

- L'environnement contraint (clé USB) interdit npm.
- Le rendu reste simple (pas d'animations complexes, pas d'état
  réactif fin).
- La maintenance par un seul développeur est plus aisée sans
  framework qui change tous les 18 mois.

### 11.2 SQLite vs JSON

Migration vers SQLite achevée en v0.5 (avant : `JsonStore`
fichiers .json dans `data/`). Bénéfices :

- Transactions (cohérence référentielle via FK).
- Requêtes joints performantes pour les lectures complexes
  (atelier d'assemblage).
- Une seule cible de backup au lieu d'une arborescence.

### 11.3 Frontend single-page

Toute l'UI dans `templates/index.html` + `app.js`. Pas de
navigation Flask multi-pages. Justifications :

- État conservé entre ateliers (filtre niveau/séquence).
- Pas de rechargement, transitions fluides.
- Une seule URL à retenir (`http://localhost:5000/`).

### 11.4 Rendu PDF par compilation locale

Pas de service distant ni de moteur web (pas de KaTeX, pas de
MathJax). Justifications :

- Fidélité avec le rendu final imprimé (le PDF est l'unique cible).
- Possibilité d'utiliser des packages LaTeX spécifiques
  (`tabularray`, `tikz`, `xint`).
- Cohérence avec la chaîne de production des livrets.

### 11.5 Auto-import des CSV référentiels au démarrage

Si la BDD est vide pour un cycle, les CSV `C0X_themes.csv` et
`C0X_sequences.csv` du dossier `referentiels/` sont importés
automatiquement. Permet de versionner les référentiels via git
sans toucher à la BDD.

---

## 12. Pour approfondir

| Sujet | Référence |
|---|---|
| Vision pédagogique, règles métier détaillées | `seqenseigne_cdc_v0_10_7.md` |
| Parcours utilisateur | `seqenseigne_usecases_v0_10_7.md` |
| Note de patch v0.10.7 | `patch_v0_10_7.md` |
| Versions historiques | `redemarrage_v010.md`, `seqenseigne_doc_v0.6.3e.md` |
| Schéma SQL complet | `appli/persistence/schema.sql` |
| Tests d'exemple | `appli/tests/test_v0_10_7_*.py` |
