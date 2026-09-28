# Redémarrage seqenseigne — v0.13.0 (chantier 1/3 série v0.13)

## Synthèse

**Création de la table BDD `param_niveaux`** + amorçage automatique
depuis `data/param_niveaux.csv` au premier démarrage.

C'est la première étape de la série v0.13 « Référentiel de niveau ».
Cette livraison est **purement infrastructurelle** : elle crée la table
et la peuple, mais aucun service ne la consulte encore. La consommation
arrivera en v0.13.1, qui remplacera les tables hardcodées
`_NOM_COURT_NIVEAU` (livret_sequence.py) et `_CYCLE_PAR_NIVEAU`
(livret_sequence.py + livret_plans_de_travail.py) par des lectures BDD.

## Pourquoi c'est nécessaire

L'application a aujourd'hui **5 sources de vérité** pour le mapping
niveau → cycle / nom :

1. `data/param_niveaux.csv` — la « vraie » source (6 lignes)
2. `data/param_niveaux.dbtex` — copie LaTeX pour le paquet (autonomie
   compilateur)
3. `_NOM_COURT_NIVEAU` (hardcoded dans `livret_sequence.py`)
4. `_CYCLE_PAR_NIVEAU` (dupliqué dans `livret_sequence.py` ET
   `livret_plans_de_travail.py`)
5. `lire_param_niveaux()` dans `CsvStore` (lecture du CSV pour
   `resoudre_macros.py`)

