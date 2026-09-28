# Redémarrage — v0.13.5.2.2 (services métier)

> Livraison du 11 mai 2026.
> Deuxième sous-version de v0.13.5.2 : validation pédagogique,
> dévalidation, calcul de couverture, liaisons évaluation ↔ objectifs.
> Toujours pas d'UI ni de routes Flask — c'est l'affaire de v0.13.5.2.3.

## Périmètre livré

### 1. Schéma BDD : nouvelle table `evaluation_objectifs`

Ajoutée à `persistence/schema.sql` :

```sql
CREATE TABLE IF NOT EXISTS evaluation_objectifs (
    evaluation_id  TEXT NOT NULL
                   REFERENCES evaluations(id) ON DELETE CASCADE,
    objectif_id    TEXT NOT NULL
                   REFERENCES objectifs_v2(id) ON DELETE RESTRICT,
    PRIMARY KEY (evaluation_id, objectif_id)
);
CREATE INDEX IF NOT EXISTS idx_evaluation_objectifs_objectif
    ON evaluation_objectifs (objectif_id);
```

**Pas de migration explicite nécessaire** : `schema.sql` étant ré-exécuté
au démarrage avec `CREATE TABLE IF NOT EXISTS`, la table est créée
automatiquement sur les BDD existantes. C'est le pattern standard pour
les nouvelles tables, par opposition aux migrations de colonnes sur
tables existantes qui passent par `_migrer_schema_post_ddl`.

**Contraintes choisies** :
- `ON DELETE CASCADE` côté évaluations : si l'éval est supprimée,
  ses liens d'objectifs disparaissent automatiquement.
- `ON DELETE RESTRICT` côté objectifs : on protège un objectif
  référencé par une éval — cohérent avec le pattern de protection
  des atomes pédagogiques. Si Laurent veut supprimer un objectif lié,
  il devra d'abord le retirer de l'éval.

### 2. Service `services/evaluations.py` — nouvelles fonctions

**Liaisons évaluation ↔ objectifs** :

```python
lister_objectifs_evaluation(conn, evaluation_id) -> list[dict]
ajouter_objectif_a_evaluation(conn, evaluation_id, objectif_id) -> dict
retirer_objectif_de_evaluation(conn, evaluation_id, objectif_id) -> None
```

Tri stable de la liste : par `sequence_code`, puis `partie_numero`,
puis `code` d'objectif.

**Validation pédagogique** (asymétrique) :

```python
valider_evaluation(conn, evaluation_id) -> dict      # contrôlé
devalider_evaluation(conn, evaluation_id) -> dict    # libre
```

**Calcul de couverture** :

```python
calculer_couverture(conn, evaluation_id) -> dict
# Retour : {objectifs: [...], exercices: [...], cellules: [...]}
```

### 3. Validation pédagogique — règles métier

Pour passer de `en_cours` à `valide` :

1. **Au moins 1 exercice attaché** à l'éval.
2. **Tous les exos ont un barème cohérent avec `mode_notation`** :

| `mode_notation` | Exo standard (`type_format='standard'`) | Exo QCM (`type_format='qcm'`) |
|---|---|---|
| `note` | `bareme_points` non NULL et ≥ 0 | `bareme_qcm_ok/partiel/ko` tous non NULL |
| `note_criteres` | `bareme_points` non NULL et ≥ 0 | `bareme_qcm_ok/partiel/ko` tous non NULL |
| `criteres` | facultatif (NULL accepté, ≥0 si présent) | facultatif (NULL accepté) |
| `aucun` | facultatif (NULL accepté, ≥0 si présent) | facultatif (NULL accepté) |

Si la validation échoue, `ValidationPedagogiqueErreur` est levée avec
un `details['raisons']` structuré listant chaque manquement :

```python
{
    'code': 'validation_pedagogique_echouee',
    'evaluation_id': 'ev_xyz',
    'raisons': [
        {'code': 'aucun_exercice'},                     # ou
        {'code': 'bareme_manquant',
         'exercice_id': 'EX042',
         'mode_notation': 'note'},                      # ou
        {'code': 'bareme_qcm_manquant',
         'exercice_id': 'EX042', 'mode_notation': 'note',
         'champs': ['ok', 'partiel', 'ko']},            # ou
        {'code': 'bareme_negatif',
         'exercice_id': 'EX042',
         'champ': 'bareme_points', 'valeur': -2.0},
    ]
}
```

L'UI v0.13.5.2.3 utilisera ces raisons pour cibler les cellules
fautives dans l'écran d'édition.

### 4. Dévalidation — asymétrie volontaire

`devalider_evaluation` ne fait **aucun contrôle métier**. C'est
cohérent avec le pattern documenté dans `services/etats_edition.py` :

> Les transitions sont manuelles et libres — pas de machine à états.
> L'enseignant assume la responsabilité.

Seule contrainte : on lève `DejaEnCours` si l'éval est déjà à
`en_cours`, pour que l'UI puisse afficher un message clair.

### 5. Couverture des objectifs — matrice creuse

