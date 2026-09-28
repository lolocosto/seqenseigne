# Redémarrage v0.13.6.13 — Chantier C : refonte du lien carte → objectif

## Périmètre

Refonte du modèle de lien entre les cartes d'automatisme et les
objectifs. Avant cette livraison, une carte portait directement
`(lien_type, lien_id)` pointant soit une notion, soit une méthode (1:1
implicite, vérifié par CHECK constraint). Désormais, le lien passe par
une table de liaison `objectif_cartes` (N:M), alignée sur la structure
des autres atomes (`objectif_notions`, `objectif_exos`,
`objectif_fiches`).

## Statut alpha — rappel

Aucune mise en production nulle part. Mais le contenu pédagogique de la
BdD doit être préservé. Toutes les modifications de schéma sont donc
**idempotentes et non-destructives** :

- `CREATE TABLE IF NOT EXISTS objectif_cartes` — ne touche pas une
  éventuelle table préexistante (cas neuf chez toi).
- **Aucun `DROP COLUMN`** sur `cartes_automatisme` : les colonnes
  `lien_type` et `lien_id` restent en place. Elles ne sont plus écrites
  par le service (les nouvelles cartes ont `lien_type=NULL, lien_id=NULL`)
  mais les anciennes valeurs sont conservées comme donnée historique.
  Leur retrait effectif est planifié pour v0.14 (nettoyage de schéma).
- Migration des données existantes : `INSERT OR IGNORE` à partir des
  liens legacy, idempotent. Au premier démarrage chez toi, la table
  sera peuplée avec 85 liaisons (49 méthode + 36 notion). Les démarrages
  suivants sont no-op.

## Décisions actées (rappel)

