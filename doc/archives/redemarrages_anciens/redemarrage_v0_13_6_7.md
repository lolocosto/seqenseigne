# Redémarrage v0.13.6.7

**Session du 14 mai 2026 — Migration notion + fix bouton carte**

---

## Périmètre

Suite directe de tes 2 remarques après v0.13.6.6.1 :

1. **Bouton « atelier actif » du second bandeau** : marche pour tous les
   ateliers sauf l'atelier carte. Cause identifiée : convention de
   nommage HTML cassée (le bouton avait l'id `atl-btn-carte` alors que
   le panel est `atl-carte_automatisme` → `atelSwitch` cherchait
   `atl-btn-carte_automatisme` qui n'existait pas → la classe `.active`
   n'était jamais posée sur le bouton).

2. **Éditeur central vidé au changement de filtre** : fonctionne
   uniquement pour la carte (seule à hériter de `AtelierEditeur`). Le
   bon traitement à long terme est de migrer les autres ateliers
   atomiques pour qu'ils héritent eux aussi de `AtelierEditeur` et
   bénéficient automatiquement de `_synchroniserItemActifAvecListe()`.

Ta directive « il est urgent de continuer à factoriser » est prise au
sérieux : cette livraison commence la migration des autres ateliers
atomiques. **Notion** est migré ici (le plus simple, fait office de
2e pilote pour valider que `AtelierEditeur` couvre bien le cas
« sidebar plate, sans rendu PDF unitaire serveur, avec génération
LaTeX côté client »).

---

## Fixes / migrations

### Fix 1 — Bouton carte : renommer pour respecter la convention

**Diagnostic** : `atelSwitch(panel)` dans `app.js` (ligne 2317) cherche
le bouton via `'atl-btn-' + panel`. Pour panel = `'carte_automatisme'`,
ça donne `'atl-btn-carte_automatisme'` — mais le bouton HTML avait
l'id `atl-btn-carte`. Donc la classe `.active` n'était jamais posée
sur ce bouton précisément (le bouton restait inerte visuellement).

**Fix** : renommer l'attribut `id` dans `templates/index.html`
ligne 462 :
- Avant : `<button … id="atl-btn-carte" …>`
- Après : `<button … id="atl-btn-carte_automatisme" …>`

C'est un fix existant **pré-v0.13.6.6** ; le bouton carte n'a jamais
correctement réagi à la classe `.active` depuis qu'il existe (v0.13.6.1).
Le bug était invisible parce que tout le bandeau avait un fond
`#fafafa` qui masquait le contraste — découvert seulement après le fix
v0.13.6.6.1 qui a retiré ce fond.

### Migration — Notion vers AtelierAtomique

Nouveau fichier `static/atelier_notion.js` (~370 lignes) qui contient
la classe `AtelierNotion extends AtelierAtomique`. Hérite donc de
toute la machinerie commune (item actif, modifie/enregistré, sidebar,
validation, onglets, garde-sortie, **vidage de l'éditeur au changement
de filtre via `_synchroniserItemActifAvecListe`**).

Spécificités notion préservées :

- **Sidebar plate** avec id format `N11/S01/N01` (utilise `num_connaissance`)
- **Formulaire** : titre + corps + sections (modèle universel à 2
  niveaux). La gestion des sections (`this.sections`, méthodes
  `ajouterSection`, `supprimerSection`, `deplacerSection`,
  `majTitreSection`, `ajouterItem`, `supprimerItem`, `deplacerItem`)
  est intégralement portée comme méthodes de classe.
- **LaTeX généré côté client** (pas de route /rendu-tex serveur) :
  surcharge `voirLatex()` qui appelle `genererLatex()` (construit le
  `.tex` à partir du formulaire) et passe à `atelierAfficherLatex`
  pour l'affichage.
- **Rendu PDF onglet** : surcharge `basculerOnglet('rendu')` qui appelle
  `rendreAtomeTab('notion')` (mécanisme générique `rendu_atome.js`).
- **Setters miroirs** : `set itemActif` et `set liste` maintiennent
  `window.ATL_NOTION_ACTIF` et `window.ATL_NOTIONS` synchronisés pour
  que les modules historiques (`rendu_atome.js`, `atelier_etat_edition.js`)
  continuent de fonctionner sans modification.

### Templates modifiés

`templates/index.html` :
- Bouton carte renommé (fix 1)
- Script `<script src="/static/atelier_notion.js"></script>` ajouté
  après `atelier_carte_automatisme.js`
- 8 `onclick="atelNotionXxx()"` remplacés par `ATELIER_NOTION.method()`.
  Le mapping est :
  | Avant | Après |
  |---|---|
  | `atelNotionNouveau()` | `ATELIER_NOTION.nouvelItem()` |
  | `atelNotionBasculerValidationCb()` | `ATELIER_NOTION.basculerValidation()` |
  | `atelNotionVoirLatex()` | `ATELIER_NOTION.voirLatex()` |
  | `atelNotionSupprimer()` | `ATELIER_NOTION.supprimer()` |
  | `atelNotionSauvegarder()` | `ATELIER_NOTION.sauvegarder()` |
  | `atelNotionTab('edition'\|'rendu')` | `ATELIER_NOTION.basculerOnglet('…')` |
  | `atelNotionAjouterSection()` | `ATELIER_NOTION.ajouterSection()` |
  | `atelNotionCopierLatex()` | `ATELIER_NOTION.copierLatex()` |

### Code mort dans app.js

Les ~370 lignes de fonctions notion dans `app.js` (lignes 2838-3197)
deviennent du code mort à partir de cette livraison. Elles ne sont
plus appelées depuis le HTML, et personne d'externe ne les appelle non
plus (vérifié par grep). À nettoyer en v0.14 avec le reste de la dette
historique (lignes ~2838-3197 + `ATL_ATOME_CONFIG.notion` dans
`atelier_atome_generique.js`).

**Pourquoi ne pas les supprimer maintenant** : pour limiter le risque
de cette livraison. Toucher à app.js (6595 lignes) au cours d'une
session présente trop d'occasions de casser autre chose. Les anciennes
fonctions notion étant inertes (jamais appelées), le coût de les
laisser en place est minime.

### Ponts rétrocompat dans atelier_notion.js

21 alias globaux conservés à la fin du fichier (`window.atelChargerNotions`,
`window.atelNotionRemplir`, `window.atelNotionRenderSections`, etc.)
pour qu'aucun code externe ne se casse. À retirer en v0.14.

---

## Validation chez toi

### Test fix 1 (bouton carte)

1. Recharger la page
2. Aller dans Carte d'automatisme (cliquer sur le bouton du 2e bandeau)
3. **Attendu** : le bouton « Carte d'automatisme » a maintenant son
   fond bleu pâle actif, comme les autres ateliers

### Tests migration notion

Tous les comportements de l'atelier Notion doivent rester strictement
identiques à ce que tu avais avant :

1. **Ouvrir l'atelier Notion** → la sidebar liste les notions
2. **Cliquer sur une notion** → l'éditeur s'ouvre, titre + corps + sections
3. **Modifier un champ** → badge « modifié » apparaît, bouton Enregistrer s'active
4. **Ajouter une section** → s'affiche en bas de la zone sections
5. **Déplacer une section** (↑/↓), **supprimer** (×), **modifier le titre**
6. **Ajouter un item** dans une section, **modifier**, **déplacer**, **supprimer**
7. **Cliquer Enregistrer** → toast « Notion enregistrée », sidebar rechargée
8. **Cliquer Valider / Repasser en cours** → pastille bascule
9. **Cliquer LaTeX généré** → ouvre la zone LaTeX avec le `.tex` construit
   à partir du formulaire
10. **Onglet Rendu PDF** → la compilation PDF se déclenche (via
    `rendu_atome.js` qui lit `ATL_NOTION_ACTIF` maintenu en miroir)
11. **+ Créer** → nouvelle notion vide dans l'éditeur
12. **Supprimer** → confirmation, puis suppression

### Test transverse : changement de filtre

1. Sélectionner N10/S01, ouvrir atelier Notion
2. Cliquer sur une notion → éditeur s'ouvre
3. Changer la séquence en haut : passer à S02
4. **Attendu** : la sidebar à gauche affiche les notions de S02, le
   panneau central revient à l'état vide

(C'est le bénéfice direct de l'héritage de `AtelierEditeur` —
`_synchroniserItemActifAvecListe()` fonctionne automatiquement.)

### En cas d'anomalie

Console JS (F12) doit donner un message clair grâce aux classes
nommées. Erreur du style :
```
TypeError: ATELIER_NOTION.xxx is not a function
  at HTMLButtonElement.onclick (...)
```
ou
```
AtelierNotion.collecterFormulaire: ...
  at AtelierEditeur.sauvegarder
```
copie-moi le message et je localise.

---

## Fichiers livrés

| Fichier | Statut |
|---|---|
| `appli/static/atelier_notion.js` | nouveau |
| `appli/templates/index.html` | modifié |

Décompresser à la racine de `seqenseigne/`. F5 sur le navigateur.

**Pas livrés** (inchangés depuis v0.13.6.6.1) :
- `static/atelier.js`
- `static/atelier_editeur.js`
- `static/atelier_atomique.js`
- `static/atelier_carte_automatisme.js`
- `static/app.js`
- `static/atelier_atome_generique.js`

---

## Suite

### v0.13.6.7.1 — Migration méthode

Pattern identique à notion (sidebar plate, formulaire titre + corps +
sections, LaTeX côté client, rendu PDF via `rendu_atome.js`). Fichier
`atelier_methode.js`.

### v0.13.6.7.2 — Migration fiche

Spécificité fiche : liaison 1-1 avec un objectif (`atelier_fiche.js`
existe déjà mais en style ancien). Migration vers la classe
`AtelierAtomique`.

### v0.13.6.7.3 — Migration exercice

Le plus complexe : bucketing par série F/A/E/EA/Autres, sections
repliables, plus de champs (variables, énoncé, corrigé, remédiation,
cadres de réponse). Le fichier `atelier_exercice.js` est déjà prêt
depuis v0.13.6.6 (livré mais non activé) — il suffira de l'activer et
de retirer le code correspondant d'app.js.

### v0.13.6.8 — Multi-sélection + menu contextuel

Une fois tous les ateliers atomiques migrés, ajouter dans
`AtelierEditeur` (donc disponible automatiquement partout) :
- Maj+clic / Ctrl+clic pour sélectionner plusieurs items
- Click droit → menu contextuel
- Actions : Valider / Repasser en cours en mode « tout ou rien »

### v0.13.6.10+ — AtelierAssemblage et AtelierRecap

Créer les deux classes manquantes de la hiérarchie pour migrer les
ateliers restants (séqniv-assemblage, évaluation, référentiel,
recap-cours, recap-exos, plans-de-travail).
