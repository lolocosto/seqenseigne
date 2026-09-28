# Redémarrage v0.13.6.8.2

**Session du 15 mai 2026 — Rationalisation du backend pour la validation d'état**

---

## Périmètre

Après la mise en lumière du bug d'URL (v0.13.6.8.1), tu as décidé
qu'on profite de l'occasion pour **rationaliser le backend**. Cette
livraison unifie les deux mécanismes parallèles de validation d'état
des atomes en **un seul** :

```
PATCH /api/atomes/<type>/<id>/etat
Body: {"etat_code": "valide" | "en_cours"}
```

avec `<type>` ∈ `{notion, methode, exercice, fiche_resume, carte}`.

La validation pédagogique de la carte est **conservée** via un système
de hooks extensible. Le `mtime` est maintenant mis à jour pour TOUS les
atomes à chaque changement d'état, ce qui prépare le mécanisme de
figeage des référentiels.

L'évaluation reste hors périmètre — c'est un assemblage, pas un atome,
elle sera traitée dans le chantier dédié aux assemblages
(séquence-niveau + évaluation).

---

## Décisions actées

| Q | R |
|---|---|
| Sort des anciennes routes `/valider` et `/devalider` ? | **Supprimer** (rupture nette, on est en alpha) |
| Inclure l'évaluation ? | **Non** (assemblage, pas atome) |
| Validation pédagogique carte ? | **Conserver** via système de hooks |

---

## Changements backend

### `services/etats_edition.py`

1. **`TABLES_ATOMES` étendu** : ajout de `'carte': 'cartes_automatisme'`.
   La carte est maintenant un type d'atome au même titre que notion,
   méthode, exercice, fiche_resume.

2. **Registre de hooks** : nouvelle constante
   `HOOKS_VALIDATION_PEDAGOGIQUE: dict[str, Callable]`.
   Peuplée via `enregistrer_hook_validation(type_atome, hook)` par les
   services métier qui veulent imposer des règles au passage → 'valide'.

3. **Nouvelle exception** `ValidationPedagogiqueErreur(message, raisons)`.
   Code stable `'validation_pedagogique_echec'`. Levée par les hooks.

4. **`changer_etat_atome` enrichi** :
   - Si transition → 'valide' et hook existe → l'exécute. Le hook peut
     lever `ValidationPedagogiqueErreur` qui remonte naturellement
     jusqu'à la route HTTP.
   - L'UPDATE met aussi à jour `mtime = CURRENT_TIMESTAMP` (toutes les
     tables atomes ont cette colonne).

### `services/cartes_automatisme.py`

1. **Suppression de `valider_carte()` et `devalider_carte()`**. Les
   appelants doivent utiliser `etats_edition.changer_etat_atome`.

2. **Suppression de `DejaValide` et `DejaEnCours`**. Le nouveau mécanisme
   est idempotent : passer un atome à son état courant ne lève pas
   d'erreur (juste un UPDATE sans effet visible).

3. **Suppression de `ValidationPedagogiqueErreur`** côté carte. La
   carte utilise maintenant celle d'`etats_edition`.

4. **Nouvelle fonction `_valider_carte_hook(conn, carte_id)`** :
   contient les règles métier carte (recto/verso non vides, lien défini,
   variables si paramétrée). Lève `etats_edition.ValidationPedagogiqueErreur`
   avec `raisons=[...]`.

5. **Auto-enregistrement** : au chargement du module, la fonction
   `_enregistrer_hook_validation_carte()` enregistre le hook dans le
   registre de `etats_edition`. C'est-à-dire :
   ```py
   # En fin de cartes_automatisme.py
   _enregistrer_hook_validation_carte()
   ```

### `routes/etats_edition.py`

1. **Ajout du code HTTP** `'validation_pedagogique_echec': 400` dans le
   mapping `_CODE_HTTP`. Le payload retourné contient maintenant
   `{error, code, raisons: [...]}` quand un hook échoue.

### `routes/cartes_automatisme.py`

1. **Suppression des routes** `POST /api/cartes/<id>/valider` et
   `/devalider`. Plus disponibles. Tout client qui les appelait reçoit
   404.

