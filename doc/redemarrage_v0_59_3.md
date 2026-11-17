# Redémarrage v0.59.3 — multisélection des séquences, atelier Référentiel (défilement, poignée, infobulle)

> Base de comparaison : 5ca9849 « v0.59.2 » (origin/main). Brief : `col4/BRIEF_V0593.md`.
> Aucune modification de schéma, aucun changement du paquet LaTeX.

## Demandes de Laurent (17 novembre)

1. (22 h) « Ajouter la possibilité de sélectionner plusieurs séquences, comme ça je les
   repasse toutes "en cours" en une seule opération. » — l'import des lots ne touche jamais
   une séquence **validée** : 24 séquences l'étaient (N11 entier, N09 sauf A1), d'où des
   livrets sans encarts et une 4e sans séances.
2. (22 h 15) Atelier **Référentiel** : la liste des référentiels n'a pas de barre de
   défilement (tous les référentiels de 6e ne se voient pas) ; il faut une **poignée** pour
   élargir le panneau, comme ailleurs.
3. (22 h 22) Le cadre « Modèle du référentiel » est très haut : son texte d'explication
   devient une **infobulle** (texte inchangé).
4. (22 h, coordinateur) Ajouter le cas de **2026_N09** : le déverrouiller pour que ses
   documents reçoivent les encarts, puis le reverrouiller.

## ⚠ À savoir d'abord : GitHub incomplet depuis la v0.59.2

La v0.59.1 était restée « base locale, non poussée » ; le zip v0.59.2 était un delta **par
rapport à la v0.59.1**, et la v0.59.2 a été poussée sur la v0.59. Sur GitHub, il manque donc
7 fichiers de la v0.59.1 : `services/fiches_cycle4.py`, `latex_texte.py`,
`livret_cartes_planches.py`, `livret_cartes_recap.py`, `referentiels_internes.py`,
`render_carte_centralise.py` et `doc/redemarrage_v0_59_1.md`. Sans eux, la liste « Documents
à publier » de **tous** les référentiels tombe en erreur (`perimetre_cartes_objectifs`
introuvable). Ils sont **dans le zip v0.59.3** (identiques à ceux de la v0.59.1 livrée) : si
la v0.59.1 a été installée en local, rien ne change chez vous ; une fois la v0.59.3 poussée,
GitHub est de nouveau complet.

## Ce qui change pour Laurent

1. **Atelier Séquence, « — Toutes les séquences — »** (portée Séquence, sélecteur de séquence
   à droite) : la barre de gauche liste les séquences du niveau (code, titre, pastille d'état ;
   « mise en route » ou « archive » à droite). Les gestes sont ceux des ateliers d'atomes :
   - clic : ouvre la séquence (le sélecteur passe sur elle) ;
   - **Ctrl+clic** : ajoute ou retire une séquence ; **Maj+clic** : sélectionne la plage ;
     clic droit : menu « Valider la sélection / Repasser en cours » ; Échap : vide la sélection ;
   - barre au-dessus de la liste : « n sélectionnés — ✓ Valider — ⟲ En cours — ✕ ».
   Le panneau central rappelle les gestes et l'état des référentiels internes du niveau.
2. **⟲ En cours** demande d'abord une confirmation : nombre et codes des séquences ;
   référentiels **validés** qui repasseront « en cours » jusqu'à la revalidation ;
   référentiels **verrouillés** qui contiennent ces séquences et ne changent pas (sinon le
   rappel « les référentiels verrouillés ne changent pas »).
3. Résumé, comme ailleurs : « 12 repassé en cours », « 11 validé, 1 en échec : A2 : La
   séquence ne peut pas être validée en l'état. — L'objectif 03 n'a pas de fiche de
   résumé. », « 1 ignoré (archive, hors référentiel) », « n déjà à jour ».
4. Le bouton **Valider** d'une séquence affiche de nouveau les raisons d'un refus (elles
   manquaient : « Séquence non validable : » sans motif).
5. **Atelier Référentiel** : la liste des référentiels défile seule (le panneau entier défile
   si les filtres et la création prennent toute la hauteur) ; **poignée** entre le panneau et
   la zone de droite, largeur mémorisée (clé `split:atl-referentiel:aside`, comme les autres
   ateliers) ; l'explication du modèle est derrière le bouton **ⓘ** à côté de « Modèle du
   référentiel » (survol ou Tab : texte complet). Hauteur du cadre : 364 → 89 px.

## Décisions

- **D1 — Où** : la liste des séquences du niveau n'existait que dans le sélecteur de
  séquence ; l'atelier Séquence (niveau) était vide quand on choisissait « — Toutes les
  séquences — ». C'est là que la liste s'affiche (même principe que l'atelier Carte mentale,
  v0.56.2). Pas de nouvel onglet.
