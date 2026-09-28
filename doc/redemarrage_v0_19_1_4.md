# Redémarrage v0.19.1.4 — Modèle de séances à deux régimes (par objectif / par série)

Première des deux livraisons préparant l'import de l'historique complet. Cette
étape **enrichit le modèle de données** pour accepter, à côté du modèle courant
de séances (par objectif), le modèle **historique** (séances par série
d'exercice, ex. 2021-22). Aucun import ici : le script d'import 4e3 viendra en
v0.19.1.5 et s'appuiera sur ce modèle.

## Contexte

En 2021-22, les plans de travail donnaient les séances sous forme d'une
**matrice (niveau-cible × série)** par séquence/partie — p. ex. cible « Très
bon » : auto-éval 1 / fondamentale 1,5 / avancée 2 / exploration 2,5 ; cible
« Satisfaisant » : auto-éval 1,5 / fondamentale 2,5 / avancée 3 (sans
exploration). Cette granularité n'a aucun équivalent par objectif : impossible
de la reverser proprement dans le modèle courant sans inventer des données.
D'où un second régime, optionnel, qui stocke l'historique tel quel.

## Décisions appliquées

- **D1 / A — Un seul champ `mode_seances`**, porté par le **référentiel**
  (`referentiel_niveaux.mode_seances` ∈ {`par_objectif`, `par_serie`}, défaut
  `par_objectif`). Une progression hérite du mode via son `referentiel_id`
  (pas de champ dédié sur `progressions`).
- **D2 / B — Table `referentiel_parties_seances`**, clé sur le **référentiel** :
  ```
  (referentiel_id, seq_code, partie_numero, niveau_cible, serie, nb_seances)
  PK = (referentiel_id, seq_code, partie_numero, niveau_cible, serie)
  ```
  `niveau_cible` ∈ {`TB`, `S`} ; `serie` ∈ {`R` (auto-éval/révisions), `F`,
  `A`, `E`}. La cible `S` n'a pas de ligne `E` (rythme sans exploration). Une
  ligne par cellule de matrice.
- **D4 / C — Affichage**. La route `/api/referentiels/<id>/parties` expose
  désormais `ref.mode_seances` et, en mode `par_serie`, un bloc
  `seances_par_serie` (la matrice). Dans l'atelier Progression, le détail d'un
  créneau affiche, en mode `par_serie` uniquement, **les deux matrices**
  (cibles « Très bon » et « Satisfaisant ») en lecture seule, avec un total par
  cible. En mode `par_objectif`, ce bloc reste masqué (comportement inchangé).

## Changements (fichiers)

- `persistence/sqlite_store.py` :
  - migration idempotente (`_migrer_schema_post_ddl`) : ajout de la colonne
    `referentiel_niveaux.mode_seances` (défaut `par_objectif`) et création de
    `referentiel_parties_seances` ;
  - nouvelle méthode `lister_seances_par_serie(referentiel_id)` ;
  - `lire_referentiel` expose `mode_seances` (via `SELECT *`, déjà inclus).
- `routes/referentiels.py` : `/parties` ajoute `ref.mode_seances` et
  `seances_par_serie` (peuplé seulement en mode `par_serie`).
- `static/atelier_progression.js` : mémorise `_modeSeances` /
  `_seancesParSerie` ; `_matricesSeances(seq, partie)` ;
  `_renderSeancesCreneau(c)` (les 2 matrices, lecture seule) ; `_fmtSeances`.
- `templates/index.html` : conteneur `#prog-seances-bloc` dans le détail du
  créneau (masqué par défaut).

## Tests

- `tests/test_v0_19_1_4_mode_seances.py` (nouveau, 7 cas) : migration (colonne
  + table + défaut `par_objectif`) ; `lister_seances_par_serie` (vide en
  par_objectif, matrice complète en par_serie, asymétrie TB/S) ; route
  `/parties` (mode + matrice exposés).
- `tests_js/atelier_progression.test.js` (+4 cas) : `_matricesSeances`
  (assemblage TB/S, isolation par partie, séquence inconnue) ; `_fmtSeances`.

**Zéro régression** : pytest (referentiel/progression/figeage/verrou) →
371 passed ; vitest → 187 passed.

## Déploiement & vérification

La migration est idempotente et rétro-compatible : les référentiels existants
restent `par_objectif`, la nouvelle table démarre vide. Décompresser le delta
sur D:/E:, puis :

    python -m outils.verifier_md5

Aucun changement visible tant qu'aucun référentiel n'est en mode `par_serie` :
ce mode et les données de matrice seront posés par le script d'import 4e3
(v0.19.1.5).

## Suite (v0.19.1.5)

Script d'import historique 4e3 2021-22 (usage unique, `outils/`) : bascule de
`N11_v2021` en `par_serie`, peuplement de `referentiel_parties` (S12 → 2
parties), de `referentiel_parties_seances` (matrices lues dans les
`*_Plan.tex`), correction de l'ordre/dates/labels des créneaux de
`pg_e011c733` (en place, IDs préservés) et redistribution du suivi S12 sur les
deux parties (4E3/4E4/4E6).
