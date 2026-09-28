# Redémarrage v0.25.0 — Référentiels externes

Intègre des référentiels dont le contenu est conçu **hors de l'appli** (docs
PDF/ODT… de collègues), sans avoir à les reconstruire en LaTeX. Débloque à terme
les progressions de mise en route « à la séance ».

## Modèle

- **Type de référentiel** : `principal` / `mer`. Un référentiel externe est de
  type `mer` (les référentiels MER sont exclusivement externes pour l'instant).
- **Niveau + année de création**, comme les référentiels principaux.
- **États** : `en_cours` (éditable) et `valide` (utilisable en progression).
  Pas de « verrouillé » ni « utilisé » : on peut ajouter des documents à tout
  moment, même après validation. La validation est libre (aucun contrôle de
  complétude par l'appli).
- **Structure** : séquences → **parties** → documents.
  - séquence : code + nom ;
  - partie : numéro + libellé + **nombre de séances** (les séances sont portées
    par la partie, ex. « Calcul mental » P1 tables / P2 compléments) ;
  - documents attachés à une partie. L'incomplétude est normale (une partie peut
    n'avoir aucun doc, ils arrivent plus tard).

## Documents

- Tous formats importables. **PDF affichés en ligne** (inline dans le
  navigateur) ; **autres formats** (ODT, ODS, DOCX, XLS…) proposés au
  **téléchargement** (les navigateurs ne les affichent pas nativement).
- Stockés sous `data/referentiels_externes/<ref_id>/`, enregistrés en base
  (nom d'origine, chemin, MIME, taille). C'est l'enseignant qui nomme ses docs.

## UI

Conception de référentiel → **Niveau** → nouveau sous-onglet **« Référentiel
externe »**. On y crée un référentiel (au niveau courant), ajoute/supprime des
séquences et des parties (avec leur nb de séances), importe/supprime des
documents par partie, et valide/dévalide le référentiel.

## Fichiers

- `persistence/sqlite_store.py` : tables `referentiel_externe`,
  `…_sequence`, `…_partie`, `…_doc` (migration idempotente).
- `services/referentiel_externe.py` (nouveau) : CRUD + validation + stockage
  des docs.
- `routes/referentiel_externe.py` (nouveau) : API REST (15 routes) dont
  téléchargement/affichage des docs.
- `app.py` : blueprint `bp_referentiel_externe`.
- `templates/index.html` : sous-onglet + panneau `atl-referentiel_externe`,
  inclusion `referentiel_externe.js`.
- `static/app.js` : `referentiel_externe` dans la portée niveau (ATL_PORTEES) +
  init (ATL_INITS).
- `static/referentiel_externe.js` (nouveau) : atelier complet.
- `tests/test_v0_25_0_referentiel_externe.py` (nouveau, 5 cas).

## Tests

- `tests/test_v0_25_0_referentiel_externe.py` : 5 passed (tables, structure
  séquence/partie, validation + état interdit, doc affichable selon MIME +
  fichier écrit, niveau obligatoire).
- vitest : 193 passed (0 régression). Sous-onglet servi, 15 routes exposées.
- Circuit complet vérifié : référentiel MER 6e → séquence « Calcul mental » →
  parties P1 (6 séances) / P2 (4 séances) → doc PDF (servi inline) → validation.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Les tables se créent au premier
lancement. Conception de référentiel › Niveau › Référentiel externe.

## Suite

- Progressions de MER « à la séance » s'appuyant sur les référentiels externes
  validés (zone C du planning MER, mode `progression`).
- Puis panachage automatismes / progression.
- Plus tard : référentiels MER conçus dans l'appli (docs spécifiques, cf. les
  fiches de calcul mental).
