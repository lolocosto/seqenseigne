# Redémarrage v0.28.0 — Panachage des MER (socle serveur)

Premier volet du panachage : chaque créneau EDT porte un type de MER
(automatisme / progression / aucune), et les plannings ne consomment que les
séances de leur type. Socle serveur ; l'UI de saisie vient en v0.28.1.

## Modèle

Le **contenu** MER (référentiels, progressions) reste **par niveau**.
L'**affectation** des créneaux est **par classe** (car l'EDT et les semaines A/B
diffèrent d'une classe à l'autre — nécessaire dès qu'on panache).

Chaque créneau EDT compté (case classe entière) porte, pour une classe qui fait
des MER, un type :
- `automatisme`, `progression`, ou `aucun` (pas de MER sur ce créneau).

Le **défaut** dépend du mode MER de la classe :
- `automatismes` → tous les créneaux en automatisme ;
- `progression` → tous en progression ;
- `panache` → `aucun` (l'enseignant choisit créneau par créneau).

L'enseignant peut surcharger chaque créneau, y compris pour **neutraliser**
(`aucun`) régulièrement un créneau, quel que soit le mode. Deux neutralisations :
- **régulière** : un créneau EDT à `aucun` (jamais de MER sur ce créneau) ;
- **exceptionnelle** : une date précise (exceptions d'affectation existantes).

Granularité : le créneau entier porte un type (la MER dure 5-10 min en début de
séance ; l'appli ne gère pas le découpage intra-créneau).

Cas limites couverts (validés) :
- une classe deux fois le même jour (mardi M1 auto + M4 progression) → identifiée
  par `edt_creneau_id`, pas par la date seule ;
- deux créneaux consécutifs (M1/M2) → 0, 1 ou 2 MER au choix.

## Logique

Fonction pure `affectation.repartir_mer(seances, mer_mode, affectations,
exceptions_dates)` : répartit les séances datées (portant `edt_creneau_id`) en
`{automatisme: [...], progression: [...]}` selon l'affectation du créneau et le
mode. Réutilise le service `affectation` (créé en v0.19.1.19, désormais
rebranché) : `lire_affectations` (par `edt_creneau_id`), `dates_exceptions`.

## Connexion aux plannings

- **Planning automatismes** (`routes/leitner.py`) : ne compte que les séances
  `automatisme` (la cadence Leitner avance sur celles-là).
- **Planning MER progression** (`routes/progression_mer.py`, JSON + PDF) : ne
  consomme que les séances `progression`.

## Fichiers

- `services/affectation.py` : `repartir_mer` (pure).
- `routes/leitner.py` : filtre les séances `automatisme`.
- `routes/progression_mer.py` : filtre les séances `progression` (2 routes).
- `tests/test_v0_28_0_panachage_mer.py` (nouveau, 6 cas).
- `doc/ROADMAP.md` : SEGPA (niveaux distincts) notée.

## Tests

- `tests/test_v0_28_0_panachage_mer.py` : 6 passed (panache par créneau, modes
  purs, neutralisations régulière et exceptionnelle, panache partiel M1/M2).
- vitest : 193 passed.
- Circuit vérifié de bout en bout : classe en panache, lun M1 = automatisme /
  jeu M2 = progression → planning auto = lundis, planning MER = jeudis.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration (tables
`affectation_*` déjà en place depuis v0.19.1.19). Aucune UI de saisie encore :
sans affectation, une classe en mode `automatismes`/`progression` se comporte
comme avant (défaut selon le mode).

## Suite

- v0.28.1 : UI de saisie du panachage — affecter chaque créneau de l'EDT à
  automatisme / progression / aucune, par classe.
