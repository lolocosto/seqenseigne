# Redémarrage v0.15.2.11 — Restructuration trace JSON + fiche liée dans l'UI

Deux livrables, tous deux issus du retour Laurent sur la trace v0.15.2.10 :

1. **Restructuration de la trace JSON** (schéma → version 2).
2. **UI atelier assemblage** : afficher la fiche de résumé liée à chaque objectif, à côté de la méthode.

## 1. Restructuration de la trace JSON (schéma v2)

### Retour Laurent

> *« Il faut faire apparaître des relations dans les séquences (voir le fichier joint modifié à la main pour S01) »*

La trace v0.15.2.10 (schéma v1) listait à plat les atomes d'une séquence dans une section `atomes_utilises`, sans dire **lequel sert à quel objectif**. Laurent a fourni un JSON édité à la main pour S01 qui dessine la structure cible : **les objectifs vivent SOUS chaque partie**, et **chaque objectif porte ses propres atomes liés**.

### Nouveau schéma (v2)

```jsonc
{
  "version_schema": 2,
  "sequences": [{
    "code", "numero", "nom", "theme_code",
    "parties": [{
      "numero",
      "nb_seances_R_AE",
      "cartes_automatisme":   [{num, type_pedago, titre}],
      "exercices_R":          [{niveau, sequence, num, serie, titre}],  // révisions
      "exercices_AE":         [{niveau, sequence, num, serie, titre}],  // approche
      "objectifs": [{
        "code", "nom", "fin_cycle", "critere_f/a/e", "nb_seances",
        // Pour les objectifs "Cours" (codes 01, 11, 21) : pas de sections atomes.
        // Pour les objectifs ordinaires :
        "methodes":      [{num_methode, titre}],     // cardinalité 0/1, en liste
        "notions":       [{num_connaissance, titre}], // via objectif_notions
        "exercices":     [{num, serie, titre}],       // via objectif_exos
        "fiches_resume": [{num_fiche, titre}]         // via fiches_resume.objectif_id
      }]
    }],
    "precedents": [{niveau, sequence, ordre}]
  }],
  // documents, themes, evaluations : structure inchangée
}
```

### Sources des relations en BDD

| Relation | Table BDD | Note |
|---|---|---|
| `objectif → méthode` | `objectifs.methode_id` | 1-1 |
| `objectif → fiche` | `fiches_resume.objectif_id` | 1-1 (stocké côté fiche) |
| `objectif → exercices` | `objectif_exos` (M-N) | série `F`/`A`/`E` traduite en `fondamental`/`avancé`/`exploration` |
| `objectif → notions` | `objectif_notions` (M-N) | ⚠️ **8 lignes seulement en prod** (voir limitation) |
| `partie → cartes_automatisme` | `objectif_cartes` agrégée par partie | union des cartes des objectifs de la partie |
| `partie → exercices_R` | `partie_exos_revision_approche` type `R` | utilise les colonnes `origin_*` |
| `partie → exercices_AE` | `partie_exos_revision_approche` type `EA` | idem |

### Traduction des codes séries

Les codes BDD `F` / `A` / `E` (utilisés dans `objectif_exos.serie` et `partie_exos_revision_approche.origin_serie`) sont traduits en labels métier `fondamental` / `avancé` / `exploration` dans la trace, conformément à la convention demandée par Laurent.

### Objectifs « Cours » (codes 01, 11, 21)

Ces objectifs (un par partie) couvrent la connaissance des notions et méthodes de la partie entière. Ils n'ont **pas** de section `methodes` / `notions` / `exercices` / `fiches_resume` dans la trace — convention sémantique cohérente avec leur rôle pédagogique.

### Limitations connues

- ⚠️ **`objectif_notions` est très peu peuplée en BDD** (8 lignes au total, dont 0 pour N11/S01). Donc dans la trace générée, `notions: []` pour la plupart des objectifs. Le plan de travail `.tex` que Laurent m'a fourni contient ces relations (codes `C01`, `C02`, etc. par objectif), mais leur intégration dans la trace nécessite un parser `.tex` — **chantier séparé à arbitrer**.

- ⚠️ Certains objectifs « artefactuels » (par exemple `obj 05`, `obj 06` dans S01 partie 1) existent en BDD mais ne sont pas dans le plan de travail réel. La trace les inclut tels quels (BDD = source de vérité au moment du figeage).

### Résultat sur N11_v2025

Sur la BDD actuelle :
- 14 séquences, **91 objectifs** au total (à travers toutes les parties)
- **57 fiches** de résumé liées à leur objectif (1-1 confirmé)
- Toutes les méthodes ordinaires ont leur fiche associée

Exemple S01 :

| Partie 1 | code | méth | exo | fiche |
|---|---|---|---|---|
| obj 01 (Cours) | 01 | — | — | — |
| obj 02 | 02 | 1 | 9 | 1 |
| obj 03 | 03 | 1 | 11 | 1 |
| obj 04 | 04 | 1 | 6 | 1 |
| obj 05 | 05 | 0 | 0 | 0 | (artefact BDD) |
| obj 06 | 06 | 0 | 0 | 0 | (artefact BDD) |

| Partie 2 | code | méth | exo | fiche |
|---|---|---|---|---|
| obj 11 (Cours) | 11 | — | — | — |
| obj 12 | 12 | 1 | 3 | 1 |
| obj 13 | 13 | 1 | 3 | 1 |

