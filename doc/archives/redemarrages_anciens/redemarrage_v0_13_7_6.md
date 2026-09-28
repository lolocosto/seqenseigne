# Redémarrage v0.13.7.6 — Nettoyage UI ateliers + slider tableau visible

## Contexte

Suite à la livraison v0.13.7.5 (icônes SVG, picker de taille, lettres
calligraphiques, générateur de tableau), une revue d'usage a remonté
plusieurs points à corriger sur les 5 ateliers de saisie et sur le
générateur de tableau.

## Cadrage validé

### Slider de largeur de colonne

| Question | Réponse |
|---|---|
| Forme du contrôle | Slider stylisé visiblement (rail bleu, poignée ronde) + label « Largeur : » devant |

Le slider natif est rendu en gris quasi invisible sur certains
navigateurs/thèmes (notamment Firefox sur PC pro Windows). Solution :
on cache l'apparence native (`-webkit-appearance: none`, `-moz-appearance: none`)
et on redessine via pseudo-éléments webkit (`::-webkit-slider-runnable-track`,
`::-webkit-slider-thumb`) ET firefox (`::-moz-range-track`, `::-moz-range-thumb`,
`::-moz-range-progress`).

### Groupe Listes

| Question | Réponse |
|---|---|
| Suppression du groupe « Listes » | Oui — redondant avec le générateur ☰ Liste qui gère déjà `nbCols` et les puces |
| Sort de seqColItem/seqColEnum dans Listes | Pas d'objet : ils restent accessibles via le générateur Liste |
| Sort des contextes qui référencent listes | Retirer la référence — les générateurs (QCM/Liste/Tableau) restent globaux à tous les contextes |

Le groupe est conservé dans le JSON (marqué `_obsolete_v0_13_7_6` avec
`items: []`) pour traçabilité. À supprimer définitivement en v0.14
(workstream cleanup).

### Champs obligatoires

| Atelier | Champs obligatoires |
|---|---|
| Exercice | titre, énoncé principal, corrigé principal |
| Notion | titre, corps |
| Méthode | titre, corps |
| Carte | titre, type pédagogique, type technique, recto, verso |
| Fiche | titre, et au moins une section avec titre + contenu non vides |

Niveau/séquence/série positionnés à la création et non modifiables après
— pas marqués ici. L'objectif (Fiche) vient de l'assemblage de séquence,
peut rester vide.

Convention : astérisque rouge classique (`<span class="atl-label-obligatoire">*</span>`)
juste après le texte du label. Légende explicative en bas de chaque
formulaire : « Les champs marqués d'une * sont obligatoires. »

### Suppressions de textes

| Atelier / Champ | Texte supprimé |
|---|---|
| Exercice / Variables (header repliable) | « (LaTeX libre, optionnel) » → bouton ✎ Éditer à la place |
| Exercice / Énoncé principal | « (LaTeX libre) » |
| Exercice / Corrigé principal | « (obligatoire) » (remplacé par *) |
| Exercice / Énoncé+corrigé remed | « (LaTeX libre) » |
| Notion / Corps | « (définition principale, LaTeX libre) » |
| Méthode / Corps | « (étapes de la méthode, LaTeX libre) » |
| Fiche / Zones | « (chaque zone produit un bloc dans la fiche imprimée) » |
| Carte / Recto | « LaTeX libre. TikZ inline supporté pour les figures. » |
| Carte / Verso | « LaTeX libre. Pour Pythagore : figure complétée avec valeurs. » |

L'atelier Thème conserve sa mention « (LaTeX libre) » (hors périmètre
des 5 ateliers concernés).

### Positionnement du bouton ✎ Éditer

| Atelier / Zone | Avant | Après |
|---|---|---|
| Exercice / Variables | Pas de bouton visible (textarea repliée) | Bouton dans le header, à la place de « (LaTeX libre, optionnel) ». `stopPropagation` pour ne pas déclencher le toggle. |
| Notion / item court (rows=2) | Bouton flottant en haut-droite → superposition avec ↑↓× | Bouton ✎ inline dans la zone `.atl-section-item-actions` |
| Méthode / item court (rows=2) | Idem Notion | Idem Notion |
| Fiche / section (rows=6) | Bouton flottant superposé avec × | Bouton ✎ inline dans la ligne d'actions du haut, à gauche du × |
| Carte / Recto+Verso | Bouton flottant en haut-droite | Bouton ✎ inline à côté du titre du cadre (« Recto (question) » / « Verso (réponse) ») |

## Architecture

### Convention « bouton ✎ manuel »

Quand le placement automatique du scanner global `EditeurLatex.scan()`
ne convient pas, on pose le bouton ✎ Éditer manuellement dans le HTML
de l'atelier et on marque le textarea avec
`data-ed-latex-attache="1"` pour que le scanner l'ignore.

