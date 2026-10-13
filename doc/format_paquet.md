# Paquet de publication — `seqenseigne.paquet` v1

> Version du format : **1.0** (seqenseigne v0.51.2).
> Code : `services/paquet_publication.py`. Contenu des référentiels :
> `doc/format_referentiel.md`.

## Rôle

Transporter un ou plusieurs référentiels de l'appli locale (profil
**atelier**) vers l'appli en ligne (profil **classe**) : structure (un JSON
par référentiel) **et** contenu des documents (PDF compilés, fichiers
déposés). Aujourd'hui par fichier (import en v0.51.3) ; plus tard envoyé par
l'API de publication.

## Contenu du zip

```
paquet_2026-10-08_1905.zip
├── paquet.json                    manifeste
├── referentiels/N11_v2025.json    un JSON par référentiel (seqenseigne.referentiel v1)
├── referentiels/M2026_N09.json
└── fichiers/c32fb78b….pdf         contenu des documents, nommés par leur sha256
```

- Les fichiers sont nommés par leur empreinte : un même fichier, utilisé par
  plusieurs documents ou référentiels, n'est stocké qu'une fois.
- Les PDF sont stockés sans recompression (déjà compressés).

## `paquet.json`

```json
{
  "format": "seqenseigne.paquet",
  "format_version": "1.1",
  "echange": {
    "type": "paquet", "numero": 3,
    "emetteur": { "id": "inst_5eb6…", "nom": "Atelier — maison", "role": "atelier" },
    "destinataire": "inst_48be…",
    "accuse": 2
  },
  "cree_le": "2026-10-08T19:05:00+02:00",
  "cree_par": "seqenseigne 0.51.7 (atelier)",
  "nom": "paquet_0003_2026-10-08_1905.zip",
  "referentiels": [
    { "id": "N11_v2025", "nom": "4e — 2025-2026 — Principal", "niveau": "N11",
      "type": "principal", "empreinte": "sha256:…", "chemin": "referentiels/N11_v2025.json" }
  ],
  "fichiers": [
    { "sha256": "c32f…", "chemin": "fichiers/c32f….pdf", "taille": 1690811,
      "mime": "application/pdf" }
  ],
  "rapport": {
    "documents_sans_pdf": ["4e — 2025-2026 — Principal : Planches de cartes d'automatisme — S01"],
    "parties_ecart": ["6e — 2026-2027 — MER : M01 partie 2 : 4 saisie(s) sur la partie, 0 d'après les objectifs"],
    "erreurs": [],
    "taille_totale": 15012345
  }
}
```

- `referentiels[].empreinte` = `empreinte` du JSON correspondant.
- `rapport` : documents compilés sans PDF (non publiés), parties dont la
  durée saisie diffère de la somme des objectifs (la durée publiée est la
  somme), taille totale des fichiers. `erreurs` est toujours vide dans un
  paquet créé (une erreur empêche la création).

### En-tête d'échange (`echange`, format 1.1, v0.51.7)

Protocole sur le modèle des datagrammes acquittés (`services/echanges.py`) :

- `emetteur` : identité de la base qui produit le paquet (identifiant créé à
  la première utilisation, nom modifiable, rôle `atelier`) ;
- `destinataire` : identifiant de l'appli en ligne liée, `null` tant
  qu'aucun retour n'a été reçu d'elle ;
- `numero` : numéro d'ordre des paquets de cet atelier (1, 2, 3…) ;
- `accuse` : dernier numéro de retour d'usage reçu de l'appli en ligne
  (`null` si aucun ; retours d'usage : v0.51.8).

À la réception, l'appli en ligne :
- se lie à l'atelier au premier paquet accepté ; refuse ensuite tout paquet
  d'un autre atelier, ou destiné à une autre instance ;
- n'accepte que le **numéro attendu** (dernier reçu + 1) : un numéro déjà
  reçu est ignoré (refus « déjà reçu ») ; un trou est refusé avec la liste
  des numéros manquants, à demander à l'atelier (« Renvoyer ») ;
- accepte un paquet sans en-tête (format 1.0, antérieur à la v0.51.7) tant
  qu'aucun paquet numéroté n'a été reçu ;
- en base partagée (même identifiant), ne contrôle pas la séquence.

L'atelier archive chaque paquet (`data/echanges/envoyes/`) pour pouvoir le
renvoyer ; un paquet acquitté par un retour d'usage est retiré de l'archive.

**Boîte aux lettres (v0.51.9)** : un envoi peut aussi être déposé dans le
dossier d'entrée de l'appli destinataire (copie automatique par le dossier
de sortie de l'émetteur). Relevé au démarrage puis périodiquement, il est
traité dans l'ordre des numéros ; un envoi hors séquence **attend** dans le
dossier l'arrivée du manquant (au lieu d'être refusé), un doublon va dans
`traites/`, un envoi refusé dans `refuses/` avec sa raison.

## Règles de création

- **Publiables** : référentiels internes **verrouillés ou utilisés** (les
  seuls qu'acceptent les progressions) ; externes et MER de la structure
  figée **non annulés**. L'ancien modèle de MER ne l'est pas.
- Publier un référentiel interne verrouillé **fige sa publication**
  (première publication conservée, resservie ensuite).
- La création est **refusée** (rapport détaillé) si : un référentiel n'est
  pas publiable ou ne respecte pas le format ; un fichier d'un document est
  introuvable ; un fichier a changé depuis la publication figée (empreinte
  différente).
- Chaque paquet créé est inscrit au **journal** (table `publications` :
  date, nom, référentiels et empreintes, nombre de fichiers, taille) ; il
  alimente « dernière publication » et « modifié depuis ».

## Vérification (lecture)

`paquet_publication.verifier(contenu)` → (manifeste, erreurs) : zip lisible,
format et version majeure, présence et **empreinte de chaque fichier**,
validité et empreinte de chaque référentiel, fichier présent pour chaque
document. L'import côté classe (v0.51.3) commence par cette vérification et
n'importe rien si elle échoue.

## Dans l'appli

- Tableau de bord (profil atelier), tuile **Publication** : référentiels
  publiables groupés par niveau, état (jamais publié, publié le…, modifié
  depuis, format invalide), cases à cocher, « Cocher les non publiés et
  modifiés », **Créer le paquet** (téléchargement), résumé, dernières
  publications.
- Routes (profil atelier ou complet) : `GET /api/publication/publiables`,
  `POST /api/publication/paquet` (`{"referentiels": [id…]}` → zip ; en-tête
  `X-Paquet-Resume`), `GET /api/publication/journal`.

## Import (v0.51.3, profil classe)

Système › Administration › **Import référentiels** : *Analyser* (rien n'est
écrit) puis *Importer*. Statuts : nouveau, mise à jour (changements
détaillés), identique, refusé (séquence ou partie commencée retirée, conflit
niveau/version, référentiel conçu dans la même base). Les associations de
documents qui deviennent orphelines sont signalées et conservées. Détail :
`services/import_publication.py`, `doc/redemarrage_v0_51_3.md`.
Essai sur une base vide : `lancer.bat classe --base-classe` (dossier
`data_classe\`).
