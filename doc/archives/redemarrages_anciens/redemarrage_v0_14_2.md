# Redémarrage v0.14.2 — Backend unifié pour le rendu PDF

## Position dans le workstream unification

| | Statut |
|---|---|
| **v0.14.1** : Renommage `exo` → `exercice` | ✓ Livré et déployé OK |
| **v0.14.2** : Backend unifié (cette livraison) | ⏳ |
| **v0.14.3** : HTML standardisé pour les 4 ateliers | À venir |
| **v0.14.4** : Client unifié (descente AtelierEditeur, suppression AtelierAtomique + rendu_atome.js, spinner) | À venir |

## Cadrage validé

Décisions rappelées (cf. v0.14.1) :
- Niveau maximum d'unification
- Backend avant HTML (le client peut survivre temporairement avec `/api/cartes/...`)
- Suppression complète de `rendu_atome.js` et `AtelierAtomique` (en v0.14.4)
- Versioning sur v0.14 pour marquer la rupture cleanup

## Architecture v0.14.2

### Avant

```
GET  /api/cartes/<id>/rendu-pdf/info        (existe, ajouté v0.13.7.6.1)
POST /api/cartes/<id>/rendu-pdf              (existe)
GET  /api/cartes/<id>/rendu-tex              (existe)
GET  /api/cartes/<id>/rendu-log              (existe)

POST /api/atomes/<type>/<id>/rendu-pdf       (exercice/notion/methode/fiche)
GET  /api/atomes/<type>/<id>/rendu-tex
GET  /api/atomes/<type>/<id>/rendu-log
                                              <-- /info ABSENT
```

### Après

```
GET  /api/cartes/<id>/rendu-pdf/info         (conservé — alias)
POST /api/cartes/<id>/rendu-pdf              (conservé — alias)
GET  /api/cartes/<id>/rendu-tex              (conservé — alias)

# Nouveau set unifié :
POST /api/atomes/carte/<id>/rendu-pdf        ✨ nouveau
GET  /api/atomes/carte/<id>/rendu-pdf/info   ✨ nouveau
GET  /api/atomes/carte/<id>/rendu-tex        ✨ nouveau
GET  /api/atomes/carte/<id>/rendu-log        ✨ nouveau

# Et /info pour les 4 ateliers manquants :
GET  /api/atomes/exercice/<id>/rendu-pdf/info  ✨ nouveau
GET  /api/atomes/notion/<id>/rendu-pdf/info    ✨ nouveau
GET  /api/atomes/methode/<id>/rendu-pdf/info   ✨ nouveau
GET  /api/atomes/fiche/<id>/rendu-pdf/info     ✨ nouveau
```

Note : aucune nouvelle route n'est définie « en dur » avec le préfixe
`carte` — c'est la généralisation du paramètre `<type_atome>` qui rend
ces URLs accessibles automatiquement dès lors que `'carte'` est dans
`TYPES_ATOMES_TOUS`.

## Implémentation

### 1. `services/latex_rendu_atome.py` — Constantes et dispatch

**Nouvelle constante** `TYPES_ATOMES_TOUS = frozenset({'exercice',
'notion', 'methode', 'fiche', 'carte'})` à côté de `TABLES_ATOMES`
existant.

Pourquoi deux constantes :
- `TABLES_ATOMES` : mapping type → nom de table SQL. Utilisé par
  `generer_tex_atome` pour lire les 4 types classiques. La carte
  n'est PAS dedans car elle a son propre générateur (recto/verso,
  format A8, préambule autonome).
- `TYPES_ATOMES_TOUS` : ensemble des types acceptés par les routes
  API. Inclut 'carte'.

**Nouvelle fonction** `generer_tex_par_type(conn, type_atome, atome_id,
**kwargs)` :

```python
if type_atome not in TYPES_ATOMES_TOUS:
    raise ValueError(...)

if type_atome == 'carte':
    from services.render_carte import generer_tex_carte
    try:
        return generer_tex_carte(conn, atome_id)
    except CarteIntrouvable/CarteErreur as e:
        raise LookupError(str(e)) from e

# 4 types classiques : délégation à generer_tex_atome
return generer_tex_atome(conn, type_atome, atome_id, **kwargs)
```

L'**homogénéisation des exceptions** est importante : sans
conversion, les routes API auraient besoin de catcher
`CarteIntrouvable` séparément de `LookupError`. Avec la conversion,
toutes les routes traitent uniformément `LookupError → 404`.

### 2. `routes/rendu_atome.py` — Validation élargie + route /info

**Modifications minimales :**
- Import : `generer_tex_par_type` et `TYPES_ATOMES_TOUS` (au lieu de
  `generer_tex_atome` et `TABLES_ATOMES`)
- `_valider_type` : compare à `TYPES_ATOMES_TOUS` (au lieu de
  `TABLES_ATOMES`)
- Les 3 routes existantes (`/rendu-tex`, `/rendu-pdf`, `/rendu-log`)
  appellent maintenant `generer_tex_par_type(...)` au lieu de
  `generer_tex_atome(...)`

**Nouvelle route** `GET /api/atomes/<type_atome>/<atome_id>/rendu-pdf/info` :

