# Redémarrage v0.59.1 — documents des cartes d'automatisme au modèle « Fiches » avec cartes

> Base de comparaison : 54ad9b9 « v0.59 » (déployée et poussée). Brief :
> `col4/BRIEF_V0591.md`. Paquet LaTeX inchangé. Aucun changement de schéma.

## Signalement (17 novembre, 14 h 38)

« J'ai créé un référentiel N11 pour 27-28 en cochant la case "cartes d'automatisme", mais je
ne retrouve ni les récap ni les planches dans les documents à produire. »

**Cause** : `services/gabarits_documents.py` — le catalogue d'un principal au modèle Fiches
était `_CATALOGUE_SIXIEME`, sans les deux documents de cartes (ils n'existaient qu'au
catalogue « Notions et méthodes »), que l'option « cartes d'automatisme » (v0.59.0) soit
cochée ou non. Deux causes secondaires, trouvées à l'audit :

- la liste des documents d'un référentiel ne s'initialisait que si elle était vide : le
  référentiel 2027_N11 déjà créé (lignes du modèle en base) n'aurait jamais reçu les deux
  nouveaux types ;
- les générateurs du cycle 4 prennent les cartes par `cartes_automatisme.niveau/sequence` :
  en 4e archivée, cela donnerait les cartes de 2025 (archives X01…X15, validées) et aucune
  carte des lots (A1…, rattachées aux objectifs).

## Ce qui change pour Laurent

1. Référentiel principal au modèle Fiches **avec** l'option cartes : « Documents à publier »
   montre, après les 9 documents du modèle, **Récap des cartes d'automatisme** et
   **Planches de cartes d'automatisme** (décochés). Le référentiel « 4e — 2027-2028 » déjà
   créé les reçoit à la première ouverture de l'onglet.
2. Ce sont les cartes **rattachées aux objectifs** de chaque séquence (onglet Séquence,
   cartes de l'objectif), y compris les cartes de 5e reprises (`niveau_creation` N10) ou
   rattachées depuis un autre niveau ; **seules les cartes validées** sont imprimées (règle
   existante du récap et des planches, inchangée). Verso des planches en miroir (bord court,
   v0.56.1), couleur du thème de la carte (A à E).
3. « Tout compiler » d'une séquence de 4e (onglet Rendu PDF) ajoute le récap et les planches
   de la séquence s'il y a des cartes validées.
4. Réimport d'un lot : une carte que le lot place sous un autre objectif **de la même
   séquence** quitte l'ancien objectif (cas des 6 cartes de coordonnées de D1, passées de
   D1-02 à D1-05). L'essai à blanc le liste.
5. Un titre de carte avec `%`, `&`, `#` ou `_` ne casse plus l'aperçu de la carte.

Sans l'option cartes, en 6e, au cycle 4, pour les mises en route et pour les référentiels
figés : même catalogue, mêmes documents, même `.tex`.

## Décisions

