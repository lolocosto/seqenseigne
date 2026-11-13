# Redémarrage v0.56.3 — atelier Carte mentale au niveau des ateliers atomiques

> Base de comparaison : 0316fce « v0.56.2 » (déployée). Aucune migration, aucune table,
> aucune route nouvelle, aucun `.dtx` modifié, aucun import de lot.

## Besoin (Laurent, 13 novembre 2026, 17 h 03)

« Je crois qu'il reste juste à mettre en place la multisélection pour valider plusieurs
éléments en une seule fois. En fait, reprends toutes les fonctionnalités communes à tous
les ateliers atomiques pour vérifier qu'elles sont bien présentes. »

## Inventaire (décision INV-CM)

Tableau fonctionnalité × atelier (Exercice, Notion, Méthode, Fiche de résumé, Carte
d'automatisme, Carte mentale) tiré du code : livré à part (`inventaire_ateliers.md` de
la livraison). Absents de TOUS les ateliers, donc pas « communs » : actions groupées
autres que l'état (supprimer, déplacer, dupliquer, exporter), recherche dans la liste,
historique / versions, navigation précédent / suivant. Sans objet pour la carte mentale
(une carte par partie, pas d'objectif lié) : filtre « Non rattachés », tags d'objectifs,
« reprendre titre objectif ».

## 1. Multisélection et actions groupées (décision CM-MULTI)

Aucune copie : l'atelier branche la multisélection d'`AtelierEditeur` (v0.13.6.8) dans
sa liste (`gererClicItem`, `gererClicDroitItem`, `selected`) : Ctrl+clic, Maj+clic
(plage), clic droit (menu « Valider la sélection / Repasser en cours / Annuler »), barre
« n sélectionnés · ✓ Valider · ⟲ En cours · ✕ », Échap.

Deux crochets ajoutés à `AtelierEditeur`, utilisés par l'action unitaire ET groupée :

- `urlEtat(id)` : URL du PATCH `{etat_code}` ; par défaut `/api/atomes/<type>/<id>/etat`
  (inchangé pour les cinq autres ateliers) ; Carte mentale : la route de la partie
  (même route que « Valider » depuis v0.56.1).
- `raisonHorsEtat(élément)` : raison d'exclure un élément (null par défaut) ; Carte
  mentale : « sans carte » (rien à valider), « séquence validée » (lecture seule).
  Les exclus ne sont pas envoyés ; le résumé les compte par raison :
  « 3 validé, 1 ignoré (sans carte) ». Tout exclu : toast d'erreur.

Résumé de l'action groupée (tous les ateliers) : le motif du premier refus du serveur
est ajouté (« 1 en échec : Séquence validée : … »).

Sélection vidée quand la liste de l'atelier change de niveau ou de séquence : en mode
séquence, l'identifiant « 2 » désignerait la partie 2 d'une autre séquence.

Serveur : `PATCH …/cartes-mentales/<n>` avec seulement `etat_code` sur une partie sans
carte → 409 `carte_absente` (avant : tentative de créer une carte vide, refusée par le
contrôle de la source avec un message trompeur). Séquence validée : 409 inchangé.

## 2. Mode côte-à-côte (décision CM-SPLIT)

Préférences › Rendu PDF › « Mode côte-à-côte » : règles `body.atelier-mode-split` de
`app.css` étendues à `#atl-cm-form` / `#atl-cm-rendu` ; `prefSplitAppliquer` connaît
`ATELIER_CARTE_MENTALE` ; poignée édition ↔ rendu (`atelierInstallerSplitterGrid`, clé
`split:atl-cm:formrendu`).

**Corrigé au passage (Carte d'automatisme)** : en mode côte-à-côte, ses onglets étaient
masqués mais sa zone de rendu jamais affichée (aucune règle) : le PDF était
inaccessible. Ajout de `#atl-carte-form` / `#atl-carte-rendu` aux mêmes règles.

## 3. Liens et Recherche (décision CM-LIENS)

- Lien direct `/?atelier=carte_mentale&niveau=N09&seq=S05&atome=2` (atome = numéro de
  partie), comme les cinq autres ateliers ; « Ouvrir » d'un résultat de Recherche et
  Ctrl+clic (nouvel onglet) par le même mécanisme (`compilBatchOuvrirAtelier`).
- **Corrigé au passage (tous les ateliers)** : le lien direct écrivait la portée dans
  `localStorage` après la lecture de `ATL_SELECTIONS` ; la liste restait sur la
  séquence précédente (l'élément s'ouvrait par son identifiant unique). La portée est
  posée aussi dans `ATL_SELECTIONS`. Indispensable pour la carte mentale.
- Recherche : type `carte_mentale` (`TYPES_RECHERCHE` = `ORDRE_TYPES` + cartes
  mentales ; titre et source LaTeX ; identifiant « N09/S03/Carte mentale P2 ») ; groupe
  « Cartes mentales » et option du filtre de type. Le rendu par lot (`ORDRE_TYPES`) est
  inchangé.
- Atelier Séquence : « ✏️ Modifier dans l'atelier Carte mentale » ouvre la partie
  choisie dans la liste déroulante (sinon l'atelier, comme avant).

## Signalé, non corrigé (Laurent décide)

- Exercice, mode « toutes les séquences » : ni en-tête ni préfixe de séquence (sections
  par série seulement).
- Règle côte-à-côte d'Exercice sur `#atl-exo-form` (identifiant disparu ; fonctionne
  grâce au style en ligne).
- Rendu par lot (Outils généraux) sans les cartes mentales (déjà compilées par l'atelier
  Séquence : « Compiler les cartes mentales », « 📦 Tout compiler »).

## Tests

- `tests_js/v0_56_3_carte_mentale_fonctions_communes.test.js` (20) : gestionnaires
  communs dans la liste, plage, barre, menu, Échap ; validation groupée (un PATCH par
  partie), parties sans carte ignorées, « déjà à jour », repasser en cours, séquence
  validée (mode séquence et « toutes »), refus du serveur avec motif, carte ouverte
  verrouillée, sélection vidée au changement de séquence, `urlEtat` par défaut inchangé ;
  côte-à-côte ; lien direct (portée immédiate) ; Recherche ; lien depuis Séquence.
- `tests/test_v0_56_3_carte_mentale_fonctions_communes.py` (6) : validation groupée
  côté serveur, 409 `carte_absente` sans création, séquence validée, Recherche (contenu,
  identifiant, filtres, route, sans table), `ORDRE_TYPES` inchangé.

## Contrôles

- pytest : 4892 réussis, 8 ignorés, 0 échec (v0.56.2 : 4886). Dernier passage complet :
  4891 + 1 échec intermittent, `test_v0_51_9_depot.py::test_releve_au_demarrage`
  (fil de relève du dépôt, délai de 5 s ; sans lien avec cette version), réussi
  ensuite 4 fois sur 4, et sur le code v0.56.2.
- vitest : 381 réussis (40 fichiers).
- Même `.tex` : 1590 sorties comparées (code v0.56.2 / v0.56.3, même base) : 0 différence.

## Appli

- Nouveaux : `tests/test_v0_56_3_carte_mentale_fonctions_communes.py`,
  `tests_js/v0_56_3_carte_mentale_fonctions_communes.test.js`, `doc/redemarrage_v0_56_3.md`.
- Modifiés : `static/atelier_editeur.js`, `static/atelier_carte_mentale.js`,
  `static/atelier_seqniv_assemblage.js`, `static/app.js`, `static/app.css`,
  `templates/index.html`, `routes/livret_sequence.py`, `routes/recherche.py`,
  `services/recherche_atomes.py`, `doc/ETAT_COURANT.md`.
- Aucun fichier supprimé.

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`).
2. Depuis `appli\` : `..\outils\python\python.exe .\outils\verifier_md5.py` (facultatif).
3. Relancer l'appli ; recharger la page (Ctrl+F5) pour les fichiers `static\`.

## Risques

- Faibles : interface seulement, plus un refus serveur nouveau (409) pour un cas qui
  échouait déjà (400). Les cinq autres ateliers gardent la même route d'état ; seul le
  texte du résumé d'une action groupée change (raisons d'exclusion, motif d'échec).
- Le lien direct pose désormais la portée immédiatement dans tous les ateliers : la
  barre de portée montre la séquence de l'atome ouvert (avant : la précédente).
