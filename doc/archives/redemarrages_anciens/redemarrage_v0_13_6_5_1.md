# Redémarrage v0.13.6.5.1

**Session du 13 mai 2026 — Compilation des documents publiables (UI + squelette)**

---

## Récap version

| Version | État |
|---|---|
| v0.13.6.4 | ✅ Catalogue des 9 documents publiables (déclaration + options) |
| **v0.13.6.5.1** | 🟡 **À déployer** — Mécanisme de compilation + UI + état effectif |
| v0.13.6.5.2 | À venir : 4 services métier manquants |
| v0.13.6.5.3 | À venir : figeage étendu |

---

## Demande initiale

Après le catalogue v0.13.6.4 (déclaration des documents à publier),
mettre en place le mécanisme qui permet à l'enseignant de **tester la
compilation** de chaque document, et de voir son état (compilé / pas
encore / KO / périmé). Périmé = un atome constituant a été modifié
depuis la compilation.

Compilation potentiellement longue (un livret_sequence = 14 séquences
× 30s = ~7 min). Donc :
- Asynchrone (thread daemon) pour ne pas bloquer Flask
- Polling de statut côté UI pour afficher la progression
- Verrou `compile_en_cours` pour empêcher les compilations concurrentes
- Reset automatique des verrous orphelins au démarrage Flask

---

## Ce qui a été fait

### Schéma BDD `persistence/sqlite_store.py`

Migration idempotente dans `_migrer_schema_post_ddl` :
- `referentiel_documents.compile_ok      INTEGER`
- `referentiel_documents.compile_date    DATETIME`
- `referentiel_documents.compile_log     TEXT`
- `referentiel_documents.compile_en_cours INTEGER NOT NULL DEFAULT 0`
- **Reset auto** : `UPDATE ... SET compile_en_cours = 0 WHERE compile_en_cours = 1`
  exécuté à chaque démarrage Flask. Couvre le cas où l'app a été tuée
  pendant une compilation.

### Service catalogue `services/referentiel_documents.py` (étendu)

`lister_documents()` retourne maintenant aussi :
- les 4 colonnes `compile_*`
- `etat_effectif` (calculé via le nouveau service compilation)
- `referentiel_id` (utile à l'état effectif)

### Service compilation `services/referentiel_documents_compilation.py` (nouveau, ~500 lignes)

- `lister_cibles_document(conn, doc_id, ref_id, type)` : retourne 1 ou
  plusieurs cibles selon le type (livret_sequence → 14 cibles,
  evaluation → N cibles, autres → 1 cible).
- `_generer_tex(conn, type, options, cible, ...)` : aiguille vers le
  bon service métier :
  - `livret_sequence` → `services.livret_sequence`
  - `livret_cours` → `services.livret_recap_cours`
  - `livret_exercices` → `services.livret_recap_exos`
  - `livret_plans` → `services.livret_plans_de_travail`
  - `evaluation` → `services.render_evaluation`
  - Les 4 autres (`livret_fiches`, `livret_corriges`, `livret_cartes_*`)
    lèvent `CompilationErreur(code='type_non_implemente')`
- `compiler_document(store, doc_id, ...)` : compile **synchrone** —
  verrou, boucle sur cibles, écriture en BDD finale. Stockage des PDF
  dans `data/referentiels/<ref_id>/`.
- `compiler_document_async(...)` : lance dans un thread daemon
- `lire_statut(doc_id)` : lit le dict de progression en mémoire
- `etat_effectif_document(conn, doc)` : calcule l'état selon les
  colonnes `compile_*` et le max(mtime) des atomes du niveau.
  Pour cette session : critère **large** (tous les atomes du niveau).
  Affinage atome→documents à venir.

### Réconciliation des options pour `livret_sequence`

Tu m'avais dit : « on change la signature en aval pour se caler sur le
format venant de l'UI ». J'ai modifié `services/livret_sequence.py`
`normaliser_options` pour :
- **détecter** si l'argument est au format plat (nouveaux noms `contenu`,
  `inclure_fiches_resume_en_fin`, etc.) ou imbriqué (historique
  `{cours: {inclure, fiches_resume: ...}, exercices: ...}`)