| Q | R |
|---|---|
| Schéma cible | Table de liaison `objectif_cartes` (sans `UNIQUE(carte_id)`) |
| Cardinalité | N:M structurel, 1:1 par usage métier actuel. L'application ne pose pas la contrainte d'unicité au niveau BdD pour permettre à un autre enseignant d'avoir une carte servant plusieurs objectifs. |
| Lien modifié depuis | Atelier d'assemblage de séquence uniquement (non implémenté en UI dans cette livraison ; pour l'instant le rattachement se fait par les routes API ou la migration automatique). |
| Workflow création | Création dans l'atelier carte sans lien (carte orpheline), rattachement plus tard. Quand l'atelier d'assemblage sera migré en OO, on y ajoutera la création directe d'atomes. |
| Orphelines | `objectif_id = NULL` (carte conserve son contenu, invisible dans l'assemblage) |
| Affichage tags | `obj 02` cohérent avec le chantier A pour les autres atomes |

## Migration des données réelles

Sur ta BdD réelle (`data/seqenseigne.db`) :
- 49 cartes méthode → 49 lignes dans `objectif_cartes` (1:1 strict)
- 36 cartes notion (notion liée à 1 objectif) → 36 lignes
- 38 cartes notion orphelines (notion sans objectif) → 0 ligne
- 0 cas ambigu (aucune notion liée à >1 objectif)

Total : **85 liaisons après migration, 38 cartes orphelines**. Toutes
les cartes restent visibles dans l'atelier carte ; seules les 85 cartes
liées apparaîtront dans l'atelier d'assemblage de séquence.

## Fichiers livrés

### Production (10 fichiers)

```
appli/persistence/schema.sql              DDL objectif_cartes + index
appli/persistence/sqlite_store.py         Migration data legacy → objectif_cartes
appli/services/cartes_automatisme.py      Helpers + creer_carte/modifier_carte
                                           acceptent objectif_ids ; hook
                                           validation utilise objectif_ids
appli/services/v2_lecture.py              _charger_cartes_de_partie via JOIN
                                           objectif_cartes (logique simplifiée)
appli/services/referentiels.py            _lister_cartes_de_partie même refactor
appli/services/liaisons_atomes.py         lister_liens_par_carte + intégration
                                           enrichir_liste_atomes('carte')
appli/routes/cartes_automatisme.py        api_lister/api_lire enrichissent
                                           avec `liens` ; api_creer accepte
                                           objectif_ids ; docstrings à jour
appli/scripts/peupler_cartes_n10.py       except Exception pour
                                           ValidationPedagogiqueErreur (au-delà
                                           de CarteErreur)
appli/static/atelier_carte_automatisme.js Refonte JS : sélecteur lien supprimé,
                                           tags `obj XX` depuis liens, bloc
                                           lecture seule `_remplirObjectifsLies`
appli/templates/index.html                Bloc « Lien » → « Objectifs liés »
                                           en lecture seule
```

### Tests (5 fichiers)

Adaptés pour le nouveau modèle :

```
appli/tests/test_v0_13_6_1_cartes_automatisme.py
appli/tests/test_v0_13_6_2_render_carte.py
appli/tests/test_v0_13_6_2_3_peuplement_cartes_n10.py
appli/tests/test_v0_13_6_3_2_assemblage_cartes.py
appli/tests/test_v0_13_6_3_referentiel_eval_cartes.py
```

Modifications-types :
- Ajout des tables `objectifs_v2`, `objectif_notions`, `objectif_cartes`
  dans les schémas minimaux des tests d'isolation
- Enrichissement des fixtures avec des objectifs liés aux notions et
  méthodes (pour que la dérivation automatique objectif_ids fonctionne)
- 2 tests « orphelin invisible » : passage à 'valide' via `UPDATE`
  direct au lieu de `valider_carte` (la validation pédagogique exige
  désormais une liaison non vide)
- 1 test du message de raison : « notion ni méthode » → « objectif »

## Architecture

### Backend

```
                  ┌─────────────────────────────────────┐
                  │  cartes_automatisme                 │
                  │  ──────────────────                 │
                  │  id, niveau, sequence, num          │
                  │  type_pedago, type_tech, nom        │
                  │  recto, verso, variables            │
                  │  etat_code, ordre, mtime            │
                  │  lien_type, lien_id (legacy, NULL   │
                  │                      pour les       │
                  │                      nouvelles)     │
                  └────────────┬────────────────────────┘
                               │
                               │ N:M (sans UNIQUE)
                               ▼
                  ┌─────────────────────────────────────┐
                  │  objectif_cartes  (v0.13.6.13)      │
                  │  ──────────────────────────         │
                  │  objectif_id  ──── FK objectifs_v2  │
                  │  carte_id     ──── FK cartes_auto…  │
                  │  ordre, mtime                       │
                  │  PRIMARY KEY (objectif_id, carte_id)│
                  └────────────┬────────────────────────┘
                               │
                               ▼
                  ┌─────────────────────────────────────┐
                  │  objectifs_v2                       │
                  └─────────────────────────────────────┘
```

### Interface service

```python
# Nouvelle interface (v0.13.6.13)
creer_carte(conn, niveau='N10', sequence='S01', objectif_ids=['ob_xxx'])
modifier_carte(conn, carte_id, objectif_ids=['ob_xxx', 'ob_yyy'])

# Rétrocompat (lien_type/lien_id encore acceptés, dérivation auto)
creer_carte(conn, niveau='N10', sequence='S01',
            lien_type='methode', lien_id='me_xxx')
# → écrit lien_type='methode', lien_id='me_xxx' dans cartes_automatisme
# ET dérive automatiquement les objectif_ids correspondants
# (via objectifs_v2.methode_id ou objectif_notions) pour les écrire
# dans objectif_cartes.
```

### Hook de validation

Le hook `_valider_carte_hook` qui exigeait `lien_type/lien_id != NULL`
exige désormais **au moins une liaison non vide dans `objectif_cartes`**
(via `carte['objectif_ids']`). Message d'erreur cohérent : « La carte
n'est liée à aucun objectif. ».

### Frontend

```
┌─ Atelier carte (avant) ─────────┐    ┌─ Atelier carte (après) ─────────┐
│ Identification                  │    │ Identification                  │
│ Lien                            │    │ Objectifs liés (lecture seule)  │
│   [○] 📖 Notion  [○] 📐 Méthode │    │   obj 02  obj 05                │
│   [select ...]                  │    │   modifiable depuis l'assemblage│
│ Variables xint                  │    │ Variables xint                  │
│ Recto / Verso                   │    │ Recto / Verso                   │
└─────────────────────────────────┘    └─────────────────────────────────┘
```

Le rendu en sidebar utilise désormais `window.atelLiensEnTags(c.liens)`
comme les autres ateliers d'atomes (cohérence avec le chantier A).

## Vérification

- Suite complète : **3233 passed, 5 skipped, 0 failed** (4 min chez moi)
- 0 régression sur les 3171 tests qui passaient en v0.13.6.12.4
- Migration testée sur la BdD réelle : 85 liaisons créées comme prévu
- Syntaxe Python (`ast.parse`) et JS (`node -c`) validées sur tous les
  fichiers modifiés

## Installation

Décompresser ce ZIP à la racine de `seqenseigne/` (les chemins relatifs
partent de `appli/`). F5 dans le navigateur après redémarrage Flask.

Au premier démarrage :
- Le `CREATE TABLE IF NOT EXISTS objectif_cartes` crée la table (no-op
  si elle existe déjà).
- La migration des 85 liaisons s'exécute automatiquement.
- Les démarrages suivants : tout est no-op (idempotent).

## Vérification post-installation (test rapide)

```sql
-- Combien de liaisons après migration ?
SELECT COUNT(*) FROM objectif_cartes;
-- Attendu : 85 sur ta BdD réelle

-- Combien de cartes orphelines (jamais liées à un objectif) ?
SELECT COUNT(*) FROM cartes_automatisme c
  WHERE NOT EXISTS (SELECT 1 FROM objectif_cartes oc WHERE oc.carte_id = c.id);
-- Attendu : 38 sur ta BdD réelle
```

Dans l'UI :
- Atelier carte : toutes les 123 cartes restent visibles. Pour celles
  qui sont liées, la zone « Objectifs liés » affiche les codes objectifs
  (`obj 02`, etc.). Pour les 38 orphelines, message « Aucun objectif
  lié — carte invisible dans l'assemblage. »
- Atelier d'assemblage de séquence : seules les 85 cartes liées
  apparaissent dans leurs parties respectives.

## Points de vigilance

1. **Cohérence creer_carte / lien legacy** : la rétrocompat des
   paramètres `lien_type`/`lien_id` est conservée intégralement. Tout
   code (script Python, test) qui appelle `creer_carte(...,
   lien_type='notion', lien_id='no_xxx')` continue de fonctionner ; les
   objectifs liés sont dérivés automatiquement et écrits dans
   `objectif_cartes`. C'est ce qui a permis d'éviter d'adapter le
   script `peupler_cartes_n10.py` lourdement (seul `except Exception`
   ajouté pour catcher la `ValidationPedagogiqueErreur`).

2. **Routes notions-disponibles / methodes-disponibles** : conservées
   au cas où, mais plus appelées par l'UI carte. À retirer en v0.14 si
   plus aucun consommateur identifié.

3. **`lien_type`/`lien_id` dans le JSON renvoyé par /api/cartes** :
   conservées dans `_row_vers_dict_carte` pour rétrocompat. L'UI peut
   les ignorer ; elle utilise désormais `c.liens` (format unifié) et
   `c.objectif_ids` (pour les opérations de modification).

## Prochaine étape

La migration des ateliers d'atomes est complète : tous (carte, notion,
méthode, fiche, exercice) héritent maintenant de `AtelierAtomique` et
partagent le format `liens` unifié. La cardinalité carte → objectif
peut maintenant être 1:N si besoin.

