# Redémarrage v0.26.1 — Progressions de MER : UI + planning

Deuxième volet : l'interface des progressions de mise en route « à la séance »,
dans l'onglet « Mises en route » (mode progression), avec le planning en frise
(même forme que les automatismes).

## Contenu

Dans Suivi annuel › Mises en route, quand la classe sélectionnée est en mode
**progression**, deux nouvelles cartes apparaissent (les cartes s'affichent selon
le mode de la classe : automatismes → planning automatismes ; progression →
progression MER + planning MER) :

### Progression de mise en route
- Choix du **référentiel MER** (liste des référentiels externes **validés** du
  niveau de la classe).
- Composition de la progression : on **pose** les parties du référentiel dans
  l'ordre voulu (choix b), on les **réordonne** (↑/↓) et on les **retire** (×).
  Chaque partie consomme son nombre de séances (affiché). Total des séances
  indiqué. Les parties déjà posées ne réapparaissent pas dans les parties à
  ajouter (une partie est atomique).

### Planning de progression MER
- PDF A3 paysage en frise, **même forme** que le planning des automatismes :
  dates horizontales, sous chaque date la **partie travaillée** ce jour-là avec
  son rang (n/N), bandes de vacances, « férié » / ∅ (indisponibilité), « — »
  quand la progression est épuisée. Affiché en ligne + lien d'ouverture.

## Fichiers

- `templates/index.html` : cartes `mer-prog-card` et `mer-plan-mer-card` dans
  `stab-mer`, ids de la carte automatismes (`mer-auto-card`).
- `static/mer.js` : orchestration selon le mode ; logique progression MER
  (référentiel, pose/retrait/déplacement de parties, planning MER).
- `services/planning_mer_detaille.py` (nouveau) : assemblage de la frise MER
  (réutilise les helpers du planning Leitner).
- `services/planning_mer_tex.py` (nouveau) : générateur LaTeX A3 (partie sous
  chaque date).
- `routes/progression_mer.py` : route PDF `…/planning-mer.pdf`.

## Tests

- vitest : 193 passed (0 régression). Syntaxe OK. Zones + route présentes.
- Compilation réelle vérifiée : planning MER A3 paysage, 0 débordement, partie +
  rang (Tables 1/6…6/6, Compléments 1/4…4/4), bande de vacances, épuisement.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration (tables créées
en v0.26.0). Suivi annuel › Mises en route : mettre une classe en mode
« progression », choisir un référentiel MER validé, poser des parties.

## Prérequis d'usage

Il faut au moins un **référentiel externe de type MER, validé**, au niveau de la
classe (créé dans Conception de référentiel › Niveau › Référentiel externe).

## Suite

- Panachage automatismes / progression (affectation par séance sur l'EdT).
- Plus tard : référentiels MER conçus dans l'appli.
