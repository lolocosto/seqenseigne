# Redémarrage v0.28.2 — Réorganisation MER : A/B dans l'affectation + plannings par classe dans « Mises en route »

Traite les remarques 2 et 3 sur l'organisation des onglets MER (la remarque 1,
config par classe disparue, était corrigée en v0.28.1.2).

## Répartition des onglets (validée)

- **« Progression de MER »** (par niveau) = le *quoi* : composition de la
  progression (référentiel, pose des parties) + un **aperçu théorique** (parties
  et plages de séances, sans dates réelles).
- **« Mises en route »** (par classe) = le *comment* : configuration du type,
  affectation des séances sur l'EdT, et **plannings datés** de la classe.

Le planning daté d'une classe a donc quitté « Progression de MER » pour « Mises
en route ».

## Point 2 — Demi-colonnes semaine A/B dans l'affectation

La grille d'affectation des séances (onglet « Mises en route ») reprend le rendu
de l'EdT enseignant : une case pleine **AB**, ou deux demi-cases **A** (gauche)
et **B** (droite) séparées par un pointillé, chacune cliquable et affectable
indépendamment. Un créneau qui n'existe qu'en semaine A (ou B) n'affiche que sa
demi-case.

## Point 3 — Plannings dans « Mises en route », conditionnés au type

Dans « Mises en route », les plannings s'affichent selon le mode MER de la classe
sélectionnée :
- **automatismes** → planning des automatismes ;
- **progression** → planning des MER (progression) ;
- **panaché** → les deux ;
- **aucune / inactif** → aucune carte planning.

Les plannings sont datés (EdT de la classe + indisponibilités), affichés en
ligne (viewer pdf.js).

## Fichiers

- `templates/index.html` : carte planning MER (progression) dans « Mises en
  route » ; carte de « Progression de MER » recentrée sur l'aperçu théorique.
- `static/mer.js` : grille d'affectation avec demi-cases A/B ;
  `merAfficherPlanning` affiche auto/prog/les deux selon le mode
  (`_merFramePlanning`).
- `static/progression_mer.js` : aperçu théorique uniquement (par niveau).

## Tests

- `node --check` (exit 0) + exécution sans erreur sur `mer.js` et
  `progression_mer.js`. vitest : 193 passed. Cartes présentes.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.28.1.2.

## Suite (notée)

Refonte de l'écran détail de gestion d'une classe : cadre « liste des élèves »
(import + ajout manuel + liste), retrait du cadre « Mises en route » (redondant
avec l'onglet du suivi annuel), statut du cadre « rythme de séances » à
déterminer.
