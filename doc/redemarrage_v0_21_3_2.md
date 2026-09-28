# Redémarrage v0.21.3.2 — Dette : plus d'année scolaire codée en dur

Corrige la dette technique des années scolaires codées en dur (repérée après le
passage à 2026-2027). Désormais, aucun repli ne fige une année : il est calculé
depuis la date, donc ne se périme jamais.

## Le problème

Des valeurs `'2025-2026'` étaient codées en dur comme repli :
- `static/edt.js` et `static/indispo.js` : fallback `window.ANNEE_COURANTE ||
  '2025-2026'` (introduit lors de la création de ces écrans).

Ces replis ne servaient que si aucune année n'était encore résolue, mais ils se
périmaient chaque année scolaire.

## Le correctif

Nouvelle fonction de calcul de l'année scolaire courante, des deux côtés :

- **JS** (`static/app.js`) : `anneeScolaireCourante()` → "AAAA-AAAA" selon la
  date (septembre→décembre = N/N+1 ; janvier→août = (N-1)/N).
- **Python** (`services/annees_scolaires.py`) : `annee_scolaire_de_date(date)`
  avec la même convention.

Les replis d'année dans `edt.js`/`indispo.js` utilisent maintenant, dans
l'ordre : l'année globale `ANNEE_ACTIVE` si définie, sinon
`anneeScolaireCourante()`. Plus aucune année en dur.

Côté Python, `annees_scolaires.courante()` continue de lire la config
`annee_courante` en priorité (donc TON réglage fait foi), et ne se replie sur le
calcul que si la config ne définit rien (ex. fichier absent).

## Ce qui N'est PAS touché

- `config/annees_scolaires.json` : c'est ta donnée, éditée à la main. Elle
  n'est pas incluse dans la livraison. Ton réglage `annee_courante` reste la
  source de vérité.

## Fichiers

- `static/app.js` : `anneeScolaireCourante()`.
- `static/edt.js`, `static/indispo.js` : replis sans année en dur.
- `services/annees_scolaires.py` : `annee_scolaire_de_date()` + repli de
  `courante()`.

## Tests

- vitest : 193 passed (0 régression). Syntaxe JS OK.
- Calcul d'année vérifié aux bornes (31 août → année précédente ; 15 septembre →
  nouvelle année), JS et Python.
- `courante()` lit toujours la config en priorité.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Se déploie par-dessus la
v0.21.3.1. Ne pas écraser ton `config/annees_scolaires.json` (non inclus).

## Suite

- v0.21.1 : effet des indisponibilités sur la progression principale.
