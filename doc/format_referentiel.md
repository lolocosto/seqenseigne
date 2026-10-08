# Format d'échange d'un référentiel — `seqenseigne.referentiel` v1

> Version du format : **1.0** (seqenseigne v0.51.1 ; précisions v0.51.2 :
> durée d'une partie, documents sans PDF, type des objectifs internes,
> accents). Transport : paquet de publication, voir `doc/format_paquet.md`.
> Schéma officiel : `schemas/referentiel-1.json` (JSON Schema 2020-12).
> Code : `services/format_referentiel.py` (export, empreintes, validation),
> `services/texte_latex.py` (textes sans LaTeX), `services/schema_json.py`
> (validateur sans dépendance).

## Rôle

Le format transporte un référentiel de l'appli locale (profil **atelier**, où
tous les référentiels sont conçus) vers l'appli en ligne (profil **classe**,
sans LaTeX), qui le reçoit en lecture seule. Il est la base du paquet de
publication (v0.51.2) et de la future API de publication.

Un fichier = un référentiel : interne ou externe, principal ou de MER. Le
fichier **se suffit à lui-même** : il décrit la structure qu'il utilise
(cycle, niveau, thèmes, découpage en séquences du niveau), puis le détail de
chaque séquence. L'appli en ligne n'a besoin d'aucune table de cycle, de
thèmes ou de séquences en dehors des référentiels publiés.

Seuls les référentiels de la **structure figée** sont exportables. L'ancien
modèle de MER ne l'est pas : il faut d'abord le recréer.

## Vue d'ensemble

```json
{
  "format": "seqenseigne.referentiel",
  "format_version": "1.0",
  "exporte_le": "2026-10-08T17:40:00+02:00",
  "exporte_par": "seqenseigne 0.51.1 (atelier)",
  "empreinte": "sha256:…",
  "referentiel": { … },
  "structure": { … },
  "types_documents": [ … ],
  "sequences": [ … ],
  "documents_annuels": [ … ],
  "publication_figee": true
}
```

| Champ | Contenu |
|---|---|
| `format`, `format_version` | Identifiant et version du format (voir « Versions »). |
| `exporte_le`, `exporte_par` | Date de l'export (ISO 8601) et appli qui l'a produit (version, profil). |
| `empreinte` | Empreinte du contenu (voir « Empreintes »). |
| `referentiel` | Fiche du référentiel. |
| `structure` | Structure utilisée : cycle, niveau, thèmes, découpage. |
| `types_documents` | Types de documents utilisés par les fichiers du référentiel. |
| `sequences` | Détail de chaque séquence du découpage : parties, objectifs, documents. |
| `documents_annuels` | Documents rattachés à l'année (ni séquence ni partie). |
| `publication_figee` | Facultatif : `true` si le document vient d'une publication conservée. |

## `referentiel`

```json
{ "id": "2025_N11", "nom": "4e — 2025-2026 — Principal", "niveau": "N11",
  "annee": "2025-2026", "type": "principal", "source": "interne",
  "version": "2025", "etat": "verrouille", "description": "",
  "mode_seances": "par_objectif" }
```

- `id` : identifiant **stable** du référentiel, inchangé d'une publication à
  l'autre (`2025_N11`, `X2026_N11a` pour un externe, `M2026_N09` pour une
  MER…). C'est la clé qu'utilisent les progressions côté classe.
- `type` : `principal` ou `mer` ; `source` : `interne` ou `externe`.
- `etat` : `en_cours`, `valide`, `verrouille`, `utilise`, `annule`.
- `mode_seances` (facultatif, internes) : mode de calcul des séances repris
  tel quel (`par_objectif`, `par_serie`).

## `structure`

```json
{
  "empreinte": "sha256:…",
  "cycle":  { "code": "C04", "nom": "Cycle 4" },
  "niveau": { "code": "N11", "nom_court": "4e", "nom_long": "quatrième",
              "annee_dans_cycle": 2 },
  "themes": [ { "code": "A", "nom": "Nombres et calculs", "couleur": "nombres", "ordre": 1 } ],
  "decoupage": [ { "code": "S05", "numero": 5, "nom": "Calcul littéral", "theme": "A" } ]
}
```

- Décrit la structure **telle qu'elle était quand le référentiel a été
  figé** (tables figées du référentiel), limitée au niveau : seules les
  séquences de ce niveau figurent dans `decoupage`.
