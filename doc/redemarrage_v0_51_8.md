# Redémarrage v0.51.8 — Retour d'usage et états de synchronisation

Seconde version du protocole d'échange (v0.51.7 : identités, paquets
numérotés). Format : `doc/format_usage.md`. Préalable à la bascule
(v0.51.9) : quand les données de classe auront quitté la base de l'atelier,
ses verrous viendront des retours d'usage.

## Décisions (validées)

- Contenu : par référentiel importé, empreinte de la publication, utilisé et
  depuis quand, date de début du premier créneau de chaque séquence
  planifiée, parties de MER posées ; rien sur les élèves, les classes, les
  établissements.
- Appli en ligne : tuile « Retour d'usage » du tableau de bord (aperçu,
  « Créer le retour d'usage (n° …) », retours envoyés avec « Renvoyer »,
  identité, atelier lié, paquet attendu).
- Atelier : tuile Publication, « Importer un retour d'usage… » ; règle
  stricte (n° attendu seulement) ; l'accusé du retour acquitte les paquets
  (retirés de l'archive) ; l'accusé de chaque paquet acquitte les retours.
- Verrous jamais perdus : usage réuni aux retours précédents ; séquence
  commencée = premier créneau passé (à la date de l'atelier) ou partie de
  MER posée ; référentiel utilisé ; interne verrouillé → « utilisé ».
- Retour portant sur une autre version que la dernière publiée : appliqué
  quand même (les verrous reflètent la réalité en classe), et l'état de
  synchronisation le dit (en retard, désynchronisé).
- États de synchronisation (badge de chaque référentiel de la tuile
  Publication) : synchronisé, modifié depuis la publication, publication en
  attente, en retard, désynchronisé (et jamais publié).

## Code

- `services/retour_usage.py` (nouveau) : `construire`, `creer` (classe) ;
  `lire`, `analyser`, `importer`, `usage`, `sequence_commencee`, `utilise`,
  `etat_synchro`, `journal` (atelier) ; table `usage_recu`.
- `routes/retour_usage.py` (nouveau) : `POST /api/retour-usage/creer`,
  `GET …/apercu` (classe) ; `POST …/analyse`, `POST …/importer`, `GET
  …/etat` (atelier) — classés route par route (`services/profils.py`).
- `services/referentiel_principal_externe.py` : `est_utilise` et
  `sequence_commencee` consultent aussi les retours.
- `services/paquet_publication.py` : `synchro` dans les publiables.
- `services/import_publication.py` : l'accusé du paquet acquitte les retours.
- `static/tableau_bord.js`, `static/echanges.js`, `templates/index.html`,
  `static/app.css` : tuile Retour d'usage, import dans la tuile Publication,
  badges de synchronisation, envois et réceptions des deux types.
- Tests : `tests/test_v0_51_8_retour_usage.py`.
