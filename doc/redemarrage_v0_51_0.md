# Redémarrage v0.51.0 — Profils de lancement (séparation en deux outils)

Premier pas du chantier « séparer l'appli en 2 » : une appli locale de
conception (avec LaTeX) et une appli en ligne de suivi des classes (sans
LaTeX), sur un seul code.

## Décisions validées (cadrage v0.51)

- Un seul code, trois profils : `complet` (défaut, comportement d'avant),
  `atelier`, `classe`. Le profil se choisit au lancement.
- Tous les référentiels (internes ET externes) se conçoivent dans l'appli
  locale (profil atelier) ; l'appli en ligne les reçoit en lecture seule.
- La structure des référentiels sera formalisée en JSON (schéma versionné)
  pour, à terme, une API qui alimente l'appli en ligne depuis l'appli locale.
- En ligne : mono-utilisateur, avec authentification (v0.52).
- Deux tableaux de bord : pilotage de la conception (atelier), pilotage de
  l'activité des classes (classe).
- Types de documents : structure, définis dans l'atelier et publiés.
- « Import suivi » (classes historiques depuis SequencesDB, qui crée aussi le
  référentiel) : profil complet seulement, outil de transition (l'essentiel
  des données historiques est déjà importé).
- Lancement : `lancer.bat atelier` (port 5000), `lancer.bat classe`
  (port 5001), sans paramètre = complet (port 5000).

Découpage : v0.51.0 profils ; v0.51.1 format JSON des référentiels (schéma
soumis avant code) ; v0.51.2 paquet de publication ; v0.51.3 import côté
classe ; v0.51.4 bascule des données de classe ; v0.52.x mise en ligne
(authentification, HTTPS, VPS) puis API de publication.

## Répartition

| Élément | atelier | classe |
|---|---|---|
| Tableau de bord | atomes à finaliser, non rattachés | séances de la semaine |
| Conception de référentiel | oui | — |
| Suivi, Planification, Paramétrage, export/import JSON (en-tête) | — | oui |
| Système › Administration | import référence, mise en forme, images, fiches ; base de données (auto-import des cycles, réinit. référence / mise en forme) | base de données (réinit. suivi) |
| Système › Préférences | édition, assemblage, types de documents, outils, chemins | types de mise en route |
| Import suivi, « Tout réinitialiser » | profil complet seulement | |

## Code

- `services/profils.py` (nouveau) : catégorie de chaque blueprint (atelier,
  structure, classe, commun) et exceptions par route (`ENDPOINTS`) ;
  `blueprint_enregistre` (un blueprint étranger au profil n'est pas
  enregistré) ; garde `before_request` : 404 hors profil, 403 pour une
  écriture sur la structure depuis le profil classe ; profil injecté dans
  les gabarits.
- `app.py` : `create_app(data_dir, profil=None)` ; lancement direct : profil
  `SEQ_PROFIL`, port `SEQ_PORT` (5001 par défaut en classe).
- `lancer.bat` : paramètres `atelier` / `classe` / `complet` et
  `--skip-verify`, dans n'importe quel ordre.
- `templates/index.html` : `<html data-profil>`, `window.SEQ_PROFIL`, badge
  du profil dans l'en-tête, attributs `data-profils` (onglets, tuiles,
  sous-onglets d'administration, blocs de la base de données, catégories de
  préférences, export/import JSON).
- `static/app.css` : règle d'affichage par profil, badge.
- `static/app.js` : `profilPermet`, `profilAffiche` ; `init()` sans classes
  en atelier ; préférences de conception chargées en atelier seulement ;
  premier sous-onglet d'administration visible.
- `static/tableau_bord.js` : tuiles chargées selon le profil.

## Tests

- `tests/test_v0_51_0_profils.py` : lecture du profil, classification
  complète, complet inchangé, classe sans aucun blueprint de compilation,
  toute route de conception refusée en classe, structure en lecture seule
  (403), routes communes, atelier sans routes de classe, page principale.
- `tests_js/profils.test.js`.
- Parcours navigateur des trois profils (clic sur tous les onglets et
  sous-onglets de navigation) : aucun appel refusé, aucune erreur JS.

## À noter

- Tant que l'import (v0.51.3) et la bascule (v0.51.4) n'existent pas, les
  profils atelier et classe lisent la même base (`data/`).
- `lancer.bat` change : régénérer la référence d'intégrité
  (`appli_inventaire.txt`) après déploiement, comme d'habitude.
