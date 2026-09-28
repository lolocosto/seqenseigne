# Redémarrage v0.13.6.7.3

**Session du 15 mai 2026 — Migration méthode**

---

## Périmètre

Migration de l'atelier Méthode vers la hiérarchie OO. Strictement
parallèle à la migration notion (v0.13.6.7) : la méthode partage le
même modèle que la notion (sidebar plate, formulaire titre + corps +
sections universelles à 2 niveaux, LaTeX côté client, rendu PDF via
`rendu_atome.js`).

C'est le 2e atelier atomique migré après carte (v0.13.6.6) et notion
(v0.13.6.7), bénéficiant désormais des correctifs structurels :
- Filtre niveau/séquence côté JS (`AtelierEditeur.filtrerListe`) —
  v0.13.6.7.1
- Ouverture d'item depuis le cache local (l'API `/api/methodes` n'a
  pas de GET unitaire, comme `/api/notions`) — v0.13.6.7.1
- Vidage de l'éditeur central au changement de filtre — v0.13.6.6.1

Le fichier `appli/static/atelier_methode.js` est essentiellement un
clone de `atelier_notion.js` adapté. Les différences sont :
- Préfixe DOM `atl-methode` au lieu de `atl-notion`
- Endpoint `/api/methodes` au lieu de `/api/notions`
- Identifiant sidebar `M01` (basé sur `num_methode`) au lieu de `N01`
  (basé sur `num_connaissance`)
- LaTeX `\begin{seqMethode}` au lieu de `\begin{seqNotion}`
- Miroirs `ATL_METHODE_ACTIF` et `ATL_METHODES`

---

## Mécanique de la classe `AtelierMethode`

```
Atelier
└── AtelierEditeur     (item actif, modifié/enregistré, sidebar, validation)
    └── AtelierAtomique (compilation PDF unitaire + .tex brut)
        └── AtelierMethode
```

Hérite donc automatiquement de :
- `chargerListe()` (GET `/api/methodes`)
- `ouvrirItem(id)` (cherche dans le cache, fallback fetch)
- `sauvegarder()` (POST/PUT)
- `supprimer()` (DELETE après confirm)
- `basculerValidation()` (POST .../validation)
- `_synchroniserItemActifAvecListe()` (vide l'éditeur au changement de filtre)
- `filtrerListe()` (niveau/séquence + état d'édition)
- `compilerRendu()` / `voirLatex()` (mais voirLatex est surchargée
  pour générer le LaTeX côté client)

Spécifique à la méthode :
- `rendreItem(m)` : ID format N11/S01/M01, placedTags depuis obj_lies
- `_htmlListeVide()` : message « Aucune méthode »
- `itemVide()` : objet vide pour création
- `collecterFormulaire()` / `remplirFormulaire(m)` : titre + corps +
  sections, validation du titre obligatoire
- `_lireSectionsDOM()` + 7 méthodes de gestion des sections (ajouter,
  supprimer, déplacer pour sections et items)
- `voirLatex()` surchargée : génère côté client
- `genererLatex()` : construit `\begin{seqMethode}{titre}{corps}...sections...\end{seqMethode}`
- `copierLatex()` : presse-papier
- `basculerOnglet('rendu')` : surcharge pour appeler `rendreAtomeTab('methode')`

---

## Code mort dans app.js

Les ~370 lignes de fonctions méthode dans `app.js` (lignes 3201-3548)
deviennent inertes (jamais appelées car les onclick HTML pointent
maintenant vers `ATELIER_METHODE`). À nettoyer en v0.14 avec le reste.

---

## Validation chez toi

Tous les comportements de l'atelier Méthode doivent rester identiques :

1. **Sidebar filtrée** par niveau/séquence (le bug v0.13.6.7→v0.13.6.7.2
   ne se reproduit pas — la classe parente fait le filtre, pas de surcharge
   qui court-circuite)
2. **Ouvrir une méthode** → l'éditeur s'ouvre avec titre + corps + sections
3. **Modifier un champ** → badge « modifié » + bouton Save s'active
4. **Sections** : ajouter, supprimer, déplacer, modifier titre,
   ajouter/supprimer/déplacer items dans une section
5. **Enregistrer** → toast « Méthode enregistrée », sidebar rechargée
6. **Valider / Repasser en cours** → pastille bascule
7. **LaTeX généré** → ouvre la zone LaTeX avec `\begin{seqMethode}...`
8. **Onglet Rendu PDF** → compilation PDF (via `rendu_atome.js`)
9. **+ Créer** → nouvelle méthode vide
10. **Supprimer** → confirmation puis suppression
11. **Changer le filtre niveau/séquence pendant l'édition** → la
    sidebar change ET l'éditeur central revient à vide

---

## Fichiers livrés

| Fichier | Statut |
|---|---|
| `appli/static/atelier_methode.js` | nouveau, ~370 lignes |
| `appli/templates/index.html` | modifié (script + 9 onclick) |

Décompresser à la racine de `seqenseigne/`. F5.

---

## Suite

### v0.13.6.7.4 — Migration fiche (prochaine session)

La fiche est plus complexe : sélecteur d'objectif, cache des titres
de zone paramétrables, bouton "Initialiser depuis", sections au
modèle un peu différent (1 textarea long au lieu de N items courts).

Migration en **conservant** le modèle actuel (pas de fusion zones/sections
ni de suppression du sélecteur d'objectif — c'est dans les chantiers
de cohérence C et D qui suivront).

### Suite des chantiers (acté précédemment)

- v0.13.6.8 : multi-sélection + menu contextuel dans `AtelierEditeur`
- v0.13.6.9 : chantier A — affichage homogène `placedTags` (`obj 02`
  partout, `S03 obj 02` pour hors séquence)
- v0.13.6.10 : chantier B — bouton « reprendre titre objectif »
- v0.13.6.11+ : chantier C — refonte modèle carte (1:1 strict vers
  objectif, lien modifiable uniquement depuis l'assemblage)
- v0.13.6.12+ : chantier D — suppression du sélecteur d'objectif
  dans atelier fiche (lien uniquement depuis l'assemblage)
- v0.13.7+ : chantier F — fusion zones/sections + description
  configurable des sections
