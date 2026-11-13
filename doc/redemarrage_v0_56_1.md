# Redémarrage v0.56.1 — atelier Carte mentale harmonisé ; miroir des planches de cartes rétabli

> Base de comparaison : 873e3b7 « v0.56 » (déployée). Aucune migration, aucune table,
> aucun `.dtx` modifié (pas de `tex seqenseigne.ins`), aucun import de lot.

## Besoin (Laurent, 13 novembre 2026)

> « Harmoniser l'atelier Cartes Mentales avec les autres ateliers : filtres du panneau de
> gauche, onglets pour l'édition et le rendu dans le panneau central, etc. Ceci doit
> permettre d'avoir un UI semblable et aussi de réutiliser le code et les mécanismes des
> autres ateliers au lieu de tout réinventer. »

> Planches de cartes d'automatisme (16 exemplaires d'une carte) : le verso n'est plus en
> miroir pour l'impression recto-verso bord court, alors que le récap l'est toujours.

## 1. Atelier Carte mentale (décision CM-HARMONISE)

**Audit des ateliers de référence** (Fiche de résumé, Carte d'automatisme, Exercice ;
Évaluation pour les sélecteurs de rendu) — schéma commun :

- panneau de gauche : en-tête « + Créer », filtre d'état (Tous / En cours / Validé | filtre
  propre à l'atelier), liste `Atelier.rendreItemHtml` (identifiant, titre, tags, pastille) ;
  niveau et séquence par la barre de portée (`ATL_FILTRE_NIVEAU/SEQ`, rechargement de
  l'atelier actif par `atelier_filtres_hook.js`) ;
- panneau central : barre d'outils (titre, badge « modifié », badge d'état, Valider /
  Repasser en cours, Supprimer, Enregistrer), onglets Édition / Rendu PDF, zone de rendu
  (barre générée par `_assurerToolbarRendu`, viewer pdf.js, erreurs LaTeX cliquables,
  .tex brut, attente, invite) ;
- `AtelierEditeur` : liste, GET unitaire, création POST, enregistrement PATCH,
  suppression, validation, détection « modifié » par instantané, garde de sortie
  (modale 3 boutons, `atelier_garde.js`), verrou lecture seule d'un élément validé, rendu
  avec cache (`…/rendu-pdf/info`) et sauvegarde silencieuse avant compilation,
  « LaTeX généré » (Ctrl+L) ; textarea `latex-textarea` + « ✎ Éditer » (EditeurLatex).

La v0.55 n'en utilisait aucune (classe autonome, fetch maison, pas d'onglets, pas de garde
de sortie ni de badge, état par liste déroulante, URL dupliquées de `seqniv_pur.js`).

**Refonte** :

- `static/atelier_carte_mentale.js` : `AtelierCarteMentale extends AtelierEditeur`
  (préfixe `atl-cm`). Surcharges limitées aux spécificités : un élément **par partie**
  (identifiant = numéro de partie, carte présente ou absente ; une partie sans carte
  s'ouvre sur le modèle) ; `endpointBase` / `endpointRenduPdf` calculés depuis la séquence
  filtrée par `SeqnivPur.urlCartesMentales` (même URL que l'onglet « Rendu PDF » de la
  séquence) ; filtre « Sans carte » ; « + Créer » = carte de la partie ouverte ou de la
  première partie sans carte (bouton « Créer la carte de cette partie » dans le
  formulaire) ; Valider = PATCH `etat_code` ; séquence validée : formulaire verrouillé,
  Enregistrer / Supprimer / Valider masqués, « + Créer » désactivé ; rendu : « À compléter
  (élève) / Complète » et « Cette carte / Toutes les cartes de la séquence » dans la barre
  du rendu (`parametresRendu`). Avertissement du contrôle (hors 4 à 8 branches) après
  l'enregistrement. Garde de sortie enregistrée (« Carte mentale ») ; Ctrl+L
  (`static/app.js`) ; libellé de la modale LaTeX (`static/atelier_commun.js`).
- `templates/index.html` : panneau `atl-carte_mentale` refait sur le schéma de Fiche de
  résumé / Carte d'automatisme.
- API (`routes/livret_sequence.py`, même famille d'URL, catégorie « atelier » par le
  blueprint) : `POST …/cartes-mentales` {numero} (créer depuis le modèle ; 409 si la carte
  existe ou si la séquence est validée) ; `GET …/cartes-mentales/<n>` (élément) ;
  `PATCH` (et `PUT`) `…/<n>` : clés absentes = valeurs actuelles, réponse = élément +
  `etat` + `avertissements` ; `…/<n>/rendu-pdf/info`, `…/<n>/rendu-pdf`,
  `…/<n>/rendu-tex` (`?version=eleve|corrigee&portee=partie|sequence`) : même générateur
  que le document « Cartes mentales » de la séquence (`generer_cartes_mentales_6e`) et même
  compilation que le livret (`_reponse_compilation`, factorisée depuis
  `api_livret_sequence_pdf`). Partie sans carte : 400 au format des erreurs de
  compilation (« Aucune carte mentale… »), affiché par l'onglet Rendu.
- `services/cartes_mentales.py` : `MODELE` (une seule source, auparavant dans le JS) et
  `element_atelier`.
- Les deux modèles de livret restent couverts (aucun test de modèle dans l'atelier ; tests
  cycle 4 et 6e de la v0.55 inchangés et verts). Liens depuis « Rendu PDF » de la séquence
  conservés (`cmOuvrirAtelier`, `cmCompiler` inchangés).

**Supprimé** (dans le même fichier, réécrit) : la classe autonome v0.55 (`choisir`,
`enregistrer(voir)`, `compiler`, `_json`, `_afficherListe`, `_afficherEditeur`), ses URL
dupliquées (`urlListe`, `urlPdf`), le modèle JS, la liste déroulante d'état, l'iframe
`atl-cm-pdf` et les identifiants `atl-cm-liste`, `atl-cm-etat-code`, `atl-cm-version`,
`atl-cm-portee`, `atl-cm-rendu-etat`, `atl-cm-btn-voir`. Aucun fichier supprimé.

Captures avant / après : `apercus/` de la livraison.

## 2. Miroir du verso des planches (décision PLANCHE-MIROIR)

**Origine de la régression** (git `--all`, docs) :

- v0.29.0 : `_miroir_horizontal_verso` + `PLANCHE_NB_COLONNES` dans
  `services/render_carte_centralise.py`, appliqué au bloc verso de `rendre_carte_planche`,
  et `tests/test_v0_29_0_verso_miroir.py`.
- Entre la v0.29.0 et la v0.32.5, le fichier a été livré **sans** le miroir : la
  v0.32.5 signale déjà (« Dette repérée ») que le test importe une fonction qui n'existe
  plus. La seule livraison de l'intervalle qui modifie ce fichier est la **v0.32.4**
  (récap aligné, `rendre_ligne_recap`) : le fichier a vraisemblablement été reconstruit à
  partir d'une copie antérieure à la v0.29.0 (la refonte « pré-tirage suffixé » date de la
  v0.15.2.3, donc d'avant le correctif : ce n'est pas elle). Le premier commit git qui
  contient le fichier (bb0f389, v0.35, 28 septembre) ne l'a déjà plus ; l'historique git
  ne remonte pas plus loin, d'où le « vraisemblablement ».
