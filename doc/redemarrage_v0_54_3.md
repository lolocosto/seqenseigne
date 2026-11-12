# Redémarrage v0.54.3 — tableau décimal à quatre classes (fiche de cours de S01)

## Besoin (Laurent, 12 novembre 2026)

> « Peux-tu modifier les tableaux de décomposition d'un nombre dans la fiche de cours de la
> séquence 1 pour qu'ils incluent les classes des millions et des milliards ? Ça implique de
> modifier la macro \seqLocTableauDecimal dans seqenseigne-style6e.dtx. »

## Audit (état de la v0.54.2)

- `\seqLocTableauDecimal{lignes}` (module v0.11) : Milliers | Unités | virgule | Partie
  décimale, 10 cellules par ligne. `\seqLocTableauNumeration` a déjà les 4 classes (entiers ;
  milliards sans couleur, millions en `seqLocMillions`).
- Usages dans les lots : S01 — fiche de résumé de S01-02 (le seul usage dans une fiche) et
  remédiation de l'exercice F n°5 de S01-02 ; S02 — 1 (exercice) ; S03 — 2 (exercices).
  La fiche de S01-03 a un `\seqLocTableauNumeration` (déjà 4 classes).
- Le tableau de la fiche S01-02 apparaît dans le livret S01 (élève, corrigé), les fiches de
  cours S01 et annuelles, les corrigés enseignant S01 et le plan de travail S01 (« À retenir »
  en entier).

## Décisions

- **D-OPTION** — Argument optionnel plutôt qu'une macro sœur :
  `\seqLocTableauDecimal[4]{lignes}` = 4 classes (milliards, millions, milliers, unités,
  virgule, dixièmes, centièmes, millièmes : **16** cellules par ligne — 4 × 3 + 1 + 3 ; le brief
  disait 19 par erreur de compte, la partie décimale garde ses 3 rangs). Sans argument (ou
  `[2]`), le corps v0.11 est repris caractère pour caractère (`\seqLoc@TableauDecimalDeux`) :
  les exercices de S01, S02 et S03 gardent leur rendu (pages des livrets S01, S02, S03 comparées
  en image, ancien et nouveau `.sty` : identiques, hors la page de la fiche S01-02). Autre valeur
  que 2 ou 4 : `\PackageError`. Aucune nouvelle macro publique : `services/style6e.py` ne change
  que de `VERSION` (v0.12).
- **D-LARGEUR** — Colonnes de 0,6 cm (0,62 cm à 2 classes), `\tabcolsep` 2,5 pt, rangs et noms
  de classes en `\footnotesize`, filet de 0,9 pt entre les classes : environ 12,5 cm, comme
  `\seqLocTableauNumeration` ; tient dans une fiche de cours et dans le plan de travail (aucune
  boîte trop large). Des colonnes de 0,5 cm élargissaient la dernière colonne (« Partie
  décimale » plus large que trois colonnes).
- **D-COULEUR** — Nouvelle couleur `seqLocMilliards` = blanc, comme la classe des milliards de
  `\seqLocTableauNumeration` (inchangé) ; millions en `seqLocMillions`. En noir et blanc, les
  classes se lisent par les filets épais et les teintes de gris (aperçu vérifié).
- **D-S01** — Lot S01 : la fiche de S01-02 passe à `[4]` (6 cases vides à gauche de 5 048,372).
  La fiche de S01-03 (`\seqLocTableauNumeration`, déjà milliards → unités) est laissée telle
  quelle ; exercices et remédiations inchangés (non demandé). Sauvegarde
  `S01.avant_0543.json`, `rapport.md` complété.

## Appli

- Modifiés : `paquet/seqenseigne-style6e.dtx` (v0.12, doc, `\changes`), `.sty` régénéré
  (`tex seqenseigne.ins` : seul `seqenseigne-style6e.sty` change), `paquet/CHANGELOG.md`,
  `services/style6e.py` (`VERSION`), 6 tests qui fixent la version du module.
- Nouveau : `tests/test_v0_54_3_tableau_decimal.py` (7).
- Aucune migration, aucun générateur modifié : cycle 4, 6e et mises en route sortent le même
  `.tex` qu'en v0.54.2 sur la même base (1589 sorties) ; après réimport, seuls changent les
  documents qui contiennent la fiche S01-02 (livret S01 élève et corrigé, fiches de cours S01
  et annuelles, corrigés S01, plan de travail S01), d'une ligne. N11_v2025 : rien d'écrit.

## Déploiement (Windows, appli fermée)

1. Sauvegarder `data\seqenseigne.db`.
2. Dézipper à la racine (à côté d'`appli\`) : `appli\…` et `reference\lot6e\S01\S01.json`.
3. Module LaTeX v0.12, depuis la racine : `copy /Y appli\paquet\seqenseigne-style6e.dtx
   reference\paquet\`, puis `cd reference\paquet`, `tex seqenseigne.ins` et `cd ..\..`.
4. Depuis `appli\` : `..\outils\python\python.exe .\outils\import_lot6e.py` (essai à blanc :
   une seule « fiche [mise à jour : 1] », S01-02), puis
   `..\outils\python\python.exe .\outils\import_lot6e.py --apply`.
5. Lancer l'appli ; Atelier › N09/S01 › « Rendu PDF » : livret, fiches de cours.
