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
  "format_version": "1.0",
  "cree_le": "2026-10-08T19:05:00+02:00",
  "cree_par": "seqenseigne 0.51.2 (atelier)",
  "nom": "paquet_2026-10-08_1905.zip",
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
