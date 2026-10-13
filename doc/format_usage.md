# Format `seqenseigne.usage` v1 — retour d'usage

Fichier JSON produit par l'appli en ligne (profil classe, tableau de bord ›
Retour d'usage) et importé dans l'appli locale (profil atelier, tableau de
bord › Publication › « Importer un retour d'usage »). Il indique quels
référentiels publiés sont utilisés en classe, pour que l'atelier verrouille
ce qui a déjà servi. **Aucune donnée d'élève, ni classe, ni établissement.**

```json
{
  "format": "seqenseigne.usage",
  "format_version": "1.0",
  "echange": {
    "type": "usage", "numero": 4,
    "emetteur": { "id": "inst_48be…", "nom": "Appli en ligne", "role": "classe" },
    "destinataire": "inst_5eb6…",
    "accuse": 7
  },
  "cree_le": "2026-10-13T10:30:00+02:00",
  "nom": "usage_0004_2026-10-13_1030.json",
  "referentiels": [
    { "id": "X2026_N11", "nom": "4e — 2026-2027 — Principal",
      "empreinte": "sha256:…",
      "utilise": true, "utilise_depuis": "2026-09-07",
      "sequences": [ { "code": "S01", "debut": "2026-09-07" },
                     { "code": "S02", "debut": "2026-11-02" } ],
      "parties_mer": [ "M01|2" ] }
  ]
}
```

- `echange` : en-tête du protocole d'échange (voir `doc/format_paquet.md`) ;
  `accuse` = dernier paquet reçu de l'atelier : il acquitte les paquets
  jusqu'à ce numéro (retirés de l'archive de l'atelier).
- `referentiels` : chaque référentiel importé (`origine = publication`) :
  - `empreinte` : empreinte de la publication en usage dans l'appli en ligne
    (sert aux états de synchronisation de l'atelier) ;
  - `utilise` : une progression principale ou de MER s'appuie dessus ;
    `utilise_depuis` : date du premier créneau daté ;
  - `sequences` : pour chaque séquence planifiée, la date de début de son
    premier créneau ; l'atelier la tient pour **commencée** quand cette date
    est passée (à sa propre date du jour) ;
  - `parties_mer` : parties de MER posées (`séquence|numéro`) ; leur séquence
    est commencée.

## Import dans l'atelier

- Règle stricte du protocole : seul le numéro attendu est accepté (déjà reçu
  → refus ; trou → refus avec les numéros à redemander, « Renvoyer » dans
  l'appli en ligne).
- Usage **réuni** aux retours précédents : un verrou n'est jamais perdu
  (séquence commencée, référentiel utilisé), même si le créneau a disparu
  côté classe ; la date de début la plus ancienne est gardée.
- Un interne verrouillé utilisé passe « utilisé » ; un référentiel inconnu
  de l'atelier est signalé.

## États de synchronisation (atelier)

| État | Sens |
|---|---|
| jamais publié | aucun paquet ne l'a contenu |
| publication en attente | la dernière version publiée n'est pas encore acquittée |
| synchronisé | l'appli en ligne a la dernière version publiée, rien n'a changé |
| modifié depuis la publication | l'appli en ligne a la dernière version, l'atelier a changé : à republier |
| en retard | le paquet de la dernière version est arrivé, mais l'appli en ligne utilise une version plus ancienne (import refusé, par exemple) |
| désynchronisé | l'appli en ligne utilise une version que l'atelier n'a jamais publiée |
