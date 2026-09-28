# Redémarrage v0.32.3 — Référentiels externes : documents annuels

Ajoute la catégorie « documents annuels » aux référentiels externes (rattachés
au référentiel, pas à une partie de séquence). Première brique du socle
documentaire, prérequis à l'association de documents aux séances.

## Modèle

Un document externe est désormais rattaché soit à une **partie** (doc de
séquence, comportement existant), soit au **référentiel** (doc annuel /
récapitulatif). La table `referentiel_externe_doc` gagne une colonne
`ref_ext_id` (migration idempotente) : un doc annuel a `ref_ext_id` renseigné et
`partie_id` vide.

## Contenu

- Service : `ajouter_doc_annuel`, `lister_docs_annuels` ; `lire` expose
  `docs_annuels` ; `supprimer` (référentiel) supprime aussi les docs annuels.
- Route : `POST /api/referentiels-externes/<rid>/docs-annuels` (import multiple).
- UI (atelier Référentiel externe) : une zone « Documents annuels » sous les
  séquences, avec import multiple, aperçu PDF inline / téléchargement, et
  suppression — comme les docs de partie.

## Fichiers

- `persistence/sqlite_store.py` : migration `ref_ext_id`.
- `services/referentiel_externe.py` : docs annuels (ajout, liste, exposition,
  suppression en cascade).
- `routes/referentiel_externe.py` : route d'import des docs annuels.
- `static/referentiel_externe.js` : zone « Documents annuels »
  (`rxtRenderDocsAnnuels`, `rxtImporterDocAnnuel`).
- `tests/test_v0_32_3_docs_annuels.py` (nouveau, 2 cas).

## Tests

- `tests/test_v0_32_3_docs_annuels.py` : 2 passed (ajout/liste/exposition/fichier
  écrit ; suppression en cascade). vitest : 193 passed.
- Circuit vérifié : migration `ref_ext_id`, ajout d'un doc annuel (affichable),
  exposition dans `lire` sans mélange avec les séquences.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. La colonne `ref_ext_id` est
ajoutée au premier lancement. Conception › Niveau › Référentiel externe : zone
« Documents annuels ».

## Suite

- v0.32.4 : exposer la catégorisation séquence/annuel des documents du
  référentiel **interne** (via leurs cibles de compilation, qui portent déjà la
  séquence ou sont « uniques » = annuelles) — pour les rendre associables.
- v0.32.5 : association des documents aux séances (pioche dans les deux sources,
  catégorisées : doc de la séquence, doc de la séquence suivante en option, doc
  annuel).