`calculer_couverture` retourne une **matrice creuse** : seules les
cellules effectivement liées sont incluses. Une cellule existe quand :

- l'objectif est déclaré couvert par l'éval (présent dans
  `evaluation_objectifs`)
- ET l'exo est attaché à l'éval (présent dans `evaluation_exercices`)
- ET il existe une ligne dans `objectif_exos` rattachant cet exo à
  cet objectif (le lien métier existant entre exos et objectifs au
  niveau des séquences)

C'est ce qui permettra à l'UI v0.13.5.2.3 d'afficher un tableau croisé
montrant :

- les objectifs déclarés mais non couverts par les exos de l'éval
  (cellules vides — à renforcer ou à retirer)
- les exos contribuant à plusieurs objectifs (cellules multiples
  sur la même ligne d'exo)

### 6. Contrôle de cohérence de niveau

Quand on ajoute un objectif à une évaluation, on vérifie qu'il
appartient au **même niveau** que l'évaluation. Sinon on lève
`ObjectifNiveauIncoherent` avec les détails.

La chaîne de jointure est : `objectifs_v2 → sequence_parties →
sequences_par_niveau.niveau`. Le helper privé `_niveau_de_objectif`
encapsule cette résolution.

### 7. Note sur `type_format='qcm'`

La colonne `exercices.type_format` existe depuis v0.13.5.2 (avec
valeur par défaut `'standard'`) mais **n'est exposée nulle part** dans
l'UI actuelle. Tous les exos en BDD chez Laurent ont donc `type_format
= 'standard'` à ce stade.

Conséquence côté validation pédagogique : le chemin "QCM" est testé
mais ne s'activera réellement qu'à partir du moment où l'atelier
Exercice sera mis à jour pour permettre la saisie de `type_format='qcm'`.
Cette mise à jour est reportée à une version ultérieure (probablement
v0.13.5.2.4 ou v0.13.5.3 selon le couplage avec la génération PDF).

## Tests

**45 nouveaux tests** dans `tests/test_v0_13_5_2_2_evaluations_metier.py`,
organisés en 12 classes :

- **Section A — Liaisons objectifs** (~13 tests)
  - `TestLierObjectif` (6) : ajout simple, multiple, inexistant, doublon, niveau incohérent, eval inexistante
  - `TestRetirerObjectif` (3) : retrait, non lié, eval inexistante
  - `TestListerObjectifs` (4 : eval vide, tri par sequence/partie/code)
- **Section B — Validation pédagogique** (~17 tests)
  - `TestValidationModeAucun` (3) : passe avec ≥1 exo, échoue vide, signale négatif
  - `TestValidationModeNote` (4) : passe avec barème, signale manquant, multiples manquants, négatif
  - `TestValidationModeCriteres` (3) : passe sans barème, passe avec barème, échoue vide
  - `TestValidationModeNoteCriteres` (2) : passe avec barème, signale manquant
  - `TestValidationQCM` (4) : passe avec tous, signale un manquant, signale tous, criteres pas de bareme
  - `TestValidationCasParticuliers` (3) : déjà_valide, eval inexistante, raisons multiples
- **Section C — Dévalidation** (~4 tests)
  - `TestDevalidation` : simple, déjà_en_cours, sans contrôle, eval inexistante
- **Section D — Couverture** (~8 tests)
  - `TestCalculerCouverture` : vide total, objectifs seuls, exos seuls, cellule simple, 1 obj × 2 exos, 1 exo × 2 obj, lien externe ignoré, eval inexistante
- **Section E — Flux complets** (~3 tests)
  - `TestFluxComplet` : création→remplissage→validation→dévalidation, modification post-validation possible, revalidation après modif d'un barème

## Bilan tests

- État de référence (post v0.13.5.1.6.1) : 2112 passent, 5 skippés.
- État après v0.13.5.2.2 : **2157 tests passent** (2112 + 45 nouveaux),
  **0 régression**, 5 skippés.

## Fichiers livrés

```
appli/
├── persistence/
│   └── schema.sql                                       (modifié)
├── services/
│   └── evaluations.py                                   (modifié — +538 lignes)
├── tests/
│   └── test_v0_13_5_2_2_evaluations_metier.py           (NOUVEAU — 45 tests)
└── doc/
    └── redemarrage_v0_13_5_2_2.md                       (ce document)
```

## Plan de la suite

- **v0.13.5.2.3** — UI atelier Évaluation : routes Flask, templates,
  JS, drag-and-drop. Bandeau de validation pédagogique avec affichage
  des `raisons` pour cibler les cellules fautives.
- **v0.13.5.3** — Génération `.tex` depuis BDD avec les macros
  finalisées en paquet v0.13.5.2 (`\seqTitreEval`, `seqEvalBareme`,
  `seqEvalObjectifs`, `seqEvalExercice`).
- **v0.13.5.2.4 (ou .3)** — Mise à jour de l'atelier Exercice pour
  exposer `type_format` ('standard' / 'qcm').

---

*Fin du redémarrage v0.13.5.2.2.*
