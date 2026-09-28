# Redémarrage v0.19.1.11 — Audit référentiels : ignorer les devoirs communs (DC) + complétion 2022-23

Correctif de l'outil d'audit `verifier_referentiels.py` et vérification des
référentiels 2022-23.

## Correctif — l'audit ignore les pseudo-séquences (DC, bilans)

L'audit de structure comparait **tous** les créneaux d'une progression aux
séquences du référentiel. Or les progressions de 3ᵉ contiennent des créneaux
**DC1/DC2/DC3** (devoirs communs) — qui occupent une place dans le planning mais
ne sont pas de vraies séquences. L'outil les signalait à tort comme
« séquence … absente du référentiel ».

Corrigé : l'audit ne considère que les codes de séquence valides de la forme
`S<chiffres>` (S01..S14). Les pseudo-séquences (DC, bilans) sont ignorées.

## Résultat de l'audit 2022-23 (sur copie de la base, imports appliqués)

- **N10_v2022** (5e2/5e4) : structure **alignée** ; livrets **14/14** après
  copie depuis les archives 5E2 → complet.
- **N12_v2022** (3e3/3e8) : structure **alignée** (DC ignorés) ; livrets
  **13/14**. Le livret **S13 manque** : la séquence S13 n'a pas été traitée
  cette année-là (pas de plan ni de livret dans les archives 3E3). Ce n'est pas
  une anomalie de l'outil — l'information est remontée telle quelle.

## Changements (fichiers)

- `outils/verifier_referentiels.py` : l'audit de structure filtre les codes de
  séquence via `_RE_SEQ_VALIDE` (`^S\d{1,2}$`), ignorant DC/bilans.
- `tests/test_v0_19_1_11_audit_ignore_dc.py` (nouveau, 2 cas) : l'audit
  n'émet pas de faux écart pour DC1/DC2/DC3 ; `_RE_SEQ_VALIDE` distingue
  séquences et pseudo-séquences.

## Tests

`tests/test_v0_19_1_11_audit_ignore_dc.py` → 2 passed.

## Déploiement & utilisation

1. Déployer ce delta ; `python -m outils.verifier_md5`.
2. Auditer les référentiels 2022-23 (lecture seule) :

       python -m outils.verifier_referentiels --ref N10_v2022 --ref N12_v2022

3. Compléter les livrets manquants depuis les archives :

       python -m outils.verifier_referentiels --ref N10_v2022 \
           --copier-livrets <dossier_5E2_2022-23> --apply
       python -m outils.verifier_referentiels --ref N12_v2022 \
           --copier-livrets <dossier_3E3> --apply

   Le livret S13 de N12_v2022 restera manquant (séquence non traitée en
   2022-23) — c'est attendu.

## Suite

- Import des progressions 2023-24 (4e3, 5e1) sur le modèle des imports
  historiques.
- Chantiers déjà identifiés : modèle « plan de travail par séquence » (pour
  copier aussi les plans PDF) ; cœur v0.19.1 (drag-drop parties → calendrier,
  changement de référentiel support).
