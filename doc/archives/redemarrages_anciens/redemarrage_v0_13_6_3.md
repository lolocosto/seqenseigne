# Redémarrage v0.13.6.3

**Session du 12 mai 2026 — Référentiel : évaluations et cartes d'automatisme**

---

## Récap version

| Version | État |
|---|---|
| v0.13.6.2.3 | ✅ Peuplement 122 cartes N10 + MANIFEST format corrigé |
| **v0.13.6.3** | 🟡 **À déployer** — Référentiel enrichi (évaluations + cartes par partie) |
| v0.13.6.4 | À venir : UI Livrets annuels |

## Demande initiale

L'onglet **Référentiel** (portée Niveau) affiche aujourd'hui les
séquences avec leur arbre partie → objectif → atomes (méthodes,
fiches, notions, exos F/A/E + R/EA). Manquaient deux choses :

1. **Les cartes d'automatisme** : à intercaler dans chaque partie de
   séquence, **avant** les Révisions/Approches, en listant les cartes
   liées aux notions/méthodes de cette partie.
2. **Les évaluations** : à afficher au top niveau (au-dessus des
   séquences), dans leur propre cadre, car rattachées au niveau et
   non aux séquences.

Englobement souhaité : un cadre « Évaluations », puis un cadre
« Séquences » au-dessous.

Pour les évaluations, un sous-cadre par éval avec son titre +
chip cliquable par exo, code couleur pour l'état (comme les exos
dans les séquences).

Réutilisation maximale de l'existant : design system `.atl-cadre`,
chips d'atomes, deeplinks, etc.

## Découvertes pendant la session

### Anomalies de rattachement méthode → objectif

L'audit initial a révélé :
- 22 méthodes liées à plusieurs objectifs (dont 16 dans des parties
  différentes)
- 0 notion multi-objectifs (sain)

Rapport détaillé livré en `anomalies_rattachement_methodes.md`.
Laurent a nettoyé la BDD en cours de session et m'a envoyé la BDD
mise à jour : **0 méthode multi-objectifs** vérifié post-nettoyage.

### Cartes orphelines

Beaucoup de cartes (60 sur 123) sont liées à des notions qui ne sont
pas encore rattachées à un objectif (le rattachement se fait dans
l'atelier d'assemblage Livret, en cours). Ces cartes restent
**invisibles** dans le référentiel — décision « option A stricte » :
le référentiel reflète le programme effectif. Les cartes apparaîtront
au fur et à mesure que les notions seront attachées à des objectifs.

## Ce qui a été fait

### Service `services/referentiels.py`

Extension de `arbre_du_niveau(conn, niveau)` :

1. **Nouvelle clé top-level `evaluations`** : liste des évaluations
   du niveau avec leur structure complète. Chaque éval contient `id`,
   `numero`, `titre`, `etat_code`, `ordre`, `mode_notation` et `exos`
   (liste de dicts type `exo` avec code court F01/A01/E01, etat_code,
   nav_niveau/nav_seq pour deeplink).

2. **Nouvelle clé `atomes_cartes` sur chaque partie** : liste des
   cartes d'automatisme rattachées via méthode/notion → objectif →
   partie. Chaque carte porte `id`, `code` (CA01, CA02…), `titre`,
   `type_pedago`, `type_tech`, `etat_code`, et nav_niveau/nav_seq.

3. **Stats globales** : les exos d'évaluation et les cartes par partie
   entrent dans `total`/`valides`/`en_cours`.

Deux nouvelles fonctions privées :
- `_lister_cartes_de_partie(conn, niveau, seq_code, partie_id)`
- `_lister_evaluations_du_niveau(conn, niveau)`

### Frontend `static/atelier_referentiel.js`

3 modifications :

1. **Englobement top-level** : `atelRefRendreArbre` génère désormais
   un cadre « Évaluations » suivi d'un cadre « Séquences » contenant
   l'arbre actuel.

2. **Bloc cartes par partie** : `atelRefPartieHtml` intercale une
   ligne « Cartes d'automatisme : `chip1` `chip2` … » *avant* le bloc
   R/EA, sur le même pattern visuel que les Révisions/Activités.

3. **Cadre Évaluations** : `atelRefEvaluationsCadreHtml` rend un
   sous-cadre par éval (atl-cadre--compact) avec titre + rangée de
   chips d'exos. Couleur du titre selon état (vert si valide).
   Titre non cliquable cette session (pas d'API pour pré-sélectionner
   une éval depuis un deeplink — évolution future possible).

4. **Deeplink étendu** : ajout du type `carte` au mapping
   atomeUrl → atelier `carte_automatisme`. Les chips de cartes sont
   donc cliquables et ouvrent l'atelier carte sur la carte précise.

### Frontend `static/app.js`

Une modification pour supporter le nouveau deeplink :

- `_appliquerDeeplink` : ajout de `carte_automatisme` à
  `types_supportes` et au mapping fnNom → `atelCarteOuvrir`.

