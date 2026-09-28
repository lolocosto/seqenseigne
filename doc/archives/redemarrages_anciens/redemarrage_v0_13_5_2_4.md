# Redémarrage — v0.13.5.2.4 (atelier Évaluation complet)

> Livraison du 11 mai 2026.
> Quatrième sous-version de v0.13.5.2 : routes Flask + UI complète de
> l'atelier Évaluation, intégré dans la portée Niveau.
> Aboutissement de la trilogie .2.1 (BDD), .2.2 (services métier),
> .2.3 (type_format auto), .2.4 (routes + UI).

## Périmètre livré

### 1. Routes Flask — `routes/evaluations.py` (nouveau, ~430 lignes)

15 endpoints, organisés en 6 sections :

**CRUD évaluations**
- `GET    /api/evaluations?niveau=N10` — liste par niveau
- `GET    /api/evaluations/<eval_id>` — détail
- `POST   /api/evaluations` — création
- `PATCH  /api/evaluations/<eval_id>` — modification partielle
- `DELETE /api/evaluations/<eval_id>` — suppression
- `POST   /api/evaluations/reordonner` — réordonnancement d'un niveau

**Liaisons exos**
- `GET    /api/evaluations/<eval_id>/exos`
- `POST   /api/evaluations/<eval_id>/exos` — attache un exo (avec barème optionnel)
- `DELETE /api/evaluations/<eval_id>/exos/<exo_id>`
- `PATCH  /api/evaluations/<eval_id>/exos/<exo_id>` — modifie le barème
- `POST   /api/evaluations/<eval_id>/exos/reordonner`

**Liaisons objectifs (v0.13.5.2.2+)**
- `GET    /api/evaluations/<eval_id>/objectifs`
- `POST   /api/evaluations/<eval_id>/objectifs` — attache un objectif
- `DELETE /api/evaluations/<eval_id>/objectifs/<obj_id>`

**Transitions d'état**
- `POST   /api/evaluations/<eval_id>/valider` — en_cours → valide (contrôlé)
- `POST   /api/evaluations/<eval_id>/devalider` — valide → en_cours (libre)

**Couverture**
- `GET    /api/evaluations/<eval_id>/couverture` — matrice creuse

**Aides UI** (sélecteurs)
- `GET    /api/evaluations/niveau/<niveau>/exos-disponibles` — exos liés au niveau, groupés par séquence
- `GET    /api/evaluations/niveau/<niveau>/objectifs-disponibles` — objectifs du niveau, groupés par séquence

#### Mapping erreurs métier → codes HTTP

Conformément à `CONVENTIONS.md` section 2, un dict `_CODE_HTTP`
centralise la traduction des `code` stables des exceptions
`EvaluationErreur` :

| Code | HTTP |
|---|---|
| `evaluation_introuvable`, `objectif_introuvable`, `exercice_introuvable`, `*_introuvable_dans_evaluation` | 404 |
| `numero_deja_utilise`, `*_deja_present`, `objectif_niveau_incoherent`, `reordonnancement_invalide`, `deja_valide`, `deja_en_cours` | 409 |
| `mode_notation_invalide`, `etat_code_invalide`, `item_langue_francaise_invalide`, `validation_pedagogique_echouee` | 400 |

Pour `ValidationPedagogiqueErreur`, le champ `details.raisons` est
exposé tel quel dans la réponse JSON pour permettre à l'UI de cibler
les éléments fautifs (énoncé sans barème, etc.).

### 2. `app.py` — enregistrement du blueprint

Ajout dans la liste de `register_blueprint` :

```python
from routes.evaluations import bp as bp_evaluations
# ...
for bp in (..., bp_preferences, bp_evaluations):
    app.register_blueprint(bp)
```

### 3. Frontend — `templates/index.html` (modifié)

**Bouton d'onglet** dans le bandeau d'ateliers portée Niveau, inséré
avant « Référentiel » :

```html
<button class="vbtn atl-grp-niveau" id="atl-btn-evaluation"
        onclick="atelSwitch('evaluation')" style="display:none">Évaluation</button>
```

**Panel `#atl-evaluation`** (sidebar + détail) inséré avant le panel
Référentiel. Structure :

- Sidebar : liste des évaluations du niveau + bouton « + Créer »
- Détail :
  - En-tête : titre éditable (sauvegarde au blur/Enter) + mode_notation
    (dropdown) + checkbox afficher_bareme + item langue française (points)
    + boutons Supprimer / Valider / Dévalider + bandeau d'erreurs de
    validation pédagogique
  - Cadre Exercices : liste numérotée avec champs de barème adaptés au
    mode_notation et au type_format de chaque exo + boutons monter/
    descendre/retirer + mini-formulaire d'ajout (séquence + exo)
  - Cadre Objectifs : liste + sélecteur d'ajout (dropdown filtrable
    avec optgroup par séquence)
  - Cadre Couverture : tableau (objectifs en lignes, exos en colonnes,
    cellules vertes là où le lien `objectif_exos` existe)

### 4. Frontend — `static/app.js` (modifié)

