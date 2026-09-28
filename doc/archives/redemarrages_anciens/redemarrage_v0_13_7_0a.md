# Redémarrage v0.13.7.0a — Garde de sortie réparée

## Périmètre

Livraison **préparatoire** au chantier éditeur LaTeX (v0.13.7.1+). Cette
livraison répare la garde de sortie des 4 ateliers atomiques cassés
(notion, méthode, exercice, fiche), qui pouvait laisser perdre des
modifications non sauvegardées sans avertissement.

Périmètre intentionnellement étroit : **rien n'est supprimé** dans
cette livraison. L'ancien pipeline (`atelier_garde_sortie.js`,
callbacks `ATL_ATOME_CONFIG`, branchement L6594-6601 d'`app.js`) reste
en place et fonctionne en repli. Le nettoyage de tout ça est l'objet
de v0.13.7.0b.

## Bug réparé

### Symptôme

Pour les ateliers **notion, méthode, exercice et fiche**, l'application
ne détectait pas qu'un formulaire avait été modifié. Conséquences :

1. Le badge « modifié » de la toolbar ne s'allumait jamais.
2. Cliquer sur un autre item de la sidebar ouvrait l'item nouveau **sans
   confirmation**, perdant silencieusement les modifications en cours.
3. Cliquer sur « + Créer » sur un item modifié faisait pareil.
4. Naviguer vers un autre atelier via le menu du haut faisait pareil.

Seul l'atelier **carte** était épargné parce qu'il avait son propre
pipeline câblé correctement.

### Cause racine

Depuis la migration OO des ateliers atomiques (v0.13.6.7+), chaque
sous-classe d'`AtelierAtomique` dispose d'une méthode `formChange()`
qui appelle `marquerModifie()` (héritée d'`AtelierEditeur`). Cette
méthode pose `this.modifie = true` et affiche le badge.

**Mais** : ce mécanisme n'est déclenché que si les champs HTML
appellent `formChange()` via `oninput`/`onchange`. Or seuls les champs
de l'atelier **carte** étaient câblés (cf. `templates/index.html`
L1917, L1921, etc.).

Pour les autres ateliers, les champs `<input>` et `<textarea>` n'avaient
ni `oninput` ni `onchange`. Donc :
- L'utilisateur tape → rien ne se passe côté JS.
- `this.modifie` reste à `false`.
- `ouvrirItem()` ne déclenche pas la confirmation (`if (this.modifie)`
  est faux).
- Le badge « modifié » reste caché.
- Le formulaire suivant écrase silencieusement l'ancien.

L'ancien pipeline `atelier_garde_sortie.js` (système à snapshots) qui
aurait dû prendre le relais a été court-circuité par les alias OO :
`atelSnapshotInstaller` n'est plus appelé nulle part depuis que
`atelAtomeNouveau`/`Charger`/`Sauvegarder`/`Supprimer` sont écrasés par
les méthodes des classes OO. Donc `_SNAPSHOTS[type]` reste à `null` en
permanence, et `atelSnapshotEstModifie` retourne toujours `false`.

Diagnostic complet réalisé en début de session. Le bug datait
probablement de la migration OO (v0.13.6.7+) mais n'a été noté
explicitement que maintenant.

## Fix

### 1. Câblage HTML (13 champs)

Ajout de `oninput="ATELIER_<TYPE>.formChange()"` (ou `onchange` pour les
sélecteurs) sur tous les champs des formulaires des 4 ateliers cassés :

| ID HTML | Atelier | Type |
|---|---|---|
| `atl-exo-titre` | Exercice | input |
| `atl-exo-variables` | Exercice | textarea |
| `atl-exo-enonce` | Exercice | textarea |
| `atl-exo-corrige` | Exercice | textarea |
| `atl-exo-cadre-rep-principal-lignes` | Exercice | input number |
| `atl-exo-remed-enonce` | Exercice | textarea |
| `atl-exo-remed-corrige` | Exercice | textarea |
| `atl-exo-cadre-rep-remed-lignes` | Exercice | input number |
| `atl-notion-titre` | Notion | input |
| `atl-notion-corps` | Notion | textarea |
| `atl-methode-titre` | Méthode | input |
| `atl-methode-corps` | Méthode | textarea |
| `atl-fiche-titre` | Fiche | input |

