# Redémarrage — projet seqenseigne v0.4
_Préparé le 14 avril 2026_

---

## Contexte général

Laurent Coste, enseignant collège (cycle 4).
Niveaux : N09=6ème, N10=5ème, N11=4ème, N12=3ème (14 séquences chacun).
Paquet LaTeX custom `seqenseigne` + application Flask de conception pédagogique.
Dépôt : `forge.apps.education.fr/laurentcoste/seqenseigne`
Environnement : clé USB MiKTeX portable x64 (MiKTeX 26.2), Python portable, Windows, `lancer.bat`.
Structure : `F:\Enseignement\seqenseigne\` avec `appli\`, `reference\`, `outils\`.

---

## Ce qui a été résolu en v0.3 → v0.4

### Paquet LaTeX

- **N10, N11, N12** : tous les livrets et documents annuels compilent (passe de régression complète confirmée).
- **Bugs datatool v3 corrigés** dans `seqenseigne-data.dtx` :
  - `seq@bases@filter@cycle` : `\DTLifstringeq` → `\ifthenelse{\equal{}{}}` avec `\dtlexpandnewvalue` déplacé
  - `seq@prerequis@annee` : `\edef\seq@tmp@rowcount{\DTLrowcount{base}}` avant chaque `\DTLifeq`

### Application Flask — ce qui fonctionne

**Import scanner** : vidage BdD → re-import complet N10/N11/N12 testé et validé.
Résultat : 166 notions, 156 méthodes, 802 exercices, 42 livrets, 0 erreur.

**Génération YAML N11/N12** : `POST /api/admin/generer-yaml` reconstruit les fichiers
`N11_sequences.yaml` et `N12_sequences.yaml` depuis `livrets_importes.json` +
`C04_sequences.csv`. Déclenché automatiquement si le YAML est vide au premier appel
de `/api/sequences?niveau=N11`.

**Nouvelles routes admin** :
- `GET /api/admin/statut` — compteurs BdD + état YAML par niveau
- `POST /api/admin/generer-yaml` — génération YAML
- `POST /api/admin/reset/reference` — vide atomes pédagogiques
- `POST /api/admin/reset/suivi` — vide classes/suivi/niveaux/versions
- `POST /api/admin/reset/tout`

**Filtres niveau/séquence dans les ateliers** : sélecteurs synchronisés dans les
sidebars Exercice, Notion, Méthode. Variables JS : `ATL_FILTRE_NIVEAU` / `ATL_FILTRE_SEQ`.

**Sous-onglet "Base de données"** dans Administration : état BdD, génération YAML,
réinitialisation avec confirmation inline.

**Bugs corrigés** :
- `re.PatternError: bad escape \s` dans `build_sequences_from_livrets` → suppression du `re.sub` inutile
- `import yaml as _yaml` en doublon → uniformisé sur le `yaml` de l'entête
- Toutes les routes admin enveloppées dans `try/except` → toujours du JSON

### Fichiers déployés en v0.4

| Fichier | Destination |
|---------|-------------|
| `app.py` | `appli\` |
| `index.html` | `appli\templates\` |
| `app.js` | `appli\static\` |
| `app.css` | `appli\static\` |
| `C04_sequences.csv` | `appli\data\` |
| `C04_themes.csv` | `appli\data\` |

---

## Points en suspens (portés de v0.3)

### Paquet LaTeX
- [ ] N09 (6ème) : migration notions/méthodes non encore faite
- [ ] Script migration `\usepackage[geometrie]` dans les 17 livrets concernés
- [ ] Test et mesure des formats précompilés `.fmt`

### Application Flask
- [ ] Atelier Progression annuelle — **priorité v0.4** (voir ci-dessous)
- [ ] Atelier Plan de travail — **priorité v0.4** (voir ci-dessous)
- [ ] Résolution des macros LaTeX dans les noms d'objectifs (YAML N11/N12 contient encore `\seqObjectifGetNom{02}`)
- [ ] Migration CSV/JSON → SQLite
- [ ] Périodes d'évaluation S1/S2 + vue bulletin + export CSV
- [ ] Données N09
- [ ] Option compilation dyslexie (xeLaTeX + OpenDyslexic + A3 + LetterSpace=20 + WordSpace=1.5 + baselinestretch=1.2 + unicode-math/latinmodern-math.otf)

### Contenu pédagogique
- [ ] Intégrer les 16 corrigés N11 dans les fichiers .tex exercices (fichier `corriges_N11.tex` disponible)
- [ ] Vérifier N12 : exercices sans corrigé (même démarche que N11)

---

## Priorités v0.4 — Ateliers Progression et Plan de travail

### Vue d'ensemble

Le plan de travail LaTeX actuel (`N1X_Plan_de_travail.tex`) mélange deux types d'informations :
1. **Organisation** : ordre des séquences, dates début/fin, nombre de séances (total, révisions, cours, par objectif)
2. **Contenu** : relation méthode → notions associées (ce lien doit migrer vers les livrets)

L'objectif est de séparer ces deux responsabilités :
- L'atelier **Progression** gère l'organisation calendaire des séquences
- L'atelier **Plan de travail** génère le document LaTeX depuis les données de progression + livrets

---

### Atelier Progression (UC-P01)

#### Ce que l'atelier doit permettre

- Choisir un niveau (N10/N11/N12)
- Voir les 14 séquences du niveau avec leur nom (depuis `C04_sequences.csv`)
- Ordonner les séquences (drag & drop ou numérotation manuelle)
- Pour chaque séquence, saisir :
  - Date de début (semaine)
  - Nombre de séances total
  - Nombre de séances pour les révisions
  - Nombre de séances pour le cours
  - Nombre de séances par objectif (dérivé ou saisi)
  - Période d'évaluation : S1 / S2 / contrôle continu
- Affecter la progression à une ou plusieurs classes
- Sauvegarder dans `N1X_progression.json`

#### Modèle de données proposé

```json
// data/N10_progression.json
{
  "niveau": "N10",
  "annee": "2025-2026",
  "sequences": [
    {
      "code": "S01",
      "ordre": 1,
      "nom": "Représentations d'un nombre",
      "periode": "S1",
      "date_debut": "2025-09-08",
      "nb_seances_total": 6,
      "nb_seances_revisions": 1,
      "nb_seances_cours": 1,
      "nb_seances_objectifs": {
        "02": 1,
        "03": 1,
        "04": 1,
        "05": 1
      }
    }
  ]
}
```

#### Routes à créer

| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/progression/<niveau>` | GET | Charge la progression d'un niveau |
| `/api/progression/<niveau>` | POST | Sauvegarde la progression |
| `/api/progression/<niveau>/reset` | POST | Réinitialise (repart des séquences dans l'ordre naturel) |

#### UI proposée

L'atelier Progression s'ajoute comme sous-onglet dans l'onglet Ateliers (après Livret),
ou comme onglet de premier niveau dans la nav principale.

Structure de la sidebar :
- Sélecteur niveau
- Liste des 14 séquences dans l'ordre courant (drag & drop)
- Bouton "Sauvegarder"

Zone principale :
- Formulaire de la séquence sélectionnée (dates, séances, période)
- Tableau synthétique de toutes les séquences

---

### Atelier Plan de travail (UC-P02)

#### Ce que l'atelier doit permettre

- Choisir un niveau
- Afficher un aperçu du plan de travail (tableau des 14 séquences avec objectifs, notions, dates)
- Générer le fichier `N1X_Plan_de_travail.tex` depuis :
  - `N1X_progression.json` (organisation)
  - `livrets_importes.json` (contenu : notions, méthodes/objectifs par séquence)
  - `C04_sequences.csv` + `C04_themes.csv` (noms, thèmes, couleurs)

#### Structure LaTeX actuelle du plan de travail (référence)

Le plan de travail actuel contient :
- En-tête : niveau, année, établissement
- Pour chaque thème : tableau des séquences du thème avec
  - Numéro et nom de séquence
  - Dates (colonne à remplir)
  - Objectifs (liste numérotée)
  - Notions associées à chaque objectif
  - Nombre de séances par objectif

La génération LaTeX doit reproduire cette structure depuis les données JSON.

#### Routes à créer

| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/plan-travail/<niveau>/apercu` | GET | Données structurées pour l'aperçu UI |
| `/api/plan-travail/<niveau>/generer` | POST | Génère le .tex et retourne son contenu |

#### UI proposée

Sous-onglet "Plan de travail" dans Ateliers, ou onglet dédié.

Zone principale :
- Sélecteur niveau + année
- Bouton "Générer le .tex"
- Zone de prévisualisation du LaTeX généré (lecture seule, avec bouton Copier)
- Affichage du tableau synthétique (notions + objectifs par séquence) pour vérification

---

### Dépendances entre les deux ateliers

```
C04_sequences.csv
C04_themes.csv
       │
       ▼
livrets_importes.json ──→ Atelier Progression ──→ N1X_progression.json
(notions, méthodes,                                       │
 exercices par seq)                                       ▼
       │                                       Atelier Plan de travail
       └──────────────────────────────────────────→ N1X_Plan_de_travail.tex
```

---

## Ordre de développement suggéré

1. **Modèle de données** : créer `N10_progression.json` (manuellement ou par reset) avec les 14 séquences dans l'ordre, champs vides
2. **Routes backend** : `GET/POST /api/progression/<niveau>` + `/api/plan-travail/<niveau>/apercu`
3. **UI Progression** : sidebar drag & drop + formulaire séquence
4. **Génération .tex** : `POST /api/plan-travail/<niveau>/generer` (remplacement de la génération LaTeX manuelle)
5. **UI Plan de travail** : aperçu tableau + zone LaTeX

**Note sur le drag & drop** : utiliser l'API HTML5 native (`draggable`, `dragover`, `drop`) — pas de bibliothèque externe. Pattern déjà utilisé dans l'atelier Livret pour les atomes.

---

## Rappel structure des fichiers `app.py`

Les nouvelles fonctions sont à placer dans l'ordre habituel :

```python
# ── Helpers progression ───────────────────────────────────────────────────────
def rj_progression(niveau):  # charge N1X_progression.json
def wj_progression(niveau, data):  # sauvegarde
def build_progression_vide(niveau):  # 14 séquences ordre naturel

# ── Routes progression ────────────────────────────────────────────────────────
@app.route('/api/progression/<niveau>', methods=['GET'])
@app.route('/api/progression/<niveau>', methods=['POST'])
@app.route('/api/progression/<niveau>/reset', methods=['POST'])

# ── Routes plan de travail ────────────────────────────────────────────────────
@app.route('/api/plan-travail/<niveau>/apercu', methods=['GET'])
@app.route('/api/plan-travail/<niveau>/generer', methods=['POST'])

# ── Lancement ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
```