- `numero` : numéro de la séquence dans le cycle ; `theme` : code d'un thème
  de `themes`, ou `null` (externes et MER n'ont en général pas de thèmes).
- `cycle` vaut `null` si le niveau n'est rattaché à aucun cycle connu.
- `empreinte` : empreinte du bloc (hors ce champ). Deux référentiels de même
  empreinte de structure ont la même structure et se comparent séquence par
  séquence.

**Un code de séquence n'a de sens que dans son référentiel** : le « S05 » de
2025 et celui de 2026 peuvent désigner deux séquences différentes. Côté
classe, une séquence est toujours repérée par le couple (référentiel, code).

### Quand la structure change

- **Nombre de thèmes, découpage en séquences, renumérotation** : on crée un
  nouveau référentiel dans l'atelier, avec sa nouvelle structure (nouvelle
  empreinte). Les référentiels déjà publiés gardent la leur ; les classes qui
  les utilisent ne sont pas touchées. Les nouvelles progressions se
  rattachent au nouveau référentiel.
- **Référentiel externe qui évolue** (séquence ou fichiers ajoutés en cours
  d'année) : même identifiant ; l'import côté classe (v0.51.3) compare les
  structures, rapporte les ajouts et modifications, et refuse la suppression
  ou la réorganisation d'une séquence déjà commencée.

## `sequences`

Une entrée par séquence du découpage, dans le même ordre.

```json
{ "code": "S05",
  "parties": [ {
    "numero": 1, "libelle": "Développer", "nb_seances": 3, "nb_seances_saisie": 4,
    "objectifs": [ {
      "code": "01", "type": "connaissance", "nom": "Connaître les notions et les méthodes",
      "nb_seances": 1, "fin_cycle": false,
      "criteres": { "F": "…", "A": "…", "E": "…" }
    } ],
    "notions":  [ { "id": "n_dist", "titre": "Distributivité" } ],
    "methodes": [ { "id": "m_dev", "titre": "Développer un produit" } ],
    "documents": [ … ]
  } ],
  "documents": [ … ] }
```

- Partie : `numero` (clé), `libelle` (facultatif, peut être vide),
  `nb_seances` = **somme des séances de ses objectifs** (règle : la durée
  d'une partie se calcule ; la progression en déduit un nombre de semaines
  selon le nombre de séances par semaine du niveau), `nb_seances_saisie`
  (valeur saisie sur la partie, pour information ; un écart est signalé dans
  la vérification et le rapport de publication), `seances_par_serie`
  (internes en mode `par_serie` seulement : `niveau_cible`, `serie`,
  `nb_seances`).
- Objectif : `code` (clé dans la séquence), `type` (`connaissance` ou
  `capacite`), `nom`, `nb_seances`, `fin_cycle`, `criteres` F / A / E. Pour
  un référentiel **interne**, le type se déduit de la position : le premier
  objectif de chaque partie est « Connaître les notions et les méthodes »
  (`connaissance`), les autres sont des capacités ; pour un externe, c'est
  le type saisi.
- `notions`, `methodes` : **titres seulement**, pour la synthèse Pronote
  (ligne « Cours : ») — identifiants et titres, pas de contenu. Vides pour un
  référentiel externe. Le contenu (cours, exercices, fiches, cartes) est porté
  par les documents PDF.

## Documents

```json
{ "ref": "rnf_8a1…", "origine": "fichier", "type": "td_x",
  "libelle": "Fiche d'activité : activite.pdf",
  "fichier": { "nom": "activite.pdf", "mime": "application/pdf", "taille": 120443,
               "sha256": "…" },
  "placement": { "seance": 2, "retour": "rendre", "delai": { "type": "semaines", "n": 1 } } }
```

- Rattachement : par sa place dans le fichier (partie, séquence ou
  `documents_annuels`).
- `ref` : clé **stable**, celle qu'utilisent déjà les associations de
  documents côté classe : identifiant du fichier pour un fichier déposé
  (`origine: "fichier"`), `type|cible` pour un PDF compilé d'un interne
  (`origine: "compile"`, ex. `livret_sequence|N11/S05`,
  `evaluation|ev_12`).
- `type` : identifiant d'un type de `types_documents` (fichiers), ou type de
  document compilé (`livret_cours`, `evaluation`…) ; `null` si non typé.
- `fichier` : nom, type MIME, taille, `sha256` du contenu. **Le contenu
  n'est pas dans le JSON** : il voyage dans le paquet de publication
  (v0.51.2), vérifié par son empreinte. Un document **compilé sans PDF**
  n'est pas publié (il figure seulement dans le rapport : pour un référentiel
  verrouillé, il ne viendra plus) ; `sha256` manque si un fichier déposé est
  absent du disque (la publication est alors refusée).
