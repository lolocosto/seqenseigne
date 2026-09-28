# Redémarrage v0.17.4 — Correctif aperçu au survol : 405 sur atome compilé

## Symptôme

Aperçu PDF au survol (v0.17.3) :
- atome NON compilé → bouton « Générer l'aperçu » OK, compile et affiche ;
- atome DÉJÀ compilé → message « Aperçu non disponible » + erreur serveur
  `"GET /api/atomes/exercice/ex_xxx/rendu-pdf HTTP/1.1" 405`.

## Cause

Pour un atome en cache, `_afficherApercuPdf` (dans `AtelierAssemblage`) faisait
un `GET /api/atomes/<type>/<id>/rendu-pdf` pour récupérer le PDF. Or cette route
n'accepte que **POST** (méthode 405 = Method Not Allowed). Il n'existe pas de
GET pour le PDF : c'est le POST qui sert le PDF — depuis le cache s'il est
valide (instantané, `compiler_atome` gère le cache via `resultat.depuis_cache`),
sinon en compilant. J'avais supposé à tort qu'un GET existait.

## Correctif

`static/atelier_assemblage.js` — `_afficherApercuPdf` utilise désormais
`POST` (comme le chemin « Générer »). Pour un atome en cache, le POST renvoie
le PDF immédiatement sans recompiler. Une seule ligne change (méthode HTTP).

## Tests

- **Vitest** : 87 passed (86 + 1 nouveau).
  - `tests_js/apercu_survol.test.js` : nouveau test « cache_valide=true →
    récupère le PDF via POST /rendu-pdf (pas GET) » qui incarne le correctif
    (vérifie explicitement que la méthode est POST, pour empêcher la
    réapparition du 405).
- **pytest** : inchangé (3793/7/0) — backend non touché, seule la méthode HTTP
  côté client change.
- **Syntaxe** : node --check OK.

## À vérifier côté Windows

1. Survoler un atome DÉJÀ compilé (sidebar seqniv) ~1,5 s → l'aperçu PDF
   s'affiche immédiatement dans la modale (plus de message « non disponible »,
   plus de 405 dans les logs).
2. Atome non compilé → toujours le bouton « Générer l'aperçu » (inchangé).
