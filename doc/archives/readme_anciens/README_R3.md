# seqenseigne — R3 : Atelier Séquence (cycle)

Chantier R3 du CdC v0.8 : CRUD complet des séquences du cycle via l'UI.

**Status** : 53 nouveaux tests (36 service + 17 routes), 649 verts au total, 0 régression.

## Périmètre

**Inclus** :
- Service CRUD `services/sequences_du_cycle.py` avec 6 exceptions métier
- 5 endpoints REST dans `routes/sequences_du_cycle.py` :
  - `GET /api/cycles/<code>/sequences/detail` — liste enrichie (thème + compteurs atomes)
  - `POST /api/cycles/<code>/sequences` — créer
  - `GET /api/sequences_du_cycle/<id>` — lire
  - `PUT|PATCH /api/sequences_du_cycle/<id>` — modifier
  - `DELETE /api/sequences_du_cycle/<id>` — supprimer (409 si atomes rattachés)
- UI : atelier « Séquence (cycle) » avec liste triée par numéro, pastilles colorées par thème, formulaire avec rattachement de thème

**Validations côté service** :
- Code obligatoire, unique dans le cycle
- Numéro obligatoire, entier positif, unique dans le cycle
- Nom obligatoire
- Thème optionnel ; s'il est fourni, doit exister dans le même cycle
- Suppression refusée si des atomes vivants (objectifs, méthodes, notions, exercices) référencent la séquence via leur colonne `sequence`

## Fichiers livrés

| Fichier | Rôle |
|---|---|
| `appli/services/sequences_du_cycle.py` | Service CRUD |
| `appli/routes/sequences_du_cycle.py` | Blueprint Flask |
| `appli/static/ateliers_seqcycle.js` | JS vanilla |
| `appli/templates/_atelier_seqcycle_fragment.html` | HTML à intégrer |
| `appli/static/_patch_app_js.txt` | Patch de `atelSwitch` |
| `appli/tests/test_R3_sequences_service.py` | 36 tests |
| `appli/tests/test_R3_sequences_routes.py` | 17 tests |

## Déploiement

### 1. Déposer les fichiers

Extraire le ZIP dans `appli/`.

### 2. Enregistrer le blueprint dans `app.py`

Ajouter l'import (après `bp_themes`) :

```python
from routes.sequences_du_cycle import bp_sequences_du_cycle
```

Ajouter à la liste d'enregistrement :

```python
    for bp in (bp_sequences, bp_classes, bp_suivi, bp_versions,
               bp_atomes, bp_param, bp_scanner, bp_admin, bp_progression,
               bp_etablissements, bp_calendrier,
               bp_annees_scolaires, bp_referentiels, bp_cycle,
               bp_themes, bp_sequences_du_cycle):          # ← ajouté
        app.register_blueprint(bp)
```

### 3. Patcher `index.html`

**3a. Bouton dans la sous-navigation** (après le bouton « Thème » ajouté en R2) :

```html
    <button class="vbtn" id="atl-btn-seqcycle" onclick="atelSwitch('seqcycle')">Séquence (cycle)</button>
```

**3b. Panneau** : copier le contenu de `templates/_atelier_seqcycle_fragment.html`
(le bloc `<div id="atl-seqcycle" ...>`) et le coller avant le `</main>` de `tab-ateliers`.

**3c. Script** avant `</body>` :

```html
<script src="/static/ateliers_seqcycle.js"></script>
```

### 4. Patcher `atelSwitch` dans `static/app.js`

Remplacer la fonction (modifiée en R2) par celle du fichier
`_patch_app_js.txt` qui ajoute `'seqcycle'` à la liste :

