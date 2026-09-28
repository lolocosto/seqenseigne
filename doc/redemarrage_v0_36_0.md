# Redémarrage v0.36.0 — Suivi simplifié : niveau par objectif, notes en temps réel

Deux évolutions du suivi de classe, à la demande de l'utilisateur.

## Bug corrigé — notes non recalculées en temps réel

Changer un niveau dans un sélecteur ne mettait pas à jour la note de la ligne
(il fallait quitter/revenir dans l'onglet). `setNivManuel` appelait seulement
`renderSummary()`. Corrigé : il appelle désormais `renderClasseView()`, qui
recalcule notes + résumé immédiatement.

## Simplification — saisie du seul NIVEAU par objectif

Suppression de toute la mécanique par exercice, jugée trop détaillée à saisir :
- cases à cocher des exercices (fondamental / avancé / exploration) ;
- cases à cocher des objectifs « cours » (notes cahier / fiches résumé / oral) ;
- dépliage/repliage des objectifs (boutons « Tout déplier/replier ») ;
- bouton « Calculer les niveaux depuis les exercices » (+ bandeau de confirmation) ;
- légende « Exercices » (F/A/E) devenue inutile.

Le suivi se fait maintenant par **saisie directe du niveau de maîtrise par
objectif** (sélecteur I / F / A / E / Abs / Disp), toujours visible, une colonne
par objectif. L'enseignant juge le niveau lui-même — la règle exercice→niveau
variant selon les objectifs, cette souplesse est volontaire et assumée.

Vue classe et vue élève simplifiées de la même façon. La note /20 (moyenne des
points des niveaux saisis) et le résumé de classe sont conservés.

## Roadmap

Le chantier « saisie par exercice » (ex-point 2) est ABANDONNÉ (remplacé par
cette saisie directe, plus simple). La mécanique de calcul des niveaux depuis les
exercices n'est plus utilisée.

## Fichiers

- `static/app.js` : `renderClasseView` et vue élève simplifiées ; `setNivManuel`
  rafraîchit la vue.
- `templates/index.html` : calc-bar, boutons déplier/replier et légende
  exercices retirés.

## Tests

- vitest : 195 passed. Vérifié : `setNivManuel` → `renderClasseView` ; plus de
  cases à cocher dans le rendu.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration (les données
d'exercices en base sont simplement ignorées). Ctrl+Shift+R.
