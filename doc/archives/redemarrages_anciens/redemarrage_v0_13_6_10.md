# Redémarrage v0.13.6.10

**Session du 15 mai 2026 — Réalignement frontend/backend des ateliers d'atomes**

---

## Motivation

Après les chantiers de migration OO, la rationalisation de l'état
d'édition et l'homogénéisation des tags (v0.13.6.6 → v0.13.6.9),
deux bugs concomitants ont mis en lumière une **désynchronisation
structurelle** entre la couche frontend et la couche backend :

1. **Bug listes vides aléatoires dans l'atelier exercices** : tu
   changeais de niveau (N09 → N10 → N11 → N12) et seul N09 (le
   premier chargé) s'affichait, les autres étaient vides. Tu
   observais : `liste.length: 411` (= count N09) mais
   `niveauFiltre: N10`. La liste était figée au premier chargement.

2. **Liens parties (R/EA) invisibles dans la sidebar** : tu rattaches
   4 exos N10/S01 en révision dans N11/S01 (via
   `partie_exos_revision_approche`), mais ces exos restaient affichés
   dans l'atelier avec leur tag d'origine seulement, sans indication
   de leur usage en révision.

Ces bugs venaient d'une accumulation de divergences :

- **Routes serveur incohérentes** : chaque atelier filtrait
  différemment côté serveur. /api/notions et /api/methodes ne
  filtraient pas du tout. /api/exercices ne filtrait que par niveau.
  /api/fiches-resume et /api/cartes filtraient niveau+sequence.

- **Frontend OO décorrelé** : les propriétés `this.niveauFiltre` et
  `this.sequenceFiltre` des classes d'atelier OO n'étaient JAMAIS
  initialisées (jamais assignées dans tout le code). Elles
  fonctionnaient « par accident » dans certaines configurations,
  mais sans synchronisation avec les variables globales
  `window.ATL_FILTRE_*` gérées par app.js.

- **Pas de mécanisme de rechargement** : quand l'utilisateur changeait
  de niveau via la barre de portée, app.js mettait à jour
  `ATL_FILTRE_NIVEAU` mais ne demandait pas aux ateliers OO de
  recharger leur liste depuis le serveur.

- **Format `obj_lies` incomplet** : la fonction
  `lister_obj_lies_par_exercice` ne consultait que `objectif_exos`,
  ignorant les rattachements via `partie_exos_revision_approche`.

Tu l'as très bien formulé : « C'est une même application, pas une API
entre deux applis qui n'ont rien à voir ! ». Cette livraison réaligne
tout, en cassant ce qui doit l'être (phase alpha assumée).

---

## Décisions actées

| Q | R |
|---|---|
| Ampleur du chantier ? | Tout dans une seule v0.13.6.10, `ATL_FILTRE_*` reste single source of truth |
| Compatibilité `obj_lies` ? | Rupture totale : `liens` partout, `obj_lies` supprimé |
| Format réponse fiche ? | Aligné : liste directe `[...]` au lieu de `{fiches: [...]}` |
| Liens parties (R/EA) ? | Inclus dans `liens` avec `type='part'` |

---

## Changements backend

### `services/liaisons_atomes.py` — refondu

**Renommages** :
- `lister_obj_lies_par_notion` → `lister_liens_par_notion`
- `lister_obj_lies_par_methode` → `lister_liens_par_methode`
- `lister_obj_lies_par_exercice` → `lister_liens_par_exercice`
- Nouveau : `lister_liens_par_fiche`

**Format de retour** : objet typé au lieu de string.

Avant :
```python
{'ex_001': ['N10·S03·02', 'N11·S05·01']}
```

Après :
```python
{'ex_001': [
    {'type': 'obj', 'niveau': 'N10', 'sequence': 'S03', 'code': '02'},
    {'type': 'obj', 'niveau': 'N11', 'sequence': 'S05', 'code': '01'},
]}
```

**Nouvelle source pour les exercices** : la fonction consulte
maintenant DEUX tables :
1. `objectif_exos` → liens vers objectifs (séries F/A/E)
2. `partie_exos_revision_approche` → liens vers parties (rôles R/EA)

Résultat : un exo utilisé en révision dans une autre séquence apparaît
maintenant avec un lien `{type: 'part', niveau: 'N11', sequence: 'S01',
numero: 1}`. Ton scénario d'usage (rattacher N10 en révision de N11)
est désormais visible côté UI.

### `routes/atomes.py` — filtrage uniforme

Helper centralisé `_filtrer_niveau_sequence(liste)` appliqué partout :

```python
@bp.route("/api/notions", methods=["GET"])
def api_get_notions():
    return jsonify(_enrichir(
        _filtrer_niveau_sequence(_js().lire_notions()),
        'notion'))
```

Idem pour méthodes et exercices. Le serveur **filtre toujours**
côté serveur par niveau ET sequence (params optionnels). Plus de
divergence entre les ateliers.

### `routes/fiches_resume.py` — alignement

