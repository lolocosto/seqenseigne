# Redémarrage v0.60.1 — suite de la version 2 du modèle Fiches et décisions du 18 novembre

> Base de comparaison : 7c47dc1 « v0.60 » (origin/main). Brief : `col4/BRIEF_V0601.md`.
> Schéma : 3 colonnes ajoutées au démarrage, valeurs neutres (`objectifs.sans_carte`,
> `referentiel_niveaux.mise_en_route`, `referentiel_niveaux.mer_referentiel`) ; le mode de
> mise en route est déduit une seule fois quand c'est sûr. Paquet LaTeX inchangé.

## Ce qui change pour Laurent

1. **Mode de mise en route du référentiel principal** (décision 18) : *aucune MER*,
   *cartes d'automatisme* ou *progression de MER* (et laquelle).
   - Au premier démarrage : **2027_N11 → cartes d'automatisme** (option cartes),
     **2026_N09 → progression de MER 2026_N09b** ; les autres : « non renseigné ».
     Instantanés et publications figées non réécrits.
   - Saisie à la création (liste « Mise en route » du formulaire, principal interne ou
     externe) et sous la barre « Format d'échange » du référentiel choisi (liste +
     « Enregistrer ») ; référentiel verrouillé ou utilisé : lecture seule.
   - Affiché dans la **vue d'ensemble** (ligne « Mise en route ») et le **document de
     rituels** ; transporté par le format d'échange (`referentiel.mise_en_route`,
     version **1.7** ; absent si non renseigné : document et empreinte inchangés).
2. **Tests courts associés aux cartes** (décision 17) :
   - nouveau document **« Tests courts »** dans « Documents à publier » d'un principal
     Fiches avec l'option cartes (2027_N11) : un par partie, sujet A/B ; la version
     **corrigée** ajoute l'encadré « Cartes d'automatisme évaluées » (cartes validées de la
     partie). Le document « Évaluations » garde ses cibles (le test court y reste).
   - cadre « Rituels… » : liste **Tests courts** — *non placés* (défaut, Leitner à l'oral)
     ou *dans les séances d'évaluation* (2 semaines après le rituel des cartes de la
     partie, 10 min, aucun objectif compté). Rien n'est imposé.
3. **Séance d'évaluation** : dans le même cadre, « Séance d'évaluation, semaine n »,
   sujet A/B, élève/corrigé, **Compiler la séance** : page d'en-tête (jour, sujets, durées,
   total) puis chaque sujet sur sa page. Refus au-delà de 50 min ou 5 objectifs (sauf une
   évaluation seule, déjà signalée par le calendrier).
4. **Plan de travail Fiches** (4e avec cartes) : en tête de chaque partie, « Cartes
   d'automatisme de la partie n (k) (planche à distribuer au début de la partie) » avec la
   liste des cartes validées. 6e inchangée.
5. **Titre court** : onglet Édition de l'atelier Séquence, champ « Titre court
   (documents) » + Enregistrer (séquence validée : lecture seule).
6. **Objectif sans carte** : à la validation d'une séquence (principal Fiches avec option
   cartes), avertissement non bloquant « L'objectif A3-04 n'a pas de carte
   d'automatisme… ». Pour un objectif voulu sans carte : `"sans_carte": true` sur
   l'objectif du lot (clé absente au réimport : valeur gardée).
7. **Bonus** (décision 16) : à l'import, une évaluation de 5e, 4e ou 3e dont le bonus
   n'est pas 1 pt est signalée, **bonus absent compris** ; rien en 6e (2 pts acceptés).
8. **Atelier Séquence, Rendu PDF** : le bloc « Carte mentale » est retiré (décision 19) ;
   les cartes mentales se compilent dans l'atelier Carte mentale (« Tout compiler » les
   garde).
9. **Rendu par lot** : type « Cartes mentales » (une par partie, version élève) et case
   **Sans cache**.
10. **Réimport des évaluations et tests courts** (refonte des tests courts de 4e) : une
    évaluation en cours prend exactement le contenu du lot (anciens exercices EV retirés,
    orphelins supprimés avec journal de restauration) ; une évaluation importée en
    `evaluations` et passée en `tests_courts` (même titre) devient le test court, sans
    doublon ; l'essai à blanc liste **ce qu'il faut repasser en cours** et comment.
11. **Module Évaluations** : multisélection (Ctrl+clic, Maj+clic, clic droit) avec
    « ✓ Valider » et « ⟲ En cours » ; repasser une évaluation en cours (ou la valider)
    fait de même pour ses exercices EV propres.
12. Sujets : « 1 pt », « 0,5 pt », « 2 pts » (avant : « 1 pts »).
13. Petits manques : séquence de chaque exercice dans la liste en « toutes les
    séquences » ; règles CSS du mode côte-à-côte sur `#atl-exercice-form` ; exemples
    « A1 » au lieu de « S01 » ; `/api/admin/cycle/importer` refuse (409) un cycle migré en
    codes A1.

## Décisions

- **D15** — Rien à changer : la règle « 10 min par objectif » de la v0.60 (T2, T3) est
  déjà commune à tous les niveaux ; en 6e, elle donne la partie 1 des sujets en deux
  parties (A3 : 30 min). Les PDF figés ne sont jamais recompilés.
- **D16** — `NIVEAUX_BONUS_1 = N10, N11, N12` ; bonus ≠ 1 (absent compris) : avertissement ;
  tests courts : règle inchangée.
