# Redémarrage v0.59.2 — vue d'ensemble du référentiel, encarts du livret, horodatage de l'import

> Base de comparaison : 711b7ee « v0.59.1 » (livrée, non poussée). Brief : `col4/BRIEF_V0592.md`.
> Paquet LaTeX : `seqenseigne-style6e` **v0.15** (encarts). Nouvelle table `encarts`
> (migration idempotente, vide au départ). Aucune autre modification de schéma.

## Demandes de Laurent (17 novembre)

1. « Un document chapeau pour le référentiel, à destination de l'enseignant, qui récapitule
   par domaine les différentes séquences avec les objectifs de chaque séquence et le nombre de
   semaines qu'on met sur chaque partie de séquence » — généré automatiquement pour tous les
   référentiels, à partir du nombre de séances par objectif (pas de nouveau champ).
2. Une collègue trouve le livret d'exercices au format Fiches « trop uniforme, presque
   triste » : petits encarts « Le saviez-vous ? », « Point histoire », « Les maths dans la vraie
   vie », « Défi », quand ça a un sens, sans nombre cible.
3. (Constat v0.59.1) L'import horodatait en heure locale : un document compilé moins d'une
   heure (deux en été) après un import s'affichait « périmé ».

## Ce qui change pour Laurent

1. **Documents à publier** : en tête de liste, **Vue d'ensemble du référentiel** (décochée),
   pour tous les modèles (Notions et méthodes, Fiches, Fiches + cartes, mises en route).
   « Tester » produit `vue_ensemble.pdf` : A4 portrait, en-tête (référentiel, niveau, année,
   modèle, état, totaux), récapitulatif par domaine, puis une section par domaine (couleur du
   thème) : chaque séquence (ordre des codes), ses parties avec leur **durée en semaines**, et
   sous chaque partie ses objectifs (code, intitulé, séances ; objectif « Cours » en gris).
   Totaux par séquence, par domaine, pour l'année.
2. Le bouton **📋 Vue d'ensemble (PDF)** (même onglet, et détail d'un référentiel externe)
   la calcule **à la volée** pour n'importe quel référentiel, figé compris, sans rien
   enregistrer.
3. **Séances** : elles se saisissent toujours par objectif (onglet Séquence, champ
   « Exos : n séance(s) » / « Cours : n séance(s) ») ; les lots peuvent maintenant les donner
   (clés `seances`, `seances_cours`). Les 12 lots de 4e sont prêts (90 séances, 30 semaines).
4. **Encarts** du livret d'exercices (élève, corrigé, corrigés enseignant) : importés des lots
   (clé `encarts`, format `lot6e/FORMAT_ENCARTS.md`), visibles en lecture seule dans l'onglet
   **Rendu PDF** de la séquence. Un défi a sa solution dans le corrigé seulement. Jamais dans
   les tests courts ni les évaluations. Un livret sans encart : même `.tex` qu'avant.
5. Un document compilé juste après un import n'est plus « périmé ».

## Décisions

### Vue d'ensemble (`services/vue_ensemble_referentiel.py`)

- **V1 — Catalogue** : type `vue_ensemble` (clé nouvelle, G3) en **tête de tous les
  catalogues** (`gabarits_documents.TYPE_VUE_ENSEMBLE`, `catalogue`, `catalogue_type`), ordre
  **0** en base : les autres documents gardent leurs numéros d'ordre. Une seule version
  (enseignant), aucune option, décochée. Hors des 9 types historiques
  (`referentiel_documents.TYPES_DOCUMENT`) : interface générique de l'onglet. Un référentiel
  **modifiable** déjà créé (« en cours », « validé ») reçoit la ligne à la première lecture
  (`_vue_ensemble_manquante`, INSERT OR IGNORE) ; la vue d'ensemble ne compte pas pour décider
  d'initialiser les documents d'un modèle (changement de modèle : les lignes du nouveau modèle
  sont toujours créées). Exclue du « Tout compiler » d'une séquence (document du référentiel
  entier) ; péremption : aucune table d'atomes (structure sans `mtime`, comme `livret_plans`) ;
  « Tester » la recalcule.
