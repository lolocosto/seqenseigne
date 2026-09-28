# Redémarrage v0.13.7.0e — Factorisation routes atomes + PATCH partout

## Périmètre

Aboutissement du fil garde-de-sortie + côté serveur :

1. **Côté serveur** : factorisation des 15 routes REST des 3 types
   d'atomes (notion, méthode, exercice) en une fonction-fabrique
   `_enregistrer_routes_atome`. Les routes notion/methode/exercice qui
   étaient quasi-identiques (3 × 5 = 15 fonctions) deviennent 3 appels
   d'une seule fonction.

2. **Côté serveur** : **toutes** les routes d'update des atomes sont
   passées en strict **PATCH** (plus de PUT). Concerne notion, méthode,
   exercice, carte et fiche. Cohérent avec la sémantique réelle des
   services `modifier_*` (whitelist + assignation partielle).

3. **Côté frontend** : méthode HTTP par défaut dans `AtelierEditeur`
   passée de PUT à **PATCH**. Le `methodeUpdate: 'PATCH'` ajouté
   spécifiquement pour la carte en v0.13.7.0d.1 est retiré (redondant
   avec le nouveau défaut).

4. **Tests** : 4 tests qui utilisaient `client.put(...)` sur des routes
   d'atomes/fiches sont migrés vers `client.patch(...)`.

C'est la livraison qui ferme proprement le fil. La pile peut maintenant
revenir au chantier prévu (factorisation des sections atomique, puis
éditeur LaTeX).

## Cohérence sémantique HTTP

### Avant (incohérent)

| Atome | Route | Méthode déclarée | Sémantique réelle |
|---|---|---|---|
| Notion | `/api/notions/<id>` | PUT | **PATCH** (partial update via whitelist) |
| Méthode | `/api/methodes/<id>` | PUT | **PATCH** |
| Exercice | `/api/exercices/<id>` | PUT | **PATCH** |
| Carte | `/api/cartes/<id>` | PATCH | **PATCH** ✓ cohérent |
| Fiche | `/api/fiches-resume/<id>` | PUT | **PATCH** |

L'incohérence n'avait jamais posé problème jusqu'à ce que la garde de
sortie unifiée (v0.13.7.0d) appelle `sauvegarder()` pour la carte. Le
parent envoyait PUT → 405 sur la carte. Symptôme : « sauvegarder » dans
la modale échouait silencieusement.

### Après (cohérent strict)

| Atome | Route | Méthode |
|---|---|---|
| Notion | `/api/notions/<id>` | **PATCH** |
| Méthode | `/api/methodes/<id>` | **PATCH** |
| Exercice | `/api/exercices/<id>` | **PATCH** |
| Carte | `/api/cartes/<id>` | **PATCH** |
| Fiche | `/api/fiches-resume/<id>` | **PATCH** |

Plus simple, plus uniforme, plus correct vis-à-vis de la spécification
HTTP.

Note importante : un client qui enverrait `PUT` à ces routes obtiendra
désormais un `405 Method Not Allowed`. Vérifié : aucun appel `PUT` à
ces routes ne subsiste dans le code (frontend + tests).

## Factorisation `routes/atomes.py`

### Avant

3 blocs identiques pour notion, méthode, exercice. Chacun :

```python
@bp.route("/api/<segment>", methods=["GET"])
def api_get_<segment>(): ...

@bp.route("/api/<segment>/<id>", methods=["GET"])
def api_get_<atome>(...): ...

@bp.route("/api/<segment>", methods=["POST"])
def api_create_<atome>(): ...

@bp.route("/api/<segment>/<id>", methods=["PUT"])
def api_update_<atome>(...): ...

@bp.route("/api/<segment>/<id>", methods=["DELETE"])
def api_delete_<atome>(...): ...
```

Soit 15 fonctions, ~170 lignes au total.

### Après

Une seule fonction-fabrique :

```python
def _enregistrer_routes_atome(bp, type_atome, segment_url,
                              creer, modifier, supprimer,
                              nom_lire, nom_ecrire,
                              message_non_trouve):
    # Génère les 5 routes (GET liste, GET unitaire, POST, PATCH, DELETE)
    ...
```

Et 3 appels :

