# Redémarrage v0.15.2.10 — Outil d'import rétroactif de référentiel

## Contexte (Laurent, mai 2026)

Demande : « Si je te fournis les PDFs d'un référentiel déjà utilisé pour
évaluer la progression des élèves (celui que j'utilise cette année),
peux-tu produire la structure JSON correspondante et stocker ces PDFs
en les associant au référentiel ? »

Cas test : `N11_v2025` (4ᵉ, mis en place rentrée 2025).

État BDD au moment de la demande :
- `N11_v2025` est à l'état **`verrouille`** (état terminal au-delà de
  `fige`).
- Sa structure pédagogique est **complète** : 5 thèmes, 14 séquences,
  30 notions, 57 méthodes, 281 exercices, 57 fiches de résumé.
- **0 évaluations** et **0 documents** tracés dans
  `referentiel_documents` : les PDFs ont été produits en externe avant
  l'arrivée du système de figeage automatisé (v0.15.2.9).

Donc le job, c'est de **reconstituer rétroactivement** le dossier
`data/referentiels/N11_v2025/_fige/` (trace.json + pdfs/) à partir
de la BDD existante + les PDFs fournis par Laurent. **Sans toucher
à l'état BDD** (déjà verrouille).

## Outil livré

`outils/importer_referentiel_externe.py`

CLI complète, idempotente, avec mode `--dry-run`. Workflow :

1. Lit la BDD pour récupérer la structure du référentiel (thèmes,
   séquences avec parties/objectifs/précédents/atomes utilisés,
   évaluations s'il y en a).
2. Génère la `trace.json` via `services.referentiel_figeage.generer_trace`
   (réutilise le code v0.15.2.9 — un seul point de vérité pour la
   construction de la trace).
3. Pour chaque PDF du dossier source, détermine son type métier :
   - Par regex sur le nom de fichier
     (`*_S<NN>_Livret.pdf` → livret_sequence S<NN>).
   - Override possible via un CSV explicite
     `fichier_source ; type_document ; sequence`.
4. Copie chaque PDF dans `<ref>/_fige/pdfs/` en le renommant selon la
   convention seqenseigne (`livret_sequence__N11__S01.pdf`).
5. Enrichit `trace.json` avec ces documents externes
   (`provenance: 'externe'`).
6. **Ne touche pas** à l'état BDD du référentiel.

### Idempotence

À chaque exécution, le dossier `_fige/` est SUPPRIMÉ puis recréé : on
peut relancer l'outil autant de fois que nécessaire (ajuster le mapping,
ajouter des PDFs, etc.) sans craindre d'accumulation.

### Usage

```bash
# Dry-run (rien n'est modifié) — recommandé pour vérifier le mapping
python -m outils.importer_referentiel_externe \
    --ref-id N11_v2025 \
    --pdfs-source ~/PDFs_4e_2025 \
    --data-dir ./data \
    --dry-run

# Exécution réelle
python -m outils.importer_referentiel_externe \
    --ref-id N11_v2025 \
    --pdfs-source ~/PDFs_4e_2025 \
    --data-dir ./data

# Avec mapping CSV explicite (si noms personnels)
python -m outils.importer_referentiel_externe \
    --ref-id N11_v2025 \
    --pdfs-source ~/PDFs_4e_2025 \
    --data-dir ./data \
    --mapping ~/PDFs_4e_2025/mapping.csv
```

### Format du CSV de mapping (optionnel)

3 colonnes séparées par `;`, pas d'en-tête, commentaires `#…` ignorés :

```csv
4e3_S01_Livret.pdf;livret_sequence;S01
4e3_S02_Livret.pdf;livret_sequence;S02
# Si tu as aussi un livret de corrigés global pour le niveau :
4e3_corriges.pdf;livret_corriges;
```

Une `sequence` vide signifie « document au niveau global » (pas par
séquence).

## Démonstration sur le PDF S01 fourni

Le ZIP de livraison contient déjà un répertoire de démonstration :
**`appli_data_demo/data/referentiels/N11_v2025/_fige/`** avec :
- `trace.json` (3728 lignes, ~110 Ko) — généré depuis la BDD.
- `pdfs/livret_sequence__N11__S01.pdf` — le PDF que Laurent a fourni,
  renommé à la convention.

Tu peux soit :
- **Déployer ce répertoire tel quel** dans ton arborescence — il
  remplace ce qu'il y a déjà sous `data/referentiels/N11_v2025/_fige/`.
- **Régénérer chez toi** avec l'outil pour les 14 séquences :
  ```bash
  python -m outils.importer_referentiel_externe \
      --ref-id N11_v2025 \
      --pdfs-source <dossier_tes_14_PDFs> \
      --data-dir <ton_data_dir>
  ```

### Vérification du contenu de la trace générée

J'ai validé la cohérence avec ton PDF S01 :

