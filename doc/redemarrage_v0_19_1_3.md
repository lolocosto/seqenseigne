# Redémarrage v0.19.1.3 — Figer le découpage en parties dans le snapshot du référentiel

Correctif de fond : au **verrouillage** d'un référentiel, le découpage en
**parties** de séquence n'était pas figé dans les tables `referentiel_*` lues
par l'atelier Progression. Conséquence (signalée sur les séquences à plusieurs
parties) : la barre latérale ne montrait que la 1re partie, et le détail d'un
créneau de 2e partie n'affichait aucun objectif.

## Diagnostic

Le verrouillage (`verrouiller_complet`) produisait bien une trace JSON complète
(parties P1/P2 correctes, lues depuis le modèle actif `sequence_parties` +
`objectifs.partie_id`) et copiait les PDF, **mais n'écrivait pas** la structure
des parties dans le snapshot en base :

- `referentiel_parties` restait **vide** ;
- `referentiel_objectifs.partie_numero` restait **à 1** partout (valeur par
  défaut posée à l'import historique).

Or l'atelier Progression — comme tous les consommateurs runtime d'un
référentiel verrouillé — lit les **tables `referentiel_*`**, pas la trace JSON
(qui n'est relue par personne : c'est un artefact d'archive). Le snapshot étant
incomplet, les 2es parties et leurs objectifs étaient invisibles.

## Architecture clarifiée (rappel)

Dans « Conception de référentiel », les données vivent dans le **modèle actif**
(éditable) jusqu'au verrouillage. **Au verrouillage**, la photo est prise :
PDF compilés + trace JSON + (désormais) snapshot complet en base. Seul un
référentiel verrouillé/utilisé porte un snapshot `referentiel_*` ; la
progression s'appuie **exclusivement** sur ce snapshot.

## Décisions appliquées

- **D1 — Le verrouillage (re)peuple le snapshot des parties** depuis le modèle
  actif, dans la transaction de `verrouiller_complet`, via la nouvelle fonction
  `peupler_snapshot_parties(conn, ref_id, niveau)` :
  - `referentiel_parties (referentiel_id, seq_code, numero, nb_seances_R_AE)` :
    une ligne par partie de chaque séquence (source `sequence_parties` jointe à
    `sequences_par_niveau`) ;
  - `referentiel_objectifs.partie_numero` corrigé à la partie réelle de chaque
    objectif (via `objectifs.partie_id → sequence_parties.numero`, apparié par
    `(seq_code, code)`) **et** `nb_seances` repris du modèle actif
    (`objectifs.nb_seances` — décision B).
  Idempotent (DELETE + INSERT de `referentiel_parties` pour ce référentiel) →
  ré-exécutable à chaque re-verrouillage. Les mêmes requêtes que la trace JSON
  sont utilisées → cohérence garantie entre JSON et tables.
- **D2 — Le déverrouillage purge le snapshot** (décision C) via
  `purger_snapshot_referentiel(conn, ref_id)` appelée par
  `services.referentiels.deverrouiller` : suppression des lignes
  `referentiel_parties` du référentiel et remise de
  `referentiel_objectifs.partie_numero` à 1. Sémantique nette : un référentiel
  `valide`/`en_cours` n'a pas de photo des parties en base (sa structure repart
  vivre dans le modèle actif, éditable). Le dossier `_verrouille/` (trace JSON +
  PDF) est conservé comme avant. Le déverrouillage n'étant possible que si le
  référentiel n'est pas `utilise` (aucune progression liée), la purge est sans
  risque.
- **D3 — La progression lit le snapshot enrichi.**
  `lister_parties_referentiel` lit désormais `referentiel_parties` en priorité
  (la photo autoportante). **Fallback** si `referentiel_parties` est vide
  (référentiels figés avant v0.19.1.3 et non re-verrouillés, ou données alpha
  incomplètes) : dériver les parties des `partie_numero` présents dans les
  objectifs, sinon une partie 1 par séquence — pour ne pas régresser
  l'affichage. La résolution des objectifs d'un créneau
  (`lire_progression_par_id`, `WHERE partie_numero=?`) est inchangée : elle
  fonctionne dès que le snapshot est correct.

## Important — référentiels déjà verrouillés

Le correctif s'applique aux **prochains** verrouillages. Les référentiels
**déjà** verrouillés (ex. `N11_v2025`) ne porteront le découpage en parties
qu'après **déverrouillage → re-verrouillage** depuis l'atelier Référentiel
(ce qui recompile les PDF et reprend la photo). En attendant, le fallback de
`lister_parties_referentiel` les affiche avec une partie par séquence (sans
perte par rapport à l'état actuel).

Un script `outils/` de re-snapshot **depuis les fichiers d'historique
d'origine** (sans passer par déverrouiller/re-verrouiller) fera l'objet d'une
passe dédiée ultérieure (format des fichiers à fournir).

## Changements (fichiers)

- `services/referentiel_figeage.py` : nouvelles fonctions
  `peupler_snapshot_parties` et `purger_snapshot_referentiel` ; appel de
  peuplement ajouté dans `verrouiller_complet` (étape 5bis, avant la transition
  d'état).
- `services/referentiels.py` : `deverrouiller` purge le snapshot des parties.
- `persistence/sqlite_store.py` : `lister_parties_referentiel` lit
  `referentiel_parties` (avec fallback).

## Tests

- `tests/test_v0_19_1_3_figeage_parties_snapshot.py` (nouveau, 7 cas) :
  peuplement de `referentiel_parties` (S12 → P1/P2, S02 → P1) ; correction des
  `partie_numero` (01-03→P1, 11-13→P2) et `nb_seances` ; idempotence ;
  `lister_parties_referentiel` voit les 2 parties ; purge au déverrouillage ;
  purge directe ; fallback une-partie quand `referentiel_parties` vide.

**Zéro régression** : référentiel/figeage/progression/verrou → 370 passed ;
consommateurs du snapshot (livret/évaluation/séquences) → 547 passed, 1 skipped ;
vitest → 183 passed.

## Déploiement & vérification

Aucune migration de base. Décompresser le delta sur D:/E:, puis :

    python -m outils.verifier_md5

Pour qu'une progression voie les parties multiples : dans « Conception de
référentiel », **déverrouiller puis re-verrouiller** le référentiel concerné
(N11). Ensuite, dans « Suivi de classe » > Progression, la barre latérale doit
lister les 2es parties (ex. S12 P1 et S12 P2) et le détail d'un créneau de
partie 2 doit afficher ses objectifs.

## Suite (cœur v0.19.1 restant)

Drag-drop parties → calendrier ; changement de référentiel support (purge des
créneaux, confirmation, restreint à `en_cours`, rétrogradation de l'ancien
référentiel). Puis, passe dédiée : script de re-snapshot des parties depuis les
fichiers d'historique.
