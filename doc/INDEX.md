# seqenseigne — Index de la documentation

> Carte de la documentation au 2 juin 2026 (v0.15.4).
>
> v0.15.4 a fait le ménage : ~ 215 notes historiques ont été déplacées dans `archives/`. Le dossier `doc/` ne contient plus que la documentation **vivante**.

## 1. Documentation vivante (à consulter en référence)

| Fichier | Rôle | Maintenu jusqu'à |
|---|---|---|
| [`README.md`](README.md) | Point d'entrée : vision, statut, architecture, stack, démarrage, roadmap | v0.15.4 |
| [`CONVENTIONS.md`](CONVENTIONS.md) | Conventions de code et de livraison (ZIP, MANIFEST.md5, style, tests) | v0.15.4 |
| [`GOTCHAS.md`](GOTCHAS.md) | Pièges connus (LaTeX, SQLite, MiKTeX, JS, …) avec résolutions | v0.15.4 |
| [`DETTE_TECHNIQUE.md`](DETTE_TECHNIQUE.md) | Dette identifiée à traiter, classée par chantier | v0.15.4 |
| [`NETTOYAGE.md`](NETTOYAGE.md) | Éléments à nettoyer dans la base de code | v0.15.4 |

**Conseil de lecture pour un nouveau venu** :
1. `README.md` (vision + architecture)
2. `CONVENTIONS.md` (comment on livre, comment on teste)
3. `GOTCHAS.md` (pièges à éviter)

## 2. Notes de livraison vivantes (v0.15.*)

Les notes de redémarrage de la série v0.15 sont conservées à la racine de `doc/` car le chantier v0.15 est en cours. Convention : `redemarrage_vX_Y_Z*.md`.

Une note par version livrée. Ces fichiers sont **figés à la version livrée** : on n'y revient pas pour les modifier, ils servent d'historique factuel.

| Plage | Thème principal |
|---|---|
| v0.15.0–v0.15.1 | Refonte des séries d'exercices, F/A/E |
| v0.15.2.* | Validation référentiel, figeage minimal puis complet (JSON + PDFs), import rétroactif de référentiels externes, restructure trace JSON (schéma v2), correction placement fiches |
| v0.15.3 | Renommage des états référentiel (fige → verrouille, ajout utilise), bloc UI affichage données verrouillées |
| v0.15.4 | Doc refondue, archivage, JSON dépliable complet, suppression bloc « Éléments à inclure » |

## 3. Archives — `archives/`

Les ~ 215 fichiers archivés (notes de livraison antérieures à v0.15, README de chantiers fermés, patches anciens, scoping de chantiers livrés, notes ponctuelles, anciennes versions du CDC) sont déplacés dans `archives/<catégorie>/`. Voir `archives/INDEX_ARCHIVES.md` pour le détail.

Catégories :

| Sous-dossier | Type |
|---|---|
| `redemarrages_anciens/` | Notes de livraison v0.5 → v0.14 (figées) |
| `readme_anciens/` | README de chantiers R1-R4 + de versions v0.5-0.11 |
| `patches/` | Notes de patch d'anciennes versions |
| `chantiers/` | Notes du chantier 14 (closed) |
| `notes/` | Notes ponctuelles (fix cache USB, recapcours, …) |
| `archives_cdc_doc/` | Anciennes versions du CDC / doc technique / use cases |
| `scoping/` | Notes de cadrage de chantiers livrés |
| `pilotage/` | Finalisations, reprises de session |

Ces fichiers ne sont **jamais** modifiés rétroactivement. Pour les retrouver : `grep -r mot-clé doc/archives/` ou navigation par sous-dossier.

## 4. Comment maintenir cet index

À chaque livraison v0.15.X :
- Ajouter une ligne dans la section 2 si nouveau thème majeur.
- Si des canoniques sont modifiées en profondeur, noter la version de maintien.

Quand on archive de nouveaux fichiers (en lançant `outils/archiver_docs.py`) :
- L'index `archives/INDEX_ARCHIVES.md` est régénéré automatiquement par le script.
- Pas besoin de modifier cet INDEX.md.
