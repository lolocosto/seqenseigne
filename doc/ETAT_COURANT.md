# ÉTAT COURANT — seqenseigne

> Fichier de synthèse pour retrouver rapidement l'état du projet au début d'une
> session. À lire en premier. Mis à jour à chaque livraison.

## Version déployée

**v0.39.1** (dernière livrée). Historique complet : `doc/redemarrage_v0_*.md`.

## Comment reprendre (pour l'assistant)

1. Lire ce fichier + le dernier `doc/redemarrage_v0_*.md`.
2. Le code de l'appli est sous `appli/` dans le zip (racine = `appli/app.py`).
3. Les zips envoyés N'INCLUENT PAS : cache de compilation d'atomes, images, la
   plupart des dossiers de référentiels (dont les PDF figés). Ces éléments
   existent chez l'utilisateur — ne pas conclure « absent » depuis le zip.
4. Protocole : reconstruire, auditer, cadrer, coder, tester (pytest + vitest),
   livrer un ZIP delta + MANIFEST md5. Jamais de .db dans une livraison.

## Chantier en cours : salles, plans de salle, plans de classe

Cadrage validé : `doc/cadrage_plans_de_classe.md` (v0.37 → v0.40).
- v0.37.0 livrée : salles + éditeur libre de plan + versions + import TikZ 302.
- v0.38.0 livrée : EdT versionné (en saisie / figé, périodes, scission,
  changements programmés, aperçu), salle et nombre d'AESH par case.
- v0.39.0 livrée : plans de classe hebdomadaires (reconduction, imposé/libre,
  aléatoire, impression).
- Prochaine étape : v0.40 — sexe à l'import, aléatoire mixte, places AESH.

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

## Dettes techniques repérées (préexistantes)

- `tests/test_v0_29_0_verso_miroir.py` : importe une fonction supprimée
  (refactor), casse la collecte pytest → à supprimer/réécrire.
- `tests/test_annees_scolaires.py` (2 cas) : attendent « 2025-2026 » comme année
  courante, dépendants de la date système → à corriger.
- `tests_js/deeplink_atelier_defini.test.js` : lit app.js par un chemin absolu
  codé en dur (`/home/claude/extract/...`) → échoue hors de cet environnement.
- Projection : préparation (grille, indispos, vacances, 1er sept.) dupliquée
  dans 5 routes + services/edt_apercu.py → helper commun à créer.
- Planification hebdo / tableau de bord : pas de filtre semaine A/B.
- MER (affectation case par case) : pas de report d'une affectation modifiée
  vers les cases futures issues d'un changement d'EdT déjà programmé.
- outils/migrer_edt_groupe_usage.py : obsolète depuis v0.38 (schéma).
- Fusion d'établissements : ne migre ni la grille horaire ni l'EdT (les salles
  oui, depuis v0.37.0).
- Outils CLI qui importent `services`/`persistence` : le Python portable
  (embeddable) n'a pas le dossier courant dans sys.path → amorce sys.path dans
  le script et lancement par chemin (`..\outils\python\python.exe outils\x.py`),
  jamais `python -m` (v0.37.1).
- Palette des niveaux : source unique = variables `--niv-*` du §20 de app.css
  (v0.36.2). Ne pas recréer de palette parallèle.

## Points d'attention récurrents

- Bien vérifier le zip reçu : plusieurs fois une version obsolète a été envoyée
  (vérifier la présence des derniers `doc/redemarrage_*.md`).
- Après chaque str_replace, vérifier le code de sortie ET l'absence de message
  d'erreur (des coquilles JS/py ont été introduites puis corrigées).
