# seqenseigne v0.6.2d — référentiel correct pour chaque classe historique

Corrige le bug "Romane voit des objectifs 11/12/13 qui n'existaient pas en
2021-2022". Les classes importées d'années antérieures affichaient les
objectifs du référentiel **actuel** (N11_v2025) au lieu de celui **d'époque**
(N11_v2021).

## Le bug

Lors de l'import d'une arborescence, plusieurs classes peuvent partager la
même progression pédagogique (ex : 4e3, 4e4 et 4e6 de 2021-2022 au même
collège partagent `pg_09456183` avec `referentiel_id = N11_v2021`).

Dans le flow d'import, chaque classe générait localement un nouvel UUID de
progression. `ecrire_progression` est un upsert par clé métier
`(niveau, annee, etablissement)` : la 1re classe créait la progression avec
son id `pg_X`, la 2e classe générait `pg_Y` mais `ecrire_progression`
détectait l'existante et réutilisait `pg_X`. **Mais** la classe avait été
construite avec `progression_id = pg_Y`, qui ne correspondait plus à rien.
À l'écriture de la classe en base, la contrainte de clé étrangère mettait
`progression_id = NULL`.

Conséquence pour la route `/api/classes/<cid>/sequences` :
- `classe.progression_id` = NULL
- Donc pas de lecture de la progression
- Donc pas de `referentiel_id`
- **Fallback sur le YAML courant** = référentiel N11_v2025 = objectifs 01-04
  et 11-13 (renumérotés récemment)

D'où les `I` sur objectifs 12 et 13 de Romane qui n'a évidemment jamais été
évaluée sur des objectifs qui n'existaient pas à son époque.

## Les corrections

### 1. `importer_arborescence.py` : synchroniser `progression_id` post-upsert

```python
store.ecrire_progression(prog)
# ecrire_progression peut remplacer prog["id"] par l'id de la progression
# existante en base (upsert par clé métier). Il faut resynchroniser :
classe["progression_id"] = prog["id"]
```

### 2. `routes/classes.py` : fallback par clé métier

La route devient robuste au cas où `classe.progression_id` est NULL en
base : elle retrouve la progression via `lire_progression(niveau, annee,
etablissement)` au lieu de tomber directement sur le YAML courant.

### 3. `reparer_progression_id.py` : outil de réparation ponctuel

Pour ne pas forcer Laurent à tout ré-importer, ce petit script met à jour
les `progression_id` manquants dans la base existante.

Testé sur la base de Laurent : 10 classes orphelines réparées sur 10.

### 4. Nouveau test : `test_progression_id_synchronise_entre_classes_memes_cle_metier`

Attrape la régression : vérifie qu'après import de 3 classes partageant
(niveau, annee, etab), les 3 pointent bien vers la même progression non
NULL.

## Validation Playwright

**Classe 4e6 de 2021-2022, séquence S03 :**
- Objectifs affichés : `obj.01, 02, 03, 04, 05, 06` ✅ (plus de 11/12/13)
- Romane Chaillou : `E / A / A / A / A / A` → note 16.7/20 ✅
- Moyenne classe : 12.4/20, distribution I=5 F=74 A=40 E=10

## Déploiement

```powershell
# 1. Copier les 3 fichiers modifiés
#    - appli\importer_arborescence.py
#    - appli\routes\classes.py
#    - appli\reparer_progression_id.py  (nouveau, à la racine de appli\)

# 2. Réparer la base existante (sans ré-import)
cd D:\Enseignement\seqenseigne\appli
python reparer_progression_id.py

# 3. Redémarrer Flask
#    Ctrl+C dans le terminal, puis relance

# 4. Rafraîchir le navigateur : Ctrl+F5

# 5. Vérifier : classe 4e6 2021-2022 → séquence S03 → Romane
#    Objectifs affichés : 01, 02, 03, 04, 05, 06 (pas 11/12/13)
#    Romane : E / A / A / A / A / A
```

Si tu préfères un ré-import propre :

```powershell
del data\seqenseigne.db
python importer_arborescence.py --racine D:\Enseignement_old
```

Avec le fix, toutes les classes auront directement le bon `progression_id`.

## Fichiers

```
appli/importer_arborescence.py        ← fix synchronisation progression_id
appli/routes/classes.py               ← fallback par clé métier
appli/reparer_progression_id.py       ← NOUVEAU : script de réparation
appli/tests/test_import_arborescence.py  ← nouveau test de non-régression
```

## Tests

326 tests verts (325 de la v0.6.2 + 1 nouveau).
