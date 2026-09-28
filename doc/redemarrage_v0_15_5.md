# Redémarrage v0.15.5 — Dette technique : factorisation `_cycle_du_niveau`, suite verte, ménage v1

## Contexte

Session dédiée à la dette technique (périmètre Bloc A + B convenu en cadrage).

En auditant l'état réel du code (et non la seule doc), trois constats :

1. **La suite n'était pas verte** : `3 failed, 3668 passed` au lieu du
   `3671 passed` annoncé en v0.15.4. Les 3 échecs étaient permanents et
   masqués depuis le renommage `_fige`→`_verrouille` de v0.15.3.
2. **Le bug `_cycle_du_niveau` était sous-estimé** : décrit comme un bug
   isolé d'un service, c'était en réalité une **duplication dans 5 services**
   dont **4 portaient le bug** C03/N10-N12.
3. **La dette v1 était sur-estimée** : la table `exercice_objectifs`, le JS
   `ATL_OBJ_CAT`, la route `/api/objectifs`, `edition_progression.py` et
   `atelier_atome_generique.js` étaient **déjà supprimés** avant v0.15.5. Il ne
   restait que 2 scripts one-shot et des commentaires.

## Plan livré (4 chantiers)

### 1. Suite verte (Bloc A) — correction `_fige` → `_verrouille`

`tests/test_v0_15_2_10_importer_referentiel_externe.py` cherchait le dossier
`_fige/` alors que l'outil `importer_referentiel_externe.py` produit
`_verrouille/` depuis v0.15.3. 13 occurrences corrigées (chemins, variable
locale `dossier_fige`→`dossier_verrouille`, nom de fonction de test, docstrings).

### 2. Factorisation `_cycle_du_niveau` (Bloc B)

**Avant** : 5 services livret embarquaient chacun leur `_cycle_du_niveau`.
Quatre (`livret_recap_exos`, `livret_recap_cours`, `livret_fiches`,
`livret_corriges`) portaient la jointure buggée :

```sql
JOIN sequences_du_cycle sdc ON spn.sequence_code = sdc.code
WHERE spn.niveau = ? LIMIT 1     -- SANS filtre cycle
```

Un code de séquence (ex. S01) existant en C03 ET C04, le `LIMIT 1` remontait
C03 pour les niveaux de cycle 4 (N10/N11/N12). Seul `livret_plans_de_travail`
était correct (déléguait déjà à `param_niveaux.lire_cycle` via un wrapper).

**Après** : les 5 wrappers supprimés. Tous les services appellent directement
`services.param_niveaux.lire_cycle(conn, niveau)` (lecture de la table
`param_niveaux`, source unique de vérité, indépendante des tables séquence).

**Décision** : appel direct plutôt que wrapper mince. Le wrapper de
`livret_plans_de_travail` ne servait qu'à reformuler le message d'exception
(« Aucun cycle trouvé… » au lieu de « Niveau inconnu… »). Or :
- `NiveauInconnu` est déjà une sous-classe de `LookupError` → contrat de type
  préservé pour tous les appelants (`except LookupError`).
- Aucun appelant ne matche le **texte** du message (vérifié exhaustivement).

Le changement de message est donc sans impact fonctionnel.

### 3. Ménage v1 résiduel (Bloc B)

- Suppression de `scripts/supprimer_v1.py` (office terminé : structures v1
  droppées du schéma ET de la BDD de prod en v0.14.6.b.2).
- Suppression de `scripts/peuplement_02_repeupler.py` (wrapper CLI orphelin ;
  les méthodes `ecrire_*` qu'il appelait vivent dans `SqliteStore` et restent
  testées).
- Tests : retrait de la classe `TestScriptSupprimerV1` ; correction de la
  docstring de `test_peuplement_repeupler.py` (il n'importait pas le script).
- Nettoyage d'une docstring obsolète dans `sqlite_store.py` (mention
  `exercice_objectifs` dans `ecrire_exercices`). Les autres mentions sont des
  commentaires historiques documentant *pourquoi* on n'écrit plus dans ces
  tables v1 — conservés à dessein.

### 4. Resynchronisation de la doc

`DETTE_TECHNIQUE.md` et `NETTOYAGE.md` mis à jour : bug `_cycle_du_niveau`
requalifié RÉSOLU, chantier « Nettoyage v1 » clôturé, items déjà faits
(`atelier_atome_generique.js`, fichier placeholder) marqués clos.

## Décisions techniques clés