- **convertir** au format imbriqué en interne avant traitement par
  le reste du module

Mapping plat → imbriqué :
- `contenu='cours_seul'` → `cours.inclure=True`, `exercices.inclure=False`
- `contenu='exercices_seul'` → l'inverse
- `inclure_fiches_resume_en_fin='non'` → `cours.fiches_resume.inclure=False`
- `inclure_fiches_resume_en_fin='completes'` → `inclure=True, a_completer=False`
- `inclure_fiches_resume_en_fin='a_completer'` → `inclure=True, a_completer=True`
- `inclure_enonces_serie_a` → `exercices.serie_A`

Les options additionnelles (`inclure_plan_travail_en_tete`,
`inclure_corriges_serie_*`, `inclure_corriges_remediation`) ne sont
pas encore exploitées par `generer_livret_sequence` — elles le seront
plus tard, quand le service métier sera étendu. Pas de modification
du code de génération du .tex cette session.

### Routes `routes/referentiel_documents_compilation.py` (nouveau)

- `POST /api/referentiels/<ref_id>/documents/<doc_id>/compiler`
  → 202 si lancé async, 400 si doc inactif, 404 si inconnu, 409 si
  déjà en cours, 503 si pdflatex indispo (gardé via compilateur_pdf)
- `GET /api/referentiels/<ref_id>/documents/<doc_id>/compiler/statut`
  → 200 `{statut: {en_cours, total, fait, etape_courante, erreur_globale},
  bdd: {compile_ok, compile_date, compile_log, compile_en_cours}}`
- `GET /api/referentiels/<ref_id>/documents/<doc_id>/pdf?cible=...`
  → 200 application/pdf, 400 si cible requise multi-cible, 404 si
  PDF non trouvé

Blueprint enregistré dans `app.py`.

### UI `static/atelier_referentiel.js` (étendu)

Sur chaque cadre Document du panneau :
- **Badge d'état effectif coloré** (gris/bleu/rouge/orange/vert)
- **Bouton « Tester »** visible si `actif=true` et pas en cours
- **Zone de progression** dépliée pendant la compilation
- **Lien PDF** pour les documents OK ou périmés (types unitaires)

