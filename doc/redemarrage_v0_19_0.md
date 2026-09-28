# Redémarrage v0.19.0 — Réalignement progression ↔ référentiel verrouillé

Première étape du chantier « Création de progression » (Phase 1 du phasage
audit → réalignement → fonctionnalités). La progression s'appuie désormais sur
le **référentiel verrouillé** en base, et l'héritage SequenceDB est retiré du
flux progression. Aucune fonctionnalité nouvelle (semaines A/B, séances
déplacées, comptage d'écart) : ce sont les v0.19.1+.

Audit de correspondance préalable : `doc/audit_v0_19_correspondance_referentiel_progression.md`.

## Décisions appliquées

- **D1** — Un créneau = une seule partie de séquence (`partie_debut ==
  partie_fin == partie`). Les objectifs du créneau sont **tous** les
  `referentiel_objectifs` du référentiel lié dont `seq_code` + `partie_numero`
  correspondent. Pas de sélection manuelle.
- **D2** — Bloc « Versions distribuées aux élèves » (ancien système de
  snapshots `/api/versions`) **remplacé** par « Livrets distribués » : affichage
  en lecture seule des `referentiel_documents` du référentiel lié (avec état de
  compilation). La conception des livrets reste dans l'atelier Référentiel.
- **D3** — Colonne `progressions.source` **supprimée** (aucune distinction
  entre progressions).
- **D4** — Créer une progression liée à un référentiel `verrouille` le fait
  passer **`utilise`** ; un référentiel `utilise` n'est plus déverrouillable
  (`deverrouiller()` refusait déjà tout état ≠ `verrouille`). Migration
  rétroactive : les référentiels déjà référencés passent `utilise`.
- **D5** — Suppression d'une progression = passage à l'état **`annule`**
  (suppression logique, rien n'est effacé), filtré de l'affichage. L'action de
  suppression elle-même (UI) relève d'une fonctionnalité ultérieure ; ici on
  pose l'infrastructure (état autorisé + filtrage).
- **Import historique** (SequenceDB) : **conservé tel quel** côté Admin
  (« Import suivi »), hors périmètre. La création de progression n'en dépend
  plus.
- **Principe** : stockage standard en base ; JSON réservé export/échange.

## Changements

### Base de données
- `persistence/schema.sql` : DDL `progressions` sans `source`, CHECK etat avec
  `annule` (bases neuves).
- `persistence/sqlite_store.py` :
  - `_migrer_schema_post_ddl` : auto-migration des bases existantes (retrait
    `source` + CHECK étendu, recréation de table FK-safe pour ne pas casser les
    FK entrantes de `creneaux` ET `classes`).
  - Correction d'un bug pré-existant de `_migrer_schema` : le CHECK et la
    condition de déclenchement de la migration `referentiel_niveaux` plantaient
    dès qu'un référentiel atteignait l'état `utilise` (pourtant légal).
  - `ecrire_progression` : `source` retiré ; passage auto `verrouille→utilise`.
  - `lire_progression_par_id` : objectifs du créneau lus depuis
    `referentiel_objectifs` (séquence + partie, avec `nb_seances`, critères
    F/A/E, `fin_cycle`).
  - `lister_progressions` : exclut les progressions `annule`.
- `services/progression.py` : champ mort `source` retiré de `progression_vide`.

### Front (`static/app.js`, `templates/index.html`)
- « Objectifs de ce créneau » : alimenté depuis le référentiel (le backend
  peuple `creneau.objectifs`) ; message SequencesDB remplacé ; affichage du
  nombre de séances prévu et d'un badge « fin de cycle ».
- « Versions distribuées aux élèves » → « Livrets distribués » : nouvelle zone
  `#prog-docs-list` alimentée par `progChargerDocuments()` via
  `GET /api/referentiels/<ref_id>/documents`, branchée aux deux points de
  chargement de la progression.
- L'ancien code JS `liv-*` / `creerVersion` / `chargerVersions` est laissé
  **non référencé** (nettoyage renvoyé au futur chantier ménage, pour éviter
  tout risque de régression).

### Migration (script dédié)
- `outils/migrer_v0_19_0_progressions.py` : retrait `source` + rétroactif
  `utilise`, dry-run/--apply/--yes, vérification post-migration. Redondant avec
  l'auto-migration du store mais utile pour appliquer/vérifier explicitement
  sur D:/E:. (La base du livrable n'est PAS incluse dans le delta ; l'app
  s'auto-migre au démarrage, ou lancer le script.)

## Tests

`tests/test_v0_19_0_progression_referentiel.py` (9 cas) : colonne `source`
absente + ignorée ; passage `utilise` (+ non déverrouillable + idempotent) ;
objectifs lus du référentiel (filtrés par partie ; vides sans référentiel) ;
filtre `annule`. `tests/test_progression.py` : assertion `source` retirée.

**Zéro régression** : pytest → 3841 passed, 7 skipped ; vitest → 153 passed.

## Déploiement

L'app **s'auto-migre au démarrage** (retrait `source`, état `annule`,
rétroactif `utilise` via le script ou au fil de l'eau). Pour appliquer/vérifier
explicitement sur chaque base D:/E: :

    python -m outils.migrer_v0_19_0_progressions          # dry-run
    python -m outils.migrer_v0_19_0_progressions --apply   # applique

## Suite (v0.19.1+)

Fonctionnalités à spécifier en sessions dédiées : semaines A/B (nb de créneaux
variable), séance supprimée/déplacée, comptage automatique séances programmées
+ écart avec `referentiel_objectifs.nb_seances`. Nettoyage du code mort
`liv-*`/versions à intégrer au chantier ménage.
