# Redémarrage v0.28.4 — Filtrage de la liste des classes

Ajoute trois filtres à la liste des classes (Gestion › Classes) : par
établissement, par année scolaire, par niveau.

## Fonctionnement

Une barre de trois sélecteurs au-dessus de la liste :
- **Établissement** : options peuplées automatiquement à partir des classes
  existantes ;
- **Année scolaire** : options peuplées automatiquement (plus récente en tête) ;
- **Niveau** : 6ème / 5ème / 4ème / 3ème.

Les filtres se combinent (ET logique). « Tous / Toutes » sur un filtre le
neutralise. La sélection est conservée lors des rafraîchissements. Un message
distinct s'affiche quand aucune classe ne correspond aux filtres (vs aucune
classe du tout).

## Fichiers

- `templates/index.html` : barre `classes-filtres` (3 sélecteurs).
- `static/app.js` : `_majOptionsFiltresClasses` (peuple étab/année),
  `_filtrerClasses` (applique les 3 filtres), `_renderClassesListFrom` filtre
  avant rendu.

## Tests

- `node --check static/app.js` : OK (exit 0). vitest : 193 passed.
- Filtres présents dans la page ; logique vérifiée (étab + niveau combinés).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.28.3.

## Noté pour la v0.29

Bug d'impression recto-verso des cartes d'automatismes : en paysage avec
retournement sur le bord court, l'ordre des rectos est inversé par rapport aux
versos (chaque verso ne tombe pas derrière son recto). À corriger dans la
génération LaTeX (ordre/miroir des pages verso).
