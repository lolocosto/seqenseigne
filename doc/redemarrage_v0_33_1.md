# Redémarrage v0.33.1 — Correctif : onglet Suivi vide (init() planté)

Corrige le bug des onglets « Suivi » (et Gestion) vides, apparu avec la
réorganisation v0.33.0.

## Cause racine

`_appliquerDeeplink()` référençait la variable `atelier` sans la définir : la
ligne `const atelier = params.get('atelier')` (et le court-circuit `if (!atelier)
return`) avaient été perdus lors d'une refonte antérieure du deeplink (v0.30.1).

Au chargement, `init()` appelle `_appliquerDeeplink()` → `ReferenceError:
atelier is not defined` → **`init()` s'interrompt**. Les onglets qui
s'initialisent à leur propre clic (Conception, Admin…) fonctionnaient quand
même, mais l'onglet « Suivi », qui dépend de la fin de `init()`, restait vide.
La réorganisation v0.33.0 a rendu le symptôme visible (avant, le défaut tombait
ailleurs).

## Correctif

Restauration, en tête de `_appliquerDeeplink` :
```
const atelier = params.get('atelier');
if (!atelier) return;   // pas de deeplink → sortie silencieuse (cas normal)
```

## Fichiers

- `static/app.js` : `_appliquerDeeplink` — définition de `atelier` restaurée.
- `tests_js/deeplink_atelier_defini.test.js` (nouveau) : non-régression.

## Tests

- vitest : 195 passed (dont 2 nouveaux). Vérifié en jsdom avec le vrai
  index.html : `init()` ne lève plus d'erreur et le clic sur « Suivi » affiche
  bien `stab-suivi`.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.33.0. Recharger le navigateur (Ctrl+Shift+R) après déploiement.
