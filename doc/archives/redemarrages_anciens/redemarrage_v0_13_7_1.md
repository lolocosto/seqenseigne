# Redémarrage v0.13.7.1 — Éditeur LaTeX (Phase 1 — squelette)

## Périmètre

Première livraison du chantier éditeur LaTeX. Phase 1 = squelette
fonctionnel mais minimal côté contenu. La Phase 2 (v0.13.7.2)
remplira la barre d'outils pour tous les contextes ; la Phase 3
(v0.13.7.3) ajoutera les guides Markdown.

Cette livraison s'appuie sur la base saine obtenue après le fil
garde-de-sortie (v0.13.7.0a → v0.13.7.0e.2).

## Architecture

### Côté serveur

- **`services/paquet_expose.py`** (nouveau) : service de filtrage de
  la table `paquet_definitions`. Expose 4 fichiers sources (cœur,
  thème, exercices, cartes) pour 3 types LaTeX (command, environment,
  tcolorbox). Les macros internes (`@` dans le nom) et les fichiers
  utilitaires (`data.sty`, `legacy.sty`, `core-eval.sty`) sont exclus.
- **`routes/paquet.py`** (nouveau) : route `GET /api/paquet/definitions`
  qui renvoie un JSON groupé par fichier.
- **`app.py`** : enregistrement du nouveau blueprint `bp_paquet`.
- **`tests/test_v0_13_7_1_paquet.py`** (nouveau) : 9 tests qui
  vérifient le filtrage par type, par fichier, l'exclusion des
  macros internes, la préservation de `args_spec`, et la structure
  de la réponse.

Résultat de l'exposition (base prod actuelle) :

| Fichier | Commandes | Environnements | Tcolorbox | Total |
|---|---|---|---|---|
| Cœur (`seqenseigne-core.sty`) | 38 | 9 | 0 | 47 |
| Thème (`seqenseigne-theme.sty`) | 62 | 6 | 18 | 86 |
| Exercices (`seqenseigne-core-exos.sty`) | 10 | 3 | 0 | 13 |
| Cartes (`seqenseigne-carte-automatisme.sty`) | 1 | 0 | 0 | 1 |
| **Total** | **111** | **18** | **18** | **147** |

### Côté frontend

- **`static/editeur_latex.js`** (nouveau, ~400 lignes) :
  - API publique `window.EditeurLatex.scan(racine?)` et
    `window.EditeurLatex.ouvrir(textarea)`.
  - Scan idempotent (marqueur `data-ed-latex-attache`) des textareas
    avec attribut `data-contexte-latex`. Auto-scan au DOMContentLoaded.
  - Bouton « ✎ Éditer » apposé à droite du label. Variante compacte
    « ✎ » pour `rows ≤ 3` (cf. cadrage Phase 1).
  - Modale plein écran (`95vw × 90vh`) avec 3 onglets :
    - **Outils** : barre d'outils pédagogique par contexte
    - **Tout le paquet** : navigation 2-colonnes (fichier source ↔
      liste des items) avec génération de snippet `\nom{}{}` ou
      `\begin{env}{}…\end{env}` selon le type
    - **Aides** : placeholder Phase 1, contenu Phase 3
  - Raccourcis clavier : `Esc` = Annuler, `Ctrl+Enter` = OK.
  - Après OK, le textarea cible reçoit la nouvelle valeur, suivi
    d'un `dispatchEvent('input')` pour que la garde de sortie
    (snapshot-based, v0.13.7.0d) détecte la modification.
- **`static/data/toolbar_seqenseigne.json`** (nouveau) : config
  minimale Phase 1, 2 contextes pilotes (`exo-enonce`, `notion-corps`)
  avec leurs groupes d'outils.
- **`static/app.css`** : +240 lignes pour styler bouton, modale,
  onglets, panneaux, navigation paquet.
- **`templates/index.html`** :
  - `<script src="/static/editeur_latex.js">` chargé après
    `rendu_atome.js`.
  - `data-contexte-latex="<contexte>"` sur les 11 textareas statiques
    (exo-énoncé, exo-corrigé, exo-rem-énoncé, exo-rem-corrigé,
    exo-variables, notion-corps, méthode-corps, fiche-section,
    carte-recto, carte-verso, carte-variables, théme-description).

