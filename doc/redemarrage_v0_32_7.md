# Redémarrage v0.32.7 — Documents « Non compilé » pour référentiels importés verrouillés

Corrige l'affichage « Non compilé » des documents de référentiels importés
(état verrouillé/utilisé) dont les PDF sont pourtant figés.

## Cause (diagnostic confirmé avec l'utilisateur)

Les référentiels des années précédentes ont été importés directement en état
verrouillé/utilisé, **avec leurs PDF figés** dans
`data/referentiels/<ref_id>/_verrouille/pdfs/`. Mais l'import n'a jamais
positionné `compile_ok`/`compile_date` sur les documents (ces champs relèvent de
la compilation « vivante », un chemin de code distinct du verrouillage). Comme
l'état effectif se fiait à `compile_ok`, les documents s'affichaient
« Non compilé » alors que leurs PDF existent.

(Les PDF ne sont pas dans les zips envoyés — l'utilisateur les retire pour la
taille — mais ils existent bien sur son disque, cf. capture `_verrouille/pdfs/`.)

## Correctif

`etat_effectif_document` accepte désormais un `data_dir` optionnel. Quand un
document n'est pas compilé (`compile_date` absent) MAIS que son référentiel est
`verrouille`/`utilise` ET que TOUTES les cibles du document ont leur PDF figé
présent dans `_verrouille/pdfs/`, l'état renvoyé est **`ok`** (au lieu de
`non_compile`). Sinon, comportement inchangé. Sans `data_dir` (rétrocompat), la
vérification est sautée.

## Fichiers

- `services/referentiel_documents_compilation.py` : `_pdfs_figes_presents` +
  `etat_effectif_document(..., data_dir=None)`.
- `services/referentiel_documents.py` : `lister_documents(..., data_dir=None)`
  transmet `data_dir` au calcul d'état.
- `routes/referentiel_documents.py` : passe `store.data_dir`.
- `tests/test_v0_32_7_etat_verrouille.py` (nouveau, 3 cas).

## Tests

- `tests/test_v0_32_7_etat_verrouille.py` : 3 passed (verrouillé + PDF figés →
  ok ; verrouillé sans PDF → non_compile ; sans data_dir → ne plante pas).
- pytest : 3958 passed (hors dettes préexistantes ci-dessous). vitest : 193.
- Vérifié sur N11_v2025 (PDF figés simulés) : livret_sequence → ok,
  livret_cours (sans PDF) → non_compile.

## Portée

Correction d'affichage (logique d'état). Les documents concernés apparaîtront
« OK » dans l'atelier Référentiel, dans « Documents à publier » et dans le suivi
de classe (livrets distribués). Aucune modification de données ni recompilation
nécessaire.

## Dettes préexistantes (rappel, non traitées ici)

- `tests/test_v0_29_0_verso_miroir.py` : importe une fonction supprimée (refactor
  antérieur) → casse la collecte pytest ; à supprimer/réécrire.
- `tests/test_annees_scolaires.py` (2 cas) : attendent « 2025-2026 » comme année
  courante, dépendants de la date système ; à corriger.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.32.6. Les documents des référentiels verrouillés/utilisés dont
les PDF figés existent s'affichent « OK ».