Compilation côté UI :
- `atelRefCompilerDoc(docId)` : lance le POST `/compiler`
- `_atlRefDemarrerPolling(docId)` : `setInterval(700ms)` qui appelle
  `/compiler/statut` jusqu'à `en_cours=false`. Stoppe et recharge la
  liste des documents (pour avoir l'état effectif à jour).
- `_atlRefMajProgress(docId, data)` : met à jour la barre et le texte.

---

## Tests

`tests/test_v0_13_6_5_1_compilation.py` — **21 tests** :
- 2 sur la migration des colonnes
- 4 sur l'état effectif (non_compile, en_cours, ko, ok)
- 3 sur les cibles (unitaire, livret_sequence × N, evaluation × N)
- 1 sur les types non implémentés
- 3 sur compiler_document (refus inactif, refus en cours, doc inconnu)
- 6 sur les routes (compile inactif, compile inconnu, ref inconnu,
  statut, pdf non compilé, pdf cible requise)
- 1 sur reset des verrous orphelins
- 1 sur l'exposition des colonnes compile_* dans lister_documents

Tous passent. Suite complète :
- Avant : 2400 (baseline v0.13.6.4)
- Après : **2421 passed, 5 skipped**, 0 régression

---

## Décisions prises

| Question | Décision |
|---|---|
| Compilation synchrone vs async | Asynchrone via thread daemon |
| Suivi de progression | Dict en mémoire + endpoint GET `/statut` + polling JS |
| Stockage des PDFs | `data/referentiels/<ref_id>/` |
| Conventions de nom PDFs | `<type>.pdf` pour unitaires, `livret_sequence__<niveau>__<seq>.pdf`, `evaluation__<eval_id>.pdf` |
| Verrou de concurrence | `compile_en_cours` en BDD + reset auto au démarrage |
| Critère "périmé" cette session | Comparaison `compile_date` vs max(mtime) de tous les atomes du niveau (large) |
| Options livret_sequence | Format plat accepté côté `normaliser_options`, conversion en interne |
| Cardinalité éval | 1 PDF par éval (cibles multiples sous une même ligne du catalogue) |
| Annulation manuelle | Pas dans cette session |
| Bouton "Tester tous" | Pas dans cette session |

---

## Hors scope (à venir)

- ❌ Les 4 services métier manquants (`livret_fiches`, `livret_corriges`,
  `livret_cartes_recap`, `livret_cartes_planches`) → v0.13.6.5.2
- ❌ Affinage des dépendances atome→documents (critère "périmé" précis)
- ❌ Extension de `generer_livret_sequence` pour utiliser les nouvelles
  options (`inclure_plan_travail_en_tete`, `inclure_corriges_serie_*`,
  `inclure_corriges_remediation`)
- ❌ Figeage étendu (exiger documents OK + remplir `referentiel_*`) →
  v0.13.6.5.3
- ❌ UI riche pour visualiser les sous-PDFs (multi-cible) — un message
  générique "Plusieurs PDFs compilés" est affiché pour l'instant
- ❌ Bouton « Tester tous »
- ❌ Annulation manuelle d'une compilation en cours

---

## Validation côté Laurent

1. Décompresser le ZIP, recharger l'app Flask. Le redémarrage déclenche
   automatiquement la migration des 4 colonnes `compile_*`.
2. Aller dans l'atelier Référentiel, sélectionner un référentiel
   `en_cours`. Onglet « Documents à publier ».
3. Activer un document simple : par exemple `livret_cours` qui n'a
   qu'une option (fiches_resume). Cliquer sur **Tester**.
4. Tu vois :
   - Bouton qui devient « Compilation… » + désactivé
   - Badge qui passe de gris « Non compilé » à bleu « Compilation… »
   - Zone de progression avec texte + barre
5. À la fin : badge devient vert « OK » (ou rouge « Erreur » si le
   `.tex` ne compile pas). Un lien « 📄 Voir le PDF » apparaît.
6. Modifier un atome du niveau (ex: changer le titre d'une notion).
   Recharger l'onglet documents → le badge devient orange « Périmé »
   (signal qu'il faut recompiler).
7. Pour un `livret_sequence` activé, le test va compiler 14 PDFs
   (autant que de séquences du niveau). La progression affichera
   `1/14`, `2/14`, etc. Long.

---

## Points d'attention

- **Compilation lourde** : un `livret_sequence` complet peut prendre
  plusieurs minutes. Pendant ce temps, le thread Flask qui sert
  l'API reste libre (compilation dans un autre thread). Le polling
  toutes les 700ms ne charge pas spécialement le serveur.
- **PDFs sur disque** : `data/referentiels/<ref_id>/` peut grossir
  vite. Pas de nettoyage automatique cette session. Si tu testes
  beaucoup, il faudra purger à la main.
- **Critère "périmé" large** : pour cette session, modifier *n'importe
  quel* atome du niveau marque *tous les documents* du référentiel
  comme périmés. La finesse atome→documents impactés viendra plus
  tard. C'est un défaut d'ergonomie mais pas un défaut de correction.
- **pdflatex absent** : si MiKTeX n'est pas trouvé, le statut sera
  `ko` avec un log explicite. Pas de plantage Flask.

---

## Fichiers livrés

```
appli/persistence/sqlite_store.py                       (modifié, +~50 lignes)
appli/app.py                                            (modifié, +~3 lignes)
appli/services/referentiel_documents.py                 (modifié, +~30 lignes)
appli/services/referentiel_documents_compilation.py     (nouveau, ~500 lignes)
appli/services/livret_sequence.py                       (modifié, +~70 lignes)
appli/routes/referentiel_documents_compilation.py       (nouveau, ~250 lignes)
appli/static/atelier_referentiel.js                     (modifié, +~180 lignes)
appli/tests/test_v0_13_6_5_1_compilation.py             (nouveau, 21 tests)
appli/doc/redemarrage_v0_13_6_5_1.md                    (ce fichier)
```