- `placement` (fichiers de partie, facultatif) : séance de distribution dans
  la partie, retour attendu (`faire`, `rendre` ou `null`), délai (`prochaine`,
  `jours`, `semaines`, `fin_creneau`, `fin_partie` ; `n` pour jours et
  semaines). `null` si aucun placement par défaut.

## `types_documents`

Types utilisés par les fichiers du référentiel : `{ "id": "td_x", "libelle":
"Livret de cours" }`. Ils se définissent dans l'atelier (Système ›
Préférences) et sont publiés avec les référentiels.

## Textes

L'appli en ligne n'a pas LaTeX. Tous les textes (noms de thèmes, de
séquences, de parties et d'objectifs, critères, titres de notions et de
méthodes) sont exportés en **texte lisible** (Unicode : `\frac{1}{2}` → 1/2,
`a^2` → a², `\times` → ×, `\og … \fg` → « … », `~` → espace insécable,
`\'E` → É, `\oe uvre` → œuvre…).
Quand la source LaTeX diffère, elle est conservée à côté dans un champ
`…_latex` (`nom_latex`, `libelle_latex`, `criteres_latex`), pour un rendu
mathématique éventuel plus tard.

## Empreintes

- `empreinte` : `sha256:` + hachage SHA-256 du document en JSON canonique
  (clés triées, sans espaces, UTF-8), **sans** `exporte_le`, `exporte_par`,
  `empreinte`, `publication_figee` ni `referentiel.etat`. Deux publications
  identiques ont la même empreinte : l'appli en ligne sait qu'il n'y a rien à
  mettre à jour. Le changement d'état (verrouillé → utilisé) ne change pas
  l'empreinte.
- `structure.empreinte` : même calcul sur le seul bloc `structure`.
- `fichier.sha256` : hachage du contenu du fichier.

## Publication figée

Un référentiel **interne verrouillé ou utilisé est publié une fois pour
toutes**. À son premier export, le document est conservé dans
`data/referentiels/<id>/_publication/referentiel.json` ; les exports suivants
le resservent à l'identique (seuls l'état et les métadonnées d'export sont mis
à jour), même si les atomes ont changé depuis (cas d'un nouveau référentiel en
cours sur le même niveau). La vérification ne fige rien. Une publication
figée produite par un exporteur corrigé depuis (liste `EXPORTEURS_PERIMES`,
aujourd'hui la v0.51.1) est régénérée au prochain export. Un référentiel
externe est toujours exporté à partir de son état du moment.

## Versions

- `format_version` = `majeure.mineure`. Ajout d'un champ **facultatif** :
  version mineure (1.1, 1.2…) ; changement incompatible : version majeure
  (2.0).
- Un lecteur refuse une version majeure qu'il ne connaît pas et ignore les
  champs facultatifs qu'il ne connaît pas d'une version mineure plus récente.
  Le schéma v1 est strict (champs inconnus refusés) : il sera mis à jour à
  chaque version mineure.

## Validation

`services.format_referentiel.valider(doc)` renvoie la liste des erreurs (vide
= valide) :

1. conformité au schéma `schemas/referentiel-1.json` (validateur interne,
   sans dépendance ; les tests vérifient aussi avec la bibliothèque
   `jsonschema`) ;
2. cohérence : version majeure, codes uniques (thèmes, séquences, parties,
   objectifs, `ref` des documents), thème de chaque séquence connu, séquences
   présentes dans le découpage, types de documents déclarés, empreintes
   exactes.

## Dans l'appli

- Conception › Niveau › Référentiel : sous le nom du référentiel choisi,
  **Exporter (JSON)** (téléchargement) et **Vérifier** (format valide,
  nombre de séquences, parties et documents, documents sans fichier,
  empreinte, publication figée).
- Routes (profil atelier ou complet) :
  `GET /api/publication/referentiels/<id>.json`,
  `GET /api/publication/referentiels/<id>/verification`.
