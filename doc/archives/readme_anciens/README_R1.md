# seqenseigne v0.6.3f — R1 : Structure du cycle

Chantier R1 du CdC v0.8 : création des tables `cycles`, `themes` et
`sequences_du_cycle`, avec import initial depuis les CSV legacy.

**Status** : 46 nouveaux tests, 547 verts au total, 0 régression.

## Périmètre

**Inclus** :
- 3 nouvelles tables en base : `cycles`, `themes`, `sequences_du_cycle`
- Script de migration idempotent `peuplement_11_migrer_schema_cycle.py`
- Service d'import CSV : `services/cycle_import.py`
- Routes Flask : `/api/cycles`, `/api/cycles/<code>/themes`,
  `/api/cycles/<code>/sequences`, `/api/admin/cycle/importer`
- Générateurs d'IDs : `nouveau_id_theme()`, `nouveau_id_sequence_du_cycle()`

**Non inclus** (à venir dans chantiers suivants) :
- UI CRUD des thèmes (→ R2)
- UI CRUD des séquences du cycle (→ R3)
- Suppression des tables `referentiel_themes` / `referentiel_sequences`
  (→ R4, refonte complète)
- Adaptation des objectifs pour pointer sur `sequences_du_cycle` (→ R4)

## Fichiers livrés

| Fichier | Rôle |
|---|---|
| `appli/persistence/schema.sql` | Ajout des 3 tables en tête |
| `appli/persistence/ids.py` | +2 générateurs d'IDs (`th_xxx`, `sc_xxx`) |
| `appli/scripts/peuplement_11_migrer_schema_cycle.py` | Migration idempotente |
| `appli/services/cycle_import.py` | Import CSV + lecteurs |
| `appli/routes/cycle.py` | Blueprint Flask |
| `appli/tests/test_R1_schema.py` | 17 tests |
| `appli/tests/test_R1_cycle_import.py` | 19 tests |
| `appli/tests/test_R1_routes.py` | 10 tests |

## Déploiement

### 1. Migrer le schéma

Sur la base existante chez toi :

```powershell
cd D:\Enseignement\seqenseigne\appli
..\outils\python\python.exe scripts\peuplement_11_migrer_schema_cycle.py
```

Sortie attendue :
```
Migration R1 — terminée
Tables créées : cycles, sequences_du_cycle, themes
Tables cible présentes : cycles, sequences_du_cycle, themes
```

### 2. Enregistrer le blueprint dans `app.py`

Ajouter à la liste des imports de routes (vers la ligne 30) :

```python
from routes.cycle             import bp_cycle
```

Ajouter `bp_cycle` à la liste d'enregistrement dans `create_app` :

```python
    for bp in (bp_sequences, bp_classes, bp_suivi, bp_versions,
               bp_atomes, bp_param, bp_scanner, bp_admin, bp_progression,
               bp_etablissements, bp_calendrier,
               bp_annees_scolaires, bp_referentiels,
               bp_cycle):                             # ← ajouté
        app.register_blueprint(bp)
```

### 3. Importer le cycle C04

```powershell
# Vérifier que les CSV sont en place
dir data\C04_themes.csv
dir data\C04_sequences.csv

# Lancer Flask, puis (dans un terminal séparé, ou via un petit outil) :
curl -X POST http://localhost:5000/api/admin/cycle/importer `
     -H "Content-Type: application/json" `
     -d '{"cycle_code": "C04"}'
```

Réponse attendue :
```json
{
  "ok": true,
  "rapport": {
    "cycle":    {"code": "C04", "cree": true, "maj": false},
    "themes":   {"crees": 5, "mis_a_jour": 0},
    "sequences":{"crees": 14, "mis_a_jour": 0},
    "avertissements": []
  }
}
```

### 4. Vérifier

```powershell
..\outils\python\python.exe -m pytest tests -q
```

Attendu : **547 verts**.

Puis :
```powershell
curl http://localhost:5000/api/cycles
curl http://localhost:5000/api/cycles/C04/themes
curl http://localhost:5000/api/cycles/C04/sequences
```

## Endpoints

### `POST /api/admin/cycle/importer`

Import d'un cycle (thèmes + séquences) depuis des CSV legacy.
Idempotent.

Corps :
```json
{
  "cycle_code":       "C04",                        // obligatoire
  "cycle_nom":        "Cycle 4",                    // optionnel
  "description":      "",                           // optionnel
  "chemin_themes":    "C04_themes.csv",             // optionnel, défaut: data/<code>_themes.csv
  "chemin_sequences": "C04_sequences.csv"           // optionnel, défaut: data/<code>_sequences.csv
}
```

Erreurs possibles :
- `400 champ_manquant` : `cycle_code` absent
- `400 themes_absent` / `sequences_absent` : CSV introuvable
- `400 themes_colonnes` / `sequences_colonnes` : colonnes CSV manquantes

### `GET /api/cycles`

Liste tous les cycles.

```json
{"cycles": [{"code": "C04", "nom": "Cycle 4", "description": ""}]}
```

### `GET /api/cycles/<code>/themes`

Thèmes du cycle, triés par ordre.

### `GET /api/cycles/<code>/sequences`

Séquences du cycle, triées par numéro, avec code et nom du thème joint.

## Notes techniques

### Contraintes d'unicité

- `cycles.code` : PK
- `themes` : `UNIQUE (cycle_code, nom)` et `UNIQUE (cycle_code, code)`
  → le même code de thème peut exister dans deux cycles différents
- `sequences_du_cycle` : `UNIQUE (cycle_code, code)` et
  `UNIQUE (cycle_code, numero)`

### Cascades FK

- `themes.cycle_code → cycles.code` : `ON DELETE CASCADE`
  (supprimer un cycle supprime ses thèmes)
- `sequences_du_cycle.cycle_code → cycles.code` : `ON DELETE CASCADE`
- `sequences_du_cycle.theme_id → themes.id` : `ON DELETE SET NULL`
  (supprimer un thème rend ses séquences orphelines, ne les supprime pas)

### Coexistence avec `referentiel_themes` / `referentiel_sequences`

Ces anciennes tables restent en place après R1. Elles seront
supprimées au chantier R4 qui restructurera les objectifs et leurs
rattachements.

## Prochaine étape : R2 — Atelier Thème

CRUD UI + API pour gérer les thèmes du cycle (ajout, modification,
suppression, couleur, description).
