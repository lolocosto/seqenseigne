# Redémarrage v0.32.3.1 — Docs annuels affichés + « Voir le PDF » multi-cibles

Deux correctifs.

## Bug 1 — les docs annuels externes ne s'affichaient pas

Le chargement de l'atelier « Référentiel externe » récupérait le détail complet
d'un référentiel mais ne recopiait que `sequences`, en oubliant `docs_annuels`.
Les documents annuels (bien enregistrés, présents dans l'arborescence) ne
remontaient donc pas à l'affichage. Corrigé : `docs_annuels` est repris à côté de
`sequences`.

## Bug 2 — « Voir le PDF » échouait pour les documents multi-cibles

Le lien « Voir le PDF » d'un document du référentiel interne renvoyait un lien
direct sans préciser de cible. Pour les documents à **plusieurs cibles** (une
par séquence : livret de séquence, **planches de cartes**, évaluations…), l'API
répond « cible requise ». Seuls `livret_sequence` et `evaluation` étaient gérés
(par un message « à venir »), pas les planches.

Corrigé : la détection multi-cible est désormais **dynamique** (d'après
`doc.cibles`), plus par liste de types en dur. Un document à plusieurs cibles
affiche **un lien par cible** (avec `?cible=…`) ; un document à cible unique
garde son lien direct.

## Fichiers

- `static/referentiel_externe.js` : `docs_annuels` repris au chargement.
- `static/atelier_referentiel.js` : `atelRefLienPdf` — liens par cible pour les
  documents multi-cibles.

## Tests

- `node --check` (exit 0) + exécution OK (referentiel_externe.js). vitest : 193
  passed. La route PDF accepte `?cible=<cible_id>` (format `N11/S01`).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Purement front. Se déploie
par-dessus la v0.32.3.

## En attente — réalignement recto/verso du récap de cartes (vue enseignant)

Le récap (1 exemplaire de chaque carte, vue enseignant) a le même besoin de
miroir recto/verso « bord court » que les planches (corrigées en v0.29). Mais
l'alignement recto/verso du récap est géré par la macro `seqCarteRecap` du
paquet LaTeX `seqenseigne-carte-automatisme` (.dtx), pas côté Python — contrairement
aux planches. La correction doit donc se faire dans le paquet (inverser l'ordre
des colonnes du flux verso), à confirmer.
