# Redémarrage v0.13.6.6

**Session du 14 mai 2026 — Refonte OO des ateliers (pilote carte)**

---

## Périmètre

Tu as demandé une factorisation transversale des 5+ ateliers JS qui se
répètent (sidebar, item actif, état modifié, validation, onglets,
compilation). Le scoping a abouti à une hiérarchie de classes ES6 :

```
Atelier (base : DOM helpers, toast, preferences, escape, rendreItemHtml)
├── AtelierEditeur (item actif, modifié/enregistré, sidebar,
│   │              validation, onglets, garde-sortie)
│   ├── AtelierAtomique (édition d'1 instance par formulaire +
│   │                    rendu PDF unitaire)
│   └── AtelierAssemblage (composition par drag-drop)  ← PAS dans cette livraison
└── AtelierRecap (sélecteur niveau + rendu PDF, pas d'édition)
                                                       ← PAS dans cette livraison
```

**Cette livraison v0.13.6.6 contient** :
- Les 3 classes ES6 strictes : `Atelier`, `AtelierEditeur`, `AtelierAtomique`
- **Pilote sur l'atelier carte uniquement** : `AtelierCarte extends AtelierAtomique`
- Migration du HTML (templates/index.html) pour utiliser
  `ATELIER_CARTE.method()` au lieu de `atelCarteXxx()`
- Ponts rétrocompat (alias `window.atelCarteXxx`) pour que rien d'autre
  ne se casse

**Ne sont PAS dans cette livraison** :
- L'atelier exercice (reporté à v0.13.6.7)
- Les ateliers notion, méthode, fiche, évaluation (v0.13.6.7+)
- Les classes `AtelierAssemblage` et `AtelierRecap` (v0.13.6.10+)
- La fonctionnalité multi-sélection + menu contextuel (v0.13.6.8)

L'exercice n'est pas dans cette livraison car son code est dispersé
entre `app.js` (6595 lignes) et `atelier_atome_generique.js`, et le
toucher demandait plus de temps que ce qu'on avait. La classe
`AtelierExercice` est cependant **écrite et incluse** dans le ZIP en
tant que fichier de référence pour la v0.13.6.7 — elle n'est juste
pas activée par `index.html`.

---

## Architecture des classes

### `Atelier` (static/atelier.js)

Classe de base. Tout atelier en hérite (directement ou via une
sous-classe). Méthodes :

- **Cycle de vie** : `init()`, `ouvrir()`, `fermer()` (hooks vides par
  défaut, à surcharger)
- **Filtres** : `get niveauFiltre`, `get sequenceFiltre` (lecture des
  globales `window.ATL_FILTRE_NIVEAU`/`SEQ`)
- **Helpers DOM** : `$(suffixe)` (= `getElementById(prefixe + '-' + suffixe)`),
  `setDisplay(suffixe, value)`, `toast(message, niveau)`
- **Échappement HTML** (statiques) : `Atelier.escHtml()`, `Atelier.escAttr()`
- **Préférences localStorage** : `lirePref(cle, defaut)`, `ecrirePref(cle, valeur)`
  (préfixées par `atl.{id}.` pour ne pas collisionner entre ateliers)
- **Rendu d'item** (statique) : `Atelier.rendreItemHtml(parts)` (anciennement
  `atelAsmItemHtml`, renommé pour refléter son usage transverse — le
  préfixe `asm` était trompeur)

### `AtelierEditeur extends Atelier` (static/atelier_editeur.js)

Pour les ateliers qui éditent du contenu persistant. Méthodes :

- **État** : `itemActif`, `modifie`, `tabCourant`, `selection` (Set, pour
  multi-sélection future)
- **Marqueurs** : `marquerModifie()`, `marquerEnregistre()`
- **Sidebar** : `chargerListe()` (GET endpointBase), `rendreSidebar()`
  (pattern plate par défaut), `rendreItem(item)` (à surcharger),
  `filtrerListe(liste)` (filtre global par défaut)
- **CRUD** : `ouvrirItem(id)`, `nouvelItem()`, `fermerEditeur()`,
  `sauvegarder()`, `supprimer()`
- **Validation** : `basculerValidation()` (en_cours ↔ valide)
- **Onglets** : `basculerOnglet(tab)` — bascule Édition/Rendu, met
  `display:flex` sur le parent rendu pour que le `flex:1` de l'iframe
  prenne effet
