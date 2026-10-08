# Redémarrage v0.51.3 — Import des paquets dans l'appli en ligne

Quatrième étape du chantier « séparer l'appli en 2 » (cadrage :
`doc/redemarrage_v0_51_0.md`). Formats : `doc/format_referentiel.md`,
`doc/format_paquet.md`. Version construite pendant que l'auteur continue la
saisie de ses référentiels dans l'appli locale ; décisions prises dans le
cadre déjà validé (import par fichier, lecture seule, rien supprimé sans
prévenir, séquence commencée protégée).

## Décisions

- Import dans le **profil classe** (aussi visible en complet), Système ›
  Administration › « Import référentiels » : **Analyser** (rien n'est écrit)
  puis **Importer**.
- Vérification complète d'abord (`paquet_publication.verifier`) : un paquet
  invalide n'importe rien.
- Statut par référentiel : **nouveau**, **mise à jour** (rapport des
  changements : séquences, parties, durées, documents), **identique** (même
  empreinte), **refusé** :
  - mise à jour qui retirerait une séquence ou une partie **déjà
    commencée** (créneau daté passé, partie de MER posée) ;
  - autre référentiel avec le même niveau et la même version ;
  - **base partagée avec l'atelier** : un référentiel conçu dans cette base
    n'est jamais remplacé (identique → « identique », sinon refusé).
- Associations de documents dont le document disparaît : **signalées
  (orphelines), jamais supprimées**.
- Un référentiel importé porte `origine='publication'` ; chaque référentiel
  s'importe dans sa propre transaction, fichiers écrits avant la base.
- Les écrans de classe lisent l'import sans changement de logique :
  structure figée (tables `referentiel_*`, durée de partie = somme des
  objectifs), fichiers déposés (`referentiel_fichiers`, mêmes chemins), PDF
  compilés (`referentiel_docs_publies`, lus par les documents de la
  progression), titres des notions / méthodes (`referentiel_titres_publies`,
  repli de la synthèse Pronote quand il n'y a pas d'atomes).
- **Base séparée pour essayer** : `lancer.bat classe --base-classe` lance le
  profil classe sur `data_classe\` (créé au besoin avec les fichiers de
  référence de `data\`, sans la base ni la configuration). Premier morceau
  de la bascule (v0.51.4).

## Code

- `services/import_publication.py` (nouveau) : `analyser`, `importer`,
  `journal`, `importes` ; tables `referentiel_docs_publies`,
  `referentiel_titres_publies`, `imports_publication` ; colonnes
  `origine`, `publication_empreinte`, `publication_importe_le` de
  `referentiel_niveaux` (migration dans `persistence/sqlite_store.py`).
- `routes/import_publication.py` (nouveau, catégorie classe) :
  `POST /api/import-publication/analyse`, `POST …/importer` (multipart,
  champ `paquet`), `GET …/etat`.
- `services/progression_doc.py` : documents compilés d'un référentiel
  importé ; `services/synthese_seance.py` : titres importés.
- `templates/index.html`, `static/import_publication.js` (nouveau),
  `static/app.js` (sous-onglet `importpub`), `static/app.css`.
- `app.py`, `lancer.bat` (`SEQ_DATA`, `--base-classe`), `.gitignore`
  (`data_classe/`, `data/referentiels_fichiers/`), `services/profils.py`.

## Tests

- `tests/test_v0_51_3_import_paquet.py` (atelier et classe sur deux bases
  séparées) : nouveaux référentiels (structure, fichiers, placements, types,
  PDF, titres, type des objectifs), lecture par les écrans de classe
  (documents disponibles, synthèse, parties, liste des référentiels), paquet
  identique, mise à jour avec rapport et ménage des fichiers, orphelins
  conservés, refus d'une séquence commencée, paquet corrompu, base partagée,
  routes, profil atelier sans la route.
- Parcours navigateur (profil classe, base vide) : analyse puis import d'un
  paquet de deux référentiels, liste et journal.

## Suite

- Retour d'usage classe → atelier (validé) : état d'usage (utilisé,
  séquences commencées, parties de MER posées), sans donnée d'élève.
- v0.51.4 : bascule des données de classe vers la base séparée.
