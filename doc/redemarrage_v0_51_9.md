# Redémarrage v0.51.9 — Boîte aux lettres (échange asynchrone)

Demande de l'auteur : ne pas exiger que l'atelier et l'appli en ligne
tournent en même temps. Chaque appli a un **dossier d'entrée** qu'elle relève
au démarrage puis périodiquement ; les envois y attendent leur traitement.

## Décisions (validées)

- Un dossier d'entrée par instance (défaut `data\echanges\entrants\`,
  réglable) ; un dossier de sortie facultatif où chaque envoi créé est
  copié (le dossier d'entrée de l'autre appli tant que les deux sont sur le
  même PC, ou un dossier synchronisé).
- Relève au démarrage, puis toutes les 5 minutes (réglable de 1 à 1440), et
  à la demande (« Relever le dépôt »).
- Un seul réglage de traitement : **confirmation** (défaut : la relève liste,
  « Traiter » applique) ou **automatique** (appliqué dès la relève, mêmes
  règles qu'à la main).
- Tampon de réception : traitement dans l'ordre des numéros ; un envoi hors
  séquence **reste dans le dossier** (« en attente, il manque le n° k »)
  jusqu'à l'arrivée du manquant ; doublon → `traites\` sans rien appliquer ;
  autre instance, fichier illisible, envoi qui ne se traite pas dans cette
  appli → `refuses\` avec un fichier `.raison.txt` ; envoi traité →
  `traites\`. Journal de la boîte aux lettres.
- L'import manuel par fichier reste possible (règle stricte).
- API de la v0.52 : la boîte aux lettres en fait un simple transport ; la
  v0.52 choisira entre un dossier synchronisé et une API réduite à
  « déposer / relever » (ROADMAP).

## Code

- `services/depot.py` (nouveau) : `reglages`, `definir`, `dossier_entrants`,
  `copier_sortant`, `lister`, `relever`, `etat`, `demarrer` (fil de relève,
  lancé par `app.py` au démarrage réel seulement — une fois en mode debug) ;
  tables `depot_reglages`, `depot_journal`.
- `routes/depot.py` (nouveau, commun) : `GET /api/depot/etat`, `POST
  /api/depot/relever`, `PUT /api/depot/reglages`.
- `services/echanges.py` : `archiver` copie l'envoi dans le dossier de
  sortie.
- `static/echanges.js` (`depotRendre`), `static/tableau_bord.js`,
  `static/app.css` : bloc « Boîte aux lettres » dans la tuile Publication
  (atelier) et la tuile Retour d'usage (appli en ligne).
- Tests : `tests/test_v0_51_9_depot.py`.

## À noter

- Pour essayer sur un seul PC : dans l'atelier, dossier de sortie = dossier
  d'entrée de l'appli en ligne (`…\data_classe\echanges\entrants` avec
  `--base-classe`), et inversement.
- Les sous-dossiers `traites\` et `refuses\` se vident à la main.
