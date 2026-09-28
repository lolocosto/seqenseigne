# Redémarrage v0.13.6.4

**Session du 12 mai 2026 — Catalogue des documents publiables**

---

## Récap version

| Version | État |
|---|---|
| v0.13.6.3.2 | ✅ Cartes dans l'atelier d'assemblage |
| **v0.13.6.4** | 🟡 **À déployer** — Catalogue des documents publiables (déclaration seule, pas de compilation) |
| v0.13.6.5 (à venir) | Mécanisme de compilation + critère de figeage |

---

## Demande initiale

Sortir du scoping documenté de mai 2025 (cf. mémoire de la session
*025_Structure et compilation des documents de référentiel*) : faire
exister dans l'atelier Référentiel un **catalogue des 9 types de
documents publiables**, avec leurs options. **Pas de compilation
cette session** : seulement déclaration / configuration.

Périmètre élargi en cours de session : **2 nouveaux types** ajoutés
au catalogue d'origine (7 → 9) :
- `livret_cartes_recap` : récap annuel des cartes (8/page, enseignant)
- `livret_cartes_planches` : planches élèves (16/page recto + 16/page
  verso, avec `\cleardoublepage` par séquence)

Les macros LaTeX existent déjà dans le paquet, juste à utiliser en
v0.13.6.5+ pour la compilation.

---

## Ce qui a été fait

### Schéma BDD `persistence/schema.sql`

Nouvelle table `referentiel_documents` :

```sql
CREATE TABLE IF NOT EXISTS referentiel_documents (
    id              TEXT PRIMARY KEY,
    referentiel_id  TEXT NOT NULL
                    REFERENCES referentiel_niveaux(id) ON DELETE CASCADE,
    type_document   TEXT NOT NULL,
    options         TEXT NOT NULL DEFAULT '{}',  -- JSON
    ordre           INTEGER NOT NULL DEFAULT 0,
    mtime           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (referentiel_id, type_document),
    CHECK (type_document IN ( ... 9 types ... ))
);
```

Pas de colonnes `compile_*` cette session — elles seront ajoutées en
v0.13.6.5+ pour le mécanisme de figeage. Index sur `referentiel_id`.

### Service `services/referentiel_documents.py` (nouveau, ~250 lignes)

- `TYPES_DOCUMENT` : tuple des 9 codes
- `ORDRE_AFFICHAGE` : ordre stable d'affichage (1..9)
- `ENUMS` : valeurs autorisées pour les radios
- `OPTIONS_PAR_DEFAUT` : dict des défauts pour chaque type
- `lister_documents(conn, ref_id)` : auto-initialise les 9 entrées si vide
- `initialiser_documents_defaut(conn, ref_id)` : idempotent
  (INSERT OR IGNORE)
- `maj_options(conn, doc_id, options)` : PATCH-like, fusion + validation
- `_valider_options(type, options)` : clés autorisées + types Python +
  valeurs énumérées (sinon `DocumentErreur` avec `code` et `details`)

### Routes `routes/referentiel_documents.py` (nouveau)

- `GET  /api/referentiels/<ref_id>/documents` — auto-init si vide
- `PUT  /api/referentiels/<ref_id>/documents/<doc_id>` — body
  `{options: {...}}`, validation côté service
- Vérifie l'appartenance du doc au référentiel (404 sinon)

Blueprint enregistré dans `app.py` :
`bp_referentiel_documents` ajouté à la liste de `register_blueprint`.

### UI — onglets dans `atl-ref-detail`

**Template `templates/index.html`** : ajout d'un bandeau d'onglets
(Tableau de bord / Documents à publier) + 2 panneaux frères :
- `#atl-ref-panneau-dashboard` : reprise du tableau de bord existant
  (arbre séquence → partie → objectif → atomes)
- `#atl-ref-panneau-documents` : rempli dynamiquement par
  `atelRefRendreDocuments()`

**JS `static/atelier_referentiel.js`** : ajout de
- `atelRefChangerOnglet(nom)` : bascule visuelle, lazy-load du panneau
  documents au premier accès
- `atelRefChargerEtRendreDocuments()` : fetch + rendu
- `atelRefRendreDocuments()` + helpers pour chaque type :
  `atelRefDocumentCadreHtml`, `atelRefDocumentOptionsHtml`, `_atlRefCb`,
  `_atlRefRadio`
- `atelRefMajOptionDoc(docId, cle, valeur)` : PUT à chaque onchange,
  réécriture du panneau au retour pour refléter l'état serveur
- Réinitialisation forcée à l'onglet `dashboard` à chaque sélection
  d'un référentiel (pas de persistance d'onglet entre sélections)

**Lecture seule** pour les référentiels figé/verrouille/annule :
bandeau d'alerte + tous les inputs en `disabled`.

---

## Tests

`tests/test_v0_13_6_4_documents_publiables.py` — **26 tests** :
- 2 sur le schéma (table + index)
- 4 sur le catalogue (9 types, défauts bien-formés, énumérés valides,
  ordre unique)
