# seqenseigne

Génération et gestion de matériels pédagogiques pour collège (cycle 4 : 6ᵉ, 5ᵉ, 4ᵉ, 3ᵉ), avec un paquet LaTeX `seqenseigne` (`.dtx`/`.sty`) et une application Flask + SQLite portable.

> **Statut v0.15.3** (juin 2026) — alpha en production chez l'auteur. Utilisé en classe au quotidien sur USB Windows + MiKTeX portable + Python portable.

## Vision

Un enseignant prépare une année de mathématiques en collège. Chaque niveau a son **programme officiel** (cycle 4), découpé en **séquences pédagogiques** que l'enseignant ordonne et adapte. Pour chaque séquence il y a des **objectifs**, des **notions** à enseigner, des **méthodes** de résolution, des **exercices** (trois séries : fondamental, avancé, exploration), des **fiches de résumé**.

`seqenseigne` gère tout ça en BDD, génère les PDFs (livrets de séquence, plans de travail, fiches de résumé, livrets annuels, récapitulatifs), tracke les évaluations, et — à partir de v0.15.3 — verrouille un référentiel pédagogique pour le réutiliser dans une progression annuelle.

## Architecture

```
seqenseigne/
├── seqenseigne.dtx           Paquet LaTeX (sources docstrip)
├── seqenseigne.sty           Paquet LaTeX (généré)
└── appli/                    Application Flask + SQLite
    ├── app.py                Point d'entrée Flask
    ├── persistence/          SQLite : schema.sql + sqlite_store.py
    ├── services/             Logique métier (séparée des routes)
    ├── routes/               Endpoints HTTP
    ├── importers/            Imports .tex et CSV
    ├── outils/               Scripts CLI (verifier_md5, purger_fiches,
    │                         importer_referentiel_externe, archiver_docs, …)
    ├── static/               JS + CSS (vanilla)
    ├── templates/            Jinja2
    ├── data/                 BDD SQLite + ressources runtime
    │   ├── seqenseigne.db
    │   ├── images/
    │   └── referentiels/<id>/_verrouille/    (trace.json + pdfs/)
    ├── tests/                pytest (3656+ tests)
    └── doc/                  Documentation (refondue v0.15.4)
        ├── INDEX.md
        ├── README.md         (ce fichier)
        ├── CONVENTIONS.md
        ├── GOTCHAS.md
        ├── DETTE_TECHNIQUE.md
        ├── NETTOYAGE.md
        ├── redemarrage_v0_15_*.md   (notes de livraison vivantes)
        └── archives/                 (notes historiques figées)
```

## Stack

- **Backend** : Python 3.12, Flask, SQLite (BDD = source unique de vérité)
- **Frontend** : JS vanilla + Jinja2 + CSS (pas de framework, pas de build)
- **LaTeX** : paquet `seqenseigne.sty` (issu de `.dtx`), MiKTeX portable x64, `pdflatex` en trois passes (pas de Perl → pas de `latexmk`)
- **Runtime** : Windows verrouillé, MiKTeX et Python portables sur clé USB
- **Tests** : pytest (3656 passed / 7 skipped / 0 failed, v0.15.3)
- **Pas de Git** : livraison par ZIP avec `MANIFEST.md5` (format à 3 colonnes `md5  taille  chemin`)

## Modèle d'état du référentiel (v0.15.3)

```
en_cours → valide → verrouille → utilise
                    └─ annule (concurrents écartés)
```

| Code BDD | Libellé UI | Sémantique |
|---|---|---|
| `en_cours` | « en cours » | atome non validé ou PDF KO |
| `valide` | « validé » | tout OK |
| `verrouille` | « verrouillé » | JSON + PDFs gelés, prêt pour progression |
| `utilise` | « utilisé » | associé à ≥ 1 progression (à venir) |
| `annule` | « annulé » | concurrent écarté, terminal caché |

## Démarrage

```bash
cd appli
python app.py
# → http://localhost:5000
```

Sur USB Windows, lancer via le raccourci `lancer_seqenseigne.bat` qui pose le `PATH` (Python + MiKTeX portables) avant de démarrer Flask.

## Roadmap

- **v0.15.4** (livré) : doc canonique refondue, archivage des notes obsolètes, UI JSON dépliable complet, suppression du double bloc « Éléments à inclure ».
- **v0.15.5** (livré) : factorisation `_cycle_du_niveau` (correction du bug C03/N10-N12 dans 4 livrets), suite verte (correction `_fige`→`_verrouille`), ménage v1, resync doc.
- **v0.16.0** (livré) : affichage PDF en iframe forcé via viewer pdf.js embarqué hors-ligne (ateliers d'atomes).
- **Unification OO des ateliers d'assemblage** : faire converger l'assemblage séquence-niveau (procédural) et l'évaluation (OO) vers une base commune `AtelierAssemblage`. Cf. `cadrage_unification_ateliers_assemblage.md`. Livraison par étape. Inclut le branchement du viewer pdf.js sur les deux assemblages, puis sur le référentiel.
- **Compilation par lot (portée générale) — fiches de résumé + cartes d'automatisme** : ajouter ces deux types d'atomes aux types compilables par lot (aujourd'hui : notion, méthode, exercice).
- **Atelier suivi de classe** : câbler la transition `verrouille → utilise` (transition auto quand un référentiel est associé à une progression).
- **CRUD cycle/niveaux/thèmes/séquences** : édition des données de référence (aujourd'hui en lecture seule). Prérequis internationalisation + import C03 complet.
- **Cartes d'automatisme 4ème/3ème** : peuplement sur le modèle de la 5ème (123 cartes). Pilote 1 séquence (format xint validé/compilé) avant industrialisation.
- **Tests JS automatisés** : candidat Vitest/Jest — déclencheur probable : la migration DnD du seqniv.
- **Badges d'état dans le panneau principal d'assemblage** : les atomes affichés dans le panneau central des ateliers d'assemblage devraient apparaître en vert pâle quand validés (comme les cartes d'automatisme dans les séquences) et transparents sinon — redondant avec la barre latérale mais utile visuellement.
- **6ème (N06)** : intégrer les docs des collègues quand l'enseignant aura ce niveau.

## Documentation

- `INDEX.md` : carte de la doc
- `CONVENTIONS.md` : conventions de code et de livraison (style, ZIP, MANIFEST.md5, …)
- `GOTCHAS.md` : pièges connus et leurs résolutions (LaTeX, SQLite, MiKTeX, …)
- `DETTE_TECHNIQUE.md` : dette identifiée à traiter
- `NETTOYAGE.md` : éléments à nettoyer dans la base de code
- `redemarrage_v0_15_*.md` : notes de livraison vivantes (sessions en cours)
- `archives/` : notes historiques figées (≥ 200 fichiers, jamais modifiées)

## Discipline alpha

- **Zéro régression** : `pytest -q` doit passer sans échec avant chaque livraison.
- **Decision-driven** : on cadre le scope et on tranche les décisions AVANT de coder.
- **Test-driven** : toute décision non évidente est encodée à la fois dans le code ET dans un test nommé qui explique pourquoi.
- **ZIP unique par livraison** : pas de patches successifs (sauf hotfix critique post-déploiement).
- **MANIFEST.md5 obligatoire** : vérification d'intégrité avant déploiement (`appli/outils/verifier_md5.py`).
- **Communication directe** : style technique, sans emoji sauf 🎉 pour les milestones.
