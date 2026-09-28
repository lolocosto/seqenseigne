# Redémarrage v0.30.3.1 — Correctif : le niveau cliqué dans la tuile était ignoré

Correctif du bug signalé : cliquer un type (ou un niveau) dans la tuile « Atomes
à finaliser » ouvrait le bon atelier, mais toujours sur le niveau **N12**, quel
que soit le niveau cliqué (le serveur recevait `niveau=N12`).

## Cause

`ATL_SELECTIONS` (les sélections de portée : niveau, séquence) est construit
**une seule fois au chargement** de `app.js`, en lisant le localStorage. Les
fonctions d'ouverture depuis la tuile écrivaient le nouveau niveau dans le
localStorage, mais **pas dans `ATL_SELECTIONS` en mémoire**. Or c'est
`ATL_SELECTIONS` (en mémoire) qui pilote `ATL_FILTRE_NIVEAU`, donc le niveau
transmis restait l'ancien.

## Correctif

`ouvrirAtelierAtomesEnCours` et `ouvrirAtelierNiveau` mettent désormais à jour
`ATL_SELECTIONS` **en mémoire** (en plus du localStorage), et
`ouvrirAtelierAtomesEnCours` force l'application de la portée
(`atelPorteeSwitch('sequence')`) avant d'activer l'atelier — pour garantir que
`ATL_FILTRE_NIVEAU` prend bien le niveau cliqué.

## Fichiers

- `static/app.js` : `ouvrirAtelierAtomesEnCours` et `ouvrirAtelierNiveau`
  synchronisent `ATL_SELECTIONS` en mémoire ; application explicite de la portée.

## Tests

- `node --check` (exit 0). vitest : 193 passed. Logique vérifiée : mettre à jour
  `ATL_SELECTIONS.sequence.niveau` fait poser le bon `ATL_FILTRE_NIVEAU`.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Purement front. Se déploie
par-dessus la v0.30.3. Vérifier : cliquer « exercices » d'un niveau ≠ 3ème
transmet bien ce niveau au serveur (log `GET /api/exercices?niveau=...`).
