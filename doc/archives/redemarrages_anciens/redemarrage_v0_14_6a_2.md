# Redémarrage v0.14.6.a.2 — Hotfix schéma `objectif_exos`

## Diagnostic

Après le hotfix v0.14.6.a.1 (Windows UTF-8), le dry-run chez Laurent
sur la vraie BDD a remonté un crash SQL :

```
sqlite3.OperationalError: no such column: num
```

À la ligne :

```python
rows_v2 = conn.execute(
    "SELECT objectif_id, serie, num, exercice_id FROM objectif_exos"
).fetchall()
```

## Cause racine

Le schéma de `objectif_exos` que je supposais (basé sur
`scripts/peuplement_12_migrer_schema_sequences.py`) :

```sql
CREATE TABLE objectif_exos (
    objectif_id    TEXT NOT NULL,
    serie          TEXT NOT NULL,
    num            INTEGER NOT NULL,   -- ←  cette colonne
    exercice_id    TEXT NOT NULL,
    ordre          INTEGER DEFAULT 0,
    PRIMARY KEY (objectif_id, serie, num),
    UNIQUE       (objectif_id, serie, exercice_id)
);
```

Mais la vraie BDD a un schéma post-migration (R4e4, dans
`persistence/sqlite_store.py` lignes 240-274) :

```sql
CREATE TABLE objectif_exos (
    objectif_id    TEXT NOT NULL,
    serie          TEXT NOT NULL,
    exercice_id    TEXT NOT NULL,
    ordre          INTEGER NOT NULL DEFAULT 0,    -- ← devient la "numérotation"
    origin_niveau  TEXT,
    origin_seq     TEXT,
    origin_serie   TEXT,
    origin_num     INTEGER,                        -- ← ancien num conservé pour info
    PRIMARY KEY (objectif_id, serie, exercice_id), -- ← PK différente
    UNIQUE       (objectif_id, serie, ordre)
);
```

La migration applicative est faite au démarrage de l'app si la
colonne `num` existe encore. Donc dès le premier lancement de Flask,
la BDD est dans le schéma cible. Les scripts de peuplement étaient
documentation historique, pas reflet de la prod.

**Conséquence** : mes tests v0.14.6.a définissaient l'ancien schéma
(avec `num`), donc validaient le script contre un schéma qui n'existe
plus en prod. Tests verts mais code cassé sur la vraie base. Faute de
ne pas avoir vérifié le schéma réel dans `persistence/sqlite_store.py`.

## Correctif

### 1. Script de migration aligné sur le schéma de prod

`scripts/migrer_v1_vers_v2.py` :

- **`_planifier_migration_liaisons`** : `SELECT ... num` → `SELECT ... ordre`,
  variable `nums_par_obj_serie` → `ordres_par_obj_serie`
- **`_appliquer_migration_liaisons`** : `MAX(num)` → `MAX(ordre)`,
  `INSERT (... num ... ordre)` → `INSERT (objectif_id, serie, exercice_id, ordre)`
- **Affichage** : `f"{serie}{num}"` → `f"{serie}#{ordre}"`
- **Plan dict** : clé `"num"` → clé `"ordre"`

### 2. Schéma de test aligné

`tests/test_v0_14_6a_migration_v1_vers_v2.py` :

```python
CREATE TABLE objectif_exos (
    objectif_id TEXT REFERENCES objectifs_v2(id) ON DELETE CASCADE,
    serie TEXT NOT NULL,
    exercice_id TEXT REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre INTEGER NOT NULL DEFAULT 0,
    origin_niveau TEXT,
    origin_seq TEXT,
    origin_serie TEXT,
    origin_num INTEGER,
    PRIMARY KEY (objectif_id, serie, exercice_id),
    UNIQUE (objectif_id, serie, ordre)
);
```

Test `test_liaison_a_la_bonne_serie` : `SELECT serie, num` →
`SELECT serie, ordre`.
Snapshot dry-run : `ORDER BY ... serie, num` → `ORDER BY ... serie, ordre`.

### 3. Test d'intégration réel (de mon côté)

