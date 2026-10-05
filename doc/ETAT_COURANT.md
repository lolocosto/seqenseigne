# ÉTAT COURANT — seqenseigne

> Fichier de synthèse pour retrouver rapidement l'état du projet au début d'une
> session. À lire en premier. Mis à jour à chaque livraison.

## Version déployée

**v0.47.3** (dernière livrée). Historique complet : `doc/redemarrage_v0_*.md`.

## Comment reprendre (pour l'assistant)

1. Lire ce fichier + le dernier `doc/redemarrage_v0_*.md`.
2. Le code de l'appli est sous `appli/` dans le zip (racine = `appli/app.py`).
3. Les zips envoyés N'INCLUENT PAS : cache de compilation d'atomes, images, la
   plupart des dossiers de référentiels (dont les PDF figés). Ces éléments
   existent chez l'utilisateur — ne pas conclure « absent » depuis le zip.
4. Protocole : reconstruire, auditer, cadrer, coder, tester (pytest + vitest),
   livrer un ZIP delta + MANIFEST md5. Jamais de .db dans une livraison.
5. Le dépôt GitHub (lolocosto/seqenseigne) contient `appli/` à la racine ; il
   est à jour à chaque livraison poussée : partir d'un `git pull`.

## Chantier en cours : suivi en séance

Découpage validé dans `doc/ROADMAP.md` (section « Suivi en séance »).
- v0.42.0 livrée : navigation (Paramétrage, Système ; Suivi › Début de
  séance, Observation, Compétences). v0.42.1 : sélecteurs (Suivi : Année,
  Établissement, Niveau, Classe partagée ; Observables : Niveau).
- v0.43.0 livrée : Début de séance (séance en cours / prochaine /
  dernière, mise en route affichée, absents sur le plan ou la liste) ;
  v0.43.1 : séances du jour (toutes classes) toujours affichées ;
  v0.43.2 : début effectif des mises en route, case « MER non faite ».
- v0.44.0 livrée : documents du début de séance (prévus et ajoutés à la
  volée, report, distribution, rattrapage des absents).
- v0.45.0 livrée : observables par niveau (communs / individuels, périodes,
  exceptions masquer / attribuer avec commentaire, copie, aperçu).
- v0.46.0 livrée : observation en séance (même séance que le début de
  séance, plan, liste effective de l'élève, occurrences, compteurs).
- v0.47.0 livrée : Suivi › Travail (à faire / à rendre, échéance
  individualisée depuis la remise, à rattraper, documents à rapporter,
  clôture, retards de la classe) ; v0.47.1 : synthèse pour le cahier de
  textes Pronote ; v0.47.2 : délai « prochaine séance / x jours / x semaines » ;
  v0.47.3 : liste des classes refiltrée dans Progression de MER / Mises en route.
- Prochaine étape : v0.48 — « travail à rendre » sur les documents des
  référentiels (principal et MER), délai à l'association, documents de la
  progression de MER.

## Derniers chantiers terminés

- **Plans de classe (v0.37 → v0.40)** — cadrage : `doc/cadrage_plans_de_classe.md`.
  Salles et éditeur libre de plan (v0.37), EdT versionné avec salle et AESH
  (v0.38), plans de classe hebdomadaires (v0.39), sexe des élèves, aléatoire
  mixte, places AESH (v0.40). Suites notées dans `doc/ROADMAP.md`.
- **Revue des dettes techniques (v0.41.0 → v0.41.3)** : suite de tests au vert
  et pdf.js versionné (v0.41.0) ; préparation de la projection unique (v0.41.1) ;
  semaine vue par la projection, report MER, sélecteur d'établissement, fusion
  encadrée (v0.41.2) ; nettoyage (v0.41.3).

## Chantier précédent : planification de la distribution de documents

- Modèle + service + route : `progression_doc` (v0.32.5).
- Affichage dans la Planification hebdo : détail de séance → docs prévus (v0.32.6/8).
- Correctif état « verrouillé/utilisé » des référentiels importés (v0.32.7).
- UI de saisie : Suivi → Progression principale → détail du créneau → section
  « Documents à distribuer » (v0.32.8).
- Association posée AU NIVEAU (créneau + rang de séance), pas par classe ; les
  décalages restent gérés par les indisponibilités.
- Sources de docs : référentiel principal interne (dont planches de cartes),
  référentiels externes (principal ET MER). Référentiels MER internes : PAS
  développés (roadmap).

## Prochaines étapes possibles

- Rappels d'impression (todo dérivée, délai 7 j configurable) — cadré, à coder.
- Tuile « Séances de la semaine » cliquable.
- Réorganisation des onglets de 1er niveau : Tableau de bord · Suivi ·
  Planification · Conception · Administration · Configuration (idée à cadrer).
- Suivi « en séance » (observations élèves par pictogrammes, mobile/tablette) —
  gros chantier, cadrage consigné dans reflexion_metier_enseignant_roadmap.md.

## Règles à respecter (acquis de la revue des dettes)

- **Projection** : toute préparation passe par `services/contexte_projection.py`
  (calendrier hors transaction, `projeter_classe`, `seances_de_la_semaine`) ;
  ne jamais recopier la séquence calendrier/EdT/grille/indisponibilités.
- **Palette des niveaux** : source unique = variables `--niv-*` du §20 de
  `app.css` (v0.36.2).
- **Libellés LaTeX des niveaux** : `param_niveaux.LIBELLES_NIVEAUX_LATEX`
  (v0.41.3) ; ne pas recréer de table locale.
- **Outils CLI** qui importent `services`/`persistence` : amorce `sys.path` dans
  le script et lancement par chemin
  (`..\outils\python\python.exe .\outils\x.py`), jamais `python -m` (v0.37.1).
- **Suppressions** : push-to-github.html crée des commits additifs ; tout
  fichier listé dans `MANIFEST_SUPPRESSIONS.md` est aussi à supprimer à la main
  sur GitHub.
- **Tests figés** : `tests/test_v0_41_1_projection_figee.py` ; ne régénérer la
  capture que pour un changement de comportement voulu, et le documenter.
- **Établissements** : création uniquement par sélecteur + « Ajouter un
  collège » (académie dans la liste connue) ; fusion refusée si la source a un
  EdT, des indisponibilités ou une grille personnalisée.

## Dettes restantes (mineures)

- `services/tableau_bord.py` (`_NIVEAU_LABEL`) et
  `services/latex_rendu_atome.py` ont encore leurs propres libellés de niveaux
  (formes différentes : « 4ème », « 4e », « Quatrième ») ; à rapprocher de
  `param_niveaux` à l'occasion.
- `tests/test_paquet_parseur.py::TestIntegration` (5) : cherche le paquet dans
  `../reference/paquet` ; ignoré sur un clone GitHub (seul `appli/` y est).

## Points d'attention récurrents

- Bien vérifier le zip reçu : plusieurs fois une version obsolète a été envoyée
  (vérifier la présence des derniers `doc/redemarrage_*.md`).
- Après chaque str_replace, vérifier le code de sortie ET l'absence de message
  d'erreur (des coquilles JS/py ont été introduites puis corrigées).