- **D2 — Aucune réimplémentation** : l'atelier Séquence hérite déjà d'`AtelierEditeur` ;
  multisélection, menu, barre, Échap et résumé sont ceux d'`AtelierEditeur`. L'atelier ne
  fournit que des crochets : `chargerListe` (`GET /api/v2/sequences-par-niveau?niveau=`),
  `rendreItem`, `ouvrirItem` (choisit la séquence dans la portée), `urlEtat` (la route
  **unitaire** `PATCH /api/v2/sequences-par-niveau/<id>/etat`), `raisonHorsEtat` (archives
  Xnn ignorées), `libelleItem` et `avertissementEtatGroupe`. Ces deux derniers crochets sont
  nouveaux dans `AtelierEditeur` et neutres par défaut (ateliers d'atomes inchangés).
- **D3 — Mêmes règles qu'une par une** : repasser en cours est toujours permis (même pour un
  référentiel verrouillé) ; valider passe par le contrôle pédagogique de la séquence
  (`_valider_sequence_hook`) ; un refus n'arrête pas les autres et est cité avec sa séquence
  et ses raisons (`raisons` posé au premier niveau de la réponse par `routes/v2_edition._erreur`).
- **D4 — Référentiels touchés** (`services/v2_edition.lister_sequences_etats`) : pour chaque
  séquence, les référentiels internes « vivants » (en cours / validé) dont le périmètre la
  contient (principal : ni Mnn ni Xnn ; mises en route : Mnn) et les « figés » (verrouillé /
  utilisé) dont l'instantané contient son code. L'état affiché d'un référentiel en cours ou
  validé est calculé à jour (règle de `maj_etat_lazy`, sans écrire).
- **D5 — Atelier Référentiel** : règle CSS manquante (`#atl-ref-sidebar > .atl-sidebar-body`
  sans `flex`/`overflow`) ; poignée ajoutée à `initAtelierSplitters` (annoncée en v0.13.5.1,
  jamais posée), largeur minimale 200 px comme ailleurs (300 px par défaut). Infobulle : il
  n'y a pas de mécanisme commun dans l'appli (seulement des `title`, qui ne s'affichent pas au
  clavier) : bouton ⓘ focusable, `aria-describedby`, bulle CSS au survol et au focus. Le texte
  est toujours écrit par `refuMajChoixModele` dans `#refu-c-modele-desc`.

## Ce qui arrive aux référentiels

| Référentiel | État avant | Quand on repasse ses séquences en cours | Après import + revalidation |
|---|---|---|---|
| **2027_N11** (4e 2027-2028, Fiches + cartes) | validé | retombe « en cours » (12 séquences non validées) | « en cours » tant que le livret de séquence et les corrigés (périmés par les encarts) ne sont pas recompilés, puis **validé** |
| **2025_N11b** (4e 2025-2026) | verrouillé | ne bouge pas (instantané S01…S14, autre famille de codes) | idem ; ne pas le déverrouiller (refusé : structure 2025 archivée) |
| **2026_N09** (6e principal) | verrouillé, publié (paquets 4 et 5) | ne bouge pas tant qu'il reste verrouillé | à déverrouiller **avant**, puis recompiler et reverrouiller (ci-dessous) |
| **2026_N09b** (6e mises en route) | validé | non touché si l'on ne sélectionne que A1…E1 | reste validé : l'import laisse les M01…M07 validées « non modifiées » |

## Marche à suivre (Windows)

### 0. Installer (appli fermée)

