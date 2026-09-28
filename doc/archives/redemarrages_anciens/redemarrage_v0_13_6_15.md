# Redémarrage v0.13.6.15 — Harmonisation backend (étape 1/2)

## ⚠ Livraison backend uniquement — UI temporairement cassée

Cette livraison contient **uniquement la refonte backend** de
l'harmonisation. Le frontend reste inchangé et **cassera** sur les
sidebars d'ateliers (notion, méthode, exercice, carte, fiche) tant que
v0.13.6.16 n'est pas livrée.

**Recommandation** : ne pas déployer v0.13.6.15 sur ton USB de travail
isolément. Attendre v0.13.6.16 qui adapte le frontend, déployer les
deux en bloc, ou déployer ailleurs pour tester.

Si tu déploies quand même : tu peux toujours créer/modifier/supprimer
les atomes (les routes POST/PUT/DELETE sont inchangées) mais les
sidebars afficheront probablement des éléments dégradés (titre vide,
identifiants `undefined/undefined/CA01`, etc.). La compilation PDF et
les imports continuent de fonctionner.

## Périmètre

L'objectif est d'éliminer les « subtilités importantes » entre les
ateliers d'édition. Avant : chaque atelier avait son propre format de
réponse côté API, ses propres préfixes calculés côté JS, sa propre
logique de chargement. Après : un contrat uniforme, un service
générique, des comportements identiques.

## Décisions actées

| Q | R |
|---|---|
| Contrat de retour des routes liste | Exactement 6 clés : `{id, titre, num, code, etat_code, liens}`. Pas de champs supplémentaires. |
| Code préfixé centralisé | Calculé côté backend par `_code_atome` (élimine la logique préfixe dans chaque `rendreItem` JS). Préfixes : `N`, `M`, `E`/`A`/`F`/`R` (selon série), `CA`, `FR`. |
| Renommage `cartes_automatisme.nom → titre` | Migration BdD idempotente (ALTER TABLE RENAME COLUMN) pour aligner sur les autres atomes |
| Format de réponse `/api/cartes` GET liste | Passé de `{"cartes": [...]}` à liste directe `[...]` (cohérent avec notion/méthode/exercice/fiche) |
| Niveau et sequence obligatoires sur les 5 routes GET liste | Plus de mode « tous » sans filtre |
| Routes GET unitaires créées | `/api/notions/<id>`, `/api/methodes/<id>`, `/api/exercices/<id>` (cartes et fiches en avaient déjà) |
| « Initialiser depuis » dans atelier_fiche | À retirer en v0.13.6.16 (les 2 fetchs `/api/methodes` et `/api/notions` sans filtre cassent avec le nouveau contrat) |

## Statut alpha — rappel

La migration `nom → titre` est non-destructive : `ALTER TABLE
cartes_automatisme RENAME COLUMN nom TO titre`, idempotente. Au premier
démarrage chez toi, les 123 cartes voient leur titre préservé. Testé
sur copie de ta BdD réelle.

## Architecture cible

### Service générique `services/atomes_liste.py`

```python
from services.atomes_liste import lister_atomes_sequence

# Retour uniforme pour les 5 types d'atomes
atomes = lister_atomes_sequence(conn, 'notion', 'N10', 'S03')
# → [{'id': 'no_xxx', 'titre': 'Proportion',
#     'num': 1, 'code': 'N01',
#     'etat_code': 'en_cours', 'liens': [...]}, ...]

# Types supportés
TYPES_ATOMES_SUPPORTES = {'notion', 'methode', 'exercice', 'carte', 'fiche'}
```

Le code préfixé est calculé centralement par `_code_atome` :

| Atome | Préfixe | Exemple |
|-------|---------|---------|
| notion | `N` | `N01`, `N12` |
| méthode | `M` | `M01`, `M12` |
| exercice | série | `E01`, `A03`, `F02`, `R05` |
| carte | `CA` | `CA01`, `CA12` |
| fiche | `FR` | `FR01`, `FR03` |

### Routes refondues

| Route | Type | Comportement |
|-------|------|--------------|
| `GET /api/notions?niveau=X&sequence=Y` | liste légère | 6 clés, paramètres obligatoires |
| `GET /api/methodes?niveau=X&sequence=Y` | liste légère | idem |
| `GET /api/exercices?niveau=X&sequence=Y` | liste légère | idem (param `serie` retiré) |
| `GET /api/cartes?niveau=X&sequence=Y` | liste légère | idem, retour devenu liste directe |
| `GET /api/fiches-resume?niveau=X&sequence=Y` | liste légère | idem |
| `GET /api/notions/<id>` | détail | **nouveau** — retour complet enrichi `liens` |
| `GET /api/methodes/<id>` | détail | **nouveau** |
| `GET /api/exercices/<id>` | détail | **nouveau** |
| `GET /api/cartes/<id>` | détail | inchangé (déjà existant + enrichi `liens` en v0.13.6.13) |
| `GET /api/fiches-resume/<id>` | détail | inchangé (enrichi `liens` en v0.13.6.14.1) |

