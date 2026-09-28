# Redémarrage v0.16.10 — Correctifs onglet Rendu PDF du seqniv + bandeau

Livraison de correctifs faisant suite au déploiement de v0.16.9. Trois points :
le bandeau aligné sur l'évaluation (remarque post-v0.16.9), le PDF qui
s'ouvrait en fenêtre externe, et le 404 du plan de travail.

## 1. Bandeau du seqniv aligné sur l'atelier Évaluation

Remarque Laurent après v0.16.9 : badge « modifié » absent et aspect du bandeau
différent des autres ateliers. Cause : j'avais fabriqué un bandeau seqniv
« maison » (IDs/classes ad hoc, pas de badge modifié) au lieu de reprendre
celui des évaluations.

Correctif :
- `templates/index.html` — toolbar du seqniv refaite à l'identique de l'éval :
  `liv-atl-toolbar-title`, `liv-atl-badge-modifie` (classe **`atl-badge-modifie`**),
  `liv-atl-etat-badge` (classe **`atome-etat-badge`**), boutons
  `liv-atl-btn-valider` et `liv-atl-btn-save` (classes `btn-sm`/`btn-prim`).
  Pas de bouton Supprimer/LaTeX (sans objet pour le seqniv).
- `static/atelier_seqniv_assemblage.js` — `majToolbar()` réécrite en réplique
  fidèle de la base : badge modifié, badge état (classes + libellés
  « Validé »/« Valider »/« Repasser en cours » identiques aux atomes), verrou
  lecture seule + classe `.asm-verrou-structure`, bouton save (display +
  `disabled` selon `modifie`). `_appliquerEtatSequence()` délègue à
  `majToolbar()`. Suppression du CSS maison `.asm-etat-badge--*` devenu inutile
  (on réutilise `.atome-etat-badge`). `app.js` : id de titre adapté
  (`liv-atl-titre` → `liv-atl-toolbar-title`).

## 2. PDF du livret en fenêtre externe → viewer pdf.js

Symptôme : le PDF compilé d'un livret de séquence s'ouvrait dans une fenêtre
externe au lieu de l'iframe intégrée (Firefox du PC de travail).

Cause : le seqniv affichait le PDF via `iframe.src = blobUrl` (affichage natif),
détourné par le Firefox de l'établissement. Les autres ateliers (atomes, éval)
utilisaient déjà depuis v0.16 le **viewer pdf.js embarqué**
(`static/vendor/pdfjs/web/viewer.html`) qui dessine le PDF dans un `<canvas>`
— donc rendu inline garanti.

Correctif : `_livretSeqAfficherPdf` appelle désormais la méthode héritée
`_afficherPdfDansViewer(iframe, blobUrl)` (d'`AtelierEditeur`), comme les autres
ateliers. Pas de duplication : on réutilise l'existant. S'applique au livret de
séquence ET au plan de travail (même méthode d'affichage).

## 3. 404 du plan de travail → route séquence réintroduite

Symptôme : « Compiler le plan de travail » → `POST /api/plans-de-travail/N10/S10/pdf`
renvoie 404.

Cause : en v0.15.1, les routes `/api/plans-de-travail/*` ont été supprimées
(l'atelier « Référentiel > Documents à publier » couvrait alors le livret
annuel). Mais le bouton « Compiler le plan de travail » de l'onglet Rendu PDF
du seqniv est resté — il pointait vers une route disparue. (Un `.pyc` orphelin
de l'ancienne route traînait dans `routes/__pycache__/`.)

Décision Laurent : réintroduire la route séquence pour faire remarcher le
bouton (plutôt que retirer le bouton). Le service
`generer_plan_de_travail_sequence` n'avait jamais été supprimé — seule la
couche HTTP manquait.

Correctif :
- `routes/plans_de_travail.py` — **recréé**, portée SÉQUENCE uniquement :
  - `POST/GET /api/plans-de-travail/<niveau>/<sequence_code>/pdf`
  - `POST/GET /api/plans-de-travail/<niveau>/<sequence_code>/tex`
  Réutilise `generer_plan_de_travail_sequence` + `compiler_atome`, pattern
  aligné sur `routes/livret_sequence.py` (helpers config/cache, validation de
  surface, codes 200/400/404/422/503). Le livret annuel reste géré par
  l'atelier Référentiel — on ne réintroduit PAS la portée niveau.
- `app.py` — import + enregistrement du blueprint `bp_plans_de_travail`.

## Tests

- **pytest** : 3796 passed, 7 skipped, 0 failed.
  - `tests/test_v0_16_10_route_plan_travail_sequence.py` (nouveau) : route
    enregistrée, 400 niveau invalide, 404 séquence inconnue, génération .tex
    sur une séquence peuplée, GET supporté.
  - `tests/test_v0_15_1_chantiers.py` (mis à jour) : `plans_de_travail.py` n'est
    plus attendu absent (réintroduit) ; recap_cours/recap_exos restent
    supprimés ; nouveau test vérifiant la portée séquence (`<sequence_code>`).
- **Vitest** : 67 passed (inchangé — le correctif PDF ne casse aucun test ;
  l'affichage viewer n'est pas unit-testé, validé visuellement).
- **Syntaxe** : node --check (JS) + ast.parse (Python) OK ; route vérifiée
  fonctionnellement (200 + .tex de ~21 ko sur N10/S10).

## Note / dette

- Un `.pyc` orphelin `routes/__pycache__/plans_de_travail.cpython-313.pyc`
  existait avant cette livraison (vestige de la route supprimée en v0.15.1).
  Il est désormais cohérent avec le `.py` réintroduit. (Les `__pycache__` ne
  sont pas livrés dans le ZIP de toute façon.)
- Le blob PDF du livret est géré par `this._livretBlobUrl` ET, via le viewer,
  par `iframe._seqBlobUrl`. Double gestionnaire du même blob → au pire une
  double révocation inoffensive (try/catch). Pas de fuite ni de crash.

## À vérifier côté Windows (validation visuelle)

1. Bandeau du seqniv : badge « modifié » apparaît à la saisie, badge état et
   boutons identiques visuellement aux autres ateliers.
2. Compiler un livret de séquence → PDF affiché DANS l'iframe (plus de fenêtre
   externe).
3. Compiler le plan de travail d'une séquence → PDF affiché dans la même
   iframe (plus de 404). Tester notamment N10/S10.
4. Une séquence sans partie → message 404 « séquence introuvable » propre
   (toast), pas d'erreur silencieuse.