- **D1 — Catalogue** (`gabarits_documents.catalogue_type(gabarit, type_ref, cartes=False)`).
  Principal + modèle Fiches + option → `_CATALOGUE_SIXIEME` suivi des deux types du cycle 4
  **sous leurs clés** `livret_cartes_recap`, `livret_cartes_planches` (mêmes objets : options
  `{actif}`, producteurs, chaînes `type|cible` côté classe, libellés côté classe et à
  l'export déjà connus). `catalogue_du_referentiel` lit l'option
  (`fiches_cycle4.option_cartes`) : validation, figeage, publication, export, progression
  côté classe et compilation suivent (`types_du_referentiel`). L'aperçu de création annonce
  les deux documents quand la case est cochée.
- **D2 — Référentiel créé en v0.59.0** (`referentiel_documents.lister_documents`) : si le
  catalogue compte le récap ou les planches sans ligne en base, que le référentiel est Fiches
  + option et encore modifiable (« en cours », « validé »), les lignes manquantes sont
  ajoutées (INSERT OR IGNORE, ordre 10 et 11, décochées) ; rien d'autre ne change. Un
  référentiel figé, ou du cycle 4, garde sa liste.
- **D3 — Cibles** (`referentiel_documents_compilation._cibles_cartes_fiches`). Modèle des
  documents du cycle 4 vérifié : **planches par séquence** (une cible par séquence qui a des
  cartes validées), **récap annuel** (une cible `unique`). Au modèle Fiches : mêmes cibles,
  plus un **récap par séquence** (document enseignant de la séquence, aussi produit par
  « Tout compiler ») ; séquences du principal (ni Xnn ni Mnn) qui ont au moins une carte
  validée rattachée ; mêmes noms de fichiers (`livret_cartes_planches__N11__A1.pdf`,
  `livret_cartes_recap.pdf`, `livret_cartes_recap__N11__A1.pdf`). La cible porte
  `perimetre='objectifs'`, que lisent les producteurs de l'orchestrateur.
- **D4 — Cartes** (`fiches_cycle4.cartes_du_perimetre`) : cartes liées par `objectif_cartes`
  aux objectifs de la séquence (ou de tout le principal pour le récap annuel, une fois
  chacune) ; validées seulement ; ordre : séquence, objectif, ordre du lien, numéro. Une
  carte reprise d'un autre niveau garde son identité (niveau, séquence, numéro) donc la
  couleur de son thème. Page de garde : « Séquence A1 — <titre court> ». Les générateurs
  gardent leur appel historique (`perimetre` absent) : même `.tex` pour le cycle 4.
- **D5 — Tout compiler** (`sequence_tout_compiler`) : table
  `DOCUMENTS_SEQUENCE_FICHES_CARTES` ajoutée quand le modèle demandé est Fiches et que le
  référentiel de l'atelier du niveau (règle R1b) a l'option ; noms `N11_A1_cartes_recap.pdf`,
  `N11_A1_cartes_planches.pdf`. Garde D-LISTE étendue (test).
- **D6 — Import, alignement des rattachements** (`import_lot6e.aligner_rattachements_cartes`,
  point 12 de l'en-tête) : le lot fait foi pour les cartes qu'il cite ; une carte citée sous
  l'objectif O perd ses liens vers les **autres objectifs de la même séquence-niveau**.
  Intouchés : liens vers des objectifs d'autres séquences, liens des cartes que le lot ne
  cite pas (ajoutés par l'auteur), carte validée ou séquence validée (lien gardé, anomalie ;
  les objectifs n'ont pas d'état propre, une séquence validée n'est de toute façon pas
  importée). Essai à blanc : section « Cartes d'automatisme… », ligne « rattachements alignés
  sur le lot : n lien(s) retiré(s) » et le détail ; journal JSON : `retraits`
  (`quoi: lien_objectif_carte`, la ligne `objectif_cartes` à réinsérer).
- **D7 — Titres de cartes** (`latex_texte.speciaux_latex`) : le titre n'est inséré que dans
  l'aperçu isolé de l'atelier (clé `nom` de `\seqCarteAutomatisme`) — ni dans les planches ni
  dans le récap, contrairement à ce que disait le rapport du lot D2. Le `%` y commentait la
  fin de la ligne d'options. `& % # _` échappés hors `$…$`, sans conversion Unicode : la clé
  n'est pas composée par le paquet, et deux cartes de 5e (« ⊥ », « ↔ ») gardent ainsi le même
  `.tex`. `texte_latex` = `unicode_latex(speciaux_latex(…))`, inchangé pour ses appelants.

## Marche à suivre (Windows, depuis `appli\`, appli arrêtée)

```
..\outils\python\python.exe .\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11
..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11 --apply
.\lancer.bat atelier
```

1. Installer le zip, vérifier les MD5, puis (après le réimport, point 2) `.\lancer.bat
   atelier`, F5, onglet Référentiel → « 4e — 2027-2028 — Principal » →
   Documents à publier : les deux documents de cartes apparaissent en fin de liste ; les
   cocher.
2. **Réimport des lots** (pour l'alignement des cartes, dont D1) : l'essai à blanc liste,
   dans « Cartes d'automatisme rattachées aux objectifs », les liens qui seront retirés
   (« N11/D1/CA1 « Abscisse et ordonnée » : lien vers D1-02 retiré (le lot la place sous
   D1-05) »…) ; vérifier qu'ils correspondent aux déplacements voulus, puis `--apply`
   (sauvegarde `sauvegardes\avant_import_lot6e_*.db`). Une relance donne « 0 lien(s)
   retiré(s) ».
3. Valider les cartes d'une séquence (onglet Séquence ou atelier des cartes), puis
   « Tester » le récap et les planches, ou « Tout compiler » de la séquence. Imprimer les
   planches en recto-verso **bord court**.

## Fichiers

Nouveaux : `tests/test_v0_59_1_cartes_fiches.py`, `doc/redemarrage_v0_59_1.md`. Modifiés :
`services/gabarits_documents.py`, `services/fiches_cycle4.py`,
`services/referentiel_documents.py`, `services/referentiel_documents_compilation.py`,
`services/referentiels_internes.py`, `services/orchestrateur_compilation.py`,
`services/livret_cartes_recap.py`, `services/livret_cartes_planches.py`,
`services/sequence_tout_compiler.py`, `services/render_carte_centralise.py`,
`services/latex_texte.py`, `outils/import_lot6e.py`, `doc/ETAT_COURANT.md`,
`paquet/CHANGELOG.md` (note : paquet inchangé). Aucun fichier supprimé, aucun JS modifié.

## Contrôles

Base de test : copie de la base archivée du 16 novembre + les 12 lots de 4e importés
(0 anomalie) + « 4e — 2027-2028 » créé par l'API (Fiches + cartes). Compilation pdflatex
(2 passes) du récap annuel, des récaps et des planches de A1 et D1 ; miroir du verso vérifié
en image sur une carte paramétrée. Alignement rejoué sur le lot D1 réel. Banc « mêmes
sorties » (5 030 sorties, « Tout compiler » compris) : code v0.59 = code v0.59.1 sur la base
sans le référentiel 2027 ; avec lui, seuls ses documents de cartes et le « Tout compiler »
de N11/A1 et N11/D1 changent. Chiffres pytest et vitest : `ETAT_COURANT.md`.

## Risques

- **Cartes non validées** : ni récap ni planches (règle existante) ; une séquence sans carte
  validée n'a pas de cible (le document compile alors « 0 cible »).
- **Réimport** : l'alignement retire des liens ; la sauvegarde et le journal (`retraits`)
  permettent le retour. Une carte validée garde ses liens (signalé) : la repasser « en
  cours » pour aligner.
- **Carte rattachée à deux séquences** : elle figure dans les planches de chacune, une seule
  fois dans le récap annuel.
- **Libellé de l'interface** : le sous-titre des deux documents reste celui du cycle 4
  (« 8 cartes par page… »).
- **Constat hors périmètre (non corrigé)** : `import_lot6e._maintenant()` écrit les `mtime`
  en heure locale alors que l'appli compare en UTC (`peremption_atomes`) : un document
  compilé moins d'une heure (deux en été) après un import s'affiche « périmé ». Sans
  conséquence sur le contenu ; recompiler plus tard, ou corriger en v0.60
  (`datetime.now(timezone.utc)`).
