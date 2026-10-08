# Redémarrage v0.50.0 — Plannings imprimables sans LaTeX

## Contexte

En vue de la mise en ligne, l'outil « classe » ne doit plus dépendre d'une
distribution LaTeX. Hors ateliers de conception, LaTeX ne servait qu'à trois
productions : planning des automatismes, planning MER (réel + aperçu
théorique), plans de classe. Les documents des ateliers (évaluations, plans
de travail, livrets, cartes, référentiels) restent en LaTeX (outil local).

## Décisions validées (cadrage v0.50)

- D1 — Rendu HTML côté serveur : gabarits Jinja `templates/impression/`
  (base commune + frise), feuille `static/impression.css`, routes
  `/impression/...` ; mêmes données que les anciens PDF ; échappement par
  Jinja (plus d'échappement LaTeX).
- D2 — Dans l'appli, le cadre affiche la page HTML ; boutons
  « Imprimer / PDF » (impression du seul cadre) et « Ouvrir dans un onglet ».
- D3 — Formats inchangés : automatismes et MER réel A3 paysage, aperçu
  théorique A4 portrait, plans de classe A4 (une page par plan).
- D4 — Plans de classe : SVG calculé en Python, même géométrie (v0.50.1).
- D5 — Mêmes cases (date encadrée + créneau en gras, puis contenu), fériés,
  ∅, bandeaux de vacances ; une case n'est jamais coupée entre deux pages.
- D6 — Transition : les routes PDF LaTeX restent (lien discret « ancien
  PDF ») jusqu'à leur retrait en v0.50.2.
- D7 — Tests HTML (pytest), contrôle Chromium (format, coupures) ; contrôle
  Firefox par l'auteur.
- D8 — Découpage : v0.50.0 plannings ; v0.50.1 plans de classe ; v0.50.2
  retrait des générateurs LaTeX et de leurs routes.
- Navigateur de l'auteur : Firefox. Imprimante du collège : A3 possible.

## Code

- `services/impression.py` (nouveau) : `lignes_theoriques` (plages de
  séances de l'aperçu théorique).
- `templates/impression/` (nouveau) : `base.html` (barre d'outils écran,
  `@page` par blocs `page_format` / `page_marge` / `format_libelle`, classe
  `dans-cadre` quand la page est dans un iframe), `_frise.html` (macro
  `frise(blocs, case)`), `planning_automatismes.html`, `planning_mer.html`,
  `planning_mer_theorique.html`.
- `static/impression.css` (nouveau) : cases en `inline-block` (coupure de
  page entre rangées seulement), bandeaux `break-after: avoid`, traits noirs
  sans fond (Firefox n'imprime pas les fonds par défaut).
- `routes/leitner.py` : `_blocs()` commun ; route
  `/impression/classes/<id>/planning-automatismes`.
- `routes/progression_mer.py` : `_ref_nom()`, `_planning_mer_classe()`,
  `_theorique()` communs ; routes `/impression/classes/<id>/planning-mer`
  et `/impression/progression-mer/<id>/planning-theorique`.
- `static/app.js` : `imprimerCadre(frameId)`, `afficherImpression(zone,
  frameId, titre, url, opts)`.
- `static/mer.js` (`_merFramePlanning(pfx, url, pdf, c)`),
  `static/progression_mer.js`, `templates/index.html` (boutons
  `*-print`, `*-dl`, `*-ancien`).

## Tests

- `tests/test_v0_50_0_impression.py` : même nombre de cases et de bandeaux
  que l'ancien .tex (jeu de la capture v0.41.1), symboles d'enveloppes,
  fériés / ∅, échappement, aperçu théorique, 404, gabarits sur blocs
  synthétiques. La capture `test_v0_41_1_projection_figee` est inchangée
  (le .tex reste identique).
- `tests_js/impression_cadre.test.js` : câblage du cadre et de l'impression.
- Chromium : A3 paysage 42 × 29,7 cm, A4 portrait ; planning dense sur deux
  pages sans case coupée, bandeau de vacances jamais seul en bas de page.

## Imprimer en PDF avec Firefox

Bouton « Imprimer / PDF » → destination « Enregistrer au format PDF » ;
vérifier le format (A3 paysage / A4) ; décocher « Imprimer les en-têtes et
pieds de page » (réglage retenu ensuite). Rappel affiché dans la barre
d'outils de chaque page ouverte dans un onglet.

## Suite

- v0.50.1 : plans de classe en SVG.
- v0.50.2 : retrait de `planning_automatismes_tex.py`, `planning_mer_tex.py`,
  `plan_classe_pdf.py` et des routes `.pdf` ; adaptation de la capture
  v0.41.1 (entrées `tex_*`) ; mise à jour de la doc.
