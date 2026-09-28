# Redémarrage v0.24.0 — Onglet « Mises en route » + planning des automatismes (frise)

Premier volet du chantier MER côté usage : un onglet dédié « Mises en route »
qui rend la configuration et le planning bien visibles, et un nouveau planning
des automatismes en « frise chronologique ».

## Onglet « Mises en route »

Nouvel onglet principal (entre « Suivi de classe » et « Conception de
référentiel »), avec deux zones :

- **Zone A — Configuration par classe** : pour l'établissement/année choisis, la
  liste des classes avec, pour chacune, une case « fait des MER » et le mode
  (Automatismes / Progression / Panaché). Édition directe (remplace l'accès
  enfoui via Gestion › Classes ; le bloc du détail classe reste en place et
  fonctionnel, les deux vues partagent les mêmes champs `mer_active`/`mer_mode`).
- **Zone B — Planning des automatismes** : sélection d'une classe en mode
  automatismes → affichage du PDF A3 **en ligne** (iframe, comme le rendu des
  atomes) + lien « Ouvrir le PDF (A3) ».

Les modes « progression » et « panaché » sont proposés dans le sélecteur mais
seront pleinement exploitables une fois les référentiels de séquences de MER en
place (chantier suivant).

## Nouveau planning des automatismes (frise)

Le PDF A3 paysage adopte le modèle demandé :
- dates alignées à l'horizontale (ex. « lun 14/09 »), retour à la ligne
  automatique ;
- une bande centrée entre deux barres horizontales pour chaque période de
  vacances (« Vacances de la Toussaint »…) ;
- sous chaque date : les enveloppes à réviser en **chiffres entourés** (pifont
  ①②③④), ou « férié », ou ∅ (indisponibilité) ;
- une ligne par période de cours (entre deux vacances).

## Fichiers

- `services/planning_leitner_detaille.py` (nouveau) : assemble la frise
  (blocs période / vacances, enveloppes, fériés, indispos). Pur, testé.
- `services/planning_automatismes_tex.py` (réécrit) : génère le LaTeX frise
  (pifont, bandes de vacances, dates horizontales). A3 paysage.
- `routes/leitner.py` : `_collecter` (récupération partagée) + route PDF qui
  assemble les blocs.
- `templates/index.html` : onglet + panneau `tab-mer` (zones A et B), rôle ARIA
  onglet, inclusion `mer.js`.
- `static/mer.js` (nouveau) : logique de l'onglet (config par classe, planning).
- `static/app.js` : init de l'onglet MER à son ouverture.
- `tests/test_v0_24_0_planning_detaille.py` (nouveau, 3 cas).

## Tests

- `tests/test_v0_24_0_planning_detaille.py` : 3 passed (périodes séparées par
  vacances, enveloppes sous les séances, férié marqué un jour de cours).
- vitest : 193 passed (0 régression). Syntaxe OK, onglet servi.
- Génération LaTeX vérifiée par compilation réelle : PDF A3 paysage, dates
  horizontales, enveloppes ①②③④ (pifont), bande de vacances. (En sandbox,
  avertissement babel `french` sans conséquence ; OK avec MiKTeX.)

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration (colonnes
`mer_active`/`mer_mode` déjà en place depuis v0.22.0). Onglet « Mises en route ».

## Suite

- Référentiels externes (docs PDF/ODT de collègues, intégrés « validés », état
  potentiellement incomplet accepté) — à cadrer, débloque le mode progression
  et la zone « planning des progressions de MER ».
- Puis panachage automatismes / progression (affectation par séance sur l'EdT).
