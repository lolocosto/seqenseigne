# Patch v0.10.7

**2 mai 2026**

Cette version livre 4 changements fonctionnels et une grosse mise à
jour documentaire. Aucune migration de schéma SQL n'est nécessaire.

## Résumé

| Item | Type |
|---|---|
| Wrap automatique sur toutes les zones de saisie | UI |
| Suppression de la zone « Objectifs associés » dans l'atelier Exercice | UI + backend |
| Badges des objectifs liés dans la sidebar des ateliers Exercice / Notion / Méthode | UI |
| Règles métier sur les liaisons notion ↔ obj et méthode ↔ obj (scope séquence + cardinalité 1-1) | backend |
| Script CLI de diagnostic des atomes orphelins | outil |
| Documentation : 4 nouveaux documents `.md` (CDC, doc technique, usecases, redémarrage) | doc |

---

## 1. Wrap automatique sur les zones de saisie

**Avant** : les zones d'édition LaTeX (énoncés, corrigés, items de
section, critères) ne wrappaient pas les longues lignes —
apparition d'un scroll horizontal dès qu'un texte dépassait la
largeur de la zone.

**Après** : toutes les zones avec la classe `.latex-textarea`
wrappent automatiquement (`white-space: pre-wrap`,
`overflow-wrap: anywhere`). Les retours à la ligne explicites sont
préservés ; les lignes très longues sont cassées visuellement sans
modifier la valeur stockée (donc le LaTeX généré reste identique).

Diff CSS (`static/app.css`) :

```css
- white-space: pre;
+ white-space: pre-wrap;
+ overflow-wrap: anywhere;
+ word-wrap: break-word;
```

## 2. Suppression de la zone « Objectifs associés » exo

**Justification** : la zone faisait doublon avec le drop d'exercices
dans l'atelier d'assemblage. Elle écrivait dans la table legacy
`exercice_objectifs`, qui n'est plus consommée par la chaîne de
rendu (depuis le passage au modèle v2 et `objectif_exos`).

**Avant** : un sélecteur dans l'atelier Exercice permettait
d'attacher un exo à des « objectifs legacy » (un par méthode).
Ces liaisons étaient stockées dans `exercice_objectifs` mais
n'étaient utilisées par aucune fonctionnalité active.

**Après** :

- Bloc HTML retiré (`atl-exo-field-obj`).
- Variables JS retirées (`ATL_EXO_OBJS`).
- Fonctions retirées (`atelExoObjAjouter`, `atelExoObjRetirer`,
  `atelExoRenderObjTags`).
- Champ `objectifs` retiré du payload `POST /api/exercices` et
  `PUT /api/exercices/<id>`. Les valeurs envoyées sont silencieusement
  ignorées ; le champ est forcé à `[]` en BDD.
- Ligne `obj=…` retirée du LaTeX généré dans la prévisualisation exo.

**Conservé** :