Ces 5 sources doivent rester alignées sous peine de divergences
silencieuses. La v0.13.0 commence à remédier en plaçant la **BDD
comme source de vérité** côté Python (les sources LaTeX restent
indépendantes pour l'autonomie du paquet).

## Modèle de données

Nouvelle table `param_niveaux` :

```sql
CREATE TABLE IF NOT EXISTS param_niveaux (
    code              TEXT PRIMARY KEY,
    cycle_code        TEXT NOT NULL REFERENCES cycles(code) ON DELETE RESTRICT,
    annee_dans_cycle  TEXT NOT NULL,         -- 'anneeun', 'anneedeux', 'anneetrois'
    nom_court         TEXT NOT NULL,         -- '5ème', '4ème', '3ème'…
    nom_long          TEXT NOT NULL DEFAULT '',  -- 'cinquième', 'quatrième'…
    ordre             INTEGER NOT NULL DEFAULT 0  -- 1..N pour tri global
);
CREATE INDEX IF NOT EXISTS idx_param_niveaux_cycle
    ON param_niveaux (cycle_code, ordre);
```

Choix structurants :

- **`code` en PRIMARY KEY** : référence stable par les autres tables
  (compatible avec l'usage existant qui utilise `'N10'`, `'N11'`…).
- **FK vers `cycles(code)` en RESTRICT** : on ne peut pas supprimer un
  cycle s'il a des niveaux (intégrité référentielle).
- **`ordre` dérivé de la position dans le CSV** : `N07=1, N08=2, …, N12=6`.
  Permet un tri global utile pour les UI (sélecteurs de niveau).
- **`annee_dans_cycle` reste textuelle** (`anneeun`/`deux`/`trois`)
  pour rester aligné sur les macros LaTeX existantes (qui consomment
  cette valeur). Pourrait être numérique mais le coût de l'aligner
  partout est inutile.
- **Nom de table `param_niveaux`** (calqué sur le CSV) plutôt que
  `niveaux_referentiel` ou `niveaux_scolaires`. C'est cohérent avec
  la dénomination des autres CSV de référence.

**Important** : la table existante `niveaux` (sans suffixe) est en
fait une table de tracking d'élèves (`classe_id`, `eleve_id`,
`niveau_code`). Elle n'a rien à voir avec le référentiel des niveaux
scolaires. Le nom `param_niveaux` permet d'éviter la confusion.

## Mécanique de peuplement

### À l'init du store

`SqliteStore.__init__` enchaîne maintenant :

1. Migrations pré-DDL (colonnes manquantes)
2. DDL principal (`CREATE TABLE IF NOT EXISTS param_niveaux …`)
3. Migrations post-DDL (ALTER TABLE pour colonnes ajoutées en cours
   de route, ex. `nb_seances` v0.12.0)
4. **Peuplement initial v0.13.0** : `_peupler_param_niveaux_si_vide`

### Algorithme de peuplement

```
Si COUNT(param_niveaux) > 0 :
    NE RIEN FAIRE (BDD est maître après amorçage)
Sinon si data/param_niveaux.csv n'existe pas :
    NE RIEN FAIRE (table reste vide, services gèreront en v0.13.1)
Sinon :
    Lire le CSV
    Pour chaque ligne valide (Code et CodeCycle non vides) :
        Préparer (code, cycle_code, annee, nom_court, nom_long, ordre)
    Pour chaque cycle_code distinct :
        INSERT OR IGNORE INTO cycles (code, nom='Cycle N', '')
        (le cycle peut déjà exister, on ne l'écrase jamais)
    INSERT INTO param_niveaux (...) — tous les niveaux d'un coup
```

L'algorithme est **idempotent** : ré-init de SqliteStore ne refait
rien tant que la table n'est pas vide.

### Robustesse

- CSV absent : table créée mais vide (pas de crash)
- CSV vide ou avec seulement le header : table vide
- CSV avec lignes mal formées (Code vide) : lignes sautées silencieusement
- CSV avec BOM UTF-8 (typique Excel) : géré via `utf-8-sig`
- Erreur SQL pendant l'INSERT : rollback propre, table reste vide,
  démarrage de l'app non bloqué

### Préservation des modifications utilisateur

- Si l'utilisateur édite la table en BDD (UPDATE, DELETE), une ré-init
  ne touche **jamais** ces modifications (la table n'est plus vide ⇒
  pas d'amorçage).
- Si l'utilisateur a personnalisé le nom d'un cycle (ex. `cycles.nom`),
  l'amorçage utilise `INSERT OR IGNORE` → ne touche pas non plus.

## Tests

**Total : 1949 tests** (vs 1931 baseline v0.12.4) → **+18 tests v0.13.0**.

Nouveau fichier `tests/test_v0_13_0_param_niveaux.py` organisé en
6 sections :

1. **TestSchema** (4 tests) : table existe, colonnes attendues, FK
   vers cycles, index `idx_param_niveaux_cycle`.
2. **TestPeuplementInitial** (3 tests) : amorçage des 6 niveaux,
   attributs corrects pour N10 et N12, ordre dérivé de la position
   CSV.
3. **TestIdempotence** (3 tests) : ré-init pas de doublons,
   modifications BDD préservées (UPDATE), suppressions BDD préservées
   (DELETE).
4. **TestRobustesse** (5 tests) : CSV absent, vide, header seul, ligne
   malformée sautée, BOM UTF-8 géré.
5. **TestCoherenceCycles** (2 tests) : cycles référencés existent en
   BDD, FK active empêche cycle inexistant.
6. **TestCsvReel** (1 test) : smoke test sur le CSV réel livré dans
   `appli/data/`.

## Fichiers touchés

```
persistence/schema.sql                     (+22 lignes : DDL param_niveaux + index)
persistence/sqlite_store.py                (+82 lignes :
                                              - appel _peupler_param_niveaux_si_vide
                                                dans _init_db
                                              - méthode complète avec gestion
                                                cycles requis + robustesse
                                                aux erreurs)
tests/test_v0_13_0_param_niveaux.py        (NOUVEAU — 18 tests, ~310 lignes)
doc/redemarrage_v0_13_0.md                 (NOUVEAU)
```

Aucune modification de service, route, ou frontend. Aucun changement
visible côté utilisateur.

## Procédure de déploiement

1. Décompresser le ZIP par-dessus la v0.12.4 actuellement déployée.
2. Relancer l'application — au démarrage, la table `param_niveaux` est
   créée et amorcée depuis `data/param_niveaux.csv`. **Idempotent** :
   relancer plusieurs fois ne fait rien de plus.
3. Aucun changement visible côté utilisateur. Pour vérifier :

```bash
sqlite3 appli/data/seqenseigne.db "SELECT * FROM param_niveaux;"
```

Doit retourner les 6 niveaux N07..N12 avec leurs cycles, années,
noms courts et longs.

## Points de validation côté Laurent

### Vérification BDD (technique)

- La table existe : `SELECT COUNT(*) FROM param_niveaux;` → 6
- Les FK sont correctes : `SELECT cycle_code FROM param_niveaux GROUP BY 1;`
  → C03 et C04 (les deux cycles existants)
- Les libellés sont corrects pour N10/N11/N12 : `SELECT * FROM
  param_niveaux WHERE cycle_code='C04' ORDER BY ordre;`

### Vérification fonctionnelle (régression)

Aucun comportement applicatif ne change. Tout doit continuer à
fonctionner comme avant :

- Atelier d'assemblage (rendu, drag-and-drop, séances, fin-de-cycle)
- Génération du livret de séquence
- Génération du livret de plans de travail (niveau et séquence)
- Récap exos / Récap cours
- Migration méthodes↔objectifs (script v0.12.4)

### Cas particulier : démarrage sur BDD vierge

Si on démarre sur une base SQLite vierge (cas tests, environnement de
dev neuf, restauration depuis backup), le premier démarrage doit :

1. Créer toutes les tables (DDL existant + nouvelle `param_niveaux`)
2. Amorcer `cycles` avec C03 et C04 si absents (via INSERT OR IGNORE)
3. Amorcer `param_niveaux` avec les 6 niveaux

Ce comportement est validé par les tests `TestSchema` et
`TestPeuplementInitial`.

## Prochaine étape

**v0.13.1** — Substitution des tables hardcodées par lectures BDD.

Au programme :
- `services/livret_sequence.py` : retrait de `_NOM_COURT_NIVEAU` et
  `_CYCLE_PAR_NIVEAU`, lecture depuis `param_niveaux`
- `services/livret_plans_de_travail.py` : retrait de
  `_CYCLE_PAR_NIVEAU` (dupliqué)
- Possibilité d'ajouter une fonction utilitaire centralisée dans un
  helper du `services/` (ex. `services.niveaux.lire_attributs_niveau()`)
- Aucun changement fonctionnel visible — juste fin de la dette technique

Ensuite **v0.13.2** — Activation des tables `referentiel_*` (versioning
millésimé), à scoper séparément.
