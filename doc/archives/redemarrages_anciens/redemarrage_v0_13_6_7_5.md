# Redémarrage v0.13.6.7.5

**Session du 15 mai 2026 — Migration exercice (5e et dernier atome)**

---

## Périmètre

Activation de l'atelier Exercice en hiérarchie OO. Le fichier
`atelier_exercice.js` était déjà écrit depuis v0.13.6.6 (squelette
~344 lignes) mais non activé : ni inclus dans le HTML, ni branché
sur les onclick. Cette livraison fait l'activation **et** enrichit
la classe avec les leçons des migrations notion/méthode/fiche.

**C'est la fin de la migration OO des 5 ateliers atomiques.**

| Atelier | Migré | Version |
|---|---|---|
| Carte d'automatisme | ✅ | v0.13.6.6 |
| Notion | ✅ | v0.13.6.7 |
| Méthode | ✅ | v0.13.6.7.3 |
| Fiche de résumé | ✅ | v0.13.6.7.4 |
| **Exercice** | **✅** | **v0.13.6.7.5** |

---

## Enrichissements apportés au squelette v0.13.6.6

Le squelette initial était fonctionnel mais incomplet. J'ai ajouté :

### 1. Setters miroir `window.ATL_EXO_ACTIF` et `window.ATL_EXO`
(leçon v0.13.6.7.3.1)

```js
set itemActif(val) {
  this._itemActif = val;
  window.ATL_EXO_ACTIF = val;
}
set liste(val) {
  this._liste = val;
  window.ATL_EXO = val;
}
```

Tout code legacy qui lit `window.ATL_EXO_ACTIF` continue de marcher
(`rendu_atome.js` a un fallback historique, mais lit en priorité
`window.ATELIER_EXERCICE.itemActif` depuis v0.13.6.7.3.1).

### 2. Surcharge `basculerOnglet` avec cas-coin `#atl-exercice-rendu`

Cas-coin spécifique à l'exercice : la zone de rendu PDF dans le HTML
porte l'id `atl-exercice-rendu` (avec « exercice » complet), alors
que `this.prefixe` = `atl-exo`. La parente `AtelierEditeur.basculerOnglet`
masque/affiche `#atl-exo-rendu` qui n'existe pas — ça aurait laissé
le panneau invisible. La surcharge masque/affiche manuellement
`#atl-exercice-rendu` en plus, puis délègue à `rendreAtomeTab('exercice')`
qui utilise déjà la convention « complète ».

```js
basculerOnglet(tab) {
  super.basculerOnglet(tab);
  const zoneExoRendu = document.getElementById('atl-exercice-rendu');
  if (zoneExoRendu) {
    zoneExoRendu.style.display =
      (tab === 'rendu' && this.itemActif) ? 'flex' : 'none';
  }
  if (tab === 'rendu' && typeof window.rendreAtomeTab === 'function') {
    window.rendreAtomeTab('exercice');
  }
}
```

À envisager pour homogénéisation future : renommer dans le HTML/CSS
`atl-exercice-rendu` → `atl-exo-rendu` pour aligner sur la convention
des autres ateliers. Pas fait dans cette livraison pour limiter les
changements.

### 3. Génération LaTeX côté client

Ajout de `voirLatex()`, `genererLatex()`, `copierLatex()`, alignés
sur le pattern notion/méthode. Format spécifique exercice :

```latex
%% ── Série fondamental ──────────────────────────────────────────
\begin{seqSerieExos}{1}

  \begin{seqExercice}[nom=...]
    énoncé
    \seqCorrige{
      corrigé
    }
  \end{seqExercice}

\end{seqSerieExos}
```

Le numéro de série est mappé : fondamental=1, avancé=2,
exploration=3, approche=4. Calque exact du code historique
`atelExoGenererLatex` (app.js ligne 2778).

### 4. Ponts rétrocompat (17 alias)

```js
window.atelChargerExercices         = () => ATELIER_EXERCICE.chargerListe();
window.atelRenderListe              = () => ATELIER_EXERCICE.rendreSidebar();
window.atelExoNouveau               = () => ATELIER_EXERCICE.nouvelItem();
window.atelExoCharger               = (id) => ATELIER_EXERCICE.ouvrirItem(id);
window.atelExoSauvegarder           = () => ATELIER_EXERCICE.sauvegarder();
window.atelExoSupprimer             = () => ATELIER_EXERCICE.supprimer();
window.atelExoRemplir               = (ex) => ATELIER_EXERCICE.remplirFormulaire(ex);
window.atelExoTab                   = (tab) => ATELIER_EXERCICE.basculerOnglet(tab);
window.atelExoSerie                 = (s, update = true) => ATELIER_EXERCICE.changerSerie(s, update);
window.atelExoMajVisibiliteRemediation = () => ATELIER_EXERCICE.majVisibiliteRemediation();
window.atelExoToggleVariables       = () => ATELIER_EXERCICE.toggleVariables();
window.atelExoToggleCadreReponsePrincipal = () => ATELIER_EXERCICE.toggleCadreReponsePrincipal();
window.atelExoToggleCadreReponseRemed = () => ATELIER_EXERCICE.toggleCadreReponseRemed();
window.atelExoVoirLatex             = () => ATELIER_EXERCICE.voirLatex();
window.atelExoGenererLatex          = () => ATELIER_EXERCICE.genererLatex();
window.atelExoCopierLatex           = () => ATELIER_EXERCICE.copierLatex();
window.atelExoBasculerValidationCb  = () => ATELIER_EXERCICE.basculerValidation();
```