- **Toolbar** : `majToolbar()` gère titre, badges modifié/état, boutons
  valider/latex/suppr/save selon `this.itemActif` et `this.modifie`
- **Garde-sortie** : confirm() automatique avant `ouvrirItem` ou
  `nouvelItem` si `this.modifie === true`
- **À surcharger obligatoirement** : `collecterFormulaire()` (retour =
  objet pour POST/PUT, ou `null` si validation échoue),
  `remplirFormulaire(item)`

### `AtelierAtomique extends AtelierEditeur` (static/atelier_atomique.js)

Pour les ateliers qui éditent une instance par formulaire. Ajoute le
rendu PDF unitaire :

- `compilerRendu()` : POST `{endpointBase}/{id}/rendu-pdf`, affiche
  PDF dans iframe ou erreurs dans panneau dédié. Sécurité : maintient
  `display:flex` sur `#{prefixe}-tabs` en sortie pour éviter le bug
  v0.13.6.5.2.2 du bandeau qui disparaissait.
- `_afficherErreurCompilation(status, data)` : liste cliquable des
  erreurs, bouton « Voir le .tex brut », bouton « Voir le log »
- `toggleTexBrut()` : lazy load `{endpointBase}/{id}/rendu-tex` au
  premier clic, affichage avec lignes numérotées et highlight des
  lignes fautives
- `scrollVersLigneTex(ligne)` : clic sur une erreur → scroll automatique
  vers la ligne, mise en évidence visuelle 1.5s

### `AtelierCarte extends AtelierAtomique` (static/atelier_carte_automatisme.js)

Pilote v0.13.6.6 — la refonte ramène le fichier de 895 lignes à
~360 lignes. Surcharges :

- `chargerListe()` : 3 fetch parallèles (cartes + notions + méthodes
  de la séquence) pour peupler les sélecteurs de lien
- `rendreItem(c)` : badge 'P' si paramétrée, ID format N11/S01/CA03,
  titre avec icône du type pédagogique, tag 'n NN' ou 'm MM' selon
  l'atome lié
- `filtrerListe(liste)` : filtre d'état local (boutons Tous/En
  cours/Validé), pas de filtre global atelAtomeFiltreEtat_OK comme
  l'ancien code
- `collecterFormulaire()` / `remplirFormulaire(c)` : champs niveau,
  sequence, num, nom, type_pedago, type_tech, recto, verso, variables,
  lien_type, lien_id
- `nouvelItem()` : surcharge la base pour faire POST immédiat avec
  défauts (modèle propre à la carte, qui crée d'abord en BDD puis
  ouvre)

### `AtelierExercice extends AtelierAtomique` (livré mais non activé)

Le fichier `static/atelier_exercice.js` est **inclus dans le ZIP** mais
**pas chargé** par `index.html`. Il sert de référence pour v0.13.6.7
quand on activera la migration exercice. Surcharges prévues :

- `rendreSidebar()` : bucketing par série F/A/E/EA/Autres en sections
  repliables (helpers existants `atelCatEstReplie`, `atelAsmCatHtml`)
- `rendreItem(ex, badgeCode)` : badge série coloré, ID N11/S04/F01,
  placedTags depuis `ex.obj_lies`
- `collecterFormulaire()` / `remplirFormulaire(ex)` : tous les champs
  exo (nom, variables, énoncé, corrigé, remédiation, cadres de réponse)
- Méthodes spécifiques : `changerSerie()`, `majVisibiliteRemediation()`,
  `toggleVariables()`, `toggleCadreReponsePrincipal()`,
  `toggleCadreReponseRemed()`

---

## Mécanisme rétrocompat (ponts dans atelier_carte_automatisme.js)

Pour qu'aucun code externe ne se casse (par ex. atelier d'assemblage
qui pointerait vers la carte), tous les anciens noms `atelCarteXxx`
sont conservés comme alias globaux qui délèguent à l'instance :

```js
window.atelCarteCharger             = () => ATELIER_CARTE.chargerListe();
window.atelCarteNouvelle            = () => ATELIER_CARTE.nouvelItem();
window.atelCarteOuvrir              = (id) => ATELIER_CARTE.ouvrirItem(id);
// ... etc, 17 alias au total
```

Ces alias seront supprimés dans v0.14 avec le reste du nettoyage.

---

## Fichiers livrés

