# Redémarrage v0.49.2 — Onglet unique « Référentiel » (étape C)

## Décisions validées

- Conception › Niveau : **un seul sous-onglet « Référentiel »** remplace
  « Référentiel » et « Référentiel externe ». Il reste dans la portée Niveau
  (un référentiel concerne un niveau) : la liste montre les référentiels du
  niveau choisi en haut à droite.
- **Liste à gauche** : tous les référentiels du niveau — internes et
  externes, principaux et MER (ancien modèle de MER compris, marqué
  « — ancien modèle », tant qu'il n'est pas recréé).
  - Filtres **Année**, **Type**, **Source** (le niveau est celui de la
    portée).
  - Pour chaque filtre sans valeur choisie, **groupage dans cet ordre** :
    année, puis type, puis source.
- **Création** : source (interne / externe) + type (principal / MER) +
  description ; nom calculé.
- **Détail à droite** selon la source : interne → détail historique (états,
  éligibilité, documents compilés…) ; externe → éditeur commun (v0.48.6 /
  v0.49.0) ; ancien modèle de MER → éditeur historique.

## Code

- `static/referentiel_unifie.js` (nouveau) : `refuInit`, `refuRendre`
  (filtres, groupage récursif), `refuChoisir`, `refuCreer` ; prise en charge
  de `atelRefRendreSidebar` (la liste commune remplace la liste interne) et
  enchaînement après `atelRefInit`.
- `templates/index.html` : barre latérale de l'onglet (filtres, création),
  conteneur `#refu-ext` du détail externe ; bouton « Référentiel externe »
  masqué (le panneau reste dans le DOM pour ses fonctions).
- `static/app.js` : portée Niveau = Évaluation, Référentiel.
- `static/referentiel_pe.js` : rafraîchit l'onglet unique après chaque action.
- `static/app.css`.

## Tests

- Pas de changement serveur ; pytest 4170 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur : deux sous-onglets seulement ; groupage année → type
  → source ; création d'un interne (détail historique affiché) ; filtre
  Source = Externe puis sélection d'une MER (éditeur commun).

## Suite

- D : découpage progressif du détail interne en blocs communs (structure,
  documents, états) — à étaler.
- Retrait de l'ancien modèle de MER après recréation par l'auteur.