- **Effets de bord de la factorisation** : avec `lire_cycle` (qui réussit dès
  que `param_niveaux` est peuplé), les générateurs `livret_fiches`/`corriges`
  ne s'arrêtent plus tôt sur un `LookupError` « cycle absent » comme avant.
  Trois fichiers de tests s'appuyaient sur cet arrêt précoce :
  - `test_v0_13_6_5_2_livrets_manquants.py` : la fixture `_setup_minimal_niveau`
    créait les séquences sous un cycle fictif `C99` ≠ cycle réel du niveau dans
    `param_niveaux` (N10→C04) → livret vide. **Corrigé** : la fixture lit le
    cycle réel via `lire_cycle` et crée thème + séquence sous ce cycle.
  - `test_v0_13_6_5_1_compilation.py` et `test_v0_13_6_5_1_1_orchestrateur.py` :
    `except LookupError: pass` ne couvrait plus le cas où le générateur va
    jusqu'à `construire_preambule` et bute sur `paquet_definitions` (absente de
    la fixture nue). **Corrigé** : ajout de `except sqlite3.OperationalError`,
    hors scope explicite de ces tests (qui ne visent que l'absence de stub
    `type_non_implemente`).

## Tests

**v0.15.5 : 3688 passed, 7 skipped, 0 failed.**

Évolution depuis v0.15.4 (3671 réels, dont 3 cassés non comptés) :
- +9 : `tests/test_v0_15_5_cycle_du_niveau.py` (nouveau, garde-fou
  anti-régression).
- −2 : `TestScriptSupprimerV1` retirée (script supprimé).
- +3 réparés : tests `_fige` de `test_v0_15_2_10`.

### Nouveau fichier de test

`tests/test_v0_15_5_cycle_du_niveau.py` :
- `TestResolutionCanonique` : `lire_cycle` renvoie C04 pour N10/N11/N12, C03
  pour N09, `NiveauInconnu`(LookupError) pour niveau inconnu, et résiste au
  contexte-piège (S01 en C03 ET C04).
- `TestPlusDeWrapperLocal` : vérifie pour chacun des 5 services qu'il n'a plus
  de `def _cycle_du_niveau`, plus la résolution de cycle buggée
  (`SELECT sdc.cycle_code … LIMIT 1` sans filtre), et qu'il importe `lire_cycle`.

## Fichiers livrés (`seqenseigne_v0_15_5.zip`)

| Fichier | Type |
|---|---|
| `appli/services/livret_recap_exos.py` | Modifié (suppression wrapper + lire_cycle) |
| `appli/services/livret_recap_cours.py` | Modifié (idem) |
| `appli/services/livret_fiches.py` | Modifié (idem) |
| `appli/services/livret_corriges.py` | Modifié (idem) |
| `appli/services/livret_plans_de_travail.py` | Modifié (idem) |
| `appli/persistence/sqlite_store.py` | Modifié (docstring nettoyée) |
| `appli/tests/test_v0_15_5_cycle_du_niveau.py` | Nouveau |
| `appli/tests/test_v0_12_1_livret_plans_de_travail.py` | Modifié (import lire_cycle) |
| `appli/tests/test_v0_15_2_10_importer_referentiel_externe.py` | Modifié (_fige→_verrouille) |
| `appli/tests/test_v0_13_6_5_2_livrets_manquants.py` | Modifié (fixture cycle réel) |
| `appli/tests/test_v0_13_6_5_1_compilation.py` | Modifié (except OperationalError) |
| `appli/tests/test_v0_13_6_5_1_1_orchestrateur.py` | Modifié (except OperationalError) |
| `appli/tests/test_v0_14_6_b2_suppression_v1.py` | Modifié (retrait TestScriptSupprimerV1) |
| `appli/tests/test_peuplement_repeupler.py` | Modifié (docstring) |
| `appli/doc/DETTE_TECHNIQUE.md` | Modifié (resync) |
| `appli/doc/NETTOYAGE.md` | Modifié (resync) |
| `appli/doc/redemarrage_v0_15_5.md` | Nouveau (ce document) |

### Suppressions (à appliquer chez toi)

| Fichier | Action |
|---|---|
| `appli/scripts/supprimer_v1.py` | À SUPPRIMER |
| `appli/scripts/peuplement_02_repeupler.py` | À SUPPRIMER |

Le ZIP de livraison contient la diff (fichiers modifiés/nouveaux). Pour les
deux scripts supprimés, exécuter chez toi :

```powershell
Remove-Item appli\scripts\supprimer_v1.py
Remove-Item appli\scripts\peuplement_02_repeupler.py
```

## Vérification post-déploiement

```powershell
.\outils\python\python.exe outils\verifier_md5.py --racine . --manifest MANIFEST.md5
.\outils\python\python.exe -m pytest tests/ -q
# Attendu : 3688 passed, 7 skipped, 0 failed
```

## Roadmap (rappel)

- Compléter l'import N11_v2025 (PDFs S02-S14).
- Parser `.tex` plan de travail (objectif → notions).
- Atelier suivi de classe : câbler `verrouille → utilise`.
- CRUD cycle/niveaux/thèmes/séquences.
- Aliases rétrocompat v0.15.3 (`figer_*`) : à retirer en v0.16+.
