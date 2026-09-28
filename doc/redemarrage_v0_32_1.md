# Redémarrage v0.32.1 — Planification hebdo : navigation corrigée + survol enrichi

Corrige le bug de navigation entre semaines et enrichit l'aperçu au survol.

## Bug corrigé — navigation entre semaines

Passer à la semaine suivante/précédente calculait un mauvais lundi (ex. dimanche
2026-09-20 au lieu du lundi 2026-09-21). Cause : le calcul JS créait la date en
heure **locale** puis la reconvertissait en **UTC** (`toISOString`), ce qui
décalait d'un jour selon le fuseau (UTC+2 l'été).

Correctif : arithmétique de date en **UTC pur** (`_planifAjouterJours`, via
`Date.UTC`), sans effet de fuseau. Vérifié : 14/09 +7 = 21/09 (y compris en fuseau
Europe/Paris), franchissements de mois et d'année corrects.

## Survol enrichi

Au survol d'une séance, l'aperçu (title) affiche désormais la classe **et** le
type (Cours / MER auto / MER prog), plus « indisponible » le cas échéant — au
lieu du seul nom de classe.

## Fichiers

- `static/planification_hebdo.js` : `_planifAjouterJours` (calcul UTC),
  `planifSemaine` simplifiée, survol enrichi.

## Tests

- `node --check` (exit 0) + exécution OK. vitest : 193 passed. Helper de date
  vérifié (avec et sans fuseau).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Purement front. Se déploie
par-dessus la v0.32.0.

## Suite (v0.32.2) — détail enrichi (en attente d'une précision)

Le détail d'une séance montrera :
- **MER** (gras) : automatismes → enveloppes à réviser (avec leurs numéros) ;
- **Principal** (gras) : code + nom de séquence (avec 1ère/2ème partie le cas
  échéant), numéro de séance (et son rang depuis le début).
Réutilisera `leitner.enveloppes_a_reviser`, la partie des créneaux et le rang de
séance. À préciser : « numéro de séance depuis le début » = rang dans la partie
de séquence.
