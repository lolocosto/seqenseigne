# patch v0.10.6 — Garde de sortie pour les ateliers de la portée Séquence

**Date** : 2 mai 2026

**Périmètre** : badge « modifié » + modale de garde « Sauvegarder /
Ne pas sauvegarder / Annuler » sur tous les ateliers atomiques de la
portée Séquence (Exercice, Notion, Méthode, Fiche).

**Score tests** : 1656/1656 + 4 skipped historiques. Aucune régression
(modifications purement frontend).

---

## Périmètre validé avec l'utilisateur (Q1-A à Q1-D)

- **Q1-A** : ateliers de la portée Séquence (Exercice, Notion, Méthode,
  Fiche). PAS l'atelier Séquence (assemblage) qui auto-sauve à chaque
  drop / drag / changement de critère / changement de nom (le `onblur`
  des inputs déclenche un POST immédiat — il n'y a donc pas d'état
  « modifié non sauvé » à protéger).
- **Q1-B** : pas de garde sur fermeture / actualisation navigateur.
  (`beforeunload` non installé.)
- **Q1-C** : garde dès qu'on sort de l'atelier vers n'importe quelle
  destination de l'application : autre atelier, autre item dans la
  sidebar, changement de portée, changement de niveau / séquence,
  onglets de navigation principale (Suivi / Admin / Préférences /
  Aide).
- **Q1-D** : garde aussi à la création d'un nouvel item alors qu'on
  est en train d'éditer un item modifié.

---

## Architecture

### 1. Module commun `static/atelier_garde_sortie.js`

Nouveau module qui expose les API suivantes sur `window` :

```js
atelSnapshotInstaller(type, donnees)   // capture un snapshot
atelSnapshotEffacer(type)              // efface le snapshot
atelSnapshotEstModifie(type)           // bool : modifs en cours ?
atelGardeMajIndicateur(type)           // affiche/cache le badge
atelGardeAvantTransition(continuation) // garde universelle
atelGardeEnregistrerHandler(type, h)   // pour l'enregistrement initial
```

Stratégie de comparaison : `JSON.stringify` du snapshot vs lecture
courante du DOM. Suffisant pour notre cas (titres + tableaux de
sections + arrays simples).

Mapping interne `type → préfixe DOM` :
- `exercice` → `atl-exo-...`
- `notion` → `atl-notion-...`
- `methode` → `atl-methode-...`
- `fiche_resume` → `atl-fiche-...`

### 2. Modale 3 boutons

Élément `<div id="atl-garde-modale">` créé à la volée, fond
semi-transparent, contenu centré avec :
- Titre « Modifications non sauvegardées »
- Liste des ateliers concernés (Exercice, Notion, Méthode, Fiche de
  résumé) — peut en afficher plusieurs simultanément
- Boutons « Sauvegarder », « Ne pas sauvegarder », « Annuler »
- Échap = Annuler

Si plusieurs ateliers ont des modifs simultanées, la modale les
sauvegarde en parallèle via `Promise.all`.

### 3. Détection des échecs silencieux

Les fonctions `atelXxxSauvegarder()` de chaque atelier captent leurs
erreurs en interne (toast + return undefined) sans rejeter la Promise.
Pour ne pas perdre les modifs lors d'une transition après échec, la
garde vérifie **après** le `Promise.all` que les snapshots ne sont
plus marqués comme modifiés. Si un atelier est encore modifié, la
transition est avortée — l'utilisateur reste sur la page et voit le
toast d'erreur.

### 4. Pattern d'instrumentation par atelier

Pour chaque atelier (exercice, notion, methode, fiche) :