### Hook items dynamiques

Pour les textareas générées dynamiquement par les sections de notion
et méthode (et par les zones de fiche), modification de leur
`rendreSections()` / `_renderSections()` respectives :
- Ajout de `data-contexte-latex="<contexte>"` sur la balise
  `<textarea>` générée.
- Appel `window.EditeurLatex.scan(zone)` à la fin de la fonction de
  rendu, pour équiper les nouvelles textareas du bouton.

Pour la fiche, l'occasion a été prise de retirer le résidu
`oninput="ATELIER_FICHE.formChange()"` qui n'avait plus de sens
depuis v0.13.7.0d (le listener délégué de `AtelierEditeur` couvre
déjà ce textarea).

## Mapping contexte → textarea

| ID HTML | Contexte | Atelier |
|---|---|---|
| `atl-exo-variables` | `variables` | Exercice |
| `atl-exo-enonce` | `exo-enonce` | Exercice |
| `atl-exo-corrige` | `exo-corrige` | Exercice |
| `atl-exo-remed-enonce` | `exo-enonce` | Exercice |
| `atl-exo-remed-corrige` | `exo-corrige` | Exercice |
| `atl-notion-corps` | `notion-corps` | Notion |
| `atl-methode-corps` | `methode-corps` | Méthode |
| `atl-theme-description` | `theme-description` | Thème |
| `atl-carte-variables` | `variables` | Carte |
| `atl-carte-recto` | `carte-recto` | Carte |
| `atl-carte-verso` | `carte-verso` | Carte |
| items de section notion (dynamique) | `notion-corps` | Notion |
| items de section méthode (dynamique) | `methode-corps` | Méthode |
| zones de section fiche (dynamique) | `fiche-section` | Fiche |

9 contextes distincts (cf. cadrage). 2 contextes pilotes ont une
barre d'outils Phase 1 : `exo-enonce` et `notion-corps`. Les
7 autres affichent un placeholder « disponible en v0.13.7.2 » et
renvoient vers l'onglet « Tout le paquet ».

## Décisions actées dans cette livraison

### Filtrage backend des fichiers source

Trois fichiers sont **intentionnellement exclus** de l'onglet
« Tout le paquet » :
- `seqenseigne-data.sty` (36 commandes) : helpers d'accès à la base
  de données (CSV) — plomberie interne, pas pertinent en rédaction.
- `seqenseigne-legacy.sty` (8 commandes) : ancien système, à éviter
  pour les nouvelles rédactions.
- `seqenseigne-core-eval.sty` (4 commandes) : utilisé par le rendu
  des évaluations, peu pertinent en cours de rédaction d'atome.

**Si tu souhaites réintroduire certains de ces fichiers** dans
l'exposition, il suffit de modifier le dictionnaire `FICHIERS_EXPOSES`
en tête de `services/paquet_expose.py`.

### Textareas hors classe `latex-textarea`

Quatre textareas (`atl-theme-description`, `atl-carte-variables`,
`atl-carte-recto`, `atl-carte-verso`) acceptent du LaTeX libre mais
n'ont pas la classe `latex-textarea` (incohérence historique).
Décision : **laisser tel quel** pour cette livraison, l'éditeur
LaTeX se base uniquement sur `data-contexte-latex`. Si à l'usage tu
constates des comportements indésirables sur ces zones (pas de
Tab/Shift+Tab, etc.), on pourra ajouter la classe dans une livraison
ultérieure.

## Fichiers livrés

```
NOUVEAUX
appli/services/paquet_expose.py
appli/routes/paquet.py
appli/static/editeur_latex.js
appli/static/data/toolbar_seqenseigne.json
appli/tests/test_v0_13_7_1_paquet.py
appli/doc/redemarrage_v0_13_7_1.md

MODIFIÉS
appli/app.py                                 (enregistrement bp_paquet)
appli/static/app.css                         (+240 lignes : styles éditeur)
appli/static/atelier_notion.js               (data-contexte-latex + scan)
appli/static/atelier_methode.js              (idem)
appli/static/atelier_fiche.js                (idem + retrait oninput résiduel)
appli/templates/index.html                   (script + 11 data-contexte-latex)
```

## Vérifications