```python
@bp.route('/api/atomes/<type_atome>/<atome_id>/rendu-pdf/info',
          methods=['GET'])
def api_rendu_pdf_info(type_atome, atome_id):
    erreur = _valider_type(type_atome)
    if erreur: return erreur

    try:
        with conn:
            tex = generer_tex_par_type(conn, type_atome, atome_id, ...)
    except LookupError: return 404
    except Exception: return {cache_valide: False, raison: 'tex_indisponible'}

    h = hash_tex(tex)
    pdf = chemin_pdf_cache(_cache_dir(), h)
    return {'cache_valide': pdf.is_file()}, 200
```

**Coût serveur** : génération du `.tex` (rapide, ms) + hashage SHA-256
+ stat fichier. **Aucun appel pdflatex.** L'UI peut interroger cette
route à chaque ouverture d'onglet Rendu PDF sans crainte de surcharge.

### 3. `routes/cartes_automatisme.py` — Inchangé

Les routes `/api/cartes/<id>/rendu-pdf`, `/api/cartes/<id>/rendu-pdf/info`,
`/api/cartes/<id>/rendu-tex` restent en place et fonctionnelles. Elles
servent d'**alias temporaire** pour la rétrocompatibilité jusqu'à
v0.14.4 où le client JS aura basculé sur les nouvelles URLs.

À supprimer dans cette future livraison v0.14.4.

## Sécurité contre les régressions

Le dispatch `generer_tex_par_type` est **un sur-ensemble** strict de
l'ancien `generer_tex_atome` :
- Pour les 4 types classiques : comportement IDENTIQUE (délégation
  pure, mêmes paramètres, même exceptions).
- Pour 'carte' : appel à `generer_tex_carte` (existant, stable depuis
  v0.13.6).

Donc :
- Les 3 routes existantes ne devraient pas changer de comportement
  pour les 4 types classiques. **Validé** : 3360 tests baseline +
  18 nouveaux v0.14.1 = 3378 tests passants avant cette livraison,
  3396 après (3378 + 18 v0.14.2). Aucun test cassé.

## Fichiers livrés

```
MODIFIÉS
  appli/services/latex_rendu_atome.py
    + TYPES_ATOMES_TOUS (constante)
    + generer_tex_par_type (fonction de dispatch, ~80 lignes)
  appli/routes/rendu_atome.py
    + Validation élargie aux 5 types
    + Route GET /info (~50 lignes)
    + Bascule des 3 routes existantes vers generer_tex_par_type

NOUVEAUX
  appli/tests/test_v0_14_2_backend_unifie.py     (18 tests)
  appli/doc/redemarrage_v0_14_2.md                (ce document)
```

## Vérifs

- pytest : **3396 passed, 5 skipped, 0 failed**
  (3378 baseline + 18 v0.14.2)
- `python -c "import ast; ast.parse(...)"` sur les 2 fichiers
  modifiés : OK

## À tester chez toi

### A — Aucune régression sur l'appli

1. Déployer le zip et hard reload navigateur.
2. **Atelier Carte automatisme** : ouvrir, choisir une carte avec
   cache, basculer vers Rendu PDF → le PDF doit s'auto-charger
   (le client utilise toujours `/api/cartes/<id>/rendu-pdf/info`).
3. **Atelier Exercice** : ouvrir, choisir un exercice, basculer vers
   Rendu PDF, cliquer « Compiler le rendu » → fonctionne comme avant
   (la route `/api/atomes/exercice/<id>/rendu-pdf` n'a pas changé).
4. Idem pour Notion, Méthode, Fiche.

### B — Vérification manuelle de la nouvelle route `/info`

Tu peux tester depuis ton navigateur ou avec curl :

```bash
# Cas atome inexistant — doit renvoyer 404
curl -i http://localhost:5000/api/atomes/notion/nx_inexistant/rendu-pdf/info

# Cas type invalide — doit renvoyer 400 avec liste des types
curl -i http://localhost:5000/api/atomes/inconnu/qq/rendu-pdf/info

# Cas carte existante (remplace par un vrai id de carte)
curl -i http://localhost:5000/api/atomes/carte/crt_756ac269b576/rendu-pdf/info
# Doit renvoyer 200 {"cache_valide": true} ou {"cache_valide": false}
```

### C — Vérification que `/api/cartes/<id>/rendu-pdf/info` (alias) fonctionne toujours

```bash
curl -i http://localhost:5000/api/cartes/crt_756ac269b576/rendu-pdf/info
```

Doit renvoyer la même chose qu'au point B sur la même carte.

## Prochaine étape : v0.14.3

HTML standardisé pour les 4 ateliers manquants. Ajout dans `index.html`
des sous-éléments :
- `#atl-<type>-btn-compiler`
- `#atl-<type>-rendu-status`
- `#atl-<type>-pdf-iframe`
- `#atl-<type>-rendu-erreur`
- `#atl-<type>-rendu-placeholder`

Pour les 4 ateliers : exercice, notion, methode, fiche. Sur le modèle
de la carte (qui les a déjà).

À cette étape, `rendu_atome.js` continue de fonctionner mais devra
être adapté pour écrire dans ce HTML statique au lieu de créer son
propre HTML par `innerHTML`. La suppression complète viendra en
v0.14.4.
