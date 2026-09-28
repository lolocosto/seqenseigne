# seqenseigne — Doc de redémarrage

**Dernière mise à jour** : 28 avril 2026 (soir)
**État final de la session** : v0.9.3 livrée, déployée et validée. La
chaîne complète **Préférences chemins → édition variables → Tab/hauteur
fixe → compilation par lot** fonctionne en bout-en-bout.

**Score compilations atomes (v0.9.3)** :
- N10 méthodes : 56/56 ✓
- N11 méthodes : 56/56 ✓ (sur les 56 uniques après dédoublonnage de la session précédente)
- N12 méthodes : 42/44 ✓ (2 atomes vides cohérents avec le workflow)
- N10 exercices : 242/242 ✓
- N11 exercices : à compiler
- N12 exercices : à compiler (en cours d'enrichissement, complétion des corrigés)

---

## Vue d'ensemble du projet

`seqenseigne` est une **app Flask + SQLite** qui pilote un **paquet
LaTeX éponyme** (forge.apps.education.fr/laurentcoste/seqenseigne).

Architecture côté appli :
- BDD `data/seqenseigne.db` qui contient les **atomes pédagogiques**
  (notions, méthodes, exercices) ainsi qu'une copie **inlinable** du
  paquet LaTeX (`paquet_definitions`, `paquet_requirepackage`).
- **Compilation isolée d'un atome** : au lieu de `\usepackage{seqenseigne}`
  qui tirerait ~110 paquets, on calcule la **fermeture transitive** des
  définitions effectivement utilisées et on les inline dans le préambule.
  Gain × 2-3 sur le temps de compilation.
- **Cache PDF** : chaque atome est hashé (SHA256 du `.tex` complet) et
  son PDF stocké dans `data/cache_rendus/`. Ré-utilisé tant que le tex
  ne change pas.
- **Compilateur batch** (v0.8) : traite N atomes en série, écrit un
  rapport Markdown, conserve les `.tex` + `.log` des échecs dans
  `data/cache_rendus/echecs/`.
- **Configuration** : `data/configuration.json` avec une racine commune
  `chemin_racine_seqenseigne` (v0.9) dont dérivent tous les autres
  chemins, modifiables via UI Préférences. Permet de basculer
  D:\ ↔ E:\ entre PC maison et PC travail en changeant un seul champ.

Périmètre BDD au moment du redémarrage :
- N10 : 64 notions, 57 méthodes, 242 exercices
- N11 : 39 notions uniques, 57 méthodes, 281 exercices
- N12 : 24 notions, 44 méthodes, 279 exercices (en complétion)

---

## Versions livrées dans la session (v0.9 → v0.9.3)

Toutes livrées par ZIP dans `/mnt/user-data/outputs/`, déployées et
validées par Laurent.

| Version | Apport |
|---|---|
| **v0.9** | Déménagement onglet Compilation → Ateliers > Rendu par lot. Section Chemins dans Préférences avec racine + 4 dérivés (sources livrets, pdflatex, paquet, ref séquences) et override par champ via checkbox étatée. Endpoint `/api/configuration/chemins-resolus` qui applique la dérivation côté backend. |
| **v0.9.1** | 3 fixes après batch méthodes du 27/04. (1) `\seqInitAnnexes` + `\seqAfficheAnnexes` autour des notions et méthodes, comme déjà fait pour les exercices, pour ouvrir `\annfile` quand `\seqAnnexe` est utilisé (couvre N11/S04/M01-02, N12/S04/M02). (2) Mapping `\wideparen` corrigé vers `yhmath` (paquet réel) au lieu de `wideparen` (paquet inexistant), couvre N11/S11/M02-04 et N12/S11/M02. (3) Bibliothèques tabularray paramétrables `tblr_libraries` (défaut `booktabs,varwidth`), pendant frontal de `tikz_libraries` ; depuis tabularray v2025A, la clé `measure=vbox` requiert `\UseTblrLibrary{varwidth}`. |
| **v0.9.2** | Champ Variables dans le formulaire d'édition d'exercice. Aucune modif backend (`variables` était déjà géré). Permet de saisir `\xintdef...`, `\newcommand{\touche}`, `\tikzstyle{axe}` propres à un exo. Faux départ corrigé : Jinja2 plantait sur `{#1}` dans le placeholder, simplifié à un seul exemple sans `{#`. |
| **v0.9.3** | 3 fixes UX dans les ateliers. (1) **Tab/Shift+Tab/Esc** dans les textareas LaTeX via délégation document : Tab insère 2 espaces, Shift+Tab désindente, Esc + Tab préserve la navigation HTML pour l'accessibilité. (2) **`tab-size: 2`** sur `textarea.latex-textarea` (au lieu de 8 par défaut). (3) **Hauteur fixe paramétrable** `atl_textarea_lignes` (défaut 25, plancher 5) — remplace l'autosize qui faisait défiler le formulaire à chaque saut de ligne. UI dans Préférences. |

---

## Bilan technique de la session

### Bugs structurels corrigés (v0.9.1)

1. **`\seqInitAnnexes` jamais appelé pour notion/méthode** (`generer_corps_notion`
   et `generer_corps_methode` dans `services/latex_rendu_atome.py`). Effet
   visuel zéro pour les atomes sans `\seqAnnexe` (le `\ifnumcomp{\theAnnexeNum}{=}{0}{}{...}`
   saute le contenu).
2. **Mauvais mapping macro→paquet** dans `MACROS_PAQUETS_EXTERNES` :
   `\wideparen` venait de `yhmath`, pas d'un paquet `wideparen` qui
   n'existe pas sur CTAN.
3. **Bibliothèques tabularray non configurables** : `\UseTblrLibrary{booktabs}`
   était codé en dur dans `INITIALISATIONS_BIBLIOTHEQUES['tabularray']`,
   pas moyen d'ajouter `varwidth` sans toucher au code. Migration vers
   `tblr_libraries` paramétrable.

### Modélisation des variables (v0.9.2 → manuel par Laurent)

Le champ `variables` des exercices était au peuplement initial
**dupliqué** : chaque exercice de N10/S03 contenait les variables de
A01..A07. La v0.9.3 prévue (script de migration auto-déduisant les vars
réellement utilisées) a été annulée car Laurent a fait le ménage à la
main sur N10 et N11. Si une vague de N12 ou autre nécessite à nouveau
ce travail, l'option de migration auto reste sur la table.

### UX d'édition LaTeX (v0.9.3)

L'autosize (v0.6.4) faisait défiler tout le formulaire à chaque saut de
ligne dans les zones volumineuses (variables, énoncé, corrigé). Détecté
en complétant les corrigés N12. Solution : hauteur fixe paramétrable +
hook Tab pour indentation propre.

---

## Score atomes — état v0.9.3

```
N10 méthodes       : 56 / 56     (100%)  ✓
N11 méthodes       : 56 / 56     (100%)  ✓
N12 méthodes       : 42 / 44     (95%)   — 2 atomes vides (workflow normal)
N10 exercices      : 242 / 242   (100%)  ✓
N11 exercices      : à compiler
N12 exercices      : à compiler (en complétion des corrigés)
N10 + N11 + N12 notions : 127 / 127 (100%) ✓ (depuis v0.8.6)
```

---

## À faire au prochain démarrage

### 1. Compilation des exercices N11

Procédure : Ateliers > Rendu par lot → filtre `type=exercice, niveau=N11`.

**Bibliothèques à avoir dans le champ tikz** : `babel,shapes.geometric,arrows.meta,positioning,calc,matrix,fit` (les 4 premiers sont par défaut, `matrix` et `fit` ont été ajoutés par Laurent en v0.9.x pour N10/S11/A02). Au cas par cas, ajouter d'autres libs si une nouvelle erreur `'/tikz/...' unknown` apparaît.

Probablement quelques échecs à creuser ensemble. Procédure :
- Laurent envoie le rapport MD + le ZIP de `data/cache_rendus/echecs/`.
- Classement par famille d'erreur.
- Fix au cas par cas : (a) champ Variables de l'exo si une macro perso
  est utilisée, (b) bibliothèque tikz/tabularray à ajouter dans Rendu
  par lot, (c) patch appli en dernier recours si bug structurel.

### 2. Compilation des exercices N12

Idem, après finition des corrigés en cours d'enrichissement.

### 3. Items roadmap notés en mémoire

Trois items pour plus tard, non bloquants :

- **Production de docs annuels** (cours, exercices, plans de travail) :
  compilation des atomes assemblés. À placer dans une des 3 granularités
  d'ateliers (séquence/niveau/cycle), à concevoir avec Laurent. Pour
  l'instant le Rendu par lot fait l'affaire.
- **Comparaison visuelle automatique de PDFs** pour valider les imports
  d'atomes. Diff page à page entre livrets générés et PDFs validés
  précédents. Pistes : `diff-pdf` ou `pdftoppm` + ImageMagick `compare`.
  Probablement Admin > BDD ou nouveau sous-onglet dédié.
- **UI Ateliers — distinction séquence/cycle** : signaler visuellement
  la portée des sous-onglets. Séquence (notion, méthode, exercice,
  séquence-niveau, fiche de résumé future) vs Cycle (thème, séquence-cycle).
  Le bouton Rendu par lot est transversal — donc 3 groupes possibles.

### 4. Items roadmap déjà notés (sessions précédentes)

- **Option compilation dyslexie** : xeLaTeX + OpenDyslexic + A3 +
  LetterSpace=20 + WordSpace=1.5 + baselinestretch=1.2 + unicode-math /
  latinmodern-math.otf. Bloc commenté dans le `.tex` à activer à la
  demande.
- **Forcer l'affichage PDF dans l'iframe** `.rendu-pdf-iframe`,
  indépendamment des paramètres Firefox. Symptôme : Firefox du PC
  travail ouvre le rendu PDF dans une nouvelle fenêtre. Côté serveur
  déjà OK (pas de Content-Disposition: attachment). Pistes :
  `pdfjs.disabled=true`, GPO DSI, CSP. Solution probable : embarquer
  PDF.js comme lib tierce pour rendu indépendant.
- **Bug latent `_paquets_externes_optionnels`** qui ignore `envs_atome`
  (signalé v0.8.6, non bloquant en prod).

---

## Cheat sheet pour reprendre le code

### Fichiers clés modifiés v0.9 → v0.9.3

```
appli/services/
├── configuration.py               # +chemin_racine_seqenseigne, +chemin_paquet,
│                                  #  +chemin_reference_sequences (v0.9),
│                                  #  +tblr_libraries (v0.9.1),
│                                  #  +atl_textarea_lignes (v0.9.3),
│                                  #  +helpers tblr_libraries(),
│                                  #  atl_textarea_lignes(),
│                                  #  _resoudre_chemin() (v0.9)
├── paquet_parseur.py              # mapping \wideparen → yhmath (v0.9.1)
├── latex_rendu_atome.py           # \seqInitAnnexes/\seqAfficheAnnexes
│                                  # autour notion+méthode (v0.9.1),
│                                  # +param tblr_libraries (v0.9.1)
├── preambule_atome.py             # +param tblr_libraries (v0.9.1),
│                                  # tabularray retiré d'INITIALISATIONS_BIBLIOTHEQUES
├── compilation_batch.py           # +param tblr_libraries (v0.9.1)

appli/routes/
├── admin.py                       # Compilation route inchangée (v0.9),
│                                  # +tblr_libraries dans preview/run (v0.9.1)
├── rendu_atome.py                 # +/api/configuration/chemins-resolus (v0.9),
│                                  # +tblr_libraries=config.tblr_libraries() (v0.9.1)

appli/static/
├── app.js                         # +atelSwitch('rdl'), +adminSousOnglet retire 'compilation' (v0.9),
│                                  # +6 fonctions Préférences chemins (v0.9),
│                                  # +adminPreremplirChemins (v0.9),
│                                  # +rdl-tblr-libs (v0.9.1),
│                                  # +variables dans atelExoRemplir/Sauvegarder (v0.9.2),
│                                  # +_ATL_TEXTAREA_LIGNES, atelAppliquerHauteurLatex,
│                                  #  prefChargerHauteurLatex, prefEnregistrerHauteurLatex (v0.9.3)
├── atelier_commun.js              # +atelierFixerHauteurLatex/Tous,
│                                  #  hook Tab/Shift+Tab/Esc,
│                                  #  skip latex-textarea dans autosize (v0.9.3)
├── app.css                        # +textarea.latex-textarea (tab-size: 2) (v0.9.3)

appli/templates/
└── index.html                     # Compilation déplacée vers atl-rdl (v0.9),
                                   # +section Chemins dans Préférences (v0.9),
                                   # +rdl-tblr-libs (v0.9.1),
                                   # +champ Variables dans atelier exercice (v0.9.2),
                                   # +classe latex-textarea sur 5 textareas,
                                   #  +section hauteur LaTeX dans Préférences (v0.9.3)

appli/tests/
├── test_configuration.py          # +TestResolutionRacineV09 (10),
│                                  #  +TestTblrLibrariesV091 (7),
│                                  #  +TestAtlTextareaLignesV093 (6) — total 41
├── test_route_rendu_atome.py      # +TestApiCheminsResolus (4) — total 16
├── test_paquet_parseur.py         # +TestMacrosPaquetsExternesV091 (2) — total 37
├── test_latex_rendu_atome.py      # +TestInitAnnexesV091 (8) — total 85
├── test_preambule_atome.py        # +TestTblrLibrariesV091 (6),
│                                  #  4 tests adaptés à la migration tabularray
└── (pas de tests pour v0.9.2 et v0.9.3 côté UI : modifs purement frontales)

appli/doc/
├── patch_v0_9.md                  # Déménagement Compilation + chemins
├── patch_v0_9_1.md                # Annexes + wideparen + tblr_libraries
├── patch_v0_9_2.md                # Champ Variables
└── patch_v0_9_3.md                # Tab + tab-size + hauteur fixe
```

### Procédure de livraison

1. Démarrer dans `/home/claude/livraison_v0XY/appli/` (copie depuis la
   version précédente déployée).
2. Modifier les fichiers nécessaires.
3. Sanity check Python ponctuels (`python -c "from app import create_app; ..."`).
4. Lancer la suite de tests par lots de 5-10 fichiers (timeout 60-120s).
5. Note de patch dans `doc/patch_v0_X_Y.md`.
6. ZIP : `cd /home/claude/livraison_v0XY && zip -rq seqenseigne_v0XY_patch.zip appli/ -x "*.pyc" "*__pycache__*" "*.db.bak*"`
7. `cp seqenseigne_v0XY_patch.zip /mnt/user-data/outputs/`
8. `present_files` pour exposer à Laurent.

### Pièges connus (réactualisés)

- **Faire le ZIP tôt** dans le cycle, pas en dernier — la limite d'usage
  des outils peut tomber juste avant.
- **Mocks dans les tests `test_route_compilation_batch.py`** : `lambda
  conn, t, i, r, **kw: "tex"` (avec `**kw`) pour tolérer les nouveaux
  paramètres ajoutés. **4 tests préexistants cassés** dans ce fichier
  depuis v0.8.5, hors scope (mocks sans `**kw`). À corriger un jour
  séparément.
- **Cache PDF** : invalidé automatiquement à chaque changement du
  préambule ou des variables (le hash SHA256 change).
- **Configuration** : `Configuration(data_dir)` prend un dossier, pas
  un fichier. Le fichier est `data_dir / 'configuration.json'`.
- **Compilation `ok=True`** : critère = fichier `atome.pdf` produit, PAS
  le code retour pdflatex. Donc des erreurs non-fatales peuvent quand
  même donner un succès. Piège pour la divergence entre TeX Live
  (tolérant, env Linux Anthropic) et MiKTeX (strict, env Laurent).
- **Jinja2 et `{# ... #}`** (v0.9.2) : le séparateur `{#` est interprété
  comme début de commentaire Jinja même dans les attributs HTML
  (placeholder, value, etc.). Si ça apparaît dans un placeholder LaTeX,
  Jinja exige un `#}` fermant ou il plante avec `Missing end of comment
  tag`. Idem `{{` (expression) et `{%` (bloc). Ne JAMAIS écrire ces
  séquences littérales dans `templates/index.html`.
- **Saisie LaTeX dans un atelier** : depuis v0.9.3, Tab insère 2 espaces
  dans les textareas `.latex-textarea`. Pour Tab natif (navigation),
  faire Esc puis Tab.

### Outils disponibles pour le diagnostic

- `pdflatex` est installé dans l'env Linux. TeX Live 2023 + babel-french
  + tkz-euclide + tabularray + vwcol + tcolorbox + yhmath + varwidth.
  Mais **pas scratch3 → simplekv** (S14 plante côté Anthropic mais OK
  côté Laurent sur MiKTeX).
- BDD réelle accessible : `/home/claude/appli/data/seqenseigne.db`.
- Logs de runs précédents souvent fournis par Laurent dans
  `/mnt/user-data/uploads/`.

### Configuration utilisateur courante

`data/configuration.json` au moment du redémarrage :
```json
{
  "chemin_racine_seqenseigne": "<E:\\... ou D:\\... selon PC>",
  "chemin_sources_livrets": "",
  "chemin_pdflatex": "",
  "chemin_paquet": "",
  "chemin_reference_sequences": "",
  "timeout_compilation_s": 30,
  "compilation_batch_max_erreurs_consecutives": 5,
  "tikz_libraries": "babel,shapes.geometric,arrows.meta,positioning,calc,matrix,fit",
  "tblr_libraries": "booktabs,varwidth",
  "atl_textarea_lignes": 25
}
```

(Les chemins vides sont dérivés automatiquement de la racine ; Laurent
peut overrider individuellement via Préférences > Chemins avec checkbox.)

---

## Récap pour reprendre la conversation

**Dire au démarrage** : « Reprenons après v0.9.3. Tous les niveaux passent
en compilation pour les notions et les méthodes (sauf 2 atomes vides
volontaires). N10 exercices passent à 100 %. À attaquer : N11 puis N12
exercices. »

**Les fixes acquis dont les futurs atomes bénéficieront** :
- `\seqInitAnnexes` automatique pour notion+méthode (v0.9.1)
- Mapping `\wideparen → yhmath` (v0.9.1)
- Champ Variables éditable par exo (v0.9.2) pour macros locales
- Bibliothèques tikz et tabularray paramétrables via Rendu par lot
- Hauteur fixe + Tab indentation dans la saisie LaTeX (v0.9.3)
- Préférences > Chemins pour basculer D:↔E: en un champ (v0.9)

**À surveiller** sur N11/N12 exercices :
- Macros perso non encore détectées → ajouter au champ Variables de l'exo.
- Nouvelles libs tikz/tabularray manquantes → ajouter dans Rendu par lot.
- Images manquantes dans `data/images/` : à régénérer via Admin > Images
  si nécessaire.
- Corrigés vides : workflow normal, signalés proprement par v0.8.4.

**Le contexte technique tient en quatre lignes** : préambule reconstruit
qui inline les définitions seqenseigne, cache PDF par hash SHA256 du
`.tex`, compilation batch SSE qui produit un rapport MD, configuration
centralisée avec racine commune et dérivés overridables.