```js
// 1. Wrapper public passe par la garde
function atelExoNouveau() {
  atelGardeAvantTransition(_atelExoNouveauReel);
}
function atelExoCharger(id) {
  atelGardeAvantTransition(() => _atelExoChargerReel(id));
}

// 2. Implementation interne installe le snapshot
function _atelExoChargerReel(id) {
  // ... charge le formulaire ...
  atelSnapshotInstaller('exercice', _atelExoLireDom());
}

// 3. Lecture DOM dédiée à la garde
function _atelExoLireDom() {
  return { serie, nom, objectifs, variables, enonce, corrige };
}

// 4. Save : MAJ du snapshot après succès
async function atelExoSauvegarder() {
  // ... PUT/POST ...
  atelSnapshotInstaller('exercice', _atelExoLireDom());
}

// 5. Suppression : effacement
async function atelExoSupprimer() {
  // ... DELETE ...
  atelSnapshotEffacer('exercice');
}

// 6. Enregistrement (DOMContentLoaded)
atelGardeEnregistrerHandler('exercice', {
  lireDom:     () => _atelExoLireDom(),
  sauvegarder: () => atelExoSauvegarder(),
});

// 7. Écoute input/change pour MAJ du badge en temps réel
formExo.addEventListener('input',  () => atelGardeMajIndicateur('exercice'));
formExo.addEventListener('change', () => atelGardeMajIndicateur('exercice'));
```

### 5. Points de transition wrappés

| Transition                                    | Wrappé via                       |
|-----------------------------------------------|----------------------------------|
| Clic sur autre atelier (`atelSwitch`)         | `atelGardeAvantTransition`       |
| Clic sur autre item dans sidebar              | `atelXxxCharger` wrappé          |
| Création nouvel item                          | `atelXxxNouveau` wrappé          |
| Changement de portée                          | `atelPorteeSwitch` wrappé        |
| Changement niveau/séquence                    | `change` listener wrappé         |
| Onglets nav principale (Suivi/Admin/Pref/Aide)| `.tab` click listener wrappé     |
| Fermeture / actualisation navigateur          | NON (Q1-B)                       |

Pour le changement de niveau/séquence : la valeur du `<select>` est
**pré-restaurée** à sa valeur précédente avant d'appeler la garde,
puis re-posée à la valeur cible si l'utilisateur confirme. Cela évite
qu'un sélecteur affiche une valeur incohérente avec l'état réel
pendant l'affichage de la modale.

### 6. Points NON wrappés (volontairement)