### Tests `tests/test_v0_13_6_3_referentiel_eval_cartes.py`

12 nouveaux tests :

- 5 tests pour la clé `evaluations` (présence, vide, structure complète,
  isolation par niveau, stats)
- 7 tests pour la clé `atomes_cartes` (présence, carte→méthode,
  carte→notion, notion non-rattachée → invisible, cumul méthode+notion,
  stats, isolation par niveau)

Tous passent (12 passed) + suite complète : **2384 passed, 5 skipped**
(= 2372 baseline + 12 nouveaux). **Zéro régression**.

## Décisions prises

| Question | Décision |
|---|---|
| Carte orpheline (notion sans objectif) | Option A stricte : invisible |
| Doublon carte sur méthode multi-parties | Inutile (BDD nettoyée par Laurent) ; filet `DISTINCT` SQL conservé |
| Titre d'éval cliquable | Non (pas d'API de pré-sélection, à ajouter plus tard) |
| Chips d'exos d'éval cliquables | Oui — ouvre l'atelier Exercice sur l'exo source |
| Chips de cartes cliquables | Oui — ajout du type `carte` au deeplink global |
| Tables `referentiel_*` modifiées | Non (chantier d'archivage différé à l'étape 4) |
| Schéma BDD modifié | Non (lecture seule sur tables existantes) |

## Hors scope (explicitement)

- ❌ Tables `referentiel_*` (chantier étape 4 plus tard)
- ❌ Snapshots/figement des évals et cartes dans les millésimes
- ❌ Atelier d'assemblage séquence-dans-niveau (étape 2 du chantier
  courant — la reprise après cette session)
- ❌ Refonte de l'atelier d'évaluation
- ❌ Pré-sélection d'une éval depuis un deeplink (l'atelier eval
  n'expose pas cette API ; à ajouter ultérieurement si utile)

## Validation

| Test | Résultat |
|---|---|
| Syntaxe Python service modifié | OK (`ast.parse`) |
| Syntaxe JS atelier_referentiel + app | OK (`node -c`) |
| Tests dédiés v0.13.6.3 | 12/12 pass |
| Suite pytest complète | 2384 pass, 5 skipped, 0 régression |
| Sanity sur BDD réelle (`arbre_du_niveau` N10) | OK — 1 éval + 4 exos + 63 cartes réparties sur S01-S14 |

## Pour la prochaine session

### Évolutions naturelles côté UI référentiel

- **Pré-sélection d'une éval via deeplink** : ajouter
  `atelEvalChargerById(evalId)` dans `atelier_evaluation.js`, exposer
  comme `window.atelEvalChargerById`, ajouter `'evaluation'` au mapping
  `app.js`. Permet de rendre le titre d'éval cliquable.
- **Lien « créer une carte pour cette notion »** quand le bloc cartes
  d'une partie est vide alors qu'il y a des notions/méthodes.

### Roadmap longue (rappel des items déjà notés)

- Étape 2 : Atelier assemblage séquence-dans-niveau (chantier courant)
- Étape 3 : Atelier plans de travail
- Étape 4 : Atelier référentiels millésimés (ouvrira les tables
  `referentiel_cartes`, `referentiel_evaluations`, etc.)
- Étape 5 : Suivi classes / progressions annuelles
- Multisélection + menu contextuel pour validation rapide (utile
  maintenant pour valider les notions/méthodes/cartes en lot)

## Points d'attention

- **Cartes liées à notion orpheline** : visuellement, beaucoup de
  cartes N10 (60/123) ne remontent pas dans le référentiel parce que
  leurs notions ne sont pas encore attachées à un objectif. C'est le
  comportement strict décidé en session. Pendant que tu travailles
  sur l'atelier d'assemblage (étape 2 du chantier), tu verras les
  cartes apparaître progressivement dans le référentiel à mesure que
  tu rattaches les notions à des objectifs.
- **Stats globales** : avec les 1 évaluation existante (4 exos) +
  63 cartes visibles, le total N10 monte à 419 atomes (vs 352 avant
  v0.13.6.3 — gain de 67 atomes : 4 exos d'éval + 63 cartes).
- **Deeplink atelier carte** : nouveau chemin `?atelier=carte_automatisme`
  fonctionne. Si tu cliques un chip CA dans le référentiel, l'atelier
  carte s'ouvre et charge la carte précise via `atelCarteOuvrir(id)`.

## Fichiers livrés

```
appli/services/referentiels.py               (modifié, +~110 lignes)
appli/static/atelier_referentiel.js          (modifié, ~80 lignes ajoutées)
appli/static/app.js                          (modifié, +2 lignes minimes)
appli/tests/test_v0_13_6_3_referentiel_eval_cartes.py  (nouveau, 12 tests)
appli/doc/redemarrage_v0_13_6_3.md           (ce fichier)
anomalies_rattachement_methodes.md           (déjà livré séparément en session)
```
