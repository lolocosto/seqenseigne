# Redémarrage v0.13.7.6.1.1.2 — Correction race condition rendu PDF carte

## Contexte

Après livraison de v0.13.7.6.1.1 :
- Point 2 (iframe résiduelle carte) **non résolu chez Laurent**
- Diagnostic via console.log (v0.13.7.6.1.1-diag) : le code fonctionne
  parfaitement quand instrumenté, mais le bug réapparaît sans logs.
  **Symptôme typique de race condition**.

## Diagnostic complet

Reconstitution du bug (sans logs) :

```
t=0    User clique carte A (avec cache)
t=0    basculerOnglet('rendu') → verifierCacheEtAfficher(A)
t=10   fetch GET /info/A en vol…
t=80   Réponse /info/A : cache_valide=true
t=80   verifierCacheEtAfficher(A) appelle compilerRendu(A)
t=85   fetch POST /rendu-pdf/A en vol…
t=200  User clique carte B (sans cache)
t=200  basculerOnglet('rendu') → verifierCacheEtAfficher(B)
       /!\ compilerRendu(A) toujours en vol /!\
t=210  fetch GET /info/B en vol…
t=270  Réponse /info/B : cache_valide=false
t=271  _remettrePlaceholderRendu() → iframe.display=none ✓
t=290  Réponse POST /rendu-pdf/A arrive !
t=291  iframe.src = blob:A, iframe.display = block
       ❌ Le PDF de A réapparaît sur l'écran de B
```

Avec les console.log : le timing change suffisamment pour que A
finisse AVANT B ne démarre. Le bug est masqué.

## Correction : compteur de génération

Pattern classique pour invalider les promesses asynchrones obsolètes :

```javascript
// État de classe (constructeur)
this._genRendu = 0;

// Au démarrage d'une exécution
const maGen = ++this._genRendu;

// Après chaque await
if (maGen !== this._genRendu) return;  // abandon silencieux
```

### Application dans `atelier_atomique.js`

**`verifierCacheEtAfficher`** :
- Incrémente `_genRendu` au démarrage
- Capture `maGen` localement
- Vérifie `maGen !== this._genRendu` après chaque `await` (fetch info,
  resp.json, et catch)
- Si génération obsolète → return silencieux, aucune modif UI

**`compilerRendu`** :
- Si appelée hors auto-cache (clic utilisateur direct) : incrémente
  `_genRendu` AUSSI pour invalider un éventuel `verifierCacheEtAfficher`
  en vol depuis un changement d'item antérieur
- Si appelée depuis `verifierCacheEtAfficher` (drapeau
  `_chargementAuto=true`) : pas d'incrément, on respecte la génération
  posée par l'appelant
- Capture `maGen` localement
- Vérifie après chaque `await` (fetch POST, resp.blob, resp.json) :
  - Si obsolète **avant** d'écrire dans iframe → return
  - Cas particulier : si `resp.ok && obsolète`, on consomme quand même
    le blob pour libérer la connexion proprement (sans l'utiliser)

**Pas de protection nécessaire dans `_remettrePlaceholderRendu`** :
elle est synchrone, elle s'exécute dans le même tick que l'appelant.

## Pourquoi ça marche

Quand le user clique B alors que `compilerRendu(A)` est en vol :
1. `++this._genRendu` → `_genRendu` passe à N+1
2. La promesse de A capturait `maGen = N`
3. Quand A obtient sa réponse, `N !== N+1` → return immédiat
4. Pas d'écriture dans `iframe.src` ni `iframe.style.display`
5. L'écriture de B (`_remettrePlaceholderRendu` ou nouvel auto-cache)
   est la dernière à s'exécuter, donc gagnante

## Fichier livré

```
MODIFIÉ
  appli/static/atelier_atomique.js
```

## Vérifs

- pytest : **3360 passed, 5 skipped, 0 failed** (aucun test cassé)
- `node --check` : OK
- Pas de nouveaux tests JS automatisés (race condition difficile à
  reproduire de manière déterministe en headless)

## Scénarios à valider chez toi

### A — Le scénario qui plantait

1. Ouvrir atelier Carte d'automatisme.
2. Cliquer sur une carte **A avec cache** → PDF s'affiche.
3. Aussitôt (sans attendre), cliquer sur une carte **B sans cache**.
4. **Vérifier** : le PDF de A ne réapparaît PAS, le placeholder de B
   reste affiché stablement.

### B — Cas où le cache est valide pour B

1. Carte A compilée, PDF affiché.
2. Cliquer carte B aussi compilée.
3. **Vérifier** : le PDF de B remplace celui de A, pas de flash résiduel.

### C — Clic utilisateur après auto-chargement

1. Carte A avec cache, PDF affiché automatiquement.
2. **Modifier le contenu** de A et sauvegarder (le cache devient invalide).
3. Basculer Édition → Rendu PDF.
4. **Vérifier** : le placeholder s'affiche (cache_valide=false).
5. Cliquer sur « Compiler le rendu ».
6. **Vérifier** : compilation normale, nouveau PDF affiché.

### D — Clics ultra-rapides

1. Avoir 5+ cartes dans la liste.
2. Cliquer rapidement plusieurs cartes successivement.
3. **Vérifier** : à la fin, le PDF (ou placeholder) affiché correspond
   à la **dernière** carte cliquée, jamais à une précédente.

## À noter

Cette correction porte sur la carte uniquement (`AtelierAtomique`).
**Quand v0.13.7.6.2 étendra ce mécanisme aux 4 autres ateliers (Exo,
Notion, Méthode, Fiche)** via le module commun `rendu_pdf_commun.js`,
le pattern de génération devra être appliqué de la même manière.

## Workstream v0.14 (rappel)

- Migration v1→v2 + suppression de la table `objectifs` v1
  (cf. redemarrage v0.13.7.6.1.1)

## Prochaine étape

v0.13.7.6.1.2 — Patch CSS « force-everything » pour le générateur de
tableau (boutons stepper invisibles à cause du thème système
Firefox/Windows).
