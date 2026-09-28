# Redémarrage v0.28.1.2 — Correctif : liste de configuration par classe réapparaît

Correctif d'un défaut introduit lors de la réparation v0.28.1.1 : la « Configuration
par classe » (choix du type de MER) ne s'affichait plus dans l'onglet « Mises en
route ». Purement front (un fichier).

## Cause

La réparation précédente avait mal reconstruit la jonction entre deux fonctions
de `static/mer.js` : `merCyclerAffectation` était tronquée et le corps de
`merRenderClasses` s'était retrouvé collé à l'intérieur, sans son entête
`function merRenderClasses()` ni sa déclaration `const zone`. Résultat :
`merRenderClasses` n'existait plus → la liste des classes (checkbox « fait des
MER » + choix du mode) ne s'affichait pas.

## Correctif

Les deux fonctions sont correctement séparées et complètes :
`merCyclerAffectation` (cycle + persistance de l'affectation) et
`merRenderClasses` (tableau de configuration par classe). Vérifié : les deux
fonctions sont définies, `node --check` sans erreur, exécution du fichier OK.

## Fichiers

- `static/mer.js` : jonction `merCyclerAffectation` / `merRenderClasses` réparée.

## Tests

- `node --check static/mer.js` : OK. Exécution : OK. Les deux fonctions
  présentes.
- vitest : 193 passed.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Purement front. Se déploie
par-dessus la v0.28.1.1. La configuration par classe réapparaît.

## Remarques en attente (non traitées ici — à cadrer)

- Rendu semaine A/B en demi-colonnes dans la grille d'affectation EdT (comme
  l'EdT enseignant).
- Déplacement du planning MER de l'onglet « Progression de MER » vers « Mises en
  route », conditionné au type de MER (masqué si « aucun »).
- (Rappel : les indisponibilités de classe se saisissent dans l'onglet
  « Indisponibilités » en choisissant la portée « classes ».)