POST/PUT/DELETE inchangés sur tous les types.

## Migration BdD — `cartes_automatisme.nom → titre`

Exécution automatique au démarrage de Flask, idempotente :

```python
# persistence/sqlite_store.py — au démarrage
if 'nom' in cols_ca and 'titre' not in cols_ca:
    conn.execute("ALTER TABLE cartes_automatisme RENAME COLUMN nom TO titre")
```

Sur ta BdD réelle (test fait sur copie) : 123 cartes, titres tous
préservés. La migration est invisible côté usage (sauf si tu fais
directement du SQL avec l'ancien nom de colonne).

Tous les sites consommateurs du backend sont alignés :
- `services/cartes_automatisme.py` : `_row_vers_dict_carte`,
  `creer_carte` (paramètre `nom` → `titre`), `modifier_carte`,
  hook validation pédagogique
- `services/v2_lecture.py` : `_charger_cartes_de_partie`
- `services/referentiels.py` : `_lister_cartes_de_partie`
- `services/livret_cartes_planches.py` et `livret_cartes_recap.py` :
  lisent `c.get('titre')`, **conservent l'option LaTeX `nom=…`** côté
  .tex (paquet seqenseigne non modifié, le renommage de l'option LaTeX
  est hors scope de cette livraison)
- `services/render_carte.py` : idem
- `scripts/peupler_cartes_n10.py` : SQL `WHERE titre = ?`, paramètre
  `creer_carte(titre=...)`. Le dict métier `TOUTES_CARTES_N10` garde
  sa clé locale `'nom'` (juste une variable Python, pas la colonne BdD).

## Fichiers livrés

### Production (13 fichiers)

```
appli/persistence/schema.sql               DDL cartes_automatisme.titre
appli/persistence/sqlite_store.py          Migration ALTER TABLE RENAME COLUMN
appli/services/atomes_liste.py             NOUVEAU — service générique
appli/services/cartes_automatisme.py       nom → titre partout
appli/services/v2_lecture.py               _charger_cartes_de_partie
appli/services/referentiels.py             _lister_cartes_de_partie
appli/services/livret_cartes_planches.py   SELECT titre, option LaTeX `nom=` conservée
appli/services/livret_cartes_recap.py      idem
appli/services/render_carte.py             carte['titre']
appli/routes/atomes.py                     5 routes : 3 liste refondues + 3 unitaires
appli/routes/cartes_automatisme.py         api_lister : retour liste directe
appli/routes/fiches_resume.py              api_lister_fiches refondu
appli/scripts/peupler_cartes_n10.py        titre= au lieu de nom=
```

### Tests adaptés (8 fichiers)

```
appli/tests/test_v0_13_6_1_cartes_automatisme.py     schéma + sites nom= + asserts
appli/tests/test_v0_13_6_2_render_carte.py           schéma + creer_carte(titre=...)
appli/tests/test_v0_13_6_2_3_peuplement_cartes_n10.py schéma
appli/tests/test_v0_13_6_3_2_assemblage_cartes.py    nom= → titre=, c['nom'] → c['titre']
appli/tests/test_v0_13_6_3_referentiel_eval_cartes.py idem (substitution batch)
appli/tests/test_v0_13_6_5_2_livrets_manquants.py    INSERT titre + fixture
appli/tests/test_v0_10_4_etats_edition.py            INSERT titre + GET /api/notions?…
appli/tests/test_routes.py                           5 tests adaptés au nouveau contrat
```

## Vérification

- Suite complète : **3238 passed, 5 skipped, 0 failed** chez moi
- 0 régression sur les tests existants (après adaptation des 7
  tests directement liés aux changements de contrat)
- Migration testée sur copie de ta BdD réelle : 123 cartes, titres
  préservés intégralement
- Syntaxe Python (`ast.parse`) validée sur tous les fichiers modifiés

## À tester chez toi — backend uniquement

⚠ **Ne teste pas via l'UI** : elle cassera. Teste directement via curl
ou les outils de dev du navigateur.

### Migration au démarrage

Premier démarrage Flask après installation : tu dois voir dans les logs
console :
```
[seqenseigne] ✓ migration cartes_automatisme.nom → titre
```
Les démarrages suivants : aucune trace (idempotent).

### Routes liste — contrat à 6 clés

```bash
curl 'http://localhost:5000/api/notions?niveau=N10&sequence=S03'
# Attendu : liste avec uniquement {id, titre, num, code, etat_code, liens}

curl 'http://localhost:5000/api/cartes?niveau=N10&sequence=S03'
# Attendu : liste directe (plus d'enveloppe {"cartes": [...]})

curl 'http://localhost:5000/api/exercices?niveau=N10&sequence=S03'
# Attendu : codes E01, A02, F03, R05 selon la série
```

### Routes liste — paramètres obligatoires

```bash
curl 'http://localhost:5000/api/notions'
# Attendu : 400 avec {"error": "Paramètres 'niveau' et 'sequence' requis."}
```

### Routes GET unitaires nouvelles

```bash
# Récupère un id via /api/notions?niveau=…&sequence=…
curl 'http://localhost:5000/api/notions/no_xxx'
# Attendu : détail complet (corps, sections, etc.) + liens
```

## Frontend cassé — détail des symptômes attendus

L'atelier carte côté JS lit aujourd'hui `c.nom`, `c.niveau`, `c.sequence`,
`c.type_pedago`, `c.type_tech` dans son `rendreItem`. Avec le nouveau
contrat, ces clés sont absentes (à l'exception de `nom` qui devient
`titre` côté UI). Symptômes attendus :

- Sidebar carte : titre vide (`c.nom` → `undefined`), identifiant
  `undefined/undefined/CA01` (pas de `c.niveau`/`c.sequence`)
- Sidebar notion/méthode/exercice/fiche : moins visibles puisque
  ces ateliers utilisent déjà le format `{id, titre, num, …}` pour
  l'essentiel, mais certains champs (`niveau`, `sequence`) sont
  manquants pour la construction de `idLib`
- Atelier fiche « Initialiser depuis » : deux fetchs `/api/methodes`
  et `/api/notions` sans filtre → 400 Bad Request. Le sélecteur reste
  vide / le bouton inopérant

Ces 4 régressions UI sont **corrigées en v0.13.6.16**.

## Notes diverses

1. **L'option LaTeX `nom=…` côté .tex est conservée** par
   `services/livret_cartes_planches.py`, `livret_cartes_recap.py` et
   `render_carte.py`. Le paquet seqenseigne (`.dtx`) attend toujours
   `nom=` comme option `xkeyval`. Le renommage de l'option LaTeX en
   `titre=` est un chantier paquet distinct, à programmer plus tard.

2. **`serie_code` pour les exercices** n'est pas posé à la création par
   `creer_exercice` du service. Il est calculé à l'écriture par
   `ecrire_exercices` (mapping `fondamental → F`, etc.). Donc pour des
   exos créés sans `serie_code` posé, le code de la liste tombera sur
   `?01` (préfixe sentinelle de `_code_atome` en cas de série vide).
   Pas observé en pratique : tous les exos importés ont un serie_code
   valide via le scanner ou le peuplement.

3. **Les routes `/api/cartes/niveau/<n>/sequence/<s>/notions-disponibles`
   et `methodes-disponibles`** : conservées au cas où. Plus appelées
   par le frontend depuis v0.13.6.13. À retirer en v0.14 si confirmé.

## Prochaine étape — v0.13.6.16

Refonte frontend pour aligner avec le nouveau contrat backend :

- `AtelierEditeur.ouvrirItem` : GET unitaire systématique (plus de
  « cache d'abord, fetch en fallback »). Suppression de la surcharge
  `AtelierFiche.ouvrirItem` qui devient identique au parent.
- `rendreItem` de chaque atelier : utilise `c.code` (préfixé) directement
  au lieu de calculer le préfixe localement. Élimine la logique
  dispersée. L'identifiant sidebar devient juste `c.niveau/c.sequence/c.code`
  — mais `c.niveau` et `c.sequence` ne sont plus dans le contrat liste ;
  le frontend les récupère via les filtres globaux `window.ATL_FILTRE_NIVEAU`
  et `window.ATL_FILTRE_SEQ` (cohérent puisque la liste est filtrée
  sur ces valeurs).
- Suppression de « Initialiser depuis » dans atelier_fiche
  (sera réintroduit plus tard avec un design propre).
- Tests HTTP nouveaux pour `PATCH /api/atomes/<type>/<id>/etat`
  (couverture qui aurait évité le bug 1 de v0.13.6.14).
- Adaptation du cas `c.type_tech === 'parametree'` pour le badge `P` :
  selon décision v0.13.6.15, le badge est retiré de la sidebar
  (info reste dans le formulaire).
