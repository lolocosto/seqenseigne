# seqenseigne — Doc de redémarrage

**Dernière mise à jour** : 26 avril 2026 (soir)
**État final de la session** : v0.8.6 livrée et déployée. **127/127
notions** (N10 + N11 + N12) compilent en isolation. 🎉

---

## Vue d'ensemble du projet

`seqenseigne` est une **app Flask + SQLite** qui pilote un **paquet
LaTeX éponyme** (forge.apps.education.fr/laurentcoste/seqenseigne).

Architecture côté appli :
- BDD `data/seqenseigne.db` qui contient les **atomes pédagogiques**
  (notions, méthodes, exercices) ainsi qu'une copie **inlinable** du
  paquet LaTeX (`paquet_definitions`, `paquet_dependances`,
  `paquet_requirepackage`).
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

Périmètre BDD au moment du redémarrage :
- N10 : 64 notions, 57 méthodes, 242 exercices
- N11 : 78 notions (39 uniques, **bug de doublonnage encore présent**),
  57 méthodes, 281 exercices
- N12 : 24 notions, 42 méthodes, 279 exercices

---

## Versions livrées dans la session

Toutes livrées par ZIP dans `/mnt/user-data/outputs/` (Laurent les a
toutes déployées et validées).

| Version | Apport |
|---|---|
| **v0.8** | Compilateur batch SSE (5 statuts), filtres type/niveau/séquence, paramètres timeout/max_erreurs in-place, rapport MD `Compilation_atomes_<date>.md` |
| **v0.8.1** | Fix EventSource qui rebouclait, fix clic sur ligne, retry à 5s sur `compilBatchOuvrirAtelier` |
| **v0.8.2** | Fix `_analyser_paquets_utilises` qui ratait les sections (option [geometrie] non détectée). Ajout `_aplatir_textes()` récursif et `_texte_complet_atome()`. |
| **v0.8.3** | Conservation des fichiers d'échec (.tex + .log) dans `data/cache_rendus/echecs/`. Lien `[log]` dans liste UI, colonne « Log » dans rapport MD. Route GET `/api/admin/compilation-atomes/echec/<nom>` avec sécurité. |
| **v0.8.4** | 3 fixes groupés : (1) `\usetikzlibrary{babel}` ajouté pour fixer 17 erreurs « + or - expected » (incompatibilité shorthands babel-french / lib tikz `calc` via `tkz-euclide`). (2) Critère « atome vide » corrigé : pour notion/méthode, vide ssi corps **ET** sections vides. (3) Exercices sans corrigé compilés en succès avec flag `sans_corrige`, section dédiée dans rapport MD. |
| **v0.8.5** | (1) Fix structurel : `_paquets_deja_charges_par_seqenseigne()` se basait sur `paquet_requirepackage` (~35 paquets de seqenseigne entier) au lieu de `PAQUETS_NOYAU + _PAQUETS_GEOMETRIE + _PAQUETS_SCRATCH` (~28 paquets vraiment chargés) → 11 paquets marqués à tort « déjà chargés ». Le cas concret : `xltabular`. (2) Bibliothèques tikz paramétrables : nouvelle clé config `tikz_libraries` (défaut : `'babel,shapes.geometric,arrows.meta,positioning,calc'`), accesseur typé, propagation, **UI dans Admin > Compilation** avec champ texte CSV. Migration de `babel` (v0.8.4) hors de `INITIALISATIONS_BIBLIOTHEQUES`. |
| **v0.8.6** | (1) `\newgeometry{left=35pt,right=35pt,top=65pt,bottom=70pt}` émis dans le préambule, alignant `\linewidth` sur les livrets (~528 pt vs ~345 pt) → débloque vwcol. (2) Init préventive `\vwcolsetup{widths={0.5,0.5}}` quand vwcol est chargé, pour éviter `Undefined control sequence` (fatal sur MiKTeX) lié à `\vwcol@widths` undef. |

---

## Bilan technique de la session — fixes structurels

Trois bugs structurels identifiés et corrigés, qui auraient touché tôt
ou tard méthodes et exercices :

1. **`_analyser_paquets_utilises` ratait les sections** (v0.8.2). Bug
   majeur car notions et méthodes ont leur contenu réparti entre
   `corps` et `sections[].items[]` : sans le fix, l'analyse ne voyait
   que `corps + corrige + variables`, donc les options du paquet
   n'étaient pas détectées et les paquets non chargés.

