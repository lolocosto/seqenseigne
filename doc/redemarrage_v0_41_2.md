# Redémarrage v0.41.2 — Dettes fonctionnelles (semaine, MER, établissements)

Troisième livraison de la revue des dettes (v0.41.x).

## Décisions validées

- **D1 — Séances de la semaine issues de la projection.** La planification
  hebdo et le tableau de bord listaient les cases d'EdT brutes : cases A **et**
  B chaque semaine, cours affichés un jour férié et la semaine de rentrée,
  exceptions MER ignorées, type MER recalculé avec une règle recopiée.
  Nouvelle fonction `contexte_projection.seances_de_la_semaine` : projection
  de chaque classe (alternance A/B, versions d'EdT, vacances, fériés, rentrée),
  type MER par `affectation.repartir_mer` (exceptions comprises) ; les séances
  touchées par une indisponibilité restent affichées, marquées `indispo`.
- **D2 — Report des affectations MER.** `affectation.definir_affectations`
  reporte une affectation modifiée sur les cases futures issues d'un
  changement d'EdT (`cases_suivantes` : même classe, jour, créneau,
  commençant à partir de la fin de la case), seulement si elles avaient
  encore l'ancienne valeur.
- **D3 — Établissement d'une nouvelle classe.** Sélecteur des établissements
  connus (présélection : établissement global) + « + Ajouter un collège »
  (nom et académie obligatoires, ville facultative). Le serveur reçoit
  `etablissement_id` (400 s'il est inconnu). Académie verrouillée sur la liste
  des académies connues (`GET /api/academies`), aussi dans le formulaire de
  modification d'établissement ; une académie inconnue est refusée (400) en
  création comme en modification. Recherche par nom (imports) insensible à la
  casse et aux espaces.
- **D4 — Fusion d'établissements.** Refus explicite (`source_avec_edt`) si la
  source a des cases d'EdT, des indisponibilités ou une grille horaire
  différente de la grille par défaut ; sinon sa grille par défaut et son état
  d'EdT sont supprimés. Classes, progressions et salles migrées comme avant.
- **D5 — Capture v0.41.1 corrigée.** Les données utilisaient le mode MER
  « panachage » au lieu de « panache » (mode invalide). Corrigé et capture
  régénérée : seules `planif_hebdo` (D1) et `planning_automatismes` (mode
  corrigé) changent.

## Tests

- pytest `tests/test_v0_41_2_dettes_fonctionnelles.py` (19).
- Suite complète : pytest 4070 réussis, 0 échec ; vitest 220 réussis.
- Parcours navigateur : nouvelle classe avec création d'un collège depuis le
  formulaire.
