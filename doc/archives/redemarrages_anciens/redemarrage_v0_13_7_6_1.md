# Redémarrage v0.13.7.6.1 — Stepper de largeur + premier pas refonte rendu PDF

## Contexte

Suite à la revue d'usage de v0.13.7.6, deux problèmes UI signalés dans
le générateur de tableau :
1. **Le slider de largeur de colonne n'apparaît pas** dans la modale
   (rectangle bleu pâle vide), donc la fonction « largeur relative »
   est invisible côté utilisateur.
2. **Les boutons d'alignement sont trop larges**, provoquant une
   scrollbar horizontale dans la modale.

Et un bug textuel : le tooltip de `\cellVert` parle de « Cellule verte »
alors que la commande crée une cellule à texte vertical.

Cette livraison apporte aussi la **première étape de la refonte du
rendu PDF** annoncée : auto-chargement du PDF si le cache est valide,
appliqué uniquement à l'atelier Carte d'automatisme dans cette
itération. L'extension aux 4 autres ateliers à rendu PDF (Exercice,
Notion, Méthode, Fiche) viendra en v0.13.7.6.2.

## Cadrage validé

### Patchs UI tableau

| Question | Réponse |
|---|---|
| Forme du contrôle de largeur | Stepper [−] ×N [+] (le slider n'est pas fiable selon le thème navigateur) |
| Style des boutons stepper | Carrés 24×24px, compteur monospace entre les deux |
| Tooltip \\cellVert | « Cellule verticale (à utiliser dans un tableau) » |

### Refonte rendu PDF

| Question | Réponse |
|---|---|
| Stratégie de déploiement | Carte d'abord (v0.13.7.6.1), 4 autres ateliers ensuite (v0.13.7.6.2) |
| Détection cache valide | Hash du .tex courant + check existence du fichier de cache |
| Convention DOM | Celle d'AtelierAtomique (HTML statique) |
| Compatibilité ascendante onclick globaux | Non — les fonctions globales rendreAtome* disparaîtront en v0.13.7.6.2 |

## Modifications

### Patchs UI tableau

#### Stepper [−] ×N [+]

Remplace le slider `<input type="range">` qui était invisible sur
certains navigateurs/thèmes (notamment Firefox sur PC pro Windows)
malgré le stylage explicite des pseudo-éléments `::-webkit-slider-*`
et `::-moz-range-*`.

Architecture :
- Le HTML rendu par `_construireLigneColonne` produit maintenant
  `<button>−</button> <span data-ratio="N">×N</span> <button>+</button>`
- Chaque clic sur les boutons met à jour `dataset.ratio` du span
  (clampé entre 1 et 4) ainsi que le texte affiché
- `_lireConfigColonnes` lit le ratio depuis `dataset.ratio` au lieu
  de `slider.value`

CSS : nouveau bloc `.ed-latex-tab-stepper-btn` (largeur fixe 24px,
fond clair, hover bleu). Les styles `.ed-latex-tab-slider*` deviennent
sans effet (plus aucun `<input type=range>` dans le HTML) mais sont
laissés en place pour éviter un gros diff de suppression — à nettoyer
en v0.14.

#### Boutons d'alignement à largeur fixe

`.ed-latex-tab-align` se voit ajouter `width: 28px; height: 28px;
flex: 0 0 auto`. Avant, le label HTML pouvait s'étirer librement,
créant des rectangles bleus de ~80px qui forçaient une scrollbar
horizontale dans la modale.

#### Tooltip \\cellVert

`"Cellule verte (à utiliser dans un tableau)"` →
`"Cellule verticale (à utiliser dans un tableau)"` dans le JSON
toolbar (groupe `mise_en_evidence`).

### Refonte rendu PDF — étape 1 (Carte uniquement)

#### Backend : nouvelle route `/info`

```
GET /api/cartes/<carte_id>/rendu-pdf/info
→ 200 JSON {cache_valide: bool}
  ou 404 JSON si la carte n'existe pas
```

Cette route :
1. Génère le `.tex` de la carte (rapide, lecture BDD + génération)
2. Calcule `hash_tex(tex)`
3. Vérifie l'existence du fichier `cache_dir/<hash>.pdf`
4. Retourne le booléen

**Important** : la route ne déclenche **jamais** `compiler_atome` — pas
de pdflatex. Coût serveur : quelques millisecondes (génération .tex
+ hashage + stat fichier). Si la génération du .tex échoue (cas rare),
on retombe en mode sûr (cache_valide=false, raison textuelle) pour que
le client puisse fallback sur le bouton Compiler.

#### Côté client : auto-chargement

`AtelierAtomique.basculerOnglet` est surchargée pour appeler
`verifierCacheEtAfficher()` quand on bascule vers l'onglet « Rendu PDF » :
1. GET `/info` → réponse `{cache_valide: bool}`
2. Si `true` → appelle `compilerRendu()` (qui sert depuis le cache,
   instantané). Le statut s'affiche « Chargement du PDF en cache… »
   puis « ✓ PDF servi depuis le cache »
3. Si `false` → laisse le placeholder en l'état, l'utilisateur clique
   sur « Compiler » comme avant

Tolérant aux erreurs réseau (try/catch silencieux) : si l'endpoint
n'est pas disponible, on retombe au comportement classique.

## Fichiers livrés

```
MODIFIÉS
  appli/static/data/toolbar_seqenseigne.json   (tooltip cellVert, version 0.13.7.6.1)
  appli/static/editeur_latex.js                 (stepper, lecture dataset, en-tête)
  appli/static/app.css                          (+60 lignes : stepper + align fixe)
  appli/static/atelier_atomique.js              (surcharge basculerOnglet, verifierCacheEtAfficher, statut auto)
  appli/routes/cartes_automatisme.py            (route GET /rendu-pdf/info)

NOUVEAUX
  appli/tests/test_v0_13_7_6_1_stepper_et_info.py  (15 tests)
  appli/doc/redemarrage_v0_13_7_6_1.md             (ce document)
```

## Vérifications

- pytest : **3356 passed, 5 skipped, 0 failed** (3346 baseline + 15
  nouveaux − 5 skipped)
- `node --check` sur les 2 JS modifiés : OK
- `python -c "import ast; ast.parse(...)"` sur la route Python : OK
- JSON validé (version 0.13.7.6.1, tooltip corrigé)

## À tester chez toi

### A — Stepper de largeur de colonne (le bug initial)

1. Ouvrir l'éditeur LaTeX dans n'importe quel champ.
2. Cliquer sur « ▦ Tableau » (rangée Générateurs).
3. **Vérifier** : sur chaque ligne de colonne, à droite des boutons
   d'alignement, on voit clairement :
   - un label « Largeur : »
   - un bouton « − » carré
   - un compteur « ×1 » en monospace
   - un bouton « + » carré
4. Cliquer plusieurs fois sur « + ». **Vérifier** : le compteur passe
   à ×2, ×3, ×4. Au-delà de ×4, le compteur reste à ×4.
5. Cliquer plusieurs fois sur « − ». **Vérifier** : le compteur
   redescend, sans aller en dessous de ×1.
6. Régler la col. 1 à ×3, valider. **Vérifier** que le LaTeX généré
   contient `colspec={X[c,3] X[c] X[c]}` (ratio 3 sur la 1re colonne).

### B — Boutons d'alignement compacts

1. Toujours dans la modale Tableau (mettre 6 colonnes pour stresser).
2. **Vérifier** : aucune scrollbar horizontale ne s'affiche dans la
   modale. Tous les éléments d'une ligne tiennent sur la largeur.
3. **Vérifier** : les 3 boutons d'alignement par ligne font ~28×28px
   chacun (et non ~80px comme avant).

### C — Tooltip \\cellVert corrigé

1. Ouvrir l'éditeur LaTeX sur une notion ou un exercice (n'importe
   quel contexte qui expose le groupe « Mise en évidence »).