2. **`_paquets_deja_charges_par_seqenseigne` mentait** (v0.8.5). Se
   basait sur `paquet_requirepackage` (ce que `\usepackage{seqenseigne}`
   chargerait en entier) au lieu de la liste réelle de ce que notre
   préambule reconstruit charge. Conséquence : 11 paquets prétendument
   « déjà chargés » alors qu'ils ne l'étaient pas. `xltabular` était la
   manifestation visible. Les 10 autres (`booktabs`, `hyperref`,
   `lastpage`, `fancyhdr`, `datetime`, `eurosym`, `pgf`, `xintexpr`,
   `datatool`, `graphics`) étaient des bombes à retardement.

3. **Mise en page différait des livrets** (v0.8.6). Sans
   `\newgeometry`, `\linewidth` était à ~345 pt en isolation contre
   ~528 pt dans les livrets. Le paquet `vwcol` calcule ses colonnes
   sur `\linewidth` et débordait en isolation. Effet de bord positif
   du fix : tous les PDFs d'atomes ressemblent désormais à ce qu'ils
   sont dans les livrets, ce qui est meilleur pour la prévisualisation
   pédagogique.

---

## État du score (notions seulement, périmètre validé)

```
N10 :  64 / 64   (100%)  ✓
N11 :  39 / 39   (100%)  ✓ (sur les 39 uniques après dédoublonnage)
N12 :  24 / 24   (100%)  ✓
─────────────────────────────────
Total : 127 / 127 (100%)
```

---

## Bug latent identifié, non corrigé

Pendant le travail v0.8.6, un bug latent a été découvert dans
`services/preambule_atome.py::_paquets_externes_optionnels` : la
fonction reçoit `envs_atome` en paramètre mais ne l'utilise pas (seul
`macros_atome` est consulté). En pratique, ça ne cause aucun problème
en prod parce que le pipeline complet compense via
`detecter_paquets_tex_manquants` dans `latex_rendu_atome.py` qui détecte
les environnements et les passe via `paquets_tex_supplementaires`. Mais
cette duplication de logique mérite un nettoyage dans le cadre d'un
refactoring v0.9.

---

## À faire au prochain démarrage

### 1. Bug du doublonnage en BDD pour N11

**État** : non résolu. Les 78 entrées de notions N11 contiennent 39
notions uniques en double. Pas un bug de l'appli, c'est l'état de la
BDD locale (Laurent a probablement lancé un peuplement N11 deux fois).

**À traiter** : Laurent doit dédoublonner sa BDD avant de continuer
sérieusement les méthodes/exos. Au choix :
- Script Python autonome qui supprime les doublons (peut être généré
  dans la prochaine session, ~30 lignes).
- Investigation du code de peuplement pour comprendre comment empêcher
  la récidive.
- Purge + repeuplement complet de N11.

### 2. Méthodes (N10 + N11 + N12 = 156 méthodes)

C'est l'étape suivante naturelle après les notions. Les méthodes
utilisent souvent les mêmes paquets que les notions, donc beaucoup des
fixes v0.8.* sont déjà acquis. **À tester** : un run batch sur les
méthodes va probablement révéler 0 ou 1 problème structurel
supplémentaire au plus.

Procédure : Laurent lance `Admin > Compilation` avec filtre
`type=methode, niveau=tous`, m'envoie le rapport MD + le ZIP des
échecs s'il y en a plus de quelques-uns.

### 3. Exercices (~800 exercices total)

Le plus gros morceau. Avantages :
- Les exos ont une structure plus simple (énoncé + corrigé), pas de
  sections.
- Beaucoup compilent déjà, vu que le critère « exercice avec énoncé »
  les laisse tous passer en compilation depuis v0.8.4 et les exos sans
  corrigé sont signalés mais pas bloquants.

À faire en deux temps probablement : N10 d'abord pour repérer
d'éventuels nouveaux paquets, puis N11/N12 ensuite.

### 4. Nettoyage v0.9 (refactoring optionnel)

- Fixer le bug latent `_paquets_externes_optionnels` qui ignore
  `envs_atome`.
- Possiblement extraire un service dédié pour la résolution des paquets
  externes (la logique est aujourd'hui répartie entre `latex_rendu_atome`,
  `preambule_atome`, `paquet_parseur`).

### 5. Item de roadmap dormant : option dyslexie

Bloc commenté à activer à la demande dans le `.tex` :
- xeLaTeX + OpenDyslexic + A3 paper
- `LetterSpace=20`, `WordSpace=1.5`, `baselinestretch=1.2`
- `unicode-math` avec `latinmodern-math.otf`

Pas urgent, mais c'était une demande de Laurent en début de chantier.

---

## Cheat sheet pour reprendre le code

### Fichiers clés modifiés dans la session