```javascript
function atelSwitch(panel) {
  ['exercice','notion','methode','livret','theme','seqcycle'].forEach(p => {
    document.getElementById('atl-'+p).style.display = p===panel ? '' : 'none';
    document.getElementById('atl-btn-'+p).classList.toggle('active', p===panel);
  });
  if (panel === 'livret')      initLivret();
  if (panel === 'progression') progInit();
  if (panel === 'theme'    && typeof atelThemeInit    === 'function') atelThemeInit();
  if (panel === 'seqcycle' && typeof atelSeqCycleInit === 'function') atelSeqCycleInit();
}
```

### 5. Vérifier

```powershell
..\outils\python\python.exe -m pytest tests -q
```

Attendu : **649 tests verts**.

Puis ouvrir l'appli, aller dans Ateliers → Séquence (cycle). Les 14 séquences
importées en R1 doivent s'afficher triées par numéro, avec une pastille de
couleur pour chaque thème rattaché.

## Endpoints détaillés

### `GET /api/cycles/<code>/sequences/detail`

Liste enrichie : chaque séquence inclut son thème (code, nom, couleur) et
les compteurs d'atomes.

```json
{
  "sequences": [
    {
      "id": "sc_xxx", "cycle_code": "C04",
      "code": "S01", "numero": 1, "nom": "Représentations d'un nombre",
      "theme_id": "th_A", "theme_code": "A", "theme_nom": "Nombres",
      "theme_couleur": "nombres",
      "atomes": {"objectifs": 14, "methodes": 12, "notions": 10, "exercices": 42},
      "nb_atomes_total": 78
    }
  ]
}
```

### `POST /api/cycles/<code>/sequences`

```json
{
  "code": "S15",           // obligatoire, unique dans le cycle
  "numero": 15,            // obligatoire, entier positif, unique
  "nom": "Nouvelle",       // obligatoire
  "theme_id": "th_xxx"     // optionnel, doit exister dans le cycle
}
```

Erreurs :
- `400 code_vide`, `numero_vide`, `numero_invalide`, `nom_vide`
- `400 theme_invalide` si `theme_id` inconnu ou dans un autre cycle
- `404 cycle_introuvable`
- `409 doublon_code`, `doublon_numero`

### `PUT|PATCH /api/sequences_du_cycle/<id>`

Mise à jour partielle. Les champs `None` (absents du JSON) sont ignorés.

Pour **détacher un thème** (mettre à NULL), passer explicitement `detacher_theme: true` :

```json
{"detacher_theme": true}
```

(Le JS gère automatiquement ce cas quand l'utilisateur sélectionne
« Aucun thème » sur une séquence qui en avait un.)

### `DELETE /api/sequences_du_cycle/<id>`

- `404 sequence_introuvable` si id inconnu
- `409 en_usage` avec un champ `details` donnant le nombre d'atomes par type :

```json
{
  "error": "...",
  "code": "en_usage",
  "details": {"objectifs": 14, "methodes": 12, "notions": 10, "exercices": 42}
}
```

## Notes techniques

### Détection des atomes rattachés

Le service compte les lignes dans `objectifs`, `methodes`, `notions` et
`exercices` dont la colonne texte `sequence` vaut le `code` de la séquence
à supprimer (ignorant le niveau : une séquence du cycle est partagée par
tous les niveaux).

Cette logique sera affinée au chantier R4 lorsque les atomes pointeront
sur `sequences_par_niveau.id` via une vraie FK.

### Gestion multi-cycles

L'UI propose automatiquement un sélecteur de cycle en haut de la sidebar.
Si un seul cycle existe (cas courant : C04 seul), le sélecteur n'a qu'une
option et peut être considéré comme fonctionnellement invisible.

Pour créer un nouveau cycle (ex: C03), passer par
`POST /api/admin/cycle/importer` avec des CSV legacy — pas de UI CRUD
dédiée à ce stade (roadmap R9 dans le CdC).

## Prochaine étape : R4 — Refonte `sequences_par_niveau` et parties

Gros chantier : suppression de la table `livrets_de_sequence`, création
de `sequences_par_niveau` + `sequence_parties` + `objectif_exos`,
renommage `creneaux.rang_*` → `partie_*`, adaptation des scanners.