| Fichier | Type | Taille |
|---|---|---|
| `appli/static/atelier.js` | nouveau | ~270 lignes |
| `appli/static/atelier_editeur.js` | nouveau | ~450 lignes |
| `appli/static/atelier_atomique.js` | nouveau | ~250 lignes |
| `appli/static/atelier_carte_automatisme.js` | refactorisé | ~410 lignes (au lieu de 895) |
| `appli/static/atelier_exercice.js` | nouveau (non activé) | ~310 lignes (pour référence v0.13.6.7) |
| `appli/templates/index.html` | modifié | +3 `<script>` + remplacement des onclick carte |

---

## Validation chez toi

### À tester impérativement (régression pilote carte)

1. **Ouvrir l'atelier carte** (depuis le menu principal après avoir
   sélectionné un niveau et une séquence) → la sidebar doit afficher
   les cartes.
2. **Cliquer sur une carte** → l'éditeur central doit s'ouvrir, le
   formulaire être rempli, la toolbar afficher le bon titre.
3. **Modifier un champ** → le badge "modifié" doit apparaître, le
   bouton "Enregistrer" s'activer.
4. **Cliquer "Enregistrer"** → le toast "Carte enregistrée." doit
   s'afficher, la sidebar se recharger.
5. **Cliquer "Repasser en cours" ou "Valider"** → la pastille d'état
   doit basculer, la sidebar refléter le nouvel état.
6. **Basculer Édition ↔ Rendu PDF** → la zone PDF doit prendre toute
   la hauteur disponible (bug v0.13.6.5.2.2 corrigé).
7. **Compiler une carte qui plante** → le bandeau d'onglets doit
   rester visible, le panneau d'erreurs s'afficher (bug v0.13.6.5.2.2
   défensif toujours actif).
8. **Cliquer "Voir le .tex brut"** dans le panneau d'erreurs → le .tex
   doit s'afficher avec lignes numérotées et highlight des fautes.
9. **Cliquer "+ Créer"** → nouvelle carte créée en BDD, ouverte dans
   l'éditeur.
10. **Cliquer "Supprimer"** → confirmation, puis suppression.
11. **Changer le filtre niveau/séquence en haut de l'écran** → la liste
    des cartes doit se recharger (via `atelCarteCharger` qui délègue à
    `ATELIER_CARTE.chargerListe`).
12. **Filtrer par état** (boutons Tous / En cours / Validé) → la
    sidebar doit se restreindre correctement.

### Validation transverse

L'application devrait fonctionner exactement comme avant ailleurs
(notion, méthode, fiche, exercice, évaluation, assemblage, etc.).
Aucun de ces ateliers n'est touché par cette livraison — c'est l'objet
de v0.13.6.7+.

### En cas d'anomalie

Si quelque chose ne marche pas dans l'atelier carte, la console
JavaScript du navigateur (F12 → Console) devrait afficher l'erreur
avec un stack trace pointant vers la classe / méthode coupable. Les
classes étant nommées explicitement, l'erreur ressemblera à :

```
TypeError: ATELIER_CARTE.xxx is not a function
  at HTMLButtonElement.onclick (...)
```

ou

```
AtelierCarte.collecterFormulaire: ...
  at AtelierEditeur.sauvegarder
```

— ce qui rend le débuggage bien plus simple qu'avec l'ancien code
fonctionnel global.

---

## Suite

### v0.13.6.7 — Migration des autres ateliers atomiques

Migrer en chaîne (1 par tour de session) :
- **Exercice** : activer `atelier_exercice.js` déjà livré, retirer
  les `atelExoXxx` d'app.js et de `atelier_atome_generique.js`
- **Notion** : créer `atelier_notion.js`
- **Méthode** : créer `atelier_methode.js`
- **Fiche** : créer `atelier_fiche.js` refactorisé (le fichier existe
  déjà mais en style ancien)

### v0.13.6.8 — Multi-sélection + menu contextuel

Ajouter dans `AtelierEditeur` (donc disponible automatiquement dans
tous les ateliers atomiques) :
- Maj+clic / Ctrl+clic pour sélectionner plusieurs items
- Click droit → menu contextuel avec actions
- Actions de base : Valider (visible si ≥1 item non validé), Repasser
  en cours (visible si tous validés). Mode "tout ou rien".
- Plus tard : Compiler (en batch), etc.

### v0.13.6.10+ — Migrer assemblage et recap

- `AtelierAssemblage extends AtelierEditeur` pour seqniv, évaluation,
  référentiel
- `AtelierRecap extends Atelier` pour recap_cours, recap_exos,
  plans_de_travail