Reste à venir dans la migration des ateliers d'édition :
- Chantier D — suppression du sélecteur objectif dans l'atelier fiche
  (workflow nouvelle fiche à scoper)
- Migration `AtelierEvaluation` en OO (~1235 lignes, encore à variables
  globales `ATL_EVAL_*` + 49 fonctions globales `atelEval*`)
- Création de `AtelierAssemblage` et `AtelierRecap` (sur la même
  hiérarchie `AtelierEditeur`)
- Nettoyage de `atelier_atome_generique.js` (~600 lignes de code mort
  désormais inutilisé) et audit de `atelier_commun.js` (832 lignes)
- Chantier F (v0.13.7+) — sections configurables, gros, scoping dédié
- v0.14 — retrait des colonnes `lien_type`/`lien_id` de
  `cartes_automatisme` (nettoyage de schéma après cette livraison)

## Note mémoire

Comme évoqué en début de session, l'item 14 de la mémoire (résidus
v0.13.5.2.5) est obsolète depuis plusieurs livraisons. Quand tu
m'autorises, je le remplace par :

> **« Statut alpha — préserver le contenu pédagogique de la BdD.
> Migrations BdD idempotentes uniquement (`CREATE TABLE IF NOT EXISTS`,
> `ALTER TABLE ADD COLUMN` conditionnel). Aucun `DROP TABLE` ni `ALTER`
> destructif sans validation explicite. Les colonnes dépréciées sont
> retirées dans des livraisons de nettoyage dédiées (typiquement
> v0.14). »**
