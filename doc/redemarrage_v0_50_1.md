# Redémarrage v0.50.1 — Plans de classe imprimables sans LaTeX

Suite du chantier v0.50 (cadrage : `doc/redemarrage_v0_50_0.md`, D4).
v0.50.0 (plannings) testée par l'auteur sous Firefox : rendu validé.

## Décisions

- D4 — Plans de classe en HTML + SVG, une page A4 portrait par plan ; même
  contenu que l'ancien rendu TikZ : tableau en haut, places tournées, noms
  (prénom / nom sur deux lignes), **gras** = placé par l'enseignant,
  *italique* = place libre à confirmer, numéros des places vides (en gris
  quand des élèves sont placés), places AESH, liste des non placés, légende.
- Les textes restent droits (seuls les rectangles tournent) ; un nom trop
  long pour la place est compressé (`textLength`).
- Transition (D6) : lien discret « ancien PDF » dans la barre d'outils du
  plan, retiré en v0.50.2 avec `plan_classe_pdf.py`.

## Code

- `services/impression.py` : `plan_svg(plan)` (repère de l'éditeur = repère
  SVG : cm de salle, y vers le bas, angle horaire ; viewBox en cm de salle,
  taille en cm de papier ≤ 17 × 21 cm).
- `templates/impression/plans_classe.html` (nouveau).
- `static/impression.css` : section « Plans de classe » (une page par plan).
- `routes/plans_classe.py` : `_plans_a_imprimer()`, route
  `/impression/plans-classe?classe_id=&salle_id=&lundi=` (sans `classe_id` :
  toutes les classes de la salle cette semaine).
- `static/plans_classe.js` : « Imprimer ce plan » / « Imprimer les plans de
  la salle » ouvrent la page HTML (nouvel onglet) ; lien « ancien PDF ».
- `static/app.css` : style du lien de transition.

## Tests

- `tests/test_v0_50_1_impression_plans.py` (jeu de la salle 302 réelle) :
  33 places comme le TikZ, styles, AESH, non placés, rotation, nom long
  compressé, proportions et taille de page, route (une classe, salle,
  salle sans plan, 404), échappement.
- Chromium : deux plans → deux pages A4.

## Suite

- v0.50.2 : retrait de `planning_automatismes_tex.py`, `planning_mer_tex.py`,
  `plan_classe_pdf.py`, des routes `.pdf` correspondantes et des liens
  « ancien PDF » ; adaptation des tests (capture v0.41.1 : entrées `tex_*` ;
  tests TikZ des plans) ; doc.
