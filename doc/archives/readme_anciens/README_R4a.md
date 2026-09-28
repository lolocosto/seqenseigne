# seqenseigne — R4a : Schéma séquences-par-niveau

Premier sous-chantier de R4 du CdC v0.8. **Zéro impact fonctionnel** :
les nouvelles tables sont créées mais restent vides, et les anciennes
tables (`livrets_de_sequence`, `objectifs`, etc.) continuent d'être
utilisées par toute l'appli.

**Status** : 26 nouveaux tests, 675 verts au total, 0 régression.

## Ce que fait R4a

Crée 5 tables dans la base :

| Table | Rôle |
|---|---|
| `sequences_par_niveau` | Une ligne par (niveau, séquence). Ex: (N11, S01), (N12, S01). Porte aussi le champ `parametres` pour le contenu LaTeX de `_param.tex`. |
| `sequence_parties` | Les parties (1, 2, 3...) dans lesquelles chaque séquence est découpée. |
| `partie_precedences` | Les précédences entre parties : une partie peut dépendre de séquences précédentes. |
| `objectifs_v2` | Nouveaux objectifs, rattachés à une partie, avec critères F/A/E. Cohabite temporairement avec l'ancienne `objectifs` jusqu'à R4f. |
| `objectif_exos` | Exercices rattachés à un objectif, indexés par (série, num). |

## Ce que R4a ne fait pas

- **Ne peuple pas** les tables (R4b)
- **Ne touche pas** aux tables existantes (`objectifs`, `livrets_de_sequence`, `livret_exercices`, `livret_revisions`, `exercice_objectifs`, `creneaux`)
- **Ne change pas** l'UI ni le backend existant

Après déploiement de R4a, l'appli fonctionne exactement comme avant.
Les nouvelles tables sont présentes et vides, prêtes à être utilisées
par R4b.

## Fichiers livrés

| Fichier | Rôle |
|---|---|
| `appli/persistence/schema.sql` | Ajout des 5 tables en tête du schéma |
| `appli/persistence/ids.py` | +2 générateurs (`sn_xxx`, `pt_xxx`) |
| `appli/scripts/peuplement_12_migrer_schema_sequences.py` | Migration idempotente |
| `appli/tests/test_R4a_schema.py` | 26 tests |

## Déploiement

### 1. Extraire le ZIP dans `appli/`

Remplace `schema.sql` et `ids.py`, ajoute le script `peuplement_12` et le fichier de test.

### 2. Migrer le schéma de la base existante

```powershell
cd D:\Enseignement\seqenseigne\appli
..\outils\python\python.exe scripts\peuplement_12_migrer_schema_sequences.py
```

Sortie attendue :
```
Migration R4a — terminée
Tables créées : objectif_exos, objectifs_v2, partie_precedences, sequence_parties, sequences_par_niveau
Tables cible présentes : objectif_exos, objectifs_v2, partie_precedences, sequence_parties, sequences_par_niveau
```

Ou, si on relance une seconde fois :
```
Migration R4a — terminée
Aucune nouvelle table à créer (schéma déjà à jour).
Tables cible présentes : ...
```

### 3. Vérifier

```powershell
..\outils\python\python.exe -m pytest tests -q
```

Attendu : **675 tests verts**.

L'appli doit continuer à fonctionner à l'identique. Rien ne bouge côté UI.

## Choix techniques

### Nommage `objectifs_v2`

La table s'appelle `objectifs_v2` pendant la phase de cohabitation
avec l'ancienne `objectifs` (qui porte aujourd'hui `niveau`, `sequence`,
`est_nouveau`, `obj_precedent_id`). Au chantier R4f, une fois que
l'ancienne sera démantelée, un `ALTER TABLE objectifs_v2 RENAME TO objectifs`
la replacera sous son nom définitif.

### Unicité `(objectif_id, serie, exercice_id)` sur `objectif_exos`

Un même exercice ne peut pas apparaître deux fois dans la même série
d'un même objectif. Il peut par contre apparaître dans deux séries
différentes (ex: un exo de fondamental et sa version en entraînement
seraient deux exercices distincts, mais un même exo peut être référencé
comme `F_01` et `R_03` pour deux objectifs différents).

### `ON DELETE RESTRICT` sur `exercices`

Une fois qu'un exercice est rattaché à au moins un objectif dans
`objectif_exos`, il ne peut pas être supprimé directement. Il faut
d'abord retirer toutes les références. Choix protecteur pour éviter
les orphelins silencieux.

### Colonne `sequences_par_niveau.parametres`

Porte le contenu LaTeX qui était jusqu'ici dans les fichiers
`Nxx_Syy_param.tex`. Sera peuplée par le scanner en R4b.

## Prochaine étape : R4b

Adapter le scanner d'atomes pour peupler les nouvelles tables **en
plus** de continuer à peupler l'ancienne structure. À la fin de R4b,
on aura les deux modèles coexistant, l'ancien toujours utilisé par
l'UI, le nouveau prêt pour R4e.
