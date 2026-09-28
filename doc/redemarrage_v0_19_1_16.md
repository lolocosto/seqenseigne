# Redémarrage v0.19.1.16 — Grille horaire par établissement

Deuxième livraison de code du chantier « progressions à la séance ». Socle :
la **grille horaire des créneaux de cours** d'un établissement (M1..M4 le matin,
S1..S4 l'après-midi). Sans UI (on cale le modèle) ; CRUD + API + tests.

Contexte : la saisie de l'emploi du temps de l'enseignant devient nécessaire
pour projeter les progressions à la séance sur des dates/heures réelles et pour
affecter les mises en route par jour. La grille horaire de l'établissement en
est le premier étage (les créneaux communs au collège). L'EDT enseignant
(quels créneaux chaque classe occupe en semaine A/B) viendra ensuite.

## Contenu

### Table `grille_horaire_creneaux`

Créée dans la migration (`_migrer_schema_post_ddl`, idempotent) :
`id, etablissement_id, code, libelle, heure_debut, heure_fin, demi_journee
('M'|'S'), ordre`, unique par `(etablissement_id, code)`.

### Peuplement des défauts (idempotent)

Au démarrage, chaque établissement **sans** créneau reçoit les 8 créneaux par
défaut (modèle Collège les Hautes Ourmes) :

| Code | Début | Fin | Demi-journée |
|------|-------|-----|--------------|
| M1 | 08:25 | 09:20 | Matin |
| M2 | 09:25 | 10:20 | Matin |
| M3 | 10:35 | 11:30 | Matin |
| M4 | 11:35 | 12:30 | Matin |
| S1 | 12:55 | 13:50 | Après-midi |
| S2 | 13:55 | 14:50 | Après-midi |
| S3 | 15:05 | 16:00 | Après-midi |
| S4 | 16:05 | 17:00 | Après-midi |

Un établissement qui a déjà des créneaux n'est pas touché (horaires
personnalisables ; ils varient d'un collège à l'autre). L'API amorce aussi les
défauts de façon paresseuse au premier GET d'un établissement sans créneau.

### Service `services/grille_horaire.py`

`defauts()`, `peupler_defauts_si_vide(conn, etab_id)`, `lister`, `creer`
(unicité du code, validation des heures HH:MM), `modifier`, `supprimer`.

### API `routes/grille_horaire.py`

- `GET  /api/etablissements/<id>/grille-horaire` — liste (+ amorçage défauts)
- `POST /api/etablissements/<id>/grille-horaire` — créer un créneau
- `PUT  /api/grille-horaire/<creneau_id>` — modifier
- `DELETE /api/grille-horaire/<creneau_id>` — supprimer

## Fichiers

- `persistence/sqlite_store.py` : table `grille_horaire_creneaux` (migration) +
  `_peupler_grille_horaire_si_vide` (appelé au démarrage).
- `services/grille_horaire.py` (nouveau).
- `routes/grille_horaire.py` (nouveau).
- `app.py` : import + enregistrement du blueprint `bp_grille_horaire`.
- `tests/test_v0_19_1_16_grille_horaire.py` (nouveau, 6 cas).

## Tests

- `tests/test_v0_19_1_16_grille_horaire.py` : 6 passed.
- pytest ciblé (grille + établissement + classes) : 86 passed, 0 régression.
- vitest : 187 passed. Démarrage de l'app vérifié (4 routes exposées).

## Déploiement

1. Décompresser le delta ; `python -m outils.verifier_md5`.
2. La migration + le peuplement s'appliquent au premier lancement (idempotent).
   Le Collège les Hautes Ourmes reçoit ses 8 créneaux par défaut.

## Suite (chantier progressions à la séance)

- Livraison 3 : **EDT enseignant par classe** (`edt_seances` : quels créneaux
  M1..S4 chaque classe occupe en semaine A/B ; comptage dérivé des séances par
  semaine). Les créneaux hors maths (concertation M3 semaine A, projet S4 lundi,
  vie de classe, co-animations) ne sont simplement pas saisis pour la classe.
- Puis : projection séance→date+heure (EDT × calendrier), règle d'affectation
  (a par jour / b par répartition + exceptions), progression de séquences de
  mise en route, ordonnancement Leitner, puis UI.
- `seances_A`/`seances_B` (livraison 1) conservés comme saisie rapide / fallback.