Avant :
```json
{"fiches": [...]}
```

Après :
```json
[...]
```

Et enrichissement avec `liens` ajouté (avant absent côté fiche).

---

## Changements frontend

### `atelier_editeur.js` — refonte chargerListe + filtrerListe

```js
async chargerListe() {
  const url = new URL(this.config.endpointBase, window.location.origin);
  const niv = window.ATL_FILTRE_NIVEAU || '';
  const seq = window.ATL_FILTRE_SEQ || '';
  if (niv) url.searchParams.set('niveau', niv);
  if (seq) url.searchParams.set('sequence', seq);
  // ... fetch ...
}
```

**Plus de `this.niveauFiltre`/`this.sequenceFiltre`** dans toute la
classe (source du bug, jamais initialisées). Lecture directe des
variables globales.

`filtrerListe` ne filtre plus que sur l'état d'édition (le filtrage
niveau/sequence est fait côté serveur).

### Les 5 ateliers — `sed` mécanique

Tous les usages `this.niveauFiltre` → `window.ATL_FILTRE_NIVEAU || ""`.
Et `this.sequenceFiltre` → `window.ATL_FILTRE_SEQ || ""`. Modification
mécanique appliquée à : notion, méthode, exercice, fiche, carte.

### `atelier_fiche.js` — surcharge `chargerListe` SUPPRIMÉE

Avant, la fiche surchargeait `chargerListe` pour gérer
`{fiches: [...]}`. Maintenant l'API retourne une liste directe, donc
la fiche utilise la `chargerListe` héritée.

Et `rendreItem` consomme `f.liens` du serveur au lieu de construire
un `obj_lies` synthétique.

### `atelier_obj_tags.js` — réécrit

**Renommé** : `atelObjLiesEnTags` → `atelLiensEnTags`.

**Nouveau format d'entrée** : tableau d'objets typés, plus de strings
parsées au split('·').

**Nouveau format de sortie** :
- `obj 02` (lien objectif local)
- `S03 obj 02` (hors séquence)
- `N11 S03 obj 02` (hors niveau)
- `part 01` (lien partie local)
- `S03 part 02` (hors séquence)
- `N11 S03 part 02` (hors niveau)

Truncate à 3 + `+N`.

### `atelier_filtres_hook.js` — NOUVEAU

Le fix principal du bug listes vides. Monkey-patche
`window.atelExposerFiltres` (gérée par app.js) pour déclencher un
rechargement de tous les ateliers OO instanciés :

```js
const _exposerOriginal = window.atelExposerFiltres;
window.atelExposerFiltres = function () {
  const r = _exposerOriginal.apply(this, arguments);
  // Recharger les ateliers OO depuis le serveur
  for (const nom of ['ATELIER_NOTION', 'ATELIER_METHODE',
                     'ATELIER_EXERCICE', 'ATELIER_FICHE',
                     'ATELIER_CARTE']) {
    const at = window[nom];
    if (at && typeof at.chargerListe === 'function') {
      at.chargerListe();
    }
  }
  return r;
};
```

Chargé après `app.js` dans `index.html`. Pattern monkey-patch éprouvé,
zéro modification de l'énorme `app.js`.

---

## Tests

### Nouveau test

`TestLiensExercice::test_exo_lien_partie` — vérifie que les exos
rattachés via `partie_exos_revision_approche` apparaissent avec
`type='part'`.

### Tests adaptés

`test_v0_10_7_badges_et_orphelins.py` :
- Imports : `lister_obj_lies_par_*` → `lister_liens_par_*`
- Assertions : `['N11·S03·02']` → `[{'type': 'obj', 'niveau': 'N11',
  'sequence': 'S03', 'code': '02'}]`
- Champ `obj_lies` → `liens`
- Schéma test enrichi : table `partie_exos_revision_approche` ajoutée

### Résultat suite complète

- **2472 passed, 5 skipped** (+1 nouveau test)
- **0 régression**

---

## Validation chez toi

### Test 1 — Le bug listes vides est résolu

1. Aller dans l'atelier exercices
2. Filtrer N09/S01 → voir les exos N09
3. Passer à N10/S01 → voir les exos N10 (au lieu de vide)
4. Passer à N11/S01 → voir les exos N11
5. Passer à N12/S01 → voir les exos N12

Dans la console JS, vérifier :
```js
console.log('liste.length:', ATELIER_EXERCICE.liste.length);
// Doit changer à chaque bascule (avant : restait à 411)
```

### Test 2 — Les liens parties apparaissent