J'ai créé une BDD synthétique avec le schéma **réel** de prod (post-R4e4)
puis exécuté la séquence complète dry-run → écriture → audit. Verdict
final : **✓ Aucun obstacle**, exit 0. Validé.

## Validation

### Tests automatiques

```
$ python -m pytest tests/test_v0_14_5_audit_v1_v2.py \
                   tests/test_v0_14_6a_migration_v1_vers_v2.py -q
40 passed in 2.66s
```

### Suite complète

```
$ python -m pytest -q
3536 passed, 5 skipped, 0 failed
```

### Validation manuelle sur schéma de prod

Mini-BDD reproduisant ton schéma : 4 objectifs v1 dont 1 orphelin,
3 objectifs v2 avec divergences, 2 liaisons `exercice_objectifs`,
1 liaison `objectif_exos` initiale (schéma sans `num`).

```
$ python scripts/migrer_v1_vers_v2.py --ecrire
  ✓ 1 objectifs créés
  ✓ 3 objectifs mis à jour
  ✓ 1 parties créées
  ✓ 1 liaisons exercice→objectif créées

$ python scripts/audit_v1_v2.py
  ✓ Aucun obstacle détecté.
```

## Fichiers livrés

```
MODIFIÉS (correctifs schéma)
  appli/scripts/migrer_v1_vers_v2.py                 (~30 lignes modifiées)
  appli/tests/test_v0_14_6a_migration_v1_vers_v2.py  (schéma + 2 tests adaptés)

NOUVEAUX
  appli/doc/redemarrage_v0_14_6a_2.md                (ce document)
```

Pas de nouveau test. Les 19 tests existants couvrent maintenant le
schéma cible (alignement avec la prod).

## À faire chez toi

### 1. Relancer les tests

```
cd appli
python -m pytest tests/test_v0_14_6a_migration_v1_vers_v2.py -v
```

Attendu : 19 passed.

### 2. Reprendre le dry-run sur ta vraie BDD

```
python -m scripts.migrer_v1_vers_v2
```

Cette fois doit afficher le rapport complet :

```
v1 (objectifs)   : 245 entrées
v2 (objectifs_v2): 213 entrées

──────────────────────────────────────────────────────────────────────
  Objectifs à CRÉER en v2 — 32
──────────────────────────────────────────────────────────────────────
  + ('N10', 'S14', '03')  partie=1 (partie existe)  nom='Mettre en ordre...'
  …

──────────────────────────────────────────────────────────────────────
  Objectifs v2 à METTRE À JOUR — 156
──────────────────────────────────────────────────────────────────────
  Synthèse par champ :
    methode_id: 156 mises à jour
    critere_A:  153 mises à jour
    critere_E:  154 mises à jour
    critere_F:   99 mises à jour
  …

──────────────────────────────────────────────────────────────────────
  Liaisons exercice→objectif à créer en v2 — 2
──────────────────────────────────────────────────────────────────────
  …

  ⚠ N avertissement(s) (non-bloquants)
  (les 2 liaisons vers objectifs orphelins, traitées après création v2)

──────────────────────────────────────────────────────────────────────
  DRY-RUN — aucune écriture effectuée
──────────────────────────────────────────────────────────────────────
```

M'envoyer la sortie complète.

### 3. Si tout est cohérent → écriture

```
python -m scripts.migrer_v1_vers_v2 --ecrire
```

Avec backup auto.

### 4. Re-audit

```
python -m scripts.audit_v1_v2
```

Doit afficher **« ✓ Aucun obstacle détecté »**.

## Note de dette technique

J'aurais dû vérifier le schéma de prod dans `persistence/sqlite_store.py`
avant d'écrire le script de migration. Le `peuplement_12` est une
documentation historique du schéma initial, pas le schéma actuel.

**Règle pour la suite** : pour tout script qui touche au schéma SQL,
vérifier **d'abord** `persistence/sqlite_store.py` (qui contient les
migrations applicatives faites au démarrage de Flask), puis seulement
les scripts de peuplement.