- Suite pytest : **3247 passed, 5 skipped, 0 failed** (3238 + 9
  nouveaux pour le service et la route paquet)
- Sanity JS sur tous les fichiers modifiés : OK
- Sanity JSON sur `toolbar_seqenseigne.json` : OK

## À tester chez toi

### Scénario A — Bouton « ✎ Éditer » apparaît

1. Ouvrir l'atelier Exercice, ouvrir un exercice existant.
2. **Vérifier** : le bouton « ✎ Éditer » apparaît à droite des labels
   « Variables », « Énoncé », « Corrigé », « Remediation > Énoncé »,
   « Remediation > Corrigé ».
3. Refaire dans Notion, Méthode, Fiche, Carte, Thème.

### Scénario B — Modale et onglet « Tout le paquet »

1. Cliquer « ✎ Éditer » sur un textarea.
2. **Vérifier** : la modale s'ouvre, contenu chargé.
3. Cliquer onglet « Tout le paquet ».
4. **Vérifier** : 4 fichiers (Cœur, Thème, Exercices, Cartes) listés
   à gauche. Cliquer Cœur → ~47 items à droite. Cliquer Thème →
   ~86 items dont 18 tcolorbox.
5. Cliquer un item (ex. `\seqFrac` dans Cœur).
6. **Vérifier** : le snippet `\seqFrac{}{}` est inséré dans la zone
   d'édition, curseur placé entre les premiers `{}`.

### Scénario C — Onglet « Outils » pilote

1. Sur un exo, cliquer « ✎ Éditer » de l'énoncé.
2. Onglet « Outils ».
3. **Vérifier** : 3 groupes apparaissent (Maths, Listes, Réponse élève).
4. Cliquer un outil (ex. `\frac`).
5. **Vérifier** : le snippet est inséré.

Sur une notion, le contexte est `notion-corps` → 3 groupes (Maths,
Environnements seqenseigne, Boîtes).

Sur un textarea avec un contexte non encore configuré (énoncé
exercice → OK ; mais corrigé exercice → contexte `exo-corrige`
encore vide en Phase 1), l'onglet Outils affiche un placeholder
« disponible en v0.13.7.2 » et renvoie vers l'onglet « Tout le
paquet ». **À tester sur le corrigé d'un exercice** pour vérifier.

### Scénario D — OK réinjecte et déclenche la garde

1. Sur un exo, cliquer « ✎ Éditer » d'un champ.
2. Modifier dans la modale.
3. Cliquer « OK — Réinjecter ».
4. **Vérifier** : la modale se ferme, le textarea contient le
   nouveau contenu, **le badge « modifié » s'allume** dans la
   toolbar de l'atelier (preuve que la garde a détecté le changement
   via `dispatchEvent('input')`).

### Scénario E — Items dynamiques de section

1. Sur une notion, ajouter une section, ajouter un item à cette
   section.
2. **Vérifier** : le textarea de l'item nouvellement créé a aussi
   le bouton « ✎ Éditer ».
3. Idem pour méthode et fiche.

### Scénario F — Raccourcis clavier

1. Ouvrir la modale.
2. `Esc` → ferme sans réinjecter.
3. Rouvrir, modifier, `Ctrl+Enter` → réinjecte et ferme.

## Restes pour la suite (Phase 2 et au-delà)

- **v0.13.7.2** : JSON complet pour les 9 contextes (barre d'outils
  pédagogique pour chaque type d'atome). Navigateur d'images
  (depuis le dossier `outils/` du dépôt). Mini-générateur de
  tableau `tblr`.
- **v0.13.7.3** : guides Markdown (xint, tkz-euclide), pipeline
  Markdown → HTML.
- **Possibilité offerte par l'architecture** : tu peux dès maintenant
  enrichir `toolbar_seqenseigne.json` (sans recompiler quoi que ce
  soit) pour étendre les contextes ou ajouter des groupes. Le
  fichier est rechargé à chaque ouverture de modale.

## Reliquat hors-périmètre noté

L'engrenage de masquage/persistance localStorage des groupes d'outils
(cf. cadrage initial) n'a pas été implémenté en Phase 1, **par
simplification** : avec seulement 2 contextes pilotes, l'utilité est
faible. Sera réintroduit en Phase 2 quand tous les contextes auront
leur barre d'outils.
