# Dette technique

> v0.15.4 — refonte. Recense la dette identifiée par chantier, classée par priorité.

## Bugs connus (à corriger en priorité)

### ~~`_cycle_du_niveau` retourne C03 pour N10/N12~~ — RÉSOLU v0.15.5

`services.referentiels._cycle_du_niveau` n'existait pas : la fonction était
**dupliquée dans 5 services livret** (`livret_recap_exos`, `livret_recap_cours`,
`livret_fiches`, `livret_corriges`, `livret_plans_de_travail`). Quatre copies
portaient le bug : jointure `spn.sequence_code = sdc.code` SANS filtre cycle +
`LIMIT 1`, qui remontait C03 pour N10/N12 (un même code de séquence, ex. S01,
existe en C03 et C04).

**Correction v0.15.5** : les 5 wrappers locaux supprimés ; tous les services
appellent désormais `services.param_niveaux.lire_cycle` (lecture de la table
`param_niveaux`, source unique de vérité, indépendante des tables séquence).
Invariant verrouillé par `tests/test_v0_15_5_cycle_du_niveau.py` (résolution
C04 pour N10/N11/N12 + garde-fou anti-réintroduction de la jointure buggée).

### `atelChargerObjectifs` produit 5 erreurs console

Atelier de chargement des objectifs depuis le côté JS. Erreurs visibles dans la console navigateur. Pas bloquant pour l'utilisateur mais pollue le debug.

## Chantiers à terminer

### ~~Atelier assemblage séquence-dans-niveau~~ — bug cycle résolu v0.15.5

Le bug `_cycle_du_niveau` qui bloquait ce chantier est corrigé (cf. ci-dessus).
Le reste du chantier assemblage reste à reprendre après v0.15.x.

### Nettoyage v1 (post v0.14.7) — CLÔTURÉ

État vérifié v0.15.5 — la quasi-totalité était déjà faite avant cette version :
- `services/edition_progression.py` : déjà supprimé (≤ v0.14.7).
- Table `exercice_objectifs` (v1) : déjà absente du schéma ET de la BDD de
  production (DROP en v0.14.6.b.2). Plus aucun SQL vivant ne la touche.
- JS `ATL_OBJ_CAT` : déjà retiré (ne restait qu'un commentaire dans `app.js`).
- Route `/api/objectifs` (v1) : déjà retirée (commentaire explicatif dans
  `routes/atomes.py`).
- Table `objectifs` (v1) : supprimée. La table `objectifs` actuelle est la v2
  renommée en v0.14.7 — ne pas confondre, ne pas toucher.

v0.15.5 a fini le ménage résiduel : suppression des 2 scripts one-shot
`scripts/supprimer_v1.py` et `scripts/peuplement_02_repeupler.py` (office
terminé, BDD migrée) + retrait de leurs références dans les tests + nettoyage
d'un commentaire obsolète dans `sqlite_store.py`.

### Série R full cleanup (deferred)

- Suppression des colonnes `objectif_exos.origin_*` (SQLite table recreation)
- Propagation dans les SELECT/INSERT
- Évaluer si `lister_exos_disponibles_pour_revision` a encore du sens.

## Améliorations identifiées

### Atelier suivi de classe

À construire. Permettra la transition `verrouille → utilise` (référentiel associé à une progression). Schéma BDD prêt en v0.15.3, transition non câblée.

### CRUD cycle/niveaux/thèmes/séquences

Aujourd'hui en lecture seule (peuplé par `data/C04_*.csv` à l'import). Pour internationalisation et extensibilité (N13-GT, N13-ASSP, niveaux primaires, …) il faudra une UI d'édition.

### Import C03 full content

Aujourd'hui v0.10.2 importe uniquement les cycles/thèmes/séquences C03 en lecture seule. L'import des connaissances + objectifs nécessite que le CRUD ci-dessus soit en place.

### Parser .tex plans de travail

Pour enrichir la trace JSON avec :
- Calendrier (dateDeb/dateFin par séquence et partie)
- Nombre de séances par objectif
- Composition fine de chaque objectif (notion-objectif via codes C01/C02/…)