- **D17a** — type `tests_courts_6e` ajouté au catalogue Fiches avec l'option cartes (après
  récap et planches), cibles `TC/N11/A3/p1` (sequence, partie) ; sujet = générateur des
  évaluations (élève identique au caractère près).
- **D17b** — paramètres de rituels `tests_courts` (`non_places` | `seances`) et
  `delai_test_court` (2).
- **D-SE** — document hors catalogue (comme les rituels), PDF dans
  `referentiels\<id>\_rituels\seance_sNN_<sujet>_<version>.pdf`. La durée n'est pas ajoutée
  aux sujets isolés : sorties inchangées.
- **D18** — colonnes et déduction ci-dessus (MER interne unique du même niveau, version
  `V` + « b ») ; saisie refusée sur un référentiel figé (409) ou annulé ; MER désignée :
  type « mer », même niveau, non annulée ; mode contrôlé avant la création (rien de créé à
  moitié).
- **D19** — bloc retiré de l'interface seulement (routes et générateur inchangés).
- **E9, TC, F4, C11, C12** : voir le journal (`livraison_v0601/JOURNAL.md`, étape 4).
- **R5** — exercices EV propres (utilisés par aucune autre évaluation) : même état que
  leur évaluation à chaque « Valider » / « Repasser en cours » ; mtime non touché.
- **R6** — évaluation en cours : le lot fait foi (exercices EV de la séquence et objectifs
  évalués) ; exercices d'autres séries ajoutés à la main gardés ; orphelin validé gardé
  (anomalie) ; évaluation validée jamais touchée (R4).
- **R7** — section « À repasser en cours avant l'import » (séquences validées,
  évaluations validées que le lot modifie, exercices EV validés d'évaluations en cours).
- **C12a** — référentiels externes : codes S01…/M01… gardés et documentés (thèmes locaux
  par rang, séquence sans thème, plus de 9 séquences par thème possibles).

## Marche à suivre (Windows)

1. Fermer l'appli, décompresser `seqenseigne_v0_60_1_delta.zip` à la racine (le dossier
   `appli\` du zip sur `appli\`), puis depuis `appli\` :
   ```
   ..\outils\python\python.exe .\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
   .\lancer.bat atelier
   ```
   Au démarrage : 3 colonnes ajoutées, modes de mise en route déduits (2027_N11, 2026_N09).
2. Vérifier le mode : Conception › Référentiel › 2026_N09, puis 2027_N11 (barre « Mise en
   route » sous « Format d'échange »).
3. **Réimport des 12 lots de 4e** (tests courts en `tests_courts`, bonus 1 pt partout ;
   ajouter aussi `"sans_carte": true` aux objectifs A3-04, B2-04, C1-05, E1-05) :
   1. copier les lots à jour dans `..\reference\lot4e\`, puis essai à blanc :
      ```
      ..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11
      ```
      lire la section **« À repasser en cours avant l'import »** (sur la copie : 12
      séquences, 23 évaluations et tests courts) ;
   2. **séquences** : Ateliers › portée Séquence › 4ème › « — Toutes les séquences — » :
      clic sur A1, Maj+clic sur E1, « ⟲ En cours » ;
   3. **évaluations** : Ateliers › portée Niveau › 4ème › Évaluation : clic sur la
      première, Maj+clic sur la dernière, « ⟲ En cours » (leurs exercices EV suivent : rien
      à faire dans l'atelier Exercice) ;
   4. relancer l'essai à blanc : la section a disparu ; appliquer :
      ```
      ..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11 --apply
      ```
      (sauvegarde et journal de restauration écrits par l'outil ; sur la copie : 0 anomalie,
      32 évaluations dont 16 tests courts à 10 + 1, aucun doublon) ;
   5. revalider : Évaluation › tout sélectionner › « ✓ Valider » ; Séquence › A1…E1 ›
      « ✓ Valider » ; recompiler les documents de 2027_N11 concernés (évaluations, tests
      courts, plans de travail).
4. 2027_N11 › Documents à publier : cocher **Tests courts** si voulu ; recompiler
   **Plans de travail** (cartes de la partie) et la **vue d'ensemble**.

## Pièges

- Sujets avec « 1 pt » : tous les sujets ayant un exercice ou un bonus à 1 pt changent
  (« 1 pts » → « 1 pt ») ; les PDF figés ne sont pas recompilés.
- Un exercice EV partagé par deux évaluations ne suit pas l'état de l'une d'elles (R5) ;
  un orphelin validé reste en base (anomalie dans le rapport).

- La déduction n'a lieu qu'une fois (à l'ajout des colonnes) : un mode remis à « non
  renseigné » n'est plus deviné.
- Les plans de travail de 2027_N11 changent (rubrique des cartes) : à recompiler.
- Tests courts placés dans les séances : avec l'ordre des codes, 2 tests courts et
  1 évaluation tombent au-delà de la semaine 30 (signalé).
- Un référentiel externe se numérote toujours S01… (documenté).

## Fichiers

Modifiés aussi pour le réimport : `outils/import_lot6e.py` (R6, R7), `services/evaluations.py`
(R5), `routes/evaluations.py` (PATCH état), `static/atelier_evaluation_oo.js` (multisélection),
`services/render_evaluation.py`, `services/rendu_atome_6e.py` (accord). Nouveaux :
`services/cartes_partie.py`, `services/mise_en_route_referentiel.py`,
`services/documents_evaluation_v2.py`, `tests/test_v0_60_1_suite_fiches.py`,
`tests_js/v0_60_1_suite_fiches.test.js`, `doc/redemarrage_v0_60_1.md`. Aucun fichier
supprimé.
