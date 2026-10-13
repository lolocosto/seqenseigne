# Redémarrage v0.51.11 — Retraits avant la bascule

Préalable à la bascule (v0.51.12), d'après la répartition validée table par
table (document « Répartition des tables entre atelier et classe »).

## Décisions (validées)

- **Ancien modèle de MER retiré** (`referentiel_externe`, `_sequence`,
  `_partie`, `_doc`) : l'auteur a basculé sa MER de 6e sur le modèle de la
  structure figée. Les progressions de MER qui s'y appuyaient encore perdent
  leur référentiel (à choisir de nouveau) et leurs parties posées ; leurs
  associations de documents de l'ancien modèle sont retirées.
- **Anciens livrets retirés** (`livrets_de_sequence`, `livret_revisions`,
  `versions`, `versions_classes`) : instantanés et versions de livrets
  d'avant les ateliers, version active par classe, verrouillage historique
  des séquences au premier exercice coché (plus lu nulle part).
- Avant suppression, le contenu est **sauvegardé en JSON** dans
  `data\sauvegardes\retrait_<nom>_<date>.json` ; la migration est faite au
  démarrage, une seule fois.
- **Atelier : Système › Administration › « Import retours d'usage »**
  (pendant de l'import de référentiels côté appli en ligne) : analyse (n°
  attendu, référentiels connus), import, usage reçu par référentiel.
- Au passage : les **documents annuels** des référentiels de la structure
  figée sont proposés à la progression (ils ne l'étaient pas).

## Code

- `services/retraits.py` (nouveau), appelé par `persistence/sqlite_store.py`
  au démarrage ; `persistence/schema.sql` sans les quatre tables de livrets.
- Ancien modèle de MER : `services/progression_mer.py` (source « fige »
  seule), `routes/progression_mer.py`, `services/progression_doc.py`,
  `services/format_referentiel.py`, `services/referentiel_principal_externe.py`,
  `routes/referentiel_principal_externe.py`, `services/profils.py`, `app.py`,
  `static/progression_mer.js`, `static/referentiel_pe.js` (écran
  intermédiaire retiré), `static/referentiel_unifie.js`,
  `templates/index.html`.
- Anciens livrets : `persistence/sqlite_store.py` (méthodes de versions et de
  livrets importés, versions actives des classes), `routes/classes.py`,
  `routes/suivi.py`, `services/classes.py`, `services/sequences.py`,
  `services/admin.py`, `routes/admin.py`, `routes/atomes.py`,
  `importers/scanner.py`, `importers/scanner_latex.py`,
  `importers/sequencesdb.py`, `static/app.js` (ancien onglet Livrets),
  `scripts/peuplement_01_migrer_schema.py`.
- Onglet : `templates/index.html`, `static/app.js`,
  `static/import_publication.js` (`impUsage…`).
- Fichiers supprimés : voir `MANIFEST_SUPPRESSIONS.md` de la livraison.
- Tests : `tests/test_v0_51_11_retraits.py` ; tests de l'ancien modèle et
  des versions retirés ; `tests/test_v0_26_0_progression_mer.py` réécrit sur
  la structure figée.
