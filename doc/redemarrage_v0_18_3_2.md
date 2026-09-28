# Redémarrage v0.18.3.2 — Correctif préfixe série AE (atelier exercice)

Correctif de la v0.18.3.1, qui avait introduit une régression : après celle-ci,
les exos d'approche tombaient dans la série « Avancée » **partout** (N09 et
N10), au lieu de leur bucket « Approche (AE) ».

## Cause (que la v0.18.3.1 avait manquée)

La route de liste de l'atelier exercice renvoie un **contrat à 6 clés sans
`serie_code` ni `serie`** : la série est encodée comme **préfixe du champ
`code`** (`F01`, `A03`, `E02`, `R05`, et `AE01` pour l'approche). Le bucketing
résolvait ce préfixe avec `ex.code.charAt(0)` — donc `'AE01'` était lu comme
`'A'` et rangé dans **Avancés**. La v0.18.3.1 avait bien renommé les buckets en
`AE`, mais la résolution `charAt(0)` ne pouvait jamais produire `'AE'` : le
bucket `AE` restait vide et tous les AE allaient en `A`.

## Correctif (`static/atelier_exercice.js`)

Nouveau helper `AtelierExercice.prefixeSerie(code)` qui reconnaît les préfixes
à **deux lettres** (`AE`) avant ceux à une lettre (`F`/`A`/`E`/`R`), via
`/^(AE|[FAER])/`. Il remplace `ex.code.charAt(0)` dans les deux endroits qui
résolvaient le code série : le bucketing de `rendreSidebar` et la déduction du
badge dans `rendreItem`.

  'AE01' → 'AE'   |   'A01' → 'A'   |   'F03' → 'F'   |   'E02' → 'E'   |   'R05' → 'R'

## Tests

`tests_js/atelier_exercice_bucket_ae.test.js` enrichi (9 cas au total) :
- constantes série en `AE` (volets 1) ;
- helper `prefixeSerie` : `AE` reconnu avant `A`, codes vides/inconnus → '' ;
- **bucketing fonctionnel** (volet 3, nouveau) : montage réel de la classe +
  appel de `rendreSidebar` avec des exos au format backend (`code: 'AE01'`),
  vérifiant que les AE vont dans le bucket `AE` et **jamais** dans `A`. C'est
  le test qui faisait défaut en v0.18.3.1.

**Zéro régression** : vitest → 145 passed (14 fichiers). Aucun fichier Python
modifié (pytest inchangé, 3832 passed).

## Déploiement

Correctif purement front. Suppose toujours la migration de données v0.18.3
appliquée (`outils/migrer_serie_ea_vers_ae.py`). À tester sur N09 et N10 : les
exos `AExx` doivent figurer dans la section « Approche (AE) » et ne plus
apparaître dans « Avancés ».