- v0.41.0 (D2, commit 741decb) : le test est supprimé avec une justification fausse
  (« miroir passé côté LaTeX en v0.32.4 ») : seul le **récap** l'est
  (`\seqCarteRecapAjouteLigneCartes`) ; `\seqCartePlanche` place les cellules dans l'ordre
  reçu (vérifié dans `paquet/seqenseigne-carte-automatisme.sty`).

**Correctif** : `_miroir_horizontal_verso` et `PLANCHE_NB_COLONNES` rétablis, appliqués
aux versos de `rendre_carte_planche` pour toutes les cartes (sans effet visible sur une
carte fixe) : ordre [3,2,1,0, 7,6,5,4, 11,10,9,8, 15,14,13,12]. Paquet LaTeX inchangé.

**Tests** : `tests/test_v0_56_1_verso_miroir_planches.py` — ordre des cellules, longueur et
involution, réponse derrière l'énoncé pour une carte paramétrée (tirages suffixés), cartes
fixes inchangées, et un test de non-régression qui échoue si l'appel au miroir est retiré
(vérifié : 2 échecs sans le miroir).

**Vérification sur PDF** : planches N11/S01 de la base de test (copie ; N11_v2025 non
modifié), carte paramétrée CA03 « Carré d'un entier » : recto ligne 1 = 9², 6², 4², 9² ;
verso ligne 1 = 81, 16, 36, 81 ; cellule (1,1) du recto (9²) → (1,4) du verso (81), les 16
cellules vérifiées.

**Autres correctifs de la même époque** (cartes : récap, planches, atelier carte) — tous
présents : v0.32.4 récap par lignes de 4 (`rendre_ligne_recap`, appelé par
`livret_cartes_recap.py`), v0.32.4.1 recto/verso par `\long\def`, v0.32.4.2 `num=0` des
positions vides, v0.30.2 « Toutes les séquences » (route `/api/cartes` à séquence
optionnelle), v0.31.0 « Non rattachés » dans l'atelier Carte d'automatisme. Aucune autre
perte trouvée.

## Contrôles

- pytest : 4871 réussis, 8 ignorés, 0 échec (v0.56.0 : 4858). vitest : 347 réussis (38
  fichiers).
- Même `.tex` : 1590 sorties comparées (code v0.56 / v0.56.1, même base) : 30 diffèrent,
  toutes des planches de cartes (`livret_cartes_planches` N10 et planches cycle 4), et
  seulement par l'ordre des cellules du verso ; livrets, fiches, évaluations, récap des
  cartes, 6e, mises en route et export de N11_v2025 identiques.

## Appli

- Nouveaux : `tests/test_v0_56_1_atelier_carte_mentale.py`,
  `tests/test_v0_56_1_verso_miroir_planches.py`, `doc/redemarrage_v0_56_1.md`.
- Modifiés : `static/atelier_carte_mentale.js`, `templates/index.html`, `static/app.js`,
  `static/atelier_commun.js`, `routes/livret_sequence.py`, `services/cartes_mentales.py`,
  `services/render_carte_centralise.py`, `tests_js/cartes_mentales_atelier.test.js`,
  `doc/ETAT_COURANT.md`.

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`).
2. Depuis `appli\` : `..\outils\python\python.exe .\outils\verifier_md5.py` (facultatif).
3. Lancer l'appli ; atelier « Carte mentale » ; recompiler les planches de cartes
   (documents « Planches de cartes d'automatisme ») avant de les réimprimer.

## Risques

- Planches déjà publiées : leur PDF est en cache ou publié avec l'ancien ordre ; le `.tex`
  change, donc la prochaine compilation produit le bon ordre, mais un PDF déjà imprimé
  reste faux.
- Le miroir suppose l'impression bord court (confirmée en v0.29.0).
- Atelier : la portée « toutes les séquences » n'est pas proposée (une carte par partie
  d'une séquence) : message « Choisir une séquence précise ».
