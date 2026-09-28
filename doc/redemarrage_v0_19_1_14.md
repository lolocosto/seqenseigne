# Redémarrage v0.19.1.14 — Détail créneau : afficher la période en trimestres

Correctif d'affichage dans l'atelier Progression.

## Problème

Dans le détail d'un créneau (panneau de droite), la période ne s'affichait pas
pour les années organisées en **trimestres** (T1/T2/T3). Le sélecteur de période
retombait sur « — Non affectée — ».

## Cause

Le `<select>` de période (`#prog-form-periode`) ne proposait que les options
**semestre** (`Sem1`, `Sem2`, `FinAnnee`) : les options **trimestre**
(`T1`, `T2`, `T3`) avaient été oubliées lors de l'ajout des semestres. Comme
`select.value = 'T1'` ne correspond à aucune option, le champ restait sur la
première (« Non affectée »), et la période n'apparaissait pas.

## Correctif

Ajout des options `T1`/`T2`/`T3` au sélecteur, regroupées par `<optgroup>`
(Trimestres / Semestres) pour la lisibilité. Toutes les valeurs de période
présentes en base (`T1`, `T2`, `T3`, `Sem1`, `Sem2`, `FinAnnee`) sont désormais
couvertes : plus aucune période ne retombe silencieusement sur « Non affectée ».

## Changements (fichiers)

- `templates/index.html` : options `T1`/`T2`/`T3` ajoutées au select
  `#prog-form-periode`, avec `<optgroup>`.

Aucun changement de code JS ni de modèle.

## Tests

Changement HTML statique. vitest → 192 passed (aucune régression).

## Déploiement

Aucune migration. Décompresser le delta sur D:/E:, puis
`python -m outils.verifier_md5`. Dans « Suivi de classe » > Progression, le
détail d'un créneau d'une année en trimestres affiche désormais correctement
T1/T2/T3.