```
appli/services/
├── preambule_atome.py        # PAQUETS_NOYAU, INITIALISATIONS_BIBLIOTHEQUES,
│                              GEOMETRY_NEWGEOMETRY, construire_preambule()
├── latex_rendu_atome.py      # generer_tex_atome(),
│                              _paquets_deja_charges_par_seqenseigne(),
│                              detecter_paquets_tex_manquants()
├── compilation_batch.py      # iter_compilation(), compiler_un_atome(),
│                              ecrire_rapport_md(), 5 statuts + flag sans_corrige
├── configuration.py          # CLES_DEFAUT inclut tikz_libraries
└── compilateur_pdf.py        # Critère « ok » = fichier PDF présent (pas le
                                code retour pdflatex !)

appli/routes/
├── admin.py                  # Routes /preview /run /rapport /echec
└── rendu_atome.py            # Rendu individuel d'atome (.tex et .pdf)

appli/static/app.js           # Sous-onglet Compilation côté UI
appli/templates/index.html    # Champ tikz_libraries en plus en v0.8.5

appli/tests/
├── test_preambule_atome.py   # 51 + 8 (v0.8.6) tests
├── test_compilation_batch.py
├── test_route_compilation_batch.py
├── test_v085.py              # 19 tests dédiés v0.8.5
└── test_latex_rendu_atome.py
```

### Procédure de livraison

1. Démarrer dans `/home/claude/livraison_v0XY/appli/`.
2. Copier les fichiers à modifier depuis la version précédente.
3. Modifier, tester en local dans `/home/claude/test_appli/`.
4. Vérifier sur la BDD réelle dans `/home/claude/appli/`.
5. Lancer la suite complète : `pytest tests/` (~945 tests, ~2 minutes).
6. Note de patch dans `doc/patch_v0_X_Y.md`.
7. ZIP : `cd /home/claude/livraison_v0XY && zip -r seqenseigne_v0XY_patch.zip appli/ -x "*.pyc" "*__pycache__*"`.
8. `cp seqenseigne_v0XY_patch.zip /mnt/user-data/outputs/`.
9. `present_files` pour exposer à Laurent.

### Pièges connus à éviter

- **Faire le ZIP tôt dans le cycle**, pas en dernier — la limite d'usage
  des outils peut tomber juste avant.
- **Mocks dans les tests** : `lambda conn, t, i, r, **kw: "tex"` (avec
  `**kw`) pour tolérer les nouveaux paramètres ajoutés.
- **Cache PDF** : invalidé automatiquement à chaque changement du
  préambule (le hash SHA256 change). Pas de purge manuelle nécessaire.
- **Configuration** : `Configuration(data_dir)` prend un dossier, pas
  un fichier. Le fichier est `data_dir / 'configuration.json'`.
- **Compilation `ok=True`** : critère = fichier `atome.pdf` produit, PAS
  le code retour pdflatex. Donc des erreurs non-fatales peuvent quand
  même donner un succès. C'est un piège pour la divergence entre TeX Live
  (tolérant) et MiKTeX (strict, ce qui plante chez Laurent).

### Outils disponibles pour le diagnostic

- `pdflatex` est installé dans l'env Linux.
- TeX Live 2023 + babel-french + tkz-euclide + tabularray + vwcol +
  tcolorbox… mais **pas scratch3 → simplekv** (S14 plante chez moi
  sur scratch3 mais OK chez Laurent).
- BDD réelle accessible : `/home/claude/appli/data/seqenseigne.db`.
- Logs de runs précédents souvent fournis par Laurent dans
  `/mnt/user-data/uploads/`.

---

## Récap pour reprendre la conversation

**Dire au démarrage** : « Reprenons après v0.8.6. Notions toutes vertes
(127/127). On attaque les méthodes ? Et au passage : doublonnage N11
toujours présent, je te prépare un script ? »

**Le contexte technique tient en trois lignes** : préambule reconstruit
qui inline les définitions seqenseigne, cache PDF par hash SHA256 du
`.tex`, compilation batch SSE qui produit un rapport MD.

**Les fixes que les nouveaux atomes (méthodes/exos) bénéficieront déjà
acquis** :
- Détection des paquets via `corps + sections + corrige + variables`
- Détection correcte des paquets « manquants » (pas de faux positifs)
- `\newgeometry{left=35pt,...}` automatique
- `\usetikzlibrary{babel}` + 4 autres libs par défaut
- Init préventive de vwcol
- Critère « atome vide » correct (corps OU sections)
- Exercices sans corrigé compilés et signalés sans bloquer

**À surveiller** sur les méthodes/exos :
- Nouveaux paquets jamais rencontrés → bug latent `_paquets_externes_optionnels`
  qui pourrait se manifester si un environnement nécessite un paquet
  qui n'est PAS aussi détecté via une macro.
- `\columnbreak` dans `seqColItem[nbCols=1]` (cas S13/N02 récurrent ?).
- Images manquantes dans `data/images/`.
