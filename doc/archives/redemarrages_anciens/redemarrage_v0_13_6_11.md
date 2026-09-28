# Redémarrage v0.13.6.11

**Session du 15 mai 2026 — Chantier B : bouton « reprendre titre objectif »**

---

## Motivation

Les objectifs sont nommés avec des libellés pédagogiques officiels
(« Pour les nombres décimaux, passer de l'écriture décimale à
l'écriture fractionnaire et inversement. »). Quand tu crées une notion,
une méthode, un exercice ou une fiche lié à un objectif, tu peux
vouloir reprendre ce libellé comme titre de l'atome (cas typique pour
une méthode : son titre EST l'énoncé de l'objectif).

Avant v0.13.6.11 : il fallait soit retaper le titre, soit copier-coller
manuellement depuis le sélecteur d'objectif (quand il est visible).

Maintenant : un bouton inline à côté du champ titre, conditionné à la
cardinalité 1:1 obj, propose la reprise en un clic.

---

## Décisions actées

| Q | R |
|---|---|
| Périmètre | Tous les ateliers atomiques (notion, méthode, exercice, fiche) si l'atome a exactement 1 lien obj. Carte hors périmètre (chantier C). |
| Que reprend le bouton | Le `nom` de l'objectif (champ `o.nom`) |
| Emplacement | Bouton inline à côté du champ titre, label « ⤵ reprendre titre objectif » |
| Si titre déjà rempli | `confirm()` avant d'écraser |

---

## Comportement détaillé

### Conditions d'affichage du bouton

Le bouton est **visible** seulement si :
- L'item actif a **exactement 1** lien de `type='obj'` dans `liens`
- L'objectif a un `nom` non vide

Sinon, le bouton est masqué (`display: none`) — le DOM est créé une
fois mais reste invisible.

### Action au clic

1. Si la cardinalité n'est plus 1:1 obj (sécurité défensive) → ne fait rien
2. Si l'objectif n'a pas de nom → toast d'erreur
3. Si le champ titre est **vide** ou égal au nom → injecte directement
4. Si le champ titre est **rempli** avec autre chose → `confirm()` avec
   les 2 valeurs côte à côte, puis injecte si confirmé

Après injection : le flag `modifie` est mis à true, l'événement
`input` est dispatché pour propager le changement aux listeners
(toolbar, garde-sortie, etc.).

---

## Architecture technique

### Backend — `services/liaisons_atomes.py`

**Extension non-breaking** du format `liens` pour les liens
`type='obj'` : ajout du champ `nom`.

```python
def _lien_obj(niveau: str, sequence: str, code: str, nom: str = "") -> dict:
    return {
        "type":     "obj",
        "niveau":   niveau,
        "sequence": sequence,
        "code":     code,
        "nom":      nom,       # ← NOUVEAU
    }
```

Les 4 fonctions `lister_liens_par_*` ajoutent `ob.nom AS nom` dans
leur SELECT et propagent à `_lien_obj`. La valeur fallback est `''`
si `ob.nom IS NULL`.

