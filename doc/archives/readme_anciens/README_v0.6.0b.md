# seqenseigne v0.6.0b — Patch cumulatif sur v0.6.0

Deux correctifs par rapport à la v0.6.0 initiale, incluant celui déjà
proposé en v0.6.0a :

## 1. Identifiant de référentiel compact (nouveau)

**Problème** : l'identifiant encodait l'année scolaire complète
(`N11_v2024-2025`), alors que l'intention est de figer l'année de
**mise en place** du référentiel. Un même référentiel peut servir sur
plusieurs années scolaires consécutives (cas observé : programme N11
inchangé depuis 2023-2024, utilisé aussi en 2024-2025 et 2025-2026 →
le nom devrait refléter 2023, pas un millésime glissant trompeur).

**Correction** : l'identifiant utilise maintenant l'année civile de
rentrée :

- `N11_v2021` (référentiel mis en place à la rentrée 2021)
- `N11_v2024b` (2ème référentiel mis en place à la rentrée 2024,
  quand un programme différent coexiste dans la même année scolaire)

La colonne `referentiel_niveaux.version` stocke maintenant `"2024"` au
lieu de `"2024-2025"`.

## 2. « Vider le suivi » efface aussi progressions + créneaux (v0.6.0a)

**Problème** : dans v0.6.0, cliquer « Vider le suivi » effaçait classes,
élèves, niveaux, mais laissait **progressions** et **créneaux** en base,
rendant l'état incohérent.

**Correction** : `reset_suivi` vide maintenant en plus `progressions`,
`creneaux`, `creneau_objectifs_exos`. Les référentiels versionnés
restent intacts (ils sont immuables et peuvent resservir à un
ré-import).

## Tests

**310 tests verts** (308 v0.6.0 + 1 pour le reset étendu + 1 pour le
nouveau cas "référentiel partagé entre 2 années scolaires").

Nouveaux tests notables :
- `test_retrouver_ou_creer_reutilise` vérifie l'id `N11_v2024`
- `test_retrouver_ou_creer_contenus_differents` vérifie le suffixe
  `N11_v2024b`
- `test_annees_scolaires_distinctes_meme_contenu` : importer la
  même structure en 2023-2024 puis en 2024-2025 → un seul référentiel
  `N11_v2023` utilisé les deux fois.
- `test_reset_suivi_vide_progressions_et_creneaux` : validation que
  le reset touche tout le suivi sauf les référentiels.

## Fichiers modifiés par rapport à v0.6.0

```
appli/importers/referentiel_builder.py  ← extraction année civile de rentrée
appli/persistence/sqlite_store.py       ← reset_suivi étendu
appli/tests/test_referentiels.py        ← assertions + nouveau test
appli/tests/test_sqlite_store.py        ← test reset étendu
```

## Déploiement

1. Dézipper l'archive à la racine de `D:\Enseignement\seqenseigne\`.
2. Effacer la base (les identifiants actuels ont l'ancien format) :
   ```
   del data\seqenseigne.db
   ```
   Pas besoin de toucher `.db-wal` / `.db-shm` — ils n'existent peut-être
   pas selon l'état du WAL.
3. Réimporter :
   ```
   python importer_arborescence.py --racine D:\Enseignement_old
   ```
4. Vérifier les nouveaux ids dans le récap final et dans la base :
   ```
   ..\outils\SQLite\sqlite3 data\seqenseigne.db "SELECT id, niveau, version, verrouille FROM referentiel_niveaux ORDER BY niveau, version;"
   ```
   Attendu : identifiants compacts `N11_v2021`, `N10_v2024`, etc.
   Un même référentiel peut être rattaché à plusieurs progressions
   (années scolaires différentes, même contenu).
