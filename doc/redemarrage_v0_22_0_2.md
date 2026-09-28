# Redémarrage v0.22.0.2 — Correctif : créneaux « à dater » inaccessibles

Correctif d'un bug de l'atelier Progression, révélé sur la progression
2026-2027. Purement front (un fichier).

## Le bug

Sur une progression où des créneaux existent **sans date** (« à dater »), il
était impossible de les positionner :

- un créneau sans date n'apparaît **pas dans le calendrier** (le calendrier
  n'affiche que les créneaux datés) ;
- cliquer la partie correspondante dans la barre latérale appelait **toujours**
  `poserPartie`, qui **crée un nouveau créneau** — donc recliquer sur une partie
  déjà « à dater » créait un doublon au lieu d'ouvrir le créneau existant.

Résultat : un créneau « à dater » n'avait aucun point d'entrée pour recevoir une
date → il restait inaccessible. La progression 2025-2026 n'était pas touchée car
ses créneaux étaient déjà datés (importés), donc présents dans le calendrier et
sélectionnables.

## Le correctif

Le clic sur une partie dans la barre latérale passe désormais par
`cliquerPartieSidebar(seq, partie)` :

- si un **créneau existe déjà** pour cette partie (placée, même « à dater »), on
  le **sélectionne** — le panneau de détail s'ouvre, permettant de saisir les
  dates, éditer ou retirer le créneau ;
- sinon (partie non encore placée), on **crée** le créneau (`poserPartie`,
  comportement d'origine).

Le panneau de détail (dates Début/Fin, bouton Retirer) était déjà fonctionnel :
il suffisait de pouvoir y accéder pour un créneau non daté.

## Fichiers

- `static/atelier_progression.js` : `cliquerPartieSidebar` (routage
  sélection/création) + `onclick` de la barre latérale.

## Tests

- vitest : 193 passed (0 régression). Logique de routage vérifiée (créneau à
  dater → sélection ; créneau daté → sélection ; partie absente → création).
- Diagnostic confirmé sur une copie de la base réelle : progression 2026-2027 =
  9 créneaux sans date (S01–S09), état `en_cours`, académie présente,
  `_estModifiable` = vrai côté données — le blocage était bien le routage du
  clic, pas les données ni les droits.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Se déploie par-dessus la
v0.22.0.1. Après déploiement : sur la progression 2026-2027, cliquer une partie
« à dater » (S01–S09) ouvre son détail pour la dater ; cliquer une partie non
placée (S10–S14) la crée.
