# Redémarrage v0.13.7.2 — Éditeur LaTeX Phase 2a (JSON complet + engrenage)

## Périmètre

Première sous-livraison de la Phase 2 de l'éditeur LaTeX. Le cadrage
prévoyait 4 chantiers (JSON 9 contextes, navigateur images, générateur
tableau tblr, engrenage). Pour ne pas faire une livraison trop grosse,
on a découpé :

- **v0.13.7.2** (cette livraison) — JSON complet pour les 9 contextes
  + engrenage de masquage par groupe avec mini-modale et persistance
  localStorage.
- **v0.13.7.3** — Navigateur d'images.
- **v0.13.7.4** — Mini-générateur de tableau tblr.
- **v0.13.7.5+** — Aides Markdown (Phase 3 originale).

## Contenu de la livraison

### JSON complet pour les 9 contextes

Avant : 2 contextes pilotes seulement (exo-enonce, notion-corps). Les
7 autres affichaient un placeholder « disponible en v0.13.7.2 ».

Après : **9 contextes** ont leur barre d'outils, totalisant **15 groupes**
réutilisables :

| Contexte | Groupes affectés |
|---|---|
| `variables` | xint_definitions, xint_aleatoire, xint_conditionnel |
| `exo-enonce` | maths_inline, listes, cadre_eleve, mise_en_page, exercice_seq |
| `exo-corrige` | maths_inline, maths_display, listes, mise_en_page, correction |
| `notion-corps` | maths_inline, envs_seqenseigne, boites, mise_en_evidence |
| `methode-corps` | maths_inline, envs_seqenseigne, etapes, boites |
| `fiche-section` | maths_inline, listes, boites, mise_en_page |
| `carte-recto` | maths_inline, mise_en_page, image |
| `carte-verso` | maths_inline, mise_en_page, image |
| `theme-description` | mise_en_page, boites |

### Première mouture pédagogique — à corriger au fil de l'usage

Le contenu de chaque groupe (snippets, libellés) est une **proposition
de départ** basée sur mon analyse du paquet seqenseigne. Tu vas
probablement vouloir :
- Ajouter des items qui te manquent
- Retirer des items que tu n'utilises jamais
- Renommer pour mieux refléter tes habitudes
- Réorganiser les groupes affectés à chaque contexte

**Tout cela se fait directement dans
`appli/static/data/toolbar_seqenseigne.json`**. Le fichier est
rechargé à chaque ouverture de modale, donc pas besoin de relancer
l'app. Convention du fichier expliquée dans la clé `_meta`.

### Engrenage et masquage par contexte

Un nouveau bouton **⚙** apparaît dans le header de la modale, à droite
des onglets. Visible uniquement quand l'onglet « Outils » est actif
(les autres onglets n'ont pas de groupes configurables).

Au clic, une **mini-modale** s'ouvre (overlay au-dessus de la modale
principale) listant tous les groupes du contexte courant, avec une
case à cocher chacun. Décocher = masquer ce groupe dans ce contexte.

Boutons :
- **Tout afficher** : recoche toutes les cases (n'enregistre pas, il
  faut cliquer Valider ensuite)
- **Annuler** : ferme la mini-modale sans rien sauvegarder
- **Valider** : enregistre et re-rend le panneau Outils

### Persistance par contexte

Les préférences sont mémorisées dans `localStorage` :
- Clé : `ed-latex:groupes-visibles:<contexte>`
- Valeur : `{"<groupe>": true/false, ...}` (JSON)

Donc chaque contexte a sa propre liste de groupes visibles. Tu peux
par exemple cacher « xint_conditionnel » dans `variables` si tu ne
t'en sers jamais — la décision est conservée pour les sessions
suivantes, et ne touche pas aux autres contextes.

Si localStorage est indisponible (mode privé) ou corrompu, le
système tombe sur le défaut « tout visible ».

### Indicateur de groupes cachés

Quand au moins un groupe est masqué dans un contexte, un message
discret apparaît au bas du panneau Outils :

> « 2 groupes masqués — utiliser ⚙ pour configurer »

Pour ne jamais oublier qu'il y a des choses cachées.

## Fichiers livrés

```
MODIFIÉS
appli/static/data/toolbar_seqenseigne.json   (JSON Phase 2 complet, 9 contextes)
appli/static/editeur_latex.js                (engrenage + mini-modale + filtrage)
appli/static/app.css                          (+98 lignes : styles engrenage/mini-modale)
appli/doc/redemarrage_v0_13_7_2.md            (NEW)
```

Aucun fichier nouveau ni supprimé côté backend ou tests : c'est une
livraison purement frontale.

## Vérifications

- Suite pytest : **3247 passed, 5 skipped, 0 failed** (identique à v0.13.7.1)
- Sanity JS sur `editeur_latex.js` : OK
- Sanity JSON sur `toolbar_seqenseigne.json` : OK
- JSON contient bien 9 contextes et 15 groupes

## À tester chez toi

### Scénario A — Tous les contextes ont une barre d'outils

1. Ouvrir un atelier (Exercice, Notion, Méthode, Fiche, Carte, Thème).
2. Cliquer « ✎ Éditer » sur n'importe quel textarea.
3. Vérifier que l'onglet « Outils » contient désormais des groupes
   réels (plus de message « disponible en v0.13.7.2 »).

