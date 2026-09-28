# Redémarrage v0.27.1 — Décalage : créneaux enjambant le seuil + bouton anti-empilement

Corrige deux problèmes du décalage de progression (principale et MER, qui
partagent la même logique).

## Bug 1 — Un créneau qui enjambe la date de décalage n'était pas décalé

Le décalage ne s'appliquait qu'aux créneaux dont la **date de début** était ≥ à
la date de décalage. Or une séquence qui **commence avant** la date de décalage
mais **se termine après** (elle enjambe le seuil) devait glisser aussi.

Exemple : S03 occupe les semaines du 07 et du 14/09 ; décalage +1 semaine à
partir du 11/09 → S03 devait passer aux semaines du 14 et du 21. Avant le
correctif, S03 restait en place (car elle commençait le 07, avant le 11).

**Correctif** : le critère porte désormais sur la **date de fin** du créneau
(`date_fin >= a_partir_de`). Un créneau qui touche ou suit la période de
décalage glisse entièrement. Corrigé côté serveur
(`services/decalage_progression.py`) ET côté client (`appliquerDecalagesJS`
dans `static/app.js`), pour la progression principale comme pour la MER.

## Bug 2 — Bouton « décaler » cliquable plusieurs fois pour la même indispo

On pouvait cliquer « décaler » plusieurs fois sur la même indisponibilité et
empiler des décalages. Désormais, si un décalage existe déjà pour une
indisponibilité (lien `indispo_id`), le contrôle est remplacé par un discret
« ✓ décalé » (le décalage reste supprimable via « Décalages de la classe »).

## Fichiers

- `services/decalage_progression.py` : critère sur la date de fin.
- `static/app.js` : `appliquerDecalagesJS` — critère sur la date de fin.
- `static/atelier_progression.js` : bouton « décaler » masqué (→ « ✓ décalé »)
  quand un décalage existe déjà pour l'indisponibilité.

## Tests

- `tests/test_v0_21_4_decalage_progression.py` : 7 passed (dont 2 nouveaux :
  créneau enjambant le seuil décalé ; créneau entièrement avant le seuil non
  décalé).
- vitest : 193 passed (0 régression).
- Cas réel vérifié : S03 (07-18/09) + décalage +1 sem au 11/09 → 14-25/09.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Se déploie par-dessus la
v0.27.0.3.

## Note

Le mécanisme « décaler » des indisponibilités fonctionne (principale et MER).
L'alternative « absorber » (réduire le nb de séances pour garder la date de fin)
n'est pas encore implémentée ; à faire si le besoin se confirme à l'usage.
