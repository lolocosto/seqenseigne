# Redémarrage v0.32.3.2 — « Voir le PDF » : cibles exposées dans la liste des documents

Corrige (réellement) le bug 2 : le lien « Voir le PDF » des documents
multi-cibles (planches de cartes, livret de séquence, évaluations) échouait
encore.

## Cause

Le correctif v0.32.3.1 rendait la détection multi-cible dynamique côté client
(via `doc.cibles`). Mais la **liste des documents** (`GET
/api/referentiels/<id>/documents`) ne renvoyait **pas** `cibles` pour chaque
document. Le client voyait donc toujours 0 cible → lien direct sans `?cible=` →
erreur « cible requise ».

## Correctif

La route de liste enrichit désormais chaque document avec ses `cibles`
(via `lister_cibles_document`). Vérifié sur la base : les planches de cartes ont
14 cibles (une par séquence, `N11/S01`…`N11/S14`), le récap en a 1 (« unique »).
Le client (v0.32.3.1) génère alors un lien par cible pour les planches, et un
lien direct pour le récap.

## Fichiers

- `routes/referentiel_documents.py` : `api_lister` ajoute `cibles` à chaque
  document.

## Tests

- vitest : 192 passed (0 échec). Vérifié : la liste renvoie 14 cibles pour les
  planches, 1 pour le récap.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Se déploie par-dessus la
v0.32.3.1. Recompiler les planches puis « Voir le PDF » : un lien par séquence
s'affiche.

## En attente — bug 3 (récap recto/verso)

La nouvelle macro `\seqCarteRecapAjouteLigneCartes` (une ligne de 4 cartes,
versos en miroir) est en place dans le paquet. Reste à modifier le générateur
Python (`livret_cartes_recap.py`) pour l'appeler une fois par ligne au lieu de
`\seqCarteRecapAjouteCarte` 4 fois. Point à clarifier : la macro prend un seul
`(niveau, sequence, num)` pour les 4 cartes de la ligne, alors que 4 cartes
consécutives peuvent venir de séquences/numéros différents — d'où une question
sur le regroupement (par séquence, ou identifiant par carte).