- **L'atelier d'assemblage (Séquence)** : tout y est auto-sauvé via
  `onblur` (nom d'objectif, critères F/A/E) ou via les API direct
  (drag-and-drop, suppression). Pas d'état « modifié non sauvé ».
- **Les onglets internes Admin** : changement entre Import référence,
  Préférences, etc. ne sort pas de l'application — pas concerné par
  Q1-C strictement parlant. Et de toute façon, en venant **depuis**
  un atelier modifié, on est passé par la garde du clic sur l'onglet
  Admin.

---

## Indicateur visuel

Badge `<span class="atl-badge-modifie">modifié</span>` placé dans la
toolbar de chaque atelier, juste avant le badge état. Style :
fond jaune doux, texte brun, bordure dorée. Affiché uniquement quand
le snapshot diffère du DOM.

CSS dans `static/app.css` (section dédiée v0.10.6).

Mis à jour en temps réel sur chaque `input` / `change` du formulaire.

---

## Fichiers ajoutés / modifiés

### Nouveaux
```
static/atelier_garde_sortie.js          — module commun (252 lignes)
```

### Modifiés
```
static/app.css                          — CSS badge + modale
templates/index.html                    — 4 badges <span>, chargement script
static/app.js                           — wrappers Nouveau/Charger pour
                                          exo/notion/methode, MAJ snapshot
                                          après save, effacement après
                                          suppr, enregistrement handlers
                                          + listeners input/change,
                                          wrapper atelSwitch,
                                          wrapper atelPorteeSwitch,
                                          wrapper change sélecteurs,
                                          wrapper .tab click listener
static/atelier_fiche.js                 — wrappers Nouveau/Charger,
                                          atelFicheLireDomComplet,
                                          MAJ snapshot après save,
                                          effacement après suppr
```

---

## Test manuel après déploiement

### Scénarios principaux

**1. Modale à la sortie d'un atelier modifié**
- Atelier Exercice : sélectionner un exercice, modifier le nom.
- Vérifier que le badge « modifié » apparaît dans la toolbar.
- Cliquer sur l'onglet « Notion ».
- ✅ Modale apparaît avec « Exercice » listé.
- Cliquer « Annuler » → on reste sur l'exercice, badge toujours là.
- Cliquer « Sauvegarder » → exercice persisté, badge disparaît,
  bascule vers Notion.

**2. Création d'un nouvel item alors qu'on en édite un modifié (Q1-D)**
- Notion : ouvrir une notion, modifier le titre.
- Cliquer « + Nouvelle » dans la sidebar.
- ✅ Modale apparaît avec « Notion » listé.
- Cliquer « Ne pas sauvegarder » → modifs perdues, formulaire vide
  pour la création.

**3. Sélection d'un autre item dans la sidebar**
- Méthode : ouvrir M1, modifier le corps.
- Cliquer sur M2 dans la sidebar.
- ✅ Modale apparaît, on peut sauvegarder M1 puis ouvrir M2.

**4. Plusieurs ateliers modifiés simultanément**
- Notion : modifier (sans sauver).
- Exercice : aller dans Exercice, modifier.
- ✅ Badge « modifié » sur les deux toolbars.
- Cliquer sur l'onglet Suivi.
- ✅ Modale liste « Exercice, Notion » → Sauvegarder → les deux
  sauvés en parallèle.

**5. Changement de niveau/séquence**
- Fiche : ouvrir une fiche d'une séquence, modifier le titre.
- Changer la séquence dans le sélecteur de portée.
- ✅ Modale apparaît, le sélecteur reste sur la valeur précédente
  pendant l'affichage.
- Annuler → sélecteur reste sur la valeur d'origine, on continue
  d'éditer la fiche.
- Confirmer → sélecteur passe à la nouvelle valeur, atelier
  rechargé.

**6. Changement de portée**
- Modifier un atome.
- Cliquer sur le bouton de portée « Niveau ».
- ✅ Modale apparaît.

**7. Onglets navigation principale**
- Modifier un atome.
- Cliquer sur Suivi / Admin / Préférences / Aide.
- ✅ Modale apparaît à chaque fois.

**8. Pas de modale si pas de modif**
- Charger un atome sans rien modifier.
- Naviguer ailleurs.
- ✅ Pas de modale, transition directe.

### Cas limites

**9. Échec silencieux à la sauvegarde**
- Modifier une notion avec un titre invalide (ex. vide si validation).
- Cliquer ailleurs, choisir « Sauvegarder » dans la modale.
- ✅ Toast d'erreur affiché par l'atelier, **on reste** sur la
  notion, badge toujours présent.

**10. Tab navigateur fermé**
- Modifier un atome.
- Fermer l'onglet navigateur.
- ✅ Pas de garde (Q1-B). Modifs perdues silencieusement.

**11. Atelier d'assemblage (Séquence)**
- Aller dans l'atelier Séquence, faire des drops, modifier des
  critères, changer le nom d'un objectif.
- Naviguer ailleurs.
- ✅ **Pas de modale** — tout est auto-sauvé en continu via les
  appels API immédiats.

---

## Pièges connus

- **Comparaison `JSON.stringify`** : sensible à l'ordre des clés.
  Comme tous les snapshots sont produits par les helpers
  `_atelXxxLireDom()` qui construisent les objets dans le même ordre
  systématique, ça fonctionne. Si un futur refactoring change l'ordre
  des clés, il faut maintenir l'ordre stable côté `lireDom` ou passer
  à une comparaison plus robuste.

- **`_atelMethodeLireDomComplet` mute `ATL_METHODE_SECTIONS`** : à
  chaque appel (donc à chaque event `input`), on resynchronise les
  sections depuis le DOM. C'est légèrement coûteux mais garantit que
  les modifs en cours dans les textareas sont prises en compte dans
  le calcul du diff. Acceptable pour V1. Idem pour Notion et Fiche.

- **Aucun listener `beforeunload`** : un Ctrl+W ou un Ctrl+R
  navigateur perd les modifs sans avertissement. C'est le choix
  Q1-B. Si plus tard on veut le réactiver, ça se fait en 5 lignes
  dans le module garde.

- **Atelier d'assemblage non couvert** : si à l'avenir on ajoute des
  champs dans l'assemblage qui ne soient pas auto-sauvés (par
  exemple un futur formulaire d'édition de précédence avec validation
  explicite), il faudra étendre la garde à cet atelier-là.

---

## À venir

- **v0.10.6+ ou v0.10.7** : plan de travail par partie (Q4 spec
  validée précédemment) avec colonnes `nb_seances` sur `objectifs_v2`
  et `nb_seances_ra` sur `sequence_parties`.
- **v0.11.0** : génération PDF livret de séquence avec inclusion des
  fiches droppées + filigrane ÉPREUVE.
