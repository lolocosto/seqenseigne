# Redémarrage v0.19.1.0 — La progression devient un atelier d'assemblage (ossature OO)

Première livraison du chantier v0.19.1 « refonte de la construction de
progression ». La progression, jusqu'ici codée en procédural dans `app.js`
(~1050 lignes de fonctions `prog*()`), devient un **atelier d'assemblage OO**
(`AtelierProgression extends AtelierAssemblage`), aligné sur l'atelier
Séquence-niveau (`AtelierSeqnivAssemblage`).

Cette livraison **0.19.1.0** porte l'**ossature** : structure OO, bandeau à 4
sélecteurs, barre latérale des parties, calendrier au centre, cycle de vie du
créneau. Le **drag-and-drop** parties → calendrier et le **changement de
référentiel** (avec purge) arrivent en **0.19.1.1**.

Cadrage : audit `doc/audit_v0_19_correspondance_referentiel_progression.md` +
session de cadrage v0.19.1 (décisions D1–D7, D-A/B/D, Q-F/G ci-dessous).

## Décisions appliquées

- **D1** — Refonte OO complète. Nouveau fichier `static/atelier_progression.js`
  (`AtelierProgression extends AtelierAssemblage`, instance unique
  `window.ATELIER_PROGRESSION`). `estPluriel = false` (une progression par
  triplet, déterminée par les sélecteurs — pas de liste en barre latérale),
  `persistanceImmediate = true` (les opérations de structure persistent au vol
  via les routes créneau ; pas de bouton « Enregistrer » global). Le procédural
  `prog*()` est retiré d'`app.js`.
- **D2** — Bandeau supérieur du panneau principal à **4 sélecteurs** :
  Année · Établissement · Niveau · **Référentiel support**. Le 4e sélecteur ne
  liste que les référentiels du niveau en état `verrouille` **ou** `utilise`.
  La clé métier d'une progression reste le **triplet** (année/étab/niveau) ; le
  référentiel est un attribut de la progression.
