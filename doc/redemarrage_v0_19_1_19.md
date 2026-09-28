# Redémarrage v0.19.1.19 — Affectation des séances (mises en route / automatismes)

Cinquième livraison du chantier « progressions à la séance ». On pose *quelle
activité de démarrage* a lieu sur chaque séance projetée (L4), sans encore en
définir le contenu. Sans UI ; tables + fonction pure + CRUD + endpoint composé
+ tests.

## Valeurs d'affectation

Trois valeurs **réservées** (toujours disponibles) + les étiquettes
personnalisées :
- `automatisme` — fil Leitner (calendrier des enveloppes à réviser, produit en
  L7).
- `progression` — séquences de mise en route (dates début/fin calées sur le
  nombre de séances, en L6).
- `aucun` — pas d'activité de démarrage.
- `mer:<id>` — étiquette personnalisée référençant un `preferences_items` de
  type `type_mise_en_route` (L1). Simple étiquette : le contenu est géré hors
  logiciel par l'enseignant.

## Deux modes (par classe / année)

- `par_seance` (**défaut, neutre**) : affectation **case par case** de l'EDT.
  Une case non affectée = `aucun`. Pensé pour une multi-sélection de créneaux
  dans l'UI (sélectionner plusieurs créneaux → les affecter en bloc).
- `par_repartition` : un **motif cyclique** (liste d'affectations) s'applique
  aux séances dans l'ordre chronologique global (numéro de séance de la L4).

Des **exceptions** (dates) forcent `aucun` quel que soit le mode (ex. jour
d'évaluation).

## Tables (migration idempotente)

- `affectation_config(classe_id, annee, mode)` — le mode actif.
- `affectation_seance(id, classe_id, annee, edt_creneau_id, affectation)` —
  affectations par créneau (mode par_seance), unique par créneau.
- `regle_repartition(classe_id, annee, motif)` — motif JSON (mode
  par_repartition).
- `affectation_exception(id, classe_id, annee, date, motif)` — retraits
  ponctuels, unique par date.

## Fonction pure `services/affectation.py`

`affecter(seances, mode, affectations_par_edt, motif, exceptions) -> [seances]`
enrichit chaque séance d'un champ `affectation`. Testable sans base/réseau.
CRUD : `lire/definir_mode`, `lire/definir_affectations` (upsert ; `aucun`
supprime la ligne → état neutre), `lire/definir_motif`,
`lister/ajouter/supprimer_exception`, `dates_exceptions`.

## Ajout dans la projection (L4)

`projection_seances.projeter` expose désormais `edt_creneau_id` pour chaque
séance (nécessaire au mode par_seance). Rétrocompatible (champ ajouté).

## API `routes/affectation.py`

- `GET/PUT /api/classes/<id>/affectation-config` — mode (+ motif, reserves en
  lecture).
- `GET/PUT /api/classes/<id>/affectations` — affectations par créneau (PUT =
  batch `items:[{edt_creneau_id, affectation}]`).
- `PUT /api/classes/<id>/repartition` — motif cyclique.
- `GET/POST /api/classes/<id>/affectation-exceptions`,
  `DELETE /api/affectation-exceptions/<id>` — exceptions.
- `GET /api/classes/<id>/planning-affecte` — projection + affectation composées.

## Fichiers

- `persistence/sqlite_store.py` : 4 tables d'affectation (migration).
- `services/projection_seances.py` : propagation de `edt_creneau_id`.
- `services/affectation.py` (nouveau).
- `routes/affectation.py` (nouveau).
- `app.py` : import + enregistrement du blueprint `bp_affectation`.
- `tests/test_v0_19_1_19_affectation.py` (nouveau, 8 cas).
- `doc/ROADMAP.md` : L5 marquée faite.

## Tests

- `tests/test_v0_19_1_19_affectation.py` : 8 passed (tables, validation des
  valeurs, par_seance, par_repartition cyclique, exceptions, défaut neutre,
  persistance mode/affectations/motif/exceptions).
- pytest ciblé (affectation + projection + edt + grille + classes + preferences)
  : 120 passed, 0 régression.
- vitest : 187 passed. Démarrage app + 6 routes affectation vérifiés.
- Vérifié de bout en bout (vraies vacances) : planning affecté à 65 séances,
  affectation par créneau et exception correctes.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Les 4 tables se créent au
premier lancement (idempotent).

## Suite

- Livraison 6 : progression de séquences de mise en route (séquences à nombre de
  séances fixe → dates début/fin sur les séances affectées `progression`).
- Livraison 7 : ordonnancement Leitner (enveloppes à réviser sur les séances
  affectées `automatisme`).
- Puis UI (dont multi-sélection de créneaux pour l'affectation, et affichage de
  l'alerte « vacances absentes » de la L4).
