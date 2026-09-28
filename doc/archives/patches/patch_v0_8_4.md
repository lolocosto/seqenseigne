# seqenseigne — Patch v0.8.4

**Date** : 26 avril 2026
**Type** : correctifs sur v0.8 (suite à v0.8.1, v0.8.2, v0.8.3)

---

## Trois corrections groupées

### 1. Erreur tikz « + or - expected » sur 17 notions de N10

**Symptôme** : 17 notions de N10 (S10/01-02, S11/02-03, S12/02-04, S12/07-12,
S13/02) plantaient en compilation isolée avec :

```
! Package tikz Error: + or - expected.
```

… alors que le livret entier dans lequel ces mêmes notions sont incluses
compile parfaitement.

**Cause** : incompatibilité entre les shorthands de `babel-french`
(ponctuation active, mathcode de la virgule modifié, etc.) et le parseur
de la bibliothèque tikz `calc`. Cette bibliothèque est appelée en interne
par des macros tkz-euclide telles que `\tkzDrawSegment` (via la clé
`add=0 and 0`) et lève cette erreur quand les shorthands de babel sont
encore actifs à l'intérieur d'un environnement `tikzpicture`.

`\usetikzlibrary{babel}` existe précisément pour ça : elle désactive les
shorthands à l'entrée d'un `tikzpicture` et les réactive à la sortie. Le
paquet `seqenseigne` la charge automatiquement quand il est utilisé en
entier, donc le livret n'a pas le problème. Le préambule reconstruit par
l'appli (qui inline les définitions au lieu de charger le paquet entier)
ne le faisait pas.

**Fix** : `services/preambule_atome.py` — ajout d'une nouvelle entrée
dans `INITIALISATIONS_BIBLIOTHEQUES` pour le paquet `tikz` :

```python
'tikz': [
    r'\usetikzlibrary{babel}',
],
```

`tikz` étant dans `PAQUETS_NOYAU`, cette init est émise dans tous les
préambules, juste après les `\usepackage` et avant les définitions
inlinées du paquet seqenseigne.

**Vérifié sur 6 notions échantillon** : toutes compilent sans la moindre
erreur tikz.

### 2. Notions et méthodes à corps seul classées à tort comme « vides »

**Symptôme** : 4 notions de N10 (`S03/02`, `S03/03`, `S10/03`, `S10/06`)
étaient marquées « Atome vide » dans les rapports de compilation, alors
que leur corps faisait entre 413 et 2933 caractères et compilait sans
problème en isolation.

