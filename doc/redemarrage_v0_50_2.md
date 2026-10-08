# Redémarrage v0.50.2 — Retrait de LaTeX hors ateliers

Fin du chantier v0.50 (cadrage : `doc/redemarrage_v0_50_0.md`, D6 / D8).
v0.50.0 (plannings) et v0.50.1 (plans de classe) validées par l'auteur sous
Firefox.

## Ce qui disparaît

- Générateurs LaTeX : `services/planning_automatismes_tex.py`,
  `services/planning_mer_tex.py`, `services/plan_classe_pdf.py`.
- Routes PDF : `/api/classes/<id>/planning-automatismes.pdf`,
  `/api/classes/<id>/planning-mer.pdf`,
  `/api/progression-mer/<id>/planning-theorique.pdf`, `/api/plans-classe/pdf`.
- Liens « ancien PDF » (onglet Mises en route, Progression de MER, plans de
  classe) et option `ancienId` / `ancienUrl` d'`afficherImpression`.

LaTeX ne sert plus qu'aux ateliers de conception (évaluations, plans de
travail, livrets, cartes, référentiels, compilation des atomes). L'import de
plans de salle depuis TikZ (`services/plan_salle_tikz.py`) est conservé :
c'est une lecture de fichier, pas une compilation.

## Code

- `routes/leitner.py`, `routes/progression_mer.py`, `routes/plans_classe.py` :
  routes `.pdf` supprimées, imports nettoyés ; les fonctions communes
  (`_blocs`, `_planning_mer_classe`, `_theorique`, `_plans_a_imprimer`) ne
  servent plus qu'au rendu HTML.
- `static/app.js` (`afficherImpression` sans lien de transition),
  `static/mer.js` (`_merFramePlanning(pfx, url, c)`),
  `static/progression_mer.js`, `static/plans_classe.js`, `static/app.css`,
  `templates/index.html`.

## Tests

- Capture `tests/test_v0_41_1_projection_figee.py` : entrées `tex_planning_*`
  remplacées par `html_planning_*` (pages imprimables HTML validées en
  v0.50.0) ; modification ciblée du fichier de capture, le reste est
  inchangé.
- `tests/test_v0_50_0_impression.py` : comparaison avec les blocs de frise de
  la route (plus avec l'ancien .tex).
- `tests/test_v0_39_0_plans_classe.py` : tests TikZ retirés (`TestPdf` →
  `TestImpression`) ; `tests/test_v0_40_0_mixte_aesh.py` : AESH vérifié sur
  le SVG ; `tests/test_v0_50_1_impression_plans.py` : comparaison TikZ
  retirée.
- `tests_js/impression_cadre.test.js` : test du lien de transition retiré.

## Suppressions à faire à la main

Voir `MANIFEST_SUPPRESSIONS.md` (à la racine du zip) : trois fichiers dans
`appli/services/`, en local et sur GitHub.