Source : `4eX_Plan_de_travail.tex` (et équivalents). Plus précis que la BDD pour l'année écoulée.

### Affichage PDF en iframe forcé

Sur le PC de l'école, Firefox ouvre les PDFs en nouvelle fenêtre malgré le `Content-Disposition: inline` côté serveur. Solution probable : embarquer PDF.js côté client.

### Outil comparaison visuelle des PDFs

Comparer automatiquement les PDFs nouvellement générés avec les précédents validés, page par page. Pistes : `diff-pdf`, ou `pdftoppm` + ImageMagick `compare`. Placement : Admin > BDD, ou sous-onglet dédié.

### Option compilation dyslexie

xeLaTeX + OpenDyslexic + A3 + `LetterSpace=20` + `WordSpace=1.5` + `baselinestretch=1.2` + `unicode-math`/`latinmodern-math.otf`. Commenté dans le `.tex`, activé sur demande.

### Sélection fine des prérequis (v0.11.x+)

Aujourd'hui tous les objectifs des séquences précédentes sont inclus sans choix. Cible : au changement de cycle (typiquement N10), permettre une sélection objectif par objectif des prérequis à inclure ; les exercices de révision tirés uniquement de ces prérequis.

### Tests JS automatisés

Aucun aujourd'hui (validation visuelle). Candidats : Vitest (ESM-natif) ou Jest. Installation dans `appli/`, ajout de `npm test` au workflow. Priorité grandissante au fur et à mesure que le JS devient complexe.

### Audit 4 sous-chantiers

À cadrer en sessions séparées :

- **3a** : JS hors ateliers d'atomes (thème, séqcycle, séqniv-assemblage, récap) + helpers communs résiduels
- **3b** : CSS / design system
- **3c** : Backend Python — duplications routes/services
- **3d** : architecture globale

### Vue de consultation de la trace verrouillée

Aujourd'hui en JS dans `atelRefMajDonneesVerrouillees`. Un mode « plein écran » avec recherche/filtres pourrait être utile. Pas urgent.

### Compléter l'import N11_v2025

Les 14 PDFs de l'année écoulée (S01 importé en v0.15.2.10, S02-S14 à importer chez Laurent avec `importer_referentiel_externe.py` v0.15.2.12.2).

## Dette docs

### Plan annuel non historisé

Le `.tex` plan de travail est artisanal côté Laurent. Pas de stockage en BDD ni dans le référentiel verrouillé. À voir si on l'intègre ou si on garde séparé.

### `objectif_notions` quasi vide en BDD

8 rows total pour ~ 30 séquences × ~ 5 objectifs ordinaires × ~ 2-3 notions. La relation notion ↔ objectif est essentiellement dans les `.tex` plans de travail, pas en BDD. À reconstruire (parser .tex ci-dessus).

## Hygiène

### Documentation : 215+ fichiers archivés en v0.15.4

Avant v0.15.4, `doc/` contenait 250 fichiers difficilement navigables. v0.15.4 a archivé ~ 215 dans `doc/archives/<categorie>/`. À maintenir : ne plus jamais laisser le dossier déraper. Outil : `outils/archiver_docs.py`.

### Aliases rétrocompat v0.15.3 à retirer

- `services.referentiels.figer_minimal` (alias de `verrouiller_minimal`)
- `services.referentiel_figeage.figer_complet` (alias de `verrouiller_complet`)
- Route `POST /api/referentiels/<id>/figer` (alias de `/verrouiller`)
- JS `atelRefFiger` (alias de `atelRefVerrouiller`)

À retirer en v0.16+ quand on aura confirmé qu'aucun appelant externe ne les référence.

### ~~`atelier_atome_generique.js` legacy~~ — déjà supprimé

Anciennement utilisé avant la factorisation `AtelierEditeur` (v0.13.6.16).
Vérifié absent du dépôt en v0.15.5 (le fichier n'existe plus). Item clos.
