# Marche à suivre — créer les deux référentiels internes de 6e

Pour Laurent. Écrite le 25 octobre 2026 (v0.54.0), mise à jour le 13 novembre (v0.56.3), **mise à jour le 16 novembre (v0.58.0)** : le référentiel interne de 6e se crée **après la migration des codes**, directement en codes A1 (A1 à E1 au lieu de S01 à S13). Les écrans et les chiffres sont les mêmes ; seuls les codes changent.
État de ta base d'atelier le 16 novembre (7 h 52) : **aucun référentiel interne de 6e** (seulement X2026_N09, externe, et M2026_N09) ; les 20 séquences S01–S13 et M01–M07 sont « en cours ».

**Correspondance des codes de 6e** (table complète en tête de `outils\ref6e_v2.md`) :

| Avant | Après | Séquence |
| --- | --- | --- |
| S01 à S04 | A1 à A4 | Nombres entiers et décimaux, fractions ; Comparaison ; Opérations ; Pré-algèbre |
| S05 à S09 | B1 à B5 | Points, segments, droites ; Cercles ; Angles ; Triangles ; Symétrie axiale |
| S10, S11 | C1, C2 | Gestion de données ; Probabilité |
| S12 | D1 | Proportionnalité |
| S13 | E1 | Pensée informatique |
| M01 à M07 | inchangées | mises en route (thème de M03, M04 : F « Grandeurs et mesures ») |

Les objectifs suivent : S01-02 devient A1-02 (livrets, plans de travail, barèmes).

Tout se fait **dans l'appli**, sur le PC qui a la base de
l'atelier (profil atelier ou complet). Compter environ une heure, compilation comprise.
Essai complet fait sur une copie de la base de test : voir « Ce que donne l'essai » à la fin.

## 0. Avant de commencer

1. Appli fermée, sauvegarder la base de l'atelier : copier `data_atelier\seqenseigne.db` (ou, appli ouverte,
   Système › Administration › « Exporter la base SQLite »).
2. **La migration des codes est faite** (v0.58.0, `outils\migrer_themes_codes_2027.py --apply`,
   marche à suivre de la migration dans `doc\redemarrage_v0_58_0.md` et le rapport de livraison) :
   dans l'atelier de 6e, les séquences s'appellent A1 à E1. Si elle ne l'est pas, la faire
   d'abord : un référentiel créé avant serait figé en S01–S13.
3. Lancer l'appli depuis `appli\` : `.\lancer.bat atelier` (ou `.\lancer.bat`).
4. Les lots (`reference\lot6e\S01` …) restent écrits en S01 : l'outil d'import les lit en A1
   (« lot S01 lu en A1 ») et ne recrée jamais de séquence S…. Ne plus réimporter de lot après l'étape 1 : l'import ne réécrit jamais un exercice, une
   fiche, une évaluation ni une séquence **validés** (il le signale). Pour corriger un lot
   ensuite : repasser l'élément « en cours », réimporter, revalider.

## 1. Valider les atomes (exercices et fiches)

Conception › niveau **6e** › atelier **Exercices**, puis atelier **Fiches de résumé** ; pour
chaque séquence A1 à E1 **et** M01 à M07 :

1. dans la liste de gauche, clic sur le premier élément, **Maj + clic** sur le dernier ;
2. clic droit › **✓ Valider la sélection** ;
3. le message dit « n validé(s) » ; s'il dit « n en échec », ouvrir l'élément en rouge :
   la raison s'affiche à la validation (énoncé vide, corrigé vide, remédiation incomplète,
   sujet B vide pour une évaluation, fiche sans section).

Les archives X01–X16 n'ont pas besoin d'être validées (hors de tout référentiel).
Volume (base de test v0.56) : environ 1 100 exercices et fiches à valider. Les cartes mentales se valident de la même façon dans l'atelier **Carte mentale** (multisélection depuis la v0.56.3).

## 2. Valider les évaluations et les tests courts

Module **Évaluations** (niveau 6e) : ouvrir chaque évaluation, bouton **Valider**.
18 évaluations sur 20 (A1–E1) et 22 tests courts sur 10 (un par partie de mise en route).

## 3. Valider les séquences

Atelier d'**assemblage** de chaque séquence (A1 à E1, puis M01 à M07), bouton **Valider**
de la barre d'outils.

- A1–E1 : contrôle par objectif d'exercices (au moins un F et un A, critères F et A, la
  fiche de résumé de l'objectif).
- M01–M07 (nouveau en v0.54.0) : contrôle **MR6** (fiche de cours de chaque partie, au moins
  un exercice de séance par objectif). Les avertissements (exercices ≠ séances prévues,
  partie sans test court) ne bloquent pas.
