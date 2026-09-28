# Doc de redémarrage — seqenseigne v0.7 (+ patch v0.7.1)

> Document à fournir en tête de la prochaine session pour reprendre le contexte.

## Ce qu'est seqenseigne

Application Flask de gestion pédagogique pour Laurent, professeur de
mathématiques au collège. Génère et gère :
- Livrets de séquence (`livrets_de_sequence/`)
- Plans de travail annuels (`documents_annuels/`)
- Livrets d'exercices et fiches de résumé
- 3 niveaux : N10 (5e), N11 (4e), N12 (3e), avec 14 séquences chacun

Stack : Python/Flask, SQLite, JavaScript vanilla, LaTeX (paquet
`seqenseigne` maintenu en `.dtx`).

Pas de Git en place : versionnement par ZIP de livraison successifs,
documenté en local par les `README_*.md` et `redemarrage_*.md` du dossier
`appli/doc/`.

Structure principale sur disque :
- `Enseignement_new/seqenseigne/` — sources `.dtx` du paquet LaTeX
- `Enseignement_new/reference/sequences/N1[012]/{exercices,notions,methodes,documents_annuels,livrets_de_sequence}/`
- `Enseignement_new/reference/paquet/` — `.sty` compilés du paquet
- `Enseignement_new/2025-2026/Collège Les Hautes Ourmes/` — classes
- `Enseignement_new/appli/` — l'application Flask de pilotage
- `Enseignement_new/appli/data/images/` — **dossier centralisé v0.7**

## État actuel — v0.7 + v0.7.1 déployées et validées

### Cycle 1 — Centralisation des images (déployé)

**Avant v0.7** : les images étaient éparpillées dans l'arborescence de
référence. Pour les exercices, à côté du `.tex`. Pour les notions et
méthodes, centralisées par niveau dans `livrets_de_sequence/Images/`
et référencées via la macro `\dirPrefix` (héritage historique).

**Après v0.7** : tout dans un dossier plat `appli/data/images/`, en
`.png` uniquement, nommées d'après le `.tex` qui les utilise :
- Exercices (codes uniques) : `<code><suffixe libre>.png`
  → `N11S03E02_enonce.png`, `N11S03E02_schema.png`
- Notions/méthodes : `<basename_du_tex><suffixe libre>.png`
  → `N10_S01_Notion_01_fig1.png`

Conversion `.jpg → .png` au passage, via Pillow.

**Implémentation** :
- Nouvelle macro paquet `\seqDefCheminImages` dans
  `seqenseigne-core.dtx` (et `.sty`). Utilise `\g@addto@macro\Ginput@path`
  pour ajouter un dossier images au chemin de recherche de `graphicx`
  sans écraser ce que `\seqDefChemin` a déjà posé. Accesseur public :
  `\seqCheminImages`. **Pas encore utilisée** côté rendu (le rendu
  interne passe par `TEXINPUTS`) ; sera utilisée par l'outil de
  régénération `reference/` v0.8+.