Le bouton manuel utilise les nouvelles classes :
- `.btn-ed-latex-manuel` (taille standard, label « ✎ Éditer »)
- `.btn-ed-latex-manuel--compact` (taille réduite, label « ✎ » seul, pour
  les lignes d'items à `rows=2`)

Le clic du bouton appelle directement `EditeurLatex.ouvrir(textarea)`,
qui est l'API publique exposée depuis v0.13.7.1.

### Convention DOM pour le titre+bouton sur Carte

Nouvelle classe `.atl-cadre-titre-row` : `display: flex` qui aligne le
titre du cadre et le bouton ✎ sur la même ligne, avec `justify-content:
space-between`.

### Slider stylé v0.13.7.6

Le slider de largeur de colonne dans le générateur de tableau (modale
« ▦ Tableau ») est désormais entièrement stylé :

- Apparence native cachée : `-webkit-appearance: none`, `-moz-appearance: none`
- Rail : 6px de haut, fond `#d0d4dc` (gris clair), bordure arrondie 3px
- Rail rempli (Firefox uniquement) : couleur `#4a90e2` (bleu vif)
- Poignée : cercle bleu `#2c6cb0`, 16×16 (webkit) ou 14×14 (Firefox),
  bordure blanche 2px, ombre légère
- Au survol : poignée bleu foncé `#1f5a99`
- Au focus : halo bleu translucide autour de la poignée

La grille de la ligne d'une colonne passe de `60px auto 1fr` (v0.13.7.5)
à `60px auto auto 1fr` pour accueillir le nouveau label « Largeur : ».

## Fichiers livrés

```
MODIFIÉS
  appli/static/data/toolbar_seqenseigne.json    (v0.13.7.6, contextes nettoyés)
  appli/static/editeur_latex.js                  (label Largeur, tooltip Tableau)
  appli/static/app.css                           (~+170 lignes styles)
  appli/static/atelier_notion.js                 (bouton ✎ items)
  appli/static/atelier_methode.js                (bouton ✎ items)
  appli/static/atelier_fiche.js                  (bouton ✎ sections)
  appli/templates/index.html                     (asterisques, légendes, modifs labels)

NOUVEAUX
  appli/tests/test_v0_13_7_6_ui.py               (29 tests)
  appli/doc/redemarrage_v0_13_7_6.md             (ce document)
```

## Vérifs

- Suite pytest complète : **3314 passed, 5 skipped, 0 failed**
  (3290 baseline + 29 v0.13.7.6)
- `node --check` sur les 4 fichiers JS modifiés : OK
- JSON validé (`json.load`, version 0.13.7.6, groupe `listes` marqué
  obsolète, 0 contexte qui le référence)

## Scénarios à tester chez toi

### A — Slider largeur de colonne (le bug initial)

1. Ouvrir l'éditeur LaTeX dans n'importe quel champ.
2. Cliquer sur « ▦ Tableau » (rangée Générateurs).
3. **Vérifier** : sur chaque ligne de colonne, un label « Largeur : »
   est visible à droite des boutons d'alignement.
4. **Vérifier** : un slider gris avec une poignée bleue ronde est
   visible à droite du label.
5. Glisser la poignée. **Vérifier** : la valeur `×1` → `×2` → `×3` → `×4`
   s'affiche à droite, et la poignée se déplace bien.

### B — Groupe Listes retiré

1. Dans l'éditeur LaTeX, ouvrir le panneau Outils.
2. **Vérifier** : aucun groupe « Listes » entre les autres groupes
   (Mise en forme, Mise en page, Maths, etc.).
3. Cliquer sur l'engrenage ⚙.
4. **Vérifier** : la liste des groupes masquables ne contient plus
   « Listes ».
5. **Vérifier** : le bouton générateur « ☰ Liste » est toujours
   disponible en haut du panneau.

### C — Astérisques et légendes

1. Ouvrir un atelier Exercice neuf.
2. **Vérifier** : les labels « Titre », « Énoncé », « Corrigé » portent
   une astérisque rouge `*` après le texte.
3. **Vérifier** : les labels « Énoncé de remédiation » et « Corrigé de
   remédiation » N'ONT PAS d'astérisque (section optionnelle).
4. Faire défiler en bas du formulaire.
5. **Vérifier** : une légende « Les champs marqués d'une * sont
   obligatoires. » apparaît en italique sous une ligne de séparation.
6. Refaire le test sur Notion, Méthode, Fiche, Carte (chacun avec ses
   champs obligatoires propres — cf. tableau Cadrage).

### D — Suppressions de textes

1. **Vérifier** que les textes suivants ont disparu :
   - Exercice / Variables : plus de « (LaTeX libre, optionnel) »
   - Exercice / Énoncé : plus de « (LaTeX libre) »
   - Exercice / Corrigé : plus de « (obligatoire) » (remplacé par *)
   - Exercice / Remed énoncé/corrigé : plus de « (LaTeX libre) »
   - Notion / Corps : plus de « (définition principale, LaTeX libre) »
   - Méthode / Corps : plus de « (étapes de la méthode, LaTeX libre) »
   - Fiche / Zones : plus de « (chaque zone produit un bloc …) »
   - Carte / Recto : plus de « LaTeX libre. TikZ inline… »
   - Carte / Verso : plus de « LaTeX libre. Pour Pythagore … »

### E — Bouton ✎ Éditer Variables (Exercice)

1. Ouvrir un atelier Exercice, déplier le bloc Variables.
2. **Vérifier** : un bouton « ✎ Éditer » apparaît dans l'en-tête
   « Variables » à droite (à la place du texte parenthétique supprimé).
3. Cliquer dessus.
4. **Vérifier** : l'éditeur LaTeX s'ouvre sur la zone Variables avec
   le contexte `variables` (groupes xint visibles).
5. Cliquer sur le chevron ou ailleurs dans l'en-tête (PAS sur le
   bouton).