- **Si une séquence ne se valide pas** : la liste des raisons s'affiche ; corriger dans
  l'atelier concerné (objectif, critère, fiche, exercice), ou dans le lot puis réimporter
  (séquence « en cours »). Ne pas forcer : le référentiel ne deviendra pas « validé » tant
  qu'une séquence ne l'est pas. Sur la base de test, aucune séquence ne bloque
  (`blocages_validation.md`).
- Une séquence validée se verrouille (structure non modifiable) : **Repasser en cours** pour
  la modifier.

## 4. Créer le référentiel principal

Conception › niveau **6e** › onglet **Référentiel**, colonne de gauche, zone de création :

1. Source **Interne**, Type **Référentiel principal**, Modèle **Fiches de résumé par
   objectif** (proposé d'office en 6e), description par exemple « Principal 6e, A1–E1 » ;
2. **+ Créer** : l'appli affiche **« Avant de créer : Référentiel principal »** —
   vérifier : état de départ « en cours » ; **13 séquences (A1 à E1), 20 parties, 52 objectifs
   (+ 20 « Connaître le cours »)** ; documents : livret de séquence, fiches de cours,
   corrigés enseignant, évaluations, travaux personnels, activités complémentaires, plans de
   travail, séances d'atelier ; préparation : 13/13 séquences validées, 0 atome et
   0 évaluation non validés (si ce n'est pas le cas, revenir aux étapes 1 à 3) ;
3. **Confirmer la création**. Il s'appelle **« 6e — 2026-2027 — Principal »**.

L'arbre (onglet « Tableau de bord ») ne montre que A1–E1, rangées par thème A à E (plus les
mises en route ni les archives X01–X16).

## 5. Créer le référentiel des mises en route

Même zone : Source **Interne**, Type **Référentiel de mises en route**, Modèle **Fiches de
résumé par objectif**, description « Mises en route 6e, M01–M07 », **+ Créer**. Vérifier
dans l'aperçu : **7 séquences, 22 parties, 25 objectifs, 131 séances** ; documents :
fiches de cours, exercices de séance, tests courts, activités complémentaires, dossier
enseignant ; 7/7 séquences validées. **Confirmer la création**. Créé après le principal, il
s'appelle **« 6e — 2026-2027 — MER b »** (la lettre distingue les deux référentiels de
l'année ; la description dit ce que c'est).

## 6. Documents à publier (pour chacun des deux)

Sélectionner le référentiel › onglet **Documents à publier** :

1. cocher **actif** pour chaque document voulu, régler ses options :
   - principal : livret de séquence (version élève, avec activités, avec E, remédiations
     après l'exercice), fiches de cours (par séquence), corrigés enseignant, évaluations
     (sujet A, élève), travaux personnels, activités complémentaires, plans de travail,
     séances d'atelier ;
   - mises en route : fiches de cours (élève = à compléter ; « complète » si on la veut
     remplie), exercices de séance (élève, 4 par A4), tests courts (sujet A, élève),
     activités complémentaires (élève), dossier enseignant (toujours corrigé : plan, fiche
     complète, corrigés, tests A et B corrigés, activités corrigées) — **un PDF par partie**
     (par test court pour les tests) ;
2. **Compiler** chaque document (barre de progression) ; un échec affiche son log ;
3. une seule version par type : la version corrigée des exercices et des tests est dans le
   dossier enseignant (mises en route) ou les « corrigés enseignant » (principal).

## 7. Validation puis verrouillage

1. Onglet Tableau de bord : **Revérifier l'éligibilité** → « Référentiel éligible » et état
   **validé** (pastille verte). Sinon la liste dit ce qui manque : atomes, évaluations,
   séquences non validées (nouveau), documents non compilés ou **périmés** (un atome du
   niveau modifié après la compilation : recompiler).
2. **Verrouiller** : le message dit le contenu figé (principal : 13 séquences, 20 parties,
   72 objectifs ; mises en route : 7 séquences, 22 parties, 25 objectifs) et le nombre de
   PDF copiés. Verrouiller les mises en route **n'annule plus** le principal (et
   inversement) ; deux principaux de la même année restent concurrents (demande de
   confirmation, comme avant).
3. Format d'échange : **Vérifier** → « Format valide », 13 (ou 7) séquences, 20 (ou 22)
   parties, n documents, version 1.2 ou 1.3 (principal), **1.4** (mises en route : documents
   rangés par partie).

## 8. Publication vers l'appli de classe

1. Tableau de bord (atelier) › tuile **Publication** : cocher les deux référentiels
   (« publiables » : verrouillés) › créer le paquet ; il part par l'API ou la boîte aux
   lettres comme d'habitude.
2. Appli de classe : Système › Administration › **Import référentiels** (si l'import n'est
   pas automatique) : **Analyser** (deux « nouveau ») puis **Importer**.

## 9. Côté classe : ce qu'il faut vérifier (sans encore toucher aux progressions)

- Suivi › **Progression principale** : « 6e — 2026-2027 — Principal » est proposé ; ses 20
  parties apparaissent (codes A1…E1 ; M2026_N09 et X2026_N09 gardent les leurs) (avec **0 séance** : les objectifs du principal n'ont pas encore de
  séances, ce sera le travail des progressions).
