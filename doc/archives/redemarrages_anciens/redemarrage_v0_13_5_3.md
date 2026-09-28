# redemarrage_v0_13_5_3.md

Document de continuité — fin de session **v0.13.5.3**.

## Statut

| Version | Statut |
|---|---|
| v0.13.5.1 → .2.5 | ✅ Atelier Évaluation BDD + services + UI complète |
| **v0.13.5.3** | 🟡 **À déployer chez Laurent** (rendu .tex + PDF + fix résidus v25) |
| v0.13.5.* | ✅ Série terminée après déploiement de cette livraison |

## Ce qui a été fait en v0.13.5.3

1. **Générateur `.tex` éval** (`services/render_evaluation.py`) — pipeline
   complet calqué sur `generer_tex_atome`, avec préambule transitif.
2. **Routes rendu-tex et rendu-pdf** — pattern strictement identique aux
   routes des atomes, réutilise `compiler_atome` (qui est générique).
3. **UI** : boutons « Compiler le rendu » et « LaTeX généré » branchés,
   gestion des erreurs de compilation (422/503) avec affichage des
   raisons.
4. **Fix résidus v25** : `api_exos_disponibles` et `calculer_couverture`
   exposent désormais niveau/sequence/serie_code/num pour le label métier
   N10/S01/F01 côté UI.
5. **Extension `preambule_atome.py`** : type `'evaluation'` ajouté à
   `WRAPPER_PAR_TYPE`.
6. **Intégration paquet `core-eval`** dans le pipeline de peuplement :
   - `scripts/peuplement_14_paquet_vers_base.py` : ajout de
     `seqenseigne-core-eval.sty` à `FICHIERS_ORDRE`
   - `services/paquet_regles_atome.py` : 6 macros éval passées en
     `STATUT_REUTILISE`, 3 règles obsolètes (`\seqEvalBaremeItem`,
     `\seqEvalQCMItem`, `qcm`) retirées

## ⚠️ Étape obligatoire au déploiement

Après déploiement du ZIP, **re-peupler la base** depuis Admin → Import
mise en forme. Le rapport doit afficher :
- Total : **353 définitions**
- seqenseigne-core-eval.sty 13 defs ... → reutilise: 13
- ✓ Toutes les règles explicites correspondent à une définition en base.

## Décisions clés Laurent (v0.13.5.3)

Documentées dans le code et dans le README de la livraison :

| Q | Décision |
|---|---|
| 1 | Titre QCM saisi en dur (le moteur seqQcm adapte les colonnes auto) |
| 2 | Pas de `theme=` dans `\seqTitreEval` (défaut macro) |
| 3 | `etab=` et `classe=` vides pour l'instant |
| 4 | Code objectifs : `S01.Obj. 02` |
| 5 | `nbReps` auto-déduit (rien à passer) |
| 6 | Énoncé inséré raw |
| 7 | `\seqEvalCorrigeExo` toujours émis, marque `\emph{}` si vide. `\seqEvalAfficheCorriges` toujours appelé |
| 8 | Item langue émis SI rempli ET mode != criteres |
| Bonus | Numéros d'exercices en chiffres romains (helper Python `_romain`) |

## Tests

| | Linux (CI Claude) | Windows attendu |
|---|---|---|
| v0.13.5.2.5 baseline | 2235 passed + 5 skipped | 2216 + 16 skipped |
| **v0.13.5.3 final** | **2292 passed + 5 skipped** | **~2281 + 16 skipped** |
| Δ | +57 | +57 |

Décomposition des +57 :
- +57 nouveaux tests dans `test_v0_13_5_3_render_evaluation.py`
  (helpers, sections du .tex, génération complète, routes, résidus v25,
  préambule)
- 0 régression sur les autres tests (les 8 lignes ajoutées au schéma
  `_SCHEMA_TEST` de `test_v0_13_5_2_2_evaluations_metier.py` réparent
  les 7 régressions induites par le SELECT enrichi de calculer_couverture)

## Fichiers livrés (8)

```
appli/services/render_evaluation.py        ← NOUVEAU (générateur .tex)
appli/services/preambule_atome.py          ← +21 lignes (type 'evaluation')
appli/services/evaluations.py              ← enrichissement SELECT calculer_couverture
appli/routes/evaluations.py                ← +145 lignes (2 routes + helpers + fix api_exos_disponibles)
appli/static/atelier_evaluation.js         ← ~120 lignes remplacées (boutons branchés)
appli/static/atelier_commun.js             ← +3 lignes (mapping libellé étendu)
appli/tests/test_v0_13_5_3_render_evaluation.py        ← NOUVEAU (57 tests)
appli/tests/test_v0_13_5_2_2_evaluations_metier.py     ← +8 lignes (schéma enrichi)
```

## Cache de compilation

Le cache `data/cache_rendus/` est **partagé** entre atomes et évaluations.
Le nom des PDF dans le cache est un hash du .tex, pas de risque de collision.
Si Laurent observe la présence de hashs nouveaux, c'est normal.

## Pour la prochaine session

### Si Laurent valide v0.13.5.3 → série v0.13.5.* close

Choix entre :

**Option A : Reprise de la roadmap ordonnée**
- Étape 3 : atelier plans de travail (dépend de l'assemblage séquence-niveau)
- Étape 4 : atelier référentiels millésimés
- Étape 5 : reprise suivi classes / progressions annuelles

**Option B : v0.14 — Refonte onglet admin + nettoyage**
- Suppression `exercice_objectifs`, `services/edition_progression.py`,
  `ATL_OBJ_CAT`, route `/api/objectifs`, table `objectifs`
- Intégration UI admin du diagnostic atomes orphelins (v0.10.7)
- Outils selectif (purger par niveau/séquence/type)

**Option C : « Livret de corrigés d'exos »** (mentionné dans le paquet)
- Sous-version `core-exos` avec 4 flags indépendants R/AE/F/A/E
- À planifier après définition fine du besoin

À décider avec Laurent en début de session.

### Si Laurent rapporte un bug sur v0.13.5.3

Reproduction en sandbox systématique. Pour les bugs liés à la
compilation LaTeX (probables : un .tex généré qui ne compile pas), le
chemin de diagnostic est :

1. Récupérer le .tex via `GET /api/evaluations/<id>/rendu-tex`
2. Le compiler en isolation sur le poste Windows
3. Identifier la ligne fautive
4. Corriger soit le générateur (`render_evaluation.py`), soit le paquet
   `seqenseigne` côté `.dtx`, soit l'énoncé en BDD si c'est une macro
   privée

## Mémo workflow Claude/Laurent (rappel)

- **Toute livraison** = ZIP racine avec `MANIFEST.md5`, `README.md`,
  doc en `appli/doc/redemarrage_*.md`
- **Sandbox testée** avant packaging
- **Linux : passed + skipped** doit être ≥ Windows attendu
- **`encoding='utf-8'` partout** dans les scripts Python (Windows cp1252)
- **Pas de Git** : delivery par ZIPs successifs
