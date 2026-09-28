# Redémarrage v0.28.1 — Panachage MER : UI d'affectation + correctif 2 séances/jour

Deuxième volet du panachage : l'interface pour affecter chaque créneau de l'EdT
à un type de MER. Corrige aussi un bug d'affichage des plannings quand une classe
a deux séances le même jour.

## Correctif — deux séances le même jour

Les assembleurs de planning (automatismes et MER) indexaient les séances **par
date** (`{date: séance}`), ce qui écrasait la 2ᵉ séance d'un même jour : une
classe ayant cours mardi M1 **et** mardi M4 ne voyait qu'une seule séance sur le
planning.

Corrigé : indexation **par date en liste** (plusieurs séances par jour), triées
par ordre de créneau. Le planning affiche désormais une case par séance, avec le
**code du créneau** (« mar 08/09 **M1** », « mar 08/09 **M4** ») pour les
distinguer. Vérifié : M1 → ➀, M4 → ➀➁ le même jour.

## UI d'affectation (onglet « Mises en route »)

Pour la classe sélectionnée (dès qu'elle fait des MER), une carte « Affectation
des séances (sur l'EdT) » affiche la **grille EdT de la classe**
(jours × créneaux). Chaque créneau de la classe est un bouton qui **cycle** entre
les types disponibles selon le mode :
- mode **automatismes** : Auto ↔ Aucune (défaut Auto) ;
- mode **progression** : Prog ↔ Aucune (défaut Prog) ;
- mode **panaché** : Auto → Prog → Aucune (défaut Aucune).

Couleurs distinctes (bleu auto, vert progression, gris aucune) + légende.
L'affectation est persistée (API `/api/classes/<id>/affectations`) et les
plannings se rafraîchissent aussitôt (leur contenu dépend de l'affectation).

« Aucune » neutralise le créneau (pas de MER), utilisable dans tous les modes.

## Fichiers

- `services/planning_leitner_detaille.py`, `services/planning_mer_detaille.py` :
  indexation par date en liste (plusieurs séances/jour).
- `services/planning_automatismes_tex.py`, `services/planning_mer_tex.py` :
  affichage du code créneau sous la date.
- `templates/index.html` : carte `mer-affect-card` (grille d'affectation).
- `static/mer.js` : chargement + rendu de la grille, cycle d'affectation,
  persistance (format `items` + année).
- `static/app.js` : rafraîchit l'affectation au changement de classe.

## Tests

- vitest : 193 passed. pytest ciblé (panachage/affectation/planning) : 18 passed.
- Correctif 2 séances/jour vérifié (assemblage : 2 cases distinctes ; PDF : M1/M4
  affichés séparément).
- Affectation vérifiée : PUT (format `items`) persiste, GET relit.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Suivi annuel ›
Mises en route : sélectionner une classe, la grille d'affectation apparaît.

## Fin du chantier MER

Le chantier MER est complet : référentiels (internes/externes), progressions
(principale, MER par niveau), plannings (automatismes Leitner, progression MER),
indisponibilités + décalages, et panachage (affectation par créneau). Restent en
roadmap : référentiels MER internes, SEGPA, tableau de bord hebdomadaire.
