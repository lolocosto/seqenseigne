# patch v0.10.4 — N09 dans les sélecteurs + état d'édition des atomes

**Date** : 1 mai 2026

**Périmètre** : ajout de N09 (6ème) dans tous les sélecteurs collège,
introduction d'un état d'édition (`en_cours` / `valide`) pour les
atomes pédagogiques (notions, méthodes, exercices), badges visuels
dans les ateliers et dans la sidebar de l'atelier d'assemblage,
filtre par état dans la liste latérale de chaque atelier.

**Score tests** : 1587/1587 passent + 4 skipped historiques. 32
nouveaux tests v0.10.4.

**Sujets restant pour les livraisons à venir** : atome fiche de
résumé (v0.10.5), plan de travail par partie (v0.10.6), génération
PDF du livret de séquence en mode tolérant avec filigrane ÉPREUVE
(v0.11.0), livret de plan de travail + récap livrets niveau (v0.11.1).

---

## 1 — N09 dans les sélecteurs

N09 (6ème, cycle 3) est désormais proposé dans 5 sélecteurs HTML :

- `admin-niveau` (Admin > Import référence > « Scanner le dossier »)
- `admin-importsuivi-sdb-niveau` (Admin > Import suivi > SequencesDB)
- `admin-importsuivi-hist-niveau` (Admin > Import suivi > historique)
- `prog-sel-niveau` (Suivi > Progression annuelle)
- `rdl-filtre-niveau` (Rendu par lot > filtre niveau)

`ATL_NIVEAUX_OPTIONS` contenait déjà N09 — pas de modif côté JS.

Pour pouvoir importer effectivement les exos N09 servant de
révisions en N10, il faut un dossier `reference/sequences/N09/`
au même format que N10/N11/N12 (fichiers `.tex` standardisés et
fichier `N09_sequences.yaml`). Ce point n'est pas couvert par
v0.10.4 — c'est une question de production de contenu, pas d'appli.

### Limites volontaires

Le sélecteur reste codé en dur (4 niveaux collège). L'extensibilité
multi-cycles (lycée N13-GT/N13-ASSP, primaire pour PE) — qui
demanderait une lecture dynamique de la base des niveaux connus —
est différée à un chantier dédié, prérequis d'un futur CRUD du
découpage de cycle.

---

## 2 — État d'édition des atomes

### Modèle de données

Table `etats_edition` :

```sql
CREATE TABLE etats_edition (
    code      TEXT PRIMARY KEY,
    nom       TEXT NOT NULL,
    ordre     INTEGER NOT NULL DEFAULT 0,
    est_final INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO etats_edition VALUES
    ('en_cours', 'En cours', 10, 0),
    ('valide',   'Validé',   20, 1);
```

Liste extensible — pour ajouter `archive`, `obsolete`, `a_revoir`
plus tard, `INSERT OR IGNORE` suffit, aucun changement de schéma.

Colonne `etat_code` ajoutée aux 3 tables atomes :

- `notions.etat_code TEXT NOT NULL DEFAULT 'en_cours'`
- `methodes.etat_code TEXT NOT NULL DEFAULT 'en_cours'`
- `exercices.etat_code TEXT NOT NULL DEFAULT 'en_cours'`

Migration automatique au démarrage via `_migrer_schema_post_ddl()`,
détecte la présence de la colonne avec `PRAGMA table_info` et
ajoute si absente. Les atomes existants en BDD passent tous à
`en_cours` (sémantiquement neutre — aucun atome existant ne sera
considéré comme validé).

### Préservation à travers ecrire_*

Point crucial : `ecrire_notions` et `ecrire_methodes` font un
`DELETE` complet suivi d'un `INSERT` pour chaque sauvegarde
unitaire (PUT depuis un atelier). Sans précaution, l'état serait
remis à `en_cours` à chaque sauvegarde.

Pattern adopté : avant le DELETE, lire les `etat_code` existants
dans un dict `etats_preexistants`. Au moment de l'INSERT pour
chaque atome, prendre dans l'ordre :

