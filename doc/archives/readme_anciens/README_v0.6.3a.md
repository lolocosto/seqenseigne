# seqenseigne v0.6.3a — infrastructure établissements + calendrier scolaire

Livraison préparatoire pour la refonte de l'écran Progression annuelle.
Pas encore d'UI : cette livraison pose les fondations côté modèle de
données et API. Les 3 livraisons suivantes (b, c, d) consommeront tout ça
pour afficher un vrai calendrier scolaire.

## Ce qui est posé

### 1. Nouvelle entité : `etablissements`

Un établissement est désormais une entité de plein droit, avec UUID opaque
(comme le reste de la base). Il remplace la colonne texte
`etablissement` qui était dupliquée dans `classes` et `progressions`.

```sql
CREATE TABLE etablissements (
    id        TEXT PRIMARY KEY,      -- 'et_xxxxxxxx'
    nom       TEXT NOT NULL,
    uai       TEXT,
    academie  TEXT DEFAULT '',
    ville     TEXT DEFAULT '',
    adresse   TEXT DEFAULT '',
    etat      TEXT DEFAULT 'propose' CHECK (etat IN ('propose','valide')),
    UNIQUE (nom)
);
```

Les tables `classes` et `progressions` portent désormais `etablissement_id`
(FK avec `ON DELETE RESTRICT`) au lieu de la colonne texte.

Un établissement a deux états :
- **`propose`** : créé à l'import ou à la main, méta (académie, ville…)
  vides ou approximatives.
- **`valide`** : validé via l'annuaire de l'Éducation Nationale par UAI,
  tous les champs sourcés officiellement.

### 2. Création automatique à l'import

Rien à faire côté importeur : quand on écrit une classe avec juste
`etablissement: "Collège Les Hautes Ourmes"`, le store détecte l'absence
de l'établissement et le crée avec l'état `propose`. Pareil pour les
progressions. Compatible avec tout le code existant.

### 3. Nouvelle colonne `progressions.etat`

Nouvelle colonne d'état de la progression :
`en_cours` / `valide` / `verrouille`. C'est le badge que l'UI affichera
dans le panneau gauche (v0.6.3b). Elle commande aussi l'activation des
boutons d'édition (v0.6.3c).

### 4. Service `calendrier_scolaire`

`services/calendrier_scolaire.py` :
- Mapping `ACADEMIE_ZONE` (25 académies métropolitaines → Zone A / B / C).
  Validé pour le zonage en vigueur depuis 2020-2021.
- `vacances(annee_scolaire, zone, store)` : appelle
  `data.education.gouv.fr` (dataset `fr-en-calendrier-scolaire`), cache
  en base.
- `jours_feries(annee, store)` : appelle `calendrier.api.gouv.fr`
  (dataset Etalab officiel), cache en base.
- `jours_feries_annee_scolaire(annee_scolaire, store)` : agrège 2 années
  civiles et filtre sur la période septembre → août. Tolérant à l'API
  partiellement indisponible.

### 5. Service `etablissements`

`services/etablissements.py` :
- `creer / lister / lire / mettre_a_jour` : CRUD standard.
- `valider_par_uai(store, etab_id, uai)` : interroge l'annuaire EN
  (`fr-en-annuaire-education`) par UAI, remplit automatiquement les
  champs académie/ville/adresse, passe l'état à `valide`.
- `rechercher_uai(store, uai)` : appel annuaire EN avec cache (les UAI
  sont stables).

### 6. Nouvelle table `cache_api`

```sql
CREATE TABLE cache_api (
    cle         TEXT PRIMARY KEY,   -- 'vacances:B:2021-2022', 'feries:2024', 'annuaire:0351234A'
    payload     TEXT NOT NULL,       -- JSON brut de la réponse API
    fetched_at  TEXT NOT NULL        -- ISO 8601
);
```

Un cache simple, pas d'invalidation automatique : les années scolaires
passées ne bougent plus ; les années futures peuvent être ré-interrogées
manuellement via `?force=1`.

### 7. Routes API

**Établissements** (`routes/etablissements.py`) :
- `GET /api/etablissements` — liste
- `GET /api/etablissements/<id>` — détail
- `POST /api/etablissements` — créer (`nom` requis, autres champs optionnels)
- `PATCH /api/etablissements/<id>` — mettre à jour méta
- `POST /api/etablissements/<id>/valider` — `{uai: "0351234A"}` → interroge
  l'annuaire, remplit, passe à `valide`
- `DELETE /api/etablissements/<id>` — supprimer (échoue si utilisé par une
  classe ou une progression)

