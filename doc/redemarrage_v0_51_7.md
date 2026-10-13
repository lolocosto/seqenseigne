# Redémarrage v0.51.7 — Protocole d'échange (paquets)

Première des deux versions du protocole d'échange atelier ↔ classe, proposé
par l'auteur sur le modèle des datagrammes : instances identifiées, envois
numérotés en séquence, en-têtes, demande des fichiers manquants, pour une
cohérence chronologique des changements. Cette version l'applique aux
paquets de publication ; la v0.51.8 y ajoute le retour d'usage (classe →
atelier), les acquittements et les états de synchronisation ; la v0.51.9
fait la bascule. Format : `doc/format_paquet.md` (format 1.1).

## Décisions (validées)

- **Identité** : chaque base a un identifiant unique (créé à la première
  utilisation) et un nom modifiable ; au premier échange reçu, elle se lie
  à son correspondant (un atelier ↔ une appli en ligne) ; un fichier d'une
  autre instance, ou destiné à une autre, est refusé ; « délier » permet
  d'oublier le correspondant (base recréée, autre machine).
- **En-tête** de chaque envoi : type, émetteur, destinataire, numéro d'ordre
  (propre à l'émetteur et au type), accusé (dernier numéro reçu de l'autre
  côté).
- **Règle stricte**, des deux côtés (paquets et retours d'usage) : seul le
  numéro attendu est accepté ; déjà reçu → ignoré ; trou → refusé avec les
  numéros à redemander (« Renvoyer » dans l'atelier).
- Paquets antérieurs (sans en-tête) acceptés tant qu'aucun paquet numéroté
  n'a été reçu. Base partagée (même identifiant) : pas de contrôle.
- **Archive** des envois (`data/echanges/envoyes/`, hors dépôt) ; retirée à
  l'acquittement (les acquittements arrivent avec les retours d'usage,
  v0.51.8).
- Un paquet attendu dont tous les référentiels sont « identiques »
  s'importe quand même : la séquence avance.

## Code

- `services/echanges.py` (nouveau) : `instance`, `renommer`,
  `correspondant`, `delier`, `entete`, `archiver`, `envois`, `lire_archive`,
  `acquitter`, `controler`, `enregistrer_reception`, `recus`, `etat` ;
  tables `instance_locale`, `correspondants`, `echanges_envoyes`,
  `echanges_recus`.
- `routes/echanges.py` (nouveau, commun aux profils) : `GET
  /api/echanges/etat`, `PUT /api/echanges/instance`, `GET
  /api/echanges/envois/<type>/<n>` (renvoi), `DELETE
  /api/echanges/correspondants/<role>`.
- `services/paquet_publication.py` : en-tête `echange`, nom
  `paquet_<n>_<date>.zip`, archive, colonne `publications.numero`, format
  1.1.
- `services/import_publication.py` : contrôle de séquence à l'analyse et à
  l'import (refus 409), lien et réception enregistrés.
- `static/echanges.js` (nouveau), `static/tableau_bord.js`,
  `static/import_publication.js`, `templates/index.html`, `static/app.css` :
  bloc identité / correspondant / envois (tuile Publication), réceptions et
  numéro attendu (Import de référentiels), message de séquence.
- `.gitignore` : `data/echanges/`.
- Tests : `tests/test_v0_51_7_echanges.py` ; tests v0.51.2, v0.51.3,
  v0.51.4 adaptés.

## À noter

- Renommer les deux instances (atelier, appli en ligne) dès la première
  utilisation : le nom par défaut est celui de la machine.
