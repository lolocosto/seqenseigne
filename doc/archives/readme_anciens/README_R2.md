# seqenseigne — R2 : Atelier Thème

Chantier R2 du CdC v0.8 : CRUD complet des thèmes du cycle via l'UI.

**Status** : 49 nouveaux tests (28 service + 21 routes), 596 verts au
total, 0 régression.

## Périmètre

**Inclus** :
- Service CRUD `services/themes.py` avec 5 exceptions métier
- Config des familles de couleurs `services/couleurs_themes.py` (6 familles)
- 6 endpoints REST dans `routes/themes.py` :
  - `GET /api/couleurs_themes` — liste des familles pour le sélecteur
  - `GET /api/cycles/<code>/themes/detail` — thèmes + compteurs de séquences
  - `POST /api/cycles/<code>/themes` — créer
  - `GET /api/themes/<id>` — lire un thème
  - `PUT|PATCH /api/themes/<id>` — modifier
  - `DELETE /api/themes/<id>` — supprimer (409 si séquences rattachées)
- UI : nouveau panneau d'atelier Thème avec liste, formulaire et
  sélecteur de couleurs visuel (pastilles colorées)

**Validations côté service** :
- Code obligatoire, unique dans le cycle
- Nom obligatoire, unique dans le cycle
- Couleur parmi les 6 slugs connus (ou vide)
- Suppression refusée si au moins une séquence du cycle est rattachée

## Fichiers livrés

| Fichier | Rôle |
|---|---|
| `appli/services/couleurs_themes.py` | Config des 6 familles de couleurs |
| `appli/services/themes.py` | Service CRUD |
| `appli/routes/themes.py` | Blueprint Flask |
| `appli/static/ateliers_theme.js` | JS vanilla pour l'atelier |
| `appli/templates/_atelier_theme_fragment.html` | HTML à intégrer dans index.html |
| `appli/static/_patch_app_js.txt` | Patch de `atelSwitch` dans app.js |
| `appli/tests/test_R2_themes_service.py` | 28 tests service |
| `appli/tests/test_R2_themes_routes.py` | 21 tests routes |

## Déploiement

### 1. Déposer les fichiers

Extraire le ZIP dans `appli/`. Le schéma de dossiers est respecté.

### 2. Enregistrer le blueprint dans `app.py`

Ajouter à la liste des imports (vers la ligne 32, après `bp_cycle`) :

```python
from routes.themes           import bp_themes
```

Ajouter `bp_themes` à la liste d'enregistrement :

```python
    for bp in (bp_sequences, bp_classes, bp_suivi, bp_versions,
               bp_atomes, bp_param, bp_scanner, bp_admin, bp_progression,
               bp_etablissements, bp_calendrier,
               bp_annees_scolaires, bp_referentiels, bp_cycle,
               bp_themes):                              # ← ajouté
        app.register_blueprint(bp)
```

### 3. Patcher `index.html` (templates/index.html)

**3a. Bouton dans la sous-navigation** (vers la ligne 438)

Chercher la barre des boutons d'ateliers :

```html
    <button class="vbtn active" id="atl-btn-exercice" onclick="atelSwitch('exercice')">Exercice</button>
    <button class="vbtn" id="atl-btn-notion"   onclick="atelSwitch('notion')">Notion</button>
    <button class="vbtn" id="atl-btn-methode"  onclick="atelSwitch('methode')">Méthode</button>
    <button class="vbtn" id="atl-btn-livret"   onclick="atelSwitch('livret')">Livret</button>
```

Ajouter juste après la ligne « Livret » :

```html
    <button class="vbtn" id="atl-btn-theme"    onclick="atelSwitch('theme')">Thème</button>
```

**3b. Panneau de l'atelier** (avant le `</main>` de `tab-ateliers`, vers la ligne 860)

Copier le contenu de `templates/_atelier_theme_fragment.html`
(le bloc `<div id="atl-theme" ...>`) et le coller juste avant le `</main>`.

**3c. Script** (avant le `</body>` à la fin du fichier)

Ajouter :

```html
<script src="/static/ateliers_theme.js"></script>
```

### 4. Patcher `static/app.js`