Les liens `type='part'` ne changent pas (un lien partie n'a pas de
notion de « nom de l'objectif »).

### Frontend — `AtelierEditeur`

Trois nouvelles méthodes dans la classe parente :

**`_reprendreObjectifDispo()`** — Helper de calcul de disponibilité.
Retourne :
- Le `nom` (string) si l'item actif a exactement 1 lien obj
- `null` sinon (0 liens, >1 liens, pas d'item actif)

**`reprendreLibelleObjectif(idChampTitre)`** — Action déclenchée par
le bouton. Gère le confirm si titre rempli.

**`_injecterBoutonReprendreTitre(idChampTitre)`** — Injecte ou
rafraîchit le bouton dans le DOM, à côté du champ titre indiqué.

### Frontend — Les 4 ateliers

Chaque atelier appelle `this._injecterBoutonReprendreTitre('...')` à la
fin de son `remplirFormulaire()` :

| Atelier | ID du champ titre | Sémantique |
|---|---|---|
| Notion | `atl-notion-titre` | titre |
| Méthode | `atl-methode-titre` | titre |
| Exercice | `atl-exo-nom` | nom (= titre en fait) |
| Fiche | `atl-fiche-titre` | titre |

L'exercice a un id `atl-exo-nom` (sémantique titre, id legacy).

### Pas de modification d'index.html

Le bouton est créé **dynamiquement en JS** dans
`_injecterBoutonReprendreTitre()`. Pas de retouche du HTML
statique. Le bouton apparaît/disparaît selon la disponibilité du
lien 1:1 obj de l'item actif.

---

## Tests

### Tests adaptés

Les assertions exactes sur les dicts `liens` ont été enrichies pour
inclure `nom`. Exemple :

```python
# Avant
assert l == {'type': 'obj', 'niveau': 'N11', 'sequence': 'S03', 'code': '02'}

# Après
assert l == {'type': 'obj', 'niveau': 'N11', 'sequence': 'S03',
             'code': '02', 'nom': 'Calculer A'}
```

### 3 nouveaux tests : `TestCardinaliteUnObjAvecNom`

- `test_methode_a_un_seul_obj_avec_nom` : cas typique 1:1 avec nom
- `test_notion_a_plusieurs_obj_pas_de_reprise` : cas où `len > 1` (le
  frontend détectera et ne proposera pas)
- `test_nom_chaine_vide_si_obj_sans_libelle` : robustesse aux objectifs
  sans nom (NULL en base → '' côté API)

### Résultat suite complète

- **2475 passed, 5 skipped** (+3 nouveaux tests vs v0.13.6.10)
- **0 régression**

---

## Validation chez toi

### Test 1 — Méthode (cas standard)

1. Atelier méthodes, ouvrir une méthode existante avec un objectif lié
2. Bouton « ⤵ reprendre titre objectif » visible à côté du champ titre
3. Cliquer dessus
4. Si titre vide → injecté direct
5. Si titre rempli différent → confirm
6. Vérifier que la sauvegarde marche

### Test 2 — Notion (cas variable)

1. Atelier notions, ouvrir une notion avec exactement 1 objectif lié
2. Bouton visible
3. Ouvrir une notion sans objectif lié
4. Bouton invisible

### Test 3 — Exercice

1. Atelier exercices, ouvrir un exo avec 1 objectif lié
2. Bouton visible, fonctionnel

### Test 4 — Fiche

1. Atelier fiches, ouvrir une fiche
2. Bouton visible (toutes les fiches ont 1:1 par construction)
3. Reprendre le titre = matérialise le fallback dérivé du
   `objectif_nom` qui apparaissait jusqu'ici en italique « (sans
   titre) ».

### Test 5 — Régression

`pytest tests/` chez toi doit afficher **3232 passed, 5 skipped**
(+3 par rapport à v0.13.6.10).

---

## Fichiers livrés

| Fichier | Statut |
|---|---|
| `appli/services/liaisons_atomes.py` | extension non-breaking (+`nom`) |
| `appli/static/atelier_editeur.js` | +3 méthodes (chantier B) |
| `appli/static/atelier_notion.js` | +1 ligne (injection bouton) |
| `appli/static/atelier_methode.js` | +1 ligne |
| `appli/static/atelier_exercice.js` | +1 ligne |
| `appli/static/atelier_fiche.js` | +1 ligne |
| `appli/tests/test_v0_10_7_badges_et_orphelins.py` | adapté + 3 nouveaux tests |

Décompresser à la racine de `seqenseigne/`. F5.

---

## Bénéfices acquis

1. **Workflow plus fluide** pour créer/modifier des atomes 1:1 vers
   un objectif : le libellé pédagogique officiel est repris en un clic
2. **API extensible** : le champ `nom` rejoint `liens` sans casser le
   reste de l'API. Si demain on ajoute `description` ou `prerequis`,
   même approche
3. **Conservation du contrôle utilisateur** : `confirm()` si écrasement
   d'un titre existant. Aucune action silencieuse destructive

---

## Suite

Roadmap mise à jour :
- **v0.13.6.12+** : chantier C — refonte modèle carte (1:1 strict
  vers objectif, et homogénéisation des tags carte). À ce moment-là,
  la carte pourra aussi bénéficier du bouton « reprendre titre objectif »
  une fois sa cardinalité fixée à 1:1.
- **v0.13.6.13+** : chantier D — suppression sélecteur objectif fiche
- **v0.13.7+** : chantier F — sections configurables
- **v0.14** : nettoyage wrappers dépréciés `valider_carte`/`devalider_carte`
