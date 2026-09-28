# Redémarrage v0.21.5.1 — Décalages : champ élargi + date corrigée

Deux corrections d'affichage sur la v0.21.5. Purement front (un fichier).

## 1. Champ « nb de semaines » élargi

Sur le contrôle « décaler [N] sem. » d'une indisponibilité, le champ numérique
était trop étroit (34 px) : les flèches du sélecteur poussaient le nombre hors
de la zone visible. Élargi à 52 px (police 11 px) — le nombre reste visible.

## 2. Date corrigée dans le panneau « Décalages de la classe »

Le libellé affichait « À partir du **undefined**/15/09 » : le motif de date ne
capturait pas l'année (regex à 2 groupes au lieu de 3). Corrigé : affiche
maintenant « À partir du 15/09/2025 ».

(Le format `jj/mm` du calendrier, volontairement sans année, n'est pas
concerné.)

## Fichiers

- `static/atelier_progression.js` : largeur du champ nb semaines ; regex de date
  du panneau des décalages (capture de l'année).

## Tests

- vitest : 193 passed (0 régression). Format de date vérifié
  (2025-09-15 → 15/09/2025). Syntaxe OK.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Purement front.
