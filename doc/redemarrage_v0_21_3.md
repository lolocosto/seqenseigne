# Redémarrage v0.21.3 — Sélecteurs du Suivi : refactor déclaratif (modèle Référentiel)

Réécrit la gestion des sélecteurs du Suivi annuel sur le **modèle déclaratif de
la Conception de référentiel** (`ATL_PORTEES[...].selecteurs` +
`atelRenderSelecteursPortee`). Remplace l'approche par pools multiples de
v0.21.2. Comportement fonctionnel identique à la cible v0.21.2, mais code plus
homogène avec le reste de l'appli et plus maintenable.

## Principe

Chaque onglet déclare sa liste de sélecteurs dans `SUIVI_ATELIER_PANNEAU` :

```
edt:         { panneau:'edt',         selecteurs:['etablissement'] }
indispo:     { panneau:'indispo',     selecteurs:['etablissement'] }
progression: { panneau:'progression', selecteurs:['etablissement','niveau','referentiel'] }
suivi:       { panneau:'suivi',       selecteurs:['classe'] }
classe/etab: { ..., selecteurs:[] }
```

Un **pool unique** (`#suivi-selecteurs-pool`) contient tous les labels
contextuels, chacun typé `data-suivi-sel="<type>"`. `suiviRenderSelecteurs`
déplace dans la barre 1, dans l'ordre déclaré, les labels de l'onglet actif,
puis les remet au pool au changement d'onglet. Les `<select>` conservent leurs
IDs et handlers métier (déplacement, pas recréation) — indispensable pour
`prog-sel-niveau`/`prog-sel-ref` (câblés à ATELIER_PROGRESSION) et `classe-sel`.

L'**Année** reste un sélecteur **global** à droite de la barre 1 (hors liste
`selecteurs`), visible en Suivi annuel, masquée en Gestion. L'**Établissement**
est global et **mémorisé** (localStorage `suivi-etab-actif`), partagé par EdT /
Indispo / Progression — même établissement d'un onglet à l'autre.

## Nettoyage

- L'ancien pool `#suivi-etab-pool` et les doubles labels année/étab du pool
  progression sont supprimés. Le pool progression ne garde que les `<select>`
  internes `prog-sel-annee`/`prog-sel-etab` (masqués, pilotés par les globaux).
- Plus de doublon d'ID (niveau/référentiel ne sont plus déclarés deux fois).

## Fichiers

- `templates/index.html` : pool unifié `#suivi-selecteurs-pool` (labels typés) ;
  pool progression réduit ; suppression de `#suivi-etab-pool`.
- `static/app.js` : `selecteurs` dans `SUIVI_ATELIER_PANNEAU` ;
  `suiviRenderSelecteurs` déclaratif ; `SUIVI_ETAB_ACTIF` mémorisé ;
  `suiviRemplirAnneeGlobale` / `suiviRemplirEtabGlobal` /
  `suiviAnneeGlobaleChange` / `suiviEtabGlobalChange` /
  `_suiviAppliquerGlobaux` / `suiviRechargerAtelierActif`.
- `tests_js/suivi_navigation.test.js` : DOM + assertions adaptés au pool
  unifié (types de sélecteurs par onglet).

## Tests

- vitest : 193 passed (dont 12 de navigation, réécrits pour vérifier la liste
  ordonnée des types de sélecteurs par onglet). Aucun doublon d'ID dans la page.
  L'app démarre, pool unifié présent.

## À VÉRIFIER manuellement (runtime non cliquable ici)

- changement Année globale / Établissement global → rechargement de l'onglet
  actif et persistance de l'établissement d'un onglet à l'autre ;
- atelier Progression : Niveau / Référentiel pilotent bien l'atelier ;
- Année masquée en Gestion.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`.

## Suite

- v0.21.1 : effet des indisponibilités sur la progression principale.