- **V2 — Source** : référentiel figé (verrouillé, utilisé) ou externe → **instantané**
  (`referentiel_themes`, `_sequences`, `_parties`, `_objectifs`) ; en cours ou validé →
  **tables de l'atelier** (`sequences_du_perimetre` du type : principal sans Xnn ni Mnn ;
  mises en route : Mnn), titre court de la séquence-niveau s'il existe, libellés de parties
  (en 6e : `objectifs_6e.json`, comme le livret).
- **V3 — Séances** : `objectifs.nb_seances` / `referentiel_objectifs.nb_seances`, objectif
  « Cours » compris. Durée d'une partie = somme de ses objectifs + ses séances de révision et
  d'approche (`nb_seances_R_AE`, modèle Notions et méthodes, affichées sur une ligne à part).
  Jamais ajoutées pour une Mnn ni pour un référentiel externe : leur instantané range dans ce
  champ la somme des objectifs (RI4, v0.51.4) — elle serait comptée deux fois.
- **V4 — Semaines** : 3 séances = 1 semaine (6 = 2, 9 = 3), arrondi à la semaine la plus
  proche (demi au-dessus) ; une partie dont la somme n'est pas un multiple de 3 porte « * » ;
  une partie sans séance affiche « — » et l'en-tête le signale. Semaines d'une séquence, d'un
  domaine, de l'année = somme des semaines des parties.