- **D3** — Barre latérale = **toutes** les parties de séquence du référentiel
  support. Chaque partie placée porte un badge indiquant les **numéros de
  semaine** où elle est posée (les parties restent en barre latérale même
  placées, comme les éléments de l'assemblage de séquence). Une partie posée
  mais non encore datée affiche « posée, à dater ».
- **D4** — Calendrier semainier déplacé dans le **panneau principal** (il sera
  la cible de drop en 0.19.1.1). Détail du créneau sélectionné à droite.
- **D7** — Périmètre strict : **aucune** fonctionnalité nouvelle (semaines A/B,
  séances déplacées, comptage prévu/réalisé). Refonte structure + UI seulement.
- **D-A** — Filtre d'état exposé sur `GET /api/referentiels` via le paramètre
  `etats` (CSV). Nouvelle route `GET /api/referentiels/<id>/parties`.
- **Q-F (b)** — Ajout d'un créneau par **clic** sur une partie → créneau créé
  **sans date** ; l'enseignant le date ensuite dans le détail (cohérent avec le
  modèle « En cours » de l'appli). Le drag-drop viendra en 0.19.1.1.
- **Q-G (a)** — Persistance immédiate : pas de bouton « Enregistrer » global.
  Il réapparaîtra (régime mixte, comme le seqniv) quand des champs de saisie
  bufferisés seront introduits.

Reporté à **0.19.1.1** : drag-drop parties → calendrier (transport typé
`DRAG = {kind, …}` du seqniv, couche simple — D-D) ; route
`POST /api/progression_id/<id>/referentiel` (changement de référentiel avec
purge des créneaux, refusé hors état `en_cours`, avec confirmation — D5) ;
rétrogradation de l'ancien référentiel `utilise → verrouille` s'il n'est plus
référencé, sauf si la progression est `annule` (D-B).

## Changements

### Base de données / store
- `persistence/sqlite_store.py` :
  - **`lister_parties_referentiel(referentiel_id)`** (nouveau) : liste à plat
    des parties `(seq_code, partie_numero)` du référentiel **figé** (lit le
    snapshot `referentiel_sequences` / `referentiel_objectifs`, pas les tables
    actives), avec `nb_objectifs` et `nb_seances_prevues` (castés en int).
    Retourne `None` si le référentiel est introuvable. Une séquence sans
    objectif expose tout de même une partie 1 (posable).

### Routes
- `routes/referentiels.py` :
  - `GET /api/referentiels` : nouveau paramètre **`etats`** (CSV, ex.
    `verrouille,utilise`) → post-filtrage par état (après la maj lazy de
    `lister_par_niveau`).
  - `GET /api/referentiels/<ref_id>/parties` (nouveau) : expose
    `lister_parties_referentiel` (+ entête `ref`). 404 si introuvable.
- `routes/progression.py` :
  - `POST .../creneau-ajouter` et `DELETE .../creneau/<id>` acceptent désormais
    un **`progression_id`** optionnel dans le body → désambiguïsation quand
    plusieurs établissements partagent le même couple (niveau, année). Sans cet
    id, `lire_progression` retombait sur l'établissement « Non renseigné » :
    **bug latent** corrigé (l'UI gère plusieurs établissements).

### Front
- `static/atelier_progression.js` (nouveau) : classe `AtelierProgression`.
  Pilote son propre cycle de vie (comme le seqniv `estPluriel:false`) :
  `init()` (sélecteurs), `rafraichir()` (charge/crée la progression du
  quadruplet), barre latérale des parties + badges semaines, calendrier (rendu
  interne réutilisant les helpers purs d'`app.js`), `poserPartie` (clic → sans
  date), `selectionnerCreneau` / `sauvegarderCreneau` (PATCH au vol) /
  `supprimerCreneau`, `changerEtat`, livrets en lecture seule. Expose
  `window.ATELIER_PROGRESSION` et `window.progInit`.
- `static/app.js` : suppression du bloc procédural `prog*()` (variables
  `PROG_*`, `progInit/Recherche/Render*/Ajout*/Creneau*/ChangerEtat/…`). Les
  **helpers calendrier purs sont conservés** (`_dateToISO`, `_lundisEntre`,
  `_bornesAnneeScolaire`, `_jourSemaine`, `_vacancesDeLaSemaine`,
  `_feriesDeLaSemaine`, `_dateCourte`, `MOIS_FR`, `JOUR_FR`, `CAL_*`) car la
  classe les consomme via `window.*`. `sousOnglet('progression')` appelle
  désormais `window.progInit()`.
- `templates/index.html` : `#stab-progression` restructuré en `atl-shell`
  (sidebar parties / main = bandeau 4 sélecteurs + calendrier + détail).
  Script `atelier_progression.js` chargé après `atelier_evaluation_oo.js`.
- `static/app.css` : styles `.prog-bandeau*`, `.prog-zone`, `.prog-calendrier`,
  `.prog-detail`, `.prog-partie-item`, badges `.prog-partie-semaine-badge`.

## Tests

- `tests/test_v0_19_1_0_atelier_progression_backend.py` (nouveau, 13 cas) :
  `lister_parties_referentiel` (ordre, comptes objectifs/séances, métadonnées
  séquence, séquence sans objectif, introuvable) ; route `/parties` (200/404) ;
  filtre `etats` (sans filtre, verrouille+utilise, un seul état) ;
  désambiguïsation créneau par `progression_id` (ajout, suppression) ; créneau
  sans date accepté.
- `tests_js/atelier_progression.test.js` (nouveau, 14 cas) : contrat OO
  (héritage, config, `progInit`, `modifie` immédiat) ; `_semainesParPartie`
  (sans progression, créneau non daté → entrée vide, n° de semaine, dédoublon
  multi-semaines, fallback `partie_debut`) ; `_estModifiable` (en_cours+académie,
  validée, verrouillée, académie absente).

**Zéro régression** : pytest → 3854 passed, 7 skipped ; vitest → 167 passed.

## Vérification & déploiement

Aucune migration de base : la structure de données est inchangée (lecture du
référentiel figé existant + routes créneau existantes enrichies d'un paramètre
optionnel rétrocompatible).

Après déploiement du delta sur D:/E:, vérifier l'intégrité :

    python -m outils.verifier_md5

Puis, dans l'onglet « Progression annuelle » : choisir Année + Établissement +
Niveau + Référentiel ; la barre latérale liste les parties du référentiel, le
calendrier s'affiche au centre ; cliquer une partie crée un créneau non daté
(badge « posée, à dater ») ; le dater dans le détail à droite fait apparaître
ses semaines en badge dans la barre latérale.

## Suite (v0.19.1.1)

Drag-drop parties → calendrier ; changement de référentiel support (avec purge
des créneaux, confirmation, restreint à l'état `en_cours`) ; rétrogradation de
l'ancien référentiel. Puis fonctionnalités v0.19.2+ (semaines A/B, séances
déplacées, comptage prévu/réalisé).