**Calendrier** (`routes/calendrier.py`) :
- `GET /api/calendrier/vacances?annee=2021-2022&academie=Rennes`
  (résout zone B via le mapping) ou `&zone=B` directement
- `GET /api/calendrier/jours-feries?annee_scolaire=2021-2022`
- `GET /api/calendrier/jours-feries?annee=2024`

Ajouter `&force=1` pour ignorer le cache et ré-interroger l'API.

## Déploiement

```powershell
# 1. Copier les fichiers :
#    - appli\app.py
#    - appli\persistence\schema.sql
#    - appli\persistence\ids.py
#    - appli\persistence\sqlite_store.py
#    - appli\services\calendrier_scolaire.py      (nouveau)
#    - appli\services\etablissements.py           (nouveau)
#    - appli\routes\etablissements.py             (nouveau)
#    - appli\routes\calendrier.py                 (nouveau)
#    - appli\tests\test_calendrier_scolaire.py    (nouveau)
#    - appli\tests\test_etablissements.py         (nouveau)

# 2. Supprimer l'ancienne base (schéma refacto)
cd D:\Enseignement\seqenseigne\appli
del data\seqenseigne.db
del data\seqenseigne.db-shm   (si présent)
del data\seqenseigne.db-wal   (si présent)

# 3. Re-importer depuis l'arborescence
python importer_arborescence.py --racine D:\Enseignement_old

# 4. Redémarrer Flask
lancer.bat
```

## Vérification

Après import, vérifier via URL directe :

```
http://localhost:5000/api/etablissements
```

Tu devrais voir la liste des établissements créés (tous en état
`propose`, académie vide). C'est normal : la prochaine livraison (v0.6.3b)
apportera l'UI pour compléter ou valider par UAI.

## Tests

**348 tests verts** (326 existants + 22 nouveaux sans aucune régression).

Nouveaux tests :
- `test_calendrier_scolaire.py` : mapping zones, cache vacances, cache
  jours fériés, agrégation année scolaire, tolérance API down (11 tests).
- `test_etablissements.py` : CRUD, unicité par nom, validation UAI mockée,
  cache UAI (11 tests).

## Notes techniques

### Compatibilité ascendante

Le refacto `etablissement → etablissement_id` est transparent :
- Les `lire_classes()` / `lire_progression()` font un JOIN avec
  `etablissements` et retournent toujours `etablissement` (nom) pour les
  appelants existants.
- Les `ecrire_*()` acceptent soit `etablissement_id`, soit `etablissement`
  (nom) — avec création automatique.
- Aucun test existant n'a eu à être modifié.

### Fallback "Non renseigné"

Les tests legacy qui créaient des progressions sans établissement
fonctionnent toujours : le store crée automatiquement un établissement
`"Non renseigné"` avec état `propose`. Évite de casser les tests, et
signale proprement à l'enseignant qu'il manque une info.

### Pourquoi pas de ponts ?

Les ponts (jour ouvré entre un férié et un week-end) ne sont pas une
règle officielle mais une pratique variable selon l'établissement et la
décision locale. Décision Laurent : s'en tenir aux jours fériés
officiels. Si besoin d'ajouter des "ponts" plus tard, le mieux sera de
laisser l'enseignant les cocher à la main dans l'UI calendrier.

## Roadmap après v0.6.3a

- **v0.6.3b** — UI gestion des établissements dans Gestion des classes.
  Bouton "Valider avec UAI" → popup saisie UAI → appel
  `/api/etablissements/<id>/valider` → remplissage automatique des champs.
- **v0.6.3c** — calendrier visuel (grille semainière sept→août) dans le
  panneau gauche du sous-onglet Progression. Vacances grisées, jours
  fériés marqués. Badge d'état de la progression
  (en_cours / valide / verrouille). Fonction `progUIEnabled(etat)` qui
  active/désactive les boutons d'édition selon l'état.
- **v0.6.3d** — détail créneau enrichi avec liste d'objectifs,
  suppression de la vue synthétique devenue redondante.

## Fichiers

```
appli/app.py
appli/persistence/schema.sql          (tables etablissements + cache_api, refacto FK)
appli/persistence/ids.py              (+ nouveau_id_etablissement)
appli/persistence/sqlite_store.py     (CRUD etablissements, refacto lire/ecrire)
appli/services/calendrier_scolaire.py (nouveau)
appli/services/etablissements.py      (nouveau)
appli/routes/etablissements.py        (nouveau)
appli/routes/calendrier.py            (nouveau)
appli/tests/test_calendrier_scolaire.py (nouveau)
appli/tests/test_etablissements.py    (nouveau)
```