1. `payload.etat_code` si fourni explicitement par le client
2. `etats_preexistants.get(id)` si l'atome existait déjà
3. `'en_cours'` par défaut

Pour `ecrire_exercices` (modèle diff-based UPDATE/INSERT), la
préservation est gratuite : les UPDATE n'incluent pas `etat_code`,
donc la colonne reste intacte. Les nouveaux INSERT prennent
`'en_cours'` par défaut.

### Q2-N : pas de retour automatique à `en_cours` après modification

Décision explicite (Q2-N de la spec) : **modifier le contenu d'un
atome validé ne le fait pas repasser en `en_cours`**. L'enseignant
peut éditer un atome validé tout en gardant son statut validé. À
sa charge la cohérence entre statut et contenu réel. Un test
dédié (`test_put_notion_preserve_etat`) garantit cette propriété.

### API

| Méthode | Endpoint | Rôle |
|---|---|---|
| GET | `/api/etats-edition` | Liste des états possibles |
| GET | `/api/atomes/<type>/<id>/etat` | État courant d'un atome |
| PATCH | `/api/atomes/<type>/<id>/etat` | Change l'état (body `{"etat_code": "..."}`) |
| GET | `/api/etats-edition/recap` | Comptage par (type, état) — diagnostic |

Avec `<type>` ∈ {`notion`, `methode`, `exercice`}.

Codes d'erreur HTTP :

- `400 type_atome_invalide` si type ∉ TABLES_ATOMES
- `404 atome_introuvable` si l'atome n'existe pas
- `404 etat_inconnu` si le code d'état n'existe pas
- `400 champ_manquant` si `etat_code` absent du body PATCH

### UI dans les ateliers (notion / méthode / exercice)

Chaque toolbar d'atelier montre :

- **Badge état** à droite du titre (`En cours` en gris, `Validé`
  en vert), masqué tant qu'aucun atome n'est sélectionné
- **Bouton « Valider »** ou **« Repasser en cours »** selon l'état
  courant. Validation déclenche un `confirm()` simple (Q2-M).
  Le repassage en cours est silencieux (opération non destructive).

Liste latérale :

- **Filtre par état** au-dessus de la liste : `Tous` / `En cours`
  / `Validé`. Mémorisé dans `window.ATL_FILTRE_ETAT[type]`.
- **Badge `Validé`** à droite de chaque ligne validée. Pas de
  badge pour les `en_cours` (état par défaut, on évite la
  pollution visuelle).

Pas de validation en masse (Q2-5).

### UI dans la sidebar de l'atelier d'assemblage

Petite **pastille** ronde (8×8 px) à droite du libellé de chaque
atome dans la sidebar :

