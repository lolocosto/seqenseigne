# Redémarrage v0.19.1.17 — EDT de l'enseignant (année courante)

Troisième livraison de code du chantier « progressions à la séance ». Deuxième
étage du socle EDT : l'**emploi du temps de l'enseignant**, ancré sur une année
scolaire. Sans UI (on cale le modèle) ; table + service + API + tests.

## Modèle

### Table `edt_creneaux`

Créée dans la migration (idempotent). Une ligne = une case de l'EDT :
`id, annee, jour (lun..sam), creneau_code (M1..S4), semaine (A|B|AB,
défaut AB), classe_id (nullable), etablissement_id, libelle, usage, ordre`,
unique par `(annee, jour, creneau_code, semaine, etablissement_id)`.

L'EDT est **global** (application mono-utilisateur) : il contient tout
l'emploi du temps, y compris les créneaux non utilisés par les progressions
(concertation, projets, vie de classe, co-animation…). Le champ `usage` fait le
tri.

### Champ `usage` (6 valeurs)

- `classe_entiere` — **seul usage compté** dans les progressions pour l'instant.
- `demi_classe_A`, `demi_classe_B` — cours en demi-classe (saisis, pas comptés).
- `groupe_option`, `groupe_horaire_ordinaire` — groupes (saisis, pas comptés).
- `autre` — vie de classe, projets hors discipline, concertation… (jamais
  compté).

### Semaine `AB` par défaut

Les créneaux présents **toutes les semaines** (majoritaires) sont `AB` ; `A`/`B`
sont l'exception (créneaux différenciés). `AB` compte à la fois pour A et B.

## Service `services/edt.py`

- Constantes `USAGES` (6), `USAGES_COMPTES` (`classe_entiere`), `JOURS`,
  `SEMAINES`.
- `lister(conn, annee, classe_id=None)` — cases + horaires (jointure grille) +
  flag `creneau_inconnu` si le code n'est plus dans la grille.
- `ajouter(...)` — valide jour/semaine/usage, exige que `creneau_code` existe
  dans la grille de l'établissement, refuse les doublons.
- `modifier(...)` — semaine/classe/libellé/usage/ordre (jour et créneau non
  modifiables : supprimer/rajouter). Contrôle d'unicité.
- `supprimer(...)`.
- `compter_seances(conn, classe_id, annee) -> {"A", "B"}` — dérivé, ne compte
  que `classe_entiere` ; A = semaine A + AB, B = semaine B + AB.
- `creneau_grille_est_reference(conn, etab, code)` — support de la garde.

## Cohérence grille ↔ EDT (décision Qc/Qiii)

`services/grille_horaire.supprimer` **refuse** désormais de supprimer un créneau
de grille référencé par au moins une case d'EDT (lève `DonneesInvalides`). La
cohérence est ainsi garantie sur l'année en cours. L'archivage des années
passées (fige EDT + grille avec la progression) est **cadré mais non codé**
(voir `doc/ROADMAP.md`).

## API `routes/edt.py`

- `GET  /api/edt[?annee=&classe_id=]` — cases + `usages`, `usages_comptes`,
  `jours`, `semaines`. Année courante par défaut.
- `POST /api/edt` — ajouter une case (201).
- `PUT  /api/edt/<id>` — modifier.
- `DELETE /api/edt/<id>` — supprimer.
- `GET  /api/classes/<classe_id>/seances-edt` — comptage A/B dérivé.

## Fichiers

- `persistence/sqlite_store.py` : table `edt_creneaux` (migration).
- `services/edt.py` (nouveau).
- `services/grille_horaire.py` : garde de cohérence dans `supprimer`.
- `routes/edt.py` (nouveau).
- `app.py` : import + enregistrement du blueprint `bp_edt`.
- `tests/test_v0_19_1_17_edt.py` (nouveau, 6 cas).
- `doc/ROADMAP.md` : découpage des livraisons réactualisé + points cadrés non
  codés (archivage, groupes).

## Tests

- `tests/test_v0_19_1_17_edt.py` : 6 passed (table, validations, comptage AB,
  usage non compté exclu, garde grille, modifier/supprimer).
- pytest ciblé (edt + grille + classes + preferences) : 104 passed, 0 régression.
- vitest : 187 passed. Démarrage de l'app + routes EDT vérifiés.

## Déploiement

1. Décompresser le delta ; `python -m outils.verifier_md5`.
2. La table `edt_creneaux` est créée au premier lancement (idempotent).

## Suite

- Livraison 4 : projection séance→date+heure (EDT × calendrier vacances/fériés ;
  convention semaine 2 = B, rentrée non comptée, semaines de vacances sautées).
- Puis règle d'affectation (a/b + retraits), progression de séquences de mise en
  route, ordonnancement Leitner, UI.
- Cadré non codé : archivage EDT/grille des années passées ; comptage fin des
  groupes (1 séance pour 2 demi-classes).
