# Redémarrage v0.27.0.3 — Plannings via le viewer pdf.js (vrai affichage dans l'appli)

Corrige (pour de bon) l'affichage des plannings dans le Suivi de classe. La
cause profonde n'était pas l'en-tête HTTP (v0.27.0.2) mais la **méthode
d'affichage** : les atomes, eux, passent par un viewer pdf.js embarqué.

## La vraie cause

Les plannings utilisaient `<iframe src="/api/…planning.pdf">` : affichage PDF
**natif** du navigateur, qui — selon la configuration — confie le PDF au lecteur
système.

Le rendu d'atome (qui s'affiche correctement) n'utilise PAS l'affichage natif :
il fetch le PDF en **blob**, crée une URL blob locale, et la charge dans le
**viewer pdf.js embarqué** (`/static/vendor/pdfjs/web/viewer.html?file=…`). Ce
viewer JavaScript rend le PDF dans la page, indépendamment de la config du
navigateur. C'est ce qui avait demandé un effort particulier à l'époque.

## Le correctif

Nouveau helper `afficherPdfDansAppli(iframe, url)` (dans `app.js`) : fetch du
PDF en blob → viewer pdf.js. Repli sur l'affichage natif en cas d'échec.

Les plannings l'utilisent :
- planning des automatismes (`mer.js`) ;
- planning de progression MER, théorique et par classe (`progression_mer.js`).

## Fichiers

- `static/app.js` : helper `afficherPdfDansAppli`.
- `static/mer.js` : planning automatismes via le viewer.
- `static/progression_mer.js` : planning MER via le viewer.

## Tests

- vitest : 193 passed (0 régression). Syntaxe OK. Viewer pdf.js servi (200).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Se déploie par-dessus la
v0.27.0.2. Les plannings s'affichent désormais dans l'appli (viewer pdf.js),
comme les rendus d'atomes.

## Suite

- v0.27.1 : effet fin des indisponibilités sur la progression MER (absorber /
  décaler).
