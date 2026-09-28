# patch v0.10.5 — Atome Fiche de résumé + atelier dédié

**Date** : 1 mai 2026

**Périmètre** : nouvel atome pédagogique « fiche de résumé » avec son
propre atelier d'édition, intégration dans l'atelier d'assemblage
(drag-and-drop sur l'objectif Connaître), bouton « Initialiser depuis
méthode/notion » avec aplatissement intelligent.

**Score tests** : 1627/1627 passent + 4 skipped historiques. 40 nouveaux
tests v0.10.5.

---

## 1 — Modèle de données

### Tables ajoutées

```sql
CREATE TABLE fiches_resume (
    id           TEXT PRIMARY KEY,
    titre        TEXT NOT NULL DEFAULT '',
    objectif_id  TEXT REFERENCES objectifs_v2(id) ON DELETE SET NULL,
    num_fiche    INTEGER,
    niveau       TEXT NOT NULL DEFAULT '',
    sequence     TEXT NOT NULL DEFAULT '',
    fichier      TEXT NOT NULL DEFAULT '',
    etat_code    TEXT NOT NULL DEFAULT 'en_cours'
);

CREATE TABLE objectif_fiches (
    objectif_id  TEXT REFERENCES objectifs_v2(id) ON DELETE CASCADE,
    fiche_id     TEXT REFERENCES fiches_resume(id) ON DELETE CASCADE,
    ordre        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (objectif_id, fiche_id)
);
```

### Décisions de design

- **Cardinalité 1-1** entre fiche et objectif (Q3-1) : refus à la
  création si l'objectif a déjà une fiche.
- **Numérotation `num_fiche` automatique par séquence** (Q3-3) :
  calculée comme `MAX(num_fiche) + 1` au moment de la création.
- **Sections** : réutilisent `atome_sections` / `atome_section_items`
  avec `entite_type='fiche_resume'`. Aucun nouveau schéma à introduire.
- **État d'édition** : intégré au mécanisme v0.10.4 ; `fiche_resume`
  ajouté au mapping `TABLES_ATOMES` du module `services/etats_edition.py`.
- **Fiche pointe vers `objectifs_v2`** (et non vers la table legacy
  `objectifs`) pour permettre la résolution simple de la partie de
  séquence via `objectifs_v2.partie_id`.

---

## 2 — Atelier Fiche de résumé

Nouveau panel `<div id="atl-fiche">` à côté de Notion / Méthode /
Exercice, dans la portée Séquence.

### Bouton « + Créer »

Crée une nouvelle fiche en mémoire (pas encore enregistrée). L'utilisateur
doit choisir un objectif lié dans le sélecteur ; les objectifs déjà
liés à une autre fiche apparaissent grisés (« déjà lié »).

### Sélecteur d'objectif lié

Liste les objectifs `objectifs_v2` de la (niveau, sequence) courante,
groupés par partie. Format : `P1 · 02 — Calculer une proportion`.

### Zones de texte (Q3-2)

Liste ordonnée de zones, chacune avec :
- **Titre** libre (champ texte, ex : « Définition », « Méthode »,
  « Propriété »…)
- **Contenu LaTeX** (textarea redimensionnable)
- **Bouton « Initialiser depuis... »** : sélecteur déroulant
- **Bouton ×** : supprimer la zone

Boutons globaux :
- **+ Ajouter une zone** : ajoute une zone vide en fin

Au moins une zone est toujours présente (suppression de la dernière =
vidage).

### Bouton « Initialiser depuis méthode/notion » (QE)

Sélecteur déroulant à côté du titre de chaque zone qui propose :
- La **méthode liée** à l'objectif lié de la fiche
- Toutes les **notions liées** à cet objectif

Au choix, l'utilisateur déclenche un appel à `POST /api/fiches-resume/aplatir-atome`
qui retourne un bloc LaTeX prêt à insérer.

**Confirmation (QE.1)** : si la zone a déjà du contenu, demande de
confirmation avant écrasement.

**Aplatissement (QE.2)** : le helper backend assemble le corps + les
sections en un seul bloc, format :

```
{corps de l'atome}

\textbf{titre section 1}

{item 1}

{item 2}

\textbf{titre section 2}

{item 1}
```

### Filtre « hors Exemples » (QF)

Les sections dont le titre (case-insensitive) est dans
`{exemple, exemples, ex, ex.}` sont **exclues** de l'aplatissement. Les
autres sections (Démonstration, Remarque, Conséquence, Propriété…)
sont conservées.

### Toolbar

- **Badge état** : reprend le mécanisme v0.10.4 (en_cours/validé)
- **Bouton Valider/Repasser en cours** : idem
- **Supprimer** : confirme puis DELETE
- **Enregistrer** : POST si nouvelle, PUT si existante

Q2-N respecté : modifier le contenu d'une fiche validée ne fait pas
repasser à `en_cours`.

### Liste latérale

- Affiche les fiches filtrées par (niveau, sequence) de la portée active
- Filtre par état : Tous / En cours / Validé (cohérent avec les autres
  ateliers)
- Identification : `N10/S01/FR01` puis le titre puis l'objectif lié

---

## 3 — Atelier d'assemblage (intégration)

### Sidebar en mode « obj Connaître ouvert » (Q3-4/5/6)

Auparavant vide ; affiche maintenant les fiches dont l'objectif lié
est dans la même partie de séquence. Chaque ligne :

- Badge « F » à gauche
- Titre de la fiche (avec l'objectif lié en title)
- Pastille d'état d'édition (vert si validé)
- Tag « attachée » à droite si la fiche est déjà droppée sur le
  Connaître courant
- **Drag-and-drop** vers la zone Fiches du Connaître
- **Double-clic** → ouvre l'atelier Fiche et charge la fiche

### Zone Fiches dans l'objectif Connaître ouvert

Nouvelle zone intitulée « Fiches de résumé du livret », en plus de
la zone Notions. Reçoit le drop d'une fiche depuis la sidebar.

Les chips de fiches attachées sont affichés dans la zone avec :
- Badge « F » à gauche
- Titre de la fiche
- Bouton × pour détacher

### Pourquoi attacher au Connaître plutôt qu'à l'obj exo ?

Choix Q3-5 : c'est le **drop sur l'obj Connaître** qui détermine
l'inclusion de la fiche dans le livret. Une fiche peut donc exister
(rattachée à son obj exo via `objectif_id` dans la table fiches_resume)
sans être incluse dans le livret tant qu'on ne l'a pas droppée.

Cohérence pédagogique : le Connaître est l'objectif « cours », et c'est
là qu'on rassemble toutes les fiches de la partie pour le livret.

---

## 4 — Endpoints API ajoutés

| Méthode | Endpoint | Rôle |
|---|---|---|
| GET | `/api/fiches-resume?niveau=&sequence=` | Lister fiches |
| GET | `/api/fiches-resume/<id>` | Détail (avec sections) |
| POST | `/api/fiches-resume` | Créer |
| PUT | `/api/fiches-resume/<id>` | Modifier |
| DELETE | `/api/fiches-resume/<id>` | Supprimer |
| POST | `/api/fiches-resume/aplatir-atome` | Aplatir (helper « Initialiser ») |
| GET | `/api/objectifs-v2/<id>/fiches` | Fiches attachées à un objectif |
| POST | `/api/objectifs-v2/<id>/fiches` | Attacher (drop) |
| DELETE | `/api/objectifs-v2/<id>/fiches/<fid>` | Détacher |
| GET | `/api/parties/<id>/fiches-disponibles` | Fiches d'une partie |

Codes d'erreur HTTP :
- `400 champ_manquant` / `type_atome_invalide`
- `404 fiche_introuvable` / `objectif_introuvable`
- `409 objectif_deja_lie` / `fiche_deja_presente`

---

## 5 — Fichiers ajoutés/modifiés

### Backend

```
persistence/schema.sql                — tables fiches_resume + objectif_fiches
services/fiches_resume.py             — service neuf (CRUD, liens, aplatir)
services/etats_edition.py             — fiche_resume dans TABLES_ATOMES,
                                        compter_atomes_par_etat tolérant
routes/fiches_resume.py               — blueprint neuf (10 endpoints)
app.py                                — enregistre bp_fiches_resume
```

### Frontend

```
templates/index.html                  — panel <div id="atl-fiche">,
                                        chargement atelier_fiche.js
static/atelier_fiche.js               — module neuf (~400 lignes)
static/atelier_seqniv_assemblage.js   — sidebar mode Connaître ouvert,
                                        zone fiches, drop, retrait
static/app.js                         — ATL_INITS.fiche → 'atelFicheInit'
static/app.css                        — .atl-fiche-section
```

### Tests

```
tests/test_v0_10_5_fiches_resume.py   — 40 tests (CRUD service + routes
                                        + aplatissement + liens)
```

---

## 6 — Test manuel après déploiement

1. **Créer une fiche** :
   - Aller dans portée Séquence > Fiche de résumé
   - Cliquer + Créer
   - Choisir un objectif lié (par ex. « P1 · 02 — Calculer X »)
   - Saisir un titre
   - Saisir du contenu dans la zone par défaut, ou cliquer
     « Initialiser depuis » → choisir une notion ou la méthode liée
   - Enregistrer

2. **Cardinalité 1-1** :
   - Tenter de créer une seconde fiche pour le même objectif → erreur
     409 « objectif déjà lié »

3. **Aplatissement** :
   - Créer une notion avec une section « Exemples » et une section
     « Remarque »
   - Lier cette notion à un objectif
   - Créer une fiche pour cet objectif
   - Cliquer « Initialiser depuis » → choisir la notion
   - Le contenu doit inclure le corps + la Remarque, **pas** les
     Exemples

4. **Validation** :
   - Cliquer Valider → confirm → badge devient « Validé »
   - Modifier le titre → l'état doit RESTER « Validé » (Q2-N)

5. **Drop sur le Connaître** :
   - Créer une fiche pour l'obj 02 d'une partie
   - Aller dans l'atelier Séquence (assemblage)
   - Ouvrir l'objectif Connaître (01) de la même partie
   - La fiche doit apparaître dans la sidebar à gauche
   - Drag-and-drop vers la zone « Fiches de résumé du livret »
   - La fiche est attachée ; chip apparaît dans la zone, tag
     « attachée » dans la sidebar

6. **Détachement** :
   - Cliquer × sur le chip de la fiche dans la zone Connaître
   - La fiche disparaît de la zone, redevient draggable dans la sidebar

---

## 7 — Pas inclus dans v0.10.5 (différé)

- **Génération PDF du livret** avec inclusion des fiches droppées
  → v0.11.0
- **Plan de travail par partie de séquence** (Q4) → v0.10.6
- **Récap livrets niveau** → v0.11.1

---

## 8 — Pièges connus

- **Pas de FK formelle de cardinalité 1-1** entre `fiches_resume.objectif_id`
  et l'objectif. La contrainte est appliquée côté service (`creer_fiche`
  refuse, `modifier_fiche` refuse aussi). Si on insère directement en
  SQL, on peut violer la contrainte ; à l'usage normal, OK.

- **Pas d'import depuis disque** dans v0.10.5 — la création de fiche
  se fait uniquement via l'atelier. Un futur scanner pourrait découvrir
  des fichiers `Fiche_*.tex` dans `reference/sequences/.../fiches/` et
  les importer comme atomes ; pas dans le scope actuel.

- **Une fiche peut être attachée à plusieurs objectifs Connaître**
  (table `objectif_fiches` permet plusieurs liens). En pratique on
  s'attend à 1 fiche → 1 obj Connaître. Si tu attaches la même fiche
  à deux Connaître (par exemple parce que tu as fait une fausse
  manipulation), il faudra détacher manuellement l'extra.

- **Les sections de fiche utilisent un seul item par section**
  (simplification UI : titre + textarea unique). Le schéma supporte
  N items par section (héritage du modèle notion/méthode), mais
  l'atelier expose seulement le premier item. Les sections
  importées avec plusieurs items ne se verront que par leur premier
  item dans cet atelier.