- 3 sur l'initialisation (insertion, idempotence, état actif=False)
- 4 sur lister_documents (auto-init, fusion options, tri, isolation
  par référentiel)
- 6 sur maj_options (activation, partielle, clé inconnue, type
  invalide, énum invalide, document introuvable)
- 1 sur la cascade FK
- 6 sur les routes (GET, GET 404, PUT, PUT invalide, PUT cross-ref,
  PUT body invalide)

**Tous passent**. Suite complète :
- Avant : 2372 passed (baseline du sandbox)
- Après : **2398 passed** (= 2372 + 26 nouveaux)
- 0 régression

---

## Décisions prises

| Question | Décision |
|---|---|
| Pré-déclaration auto à la 1ère ouverture | Oui — 9 entrées créées au 1er GET, idempotent |
| Granularité séquence / éval | Tout ou rien (1 entrée `livret_sequence` pour les 14, 1 entrée `evaluation` pour toutes les évals) |
| Position UI | Onglets dans `atl-ref-detail` (Tableau de bord / Documents à publier) |
| Persistance d'onglet entre sélections | Non — toujours retour à Tableau de bord |
| Format des options | JSON dans une colonne unique `options` |
| Lecture seule sur référentiel figé | Oui, bandeau + inputs disabled |
| Validation côté service | Clés autorisées + types Python + énumérés |

---

## Hors scope (à venir)

- ❌ Compilation des documents (service `compiler_document`, boutons
  Tester, badges de statut)
- ❌ Colonnes `compile_ok` / `compile_date` / `compile_log` /
  `compile_en_cours` dans la table
- ❌ Critère de figeage adapté (« tous les documents `actif=true` en
  état OK »)
- ❌ Sous-atelier QCM (différé)
- ❌ Évolution du paquet LaTeX `core-exos` (4 flags) — prérequis du
  livret de corrigés en compilation

---

## Validation

| Test | Résultat |
|---|---|
| Syntaxe Python (service + route + app) | OK |
| Syntaxe JS (atelier_referentiel) | OK |
| Tests dédiés v0.13.6.4 | 26/26 |
| Suite pytest complète | **2398 passed, 5 skipped, 0 régression** |
| Sanity sur BDD réelle (N12/2025) | 9 documents listés, ordre OK |

---

## Notes pour la prochaine session

### Évolutions de cette UI

- **Aperçu agrégé** : indicateur en bas du panneau « X documents
  actifs sur 9 ». Utile dès qu'on a 9 cadres.
- **Profils de référence** : bouton « Tout cocher » / « Configuration
  d'usage A » / « Configuration d'usage B » pour basculer rapidement.
  À voir si utile.
- **Cohérence avec atelier d'assemblage** : la section
  « Éléments à inclure » de l'atelier d'assemblage séquence-dans-niveau
  est toujours là. Elle pilote la **compilation testable depuis
  l'onglet Rendu PDF de l'atelier d'assemblage** (compilation à la
  volée par séquence). Le panneau Documents du référentiel pilote la
  **compilation du référentiel entier**. Ces deux UIs doivent diverger
  pour l'instant — mais à un moment, on pourrait imaginer que les
  options d'assemblage *individuel* se rabattent sur celles du
  référentiel (cohérence pédagogique). À discuter plus tard.

### v0.13.6.5 — Mécanisme de compilation

Suite logique. Pré-requis avant figeage :
1. Ajouter les colonnes `compile_ok` / `compile_date` / `compile_log` /
   `compile_en_cours` à `referentiel_documents`
2. Service `compiler_document(doc_id)` qui pilote le compilateur web
   2-pass (existe déjà pour les atomes individuels)
3. UI : bouton « Tester » par document + bouton global « Tester tous »
4. État effectif calculé à la lecture (NULL / KO / périmé / OK)
5. Critère de figeage adapté : tous les documents `actif=True` doivent
   être en état effectif `OK`

### Génération de cartes spécifiquement

Pour les 2 nouveaux types `livret_cartes_*`, voir comment les macros
LaTeX du paquet sont appelées :
- Récap (enseignant) : boucle simple sur toutes les cartes du niveau,
  ordre des séquences + saut de page entre séquences
- Planches (élèves) : pour chaque carte, page de 16 rectos + page de
  16 versos + `\cleardoublepage` à chaque nouvelle séquence

### Fichiers livrés

```
appli/persistence/schema.sql                             (modifié, +~36 lignes)
appli/app.py                                             (modifié, +2 lignes)
appli/services/referentiel_documents.py                  (nouveau, ~250 lignes)
appli/routes/referentiel_documents.py                    (nouveau, ~95 lignes)
appli/static/atelier_referentiel.js                      (modifié, +~300 lignes)
appli/templates/index.html                               (modifié, ~+50 lignes)
appli/tests/test_v0_13_6_4_documents_publiables.py       (nouveau, 26 tests)
appli/doc/redemarrage_v0_13_6_4.md                       (ce fichier)
```
