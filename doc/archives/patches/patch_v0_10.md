# patch v0.10 — fondations de l'atelier d'assemblage de séquence-niveau

**Date** : 30 avril 2026

**Périmètre** : backend uniquement (services, routes, schéma BDD, tests).
L'UI elle-même viendra dans la livraison v0.10.1.

**Score tests** : 1508/1508 passent (4 skipped historiques inchangés).

---

## Objectif

Préparer toutes les fondations nécessaires au nouvel atelier d'assemblage
d'une séquence-dans-niveau, dans lequel l'enseignant organise par drag &
drop des parties, des objectifs, des méthodes et des exercices. La
livraison v0.10 ajoute uniquement les briques techniques (BDD + API +
tests) ; l'UI sera livrée en v0.10.1.

L'éditeur v2 actuel (`ateliers_seqniv_v2_edit.js`) est conservé tel quel
en v0.10. Il sera supprimé après que le nouvel atelier aura repris toutes
ses fonctionnalités.

---

## Schéma BDD — 2 nouvelles tables

`persistence/schema.sql` :

### `partie_exos_revision_approche`

Exos de révision (R) ou d'approche (EA) attachés directement à une
**partie**, indépendamment de tout objectif.

```sql
CREATE TABLE partie_exos_revision_approche (
    partie_id      TEXT NOT NULL REFERENCES sequence_parties(id) ON DELETE CASCADE,
    type           TEXT NOT NULL,        -- 'R' ou 'EA'
    exercice_id    TEXT NOT NULL REFERENCES exercices(id) ON DELETE RESTRICT,
    ordre          INTEGER NOT NULL DEFAULT 0,
    origin_niveau  TEXT,
    origin_seq     TEXT,
    origin_serie   TEXT,
    origin_num     INTEGER,
    PRIMARY KEY (partie_id, type, exercice_id),
    UNIQUE (partie_id, type, ordre)
);
```

Pourquoi pas sur `objectif_exos` ? Parce que l'enseignant doit pouvoir
choisir des exos R/EA en début d'une partie sans avoir activé l'objectif
« Connaître les notions et les méthodes » de cette partie. Les deux usages
coexistent : `objectif_exos.serie='R'` reste valide pour les exos R/EA
historiquement attachés à un objectif (0 ligne en base courante, donc pas
de migration de données nécessaire).

### `ui_etat_atelier_sequence`

Persistance de l'état UI de l'atelier d'assemblage : quel objectif est
ouvert en édition pour chaque séquence-par-niveau.