- Suivi › **Progression de MER** : « 6e — 2026-2027 — MER b » est proposé à côté de
  M2026_N09 ; ses 22 parties s'affichent avec leurs séances (M01 Tables de multiplication
  (6)…), se posent **dans n'importe quel ordre** et se déplacent (↑ ↓).
- **Attention** : la progression de MER de l'année en cours utilise M2026_N09. **Changer de
  référentiel efface les parties déjà posées** (comportement existant). Ne pas basculer la
  classe avant le chantier des progressions ; la table `correspondance_M2026_N09.md` dira
  quelles parties reposer.
- Le bouton « 📄 documents » d'une partie interne dit que l'association des documents
  viendra avec les progressions.

## 10. Si quelque chose ne va pas

| Symptôme | Que faire |
|---|---|
| « + Créer » n'affiche pas l'aperçu | vérifier qu'un niveau (6e) est choisi dans la portée ; recharger la page (Ctrl + F5) |
| Aperçu : 0 séquence de mise en route | les lots M01–M07 ne sont pas importés dans cette base |
| Une séquence refuse d'être validée | lire les raisons ; corriger (atelier ou lot + réimport, séquence « en cours ») ; voir `blocages_validation.md` |
| Le référentiel reste « en cours » | Revérifier l'éligibilité ; la liste dit quoi : souvent un document **périmé** après une retouche d'atome (recompiler) |
| Un document ne compile pas | « Erreurs » sous le document (log) ; le même document se compile seul dans l'onglet « Rendu PDF » de la séquence |
| Erreur au verrouillage | message explicite (état, éligibilité) ; rien n'est modifié |
| Il faut corriger après verrouillage | **Déverrouiller** (si aucune progression ne l'utilise) : l'instantané est retiré et la publication figée mise de côté (dossier `_publication_avant_<date>`) ; corriger, recompiler, reverrouiller ; le paquet suivant arrive côté classe comme une **mise à jour** (refusée si elle retire une séquence ou une partie déjà commencée) |

## Ce que donne l'essai v0.58.0 (copie de ta base du 16 novembre, migrée)

| Contrôle | Résultat |
|---|---|
| Migration (`--apply`) | cycle 3 en A1…E1, M01–M07 inchangées, X01–X16 intactes |
| Import des 20 lots de `reference\lot6e` | lus en A1, **0 créé, 0 mis à jour**, base identique après deux imports |
| Aperçu « Avant de créer » (principal) | **13 séquences A1…E1, 20 parties, 52 objectifs (+ 20)** — comme avant la migration |
| Aperçu (mises en route) | 7 séquences, 22 parties, 25 objectifs, 131 séances — comme avant |
| Livret de séquence A1 compilé | objectifs affichés A1-02 … A1-14 (aperçu `apercus\livret_6e_N09_A1_p1-01.png`) |

Les étapes 1 à 9 n'ont pas été rejouées en entier sur la base migrée (validation et compilation
de tous les documents : environ une heure) ; elles l'avaient été le 25 octobre (ci-dessous), et la
migration ne change que les codes.

## Ce que donnait l'essai (copie de la base de test, 25 octobre)

Fait par les routes de l'appli, dans l'ordre ci-dessus (`work/e2e.py`, résultats
`work/e2e/resultats.json`) :

| Étape | Résultat |
|---|---|
| 1-3 Validation | 932 exercices, 96 fiches, 40 évaluations et tests courts, 20 séquences : **0 refus** |
| 4-5 Création | aperçus conformes (13 / 20 / 52 + 20 ; 7 / 22 / 25, 131 séances) ; « 6e — 2026-2027 — Principal » (2026_N09) et « 6e — 2026-2027 — MER b » (2026_N09b) |
| 6 Documents | principal : 8 documents, 118 PDF ; mises en route : 5 documents, 89 PDF ; **0 échec**, environ 13 min de compilation en tout |
| 7 Verrouillage | les deux « validés » puis verrouillés, aucun annulé ; contenu figé 13 / 20 / 72 et 7 / 22 / 25 ; export valide (1.3 et 1.4) |
| 8 Publication | un paquet, 2 référentiels, 207 fichiers, 25,8 Mo ; base de classe de **test** neuve : 2 « nouveau », importés |
| 9 Côté classe | progression principale : 20 parties (0 séance) ; progression de MER : 22 parties, 5 posées dans un ordre libre (M05 p2, M01 p1, M03 p3, M02 p4, M01 p2) puis déplacées, aperçu théorique correct |
| N11_v2025 | empreinte, lignes de ses tables et export **identiques** avant / après |

Aperçus : `apercus/` (écran d'aperçu avant création, planning théorique de la classe,
fiche de cours, exercices de séance, test court, dossier enseignant, livret S12).
