# Redémarrage v0.51.18 — Ordre des exercices du livret, numéros du plan de travail

## Symptômes

- Livret de séquence : exercices d'une série mélangés (objectifs 04, 02,
  02, 13, 03…) au lieu de suivre l'ordre des objectifs.
- Plan de travail : numéros d'exercices incohérents avec le livret
  (« 1,2,3,4 » pour l'objectif 02 puis encore « 1,2,3,4 » pour le 03).

## Causes

- Le livret triait les exercices de chaque série par identifiant. Depuis
  que les identifiants sont aléatoires (`ex_xxxxxxxx`), ce tri mélange
  les objectifs (code inchangé depuis avant v0.35 ; les anciens ids,
  dérivés des noms de fichiers, se triaient par objectif).
- Le plan affichait `objectif_exos.ordre`, rang de l'exercice dans son
  objectif, alors que le livret numérote en continu dans chaque série.
  Les deux calculs étaient indépendants.

## Décisions (validées)

- **D1** Ordre du livret : partie → code d'objectif → rang, pour les
  séries AE, F, A, E ; Révisions : partie → R puis EA → rang. Les
  corrigés suivent.
- **D2** Une seule numérotation pour le livret et le plan :
  `services/numerotation_livret.py`.
- **D3** Numéros du plan = numéros du livret, continus sur la séquence
  (série 0 = R/EA des parties puis AE des objectifs ; séries F, A, E).
- **D4** Exercice sur deux objectifs d'une même série : émis une fois (au
  premier objectif), même numéro affiché sous les deux.
- **D5** Exercice de révision aussi rattaché à une série : seulement en
  Révisions (livret et plan).

## Code

- `services/numerotation_livret.py` (nouveau) : `lire_structure_exos`
  (lecture minimale, mêmes tris que `v2_lecture`), `numeroter_exos_livret`,
  `numeroter_sequence`, `NumerotationLivret.numeros(...)`.
- `services/livret_sequence.py` : exercices émis dans l'ordre de
  `numeroter_sequence` (plus de tri par identifiant).
- `services/livret_plans_de_travail.py` : `exos_R`, `exos_EA`, `exos_F/A/E`
  = numéros du livret (paramètre `numerotation`, calculé une fois par
  séquence).
- Tests : `tests/test_v0_51_18_numerotation_livret.py` (9 tests, ids
  volontairement « à l'envers », concordance livret ↔ plan) ;
  `tests/test_v0_12_1_livret_plans_de_travail.py` adapté
  (`test_exos_R_et_EA`, `test_exos_par_serie`). Vérifié : 3 des nouveaux
  tests échouent sur le code v0.51.17.1.

## Déploiement

Aucun changement de paquet ni de base. Recompiler livrets et plans de
travail.
