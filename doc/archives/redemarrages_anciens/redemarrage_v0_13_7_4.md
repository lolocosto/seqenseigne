# Redémarrage v0.13.7.4 — Navigateur d'images + élargissement modales

## Périmètre

Suite directe de v0.13.7.3 (wrapping de sélection + générateurs QCM/Liste).
Cette livraison ajoute :

1. **Navigateur d'images** : choisir une image depuis `data/images/`
   et insérer `\includegraphics{nom.png}` en un clic
2. **Élargissement des mini-modales** (+50%) demandé après usage
   réel des générateurs : 440px → 660px de large

## Décisions de cadrage actées

| Question | Réponse |
|---|---|
| Affichage | Liste par défaut (rapide), bouton bascule vers grille avec miniatures. Préférence persistée en localStorage (clé `ed-latex:images-vue`). |
| Chemin inséré | `\includegraphics{nom.png}` — nom + extension, sans dossier. Le `\graphicspath{{data/images/}{./images/}{./}}` du préambule (livret_sequence.py L1023) résout. |
| Options par défaut | Aucune. Snippet brut, l'enseignant ajuste à la main si besoin. |
| Placement bouton | Dans le groupe `image` du JSON (remplace l'item `\includegraphics` actuel). PAS de 4e bouton dans la rangée Générateurs (qui reste à 3 : QCM / Liste / Tableau). |

## Backend

### Nouveau service `services/images_navigateur.py`

Liste les fichiers du dossier `<data_dir>/images/` :
- Extensions reconnues : `.png`, `.jpg`, `.jpeg`, `.pdf` (whitelist, casse-insensible)
- Fichiers cachés (`.hidden.png`) exclus
- Sous-dossiers exclus (flat)
- Retour : `[{nom, taille}, ...]` trié par nom (ordre lexicographique)
- Dossier inexistant → liste vide (pas d'erreur)

### Nouvelles routes `routes/images.py`

- **`GET /api/images`** : retourne `{"images": [...]}`
- **`GET /api/images/preview/<nom>`** : sert le fichier image. Trois
  niveaux de validation :
  1. Caractères interdits dans le nom : `..`, `/`, `\\`, début par `.`
  2. Whitelist d'extensions
  3. Résolution du chemin et vérification qu'il est bien dans
     `data/images/` via `relative_to()` (défense en profondeur)

  Si l'une des trois échoue → 404 sans détail.

### Enregistrement dans `app.py`

Import et ajout dans la liste de blueprints, après `bp_paquet`.

## Frontend

### Snippet spécial `__NAVIGATEUR_IMAGES__`

Convention introduite dans cette livraison (documentée dans le `_meta`
du JSON) : un snippet de cette valeur déclenche l'ouverture d'une
mini-modale au lieu d'une insertion classique. La fonction
`_gererClicSnippet()` aiguille selon la valeur du snippet.

Pour l'instant un seul snippet spécial. Si on en ajoute d'autres
(ex. générateur tikz, navigateur de fichiers .csv pour datatool…),
on étendra cette fonction. Pas de surcharge de design pour l'instant.

### Mini-modale type `image`

S'inscrit dans la dispatcher de `_ouvrirMiniModale(type)` existant
(v0.13.7.3). Bouton « Valider » masqué : l'insertion se fait au clic
direct sur une image. Bouton « Annuler » conservé pour fermer sans rien
faire.

Architecture interne :
- Cache JS `_imagesCache` : recharge la liste seulement à la 1re
  ouverture. Si Laurent ajoute une image en cours de session, il faut
  fermer/rouvrir l'éditeur. Acceptable pour l'usage hors ligne.
- Recherche live : filtrage par sous-chaîne, casse-insensible.
- Bascule liste/grille : préférence sauvegardée en localStorage.

### Élargissement modale (+50%)

`.ed-latex-conf-contenu` : `width: min(440px, 80vw)` →
`width: min(660px, 90vw)`. Et `max-height: 70vh → 80vh` pour faire de
la place aux vignettes du navigateur.

Effet de bord positif : les générateurs QCM et Liste profitent aussi
de la largeur supplémentaire, comme tu l'as demandé.

## Sécurité

La route `/api/images/preview/<nom>` est sensible (sert des fichiers
arbitraires depuis le disque). Couverture tests :

- `test_path_traversal_avec_dotdot_refuse` : `../secret.png` refusé
- `test_path_traversal_double_dotdot_refuse` : `../../etc/passwd` refusé
- `test_fichier_cache_refuse` : `.cache.png` refusé même si présent
- `test_extension_non_image_refuse` : `readme.txt` refusé même si présent
- `test_caractere_separateur_dans_le_nom_refuse` : encodages variés
  des séparateurs refusés

5 tests de sécurité sur 18 au total. Le pattern de défense en
profondeur (3 niveaux) est volontairement redondant : si l'un cède, les
autres rattrapent.

## Fichiers livrés

```
NOUVEAUX
appli/services/images_navigateur.py
appli/routes/images.py
appli/tests/test_v0_13_7_4_images.py
appli/doc/redemarrage_v0_13_7_4.md

MODIFIÉS
appli/app.py                                  (enregistrement bp_images)
appli/static/editeur_latex.js                 (mode image + interception)
appli/static/app.css                           (élargissement + styles navigateur)
appli/static/data/toolbar_seqenseigne.json    (snippet spécial __NAVIGATEUR_IMAGES__)
```

## Vérifications

- Suite pytest : **3285 passed, 5 skipped, 0 failed** (3267 baseline
  + 18 nouveaux)
- Tests de sécurité de la route preview : OK 5/5
- Sanity JS / JSON / Python : OK

## À tester chez toi

### Scénario A — Affichage en liste (vue par défaut)

1. Ouvrir l'éditeur LaTeX sur le recto d'une carte d'automatisme
   (contexte `carte-recto` qui contient le groupe `image`).
2. Dans le groupe « Image », cliquer sur « **🖼 Choisir une image…** ».
3. **Vérifier** : la mini-modale s'ouvre, plus large qu'avant (660px).
   La liste de tes images apparaît avec leur taille.
4. **Vérifier** : tri alphabétique, compteur en haut à droite.
5. Taper quelques caractères dans la recherche.
6. **Vérifier** : filtrage live.

### Scénario B — Bascule vers grille

1. Cliquer « **⊞ Grille** » dans la toolbar du navigateur.
2. **Vérifier** : passage à l'affichage en grille avec vignettes.
3. Fermer la mini-modale (Annuler ou Esc), puis rouvrir.
4. **Vérifier** : la préférence grille est mémorisée.

### Scénario C — Insertion d'une image

1. Vue liste : cliquer sur une ligne (par exemple `schema-thales.png`).
2. **Vérifier** : la mini-modale se ferme et `\includegraphics{schema-thales.png}`
   est inséré dans la zone d'édition.
3. Refaire en vue grille (clic sur une vignette).
4. **Vérifier** : même comportement.

### Scénario D — Compilation

1. Valider l'édition LaTeX (« OK — Réinjecter »).
2. Sauvegarder la carte.
3. Compiler.
4. **Vérifier** : l'image apparaît bien dans le PDF (le `\graphicspath`
   du préambule trouve `data/images/schema-thales.png`).

### Scénario E — Cas limite : dossier images vide

(à tester si tu as ce cas, sinon sauter)

1. Si `data/images/` ne contient aucune image, la mini-modale affiche
   « Aucune image dans data/images/. Importer des images via l'onglet
   Admin… ».

### Scénario F — Sécurité (curiosité)

Pas de test manuel à faire — la route est protégée par 3 niveaux de
validation, couverts par 5 tests pytest dans
`tests/test_v0_13_7_4_images.py`.

### Scénario G — Élargissement profite aux autres générateurs

1. Ouvrir le générateur QCM (« ⊞ QCM » dans la rangée Générateurs).
2. **Vérifier** : la modale est plus large qu'avant, la saisie est
   plus confortable (notamment pour le bloc Scoring dépliable).
3. Idem pour le générateur Liste (« ☰ Liste »).

## Reliquats notés

- **Cache des images non rafraîchi** : si tu ajoutes une image en
  cours de session, il faut fermer/rouvrir l'éditeur pour la voir.
  Acceptable pour l'usage hors ligne (USB), à reconsidérer si tu
  remontes du frottement.
- **Préchargement des miniatures** : actuellement le `<img loading="lazy">`
  fait le travail au scroll. Si tu as 100+ images, le premier passage
  en mode grille peut être un peu lent. Pas optimisé tant que ce n'est
  pas un problème mesuré.
- **Tests partiels / vrai code** (ton avertissement du jour) : tu m'as
  prévenu que tes tests sont partiels et que certaines choses
  apparaîtront en rédaction réelle. Je le note ici pour la traçabilité.

## Prochaine étape

**v0.13.7.5** — Générateur de tableau `tblr`. Le bouton « ▦ Tableau »
est déjà en place dans la rangée Générateurs (placeholder
« disponible en v0.13.7.5 »). Mini-modale à construire avec :
- Nombre de lignes / colonnes
- Type de colonnes (gauche, centré, droite, X[..])
- Filets (booktabs ? simple ? aucun ?)
- Caption / label éventuels

Questions de cadrage à trancher au début de la livraison.