2. **Nettoyage du mapping `_CODE_HTTP`** : suppression de
   `'deja_valide'`, `'deja_en_cours'`, `'validation_pedagogique_echouee'`
   (cette dernière était le code de l'erreur carte, remplacée par celle
   d'`etats_edition` qui a un code différent).

---

## Changements frontend

### `static/atelier_carte_automatisme.js`

**Suppression de la surcharge `_postChangementEtat`**. Le mécanisme
unifié `PATCH /api/atomes/carte/<id>/etat` (avec `typeApi: 'carte'`
déjà configuré) fonctionne naturellement maintenant que `'carte'` est
dans `TABLES_ATOMES`.

Conséquence : le code de la carte est **plus simple** qu'avant
v0.13.6.8.1. Plus aucune divergence avec les autres ateliers atomiques.

### `static/atelier_editeur.js`

`_postChangementEtat` enrichi pour **récupérer les `raisons`** du
payload d'erreur quand la validation pédagogique échoue :
```js
let msg = errData.error || errData.message || `HTTP ${resp.status}`;
if (Array.isArray(errData.raisons) && errData.raisons.length > 0) {
  msg += ' — ' + errData.raisons.join(' ');
}
```

Donc si tu essaies de valider une carte avec recto vide, le toast
affichera : « La carte ne peut pas être validée en l'état. — Le recto
est vide. La carte n'est liée à aucune notion ni méthode. »

---

## Changements de tests

### `tests/test_v0_10_4_etats_edition.py`

1. **`_SCHEMA_TEST` enrichi** : ajout de `mtime` sur toutes les tables
   atomes, ajout de `fiches_resume` et `cartes_automatisme`.
2. **Fixture `base` enrichie** : insertion d'une fiche et d'une carte.
3. **`test_tous_les_types_atomes_supportes`** étendu : 5 types testés
   maintenant (avec une nuance pour carte qui a le hook).
4. **`test_recap_initial`** mis à jour pour 5 types.

### `tests/test_v0_13_6_1_cartes_automatisme.py`

1. **`_SCHEMA_TEST` enrichi** : ajout de la table `etats_edition`
   (peuplée) + `mtime` sur notions/methodes.
2. **Classe `TestValiderDevalider`** entièrement réécrite :
   - Utilise `changer_etat_atome` au lieu de `valider_carte`/`devalider_carte`
   - Lève `etats_edition.ValidationPedagogiqueErreur` au lieu de celle
     de la carte
   - Plus de `DejaValide`/`DejaEnCours` → remplacés par tests d'idempotence
   - Nouveau test `test_mtime_mis_a_jour_au_changement_etat`
3. **Classe `TestRoutesWorkflow`** :
   - Routes : `POST /api/cartes/<id>/valider` → `PATCH /api/atomes/carte/<id>/etat`
   - Format réponse : avant la carte complète, maintenant
     `{type_atome, atome_id, etat_code}` (format etats_edition)
   - Code d'erreur : `'validation_pedagogique_echouee'` → `'validation_pedagogique_echec'`
   - Raisons : avant dans `details.raisons`, maintenant au top level
     `raisons`
   - Nouveau test `test_anciennes_routes_404` qui vérifie que les
     anciennes routes ont bien disparu

### Résultat suite complète

- **2471 passed, 5 skipped** (vs 2469 avant : 2 tests supplémentaires nets)
- **0 régression**

---

## Schéma BDD

Pas de migration nécessaire. La colonne `mtime` existe **déjà** sur
toutes les tables atomes :
- `cartes_automatisme.mtime` : présent dans `schema.sql` (DDL initial)
- `notions/methodes/exercices/fiches_resume.mtime` : ajouté par
  migration `_migrer_schema_post_ddl` au démarrage Flask
- `evaluations.mtime` : présent dans le DDL initial (mais hors périmètre)

Donc à l'installation de cette livraison, **rien à faire côté BDD**.

---

## Validation chez toi

### Test fonctionnel 1 — Validation individuelle (chaque atelier)
1. Ouvrir un exercice, cliquer « Valider » → pastille verte, persistance
2. Cliquer « Repasser en cours » → pastille grise, persistance
3. Idem pour notion, méthode, fiche
4. **Carte** : avec recto/verso/lien renseignés → validation OK
5. **Carte** : avec recto vide → toast d'erreur explicite :
   « La carte ne peut pas être validée en l'état. — Le recto est vide. »

### Test fonctionnel 2 — Multi-sélection
6. Sélectionner 5 exercices, cliquer « Valider » → toast « 5 validés »
7. Plus aucun 404 dans le log Flask
8. Sélectionner 3 cartes dont 2 valides et 1 incomplète → toast
   reflète : « 2 validées, 1 en échec — Le recto est vide. ... »

### Test fonctionnel 3 — Anciennes routes supprimées
9. `curl -X POST http://localhost:5000/api/cartes/<id>/valider` → 404
   (vérification rapide depuis le terminal)

### Test mtime
10. Valider un atome puis observer le `mtime` en BDD :
    ```bash
    sqlite3 data/db.sqlite "SELECT id, etat_code, mtime FROM notions LIMIT 5"
    ```
    Le `mtime` doit refléter l'instant de la dernière transition.

---

## Bénéfices acquis

1. **Un seul mécanisme** côté backend pour 5 types d'atomes
2. **Un seul code path** côté frontend (la surcharge dans `AtelierCarte`
   a disparu)
3. **Validation pédagogique extensible** : si tu veux ajouter une règle
   pour notion (« titre non vide »), tu ajoutes un hook dans
   `services/notions.py` (ou similaire) et tu fais
   `etats_edition.enregistrer_hook_validation('notion', mon_hook)`.
4. **`mtime` mis à jour systématiquement** : prêt pour le figeage des
   référentiels.
5. **Code mort supprimé** : ~50 lignes en moins entre service et routes
   carte.

---

## Fichiers livrés

| Fichier | Statut |
|---|---|
| `appli/services/etats_edition.py` | refondu (TABLES_ATOMES étendu, hooks, ValidationPedagogiqueErreur, mtime) |
| `appli/services/cartes_automatisme.py` | refondu (suppression valider/devalider, ajout hook + auto-enregistrement) |
| `appli/routes/etats_edition.py` | enrichi (ValidationPedagogiqueErreur) |
| `appli/routes/cartes_automatisme.py` | nettoyé (suppression routes /valider et /devalider) |
| `appli/static/atelier_editeur.js` | enrichi (récupération des raisons) |
| `appli/static/atelier_carte_automatisme.js` | nettoyé (suppression surcharge `_postChangementEtat`) |
| `appli/tests/test_v0_10_4_etats_edition.py` | adapté (SCHEMA_TEST + 2 nouveaux types) |
| `appli/tests/test_v0_13_6_1_cartes_automatisme.py` | adapté (nouveau mécanisme) |

Décompresser à la racine de `seqenseigne/`. F5.

---

## Architecture résultante

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend                                                       │
│  ─────────                                                      │
│  AtelierEditeur._postChangementEtat()                           │
│     → PATCH /api/atomes/<type>/<id>/etat                        │
│         body: {"etat_code": "valide" | "en_cours"}              │
│                                                                 │
│  Tous les ateliers (carte, notion, méthode, fiche, exercice)    │
│  utilisent ce même code path.                                   │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  routes/etats_edition.py                                        │
│  ─────────────────────────                                      │
│  PATCH /api/atomes/<type>/<id>/etat                             │
│     → services.etats_edition.changer_etat_atome()               │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  services/etats_edition.py                                      │
│  ──────────────────────────                                     │
│  changer_etat_atome(conn, type, id, etat):                      │
│     1. Vérifier type ∈ TABLES_ATOMES (5 types)                  │
│     2. Vérifier atome existe                                    │
│     3. Vérifier code d'état valide                              │
│     4. Si nouvel_etat == 'valide' :                             │
│        hook = HOOKS_VALIDATION_PEDAGOGIQUE.get(type)            │
│        if hook : hook(conn, id)                                 │
│           ↑ peut lever ValidationPedagogiqueErreur              │
│             qui remonte naturellement vers HTTP 400             │
│     5. UPDATE etat_code + mtime = CURRENT_TIMESTAMP             │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                  ┌─────────────────────────────┐
                  │  Hooks enregistrés          │
                  │  ────────────────────       │
                  │  - 'carte' →                │
                  │    services/cartes_automa.. │
                  │    _valider_carte_hook      │
                  │                             │
                  │  (autres types : pas de     │
                  │   hook → validation libre)  │
                  └─────────────────────────────┘
```

---

## Suite

Roadmap inchangée :
- v0.13.6.9 : chantier A — affichage homogène `placedTags`
- v0.13.6.10 : chantier B — bouton « reprendre titre objectif »
- v0.13.6.11+ : chantier C — refonte modèle carte (1:1 strict vers objectif)
- v0.13.6.12+ : chantier D — suppression sélecteur objectif fiche
- v0.13.7+ : chantier F — description configurable des sections

**Et plus tard** : généraliser le mécanisme unifié aux **assemblages**
(séquence-niveau et évaluation). Probablement un chantier dédié quand
on attaquera l'atelier d'assemblage de séquence-dans-niveau (étape 2
de l'ordre de travail).

---

## Leçon retenue (suite de v0.13.6.8.1)

Le bug d'URL fictive de v0.13.6.8.1 a eu un effet positif : il a
révélé une dette technique structurelle (deux mécanismes parallèles
qui faisaient grosso modo la même chose). Au lieu de patcher
ponctuellement, on a unifié.

C'est exactement ce que tu décrivais dans tes principes :
« Chaque fois qu'un bug touche plusieurs ateliers, c'est signe qu'il
faut migrer en OO/factoriser plutôt que patcher. »

La même règle s'applique au backend : un bug d'URL sur 5 ateliers
révèle qu'il y avait probablement 2 mécanismes parallèles. Confirmé.
