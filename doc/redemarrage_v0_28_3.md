# Redémarrage v0.28.3 — Détail de classe (Gestion) : cadre « Élèves » unifié, cadres MER et Rythme retirés

Refonte de l'écran de détail d'une classe (Gestion › Classes).

## Changements

1. **Cadre « Élèves » unifié** : l'import CSV (Pronote), l'ajout manuel et la
   liste des élèves (avec compteur et bouton « Vider ») sont regroupés dans un
   seul cadre « Élèves », au lieu de trois cadres séparés.

2. **Cadre « Mises en route (MER) » retiré** : redondant avec l'onglet « Mises
   en route » du Suivi annuel, qui gère désormais toute la configuration MER
   (type, affectation, plannings).

3. **Cadre « Rythme de séances (A/B) » retiré** : obsolète. Le rythme se déduit
   de l'EdT hebdomadaire détaillé ; le comptage manuel A/B ne servait plus
   (aucun calcul métier ne l'utilisait). Confirmé avec l'utilisateur.

Les champs en base (`seances_A`, `seances_B`, `mer_active`, `mer_mode`) sont
**conservés** (pilotés ailleurs / réversibles) ; seule leur UI dans le détail de
classe est retirée.

## Fichiers

- `templates/index.html` : détail de classe réorganisé (cadre « Élèves »
  unifié ; cadres MER et Rythme supprimés).
- `static/app.js` : remplissage rythme/MER retiré de `selectClasse` ; fonctions
  mortes supprimées (`_majBlocMer`, `sauverMerClasse`,
  `ouvrirPlanningAutomatismes`, `sauverRythmeClasse`).

## Tests

- `node --check static/app.js` : OK (exit 0). vitest : 193 passed.
- Page rendue vérifiée : cadre « Élèves » unifié présent (import + ajout +
  liste) ; cadres MER et Rythme absents ; aucune référence morte hors
  commentaires.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration (champs en base
conservés). Se déploie par-dessus la v0.28.2.
