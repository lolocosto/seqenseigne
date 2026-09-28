# seqenseigne — R4b : Peuplement v2 depuis la base

Deuxième sous-chantier de R4. Peuple les 5 tables du modèle
séquences-par-niveau (créées en R4a) à partir des données déjà en base
enrichies en C1, et des plans de travail LaTeX pour le découpage en
parties.

**Status** : 27 nouveaux tests (22 service + 5 routes), 702 verts au total, 0 régression.

## Périmètre

**Inclus** :
- Service `services/scanner_vers_v2.py` qui orchestre le peuplement
- Script CLI `scripts/peuplement_13_v2_depuis_base.py`
- 2 endpoints admin :
  - `POST /api/admin/v2/peupler` — lance le peuplement (niveaux configurables)
  - `GET /api/admin/v2/statistiques` — compteurs de l'état v2

**Sources des données** :
1. `objectifs` (legacy) → `objectifs_v2` (nom, critères, méthode, id conservé)
2. `livret_exercices` → `objectif_exos` (avec conversion `fondamental`→`F`, etc.)
3. `N1X_Plan_de_travail.tex` → découpage en `sequence_parties`
4. `N1XSyy_param.tex` → colonne `sequences_par_niveau.parametres`

**Idempotent** : peut être relancé autant de fois que nécessaire. Chaque
exécution purge ce qui a été peuplé pour le niveau traité avant de
repeupler proprement.

**Pas de modification des tables legacy** : `objectifs`, `livrets_de_sequence`,
`livret_exercices`, `livret_revisions`, `exercice_objectifs` restent
intactes. L'UI continue de fonctionner sur le modèle legacy.

## Fichiers livrés

| Fichier | Rôle |
|---|---|
| `appli/services/scanner_vers_v2.py` | Service de peuplement |
| `appli/routes/peuplement_v2.py` | Blueprint Flask |
| `appli/scripts/peuplement_13_v2_depuis_base.py` | Script CLI |
| `appli/tests/test_R4b_scanner_vers_v2.py` | 22 tests service |
| `appli/tests/test_R4b_routes.py` | 5 tests routes |

## Conversion des séries

Les tables legacy utilisent des noms longs, la v2 utilise des codes
courts (définis dans le CdC v0.8) :

| Legacy | v2 | Sens |
|---|---|---|
| `fondamental` | `F` | Fondamental |
| `avancé` | `A` | Approfondissement |
| `exploration` | `E` | Expertise |
| `approche` | `EA` | Entrée-activité |
| `révision` | `R` | Révisions (exos hérités du niveau N-1) |

## Déploiement

### 1. Extraire le ZIP dans `appli/`

### 2. Enregistrer le blueprint dans `app.py`

Ajouter l'import (après `bp_sequences_du_cycle`) :

```python
from routes.peuplement_v2     import bp_peuplement_v2
```

Ajouter à la liste d'enregistrement :

```python
    for bp in (bp_sequences, bp_classes, bp_suivi, bp_versions,
               bp_atomes, bp_param, bp_scanner, bp_admin, bp_progression,
               bp_etablissements, bp_calendrier,
               bp_annees_scolaires, bp_referentiels, bp_cycle,
               bp_themes, bp_sequences_du_cycle,
               bp_peuplement_v2):                         # ← ajouté
        app.register_blueprint(bp)
```

### 3. Lancer le peuplement sur la base existante

**Option A — depuis le script CLI** (recommandée pour un premier run) :

```powershell
cd D:\Enseignement\seqenseigne\appli
..\outils\python\python.exe scripts\peuplement_13_v2_depuis_base.py `
    --plans-dir D:\Enseignement\seqenseigne\reference\sequences `
    --niveaux N10,N11,N12
```

Sortie attendue (ordre de grandeur) :
```
Totaux :
  sequences_par_niveau créées : 42
  parties créées              : 42
  objectifs_v2 créés          : 245
  objectif_exos créés         : 731
```

Le détail par niveau est affiché en dessous. Les éventuels exercices
non trouvés sont listés — ce sont des incohérences entre les plans de
travail et la base, que tu pourras corriger plus tard.

**Option B — depuis l'appli via curl** :

```powershell
curl.exe -X POST http://localhost:5000/api/admin/v2/peupler `
  -H "Content-Type: application/json" `
  -d '{\"niveaux\":[\"N10\",\"N11\",\"N12\"],\"plans_dir\":\"D:/Enseignement/seqenseigne/reference/sequences\"}'
```

### 4. Vérifier

```powershell
..\outils\python\python.exe -m pytest tests -q
# Attendu : 702 verts

curl.exe http://localhost:5000/api/admin/v2/statistiques
```

L'appli doit continuer à fonctionner exactement comme avant côté UI.
Rien n'est changé visuellement — seules les tables v2 sont maintenant
peuplées et prêtes pour R4c/d/e.

## Cas particuliers gérés

### Sans plan de travail disponible

Si `--plans-dir` n'est pas fourni ou ne contient pas le
`Nxx_Plan_de_travail.tex`, une **partie unique numéro 1** est créée
par séquence, contenant tous ses objectifs. Tu pourras redécouper
plus tard depuis l'UI R4e.

### Séquences sans objectifs mais avec livret

Une séquence qui a un livret mais pas encore d'objectifs reçoit
une `sequences_par_niveau` + une partie vide. C'est cohérent :
la structure est posée, prête à recevoir des objectifs.

### IDs des objectifs conservés

Les `objectifs_v2.id` reprennent les `objectifs.id` legacy. Cela
simplifie les éventuelles requêtes croisées et garantit qu'aucun
consommateur externe (dashboard, export, etc.) ne sera surpris par
un changement d'id silencieux.

## Limites connues

- Les **révisions** (série `R`, exos hérités de N-1) ne sont pas
  encore peuplées. `livret_revisions` n'a pas de lien avec un objectif
  précis, donc on ne peut pas déduire à quel objectif_v2 les attacher.
  À traiter en R4e quand l'UI permettra de gérer explicitement les
  précédences au niveau **partie** (plus adapté que par objectif).

- Les **précédences** de partie (`partie_precedences`) ne sont pas
  non plus peuplées : l'info des blocs du plan contient des numéros
  d'exercices, pas des `(niveau, seq)` source. À traiter en R4e.

Ces deux points ne bloquent pas la suite. L'UI R4e pourra éditer ces
relations directement.

## Prochaine étape : R4c

Renommage `creneaux.rang_debut` / `rang_fin` → `partie_debut` / `partie_fin`.
Un chantier rapide et localisé pour aligner le vocabulaire sur le
nouveau modèle.
