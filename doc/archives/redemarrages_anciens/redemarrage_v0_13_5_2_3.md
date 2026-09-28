# Redémarrage — v0.13.5.2.3 (déduction type_format)

> Livraison du 11 mai 2026.
> Mise à jour de l'atelier Exercice pour calculer `type_format`
> automatiquement à partir de l'énoncé. Pas de UI, pas de saisie, pas
> de routes nouvelles : le champ est purement dérivé du contenu LaTeX.
>
> Prérequis pour v0.13.5.2.4 (UI atelier Évaluation) qui aura besoin
> de distinguer QCM et standard pour afficher les bons champs de
> barème.

## Décisions

### Q1 — Comment exposer `type_format` dans l'atelier Exercice ?

**Réponse retenue** : on ne l'expose pas. Le champ est **déduit
automatiquement** de la présence de l'environnement LaTeX `seqQcm`
dans l'énoncé.

C'est une simplification radicale : pas de sélecteur, pas de bouton,
pas de migration de données client, pas de risque d'incohérence
contenu/type, pas de question UX sur le comportement quand on change
de type pour un exo déjà utilisé.

### Q2 — Adapter le formulaire si QCM ?

**Réponse retenue** : non. Tous les champs restent visibles. L'éditeur
de l'enseignant accepte du LaTeX libre, qu'il s'agisse d'un seqQcm ou
non.

### Q3 — Que faire si on change le type_format d'un exo utilisé ?

**Sans objet** : le champ se recalcule simplement à chaque sauvegarde.
Si l'enseignant retire un `seqQcm` d'un exo, le type passe à
`'standard'` à la sauvegarde suivante. Côté évaluation, c'est le
moteur de validation pédagogique qui constatera (à la prochaine
tentative de validation) que les barèmes ne sont peut-être plus
cohérents.

### Q4 — Quels champs sont scannés pour détecter `seqQcm` ?

**Réponse retenue** : `enonce` uniquement. Pas `corrige`, pas
`remed_*`.

## Périmètre livré

### 1. `services/atomes.py` — Helper + connexions

Nouvelle fonction privée :

```python
def _deduire_type_format(enonce: str) -> str:
    """Retourne 'qcm' si l'énoncé contient \\begin{seqQcm}, sinon 'standard'."""
```

La regex utilisée tolère un éventuel espace/tab entre `\begin` et `{seqQcm}`
(robustesse à des écritures comme `\begin {seqQcm}`).

Cas marginal documenté : un `\begin{seqQcm}` apparaissant dans un commentaire
LaTeX (`% \begin{seqQcm}`) déclenche aussi la détection. Pas de filtrage
des commentaires : la présence du marqueur dans le source compte. Cas peu
réaliste en pratique.

Appel :
- `creer_exercice` : `type_format` calculé depuis `data["enonce"]`
- `modifier_exercice` : `type_format` recalculé depuis l'énoncé courant
  (après merge des modifications)

Le `type_format` passé éventuellement dans `data` est **ignoré** dans
les deux cas — la valeur stockée est purement dérivée.

### 2. `persistence/sqlite_store.py` — Persistance

`lire_exercices` : ajoute `d["type_format"] = d.get("type_format") or "standard"`
pour normaliser la valeur (default 'standard' si manquante).

`ecrire_exercices` :
- UPDATE : ajoute la colonne `type_format = ?` dans le SET, avec default
  `'standard'` si absent du dict.
- INSERT : idem, dans la liste des colonnes et des valeurs.

### 3. `persistence/sqlite_store.py` — Migration de rattrapage v0.13.5.2.3

Ajout à `_migrer_schema_post_ddl` :

```sql
UPDATE exercices SET type_format = 'qcm'
WHERE type_format != 'qcm'
  AND enonce LIKE '%\begin{seqQcm}%'
```

Pourquoi ? Avant cette livraison, **tous les exos en base ont
`type_format='standard'`** (valeur par défaut posée par la migration
v0.13.5.2). La migration de rattrapage corrige rétroactivement les exos
qui contiennent un `seqQcm` dans leur énoncé.

Idempotente : ne touche que les exos qui ne sont pas déjà en `'qcm'`. Si
on relance, plus rien à corriger.

Note importante : pas d'auto-correction `'qcm' → 'standard'` ici. Si un
enseignant a manuellement édité `type_format='qcm'` mais que l'énoncé ne
contient pas/plus de seqQcm, la migration ne corrige pas — c'est la
prochaine sauvegarde via l'UI qui rectifiera. Choix conservateur : on ne
veut pas qu'une migration auto efface un statut posé volontairement.

### 4. Tests `tests/test_v0_13_5_2_3_type_format.py` — 27 tests

| Section | Classe | Tests |
|---|---|---|
| A | `TestDeduireTypeFormat` | 12 (cas nominaux et limites du helper) |
| B | `TestCreerExerciceTypeFormat` | 4 (création) |
| C | `TestModifierExerciceTypeFormat` | 4 (modification) |
| D | `TestPersistanceTypeFormat` | 4 (lire/écrire) |
| E | `TestMigrationRattrapage` | 3 (migration v0.13.5.2.3) |

## Bilan tests

- État de référence (post v0.13.5.2.2) : 2157 passent, 5 skippés.
- État après v0.13.5.2.3 : **2184 tests passent** (2157 + 27 nouveaux),
  **0 régression**, 5 skippés.

## Au démarrage chez Laurent

Quand `lancer.bat` redémarre l'appli :

1. `schema.sql` réexécuté (aucun changement)
2. `_migrer_schema_post_ddl` ré-exécuté :
   - Les anciennes migrations sont idempotentes (no-op)
   - La nouvelle migration `v0.13.5.2.3` est exécutée **une fois** :
     les exos contenant `\begin{seqQcm}` passent de `'standard'` à `'qcm'`
   - Au prochain démarrage, plus rien à faire (UPDATE renvoie rowcount=0)

À surveiller au premier démarrage : vérifier que la requête SQL n'a pas
ramené des faux positifs (`enonce LIKE '%\begin{seqQcm}%'` est large
mais simple ; si Laurent a un commentaire `% example: \begin{seqQcm}` dans
un exo standard, l'UPDATE le classera en qcm. Cas marginal, on peut
recorrigeer à la main via l'UI ou un SQL direct si besoin).

## Fichiers livrés

```
appli/
├── persistence/
│   └── sqlite_store.py                                  (modifié)
├── services/
│   └── atomes.py                                        (modifié)
├── tests/
│   └── test_v0_13_5_2_3_type_format.py                  (NOUVEAU — 27 tests)
└── doc/
    └── redemarrage_v0_13_5_2_3.md                       (ce document)
```

## Plan de la suite

- **v0.13.5.2.4** — UI atelier Évaluation : routes Flask, templates,
  JS, drag-and-drop. Utilisera `type_format` pour afficher les bons
  champs de barème (bareme_points pour standard, bareme_qcm_* pour qcm).
- **v0.13.5.3** — Génération `.tex` depuis BDD avec les macros
  finalisées en paquet v0.13.5.2.

---

*Fin du redémarrage v0.13.5.2.3.*