1. Sauvegarder `data\seqenseigne.db` ; dézipper à la racine (à côté d'`appli\`) : `appli\…`.
2. Depuis `appli\` :
   ```
   ..\outils\python\python.exe .\outils\verifier_md5.py --racine . --manifest MANIFEST.md5
   .\lancer.bat atelier
   ```

### 1. 4e

1. Conception de référentiel › **Séquence** › Niveau **4ème (N11)**, Séquence **— Toutes les
   séquences —**, atelier **Séquence**.
2. Clic sur **A1**, puis **Maj+clic** sur **E1** (12 séquences, les archives X… ne sont pas
   prises) → **⟲ En cours** → lire l'avertissement (2027_N11 repassera « en cours ») → OK.
   Résumé attendu : « 12 repassé en cours ».
3. Appli fermée ou ouverte, depuis `appli\` (essai à blanc, puis application) :
   ```
   ..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11
   ..\outils\python\python.exe .\outils\import_lot6e.py --niveau N11 --apply
   ```
   Sur la copie de votre base : 45 encarts, 90 séances (84 objectifs). Les **évaluations
   validées dans le module Évaluations** restent « non modifiées » (message de l'import) :
   c'est leur propre état, indépendant des séquences.
4. Recharger l'atelier, même sélection A1…E1 → **✓ Valider** : « 12 validé ».
5. Onglet Référentiel › « 4e — 2027-2028 — Principal » › Documents à publier : recompiler
   **Livret de séquence** et **Corrigés** (marqués périmés) et **Vue d'ensemble** (jamais
   marquée périmée : elle a été compilée quand il n'y avait aucune séance ; maintenant 90
   séances, 30 semaines). Le référentiel redevient **validé**.

### 2. 6e (2026_N09)

1. **Vérifier** dans l'onglet Référentiel que « 6e — 2026-2027 — Principal » est
   **verrouillé** et non « utilisé » (« utilisé » = une progression ou un retour d'usage de
   l'appli de classe le désigne : déverrouillage refusé). Sur la copie : verrouillé.
2. **Déverrouiller** 2026_N09. Son instantané est retiré (il sera réécrit au
   reverrouillage) ; sa publication figée `_publication\` est renommée
   `_publication_avant_<date>\` ; `_verrouille\` est gardé jusqu'au reverrouillage.
3. Atelier Séquence, Niveau **6ème (N09)**, — Toutes les séquences — : clic sur **A1**,
   **Maj+clic** sur **E1** (13 séquences ; **ne pas** prendre M01…M07, sinon 2026_N09b
   repasserait « en cours ») → **⟲ En cours** → OK.
4. Import, depuis `appli\` :
   ```
   ..\outils\python\python.exe .\outils\import_lot6e.py
   ..\outils\python\python.exe .\outils\import_lot6e.py --apply
   ```
   Sur la copie : encarts 5 → 35 ; « M01…M07 : séquence-niveau validée, non modifiée » (voulu).
5. Même sélection A1…E1 → **✓ Valider** : « 13 validé ».
6. Onglet Référentiel › 2026_N09 › Documents à publier : recompiler **Livret de séquence** et
   **Corrigés** (périmés par les encarts) ; les autres documents restent « ok ». Quand tout
   est validé et compilé, le référentiel repasse **validé** → **Verrouiller** : instantané
   réécrit depuis l'atelier en codes **A1…E1** (13 séquences, 20 parties, 72 objectifs,
   comme avant), PDF copiés dans `_verrouille\`. Vérifier que la réponse ne signale aucun
   « échec de copie » (un PDF jamais compilé sur ce poste manquerait dans `_verrouille\pdfs\`).
   Sur la copie : 13 livrets avec leurs encarts (35 au total, de 2 à 5 par séquence).
7. **Republier** 2026_N09 (Tableau de bord, tuile **Publication** : nouveau paquet ; côté classe, Système › Échanges › Import de référentiels) : le contenu a changé
   (empreinte nouvelle), l'appli de classe le reçoit comme une **mise à jour** (« Documents :
   n ajoutés/retirés ») ; la structure (séquences, parties) ne change pas, rien n'est refusé.
   Tant que ce n'est pas fait, l'appli de classe garde les PDF sans encarts.

## Pièges

- **Documents « périmés » qui ne se recompilent pas seuls** : livret et corrigés après
  l'import ; il faut les recompiler (sinon le référentiel reste « en cours » et ne se
  verrouille pas).
- **Vue d'ensemble jamais « périmée »** : recompilée à la main après l'import des séances
  (2027_N11) ; pour la 6e, le principal n'a toujours **aucune séance** (non fixées dans
  `ref6e_v2.md`) : sa vue d'ensemble reste sans durées.
- **2025_N11b** affiche « 4 documents périmés » (avant comme après) : référentiel verrouillé,
  structure 2025 archivée, recompilation refusée ; ses PDF figés font foi. Ne rien faire.
- **PDF figés** : tant que 2026_N09 est verrouillé, l'appli sert ses PDF figés (sans encarts) ;
  après déverrouillage/recompilation/reverrouillage, `_verrouille\pdfs\` est remplacé ; l'appli
  de classe ne voit le changement qu'après republication.
- **Images** : les livrets de 6e A1 utilisent `coloriage-centiemes.png` (dossier d'images de
  l'atelier) ; sans lui, la compilation de A1 échoue (constaté sur la copie de travail, qui
  n'avait pas le dossier).

## Fichiers

Nouveaux : `tests/test_v0_59_3_multiselection_sequences.py`,
`tests_js/v0_59_3_multiselection_sequences.test.js`, `doc/redemarrage_v0_59_3.md`. Modifiés :
`services/v2_edition.py`, `routes/v2_edition.py`, `static/atelier_editeur.js`,
`static/atelier_seqniv_assemblage.js`, `static/seqniv_pur.js`, `static/app.js`,
`static/app.css`, `templates/index.html`, `tests_js/v0_56_3_carte_mentale_fonctions_communes.test.js`
(liste Échap), `doc/ETAT_COURANT.md`, `paquet/CHANGELOG.md`. Repris de la v0.59.1 (absents de
GitHub) : les 7 fichiers listés plus haut. Aucun fichier supprimé.

## Risques

- Repasser en cours des séquences d'un référentiel **verrouillé** est permis (comme une par
  une) : son contenu ne change pas, mais ses séquences redeviennent modifiables dans l'atelier ;
  l'avertissement le cite.
- Sélectionner aussi M01…M07 en 6e ferait retomber 2026_N09b « en cours » (l'avertissement le
  dit) ; à éviter si on ne réimporte pas les mises en route.
- Infobulle : au survol ou au focus seulement ; sur tablette, toucher ⓘ (focus) l'affiche.
