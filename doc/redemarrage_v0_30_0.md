# Redémarrage v0.30.0 — Tableau de bord (socle, écran d'accueil)

Premier volet du tableau de bord : un nouvel onglet « Tableau de bord », placé
en tête et servant d'écran d'accueil, avec deux tuiles fixes. La
configurabilité (activer/réordonner les tuiles) et les tuiles restantes
viendront ensuite.

## Contenu

Onglet principal **« Tableau de bord »** (premier, actif par défaut). Grille de
tuiles responsives. Deux tuiles dans cette version :

- **Séances de la semaine** (suivi) : les séances de la semaine en cours, toutes
  classes, regroupées par jour. Chaque séance porte sa classe, son créneau et
  son type (Cours / MER auto / MER prog selon l'affectation de la classe).
- **Conception — atomes à finaliser** : pour chaque niveau, le nombre d'atomes
  encore « en cours » par type (notions, méthodes, exercices, cartes). Représente
  le travail de conception restant. « Rien à finaliser » si tout est validé.

## Architecture

- `services/tableau_bord.py` (nouveau) : agrégats (pur / requêtes) —
  `atomes_en_cours_par_niveau`, `seances_de_la_semaine`. Le tableau de bord ne
  fait qu'afficher ces données (pas de calcul métier côté client).
- `routes/tableau_bord.py` (nouveau) : API (2 endpoints).
- `app.py` : blueprint `bp_tableau_bord`.
- `templates/index.html` : onglet + panneau `tab-accueil` (2 tuiles) ; l'onglet
  « Suivi de classe » n'est plus l'écran par défaut.
- `static/tableau_bord.js` (nouveau) : rendu des tuiles.
- `static/app.js` : init du tableau de bord au démarrage et à l'ouverture de
  l'onglet.

## Tests

- `tests/test_v0_30_0_tableau_bord.py` : 3 passed (agrégat atomes par
  niveau/type, tout validé → total 0, structure séances de la semaine).
- vitest : 193 passed. Vérifié sur la base réelle : atomes en cours (ex. 6ème,
  4ème, 3ème avec leurs décomptes) et séances de la semaine.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. L'écran
d'accueil est désormais le tableau de bord.

## Suite

- Tuiles restantes : « éléments non rattachés » (à définir : ce que « rattaché »
  signifie précisément) et « derniers résultats d'évaluation » (à définir :
  quels résultats, quelle fenêtre).
- Puis configurabilité : activer/désactiver et réordonner les tuiles (approche B
  validée).
