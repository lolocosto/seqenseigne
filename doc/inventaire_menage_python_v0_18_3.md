# Inventaire D8 — ménage des fichiers Python (racine, scripts/, outils/)

Document de **travail** établi en v0.18.3. **Aucune suppression ni déplacement
n'a été effectué** : ce fichier sert de base de décision pour un ménage
ultérieur (à valider fichier par fichier). La classification repose sur
l'analyse des imports réels (`grep` des `import`/`from` dans tout le dépôt).

Légende :
- **RUNTIME** : importé par l'app (routes/services) → NE PAS toucher.
- **TESTÉ** : importé par la suite de tests → garder (déplacement possible mais
  imports de tests à mettre à jour).
- **OUTIL CLI** : script autonome lancé à la main, non importé → candidat à
  conservation dans `outils/` ou archivage.
- **ONE-SHOT** : migration/diagnostic ponctuel, probablement périmé → candidat
  à archivage (`doc/archives/` ou dossier `scripts/_archive/`).

## Racine de appli/

| Fichier | Classe | Détail |
|---|---|---|
| `app.py` | RUNTIME | Point d'entrée Flask. Reste à la racine. |
| `scanner_latex.py` | RUNTIME+TESTÉ | Importé par `importers/scanner_latex.py` et des tests. NE PAS toucher. |
| `migrer.py` | TESTÉ | Importé par 3 tests (schéma, renommage, v2). Garder ; déplacement délicat (imports tests). |
| `importer_arborescence.py` | TESTÉ | Importé par `tests/test_import_arborescence.py`. Garder. |
| `clean_cache.py` | OUTIL CLI | Non importé. Référencé seulement dans de vieux READMEs archivés. Candidat archivage. |
| `query_paquet.py` | OUTIL CLI | Non importé, aucune référence doc. Candidat archivage. |
| `reparer_progression_id.py` | ONE-SHOT | Non importé. Référencé dans READMEs v0.6.x archivés. Réparation ponctuelle ancienne → candidat archivage. |

## scripts/

| Fichier | Classe | Détail |
|---|---|---|
| `migration_images.py` | RUNTIME | Importé par `routes/rendu_atome.py`. NE PAS toucher. |
| `peuplement_14_paquet_vers_base.py` | RUNTIME | Importé par `services/admin.py` et `services/livret_plans_de_travail.py`. NE PAS toucher. |
| `peupler_cartes_n10.py` | RUNTIME | Importé par `services/cartes_automatisme.py`. NE PAS toucher. |
| `cartes_n10_data.py` | RUNTIME (indirect) | Importé par `peupler_cartes_n10.py` (lui-même runtime) + un test. Garder. |
| `purger_fiches.py` | TESTÉ | Importé par `tests/test_purger_fiches.py`. Outil de maintenance pérenne. Garder. |
| `lister_atomes_orphelins.py` | TESTÉ | Importé par `tests/test_v0_10_7_badges_et_orphelins.py`. Garder. |
| `migrer_v0_13_5_2.py` | TESTÉ | Importé par un test. ONE-SHOT historique mais couvert par test. À conserver tant que le test existe. |
| `migrer_xint_eval_vers_the_expr.py` | TESTÉ | idem. |
| `peuplement_01_migrer_schema.py` | TESTÉ | Importé par 2 tests. Garder. |
| `peuplement_11_migrer_schema_cycle.py` | TESTÉ | Importé par `tests/test_R1_schema.py`. Garder. |
| `peuplement_14_verif_couverture.py` | TESTÉ | Importé par un test + `peuplement_14_rapport_dette.py`. Garder. |
| `peuplement_14_rapport_dette.py` | OUTIL CLI | Non importé directement (importe verif_couverture). Diagnostic. Candidat archivage si la dette est soldée. |
| `creation_livret_N10_S01.py` | ONE-SHOT | Non importé. Script de création ponctuel N10/S01. Candidat archivage. |
| `diagnostic_livret_N10_S01.py` | ONE-SHOT | Non importé. Diagnostic ponctuel. Candidat archivage. |
| `lister_exos_R.py` | OUTIL CLI | Non importé. Diagnostic exos R. Candidat archivage (ou à garder si utile au quotidien). |
| `migration_v0_13_4_1_dates_fin.py` | ONE-SHOT | Non importé. Migration datée périmée. Candidat archivage. |

## outils/

| Fichier | Classe | Détail |
|---|---|---|
| `verifier_md5.py` | RUNTIME+TESTÉ | Importé par `peupler_cartes_n10.py` et un test. Pilier des livraisons. NE PAS toucher. |
| `archiver_docs.py` | TESTÉ | Importé par `tests/test_v0_15_4_archiver_docs.py`. Garder. |
| `importer_referentiel_externe.py` | TESTÉ | Importé par un test. Garder. |
| `diagnostic_cartes_validation.py` | OUTIL CLI | Non importé. Diagnostic pérenne. Garder dans outils/. |
| `migrer_serie_ea_vers_ae.py` | OUTIL CLI | **Nouveau v0.18.3.** Migration EA→AE. Garder (réutilisable sur D:/E:). |

## Synthèse des candidats à archivage (à valider)

Sans aucun impact runtime ni test, donc archivables en sécurité :
- Racine : `clean_cache.py`, `query_paquet.py`, `reparer_progression_id.py`
- scripts/ : `creation_livret_N10_S01.py`, `diagnostic_livret_N10_S01.py`,
  `migration_v0_13_4_1_dates_fin.py`, `peuplement_14_rapport_dette.py`
  (si dette soldée), `lister_exos_R.py` (si plus utilisé)

**Décision attendue de Laurent** : valider l'archivage fichier par fichier, et
choisir la destination (`doc/archives/scripts_obsoletes/` ? suppression pure ?).
Le déplacement effectif fera l'objet d'une livraison dédiée (avec
`MANIFEST_SUPPRESSIONS.md` + commandes PowerShell prêtes à coller, selon le
protocole habituel).
