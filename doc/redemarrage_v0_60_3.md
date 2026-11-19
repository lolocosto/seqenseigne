# Redémarrage v0.60.3 — filets des tableaux ; noms des documents par niveau

Delta par rapport à c2e104a « v0.60.2 » (déployée et poussée par Laurent). Brief :
`col4/BRIEF_V0603.md`. Paquet LaTeX : `seqenseigne-style6e` **v0.16**, `seqenseigne-data`
**v1.2**. Aucune modification de schéma ni de format d'échange.

## Signalements de Laurent (19 novembre)

1. Les filets intérieurs des tableaux disparaissent à l'écran et à l'impression sur les
   cellules colorées — exemple : l'en-tête rose du tableau des sommes (4e, C2, AE01).
2. « Les livrets, corrections enseignant et plans de travail sont nommés avec "6e" même en
   4e… à modifier. »

## Ce qui change pour Laurent

- **Filets noirs** dans tous les tableaux des livrets de séquence (élève et corrigé) et des
  corrigés enseignant du modèle Fiches, quel que soit le niveau. Cause : le tableau
  « Suivi par objectif » de la page de garde a des filets gris clair (`black!30`) ; avec
  colortbl, `\arrayrulecolor` est **global**, malgré le groupe de la boîte : tous les
  tableaux qui suivaient la page de garde héritaient de ce gris à 30 %, invisible sur un
  fond coloré. Le tableau de suivi garde son gris clair ; les autres tableaux retrouvent la
  couleur d'avant (noir). Avant / après : `apercus/tableau_sommes_4e_C2_AE01_*.png` de la
  livraison.
- **Documents concernés** (les seuls qui composent la page de suivi, vérifié sur les 5 412
  sorties du banc) : livret de séquence (`livret_sequence_6e`, élève et corrigé) et corrigés
  enseignant (`corriges_6e`, par séquence et annuel) du modèle Fiches — en 6e et en 4e (et
  tout niveau à ce modèle), y compris « Tout compiler » d'une séquence et le Rendu PDF du
  livret. Plans de travail, évaluations, tests courts, fiches de cours, cartes mentales,
  TP, activités : pas de page de suivi, rendu inchangé.
- **Noms au niveau réel** (modèle Fiches) : `livret_sequence_4e__N11__C2.pdf`,
  `corriges_4e__N11__C2.pdf`, `plans_travail_4e__N11__C2.pdf`, `evaluation_4e__N11__A1__EV01.pdf`,
  `tests_courts_4e__…`, `travaux_personnels_4e__…`, `cartes_mentales_4e__…`,
  `fiches_cours_4e.pdf`… ; libellés « Livret 4e N11/C2 », « Corrigés 4e … » ; titre du
  `.tex` (commentaire de tête) « Livret de séquence 4e — … ». **En 6e, rien ne change**
  (mêmes noms : PDF figés de 2026-2027 et publications intacts).
- Un PDF compilé avant la v0.60.3 reste disponible (téléchargé sous son nouveau nom) ; la
  prochaine compilation du document écrit le nouveau nom et **supprime l'ancien**.

## Décisions