6. **Vérifier** : le bloc Variables se replie/déplie normalement.
   Le bouton ✎ ne doit PAS déclencher le toggle (`stopPropagation`).

### F — Bouton ✎ Éditer sur items courts (Notion/Méthode)

1. Ouvrir un atelier Notion, ajouter une section, ajouter quelques
   items (rows=2).
2. **Vérifier** : chaque item a une zone d'actions à droite avec
   `✎ ↑ ↓ ×` alignés horizontalement.
3. **Vérifier** : aucun bouton ✎ ne flotte en haut-droite du textarea
   (plus de superposition avec ↑↓× comme avant).
4. Cliquer sur ✎ d'un item.
5. **Vérifier** : l'éditeur LaTeX s'ouvre avec le contenu de CET
   item (pas un autre).
6. Refaire le test sur l'atelier Méthode.

### G — Bouton ✎ Éditer sur Fiche

1. Ouvrir un atelier Fiche, ajouter une zone.
2. **Vérifier** : sur la ligne du haut de la zone, on a : `[sélecteur de
   titre] [ ✎ Éditer ] [ × ]` alignés.
3. **Vérifier** : aucun bouton ne flotte en haut-droite du textarea.
4. Cliquer sur ✎ Éditer.
5. **Vérifier** : l'éditeur LaTeX s'ouvre sur le contenu de CETTE zone.

### H — Bouton ✎ Éditer sur Carte Recto/Verso

1. Ouvrir un atelier Carte automatisme.
2. **Vérifier** : à droite du titre « Recto (question) », un bouton
   « ✎ Éditer ». Idem pour « Verso (réponse) ».
3. Cliquer sur ✎ du Recto.
4. **Vérifier** : l'éditeur LaTeX s'ouvre avec le contexte `carte-recto`.

## Reliquats notés

- **Atelier Thème** : conserve sa mention « (LaTeX libre) » sur le
  champ Description. Hors périmètre des 5 ateliers concernés par cette
  livraison. À recadrer si besoin futur.

- **Atelier Carte / Variables xint** : non modifié (toujours avec son
  paragraphe explicatif). La zone reste optionnelle (visible seulement
  si type technique = paramétrée). Le scanner pose son bouton ✎
  automatique à côté du titre du cadre (comportement v0.13.7.5
  inchangé). Si on veut l'aligner sur le pattern Recto/Verso en
  v0.14, c'est mécanique.

- **Slider sur navigateurs très anciens** : les sélecteurs webkit/firefox
  couvrent Chrome/Edge/Firefox/Safari récents. IE11 et Opera Mini ne
  sont pas ciblés (l'appli n'est pas testée dessus de toute façon).

## v0.13.7.6.1 — Refonte rendu PDF (prochaine livraison)

Préparation prévue pour la livraison suivante : factorisation des
deux flux de rendu PDF aujourd'hui divergents :

- `static/rendu_atome.js` (exercice / notion / méthode / fiche)
- `AtelierAtomique.compilerRendu()` dans `static/atelier_atomique.js` (carte)

Cible : un module unique `static/rendu_pdf_commun.js` avec convention
DOM unifiée (`#{prefixe}-pdf-iframe`, `#{prefixe}-btn-compiler`,
`#{prefixe}-rendu-status`, `#{prefixe}-rendu-erreur`).

Comportement cible :
- À l'ouverture de l'onglet Rendu PDF, appel léger à
  `GET /api/atomes/<type>/<id>/rendu-pdf/cache-status` (nouveau)
- Si `cache_valide=true` → fetch direct du PDF (instantané)
- Sinon → bouton « Compiler le rendu » comme aujourd'hui

Backend à ajouter : route `cache-status` qui régénère le `.tex` et
vérifie l'existence du PDF de cache via `hash_tex` (rapide, pas de
pdflatex).

Périmètre : tous les ateliers à rendu PDF (Exercice, Notion, Méthode,
Fiche, Carte).

## Prochaine étape après v0.13.7.6.1

**v0.13.8 — Retour au référentiel** : reprise du workstream v0.13
(création d'un référentiel de niveau, cf. roadmap).