À tester en particulier sur :
- L'énoncé d'exercice (5 groupes)
- Le corrigé d'exercice (5 groupes — différents)
- Le corps d'une notion (4 groupes)
- Une section de fiche (4 groupes)
- Le recto d'une carte (3 groupes)
- La description d'un thème (2 groupes)
- Le champ « Variables » d'un exercice (3 groupes xint)
- Le champ « Variables » d'une carte (3 groupes xint, mêmes que ci-dessus)

### Scénario B — Masquer un groupe

1. Sur l'énoncé d'un exercice, cliquer « ✎ Éditer ».
2. Onglet « Outils » ouvert par défaut.
3. Cliquer le bouton ⚙ dans le header de la modale.
4. **Vérifier** : mini-modale s'ouvre, liste 5 groupes avec cases cochées.
5. Décocher « Réponse élève ».
6. Cliquer « Valider ».
7. **Vérifier** : panneau Outils re-rendu, « Réponse élève » disparu,
   indication au bas « 1 groupe masqué — utiliser ⚙ pour configurer ».

### Scénario C — Persistance entre sessions

1. Reprendre le scénario B (avec « Réponse élève » caché).
2. Cliquer « Annuler » pour fermer la modale principale.
3. Rouvrir n'importe quel exercice → cliquer « ✎ Éditer » sur l'énoncé.
4. **Vérifier** : « Réponse élève » est toujours masqué (persistance OK).
5. Recharger la page complète (F5).
6. Refaire l'étape 3.
7. **Vérifier** : toujours masqué.

### Scénario D — Persistance par contexte indépendante

1. Avec le scénario C en place, ouvrir le **corrigé** de cet exercice
   (contexte différent : `exo-corrige`).
2. Cliquer « ✎ Éditer ».
3. Onglet « Outils » : **vérifier** que les groupes du corrigé sont
   tous présents — la préférence sur « Réponse élève » dans
   `exo-enonce` ne touche pas `exo-corrige`.

### Scénario E — Mini-modale : Esc et clic sur fond

1. Ouvrir la mini-modale ⚙.
2. Décocher quelque chose mais sans valider.
3. Appuyer Esc.
4. **Vérifier** : la mini-modale se ferme, **la modale principale reste
   ouverte** (Esc ne descend pas au niveau principal pendant que la
   mini-modale est ouverte), aucune préférence n'est enregistrée.
5. Refaire l'étape 1.
6. Cliquer sur le fond grisé de la mini-modale.
7. **Vérifier** : idem, ferme la mini-modale uniquement.

### Scénario F — « Tout afficher »

1. Masquer 2-3 groupes via ⚙ + Valider.
2. Rouvrir ⚙.
3. Cliquer « Tout afficher ».
4. **Vérifier** : toutes les cases sont cochées **mais rien n'est
   enregistré tant qu'on n'a pas cliqué Valider** (UX standard :
   l'action peut être annulée).
5. Cliquer Annuler.
6. **Vérifier** : retour à l'état avec 2-3 groupes masqués.
7. Refaire 1-3.
8. Cliquer Valider.
9. **Vérifier** : tous les groupes redeviennent visibles.

## Restes pour la suite

- **v0.13.7.3** : Navigateur d'images (sera utilisé en particulier
  dans le groupe `image` qui contient pour l'instant juste
  `\includegraphics[width=…]{...}` à compléter à la main). Questions
  de cadrage à trancher à ce moment-là : quel dossier (outils/,
  appli/outils/, autre ?), quel chemin inséré dans le snippet.
- **v0.13.7.4** : Mini-générateur de tableau `tblr`. Mini-UI dans
  un sous-onglet ou modal d'option pour générer le code à partir
  de paramètres (lignes, colonnes, alignements, bordures).
- **v0.13.7.5+** : Aides Markdown (xint, tkz-euclide). Pipeline
  Markdown → HTML local.

## Notes sur la mouture du JSON

J'ai pris quelques libertés pédagogiques :
- **Groupe `xint_*`** pour `variables` : 3 groupes (définitions,
  aléatoire, conditionnel) qui couvrent les patterns les plus
  courants. Les variables de carte et d'exercice utilisent le même
  contexte donc bénéficient des 3.
- **Groupe `etapes`** pour méthode : minimaliste (juste 2 items —
  liste numérotée et « Étape ~: » en gras). À enrichir selon ce que
  tu utilises vraiment.
- **Groupe `image`** pour cartes : un seul item `\includegraphics`
  pour l'instant — sera vraiment utile quand le navigateur d'images
  sera là (v0.13.7.3).
- **Boîtes** est duppliqué entre 4 contextes (notion, méthode, fiche,
  theme-description) — c'est volontaire, c'est le même groupe
  réutilisé.
- **Carte-recto et carte-verso** ont exactement les mêmes groupes —
  ils pourraient être fusionnés en un contexte unique `carte-face`
  si tu préfères. Conservés distincts pour l'instant au cas où tu
  veuilles diverger plus tard.

À toi de retravailler ce JSON selon ton usage réel.