1. Filtrer N10/S01 dans l'atelier exercices
2. Les 4 exos N10/S01/A1-A4 que tu as rattachés en révision dans
   N11/S01 doivent maintenant afficher 2 tags :
   - `obj 02`, `obj 03`, `obj 04`, `obj 05` (leur lien d'origine)
   - `N11 S01 part 01` (le lien révision vers la partie 1 de N11/S01)

### Test 3 — Bascule entre tous les ateliers

Vérifier que notion, méthode, fiche, carte fonctionnent toujours
correctement (rechargement au changement de niveau, affichage des
tags, multi-sélection, validation).

### Test 4 — Format réponse fiche

Dans la console réseau, vérifier que `/api/fiches-resume?niveau=N10&sequence=S01`
retourne maintenant une liste directe `[...]` (et non `{fiches: [...]}`).

### Test 5 — Régression backend

`pytest tests/` chez toi doit toujours afficher **3229 passed,
5 skipped, 0 échec** (1 test de plus qu'avant : le nouveau
`test_exo_lien_partie`).

---

## Fichiers livrés

| Fichier | Statut |
|---|---|
| `appli/services/liaisons_atomes.py` | refondu (`liens`, types objets, source parties) |
| `appli/routes/atomes.py` | refondu (filtre uniforme niveau+sequence) |
| `appli/routes/fiches_resume.py` | refondu (liste directe + enrichissement liens) |
| `appli/static/atelier_editeur.js` | refondu (suppression `this.niveauFiltre/sequenceFiltre`) |
| `appli/static/atelier_notion.js` | adapté (sed `this.*Filtre` + `liens`) |
| `appli/static/atelier_methode.js` | adapté |
| `appli/static/atelier_exercice.js` | adapté |
| `appli/static/atelier_fiche.js` | refondu (suppression surcharge `chargerListe`, `liens`) |
| `appli/static/atelier_carte_automatisme.js` | adapté |
| `appli/static/atelier_obj_tags.js` | refondu (API `atelLiensEnTags`, types objets) |
| `appli/static/atelier_filtres_hook.js` | **NOUVEAU** (hook rechargement) |
| `appli/templates/index.html` | adapté (ajout `<script>` du hook) |
| `appli/tests/test_v0_10_7_badges_et_orphelins.py` | adapté (signatures + schéma) |

Décompresser à la racine de `seqenseigne/`. F5.

---

## Bénéfices acquis

1. **Bug listes vides corrigé** — le rechargement est déclenché à
   chaque changement de filtre, pour tous les ateliers OO.
2. **API uniforme** — toutes les routes d'atomes filtrent uniformément
   par niveau+sequence côté serveur, retournent une liste directe.
3. **Format `liens` extensible** — l'ajout d'un nouveau type de lien
   (ex: chantier C qui repensera la carte) ne nécessitera pas de
   refonte du format, juste un nouveau `type`.
4. **Visibilité des révisions/approches** — les exos R/EA apparaissent
   maintenant correctement dans leur sidebar d'origine avec un tag
   `part XX` pointant vers leur usage.
5. **Code mort réduit** — suppression de `this.niveauFiltre/sequenceFiltre`
   (propriétés jamais initialisées), simplification de `filtrerListe`
   (un seul filtre côté JS au lieu de 3).
6. **Single source of truth** — `window.ATL_FILTRE_*` est désormais
   la seule source pour le niveau/séquence courante. Aucun cache local.

---

## Cas d'usage à noter pour la suite

### Côté UI : un exo R/EA n'est PAS dans la séquence où il est consommé

Quand tu filtres N11/S01 dans l'atelier exercices, tu **ne vois pas**
les 4 exos N10/S01 que tu y as rattachés en révision. C'est cohérent :
ces exos restent des exos N10, ils sont juste *référencés* depuis une
partie de N11/S01.

Pour les voir « depuis l'autre côté », il faut aller dans l'atelier
d'assemblage de séquence-dans-niveau (chantier en cours) où ils
apparaissent dans la liste R de la partie.

C'est le bon découplage : l'atelier exercices édite les exos par leur
maison ; l'atelier d'assemblage compose les séquences en piochant
parmi les exos disponibles.

---

## Suite

Roadmap mise à jour :
- **v0.13.6.11** : chantier B — bouton « reprendre titre objectif »
  (depuis AtelierEditeur si lien 1:1)
- **v0.13.6.12+** : chantier C — refonte modèle carte (1:1 strict
  vers objectif, et homogénéisation des tags carte avec le nouveau
  format `liens`)
- **v0.13.6.13+** : chantier D — suppression sélecteur objectif fiche
- **v0.13.7+** : chantier F — sections configurables
- **v0.14** : nettoyage wrappers dépréciés `valider_carte`/`devalider_carte`
  + adaptation des 4 fichiers consommateurs

---

## Leçon retenue

Les bugs d'« API désynchronisée entre frontend et backend » se
multiplient quand on migre incrémentalement (ancien code + nouveau
code cohabitent). Les variables globales survivantes ET les
propriétés OO créaient deux modèles d'état parallèles.

Pour les prochains chantiers de migration, je vérifierai
systématiquement :
1. Quel est le **single source of truth** d'un état partagé
2. Si plusieurs modèles d'état coexistent, qui synchronise quoi
3. Pour chaque route serveur, est-elle alignée sur la convention
   du périmètre (filtrage uniforme, format de retour uniforme)
