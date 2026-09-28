# Redémarrage v0.34.1 — Sélecteur d'année dans le Suivi de classe

Ajoute un sélecteur d'année scolaire au bandeau du Suivi de classe, pour accéder
à l'historique des années précédentes.

## Changement

Le sous-onglet Suivi de classe expose désormais : **Année · Établissement ·
Niveau · Classe** (l'année a été ajoutée en tête).

- Le label `annee` du pool (ex-`_annee_interne`, masqué) devient un sélecteur
  déclarable et visible ; il conserve l'id `#annee-sel` que les flux existants
  lisent (`onAnneeChange`).
- L'atelier `suivi` déclare `['annee', 'etablissement', 'niveau', 'classe']`.
- Changer l'année réinitialise la classe, recharge les classes de l'année et
  refiltre la liste (mécanisme `onAnneeChange` existant). Combiné aux filtres
  Établissement/Niveau (v0.34 étape A), on sélectionne sans ambiguïté une classe
  d'une année passée (historique).

Le sélecteur est déjà peuplé par `chargerAnnees` (toutes les années + « Toutes
les années »), donc aucun câblage supplémentaire de données.

## Fichiers

- `templates/index.html` : label `data-suivi-sel="annee"` (visible, déclarable).
- `static/app.js` : atelier `suivi` déclare le sélecteur `annee`.
- `tests_js/suivi_navigation.test.js` : tests adaptés (Suivi = annee+etab+niveau
  +classe ; comptage des labels du pool).

## Tests

- vitest : 195 passed. Vérifié : label `annee` déclarable, présent dans le
  bandeau du Suivi.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Ctrl+Shift+R.
Se déploie par-dessus la v0.34.0.