- Script `appli/scripts/migration_images.py` : analyse en mémoire (pas
  d'effet de bord) puis application. Modes `--dry-run` / `--apply` en
  CLI, ou via l'API admin web. Détection des collisions par hash SHA256,
  partage des images identiques sur une seule cible. Idempotence
  validée : re-run sans effet.
- Routes `POST /api/admin/images/preview` et `/api/admin/images/apply`
  dans `routes/admin.py`.
- Sous-onglet « Images » dans Administration (HTML + JS) avec
  compteurs, liste des conflits, log déroulable.
- `services/compilateur_pdf.py` : nouveau paramètre `dossier_images`
  qui ajoute `appli/data/images/` au `TEXINPUTS` (recherche récursive).

**Distinction des deux versants validée** :
1. *Rendu interne* (atomes, livrets compilés depuis l'appli) : pas de
   macro LaTeX à poser, `TEXINPUTS` suffit. Le `.tex` peut rester
   minimaliste.
2. *Régénération `reference/` depuis la BDD* (outil futur, pas dans
   cette livraison) : la macro `\seqDefCheminImages` sera posée
   explicitement dans chaque `.tex` régénéré.

### Patch v0.7.1 — Images centralisées dans livrets_de_sequence

**Découvert au déploiement v0.7** : 100 images introuvables, toutes du
pattern `\includegraphics{\dirPrefix/Images/X}`. Les images des
notions/méthodes étaient centralisées dans `livrets_de_sequence/Images/`
du niveau, pas à côté du `.tex` qui les utilise.

**Correctifs (1 seul fichier modifié, `migration_images.py`)** :
1. Le scanner descend maintenant dans `livrets_de_sequence/`.
2. Tri déterministe des `.tex` utilisateurs (par chemin alphabétique) :
   le « 1er utilisateur » donne son nom à l'image cible. Pour
   `pavage_tomettes.jpg` partagée par N10 et N11, le nom cible est
   `N10_S11_Methode_05_pavage_tomettes.png` et les 2 `.tex` pointent
   vers ce nom.
3. Idempotence renforcée pour les images orphelines après réécriture :
   nouveau test qui scanne le dossier cible à la recherche d'un fichier
   `*_<stem_source>.png` pour éviter de re-convertir un JPG dont le PNG
   cible existe déjà.

**Résultat post-déploiement (validé en production)** :
- 257 images migrées (237 copiées + 20 converties)
- 132 `.tex` modifiés, 292 `\includegraphics` réécrits
- 0 introuvable, 0 conflit
- 12 doublons identiques mutualisés (images partagées entre niveaux)
- 14 orphelines signalées (images jamais référencées, à arbitrer)

### Cycle 2 — Adaptation des tests désactivés (déployé)

7 fichiers de tests étaient en `pytest.skip(allow_module_level=True)`
depuis v0.6.4. Tous ré-armés sur le nouveau schéma `atome_sections` +
`atome_section_items`.

**État actuel : 1264 tests passent, 4 skipped** (les 4 skipped étant
des tests qui dépendent d'un environnement non disponible, non liés
à v0.7).

Note historique : un test (`test_R4a_schema::test_colonnes_objectifs_v2`)
a remonté un échec post-déploiement v0.7. C'était un test obsolète
depuis v0.6.4 (la colonne `objectifs_v2.fin_cycle` ajoutée en v0.6.4
n'avait pas été reflétée dans l'assertion). Fixé en v0.7.1 par ajout
de `"fin_cycle"` à l'ensemble attendu — typique des régressions
latentes que les tests désactivés cachaient.

## Architecture des fichiers clés

```
appli/
├── app.py                              — entry point Flask
├── persistence/
│   ├── schema.sql                      — atome_sections + atome_section_items
│   └── sqlite_store.py                 — _lire_sections / _ecrire_sections
├── scanner_latex.py                    — parseur, modèle universel à 2 niveaux
├── scripts/
│   └── migration_images.py             — script v0.7.1 (idempotent)
├── services/
│   ├── atomes.py                       — CRUD, _a_des_items helper
│   ├── compilateur_pdf.py              — +param dossier_images v0.7
│   ├── latex_rendu_atome.py            — _charger_sections, _rendu_sections
│   ├── latex_gen.py                    — génération livret de séquence
│   ├── admin.py                        — statut_bdd
│   └── paquet_parseur.py               — parse les .sty
├── routes/
│   ├── admin.py                        — +/api/admin/images/{preview,apply}
│   └── rendu_atome.py                  — passe dossier_images
├── data/
│   └── images/                         — dossier centralisé v0.7 (257 images)
├── static/
│   ├── app.js                          — adminImages{Preview,Apply}
│   ├── atelier_commun.js               — splitters
│   └── rendu_atome.js                  — sauvegarde auto
├── templates/
│   └── index.html                      — sous-onglet Images
└── tests/
    └── (1264 tests verts, 4 skipped)
```

## Décisions architecturales actées

- **Source de vérité = la BDD**. L'arborescence `reference/` reste
  cohérente après migration v0.7 mais devient progressivement
  secondaire ; un outil de régénération `reference/` depuis la BDD est
  prévu plus tard.
- **Stockage plat des images** : `appli/data/images/`.
- **Conventions de nommage** :
  - Exercices : `<code>[_<suffixe libre>].png`
  - Notions/méthodes : `<basename_du_tex>[_<suffixe libre>].png`
  - Images partagées entre plusieurs `.tex` : nommées d'après le 1er
    `.tex` utilisateur (ordre alphabétique de chemin), pas de
    duplication sur disque.
- **Pas de modification du paquet pour le rendu interne** : les images
  sont trouvées via `TEXINPUTS` étendu côté compilateur Python.
- **2 Makefile** : `Makefile.win` et `Makefile.unix`.
- **`@` dans .tex** restreint aux `.dtx` ; wrappers publics requis.

## Roadmap pour la suite

**Trajectoire d'ensemble** : maintenant que la chaîne d'images est
saine, valider en profondeur la chaîne de compilation, puis remonter
vers les livrets, les référentiels, et les progressions de classe.

### Priorité 1 : Compilateur batch des atomes

Aujourd'hui, le rendu d'atome se fait à la demande dans l'UI. On veut
un **mode batch** qui :
- Compile tous les atomes de la BDD (notions, méthodes, exercices)
- Liste les succès / échecs avec les logs
- Idéalement exposé via un bouton admin (preview rapide + apply long)
- Produit un rapport `compilation_atomes_rapport.md` avec les erreurs

C'est aussi ce qui va valider en profondeur la migration v0.7 des
images : si une image a été mal renommée ou mal réécrite, ça remontera
ici.

Pas démarré. Bon premier cycle après v0.7.1 (court, bien borné).

### Priorité 2 : Compilation des livrets de séquence + fiches de résumé

Pendant logique de la P1 mais à un cran au-dessus :
- Compiler tous les livrets de séquence (1 PDF par séquence × 3
  niveaux × 14 = 42 PDF)
- Compiler les fiches de résumé (en attendant l'atelier dédié, voir P3)
- Possible occasion de poser `\seqDefCheminImages` dans les `.tex`
  générés par `services/latex_gen.py` (versant 2 lisible)

Pas démarré. À chiffrer après P1.

### Priorité 3 : Atelier « Fiche de résumé »

Nouvel onglet dans l'atelier objectifs pour éditer la fiche de résumé
de chaque objectif :
- Mécanique de sections universelles identique à notions/méthodes
- Vocabulaire dédié dans la datalist : `Énoncé`, `À retenir`,
  `Exemple type`, `Méthode`…
- Génération `.tex` calquée sur `generer_corps_notion` /
  `generer_corps_methode`, environnement dédié `seqResume` à définir
  côté paquet.

Pas démarré.

### Priorité 4 : Référentiels (création / édition depuis l'UI)

Les tables `referentiel_niveaux`, `referentiel_themes`,
`referentiel_sequences`, `referentiel_objectifs` existent en BDD. Il
faut finaliser le workflow de création/édition d'un référentiel depuis
l'UI (à creuser : qu'est-ce qui marche déjà, qu'est-ce qui manque ?).

### Priorité 5 : Suivi / progressions annuelles

S'appuie sur les référentiels P4. Plomberie déjà en place
(`services/progression.py`, `services/edition_progression.py`,
`routes/progression.py`) mais à finir et raccorder à l'UI.

### Sur la table : Roadmap dyslexie

Mode de rendu dyslexie-friendly (xeLaTeX + OpenDyslexic + A3 +
LetterSpace=20 + WordSpace=1.5 + baselinestretch=1.2 + `unicode-math`
avec `latinmodern-math.otf`). Configuration à garder commentée dans
le `.tex` et activée via une option de compilation. Pas démarré.

### Sur la table : Outil de régénération `reference/` depuis la BDD

Pendant logique de la centralisation des images : un outil qui
régénère l'arborescence `reference/sequences/` sur disque depuis la
BDD, avec `.tex` humainement lisibles + `\seqDefCheminImages{...}` en
tête. Idempotent (un re-run produit un diff vide). Pas démarré.

### Sur la table : Arbitrage des 14 images orphelines

Au déploiement v0.7.1, 14 images étaient présentes dans
`livrets_de_sequence/Images/` mais référencées par aucun `.tex`. À
arbitrer (héritage à supprimer, ou à brancher dans un `.tex` qui les
manque). Cf. log de migration. Pas urgent.

## Comment tester rapidement

Pour valider qu'une nouvelle session a bien repris le contexte :

```bash
cd Enseignement_new/appli

# 1. Tous les tests doivent passer.
python -m pytest tests/ -q
# → Doit afficher 1264 passed, 4 skipped.

# 2. La migration des images est idempotente : la lancer ne doit rien faire.
python scripts/migration_images.py \
    --reference ../reference/sequences \
    --images data/images --dry-run
# → Doit afficher 0 copie, 0 conversion, et la quasi-totalité en SKIP.

# 3. Démarrer l'application :
python app.py                     # → http://localhost:5000

# 4. Tester un rendu d'atome avec image (p.ex. N10S01E03 qui posait
#    problème en v0.6.4) — doit compiler sans erreur.
```

Pour vérifier la base :
```bash
sqlite3 data/seqenseigne.db "SELECT COUNT(*) FROM atome_sections;"
# devrait retourner ~473 si toutes les séquences sont importées
```

## Conventions de communication

- Laurent préfère **un seul ZIP par livraison** (pas de patches
  successifs sauf bug critique post-déploiement, comme v0.7.1).
- Cadrage rigoureux **avant** de coder : poser les questions
  bloquantes, valider l'archi, puis exécuter.
- Pas de migration de données BDD nécessaire (Laurent vide la base
  quand il veut).
- `make -s` (silent) suffit pour Laurent ; pas besoin de bavardage des
  commandes.
- Style : warm + technique + pas d'emojis sauf petite victoire (🎉).
- Pas de Git : versionnement par ZIP + `redemarrage_*.md` successifs.