Les checkboxes `atl-exo-cadre-rep-principal-actif` et
`atl-exo-cadre-rep-remed-actif` avaient déjà un `onchange` câblé sur
`toggleCadreReponse*()`. Plutôt que d'ajouter un second handler dans
le HTML, ces deux méthodes ont été enrichies d'un `this.marquerModifie()`
final (cf. point 2). Logique identique, plus propre à maintenir.

### 2. Patch JS `atelier_exercice.js`

Les méthodes `toggleCadreReponsePrincipal()` et `toggleCadreReponseRemed()`
modifient l'état affichage (cadre de réponse activé ou non) en réponse
à la case à cocher. Elles ne marquaient pas le formulaire comme modifié.
Ajout d'un `this.marquerModifie()` final, conditionné à `this.itemActif`
(pour éviter de marquer dirty avant qu'un item soit ouvert).

### 3. Patch JS `atelier_garde_sortie.js`

La fonction `atelGardeAvantTransition()` est appelée quand l'utilisateur
quitte un atelier pour aller ailleurs dans l'application (menu du haut).
Elle vérifiait `atelSnapshotEstModifie(type)` (l'ancien pipeline qui ne
fonctionne plus). Le patch :

- Ajoute une table `_SINGLETONS` qui associe chaque type au nom de la
  variable globale du singleton OO (`exercice → 'ATELIER_EXERCICE'`,
  etc.).
- Définit `_singletonModifie(type)` qui lit `window[nom].modifie`.
- Définit `_singletonSauvegarder(type)` qui appelle
  `window[nom].sauvegarder()`.
- Modifie `atelGardeAvantTransition` pour qu'elle :
  - détecte les modifs via `_singletonModifie(t) || atelSnapshotEstModifie(t)`
  - sauvegarde via `_singletonSauvegarder(t)`
  - vérifie après coup que `this.modifie` est bien remis à `false`

L'OR entre les deux mécanismes (`_singletonModifie || atelSnapshotEstModifie`)
préserve le comportement historique pour des ateliers qui repasseraient
au pipeline snapshot, par sécurité. En pratique, seul `_singletonModifie`
détecte aujourd'hui parce que les snapshots ne sont plus alimentés.

`atelGardeMajIndicateur` (badge "modifié" en toolbar) n'a pas été
patché : le badge est de toute façon piloté par `majToolbar()` dans
`AtelierEditeur` (L590-593), qui lit `this.modifie` directement.
L'appel à `atelGardeMajIndicateur` dans le branchement L6580 d'`app.js`
reste actif mais devient redondant — il sera retiré en v0.13.7.0b avec
le reste du pipeline historique.

## Fichiers livrés (3 fichiers)

```
appli/templates/index.html              + 13 attributs oninput/onchange
appli/static/atelier_exercice.js        + 2 lignes marquerModifie() dans toggles
appli/static/atelier_garde_sortie.js    refonte atelGardeAvantTransition,
                                        ajout helpers _SINGLETONS/_singletonModifie/
                                        _singletonSauvegarder, repli historique
                                        conservé via OR
```

Aucune modification serveur. Aucun test modifié. Suite : **3238 passed**.

## Vérification

- Suite complète : **3238 passed, 5 skipped, 0 failed** (inchangée)
- Sanity JS (`node -c`) sur les 3 fichiers modifiés : OK
- Audit refs orphelines : RAS (rien n'est retiré dans cette livraison)

## À tester chez toi

### Atelier Notion

1. Ouvrir l'atelier Notion, sélectionner niveau/séquence, ouvrir une
   notion existante.
2. Modifier le titre. **Le badge « modifié » doit s'afficher dans la
   toolbar.**
3. Cliquer sur une autre notion dans la sidebar. **Une popup native
   `confirm()` doit demander si on perd les modifs.**
4. Annuler → on reste sur l'item modifié.
5. Confirmer → on bascule sur l'autre notion, le titre revient à sa
   valeur d'origine.
6. Modifier le titre à nouveau. Cliquer sur l'onglet « Méthode » du
   menu du haut. **La modale 3 boutons (Sauvegarder/Ne pas sauvegarder/
   Annuler) doit apparaître.**
7. Pareil avec le corps (textarea).

### Atelier Méthode

Identique au point précédent, en partant de l'atelier Méthode.

### Atelier Exercice

1. Ouvrir un exercice existant.
2. Modifier le titre, l'énoncé, le corrigé, les variables. Pour chacun,
   le badge « modifié » doit s'afficher.
3. Cocher/décocher « Cadre de réponse » → badge.
4. Changer le nombre de lignes du cadre → badge.
5. Modifier l'énoncé de remédiation (si visible, série F ou A) → badge.
6. Cliquer sur la série « Avancé » alors qu'on était en « Fondamental »
   → badge (déjà OK avant v0.13.7.0a, mais à vérifier qu'on ne l'a pas
   cassé).
7. Cliquer sur un autre exercice → confirmation.

### Atelier Fiche

1. Ouvrir une fiche.
2. Modifier le titre → badge.
3. Modifier le corps d'une section (textarea) → badge (déjà OK avant,
   à vérifier qu'on ne l'a pas cassé).
4. Cliquer sur une autre fiche → confirmation.

### Atelier Carte

Doit continuer à fonctionner exactement comme avant (touché à zéro
ligne dans cette livraison).

### Cas particulier : la modale 3 boutons (transitions inter-ateliers)

L'ancien système `atelier_garde_sortie.js` affiche une modale custom
avec trois choix (Sauvegarder, Ne pas sauvegarder, Annuler) quand on
change d'atelier. Cette modale est conservée et fonctionne à présent
grâce au patch sur `atelGardeAvantTransition`.

L'écart avec la garde intra-atelier (changement d'item dans la même
sidebar) :

