# Redémarrage v0.27.2 — Décalage par « semaines neutralisées » (progression principale)

Implémente la spécification `doc/spec_decalage_semaines_neutralisees.md`
(validée). Un décalage se comporte désormais comme une **période de vacances
insérée** : il neutralise des semaines de cours, que les créneaux enjambent.

## Ce qui change

Avant : un décalage déplaçait un créneau **en bloc** (+N×7 jours sur début et
fin). Un créneau enjambant la date de décalage glissait entièrement, et les
décalages cumulés se télescopaient.

Maintenant : un décalage **neutralise la/les semaine(s) de cours** contenant
l'indisponibilité (Qb). Une semaine neutralisée est **transparente** (comme les
vacances) ; les créneaux l'enjambent (semaines de cours de part et d'autre).
Les dates des créneaux sont recalculées en **semaines de cours effectives**
(algorithme §9 de la spec) :
- le début saute les semaines neutralisées qui le précèdent ;
- la fin s'étale sur le nombre de semaines de cours du créneau, en sautant les
  semaines neutralisées ET de vacances → « étirement ».

Exemple validé (cas réel S03) : S03 sur les semaines du 07 et du 14, décalages
+1 au 11/09 et +1 au 22/09 → **S03 sur les semaines du 14 et du 28**, la semaine
du 21 transparente. (Avant : 21 et 28, avec un trou.)

## Périmètre

- **Progression principale UNIQUEMENT** (créneaux datés sur des semaines).
- **PAS la progression MER** : elle se compte à la séance ; les indisponibilités
  y retirent déjà des séances de la projection, donc le décalage à la séance est
  déjà correct et intrinsèque (remarque de l'utilisateur, intégrée à la spec
  §10).

## Affichage

Une semaine neutralisée porte un marqueur « ⤵ Décalage : <motif> » (couleur
indisponibilité), et n'affiche pas les créneaux (transparence). Deux décalages
neutralisant la même semaine → union (comptée une fois, Q2).

## Fichiers

- `static/atelier_progression.js` : `_creneauxAffichage` réécrit
  (`_appliquerNeutralisations`, `_semainesNeutralisees`, `_lundiDe`,
  `_lundisAnnee`) ; `_creneauxDeLaSemaine` saute les semaines neutralisées ;
  `_semaineNeutralisee` / `_motifNeutralisation` ; marqueur dans `_ligneSemaine` ;
  invalidation des caches dans `_chargerDecalages`.
- `services/decalage_progression.py` : fonctions pures réécrites
  (`semaines_neutralisees`, `appliquer_decalages` avec calendrier), miroir de
  la logique JS.
- `tests/test_v0_21_4_decalage_progression.py` : cas A/B/C + union + copie.
- `doc/spec_decalage_semaines_neutralisees.md` : spec (référence).

## Tests

- `tests/test_v0_21_4_decalage_progression.py` : 6 passed (cas A/B/C de la spec,
  union des semaines, copie non destructive).
- pytest ciblé (décalage/progression/mer) : 271 passed. vitest : 193 passed.
  Algorithme vérifié en simulation sur les cas A/B/C.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.27.1.

## Hors périmètre (rappel)

Le choix « absorber » (réduire le nb de séances au lieu de décaler) reste non
implémenté ; à faire si le besoin se confirme.
