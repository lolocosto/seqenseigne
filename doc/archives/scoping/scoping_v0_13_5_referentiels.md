# Scoping v0.13.5 — Référentiels millésimés en service

> **Version finale** après itérations de cadrage du 2026-05-07.
> Cadre la mise en service des tables `referentiel_*` (introduites en
> v0.6.x, schéma déjà en place mais utilisation périphérique aujourd'hui).

## 1. État des lieux

### 1.1 Schéma déjà en place

Quatre tables sont définies dans `persistence/schema.sql` :

- `referentiel_niveaux` (id, niveau, version, date_debut, date_fin,
  description, etat) avec `UNIQUE(niveau, version)` et CHECK constraint
  `etat IN ('en_cours', 'valide', 'verrouille')`.
- `referentiel_themes` (referentiel_id, code, nom, couleur).
- `referentiel_sequences` (referentiel_id, code, numero, nom,
  theme_code).
- `referentiel_objectifs` (referentiel_id, seq_code, code, nom,
  fin_cycle, critere_f/a/e).

`progressions.referentiel_id` a une FK `ON DELETE RESTRICT`.

### 1.2 Évolutions de schéma à apporter en v0.13.5.1

#### 1.2.1 Recréation de `referentiel_niveaux` avec CHECK étendu

Le CHECK actuel autorise 3 états. Il faut **5 états** :

```
en_cours | valide | fige | verrouille | annule
```

Recréation de table SQLite (CHECK ne se modifie pas par ALTER). Les
10 référentiels existants (tous `verrouille`) restent valides.

#### 1.2.2 Nouvelle table `referentiel_parties`

Les parties de séquence servent de support aux créneaux dans les
progressions.

```sql
CREATE TABLE referentiel_parties (
    referentiel_id   TEXT NOT NULL,
    seq_code         TEXT NOT NULL,
    numero           INTEGER NOT NULL,
    nb_seances_R_AE  REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (referentiel_id, seq_code, numero),
    FOREIGN KEY (referentiel_id, seq_code)
        REFERENCES referentiel_sequences (referentiel_id, code)
        ON DELETE CASCADE
);
```

#### 1.2.3 Enrichissement `referentiel_objectifs`

```sql
ALTER TABLE referentiel_objectifs
    ADD COLUMN partie_numero INTEGER NOT NULL DEFAULT 1;
ALTER TABLE referentiel_objectifs
    ADD COLUMN nb_seances     REAL    NOT NULL DEFAULT 0;
```

#### 1.2.4 Nouvelle table `referentiel_obj_exos`

Liste des exos rattachés aux objectifs (pour le suivi). Liste seule,
contenu figé par PDF en v0.13.5.3.

```sql
CREATE TABLE referentiel_obj_exos (
    referentiel_id  TEXT NOT NULL,
    seq_code        TEXT NOT NULL,
    obj_code        TEXT NOT NULL,
    serie           TEXT NOT NULL,        -- 'F', 'A', 'E'
    num             INTEGER NOT NULL,
    ordre           INTEGER NOT NULL,
    origin_niveau   TEXT,
    origin_seq      TEXT,
    PRIMARY KEY (referentiel_id, seq_code, obj_code, serie, num),
    FOREIGN KEY (referentiel_id, seq_code, obj_code)
        REFERENCES referentiel_objectifs (referentiel_id, seq_code, code)
        ON DELETE CASCADE
);
```

### 1.3 Données présentes dans la base de Laurent

10 référentiels, tous **verrouillés**, avec `date_fin` posées par la
v0.13.4.1 sauf le plus récent par niveau (N10_v2024, N11_v2025,
N12_v2024 restent NULL). 10 progressions historiques rattachées.

**Décision** : les référentiels historiques sont laissés tels quels.
Pas de remplissage rétroactif des nouvelles tables. Un script ad hoc
d'analyse des livrets PDF + progressions pourra venir plus tard si
nécessaire.

### 1.4 Mécanismes déjà branchés (rappel)

- `routes/classes.py:api_classes_sequences` : charge depuis le
  référentiel via `build_sequences_from_referentiel`.
- `services/latex_rendu_atome.py` : résout les macros LaTeX avec tri
  déterministe (corrigé en v0.13.4.1).
- `routes/suivi.py:_verrouiller_referentiel_de_classe` : verrouillage
  auto à la 1re éval.
- `services/referentiels.py` : `lister_par_niveau`, `recommande` (à
  durcir en v0.13.5.4).

## 2. Architecture cible

### 2.1 Principe (Vision A étendue)

Les référentiels sont des **snapshots historiques figés**. Les tables
actives restent maîtresses pour la production de docs et le travail
dans les ateliers d'atomes.

**Différence clé avec un snapshot pur** : un référentiel a deux phases :

- **Phase coquille** (`en_cours` / `valide`) : seul `referentiel_niveaux`
  est peuplé. Sert de tableau de bord ("Où j'en suis dans mon
  référentiel N11 ?") et de marqueur d'intention.
- **Phase figée** (`fige` / `verrouille`) : toutes les tables
  `referentiel_*` sont peuplées + PDF stockés. Le référentiel est
  autonome de la BDD active.

### 2.2 Modèle de données

| Domaine | Source de vérité | Notes |
|---------|------------------|-------|
| Production de docs | Tables actives | Inchangé |
| Suivi des cases d'exos | `referentiel_obj_exos` | Peuplé au figeage |
| Affichage séquences classe | Référentiel rattaché à sa progression | Déjà en place |
| Macros LaTeX | Tables actives (cible post-v0.13.5) | Aujourd'hui : `referentiel_*` avec tri déterministe (v0.13.4.1) |
| PDF figés | `data/referentiels/<ref_id>/...` | Créés au figeage (v0.13.5.3) |

## 3. Cycle de vie d'un référentiel — 5 états

```
   Création
   (saisie : niveau seul,
    nom auto)               tous atomes liés         Action explicite
        │                   du niveau valides         "Figer"
        ▼                          │                       │
   ┌──────────┐                    ▼                       ▼
   │ en_cours │ ───────────▶ ┌────────┐ ──────────▶ ┌────────┐
   │          │              │ valide │             │  fige  │
   │ COQUILLE │ ◀─────────── │        │             │        │
   │          │  ≥1 atome    └────────┘             └────────┘
   └──────────┘  repasse                                 │
        │        en_cours                                │ utilisation
        │                                                │ pour création
        │ suppression                                    │ de progression
        │ directe                                        ▼
        │                                          ┌────────────┐
        │                                          │ verrouille │
        ▼                                          └────────────┘
       (BDD)                                       (1re éval saisie)


   Hors flow :

   - `annule` : référentiel `en_cours` ou `valide` automatiquement
     écarté lors d'un figeage qui suffixe (cf. § 3.5).
     Coquille préservée pour traçabilité.

   - `date_fin` posée auto à la création d'une progression sur un
     niveau, sur tous les fige/verrouille du même niveau dont
     date_fin = NULL (cf. § 3.7).
```

### 3.1 Création (état initial `en_cours`)

**Saisie utilisateur** : niveau seul (ex. N11), description optionnelle.

**Nom auto** : `<année>_<niveau><suffixe>` où :
- `<année>` = année civile de début d'année scolaire (2025 pour
  l'année 2025-2026, même si le référentiel est créé en avril 2026).
  Calcul : si mois courant ≥ août (8), `année = annee_courante`,
  sinon `année = annee_courante - 1`.
- `<niveau>` = code niveau (N10, N11, N12, …).
- `<suffixe>` = lettre alphabétique. Première disponible dans l'ordre :
  vide, `b`, `c`, `d`, …, `z`. **Tous états confondus** (y compris
  `annule` et `verrouille`).

Exemples : `2025_N11`, `2025_N11b`, `2025_N11c`.

**Contenu créé** : **uniquement une ligne dans `referentiel_niveaux`**.
Aucune autre table n'est peuplée. État `en_cours`.

### 3.2 Phase coquille — sert de tableau de bord

L'atelier Référentiel (portée Niveau, cf. § 4) affiche en temps réel
l'état des atomes du niveau, en arbre :
**séquence → partie → objectif → atomes** (notion, méthode, exo, fiche).

Permet à l'utilisateur de visualiser ce qui manque avant figeage.

### 3.3 Transition automatique `en_cours → valide` (v0.13.5.2)

Déclenchée à chaque changement d'état d'un atome. Si **tous** les
atomes du niveau ont `etat_code='valide'`, le référentiel passe à
`valide`.

**Périmètre "atomes du niveau"** : tous les atomes (notion, méthode,
exo, fiche) présents dans les tables actives qui ont ce niveau. Pas
une sélection figée — c'est l'ensemble du niveau au moment du calcul.

### 3.4 Transition automatique `valide → en_cours` (v0.13.5.2)

Symétrique : si un atome lié au niveau repasse à `en_cours`, le
référentiel `valide` redevient `en_cours`.

`fige` et `verrouille` ne sont **pas affectés**.

### 3.5 Action explicite `valide → fige`

**Déclenchée par bouton** "Figer" dans l'atelier Référentiel.
Disponible uniquement si l'état est `valide`.

**Règle de confirmation** : confirmation demandée si et seulement si
il existe au moins un autre référentiel `<même_année>_<même_niveau><Y>`
avec :
- `<Y>` antérieur dans l'ordre alphabétique au suffixe en cours,
- ET état `en_cours` ou `valide`.

**Exemples** :

| Existant pour 2025_N11* | On figerait | Comportement |
|--------------------------|-------------|--------------|
| (rien) | `2025_N11` | Pas de confirmation |
| `2025_N11` (en_cours) | `2025_N11b` | Confirmation. OK → `2025_N11` → `annule` |
| `2025_N11` (verrouille) | `2025_N11b` | Pas de confirmation |
| `2025_N11` (annule) | `2025_N11b` | Pas de confirmation |
| `2025_N11` (fige) | `2025_N11b` | Pas de confirmation |
| `2025_N11` (en_cours) + `2025_N11b` (en_cours) | `2025_N11c` | Confirmation. OK → les 2 → `annule` |

**Logique** : on n'écarte que les coquilles inachevées. `fige` cohabite
(il a son PDF, sa vie propre — cas typique : "j'ai figé en septembre,
je refige en avril avec un autre suffixe").

**Effets du figeage** (en v0.13.5.1, périmètre minimal) :
- Vérification de la règle de confirmation.
- Si confirmé : référentiels en_cours/valide antérieurs → `annule`.
- État → `fige`, `date_debut = NOW()`.

**Effets complets** (ajoutés en v0.13.5.3) :
- Remplissage des tables `referentiel_themes`, `_sequences`, `_parties`,
  `_objectifs`, `_obj_exos` depuis les tables actives.
- Compilation des PDF (livrets, plans de travail, fiches de résumé,
  récap éventuels).
- Stockage dans `data/referentiels/<ref_id>/`.

### 3.6 Transition automatique `fige → verrouille`

Déjà en place via `_verrouiller_referentiel_de_classe`. À adapter en
v0.13.5.4 pour partir de `fige` au lieu de `valide`.

### 3.7 Positionnement automatique de `date_fin` (v0.13.5.4)

Quand une progression est créée pour un niveau N en utilisant le
référentiel R_nouveau, le système positionne `date_fin = NOW()` sur
**tous les référentiels du même niveau** qui sont :
- état `fige` ou `verrouille`,
- ET `date_fin IS NULL`,
- ET pas R_nouveau lui-même.

### 3.8 Suppression directe

L'utilisateur peut **supprimer** un référentiel `en_cours` (uniquement)
sans confirmation supplémentaire au-delà du clic sur le bouton.

Pas de suppression possible pour `valide`, `fige`, `verrouille`,
`annule`.

## 4. UI — Atelier Référentiel (portée Niveau)

L'UI est intégrée comme un **atelier d'assemblage** dans la portée
Niveau, au même titre que Récap cours, Récap exos, Plans de travail.

**Pas un sous-onglet Admin** — c'est un acte d'assemblage de niveau
qui mérite sa place dans les ateliers.

### 4.1 Structure

Bouton `atl-btn-referentiel` dans la barre `atl-grp-niveau`.

### 4.2 Contenu de l'atelier

**Sidebar gauche** : liste des référentiels du niveau (tous états),
avec leur nom, état (badge coloré), description, dates. Bouton
"+ Créer" en haut.

**Panneau principal** :
- Si aucun référentiel sélectionné : invite à en créer ou en
  sélectionner.
- Si référentiel `en_cours` ou `valide` sélectionné : tableau de bord
  en arbre **séquence → partie → objectif → atomes** avec état de
  chaque atome.
  - Bouton "Supprimer" (uniquement `en_cours`).
  - Bouton "Figer" (uniquement `valide`, et en v0.13.5.1 = transition
    d'état seulement, sans PDF).
- Si référentiel `fige` / `verrouille` / `annule` : vue lecture seule
  des métadonnées, plus tard accès aux PDF (v0.13.5.3+).

### 4.3 Calcul live de l'état des atomes

L'arbre interroge les tables actives pour le niveau du référentiel
sélectionné, et affiche l'état d'édition (`etat_code`) de chaque
atome.

## 5. Découpage en sous-versions

| Version | Périmètre |
|---------|-----------|
| **v0.13.5.0** ✅ | Doc de scoping (ce document) |
| **v0.13.5.1** | Schéma + création coquille + suppression + UI arbre + bouton "Figer" minimal (transition d'état + annulation des concurrents, SANS compilation PDF) |
| **v0.13.5.2** | Transitions auto `en_cours ↔ valide` + hooks dans les routes de validation d'atomes |
| **v0.13.5.3** | Effets complets de "Figer" : remplissage des tables `referentiel_*` depuis les tables actives + compilation PDF + stockage |
| **v0.13.5.4** | Création progression depuis `fige`/`verrouille` uniquement + `date_fin` auto |
| **v0.13.5.5** (différé v0.15) | Cas 5 : substitution en cours d'année |

## 6. Périmètre exact de v0.13.5.1

### 6.1 Schéma

- Recréation `referentiel_niveaux` avec CHECK étendu (5 états).
- Création `referentiel_parties`.
- ALTER `referentiel_objectifs` (ajout `partie_numero` DEFAULT 1,
  `nb_seances` DEFAULT 0).
- Création `referentiel_obj_exos`.

Les nouvelles tables resteront vides en v0.13.5.1 (peuplement en .3).

### 6.2 Backend Python

- Service `services/referentiels.py` enrichi avec helpers nom auto,
  création coquille, suppression, figer minimal, et un helper
  `arbre_du_niveau` pour l'UI tableau de bord.

### 6.3 Routes Flask

- `POST /api/referentiels/coquille` body `{niveau, description}`
- `DELETE /api/referentiels/<ref_id>`
- `POST /api/referentiels/<ref_id>/figer` body `{force_confirme: bool}`
- `GET /api/referentiels/<ref_id>/arbre`

### 6.4 Frontend

- Bouton `atl-btn-referentiel` dans `atl-grp-niveau`.
- Panel `atl-referentiel` avec sidebar + zone arbre.
- Fichier `static/atelier_referentiel.js` (nouveau).

### 6.5 Tests pytest

Couverture des services, routes, et de la migration de schéma.

### 6.6 Hors périmètre v0.13.5.1

- Calcul automatique de `valide` (→ v0.13.5.2)
- Compilation PDF + stockage (→ v0.13.5.3)
- Filtrage des référentiels disponibles à la création de progression
  (→ v0.13.5.4)
- Migration historique (→ jamais ou ad hoc plus tard)