Ajout de `'evaluation'` dans `ATL_PORTEES.niveau.ateliers` (position 4,
avant `'referentiel'`) et de `evaluation: 'atelEvalInit'` dans
`ATL_INITS`.

### 5. Frontend — `static/atelier_evaluation.js` (nouveau, 810 lignes)

Pattern d'`atelier_referentiel.js` (v0.13.5.1) : état local (variables
module), init exposé sur window, rendu sidebar + détail séparés,
handlers exposés sur window pour les onclicks HTML.

Sections fonctionnelles :
- Chargement des données (liste, détail, exos dispos, objectifs dispos)
- Rendu sidebar (items avec badge ✓/✏)
- Rendu détail (titre, méta, badges, boutons valider/dévalider)
- Rendu exos (champs de barème conditionnels selon mode×type_format)
- Rendu objectifs (liste avec retirer)
- Rendu couverture (tableau croisé objectifs×exos avec cellules colorées)
- Actions : créer, supprimer, sauver titre, sauver méta, ajouter/retirer
  exo, sauver barème, monter/descendre exo, ajouter/retirer objectif,
  valider, dévalider
- Affichage formaté des erreurs de validation pédagogique

#### UX (décisions Laurent)

- **Création** : « + Créer » crée immédiatement une éval `Nouvelle
  évaluation` avec `mode_notation='note'` et `etat_code='en_cours'`.
  L'enseignant la renomme via l'input titre (sauvegarde au blur/Enter).
- **Ajout exo** : mini-formulaire inline avec deux dropdowns séquence
  puis exo. Les exos déjà attachés sont automatiquement filtrés.
- **Ajout objectif** : dropdown unique avec `<optgroup>` par séquence
  pour la lisibilité. Les déjà-attachés sont filtrés.
- **Couverture** : tableau directement en bas du détail. Cellule
  pleine = lien `objectif_exos` existant. Cellule vide = objectif non
  couvert par cet exo (ou exo non rattaché à cet objectif au niveau
  pédagogique).
- **Erreurs de validation pédagogique** : affichage structuré dans un
  bandeau rouge sous l'en-tête, message lisible par raison
  (aucun_exercice / bareme_manquant / bareme_qcm_manquant /
  bareme_negatif).

## Tests

### 43 nouveaux tests de routes dans `tests/test_v0_13_5_2_4_evaluations_routes.py`

| Section | Tests |
|---|---|
| TestCRUDEvaluations | 13 |
| TestLiaisonsExos | 10 |
| TestLiaisonsObjectifs | 6 |
| TestTransitionsEtat | 6 |
| TestCouverture | 3 |
| TestSelecteursAides | 4 |

### Bilan tests

- État de référence (post v0.13.5.2.3) : 2184 passent, 5 skippés.
- État après v0.13.5.2.4 : **2227 tests passent** (2184 + 43 nouveaux),
  **0 régression**, 5 skippés.

### Tests JS

Aucun test JS automatisé n'est livré (cf. roadmap : Vitest/Jest à
introduire ultérieurement). Validation visuelle attendue chez Laurent :

1. Cliquer sur l'onglet « Niveau » dans la portée
2. Sélectionner un niveau (N10/N11/N12)
3. Cliquer sur « Évaluation » dans le bandeau
4. Vérifier l'apparition d'une sidebar vide « Aucune évaluation… »
5. Cliquer « + Créer » → une évaluation « Nouvelle évaluation » apparaît
6. Renommer le titre, modifier le mode
7. Ajouter un exo via le mini-formulaire (séquence → exo)
8. Ajouter un objectif via le dropdown
9. Vérifier le tableau de couverture
10. Tester la validation pédagogique (erreur si barème manquant)
11. Valider, puis dévalider

## Fichiers livrés

```
appli/
├── app.py                                                (modifié — +1 blueprint)
├── routes/
│   └── evaluations.py                                    (NOUVEAU — 430 lignes)
├── templates/
│   └── index.html                                        (modifié — +bouton +panel)
├── static/
│   ├── app.js                                            (modifié — ATL_PORTEES + ATL_INITS)
│   └── atelier_evaluation.js                             (NOUVEAU — 810 lignes)
├── tests/
│   └── test_v0_13_5_2_4_evaluations_routes.py            (NOUVEAU — 43 tests)
└── doc/
    └── redemarrage_v0_13_5_2_4.md                        (ce document)
```

## Plan de la suite

- **v0.13.5.3** — Génération `.tex` depuis BDD avec les macros
  finalisées en paquet v0.13.5.2 (`\seqTitreEval`, `seqEvalBareme`,
  `seqEvalObjectifs`, `seqEvalExercice`). Pipeline équivalent à
  `services/latex_rendu_atome.py` mais pour les évaluations.
- **v0.13.5.4 ?** — Onglet « Rendu PDF » dans l'atelier Évaluation,
  compilation pdflatex (similaire aux autres ateliers d'atomes).
- **v0.13.5.5** — Mécanisme `compile_*` (compilation différentielle
  basée sur mtime).

---

*Fin du redémarrage v0.13.5.2.4. La v0.13.5.2 est désormais complète :
BDD + services métier + routes + UI. Reste la génération PDF, qui sort
du périmètre v0.13.5.2.*
