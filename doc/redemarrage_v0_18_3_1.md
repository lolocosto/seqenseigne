# Redémarrage v0.18.3.1 — Correctif affichage série approche (atelier exercice)

Correctif de la v0.18.3. Après l'unification `serie_code` → `AE`, deux
symptômes subsistaient **dans l'atelier exercice** (la sidebar d'assemblage,
elle, fonctionnait) :

1. Les exos d'approche n'apparaissaient pas du tout (ex. N10S14AE01/AE02).
2. En N09, ils étaient classés à tort dans la série « avancée »
   (ex. N09S01AE01 à AE06).

## Cause

La donnée était saine (`serie_code='AE'`, `serie='approche'` partout). Le bug
était dans le **bucketing d'affichage** de `static/atelier_exercice.js`, resté
sur l'ancienne convention `EA` :

- l'objet `buckets` et le tableau `ordre` déclaraient un bucket `'EA'`, absent
  des données → un exo de `serie_code='AE'` ne trouvait aucun bucket et tombait
  dans `'Autres'` (symptôme 1) ;
- le fallback de résolution du code (`ex.code.charAt(0)` sur un code `'AE01'`)
  renvoyait `'A'` quand `serie_code` n'était pas exploité, rangeant l'exo dans
  le bucket **A / avancés** (symptôme 2, N09) ;
- `SERIE_BUCKETS` et `SERIE_EN_CODE['approche']` pointaient encore `'EA'`.

## Correctif (`static/atelier_exercice.js`)

Quatre changements, tous dans le bucketing d'affichage (la création d'exo, qui
utilise les noms longs `fondamental`/`avancé`/`exploration`/`approche`, n'est
pas concernée) :

- `buckets = { F, A, E, AE, Autres }` (était `EA`) ;
- `ordre = ['F','A','E','AE','Autres']` (était `EA`) ;
- `SERIE_BUCKETS` : clé `AE` avec label « Approche (AE) » (était `EA` / « (EA) ») ;
- `SERIE_EN_CODE['approche'] = 'AE'` (était `'EA'`).

## Tests

`tests_js/atelier_exercice_bucket_ae.test.js` (nouveau, 5 cas) : vérifie que
les quatre constantes sont en `AE` (et plus en `EA`), que la résolution du code
lit `ex.serie_code` avant tout fallback, et que le bucket par défaut `'Autres'`
n'est atteint que pour un code inconnu.

**Zéro régression** : vitest → 141 passed (14 fichiers). Aucun fichier Python
modifié (pytest inchangé, 3832 passed à la v0.18.3).

## Rappel déploiement

Ce correctif est purement front. Il suppose que la **migration de données
v0.18.3** (`outils/migrer_serie_ea_vers_ae.py`) a bien été appliquée sur les
bases D:/E: : si des exos portaient encore `serie_code='EA'`, ils
resteraient hors du bucket `AE`. Vérifier avec un dry-run :

    python -m outils.migrer_serie_ea_vers_ae