- **F1** — `seqenseigne-style6e` v0.16 : `\__seqsix_suivi_composer:Nn` sauve `\CT@arc@`
  avant la boîte et le rétablit globalement après (à chaque composition : le tableau peut
  être composé jusqu'à quatre fois pour tenir sur une page). Rendu du suivi identique
  (page de garde identique au pixel près sur le livret corrigé 4e C2).
- **F2** — `seqenseigne-data` v1.2 : `\seqTableauObjectifs` pose `\seq@rule@color` (un
  `\def` local) dans le groupe de `center` au lieu d'avant : même tableau, plus de fuite
  dans la suite du document (macro des anciens livrets du cycle 4, non émise par l'appli).
- **F3** — inventaire : plus aucune commande globale de couleur ou d'épaisseur de filets
  (`\arrayrulecolor`, `\doublerulesepcolor`, `\rowcolors`, `\arrayrulewidth`, `\CT@arc@`)
  dans le paquet, les gabarits Python ni les contenus de la base de test ; un test
  (`test_filets_aucune_autre_commande…`) protège l'inventaire.
- **N1** — nom = clé du type dont le suffixe `_6e` devient le niveau du référentiel
  (`param_niveaux.nom_court` « 4ème » → « 4e », ASCII : accepté par la route des PDF figés) ;
  le reste du nom est inchangé. Les **clés** de types (`livret_sequence_6e`…) restent : nom
  interne lié au module LaTeX, partagé avec l'appli de classe (`type|cible`), jamais affiché.
- **N2** — une cible renommée porte `noms_anciens` : lus en secours par le téléchargement
  (`/documents/<id>/pdf`), l'état « PDF figés présents », la publication
  (`format_referentiel._pdf_compile`, nom trouvé renvoyé) et le figeage (copie sous le
  nouveau nom) ; la compilation supprime l'ancien PDF après avoir écrit le nouveau.
- **N3** — `cible_id` et clé d'artefact inchangés : aucune recompilation imposée par le
  renommage, liens côté classe intacts. Cache des rendus : clé = `.tex` + empreinte du
  paquet ; la mise à jour des `.sty` change l'empreinte, donc les PDF en cache sont
  recompilés d'eux-mêmes (pas besoin de « Recompiler sans cache » si le paquet de
  `reference\paquet` est mis à jour **avant** toute compilation).

## Marche à suivre (Windows)

1. Fermer l'appli, décompresser `seqenseigne_v0_60_3_delta.zip` à la racine (le dossier
   `appli\` du zip sur `appli\`), puis depuis `appli\` :
   ```
   ..\outils\python\python.exe .\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
   ```
2. **Paquet LaTeX, avant toute compilation**, depuis la racine (dossier qui contient
   `appli\` et `reference\`) :
   ```
   copy /Y appli\paquet\seqenseigne-style6e.dtx reference\paquet\
   copy /Y appli\paquet\seqenseigne-data.dtx reference\paquet\
   copy /Y appli\paquet\seqenseigne-style6e.sty reference\paquet\
   copy /Y appli\paquet\seqenseigne-data.sty reference\paquet\
   ```
   (les `.sty` livrés sont ceux que produit `tex -8bit seqenseigne.ins` ; pour les
   régénérer soi-même : `cd reference\paquet`, `tex -8bit seqenseigne.ins`, répondre `y`
   à chaque « Overwrite », `cd ..\..`).
3. `.\lancer.bat atelier` (depuis `appli\`) ; Ateliers › Référentiel › référentiel de 4e
   2027-2028 › Documents à publier : « Tester » sur **Livret de séquence** et **Corrigés
   enseignant** (filets noirs) ; les autres documents peuvent attendre (seul leur nom
   change, l'ancien PDF reste servi). Rendu PDF des ateliers et « Tout compiler » : rien à
   faire (cache invalidé par le nouveau paquet).
4. Si un document a été compilé entre l'étape 1 et l'étape 2 : Rendu PDF › « Recompiler
   sans cache » (ou Système › Base de données › « Vider le cache des rendus PDF »).

## Pièges

- Un référentiel **figé** (6e 2026-2027) garde ses PDF figés, donc les filets gris clair :
  il n'est pas recompilable. Pour réimprimer un livret de 6e avec des filets noirs : atelier
  Séquence › « Tout compiler » (ou Rendu PDF), qui compile avec le nouveau paquet.
- Copier les `.sty` dans `reference\paquet` est indispensable : pdflatex lit ce dossier, pas
  `appli\paquet`. Sans la copie, un rendu compilé avec l'ancien `.sty` serait mis en cache
  sous la nouvelle empreinte (d'où l'étape 4).
- Un lien vers un ancien nom (`…_6e__N11__…pdf`) gardé hors de l'appli ne marche plus après
  la recompilation du document (l'ancien fichier est supprimé) : passer par l'appli.

## Tests

`tests/test_v0_60_3_filets_noms_niveau.py` (19 ; 17 échouent sur la v0.60.2) : filets
rétablis après le suivi (code et compilation réelle : `\CT@arc@` = `\relax` après la page
de suivi, une couleur choisie avant est retrouvée après), tableau d'objectifs, inventaire,
version ; niveau du fichier, noms et libellés en 4e, 6e inchangée, plus de « 6e » en dur,
ancien PDF servi, publication et figeage, compilation qui supprime l'ancien nom. Versions
du module mises à jour dans 6 tests existants (motif en commentaire).

## Fichiers

Modifiés : `paquet/seqenseigne-style6e.dtx`, `.sty`, `paquet/seqenseigne-data.dtx`, `.sty`,
`paquet/CHANGELOG.md`, `services/style6e.py`, `services/referentiel_documents_compilation.py`,
`routes/referentiel_documents_compilation.py`, `services/documents_evaluation_v2.py`,
`services/format_referentiel.py`, `services/referentiel_figeage.py`,
`services/livret_sequence_6e.py`, `services/plan_travail_6e.py`, `services/cartes_mentales.py`,
`services/render_evaluation.py`, `services/documents_6e.py`, `services/rendu_atome_6e.py`,
`services/mises_en_route_6e.py`, `tests/test_v0_52_4_modeles.py`,
`tests/test_v0_52_5_objectifs_s05.py`, `tests/test_v0_52_7_marqueurs.py`,
`tests/test_v0_52_8_calculatrice_tp_astuce.py`, `tests/test_v0_53_0_mises_en_route.py`,
`tests/test_v0_53_1_mer_parties.py`, `tests/test_v0_59_2_vue_encarts.py`,
`doc/ETAT_COURANT.md`, `doc/ROADMAP.md`. Nouveaux :
`tests/test_v0_60_3_filets_noms_niveau.py`, `doc/redemarrage_v0_60_3.md`. Aucun fichier
supprimé.