2. Survoler le bouton `\cellVert`.
3. **Vérifier** : le tooltip dit « Cellule verticale (à utiliser dans
   un tableau) » et non « Cellule verte ».

### D — Auto-chargement du PDF — Carte d'automatisme

1. Ouvrir l'atelier Carte d'automatisme, choisir une carte.
2. Onglet Édition : faire une petite modification, sauvegarder.
3. Onglet Rendu PDF : cliquer sur « Compiler le rendu » (compilation
   classique, ~5-10s).
4. **Vérifier** : le PDF s'affiche, statut « ✓ Compilé en N ms ».
5. Aller sur Édition (sans rien modifier), puis revenir sur Rendu PDF.
6. **Vérifier** : **le PDF se charge automatiquement**, sans cliquer
   sur Compiler. Le statut affiche « Chargement du PDF en cache… »
   puis « ✓ PDF servi depuis le cache » en quelques dizaines de ms.

### E — Pas d'auto-chargement si cache invalide

1. Sur la même carte, modifier le texte du recto ou verso, sauvegarder.
2. Basculer sur l'onglet Rendu PDF.
3. **Vérifier** : pas d'auto-chargement (le contenu du recto a changé,
   le hash du .tex est différent, le cache n'est plus valide).
4. Le placeholder ou le bouton « Compiler » reste affiché normalement.
5. Cliquer sur Compiler → recompilation classique.

