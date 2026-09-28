# Redémarrage v0.21.3.1 — Correctif : année globale ignorée par la Progression

Correctif de bug sur la v0.21.3. Purement front (un fichier + son test).

## Le bug

En basculant vers l'onglet « Progression principale », l'année affichée était
toujours 2025-2026 (l'année courante), quelle que soit l'année choisie dans le
sélecteur global.

Cause : à l'ouverture de la progression, `progInit()` peuple son sélecteur
d'année interne (`prog-sel-annee`) avec son année par défaut (l'année courante),
ce qui écrasait l'année globale. Contrairement à EdT et Indisponibilités, la
progression n'appliquait pas les sélecteurs globaux après son init.

## Le correctif

Après `progInit()`, on applique désormais les sélecteurs globaux (comme pour
EdT/Indispo) : `_suiviAppliquerGlobaux('progression')` force `prog-sel-annee` et
`prog-sel-etab` à l'année + l'établissement globaux, puis re-déclenche
`ATELIER_PROGRESSION.onSelecteurChange()` pour recharger la bonne progression.

`_suiviAppliquerGlobaux` gère maintenant le cas `progression` (en plus de edt /
indispo), et amorce l'année/établissement globaux depuis les sélecteurs de la
progression au tout premier passage si besoin.

## Fichiers

- `static/app.js` : `suiviSwitch` applique les globaux après `progInit()` ;
  `_suiviAppliquerGlobaux` étendu au cas `progression`.
- `tests_js/suivi_navigation.test.js` : le stub `progInit` retourne désormais
  une promesse (pour le chaînage `.then`).

## Tests

- vitest : 193 passed (0 régression).
- Logique du correctif vérifiée en simulation : `prog-sel-annee` est bien forcé
  à l'année globale et `onSelecteurChange` rappelé.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Se déploie directement par-dessus
la v0.21.3.

## Suite

- v0.21.1 : effet des indisponibilités sur la progression principale.
