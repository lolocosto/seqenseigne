# Redémarrage v0.26.0 — Progressions de MER à la séance (socle serveur)

Premier volet des progressions de mise en route « à la séance » : le pendant, en
séances, de la progression principale (en semaines). Socle serveur uniquement
(modèle + service + API) ; l'UI vient en v0.26.1.

## Modèle

- `progression_mer(id, classe_id, annee, ref_mer_id, ref_mer_source, etat)` :
  une progression MER par classe/année (contrainte d'unicité), adossée à UN
  référentiel MER. `ref_mer_source` indique où lire la structure du référentiel
  — « externe » aujourd'hui ; « interne » plus tard (référentiels MER conçus
  dans l'appli). `etat` ∈ {en_cours, valide}.
- `progression_mer_partie(id, progression_mer_id, partie_id, partie_source,
  ordre)` : les parties posées, dans l'ordre. Une partie est atomique (posée une
  seule fois) ; son nombre de séances est lu dans le référentiel, non dupliqué.

## Logique

- `progression_mer.projeter_mer(seances, parties)` (pure) : affecte à chaque
  séance datée la partie en cours, en consommant le nb de séances de chaque
  partie dans l'ordre. Au-delà de la dernière partie, la progression est
  « épuisée » (pas de partie). Renvoie chaque séance enrichie de la partie, du
  rang (n/N) et de la séquence.
- Résolution des parties selon la source (`resoudre_partie`,
  `lister_parties_disponibles`) : délègue aux tables du référentiel externe
  aujourd'hui ; extensible à l'interne.
- Choix des parties (b) : on pose les parties voulues, dans l'ordre voulu (comme
  la progression principale) — pas toutes automatiquement.
- Changer de référentiel purge les parties posées (elles référençaient l'ancien).

## API

- `GET /api/classes/<id>/progression-mer` : lit (crée si besoin) la progression.
- `POST …/progression-mer/referentiel` : associe un référentiel MER.
- `POST /api/progression-mer/<id>/etat` : en_cours / valide.
- `GET /api/progression-mer/<id>/parties-disponibles` : parties du référentiel.
- `POST /api/progression-mer/<id>/parties` : poser une partie (doublon refusé).
- `DELETE /api/progression-mer/parties/<pose_id>` : retirer.
- `POST /api/progression-mer/parties/<pose_id>/deplacer` : réordonner.
- `GET /api/classes/<id>/planning-mer` : projette les parties sur les séances
  datées (réutilise la projection EdT × calendrier × indisponibilités).

## Fichiers

- `persistence/sqlite_store.py` : tables `progression_mer`,
  `progression_mer_partie`.
- `services/progression_mer.py` (nouveau) : projection pure + CRUD + résolution.
- `routes/progression_mer.py` (nouveau) : API (7 routes).
- `app.py` : blueprint `bp_progression_mer`.
- `tests/test_v0_26_0_progression_mer.py` (nouveau, 5 cas).

## Tests

- `tests/test_v0_26_0_progression_mer.py` : 5 passed (tables, projection
  ordonnée + épuisement, liste vide, CRUD + ordre + doublon interdit, purge au
  changement de référentiel).
- vitest : 193 passed (0 régression).
- Circuit complet vérifié : référentiel externe MER validé → progression MER →
  pose de 2 parties (ordre choisi) → planning projeté (10 séances utilisées =
  6+4).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Les tables se créent au premier
lancement. Aucune UI encore (v0.26.1).

## Suite

- v0.26.1 : UI dans l'onglet « Mises en route » (mode progression) — choix du
  référentiel MER, pose/ordre des parties, planning MER (même frise que les
  automatismes).
- Puis panachage automatismes / progression.