**Cause** : le critère de détection d'atome vide dans
`services/compilation_batch.py::compiler_un_atome` utilisait directement
`_a_des_items()` (importé de `services/atomes.py`). Cette fonction est
documentée comme « Helper v0.6.4 — utilisé par les rapports de couverture
pour signaler les notions/méthodes incomplètes » : elle dit `True` si la
notion a au moins une section avec un item non vide, rien d'autre. C'est
un indicateur de couverture pédagogique (« cette notion mériterait
d'avoir un exemple »), **pas** un critère de compilabilité.

J'ai abusé de cette fonction en v0.8 : une notion sans section mais avec
un corps non vide (cas légitime du modèle universel à 2 niveaux) était
classée comme vide à tort.

**Fix** : remplacement du critère pour notion/méthode dans
`compiler_un_atome()` :

```python
# Avant
if not _a_des_items(atome.data):
    return STATUT_ECHEC_VIDE

# Après
corps_non_vide = bool((atome.data.get('corps', '') or '').strip())
a_des_items = _a_des_items(atome.data)
if not corps_non_vide and not a_des_items:
    return STATUT_ECHEC_VIDE
```

Une notion/méthode est désormais considérée comme vide uniquement si
**ni le corps ni les sections** ne contiennent de contenu non vide.

**Vérifié sur les 4 notions concernées** : toutes passent maintenant en
statut `succes` au lieu de `echec_vide`.

### 3. Exercices sans corrigé : ne plus rejeter, signaler informativement

**Avant v0.8.4** : un exercice sans corrigé était rejeté avec
`echec_vide`, ce qui faussait les statistiques (un exercice sans corrigé
n'est pas un atome impossible à compiler — c'est juste une incomplétude
pédagogique).

**Après v0.8.4** :

- Un exercice avec énoncé est compilé normalement, même sans corrigé.
- L'événement de succès porte un flag `sans_corrige=True` quand le
  corrigé manque.
- Le rapport Markdown gagne une nouvelle section
  **« Exercices sans corrigé »** qui liste ces exercices séparément.
  Ils figurent toujours dans « Compilations OK » (puisqu'ils compilent
  bien), la nouvelle section sert à les rendre visibles pour traitement
  ultérieur.
- Les exercices sans **énoncé** restent rejetés en `echec_vide` (un
  exercice sans énoncé n'a vraiment rien à montrer).

---

## Fichiers modifiés

- `services/compilation_batch.py` :
  - Critère « atome vide » corrigé pour notion/méthode (corps OU sections).
  - Flag `sans_corrige` ajouté sur l'événement des exercices sans corrigé.
  - Section « Exercices sans corrigé » ajoutée à `ecrire_rapport_md()`.
- `services/preambule_atome.py` :
  - Ajout de l'entrée `'tikz'` dans `INITIALISATIONS_BIBLIOTHEQUES` pour
    émettre `\usetikzlibrary{babel}` après le `\usepackage{tikz}`.
- `tests/test_compilation_batch.py` :
  - Test `test_exercice_vide_corrige_manquant` remplacé par 2 nouveaux :
    `test_exercice_sans_corrige_v084_compile_avec_flag` et
    `test_exercice_avec_corrige_pas_de_flag`.
  - 5 nouveaux tests sur le critère « atome vide » corrigé pour
    notion/méthode (corps seul valide, vraiment vide rejeté, corps blanc
    rejeté, sections seules valides, idem pour méthode).
  - 2 nouveaux tests sur la section « Exercices sans corrigé » du
    rapport MD.
- `tests/test_preambule_atome.py` :
  - 3 nouveaux tests sur l'init `\usetikzlibrary{babel}`
    (présence dans le préambule, ordre correct, présence dans le
    dictionnaire exporté).

---

## Tests

```
python -m pytest tests/test_compilation_batch.py tests/test_preambule_atome.py tests/test_route_compilation_batch.py
```

→ 130 tests verts (50 + 47 + 33), dont 12 nouveaux pour v0.8.4.

Suite complète : 914 verts + 4 skipped sur le périmètre testé. Aucune
régression.

---

## Effet attendu après déploiement

Sur ton dernier rapport (`Compilation_atomes_2026-04-26_16-49-08.md`),
les **17 erreurs « + or - expected » disparaissent** et les **4 atomes
classés « vides » à tort passent en succès**.

Restent à traiter (non couverts par v0.8.4) :

- 2 erreurs d'images manquantes : `./Images/touche_div_euclidienne.jpg`
  (S04/03) et `./Images/notion5_img1.png` (S13/03). À résoudre dans la
  BDD ou dans le dossier d'images.
- 1 erreur `pgfkeys: tikz/diamond` (S14/01). C'est un autre cas, qui
  nécessite probablement `\usetikzlibrary{shapes.geometric}`. Une fois
  v0.8.4 déployé, le `[log]` de cette notion permettra de confirmer le
  diagnostic et de produire un v0.8.5 ciblé si tu veux.

**Bilan estimé après v0.8.4** : sur les 64 notions N10, environ 60
devraient passer en succès (43 avant + 17 fix tikz babel + 4 fix
critère vide), restent ~4 cas qui nécessitent du contenu BDD à corriger.

---

## Comment tester chez toi

Comme pour v0.8.2, il faut **invalider le cache** avant de relancer pour
que les atomes soient effectivement recompilés (sinon ils restent en
statut `cache` avec leur ancien hash défaillant). Soit tu supprimes les
PDFs du cache :

```
rm appli/data/cache_rendus/*.pdf appli/data/cache_rendus/*.log
```

soit tu sais qu'un seul caractère modifié dans le préambule (par exemple
ce patch lui-même qui ajoute `\usetikzlibrary{babel}`) invalide tous les
hashes — donc le cache est de facto invalidé après ce patch sans rien
faire de plus.

Une fois la compilation relancée, les fichiers `.tex` et `.log` des
échecs restants (s'il en reste) sont accessibles via le lien `[log]`
dans la liste, comme en v0.8.3.
