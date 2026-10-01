# Redémarrage v0.41.1 — Un seul point de préparation de la projection

Deuxième livraison de la revue des dettes (v0.41.x). Aucun changement visible.

## Constat (audit)

La séquence « classe → établissement/académie → EdT compté + grille +
indisponibilités → vacances + fériés (hors transaction) → borne du
1er septembre → `projection_seances.projeter` » était recopiée **9 fois** :
`routes/projection.py`, `routes/leitner.py`, `routes/affectation.py`,
`routes/progression_mer.py` (×2 : planning et PDF),
`routes/decalage_progression.py` (vacances seules), `services/edt_apercu.py`,
`services/planification_hebdo.py` (×2 : grille de la semaine et détail de
séance, ce dernier avec deux projections). **Aucune divergence de
comportement** entre les copies (même borne, même filtre des cases comptées,
même traitement des erreurs réseau).

## Décisions

- **D1 — Comportement figé avant le refactor** :
  `tests/test_v0_41_1_projection_figee.py` + capture
  `tests/fixtures/snapshot_projection_v0_41_1.json`, prise sur le code
  v0.41.0. Jeu de données : EdT A/B, demi-groupe non compté, EdT figé avec
  suppression programmée au 04/01, indisponibilité, MER en panachage avec
  affectations par case et exception, progression principale, vacances et
  fériés fictifs. Sorties figées : projection, planning d'automatismes (JSON
  et .tex du PDF), planning affecté, planning MER (JSON et .tex du PDF),
  progression réalisée, planification hebdo (grille et 3 détails de séance :
  exception, MER auto, MER progression), aperçu d'EdT. Vérifié : une
  modification de la borne du 1er septembre fait échouer le test.
- **D2 — `services/contexte_projection.py`** : `infos_classe`,
  `calendrier(store, annee, academie, feries=True)` (hors transaction),
  `date_min`, `donnees_classe`, `projeter_donnees`, `projeter_classe`.
- **D3 — Les 9 copies appellent ce module.** Les routes ne gardent que la
  lecture des paramètres et la mise en forme de la réponse.
- **D4 — Capture identique avant / après.**

## Tests

- pytest : 4051 réussis, 0 échec (dont 6 nouveaux).
- vitest : 220 réussis.

Régénérer la capture seulement si un changement de comportement est voulu :
`..\outils\python\python.exe tests\test_v0_41_1_projection_figee.py --regenerer`.