```sql
CREATE TABLE ui_etat_atelier_sequence (
    sequence_par_niveau_id TEXT PRIMARY KEY
                           REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    objectif_ouvert_id     TEXT REFERENCES objectifs_v2(id) ON DELETE SET NULL,
    derniere_maj           TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Permet à l'utilisateur de quitter l'atelier puis y revenir et retrouver
l'objectif qu'il était en train d'éditer. Un seul objectif ouvert à la
fois par séquence (Q8 du cahier des charges).

---

## Services — `services/v2_edition.py`

### Helper

- `code_objectif_connaitre(numero_partie)` → `'01'`, `'11'`, `'21'`, ...
  Convention canonique : 1er chiffre = (numéro de partie - 1).

### Réordonnancement

- `reordonner_parties(conn, sn_id, partie_ids_dans_ordre)` — réécrit
  atomiquement les `numero` 1..N des parties (passage par numéros négatifs
  pour éviter collision UNIQUE). Ne touche PAS aux codes des objectifs ;
  c'est au frontend de chaîner avec `reordonner_objectifs_dans_partie`
  pour respecter la convention `0X / 1X / 2X`.

- `reordonner_objectifs_dans_partie(conn, partie_id, objectif_ids_dans_ordre)`
  — réécrit les codes des objectifs selon leur position. L'objectif
  « Connaître » (s'il existe) doit rester en position 0 ; les autres
  prennent les codes `X2, X3, X4...` où X = numero_partie - 1. Atomique
  via codes temporaires `~tmp1`, `~tmp2`...

### Activation de l'objectif Connaître

- `activer_objectif_connaitre(conn, partie_id, nom='', critere_F='', critere_A='', critere_E='')`
  — crée l'objectif `0X` avec le nom et les critères pré-remplis fournis.
  409 si l'objectif existe déjà dans la partie.

### Exos R/EA au niveau partie

- `lister_exos_revision_approche(conn, partie_id)` → `{"R": [...], "EA": [...]}`
- `ajouter_exo_revision_approche(conn, partie_id, type_, exercice_id, origin_*=None)`
- `retirer_exo_revision_approche(conn, partie_id, type_, exercice_id)` —
  recompacte les ordres restants.
- `reordonner_exos_revision_approche(conn, partie_id, type_, exercice_ids)`

### État UI persistant

- `lire_etat_ui_atelier_sequence(conn, sn_id)` → état neutre si pas de
  ligne (pas d'erreur).
- `ecrire_etat_ui_atelier_sequence(conn, sn_id, objectif_ouvert_id)` —
  UPSERT. Vérifie que l'objectif appartient bien à la séquence.

### Nouvelles exceptions

```
TypeRevisionApprocheInvalide        → 400
ExoRevisionApprocheDejaPresent       → 409
ExoRevisionApprocheIntrouvable       → 404
ObjectifConnaitreDejaPresent         → 409
```

---

## Service `services/v2_lecture.py` — réponse enrichie

Ajouts sans casser l'existant :

- Chaque partie a désormais aussi `exos_revision_approche = {"R": [...], "EA": [...]}`.
- Le top-level reçoit `etat_ui = {"objectif_ouvert_id", "derniere_maj"}`.

Robustesse : si la table `partie_exos_revision_approche` ou
`ui_etat_atelier_sequence` n'existe pas (vieux schéma), ces champs
remontent vides — pas d'erreur.

**Test impacté** : `test_lecture_structure_racine` mis à jour pour
attendre la nouvelle clé `etat_ui` dans la réponse.

---

## Routes — `routes/v2_edition.py`

9 nouveaux endpoints :

| Méthode | URL | Rôle |
|---|---|---|
| PATCH | `/api/v2/sequences-par-niveau/<sn_id>/parties/ordre` | Réordonner les parties |
| PATCH | `/api/v2/parties/<partie_id>/objectifs/ordre` | Réordonner les objectifs DANS une partie |
| POST | `/api/v2/parties/<partie_id>/objectif-connaitre` | Activer l'objectif Connaître |
| GET | `/api/v2/parties/<partie_id>/exos-revision-approche` | Lister R/EA d'une partie |
| POST | `/api/v2/parties/<partie_id>/exos-revision-approche` | Ajouter un exo R ou EA |
| DELETE | `/api/v2/parties/<partie_id>/exos-revision-approche/<type>/<exercice_id>` | Retirer un exo |
| PATCH | `/api/v2/parties/<partie_id>/exos-revision-approche/<type>/ordre` | Réordonner les exos R ou EA |
| GET | `/api/v2/sequences-par-niveau/<sn_id>/etat-ui` | Lire l'objectif ouvert |
| PUT | `/api/v2/sequences-par-niveau/<sn_id>/etat-ui` | Écrire l'objectif ouvert |

Tous les codes d'erreur métier remontent en 400/404/409 selon le mapping
`_CODE_HTTP` (pattern existant).

---

## Tests — nouveau fichier `tests/test_v0_10_assemblage.py`

74 tests organisés en 8 classes :
1. `TestCodeObjectifConnaitre` (7) — helper pur.
2. `TestReordonnerParties` (9) — drag & drop des parties.
3. `TestReordonnerObjectifsDansPartie` (7) — drag & drop dans une partie.
4. `TestActiverObjectifConnaitre` (5) — création de l'obj 0X.
5. `TestExosRevisionApproche` (14) — exos R/EA niveau partie.
6. `TestEtatUiAtelierSequence` (9) — persistance objectif ouvert.
7. `TestV2LectureEnrichie` (4) — intégration avec v2_lecture.
8. `TestRoutes` (16) — tests d'intégration via client Flask.

Conventions reprises de `test_R4e2_edition.py` : fixture `conn` SQLite
mémoire avec schéma minimal, fixture `base_peuplee` avec une mini-séquence
N11/S03 + parties + objectifs + exercices.

---

## Critères pré-remplis pour l'objectif Connaître

Pas codés en dur côté backend (ce serait fragile et difficile à maintenir).
La fonction `activer_objectif_connaitre()` accepte les critères F/A/E en
paramètres ; c'est l'**UI** (livraison v0.10.1) qui les fournira au moment
de l'appel API, idéalement depuis Préférences (configurable une fois pour
toutes par l'enseignant).

Valeurs cibles convenues avec Laurent (CdC v0.10) :

- F (Fondamental, à consolider) : *A noté la trace écrite en classe.*
- A (Avancé, satisfaisant) : *A complété les fiches de résumé.*
- E (Exploration, très bon) : *Sait résumer le cours à l'oral.*

---

## Pas inclus dans v0.10 (planifié pour v0.10.1)

- Le panneau HTML `#atl-livret-assemblage`.
- Le fichier `static/atelier_seqniv_assemblage.js`.
- Le drag & drop méthodes/exos/parties/objectifs.
- La bascule barre de gauche méthodes ↔ exercices.
- Le rendu des objectifs ouvert/fermé.
- La section Préférences pour les critères pré-remplis par défaut.
- Le toggle « Atelier d'assemblage / Édition avancée » dans la toolbar.

---

## Pour reprendre en v0.10.1

Tout est en place côté backend. Plan UI :

1. Renommer le panneau `#atl-livret` actuel en `#atl-livret-edit-v2` ;
   ajouter un panneau frère `#atl-livret-assemblage`. Sous-onglet de bascule
   dans la toolbar de l'atelier Séquence (atelier qui sait basculer entre
   « Assemblage » par défaut et « Édition avancée »).
2. `static/atelier_seqniv_assemblage.js` — fichier neuf, chargé par
   `index.html`. Pattern d'auto-branchement sur DOMContentLoaded comme les
   autres ateliers. Hook `window.seqnivAssemblageRafraichir()` appelé
   depuis `app.js > initLivret()` quand le panneau est actif.
3. Rendu basé sur `GET /api/v2/sequences-par-niveau/<niveau>/<seq>` (déjà
   enrichi en v0.10 avec exos_revision_approche et etat_ui).
4. Drag & drop natif HTML5 (`draggable=true`, `dragstart/dragover/drop`).
   Les autres ateliers de l'appli n'utilisent pas de lib externe — on
   reste cohérent.
5. Préférences > Atelier d'assemblage : 3 textareas pour les critères
   pré-remplis F/A/E par défaut, persistés dans `data/configuration.json`.