Ouvrir `appli/static/app.js` et chercher la fonction `atelSwitch` (vers
la ligne 1077). La remplacer par cette nouvelle version (qui ajoute
`'theme'` à la liste et appelle `atelThemeInit()`) :

```javascript
function atelSwitch(panel) {
  ['exercice','notion','methode','livret','theme'].forEach(p => {
    document.getElementById('atl-'+p).style.display = p===panel ? '' : 'none';
    document.getElementById('atl-btn-'+p).classList.toggle('active', p===panel);
  });
  if (panel === 'livret')      initLivret();
  if (panel === 'progression') progInit();
  if (panel === 'theme' && typeof atelThemeInit === 'function') atelThemeInit();
}
```

### 5. Vérifier

```powershell
..\outils\python\python.exe -m pytest tests -q
```

Attendu : **596 tests verts**.

Puis lancer Flask, ouvrir l'appli, aller dans Ateliers → Thème :
- Les 5 thèmes importés en R1 doivent s'afficher, avec leur pastille de couleur
- Clic sur un thème → formulaire d'édition pré-rempli
- Le compteur « N seq » à droite indique le nombre de séquences rattachées

## Endpoints détaillés

### `GET /api/couleurs_themes`

Liste des familles de couleurs disponibles pour le sélecteur.

```json
{
  "familles": [
    {"slug": "nombres",       "libelle": "Rouge / Jaune",   "hex_principal": "#d92626"},
    {"slug": "donnees",       "libelle": "Bleu / Canard",   "hex_principal": "#2638d9"},
    {"slug": "grandeurs",     "libelle": "Marron / Orange", "hex_principal": "#8b4513"},
    {"slug": "geometrie",     "libelle": "Violet / Vert",   "hex_principal": "#7326a0"},
    {"slug": "algorithmique", "libelle": "Rose / Lime",     "hex_principal": "#c41e80"},
    {"slug": "noir_gris",     "libelle": "Noir / Gris",     "hex_principal": "#262626"}
  ]
}
```

### `POST /api/cycles/<code>/themes`

Créer un thème.

Corps :
```json
{
  "code": "F",
  "nom": "Nouveau thème",
  "code_couleur": "noir_gris",   // optionnel, vide par défaut
  "description": "…",             // optionnel, LaTeX libre
  "ordre": 6                      // optionnel, auto-incrémenté si absent
}
```

Erreurs :
- `400 code_vide` / `nom_vide`
- `400 couleur_invalide` si `code_couleur` inconnu
- `404 cycle_introuvable` si cycle absent
- `409 doublon_code` / `doublon_nom`

### `PUT|PATCH /api/themes/<id>`

Mise à jour partielle. Seuls les champs passés sont modifiés. Tous
les champs du POST peuvent être mis à jour (sauf `cycle_code`).

### `DELETE /api/themes/<id>`

- `404 theme_introuvable` si id inconnu
- `409 en_usage` si au moins une séquence est rattachée au thème

## Notes techniques

### Choix de stockage

- `themes.code_couleur` stocke un slug (`nombres`, `donnees`…) —
  identifiant technique compatible LaTeX
- Le libellé parlant (« Rouge / Jaune ») n'est **pas** en base : il est
  défini dans `services/couleurs_themes.py` et exposé via l'API
- **Ajouter une famille** = modifier `FAMILLES_COULEURS` dans le fichier
  de config, rien d'autre. L'appli et le sélecteur se mettent à jour
  automatiquement.

### Unicité code/nom

Au niveau du cycle uniquement. Le code « A » peut exister dans C03 et
C04 en même temps (ids différents).

### Suppression

La FK `sequences_du_cycle.theme_id → themes.id` est `ON DELETE SET NULL`,
donc techniquement SQLite laisserait la suppression aboutir en
détachant les séquences. Mais le service `supprimer_theme` **refuse
explicitement** tant qu'une séquence est rattachée, pour éviter les
orphelins silencieux. L'enseignant doit détacher manuellement (ou via
l'atelier Séquence du cycle qui viendra en R3).

## Prochaine étape : R3 — Atelier Séquence du cycle

CRUD UI + API pour gérer les 14 séquences du cycle (nom, numéro,
rattachement thème).