Évite de casser le code interne qui pourrait appeler ces noms
historiques (autres modules, console debug, scripts utilisateur).

---

## Modifications HTML

### 1. Inclusion du script
```html
<script src="/static/atelier_fiche.js"></script>
<script src="/static/atelier_exercice.js"></script>   ← nouveau
```

Placé APRÈS `atelier_atomique.js` (la classe parente doit être
chargée d'abord).

### 2. IDs sur les onglets (leçon v0.13.6.7.3.1)
```html
<div class="atl-tabs" id="atl-exo-tabs" style="display:none">
  <button class="atl-tab active" id="atl-exo-tab-btn-edition"
          onclick="ATELIER_EXERCICE.basculerOnglet('edition')">Édition</button>
  <button class="atl-tab" id="atl-exo-tab-btn-rendu"
          onclick="ATELIER_EXERCICE.basculerOnglet('rendu')">Rendu PDF</button>
</div>
```

### 3. Remplacement des onclick (11 modifs)
Tous les `onclick="atelExoXxx()"` et `onchange="atelExoXxx()"` du HTML
sont remplacés par leurs équivalents `ATELIER_EXERCICE.xxx()` :
- `atelExoNouveau()` → `ATELIER_EXERCICE.nouvelItem()`
- `atelExoBasculerValidationCb()` → `ATELIER_EXERCICE.basculerValidation()`
- `atelExoVoirLatex()` → `ATELIER_EXERCICE.voirLatex()`
- `atelExoSupprimer()` → `ATELIER_EXERCICE.supprimer()`
- `atelExoSauvegarder()` → `ATELIER_EXERCICE.sauvegarder()`
- `atelExoSerie('X')` → `ATELIER_EXERCICE.changerSerie('X')`
- `atelExoToggleVariables()` → `ATELIER_EXERCICE.toggleVariables()`
- `atelExoToggleCadreReponsePrincipal()` → `ATELIER_EXERCICE.toggleCadreReponsePrincipal()`
- `atelExoToggleCadreReponseRemed()` → `ATELIER_EXERCICE.toggleCadreReponseRemed()`
- `atelExoCopierLatex()` → `ATELIER_EXERCICE.copierLatex()`

Audit : `0 onclick atelExo restant` ✓

---

## Cas-coins identifiés et résolus

### 1. Asymétrie API `/api/exercices`
Le backend filtre par `niveau` et `serie` côté serveur, mais **pas
par `sequence`**. Quand `AtelierEditeur.chargerListe()` envoie
`?niveau=X&sequence=Y`, le `sequence=Y` est ignoré. Le filtre côté
JS (`AtelierEditeur.filtrerListe()` depuis v0.13.6.7.1) compense.

### 2. Pas de GET unitaire `/api/exercices/<id>`
Comme pour notion et méthode. L'ouverture cherche dans le cache local
(comportement parente v0.13.6.7.1).

### 3. `#atl-exercice-rendu` vs convention `atl-exo-rendu`
Détaillé plus haut (point 2 des enrichissements).

---

## Vérifications appliquées (leçons des migrations précédentes)

- ✅ **IDs sur les onglets** (leçon v0.13.6.7.3.1) : ajout dès l'écriture
- ✅ **Pas de surcharge `filtrerListe`** : la parente fait le job
  (filtre niveau/séquence + état d'édition)
- ✅ **Setters miroir window** sur `ATL_EXO_ACTIF` et `ATL_EXO`
- ✅ **Ordre des scripts** : `atelier_exercice.js` chargé après
  `atelier.js`, `atelier_editeur.js`, `atelier_atomique.js`
- ✅ **Champs statiques ES2015-compat** : déjà fait en v0.13.6.6.1
  (`AtelierExercice.SERIE_BUCKETS = {...}` post-classe, pas dans le
  corps de la classe — évite l'erreur sur navigateurs anciens)

---

## Code mort dans app.js

Les ~370 lignes de fonctions exercice dans `app.js` (lignes 1512,
2353, 2470, 2483-2810, 6251) deviennent inertes après cette
livraison (jamais appelées, car les onclick HTML pointent maintenant
vers `ATELIER_EXERCICE`).

**Particularité importante** : le wrapper `atelExoBasculerValidationCb`
(app.js ligne 6251) lit `ATL_EXO_ACTIF` et `ATL_EXO` directement
(sans `window.`). Si on l'invoque, il accède à la `let` d'app.js
restée à `null` (pas mes setters miroir). C'est pour ça que le HTML
appelle directement `ATELIER_EXERCICE.basculerValidation()` au lieu
du wrapper. Le wrapper reste juste pour rétrocompat externe et il
est lui-même remplacé en pont rétrocompat dans
`atelier_exercice.js` (qui appelle correctement la classe).

À nettoyer en v0.14 avec le reste du code mort des migrations.

---

## Validation chez toi

Tous les comportements de l'atelier Exercice doivent rester
identiques. Liste de tests :

### Tests sidebar
1. **Sidebar filtrée par niveau/séquence** (le bug v0.13.6.7→v0.13.6.7.2
   ne doit pas se reproduire)
2. **Bucketing par série** : sections Fondamentaux / Avancés /
   Exploration / Approche / Autres avec items dans les bons buckets
3. **Sections repliables** : cliquer sur l'en-tête d'une catégorie
   replie/déplie le bucket
4. **Badge série** coloré (F bleu, A orange, E violet, EA gris) à
   gauche de chaque item dans la sidebar
5. **placedTags objectifs** à droite (codes objectifs liés depuis
   `ex.obj_lies`)

### Tests éditeur
6. **Cliquer sur un exercice** → l'éditeur s'ouvre avec nom, énoncé,
   corrigé, série, variables, remédiation, cadre de réponse
7. **Changer la série** (Fondamental / Avancé / Exploration / Approche)
   → bouton série actif change, et la zone Remédiation apparaît/disparaît
   (visible pour F et A, masquée pour E et EA)
8. **Modifier un champ** → badge « modifié » + bouton Save s'active
9. **Toggle Variables** → la zone Variables apparaît/disparaît
10. **Toggle Cadre Réponse Principal** → la zone lignes apparaît/disparaît
11. **Toggle Cadre Réponse Remed** → idem

### Tests onglets et rendu
12. **Cliquer Rendu PDF** → trait bleu sous Rendu PDF + bouton Compiler
    s'affiche (vérification de la leçon v0.13.6.7.3.1)
13. **Compiler** → PDF généré

### Tests sauvegarde/validation
14. **Sauvegarder sans énoncé** → toast d'erreur
15. **Sauvegarder sans corrigé** → toast d'erreur
16. **Sauvegarder valide** → toast « Exercice enregistré »
17. **Valider / Repasser en cours** → pastille bascule (réutilise
    `AtelierEditeur.basculerValidation`)
18. **Supprimer** → confirmation, suppression effective

### Tests LaTeX
19. **Bouton « LaTeX généré »** → ouvre la zone LaTeX avec
    `\begin{seqSerieExos}{N}...\end{seqSerieExos}`
20. **Copier** → presse-papier

### Tests transverses
21. **Changer le filtre niveau/séquence pendant l'édition** → sidebar
    change ET éditeur central revient à vide (`_synchroniserItemActifAvecListe`
    de v0.13.6.7.1)
22. **Régression** : carte, notion, méthode, fiche doivent continuer
    à fonctionner comme avant

---

## Fichiers livrés

| Fichier | Statut |
|---|---|
| `appli/static/atelier_exercice.js` | **nouveau / activé** (~494 lignes, dont ~150 enrichissements depuis v0.13.6.6) |
| `appli/templates/index.html` | modifié (script + IDs onglets + 11 onclick) |

Décompresser à la racine de `seqenseigne/`. F5.

---

## Suite

### Migration OO terminée

Tous les ateliers d'atomes sont maintenant en OO. La hiérarchie est
stable :

```
Atelier (base)
└── AtelierEditeur (modif/enregistré, sidebar, filtres)
    ├── AtelierAtomique (compilation PDF unitaire)
    │   ├── AtelierCarte    (v0.13.6.6)
    │   ├── AtelierNotion   (v0.13.6.7)
    │   ├── AtelierMethode  (v0.13.6.7.3)
    │   ├── AtelierFiche    (v0.13.6.7.4)
    │   └── AtelierExercice (v0.13.6.7.5)
    └── AtelierAssemblage (à créer, pour l'atelier de séquence-dans-niveau)
    └── AtelierRecap (à créer, pour les ateliers récap)
```

### Roadmap (rappel)

- **v0.13.6.8** : multi-sélection + menu contextuel dans `AtelierEditeur`
  (Maj+clic, Ctrl+clic, click droit, actions Valider/Repasser en cours
  « tout ou rien »)
- **v0.13.6.9** : chantier A — affichage homogène des `placedTags`
  (format `obj 02`, ou `S03 obj 02` hors séquence)
- **v0.13.6.10** : chantier B — bouton « reprendre titre objectif »
  dans `AtelierEditeur` (si lien 1:1)
- **v0.13.6.11+** : chantier C — refonte modèle carte (1:1 strict
  vers objectif, lien modifiable uniquement depuis l'assemblage)
- **v0.13.6.12+** : chantier D — suppression sélecteur objectif fiche
- **v0.13.7+** : chantier F — fusion zones/sections + description
  configurable des sections
