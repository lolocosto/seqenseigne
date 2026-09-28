# Redémarrage v0.27.3.1 — Correctif : créneaux absents en vue « réalisée »

Correctif du rapatriement serveur du décalage (v0.27.3). En vue « réalisée »
d'une classe, les créneaux ne s'affichaient plus (calendrier vide, seules les
semaines neutralisées apparaissaient).

## Cause

La route `/api/classes/<id>/progression-realisee` cherchait la progression via
`classe.progression_id`. Or ce champ est vide (`None`) : la progression
principale est identifiée par le triplet **(niveau, année, établissement)**, pas
par un `progression_id` porté par la classe. Résultat : progression introuvable
→ 0 créneau renvoyé → calendrier vide.

## Correctif

La route récupère désormais la progression via
`lire_progression_par_triplet(niveau, année, établissement)` — le niveau et
l'établissement étant lus sur la classe. Les créneaux (décalés côté serveur)
sont alors correctement renvoyés.

## Fichiers

- `routes/decalage_progression.py` : progression cherchée par triplet.

## Tests

- vitest : 193 passed. pytest décalage : 6 passed.
- Vérifié sur la base réelle : classe sans décalage → 19 créneaux ; classe 4E4
  (2 décalages) → 19 créneaux + 2 semaines neutralisées, S03 décalé du 14/09 au
  02/10 (semaines 14 et 28, le 21 neutralisé).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Se déploie par-dessus la
v0.27.3.
