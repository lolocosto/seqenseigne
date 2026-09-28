# Redémarrage v0.31.1 — Tuile « Éléments non rattachés »

Ajoute la tuile « Conception — éléments non rattachés » au tableau de bord, avec
action par type (comme la tuile « atomes à finaliser »). Complète le filtre
livré en v0.31.0.

## Contenu

Nouvelle tuile : pour chaque niveau, le nombre d'atomes **non rattachés** (liés à
aucun objectif) par type (notions, méthodes, exercices, cartes, fiches).
« Tout est rattaché » si rien à faire.

Chaque nombre par type est **cliquable** : ouvre l'atelier du type, niveau voulu,
**toutes les séquences**, avec le filtre **« Non rattachés » pré-activé**. On
tombe directement sur les atomes à rattacher.

## Architecture

- `services/tableau_bord.py` : `atomes_non_rattaches_par_niveau` — compte, par
  niveau et par type, les atomes dont `liens` est vide (réutilise
  `lister_atomes_sequence` en mode toutes séquences, qui fournit `liens` pour les
  5 types).
- `routes/tableau_bord.py` : `GET /api/tableau-bord/atomes-non-rattaches`.
- `templates/index.html` : tuile `tdb-non-rattaches`.
- `static/tableau_bord.js` : `tdbChargerNonRattaches` (rendu + action) ; label
  « fiches » ajouté.
- `static/app.js` : `ouvrirAtelierAtomesNonRattaches` — ouvre l'atelier, toutes
  séquences, clique le bouton « Non rattachés » (via son onclick).

## Tests

- `tests/test_v0_31_1_non_rattaches.py` : 2 passed (comptage par niveau/type ;
  jamais de total 0 dans le retour). vitest : 193 passed.
- `node --check` (exit 0). Action vérifiée : niveau posé, atelier activé, bouton
  « Non rattachés » cliqué.
- Sur la base réelle : 6ème 387 (exercices), 5ème 62 (9 cartes, 26 exos, 27
  notions), 4ème 25, 3ème 33.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.31.0.

## Suite

- Tuile « Derniers résultats d'évaluation » (dernière tuile de la liste
  initiale ; à définir : quels résultats, quelle fenêtre).
- Configurabilité des tuiles (activer/désactiver, réordonner) et enrichissement
  de la barre d'actions.