### F — Tolérance aux erreurs réseau

1. (Optionnel) Couper le réseau ou stopper le serveur Flask.
2. Cliquer sur l'onglet Rendu PDF d'une carte.
3. **Vérifier** : pas d'erreur visible, l'UI reste comme avant (le
   try/catch silencieux de `verifierCacheEtAfficher` absorbe l'échec
   GET /info, l'utilisateur garde l'option de cliquer sur Compiler).

## Reliquats notés

- **Tests JS automatisés** : le stepper et l'auto-chargement reposent
  sur la validation manuelle. Dette héritée de v0.13.7.5/6.
- **Styles slider CSS** : `.ed-latex-tab-slider*` et associés sont
  laissés en place dans `app.css` mais ne sont plus utilisés. À
  supprimer en v0.14 (workstream cleanup).
- **Module commun `rendu_pdf_commun.js`** : pour cette première
  itération, la logique de cache + auto-chargement vit directement
  dans `atelier_atomique.js`. Elle sera extraite en module commun à
  l'occasion de v0.13.7.6.2 (factorisation simultanée avec les 4
  autres ateliers à rendu PDF).

## v0.13.7.6.2 — Extension aux autres ateliers (prochaine livraison)

Périmètre prévu :
- **Backend** : nouvelles routes
  - `GET /api/atomes/<type>/<id>/rendu-pdf/info` (générique pour
    exercice/notion/méthode/fiche)
- **Module commun JS** : `static/rendu_pdf_commun.js` extrait depuis
  `atelier_atomique.js`, exposant une classe `RenduPdfPanneau`
  paramétrée par `{endpointBase, prefixe, getId}`
- **HTML** : `index.html` doit gagner pour chaque atelier
  exercice/notion/methode/fiche un bloc statique aligné sur la
  convention atelier_atomique :
  - `#atl-{type}-btn-compiler`
  - `#atl-{type}-rendu-status`
  - `#atl-{type}-pdf-iframe`
  - `#atl-{type}-rendu-erreur`
  - `#atl-{type}-rendu-placeholder`
- **rendu_atome.js** : devient mince, juste un branchement par type
  vers RenduPdfPanneau
- **Suppression** des fonctions globales `rendreAtomeTab`,
  `rendreAtomeLancer`, `rendreAtomeToggleTex`, `rendreAtomeScrollTo`
  (remplacées par les méthodes de RenduPdfPanneau)

## Prochaine étape après v0.13.7.6.2

**v0.13.8 — Retour au référentiel** : reprise du workstream v0.13
(création d'un référentiel de niveau, cf. roadmap).