- La table `exercice_objectifs` est conservée pour rétrocompatibilité
  (peuplée par le scanner d'import). Suppression définitive prévue en
  v0.14.
- Le champ `objectifs` reste exposé en lecture (`GET /api/exercices`)
  pour ne pas casser les tests existants.

## 3. Badges des objectifs liés dans la sidebar

**Nouveau** : chaque atome (notion, méthode, exercice) affiche dans
la sidebar des ateliers la liste des objectifs auxquels il est lié,
sous forme de chips compactes en dessous du titre.

**Format** :

- **Lien local** (obj dans la séquence courante) : `02` (chip neutre).
- **Lien externe** (obj dans une autre séquence) : `N10·S04·02` (chip
  pâle, italique).
- Au-delà de 3 chips : suffixe `+N` indiquant le nombre restant.

**Cas d'usage le plus utile** : pour les exercices, voir
immédiatement où un exo est utilisé (y compris en révision dans une
autre séquence ou un autre niveau).

**Implémentation** :

- Module `services/liaisons_atomes.py` (nouveau) : 3 fonctions de
  calcul + helper `enrichir_liste_atomes(conn, liste, type_atome)`.
- Routes `GET /api/notions`, `GET /api/methodes`, `GET /api/exercices`
  ajoutent le champ `obj_lies: ["N10·S04·02", ...]` à chaque atome.
- Helper JS `atelObjLiesBadgesHtml(obj_lies, niv, seq)` dans `app.js`
  pour le rendu des chips.
- Classes CSS dédiées : `.atl-item-objs`, `.atl-item-objchip`,
  `.atl-item-objchip--ext`, `.atl-item-objchip-more`.

## 4. Règles métier (backend)

### 4.1 Scope séquence sur notions et méthodes

**Avant** : aucune validation. Une notion N11/S03 pouvait être liée
à un objectif de N10/S05 silencieusement.

**Après** :

- Une notion ne peut être liée qu'à un objectif **de sa séquence
  d'origine** (champs `niveau` et `sequence`).
- Idem pour les méthodes.
- Tolérance legacy : si l'atome n'a pas de scope renseigné (champs
  vides), la liaison est autorisée — fallback pour les données
  historiques.

**Erreurs** :

- `NotionHorsSequence` (HTTP 409) lors d'un `POST
  /api/v2/objectifs/<id>/notions` hors scope.
- `MethodeHorsSequence` (HTTP 409) lors d'un `PATCH
  /api/v2/objectifs/<id>/methode` hors scope.

### 4.2 Cardinalité 1-1 méthode → objectif

**Avant** : une méthode pouvait être liée silencieusement à
plusieurs objectifs (chaque attache écrasait l'objectif précédent
sans erreur, mais comme `methode_id` est une colonne directe sur
`objectifs_v2`, plusieurs objectifs pouvaient finir par référencer
la même méthode).

**Après** : tentative de lier une méthode déjà attachée à un autre
objectif → erreur `MethodeDejaLiee` (HTTP 409). L'utilisateur doit
détacher d'abord.

L'idempotence est préservée : réattacher la même méthode au même
objectif est un no-op silencieux.

### 4.3 Héritage du scope à la création

À la création d'une notion ou méthode dans l'UI, les champs
`niveau` et `sequence` sont automatiquement renseignés depuis le
contexte courant (`ATL_FILTRE_NIVEAU` / `ATL_FILTRE_SEQ`). À la
modification d'un atome legacy sans scope, le scope courant est
appliqué pour faciliter la régularisation.

## 5. Script CLI `lister_atomes_orphelins.py`

**Nouveau** : `scripts/lister_atomes_orphelins.py` qui détecte les
notions et méthodes potentiellement orphelines :

- **SANS_SCOPE** : pas de `(niveau, sequence)` posés.
- **SANS_LIEN** : aucune liaison vers un objectif_v2.

Usage :

```bash
python3 -m scripts.lister_atomes_orphelins --db data/seqenseigne.db
```

Sortie : tableau texte aligné, séparé en sections « Notions
orphelines » et « Méthodes orphelines », avec un résumé.

Cible : à intégrer dans l'UI admin en v0.14.

## 6. Documentation

4 nouveaux documents `.md` en français, qui consolident l'état du
projet à la v0.10.7 :

- `doc/seqenseigne_cdc_v0_10_7.md` — Cahier des charges complet :
  vision, périmètre fonctionnel, règles métier, décisions
  structurantes, hors-scope, glossaire.
- `doc/seqenseigne_doc_technique_v0_10_7.md` — Conception technique :
  architecture, schéma BDD, modules, API REST, chaîne de rendu,
  persistance, tests.
- `doc/seqenseigne_usecases_v0_10_7.md` — Cas d'usage utilisateur :
  parcours scénario par scénario, pièges et résolutions.
- `doc/redemarrage_v0_10_7.md` — Note de redémarrage compacte pour
  reprise du développement.

---

## Tests

**Avant** : 1656 passants + 4 skipped.

**Après** : **1687 passants** + 4 skipped.

Nouveaux tests :

- `tests/test_v0_10_7_regles_metier.py` — 17 tests : scope notion,
  scope méthode, cardinalité 1-1, héritage, exo objectifs ignoré.
- `tests/test_v0_10_7_badges_et_orphelins.py` — 12 tests : calcul des
  obj_lies (notion/méthode/exo), enrichissement de liste, script CLI.

Tests adaptés (changement de comportement attendu) :

- `tests/test_R4e3_edition_objectif.py` — 5 tests sur
  `modifier_methode_objectif` adaptés à la nouvelle cardinalité 1-1
  et au scope.

## Fichiers modifiés ou créés

```
static/app.css                          ← wrap pre-wrap + chips obj_lies
static/app.js                           ← retraits ATL_EXO_OBJS,
                                          payload notion/méthode envoie
                                          niveau/sequence,
                                          atelObjLiesBadgesHtml +
                                          ajouts dans atelRender*
templates/index.html                    ← bloc atl-exo-field-obj retiré
services/v2_edition.py                  ← 3 erreurs ajoutées,
                                          _lire_niv_seq_objectif,
                                          modifier_methode_objectif
                                          (scope+1-1),
                                          ajouter_notion_objectif (scope)
services/atomes.py                      ← creer_exercice/modifier_exercice
                                          sans objectifs ;
                                          creer_notion/methode/modifier_*
                                          acceptent niveau/sequence
services/liaisons_atomes.py             ← NEW (calc obj_lies)
routes/atomes.py                        ← helper _enrichir,
                                          GET notions/methodes/exercices
                                          enrichis
routes/v2_edition.py                    ← codes HTTP 409 ajoutés
                                          (notion_hors_sequence,
                                          methode_hors_sequence,
                                          methode_deja_liee)
scripts/lister_atomes_orphelins.py      ← NEW
tests/test_R4e3_edition_objectif.py     ← 5 tests adaptés
tests/test_v0_10_7_regles_metier.py     ← NEW 17 tests
tests/test_v0_10_7_badges_et_orphelins.py ← NEW 12 tests
doc/redemarrage_v0_10_7.md              ← NEW
doc/seqenseigne_cdc_v0_10_7.md          ← NEW
doc/seqenseigne_doc_technique_v0_10_7.md ← NEW
doc/seqenseigne_usecases_v0_10_7.md     ← NEW
doc/patch_v0_10_7.md                    ← ce document
```

## Migration recommandée

1. Sauvegarder `data/seqenseigne.db` avant déploiement.
2. Déployer le patch (remplacer le contenu de `appli/`).
3. Lancer la suite de tests : `python3 -m pytest tests/ -q`.
4. Démarrer l'application et vérifier visuellement :
   - Le wrap des zones de saisie fonctionne.
   - La zone « Objectifs associés » a disparu de l'atelier Exercice.
   - Les badges `obj_lies` apparaissent dans les sidebars.
5. Optionnellement, exécuter le diagnostic des orphelins :
   `python3 -m scripts.lister_atomes_orphelins`.