- Verte (#4a9747) si l'atome est validé
- Grise atténuée (40% opacité) si en cours

Discret mais visible — permet de repérer en un coup d'œil les
atomes encore en chantier sans surcharger l'UI.

### Q2-P : préparation pour le mode ÉPREUVE

Backend prêt pour la génération PDF tolérante (v0.11.0) : la
fonction `compter_atomes_par_etat()` permet de savoir combien
d'atomes d'une séquence sont validés. La logique « ÉPREUVE »
sera implémentée dans la livraison génération PDF.

---

## Fichiers modifiés

### Backend
```
persistence/schema.sql                    — table etats_edition + seed
persistence/sqlite_store.py               — _migrer_schema_post_ddl ;
                                            lire_/ecrire_notions/methodes
                                            préservent etat_code
services/etats_edition.py                 — service neuf
services/v2_edition.py                    — etat_code dans
                                            lister_methodes/notions/exos_dispos
routes/etats_edition.py                   — blueprint neuf
app.py                                    — enregistre bp_etats_edition
```

### Frontend
```
templates/index.html                      — N09 dans 5 sélecteurs ;
                                            badge + bouton + filtre dans
                                            les 3 toolbars d'atelier
static/atelier_etat_edition.js            — module neuf (rafraichir,
                                            basculer, filtrer)
static/app.js                             — atelXxxAfficherEditeur
                                            rafraîchissent le badge ;
                                            atelRender*Liste filtrent
                                            par état
static/atelier_seqniv_assemblage.js       — _renduItem accepte etatCode ;
                                            5 call sites passent etat_code
static/app.css                            — .atome-etat-badge,
                                            .atl-list-item-etat,
                                            .exo-etat (filtre boutons),
                                            .asm-item-etat-badge (sidebar)
```

### Tests
```
tests/test_v0_10_4_etats_edition.py       — 32 tests (service + routes
                                            + intégration via /api/notions)
tests/test_R4e3_edition_objectif.py       — etat_code dans le schéma méthodes
tests/test_R4e4b_edition_exos.py          — etat_code dans le schéma exos
                                            + invariant de champs renvoyés
```

---

## Test manuel après déploiement

1. **N09 dans les sélecteurs** : Admin > Import référence : N09
   doit apparaître dans le sélecteur niveau. Idem dans Suivi >
   Progression annuelle, et dans le filtre Rendu par lot.

2. **Badge état dans les ateliers** : ouvrir l'atelier Exercice,
   sélectionner un exo. Le badge `En cours` doit s'afficher dans
   la toolbar, et le bouton `Valider` doit être présent.

3. **Validation** : cliquer `Valider` → confirm() s'affiche →
   confirmer → le badge passe à `Validé` (vert), le bouton
   devient `Repasser en cours`. Recharger la page : l'état est
   persisté.

4. **Q2-N** : sur l'exo validé, modifier le titre puis cliquer
   `Enregistrer`. Le badge doit RESTER `Validé` (pas de retour
   automatique à `en_cours`).

5. **Filtre par état** : cliquer `Validé` dans le filtre au-dessus
   de la liste. Seuls les atomes validés doivent rester visibles.

6. **Sidebar de l'atelier d'assemblage** : ouvrir une séquence
   (par ex. N11/S03). Les méthodes/notions/exos validés montrent
   une pastille verte à droite. Les autres une pastille grise.

7. **API directe** (optionnel) : `curl http://127.0.0.1:5000/api/etats-edition/recap`
   retourne le compte d'atomes par (type, état). Utile pour
   diagnostiquer.

---

## Pas inclus dans v0.10.4 (différé)

- **Atome fiche de résumé** (Q3) → v0.10.5
- **Plan de travail par partie** (Q4) → v0.10.6
- **Génération PDF avec filigrane ÉPREUVE** (Q2-P) → v0.11.0
- **Livret de plan de travail** (Q5) → v0.11.1
- **Récap livrets niveau** (compile les 14 livrets de séquence
  d'un niveau d'un coup) → v0.11.1

L'état d'édition est conçu pour interagir avec ces livraisons
futures :
- v0.10.5 ajoutera `fiches_resume.etat_code` via la même migration
- v0.11.0 utilisera `compter_atomes_par_etat` pour décider du
  filigrane ÉPREUVE
- v0.11.1 idem au niveau niveau entier

---

## Pièges connus

- **Pas de FK formelle entre `<table>.etat_code` et
  `etats_edition.code`** — choix volontaire pour rester souple :
  on peut ajouter/retirer des états sans contrainte. La
  validation est faite côté service (`changer_etat_atome` lève
  `EtatInconnu` si le code n'est pas dans `etats_edition`).

- **`ecrire_notions` reçoit la liste complète** — pattern legacy.
  Si un client n'envoie que partiellement les notions (par ex.
  oubli d'une notion), elles seraient supprimées. C'est le
  contrat actuel ; pas changé en v0.10.4.

- **Tests fixtures avec schéma maison** — deux tests anciens
  (test_R4e3, test_R4e4b) ont leur propre `_SCHEMA_TEST` in-memory
  qui ne synchronise pas avec `schema.sql`. Mes ajouts y ont été
  reportés. Si une nouvelle colonne est ajoutée plus tard à
  `methodes`/`exercices`, ne pas oublier ces deux fichiers.
