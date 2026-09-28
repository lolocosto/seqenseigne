# Redémarrage v0.32.12 — Retrait du panneau « Livrets distribués aux élèves »

Suppression du panneau de droite « Livrets distribués aux élèves » dans Suivi de
classe → Progression principale.

## Motivation

Ce panneau (lecture seule) listait les documents du référentiel verrouillé lié à
la progression. Il faisait doublon avec l'atelier Conception de référentiel
(« Documents à publier »), où cette information est déjà présente et suffisante.
Le retirer libère de la place pour le calendrier et le détail du créneau.

## Changements

- Panneau HTML `prog-docs-bloc` (« Livrets distribués aux élèves ») supprimé.
- Les deux appels à `_chargerDocuments()` (qui remplissait ce panneau) sont
  neutralisés. La fonction elle-même est laissée en place (inoffensive, plus
  appelée) pour limiter le risque de régression.

Sans effet sur la saisie « Documents à distribuer » (dans le détail du créneau)
ni sur le calendrier, qui restent en place.

## Fichiers

- `templates/index.html` : panneau retiré.
- `static/atelier_progression.js` : appels à `_chargerDocuments` neutralisés.

## Tests

- `node --check` (exit 0). vitest : 193 passed. Page vérifiée : panneau absent,
  calendrier et saisie docs présents.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.32.11.
