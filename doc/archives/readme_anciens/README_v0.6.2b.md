# seqenseigne v0.6.2b — patch UI

Trois corrections UI isolées, aucun changement côté backend ou base.

## Corrections

### 1. Doublon de toolbar (cause des comportements bizarres)

Le HTML contenait **deux fois** les trois select `annee-sel`, `classe-sel`,
`seq-sel` : une toolbar globale au-dessus des sous-onglets, et une
deuxième à l'intérieur de "Suivi des séquences". En HTML, deux éléments
avec le même `id` font que `getElementById` ne retourne que le premier ;
les mises à jour du JS pouvaient cibler l'un, l'utilisateur interagir
avec l'autre. D'où la perception "les select marchent bien mais rien ne
se passe" — c'était vrai pour celui qui servait de décoration.

**Correction** : la toolbar globale est supprimée. Les trois select
vivent désormais uniquement dans le sous-onglet "Suivi des séquences",
où ils ont leur raison d'être.

### 2. Gestion des classes — vue globale

`renderClassesList()` affichait uniquement les classes présentes dans
`CLASSES`, qui est filtré par l'année active. Résultat : dans "Gestion
des classes", on ne voyait que les 3 classes de 2025-2026 au lieu des 20
réellement présentes en base.

**Correction** : la fonction est devenue `async` et appelle désormais
`/api/classes` sans filtre d'année. Le sous-onglet affiche **toutes** les
classes de toutes les années, triées par année décroissante puis par
nom. Le header détail inclut maintenant l'année entre parenthèses pour
distinguer les classes de même nom.

### 3. Créneau : plantage sur `prog-form-partie`

Le JS lisait/écrivait dans un champ `prog-form-partie` qui n'existait
plus dans le template HTML, ce qui provoquait `null.value` à la
sélection d'un créneau dans la Progression annuelle.

**Correction** : les deux références au champ disparu sont supprimées.
La valeur `partie` d'un créneau est conservée telle quelle en base (le
JS ne la touche plus).

## Fichiers

Deux fichiers à remplacer :

```
appli/static/app.js
appli/templates/index.html
```

## Déploiement

1. Copier les 2 fichiers vers `D:\Enseignement\seqenseigne\appli\`.
2. Redémarrer Flask (Ctrl+C puis relance).
3. Rafraîchir le navigateur avec **Ctrl+F5** (indispensable, sinon le
   cache navigateur sert l'ancien app.js).

## Ce qu'il reste à regarder (plus tard)

Un bug de données relevé au passage : les objectifs non-01 affichent
`\seqObjectifGetNom{02}` au lieu du vrai nom. Ça vient du référentiel
importé qui ne résout pas ces macros. À traiter séparément — ça n'a
rien à voir avec la refacto v0.6.2.
