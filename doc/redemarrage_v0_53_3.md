# Redémarrage v0.53.3 — tableau de conversion commun, touche π, séance 4 de M02, onglet « Rendu PDF » des mises en route

## Besoins (Laurent, 25 octobre 2026)

1. « Une macro commune de tableau de conversion pour assurer une mise en forme homogène des
   tableaux de conversion. »
2. Touche π (photos des claviers) : TI-Collège Plus, touche π directe à gauche de « sin » (la
   fonction seconde « angle » est au-dessus, ne pas appuyer sur 2nde) ; Casio fx-92 Collège,
   π en bleu au-dessus de la touche 7 : SECONDE puis 7.
3. M02, séance 4 : refaire l'item 90 − 52,3 (zéro à ajouter) pour que toute la séance colle au
   critère F.
4. Onglet « Rendu PDF » d'une Mnn (ajout du 25 octobre, après déploiement de la v0.53.2) : les
   sélecteurs de droite seulement quand ils ont un sens pour le document ; « Test n° » borné
   (serveur compris) ; bouton « Tout compiler » avec progression, statuts et archive ZIP.

## 1. Décisions

- **D-TC — Tableau de conversion commun** : module `seqenseigne-style6e` **v0.11**,
  `\seqTableauConversionSix[options]{lignes}` et `\seqLigneConversionSix[note]{nombre}{unité}`.
  Nommées en `…Six` comme les autres macros publiques du module : l'import les contrôle déjà
  (`RE_SIX`), et un nom absent du module est signalé dans l'essai à blanc.
  - Options : `grandeur` = `longueur` (défaut) | `masse` | `contenance` | `aire` (deux colonnes
    par unité, filet gris entre elles) ; `hectares` (= `ha`) ou `hectares=ha-a-ca` (aires) ;
    `prefixes`, `valeurs` (ligne « Préfixe », ligne « Valeur », colonne d'étiquettes) ; `note`
    (colonne de commentaire à droite) ; `compact` (caractères et lignes plus serrés, pour un
    exercice au quart d'A4 déjà rempli) ; `colonne` (0,8 cm par défaut : le tableau mesure environ
    6 cm et tient dans un exercice au quart d'A4) ou `largeur` (totale).
  - Une ligne place le nombre un chiffre par colonne, le chiffre des unités dans la colonne de
    l'unité (colonne de droite pour une aire ; `ha`, `a`, `ca` = hm, dam, m) ; virgule posée
    après le chiffre des unités (`\rlap`) ; zéros de tête gardés (0005,6 dans la colonne des
    dm : 0,005 6 hm = 5,6 dm). Sans étoile : chiffres **donnés** (les deux versions). Étoile :
    **réponse** (`\seqLocCellule` : vide en version élève, rouge gras au corrigé et dans la
    version complète). Unité absente : erreur LaTeX explicite ; chiffres hors du tableau :
    avertissement.
  - Pas de tableau de durées : on compte par 60 et aucun lot n'en a besoin.
  - Implémentation en `expl3` (préambule et lignes calculés, rendus d'un coup dans la cellule) ;
    `colortbl` requis par le module (déjà chargé par le cœur du paquet).
- **Inventaire des lots** : les seuls tableaux de conversion sont ceux de M03 (fiche partie 1 :
  unités / préfixes / valeurs et placement ; fiche partie 2 : tableau des aires), remplacés par
  la macro. M02, M04 et les lots S n'en ont pas (rien à modifier dans S). M03, séances 3 et 7 :
  l'astuce renvoie à un tableau à remplir imprimé à côté d'elle (une ligne réponse : calcul 1,
  calcul 3, option `compact`), dans la bande du quart d'A4 (131,7 et 135,0 pt pour 147,3 pt ;
  vérifié dans la planche de l'appli, qui ajoute une ligne d'en-tête).
- **Touche π** (M04, fiche de la partie 3, versions élève et complète) : texte de Laurent ; la
  réserve « touche à vérifier » du rapport du lot est levée.
- **M02 séance 4** : item 5 = 90,4 − 52,3 = 38,1 (retenue gardée, aucun zéro) ; corrigé rédigé
  sans « zéros » ; l'exemple 90 − 52,3 de la fiche est gardé, car il explique le zéro à ajouter
  (critère A, séance 9 dans le cahier).

- **D-SEL — Sélecteurs par document** : table `SELECTEURS_DOCUMENT_MER` (serveur :
  `services/mises_en_route_6e.py` ; navigateur : `static/seqniv_pur.js`, comparées par un test) :

  | Document | Sélecteurs affichés |
  |---|---|
  | Fiche de cours | Version, Exemplaires |
  | Exercices de séance | Version, Par A4 |
  | Test court | Version, Exemplaires, Test n°, Sujet |
  | Plan de séquence | aucun |
  | Dossier enseignant | aucun (une seule version) |
  | Activités complémentaires | Version |

  Les sélecteurs masqués gardent leur valeur (sans effet sur le document). L'onglet des
  séquences principales (Snn) n'a pas ces sélecteurs (livret : cases à cocher) : inchangé.
- **Test n° borné** : de 1 au nombre de tests courts de la partie choisie (ou de toute la
  séquence) ; une valeur hors bornes est ramenée dans les bornes à la saisie et à l'envoi
  (`SeqnivPur.bornerTestMer`, `max` du champ mis à jour au changement de partie) ; le serveur
  refuse aussi (400, « test n° 2 hors bornes, de 1 à 1 (… dans la partie 1) », « le premier test
  court est le n° 1 »).
- **D-TOUT — « Tout compiler »** (`services/mer_tout_compiler.py`, route
  `GET …/<Mnn>/mer/tout-compiler?partie=n`) : même mécanisme que le rendu par lot de
  l'administration (flux SSE lu par `EventSource`, un événement par document, cache de
  compilation `cache_rendus`, annulation par fermeture de la connexion — bouton « Annuler » —,
  abandon après N erreurs d'infrastructure consécutives, réglage du rendu par lot).
  **D-TOUT-LISTE** : pour la partie choisie ou chaque partie de la séquence, fiche élève et
  complète, exercices de séance élève et corrigé (4 par A4), chaque test court en sujets A et B
  élève et corrigé, plan, dossier enseignant, activités complémentaires élève et corrigé (si la
  partie en a). Noms : `M03_p1_fiche_eleve.pdf`, `M03_p1_seances_4parA4_corrige.pdf`,
  `M03_p1_test1_A_eleve.pdf`, `M03_p1_dossier_enseignant.pdf`… Statuts affichés au fil de l'eau
  (succès, succès (cache), échec avec lien « log » : `GET …/mer/echec/<nom>.log`, .tex et .log
  gardés dans `cache_rendus\echecs_mer\`), puis téléchargement automatique de l'archive
  `M03_partie1_documents_<date>.zip` (`data\rapports\`, `GET …/mer/archive/<nom>.zip`).
  Routes de la catégorie « atelier » (blueprint `livret_sequence`, `services/profils.py`).

## 2. Appli

- `services/style6e.py` : `MACROS` (+ `seqTableauConversionSix`, `seqLigneConversionSix`),
  `VERSION = "v0.11"` ; `outils/import_lot6e.py` : les messages citent `VERSION` au lieu de
  « v0.10 » écrit en dur.
- `services/mises_en_route_6e.py` (D-SEL, messages des bornes du test n°),
  `services/mer_tout_compiler.py` (nouveau), `routes/livret_sequence.py` (3 routes),
  `static/seqniv_pur.js`, `static/atelier_seqniv_assemblage.js`.
- Cycle 4 et principal de 6e : même `.tex` qu'en v0.53.2 (1 136 sorties comparées, identiques).
- Tests : `tests/test_v0_53_3_tableau_conversion.py`, `tests/test_v0_53_3_rendu_mer.py`,
  `tests_js/mer_rendu_selecteurs.test.js` ; adaptés (changement voulu, module v0.11) :
  `tests/test_v0_52_4_modeles.py`, `test_v0_52_5_objectifs_s05.py`, `test_v0_52_7_marqueurs.py`,
  `test_v0_52_8_calculatrice_tp_astuce.py`, `test_v0_53_0_mises_en_route.py`,
  `test_v0_53_1_mer_parties.py`.

## 3. Lots

`reference/lot6e/M02`, `M03`, `M04` (générateurs `work/gen/` mis à jour ; M04 : la correction
d'assemblage v0.53.2 de l'AC 2 est reportée dans `ac.py`). L'essai à blanc montre : M02-02
« mis à jour : 1 » (MR04) ; M03 fiches des parties 1 et 2 « mise à jour », M03-02 et M03-12
« mis à jour : 1 » (MR03, MR07) ; M04 fiche de la partie 3 « mise à jour ».

## 4. Résultats

Voir `SP/livraison_v0533/` : import S01–S13 + M01–M07 (essai, `--apply`, second `--apply`
sans changement), compilation de tous les documents des parties de M02, M03 et M04, pytest,
vitest.

## Déploiement (Windows, appli fermée)

1. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et `reference\lot6e\…`.
2. Module LaTeX v0.11, depuis la racine : `copy /Y appli\paquet\seqenseigne-style6e.dtx
   reference\paquet\`, puis `cd reference\paquet`, `tex seqenseigne.ins` et `cd ..\..`.
3. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py` (essai à blanc),
   puis `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.
4. Lancer l'appli ; Atelier › séquence N09/M03 › onglet « Rendu PDF » : fiche de cours,
   parties 1 et 2 ; exercices de séance, partie 1 (séance 3) et partie 2 (séance 7) ;
   « 📦 Tout compiler » (partie 1, puis toute la séquence).