- **Intra-atelier** (ouvrirItem, nouvelItem, supprimer) : `confirm()`
  natif binaire (Annuler / OK). Comportement géré par `AtelierEditeur`.
- **Inter-atelier** (menu du haut, autre portée) : modale 3 boutons.
  Comportement géré par `atelier_garde_sortie.js` (patché).

C'est cohérent : intra-atelier, l'utilisateur peut juste choisir
d'enregistrer manuellement avant de cliquer ailleurs (il voit le
formulaire). Inter-atelier, la modale propose l'enregistrement
direct (l'utilisateur ne voit plus le formulaire à ce moment).

## Limitations connues

1. **Bouton « + Créer » avec atome modifié** : `nouvelItem()` dans
   `AtelierEditeur` vérifie `this.modifie` (L302) et fait un `confirm()`.
   Comportement identique à la carte. OK.

2. **Fermeture du navigateur / actualisation** : décision de v0.10.6
   (Q1-B), pas de `beforeunload`. Inchangé. Si l'utilisateur ferme
   l'onglet sans sauvegarder, modifs perdues sans avertissement.
   Hors-périmètre cette livraison.

3. **Le badge « modifié »** : double système temporairement en place :
   - Le `majToolbar()` d'`AtelierEditeur` pilote le badge correctement
     depuis `this.modifie`. ✅
   - Le branchement L6578-6580 d'`app.js` appelle aussi
     `atelGardeMajIndicateur()` à chaque input, qui consulte
     `atelSnapshotEstModifie` (qui retourne toujours false). Sans
     effet, donc inoffensif. Sera retiré en v0.13.7.0b.

4. **Le branchement L6594-6601 d'`app.js`** qui enregistre
   `lireDom: _atelNotionLireDomComplet, sauvegarder: atelNotionSauvegarder`
   pour la garde historique. Reste en place mais inopérant (snapshots
   pas alimentés). Sera retiré en v0.13.7.0b.

## Prochaine étape — v0.13.7.0b

Nettoyage et factorisation. Périmètre prévu :

1. Suppression du code mort dans `app.js` (~700 lignes — toutes les
   fonctions `atelNotion*` et `atelMethode*` et leurs callbacks
   `ATL_ATOME_CONFIG.<type>.callbacks`).
2. Factorisation des sections (notion/méthode) directement dans
   `AtelierAtomique` (option a actée).
3. Suppression de `atelier_garde_sortie.js` (l'ancien pipeline
   complet).
4. Suppression de `atelier_atome_generique.js` (legacy court-circuité).
5. Suppression du branchement L6558-6616 d'`app.js`.
6. Câblage de la garde inter-ateliers via un nouveau helper plus
   propre (lit directement les singletons `window.ATELIER_*`).

Suite v0.13.7.0b validée → v0.13.7.1 (squelette éditeur LaTeX) tel que
cadré dans `cadrage_v0_13_7_1_editeur_latex.md`.