## 2. Fiche de résumé liée dans l'UI atelier assemblage

### Retour Laurent

> *« Dans l'UI des assemblages de séquence, il manque la fiche de résumé liée à un objectif (à afficher au même endroit que la méthode liée à un objectif). »*

### Avant

Dans l'atelier `static/atelier_seqniv_assemblage.js`, chaque objectif ouvert affichait un bandeau « Méthode liée : … » avec deux boutons « Éditer » et « Délier ». Pour les fiches de résumé, l'affichage existait UNIQUEMENT pour l'objectif « Connaître les notions et les méthodes » (code 01/11/21) sous forme d'une zone de drag-and-drop des fiches du livret. Pour les autres objectifs (02, 03, etc.) : **aucune indication** de la fiche associée, alors que la relation 1-1 existe en BDD.

### Après

Backend `services/v2_lecture.py` — ajout des champs `fiche_id`, `fiche_titre`, `fiche_num` à la réponse pour chaque objectif (chargés via une query séparée résiliente aux schémas de test minimaux).

Frontend `static/atelier_seqniv_assemblage.js` — nouveau bandeau `ficheBloc` rendu juste sous `methBloc`. Pour un objectif ordinaire avec une fiche liée :

```
┌─────────────────────────────────────────────────────────────┐
│ Méthode liée : Utiliser les puissances …    [Éditer] [Délier]│
│ Fiche de résumé liée : Utiliser les puissances …    [Éditer] │
│ F — À consolider     ┌──────────────────────────────────┐    │
│ A — Satisfaisant     │  critères textarea               │    │
│ E — Très bon         └──────────────────────────────────┘    │
│ … exercices, notions, …                                      │
└─────────────────────────────────────────────────────────────┘
```

Le bouton « Délier » est volontairement absent côté fiche : la relation `fiches_resume.objectif_id` se gère depuis l'atelier Fiche (en mettant `objectif_id` à NULL). C'est aussi plus conservateur — pas de surcharge de l'UI pour un cas d'usage rare.

## Tests

**v0.15.2.11 : 3633 passed, 7 skipped, 0 failed** (+14 par rapport à v0.15.2.10).

### Nouveaux fichiers

| Fichier | Nb | Couverture |
|---|---|---|
| `tests/test_v0_15_2_11_trace_v2.py` | 12 (+1 skip) | Schéma v2, structure nichée parties/objectifs/atomes, traduction des séries, objectif Cours sans atomes, smoke test N11_v2025 (skip si BDD test) |
| `tests/test_v0_15_2_11_ui_fiche_objectif.py` | 2 | Backend renvoie `fiche_id`/`fiche_titre`/`fiche_num` pour chaque objectif, `None` si pas de fiche |

### Tests adaptés

| Fichier | Raison |
|---|---|
| `tests/test_v0_15_2_9_figeage.py` | Test bout-en-bout adapté à la nouvelle structure (objectifs sous parties) |
| `tests/test_v0_15_2_9_figeage_route.py` | `version_schema == 2` au lieu de 1 |

## Fichiers livrés

### Code (`seqenseigne_v0_15_2_11.zip`)

| Fichier | Type |
|---|---|
| `appli/services/referentiel_figeage.py` | Modifié (refonte structure trace, schéma v2) |
| `appli/services/v2_lecture.py` | Modifié (champs fiche pour objectifs) |
| `appli/static/atelier_seqniv_assemblage.js` | Modifié (bandeau fiche liée) |
| `appli/tests/test_v0_15_2_11_trace_v2.py` | Nouveau |
| `appli/tests/test_v0_15_2_11_ui_fiche_objectif.py` | Nouveau |
| `appli/tests/test_v0_15_2_9_figeage.py` | Modifié (adaptation v2) |
| `appli/tests/test_v0_15_2_9_figeage_route.py` | Modifié (schema_version=2) |
| `appli/doc/redemarrage_v0_15_2_11.md` | Nouveau |

Pas de `.dtx`/`.sty`, pas de changement BDD.

### Données démo (`seqenseigne_v0_15_2_11_data_demo.zip`)

Régénération du `data/referentiels/N11_v2025/_fige/` avec la nouvelle structure :
- `trace.json` v2 (118 ko, 14 séquences détaillées)
- `pdfs/livret_sequence__N11__S01.pdf` (toujours présent)

## Vérification

```powershell
.\outils\python\python.exe outils\verifier_md5.py --racine . --manifest MANIFEST.md5
.\outils\python\python.exe -m pytest -q
# Attendu : 3633 passed, 7 skipped, 0 failed
```

## À arbitrer pour la prochaine session

1. **Parser le `.tex` plan de travail pour enrichir la trace** : tu m'as fourni `4e3_Plan_de_travail.tex` qui contient les relations `objectif → notions` (codes C01, C02, …) que la BDD n'a pas. Faut-il faire un script `outils/parser_plan_de_travail.py` ?
2. **Compléter l'import N11_v2025** avec tes 13 autres PDFs (S02-S14).
3. **Pour la 6ème** (N06) : examen de la structure des docs des collègues.
4. **Atelier assemblage séquence-dans-niveau** (EN COURS dans userMemories) — bug `_cycle_du_niveau`.
5. **Vue de consultation de la trace figée** dans l'UI (lecture humaine du JSON).