```python
_enregistrer_routes_atome(bp, type_atome='notion', segment_url='notions',
                          creer=svc.creer_notion, ...)
_enregistrer_routes_atome(bp, type_atome='methode', segment_url='methodes', ...)
_enregistrer_routes_atome(bp, type_atome='exercice', segment_url='exercices', ...)
```

Soit ~30 lignes de config + ~100 lignes de fabrique = ~130 lignes pour
les mêmes 15 routes. Surtout : **0 duplication** entre les types.

Les fonctions Flask sont générées via `add_url_rule(... view_func=...)`
plutôt que `@bp.route` décorateur, parce qu'on les définit dans une
boucle. Les noms `__name__` sont posés explicitement pour que les
endpoints Flask gardent des noms uniques (`api_get_notions`,
`api_get_methodes`, etc., comme avant).

## Fichiers livrés

```
appli/routes/atomes.py                        [MOD]   factorisation + PATCH
appli/routes/cartes_automatisme.py            [MOD]   commentaire mis à jour
appli/routes/fiches_resume.py                 [MOD]   PUT → PATCH
appli/static/atelier_editeur.js               [MOD]   défaut: PATCH
appli/static/atelier_carte_automatisme.js     [MOD]   retrait methodeUpdate
appli/tests/test_routes.py                    [MOD]   put → patch
appli/tests/test_v0_10_4_etats_edition.py     [MOD]   put → patch
appli/tests/test_v0_10_5_fiches_resume.py     [MOD]   2× put → patch
appli/doc/redemarrage_v0_13_7_0e.md           [NEW]
```

Bilan en lignes (estimé) :
- `atomes.py` : 311 → 286 lignes (−25, et surtout +0 duplication)
- Autres fichiers : +/- quelques lignes (config carte allégée, commentaires)

## Vérifications

- **Suite pytest : 3238 passed, 5 skipped, 0 failed** (identique au baseline)
- Sanity Python sur les 3 fichiers `routes/` modifiés : OK
- Sanity JS sur les 2 fichiers JS modifiés : OK
- Audit refs : aucun PUT vers les routes atomes/cartes/fiches dans le
  frontend ni les tests

## À tester chez toi

### Scénario A — Sauvegarde directe (le bug v0.13.7.0d.1)

Pour les 5 ateliers (Exercice, Notion, Méthode, Fiche, Carte) :

1. Ouvrir un item existant.
2. Modifier un champ.
3. Cliquer le bouton « Enregistrer » dans la toolbar.
4. **Sauvegarde OK, toast confirmant, badge éteint, pas d'erreur 405 dans les logs.**

### Scénario B — Garde de sortie

Re-jouer les scénarios de v0.13.7.0d et v0.13.7.0d.1 :
- Changement d'item dans la sidebar avec modifs en cours → modale 3 boutons → tous les choix marchent.
- Changement d'atelier via menu du haut avec modifs en cours → idem.
- « Ne pas sauvegarder » → modifications visuellement perdues au retour dans l'atelier.

### Scénario C — Toujours pas de régression sur la création

Pour les 5 ateliers : créer un nouvel item via « + Nouveau / Nouvelle ».
La création utilise POST, **pas** PATCH. Doit toujours fonctionner.

### Diagnostic log si problème

Côté serveur : tu devrais voir maintenant des lignes du type
`PATCH /api/notions/<id> HTTP/1.1" 200` (et plus de `PUT`). Si tu vois
`PUT ... 405`, c'est qu'il reste un appel PUT qu'on a manqué (frontend
ou tests externes).

## Prochaines étapes (rappel)

- **Tests par toi en production** → si OK, on enchaîne sur l'éditeur LaTeX.
- **v0.13.7.0f (optionnelle)** : factorisation des sections notion/méthode
  dans `AtelierAtomique` (chantier prévu depuis v0.13.7.0b, repoussé
  trois fois). À traiter avant ou en parallèle de v0.13.7.1 ?
- **v0.13.7.1** : squelette éditeur LaTeX (cadrage acté).

Mon avis : la factorisation des sections devient de moins en moins
prioritaire au fur et à mesure que la pile bouge. On peut très bien
attaquer directement l'éditeur LaTeX en v0.13.7.1 et faire la
factorisation sections plus tard (v0.14 ou ad-hoc). À discuter une
fois v0.13.7.0e validée.