- **V5 — Référentiel figé** : **calculée à la volée** (`GET /api/v2/referentiel/<id>/
  vue-ensemble/rendu-pdf` ou `rendu-tex`, blueprint atelier, cache du compilateur) ; aucune
  ligne ajoutée à ses documents (même quand sa liste s'initialise à la première lecture,
  cas d'un externe utilisé jamais ouvert), rien dans `_verrouille/`, empreintes et publications
  inchangées. Choix plutôt que « non figés seulement » : N11_v2025 et les référentiels de cette
  année se consultent aussi.
- **Domaines** : thèmes A à F du référentiel (ordre du thème, puis code), couleurs du module
  `seqenseigne-theme` (nombres rouge, géométrie violet, données bleu, proportionnalité canard,
  algorithmique magenta, grandeurs brun). Document autonome (paquets LaTeX standard :
  `longtable`, `booktabs`, `xcolor`), rien du paquet seqenseigne.

### Séances par objectif : état et remplissage

- **Audit** : stockées dans `objectifs.nb_seances` (atelier ; l'interface les saisit déjà par
  objectif), recopiées à l'instantané (`referentiel_objectifs.nb_seances`) ;
  `referentiel_parties_seances` ne sert qu'aux référentiels de 2021 (mode `par_serie`).
  L'import des lots écrivait `nb_seances = 0` à la création d'un objectif : **4e 2027-2028 et
  principal de 6e : 0 séance partout** ; mises en route : remplies (clé `seances` des lots M).
- **S1 — Clés de lot** (`outils/import_lot6e.py`, point 13) : `seances` d'un objectif,
  `seances_cours` du lot (séances de l'objectif « Cours » : un nombre pour toutes les parties,
  ou `{"1": 1, "2": 1}`). Clé absente : valeur en base gardée (saisie de l'atelier) ; valeur
  invalide : anomalie, ignorée ; idempotent ; l'essai à blanc liste « A1-02 : 0 → 2
  séance(s) ».
- **4e** : `W/lot4e/*/*.json` complétés (clés ajoutées seulement) d'après
  `col4/ref4e_etape2_parties_objectifs.md` (codes S03-02 → A1-02, intitulés contrôlés contre
  les lots et `outils/objectifs_4e.json` : 0 écart) : 12 séquences, 16 parties, 54 objectifs,
  90 séances, **30 semaines**, toutes les parties en multiples de 3.
- **6e** : `outils/ref6e_v2.md` ne fixe **aucune** séance pour le principal (« Reste à faire :
  fixer les séances du principal ») : lots de 6e non modifiés. À saisir dans l'atelier
  (onglet Séquence, objectif par objectif) ou à donner dans les lots (clé `seances`) une fois
  décidées.

### Encarts (`services/encarts.py`, module v0.15)

- **E1 — API LaTeX** : un seul environnement paramétré
  `\begin{seqEncartSix}[pleine|demi]{type}{titre}` (types `savoir`, `histoire`, `vraievie`,
  `defi`), plutôt que quatre environnements : une seule mise en forme, le type est une donnée.
  Pictogramme TikZ au trait par type (point d'interrogation, sablier, maison, étoile) et
  couleur propre (bleu, brun, vert, orange), cadre léger (filet 0,6 pt, fond à 5 %), police du
  document, insécable ; demi-largeur 48,5 % ; type inconnu = erreur de compilation.
  `\seqSolutionDefiSix{…}` : rien en version élève, « Solution : » en rouge au corrigé.
  `\seqPictoEncartSix{type}`.
- **E2 — Stockage** : table `encarts` (rattachée à une partie, et à un objectif pour un encart
  d'objectif ; position, exercice, type, titre, texte, solution, largeur, source jamais
  imprimée, ordre, `mtime` UTC, `niveau` et `sequence` dénormalisés), comme
  `cartes_mentales`. Classée « atelier » pour la bascule (`services/repartition.py`).
- **E3 — Positions** : `apres_activite`, `apres_exercice` (+ `exercice`, après sa remédiation
  si elle le suit), `fin_objectif`, `fin_partie` (avant la carte mentale). Exercice absent du
  livret (série E non incluse) : fin d'objectif. Deux `demi` consécutifs : côte à côte.
- **E4 — Import** : clé `encarts` d'un objectif ou du lot (encarts de partie). Dès qu'un lot
  porte la clé, il fait foi pour les encarts de sa séquence (créés, mis à jour, retirés ;
  retraits dans le journal de `--apply`) ; sans clé : rien ne bouge. Refus (anomalie) : type,
  position, largeur inconnus, texte vide, exercice absent, solution hors défi, environnement
  écrit dans le texte, macro `\seq…` inconnue. Avertissements : texte long (repère : 520
  caractères en pleine largeur, 240 en demi), défi sans solution, encart sans source. Jamais
  sur une séquence validée (lot non importé).
- **E5 — Atelier** : **lecture seule** (onglet Rendu PDF de la séquence : type, titre, place,
  texte, solution, source ; `GET /api/v2/livret-sequence/<niveau>/<séquence>/encarts`).
  L'édition passe par le lot : un encart n'est pas un atome (ni état, ni rendu seul), une
  édition complète aurait demandé un atelier de plus.
- **Péremption** : `encarts` compte pour le livret de séquence et les corrigés enseignant.

### Horodatage (point 3)

- **H1** : `import_lot6e._maintenant()` en **UTC** (`datetime.now(timezone.utc)`), comme
  `CURRENT_TIMESTAMP` et `compile_date` que compare `peremption_atomes` ; vaut aussi pour
  `import_lot6e_mer`. Même défaut corrigé dans `outils/reparer_series_approche.py` et
  `outils/migrer_themes_codes_2027.py` (mtime écrits en heure locale). Les `mtime` déjà écrits
  en heure locale (une heure d'avance) se résorbent d'eux-mêmes au plus tard une heure après
  l'import ; rien à migrer.

## Marche à suivre (Windows, appli fermée)

1. Sauvegarder `data\seqenseigne.db` ; dézipper à la racine (à côté d'`appli\`) : `appli\…`.
2. Module LaTeX v0.15, **depuis la racine** :
   ```
   copy /Y appli\paquet\seqenseigne-style6e.dtx reference\paquet\
   cd reference\paquet
   tex seqenseigne.ins
   cd ..\..
   ```
   (répondre `y` si `tex` demande d'écraser un `.sty` ; seul `seqenseigne-style6e.sty` change).
3. Lots de 4e : remplacer `reference\lot4e\<séq>\<séq>.json` par ceux de `W/lot4e` (clés
   `seances`, `seances_cours` ajoutées, rien d'autre). Puis, **depuis `appli\`** :
   ```
   ..\outils\python\python.exe .\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
   ..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11
   ..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11 --apply
   .\lancer.bat atelier
   ```
   Essai à blanc : section « Séances des objectifs (v0.59.2) » — 70 objectif(s) « 0 → n
   séance(s) », 0 anomalie nouvelle ; une relance après `--apply` dit « 0 objectif(s) dont les
   séances changent ».
4. Onglet Référentiel → « 4e — 2027-2028 — Principal » → Documents à publier : **Vue
   d'ensemble du référentiel** en tête ; la cocher et « Tester » (90 séances, 30 semaines), ou
   le bouton **📋 Vue d'ensemble (PDF)** (aussi pour N11_v2025 ou le principal de 6e).
5. Encarts : quand les lots les apporteront, réimporter (`import_lot6e.py`, essai à blanc puis
   `--apply`) ; ils apparaissent dans le livret (élève et corrigé) et, en lecture seule, dans
   l'onglet Rendu PDF de la séquence.

## Fichiers

Nouveaux : `services/vue_ensemble_referentiel.py`, `services/encarts.py`,
`tests/test_v0_59_2_vue_encarts.py`, `doc/redemarrage_v0_59_2.md`. Modifiés :
`services/gabarits_documents.py`, `services/referentiel_documents.py`,
`services/referentiel_documents_compilation.py`, `services/orchestrateur_compilation.py`,
`services/peremption_atomes.py`, `services/sequence_tout_compiler.py`,
`services/livret_sequence_6e.py`, `services/style6e.py`, `services/repartition.py`,
`persistence/sqlite_store.py`, `routes/livret_sequence.py`, `outils/import_lot6e.py`,
`outils/reparer_series_approche.py`, `outils/migrer_themes_codes_2027.py`,
`static/atelier_referentiel.js`, `static/referentiel_unifie.js`,
`static/atelier_seqniv_assemblage.js`, `paquet/seqenseigne-style6e.dtx` et `.sty`,
`paquet/CHANGELOG.md`, `doc/ETAT_COURANT.md` ; tests mis à jour (vue d'ensemble en tête des
catalogues, module v0.15, péremption) : `test_v0_13_6_4`, `test_v0_15_2_6`, `test_v0_52_1`,
`test_v0_52_4`, `test_v0_52_5`, `test_v0_52_7`, `test_v0_52_8`, `test_v0_53_0`,
`test_v0_53_1`, `test_v0_54_0`, `test_v0_56_0`, `test_v0_59_1`. Aucun fichier supprimé.

## Risques

- **Séances de 6e** : non fixées ; la vue d'ensemble du principal de 6e affiche « — » partout
  tant qu'elles ne sont pas saisies (ou données par les lots).
- **Ligne « Vue d'ensemble » ajoutée** aux référentiels modifiables (y compris les externes
  en cours et la MER) : décochée, sans effet sur la validation ni la publication tant qu'elle
  n'est pas cochée ; une fois cochée et compilée, elle est publiée avec les documents annuels.
- **Vue d'ensemble jamais « périmée »** : après une modification des séances, la recompiler
  (« Tester ») ; le bouton à la volée est toujours à jour.
- **Encarts** : édition seulement par les lots ; un lot qui porte la clé `encarts` retire les
  encarts de la séquence qu'il ne cite pas (journal pour revenir en arrière).
- **Arrondi** : une partie de 4 séances compte 1 semaine (signalée « * ») ; c'est la règle
  demandée, pas un calendrier.