| Aspect | Trace générée | PDF S01 (toi) |
|---|---|---|
| Titre séquence | « Représentations d'un nombre » | « Représentations d'un nombre » ✓ |
| Parties | 2 | « (1ère partie) » et « (2nde partie) » ✓ |
| Objectifs | 7 (01-04 + 11-13) | Page 3 : 01, 02, 03, 04, 11, 12, 13 ✓ |
| Critères F/A/E | présents | Page 3 ✓ |
| Prérequis | 1 | « Objectifs de 5e » ✓ |
| Atomes liés | 6 notions, 5 méthodes, 32 exos, 5 fiches | Cohérent avec le contenu du livret ✓ |

## Ce que la trace ne contient PAS encore (et qu'on pourrait ajouter)

Tu m'as aussi fourni `4e3_Plan_de_travail.tex` qui documente la
**progression annuelle réelle** de tes 4ᵉ (dates, séances par objectif,
quels exercices pour quels objectifs en F/A/E…). Cette information
n'est PAS dans la BDD — elle est purement dans le `.tex`.

Si tu veux que la trace soit enrichie avec ces données, je peux écrire
un parser `outils/parser_plan_de_travail.py` qui extrait :

- Le calendrier (dateDeb/dateFin par séquence et partie)
- Le nombre de séances (total, révisions, cours, par objectif)
- La composition de chaque objectif (quels exercices F, A, E)

Et qui les injecte dans `trace.json` au niveau de chaque séquence,
section `plan_de_travail` (nouvelle clé).

**À arbitrer en début de session suivante** : faut-il faire cet
enrichissement maintenant, ou la trace BDD-seule suffit pour le suivi
annuel ?

## Tests

**v0.15.2.10 : 3619 passed, 6 skipped, 0 failed** (+14 par rapport à v0.15.2.9).

Nouveau fichier `tests/test_v0_15_2_10_importer_referentiel_externe.py`,
14 tests qui couvrent :

- Détection regex (livret_sequence par convention `*_S<NN>_Livret.pdf`).
- Chargement CSV explicite (override + commentaires).
- Convention de nom métier (avec/sans séquence).
- Référentiel inconnu → ValueError.
- Dry-run : aucune écriture.
- Cas nominal : `trace.json` + PDFs copiés et renommés.
- Idempotence : relance écrase proprement.
- PDFs non mappés listés sans bloquer.
- État BDD non modifié.
- Trace : documents externes injectés avec `provenance: 'externe'`.
- CSV override prend priorité sur regex.

## Fichiers livrés

### Delta code (ZIP principal `seqenseigne_v0_15_2_10.zip`)

| Fichier | Type |
|---|---|
| `appli/outils/importer_referentiel_externe.py` | Nouveau |
| `appli/tests/test_v0_15_2_10_importer_referentiel_externe.py` | Nouveau |
| `appli/doc/redemarrage_v0_15_2_10.md` | Nouveau (ce document) |

Pas de modification de service/route/UI : c'est un outil hors-ligne.

### Démonstration de données (ZIP séparé `appli_data_demo.zip`)

Contient le `data/referentiels/N11_v2025/_fige/` pré-rempli :
- `trace.json` (généré depuis ta BDD)
- `pdfs/livret_sequence__N11__S01.pdf` (renommé)

À déployer tel quel dans ton arborescence si tu veux gagner du temps,
ou à régénérer chez toi avec les 14 PDFs.

## Vérification

```powershell
.\outils\python\python.exe outils\verifier_md5.py --racine . --manifest MANIFEST.md5
.\outils\python\python.exe -m pytest -q
# Attendu : 3619 passed, 6 skipped, 0 failed
```

## Prochaines pistes

1. **Compléter l'import N11_v2025** : tu fournis les 13 autres PDFs,
   tu lances l'outil chez toi. Si certains noms ne suivent pas la
   convention, on rédige ensemble un `mapping.csv`.
2. **Enrichir la trace avec le plan de travail .tex** (parsing du
   calendrier, séances, exercices par objectif). À arbitrer.
3. **Vue de consultation de la trace figée** dans l'UI (lecture humaine
   du JSON, navigation par séquence). Chantier UI séparé.
4. **N09 et N12** quand pertinent (mais tu m'as dit que tu n'as ni 5ᵉ
   ni 3ᵉ cette année).
5. **N06 (6ème)** : tu m'as dit que tu utilises les docs des collègues
   cette année. Question ouverte : leur structure entre-t-elle dans
   notre modèle séquences/objectifs/atomes ? À examiner ensemble.

### Roadmap (rappel)
- Atelier assemblage séquence-dans-niveau (EN COURS, bug `_cycle_du_niveau`)
- Diagnostic perf tcolorbox (piste D)
- v0.13 — CRUD cycles/niveaux/thèmes
- v0.14 — Admin refonte
- v0.15 — Progressions annuelles
