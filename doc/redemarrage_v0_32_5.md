# Redémarrage v0.32.5 — Association de documents à la progression (socle backend)

Premier volet : le modèle et le service pour associer des documents à distribuer
à un point de la progression, au NIVEAU (pas par classe). L'UI de saisie et
l'affichage dans la Planification hebdo viendront ensuite.

## Modèle

Un document est associé à (type de progression, progression, créneau/partie,
rang de séance). Toutes les classes du niveau en héritent ; les décalages réels
(absences, indisponibilités) restent gérés par le mécanisme existant. On reste au
niveau du BLOC (créneau + rang), pas de la planification fine séance par séance,
pour absorber les écarts prévu/réalisé sans re-saisie.

Table `progression_doc(id, prog_kind, prog_ref, creneau_ref, rang_seance,
doc_source, doc_ref, doc_libelle, ordre)` :
- `prog_kind` : `principale` | `mer`
- `prog_ref` : id de progression (principale) ou `progression_mer.id`
- `creneau_ref` : id du créneau (principale) ou de la partie MER
- `rang_seance` : rang de la séance dans ce créneau
- `doc_source` : `interne` | `externe`
- `doc_ref` : interne → `type_document|cible_id` (ex.
  `livret_cartes_planches|N11/S05`) ; externe → id du doc

## Sources de documents (toutes existantes)

- interne (réf. principal) : documents compilés par cible séquence, ou annuels
  (cible « unique »). **Les cartes d'automatisme** en font partie via le type
  `livret_cartes_planches` — « distribuer les planches de la séquence » est donc
  couvert.
- externe (réf. principal ET MER) : docs de partie (séquence) + docs annuels.
- Les référentiels MER **internes** n'existent pas encore (cf. ROADMAP).

## Fichiers

- `persistence/sqlite_store.py` : table `progression_doc` (+ index).
- `services/progression_doc.py` (nouveau) : CRUD + `documents_disponibles`
  (séquence / séquence suivante en option / annuels).
- `routes/progression_doc.py` (nouveau) : API (liste, ajout, suppression,
  disponibles).
- `app.py` : blueprint `bp_progression_doc`.
- `tests/test_v0_32_5_progression_doc.py` (nouveau, 4 cas).

## Tests

- `tests/test_v0_32_5_progression_doc.py` : 4 passed. vitest : 193 passed.
- Vérifié sur la base réelle (N11) : docs disponibles pour S05 = « Livret de
  séquence — S05 » + « Planches de cartes d'automatisme — S05 » ; annuels = 6 ;
  séquence suivante S06 = 2.
- Corrigé un contrat de test obsolète (v0.30.2) : la liste d'atomes expose
  désormais aussi la clé `sequence`.

## Dette repérée (préexistante, NON incluse dans ce delta)

`tests/test_v0_29_0_verso_miroir.py` importe `_miroir_horizontal_verso`, qui
n'existe plus dans `render_carte_centralise.py` (refactor antérieur). Ce test
obsolète casse la collecte pytest ; à supprimer ou réécrire (hors périmètre).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. La table `progression_doc` est
créée au premier lancement.

## Suite

- v0.32.6 : UI de saisie de l'association dans l'atelier de progression
  (principale et MER) + affichage des docs prévus dans la Planification hebdo.
