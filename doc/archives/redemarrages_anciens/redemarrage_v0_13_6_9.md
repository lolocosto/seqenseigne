# Redémarrage v0.13.6.9

**Session du 15 mai 2026 — Chantier A : homogénéisation des `placedTags`**

---

## Périmètre

Premier chantier de cohérence après la migration OO et la rationalisation
backend. Unifie le format d'affichage des tags d'objectifs liés dans
les sidebars des ateliers atomiques.

Cible : **notion, méthode, exercice, fiche**. La carte est laissée
telle quelle pour cette livraison (sera traitée au chantier C avec la
refonte de son modèle 1:1 vers objectif).

---

## Décisions actées

| Q | R |
|---|---|
| Format des tags | Local `obj 02`, hors séquence même niveau `S03 obj 02`, hors niveau `N11 S03 obj 02` |
| Périmètre carte | Hors périmètre, sera traitée au chantier C |
| Truncate | 3 tags max + indicateur `+N` |

---

## Format unifié

Trois cas selon la position de l'objectif lié relativement au filtre
courant (`window.ATL_FILTRE_NIVEAU` + `window.ATL_FILTRE_SEQ`) :

| Cas | Tag affiché |
|---|---|
| Objectif dans la séquence courante | `obj 02` |
| Hors séquence, même niveau | `S03 obj 02` |
| Hors niveau (autre cycle ou autre niveau) | `N11 S03 obj 02` |

Au-delà de 3 tags, on tronque et on ajoute `+N` (ex : `+2` pour
5 objectifs liés au total).

---

## Avant / Après

### Notion / Méthode / Exercice

```
Avant :  02           (local)
         N10·S03·02   (hors)

Après :  obj 02       (local)
         S03 obj 02   (hors séq, même niveau)
         N11 S03 obj 02 (hors niveau)
```

### Fiche

```
Avant :  obj 02       (toujours ce format, ne distinguait pas
                       les cas local/hors)

Après :  obj 02       (local — identique mais ce n'est plus un
                       formatage spécifique fiche, c'est l'API
                       commune)
```

Conséquence : visuellement, le seul changement perceptible pour la
fiche est que **si** un jour une fiche est créée pointant vers un
objectif dans une autre séquence (cas non standard), le tag se met
à inclure `S03 obj 02`. En pratique, les fiches sont toujours dans
la même séquence que leur objectif, donc le comportement reste
identique.

---

## Architecture

### Fichier nouveau : `static/atelier_obj_tags.js`

Redéfinit `window.atelObjLiesEnTags(obj_lies, niveau, sequence)` avec
la nouvelle logique. Expose aussi un helper `window.atelObjLienEnTag`
pour formater un lien unique (utilisé en interne, exposé au cas où).

### Chargement

Ajouté dans `index.html` **juste après** `app.js` :

```html
<script src="/static/app.js"></script>
<!-- v0.13.6.9 chantier A -->
<script src="/static/atelier_obj_tags.js"></script>
```

Pattern « monkey-patch » : `app.js` continue de définir l'ancienne
version de `atelObjLiesEnTags`, mais le nouveau fichier l'écrase
immédiatement après. La dernière définition gagne. Ainsi je n'ai
pas eu à toucher au gros `app.js` (6500+ lignes).

C'est aussi le pattern qu'on a utilisé pendant les migrations OO :
les classes `Atelier*` cohabitent avec l'ancien code dans `app.js`,
et c'est la version chargée en dernier qui est utilisée.

### Modification dans `AtelierFiche.rendreItem`

La fiche construisait avant son placedTag à la main :

```js
const placedTags = f.objectif_code ? [`obj ${f.objectif_code}`] : [];
```

Refactorisé pour utiliser l'API commune :

```js
const obj_lies = f.objectif_code
  ? [`${f.niveau || ''}·${f.sequence || ''}·${f.objectif_code}`]
  : [];
const placedTags = window.atelObjLiesEnTags
  ? window.atelObjLiesEnTags(obj_lies, f.niveau, f.sequence)
  : (f.objectif_code ? [`obj ${f.objectif_code}`] : []);
```

Le fallback (`?:` final) est défensif : si pour une raison X le
fichier `atelier_obj_tags.js` n'est pas chargé, on retombe sur
l'ancien comportement.

### Pas de modification backend

Volontairement. L'`obj_lies` côté notion/méthode/exercice est déjà
au bon format (`N10·S03·02`) depuis `services/liaisons_atomes.py`.
Pour la fiche, on synthétise côté JS à partir de
`f.niveau`/`f.sequence`/`f.objectif_code` (3 champs déjà présents
dans la requête `lister_fiches_resume`). Risque de régression
backend = zéro.

---

## Validation chez toi

### Test 1 — Atelier notion / méthode / exercice
Ouvrir un atelier, filtrer sur une séquence (N10/S03 par exemple).
1. Un atome lié à un objectif **de la séquence courante** doit
   afficher `obj 02` (et pas juste `02`)
2. Un atome lié à un objectif d'une **autre séquence du même niveau**
   doit afficher `S05 obj 01` (et pas `N10·S05·01`)
3. Un exercice de révision lié à un objectif d'**un autre niveau**
   (par exemple un exo N11 qui révise une notion N10) doit afficher
   `N10 S05 obj 02`
4. Un atome lié à 5 objectifs doit afficher 3 tags + `+2`

### Test 2 — Atelier fiche
Le comportement reste identique en pratique (fiche toujours dans
la même séquence que son objectif → tag `obj 02`).

### Test 3 — Atelier carte
Inchangé. Affiche toujours `n NN` / `m MM` selon le lien
notion/méthode. Sera traité au chantier C.

### Test 4 — Régression
Le filtre par état (Tous / En cours / Validé) doit toujours marcher
sur tous les ateliers. La multi-sélection aussi.

---

## Fichiers livrés

| Fichier | Statut |
|---|---|
| `appli/static/atelier_obj_tags.js` | **nouveau** |
| `appli/static/atelier_fiche.js` | modifié (placedTags via API commune) |
| `appli/templates/index.html` | modifié (1 ligne `<script>` ajoutée) |

Décompresser à la racine de `seqenseigne/`. F5.

---

## Bénéfices acquis

1. **Affichage uniforme** sur les 4 ateliers atomiques migrés
2. **Préfixe `obj`** systématique : plus lisible qu'un code isolé
   « 02 » qui ne signifiait rien d'évident
3. **Séparateur espace** plutôt que `·` : tags plus lisibles
4. **Code de formatage centralisé** dans un seul fichier (28 lignes
   sans compter les commentaires) — facile à maintenir et étendre
5. **`AtelierFiche`** ne fait plus sa popote spécifique pour
   construire ses tags ; il utilise l'API commune

---

## Suite

Roadmap inchangée :
- **v0.13.6.10** : chantier B — bouton « reprendre titre objectif »
  (depuis AtelierEditeur si lien 1:1)
- **v0.13.6.11+** : chantier C — refonte modèle carte (1:1 strict
  vers objectif, et homogénéisation des tags carte à ce moment)
- **v0.13.6.12+** : chantier D — suppression sélecteur objectif fiche
- **v0.13.7+** : chantier F — fusion zones/sections + description
  configurable
- **v0.14** : nettoyage wrappers dépréciés `valider_carte`/`devalider_carte`
  + adaptation des 4 fichiers concernés
