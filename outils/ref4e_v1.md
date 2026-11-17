# Référentiel 4e — structure proposée (nouveau programme, rentrée 2027)

Nov 16, 2026 · @Laurent Coste

## Codes de la rentrée 2027 (v0.58.0)

Ce référentiel est écrit directement en codes de thème (lettre du thème + rang), ceux de la base depuis la migration (`outils/migrer_themes_codes_2027.py`, table `outils/correspondance_codes_2027.json`). Les anciens codes sont rappelés pour mémoire ; les objectifs se numérotent dans la séquence (S03-02 devient A1-02).

| Ancien | Nouveau | Numéro | Séquence (nom du cycle, appli) | Titre court de 4e (documents) | Thème |
| --- | --- | --- | --- | --- | --- |
| S03 | A1 | 11 | Calcul numérique | Nombres relatifs : produits et quotients | A |
| S15 | A2 | 12 | Nombres rationnels et arithmétique | Nombres rationnels | A |
| S01 | A3 | 13 | Représentations d'un nombre | Puissances et racine carrée | A |
| S05 | A4 | 14 | Calcul littéral | Calcul littéral et équations | A |
| S11 | B1 | 21 | Transformations géométriques | Translations et parallélogrammes | B |
| S12 | B2 | 22 | Géométrie plane | Triangles | B |
| S13 | B3 | 23 | Représentation en trois dimensions | Représentation de l'espace | B |
| S06 | C1 | 31 | Traitement, représentation et interprétation des données | Statistiques | C |
| S07 | C2 | 32 | Probabilités | Probabilités | C |
| S09 | D1 | 41 | Fonctions | Fonctions et programmes de calcul | D |
| S08 | D2 | 42 | Proportionnalité | Proportionnalité, ratios et pourcentages | D |
| S14 | E1 | 51 | Algorithmique et programmation | Algorithmique et programmation | E |

Séquences d'archive du cycle 4 : X02, X04, X10 (migration) ; l'archivage de la structure de 2025 (proposé, `besoins_appli_fiches_4e.md`) ajoutera X01, X03, X05 à X09, X11 à X14 au niveau N11.

## Cadre

Ce document est le référentiel de 4e au format de `outils/ref6e_v2.md`, prêt à servir de source de vérité aux outils d'import (transcription en `objectifs_4e.json`, comme `objectifs_6e.json` pour la 6e). **Rien n'a été écrit dans la base.**

- **Programme** : annexe 2 de l'arrêté du 18 février 2026 (cycle 4, partie 4e : 69 objectifs O01 à O69, 39 automatismes A01 à A39) ; exemples de réussite du document « Exemples pour la mise en œuvre — Cycle 4 — 2026 ».
- **Structure** : étapes 1 et 2 validées (`col4/ref4e_etape1_sequences.md`, `col4/ref4e_etape2_parties_objectifs.md`, décisions du 13 au 15 novembre 2026, `col4/DECISIONS_CYCLE4.md`) ; inventaire de l'étape 3 (`col4/ref4e_etape3_inventaire.md`).
- **Modèle** : « Fiches de résumé par objectif » (valeur technique `sixieme`), comme la 6e, **avec les cartes d'automatisme dans la progression principale** : pas de référentiel de mises en route ; les cartes sont rattachées aux objectifs du principal et révisées par Leitner en début de séance.
- **Budget** : 30 semaines, 3 séances d'apprentissage par semaine (90), une séance d'évaluation toutes les deux semaines (15, de 50 min utiles, 10 min par objectif évalué, 5 objectifs au plus) ; parties de 1, 2 ou 3 semaines entières ; la dernière séquence de l'année n'est pas évaluée.
- **Contenus existants** : atelier N11 (4e de l'ancien programme, codes A1 depuis la migration) ; contenus de 5e (N10) et de 3e (N12) à adapter quand la notion change de niveau. Codes d'atomes : N11/A1/F01 = exercice F01 de la séquence A1 de 4e (affiché EN01 au modèle Fiches) ; CA = carte d'automatisme ; C = notion ; M, FR = méthode et fiche de résumé du cycle 4.
- **Statut** : proposition à valider point par point (`col4/ref4e_etape3_inventaire.md`, § 6).

## Organisation actuelle et comparaison avec le programme

Le référentiel utilisé cette année, N11\_v2025 (figé), suit l'ancien programme : 14 séquences, 19 parties, 76 objectifs (instantané). Le nouveau programme de 4e retire de la 4e les puissances de 10 et l'écriture scientifique, Thalès et le cosinus, les rotations et les triangles égaux, les sections et le repérage dans l'espace, les nombres premiers ; il y ajoute les nombres rationnels (séquence A2), la droite des milieux, le cercle circonscrit au triangle rectangle, le rectangle sans équerre, la moyenne pondérée, les notations ensemblistes, les expériences à deux épreuves, la fluctuation, les ratios, le partage proportionnel, le coefficient multiplicateur et les programmes de calcul.

| Séquence | Statut | Programme de 4e |
| --- | --- | --- |
| A1 (S03) Calcul numérique | réduite | Produits, quotients et enchaînements avec les relatifs ; fractions déplacées en A2 |
| A2 (S15) Nombres rationnels et arithmétique | nouvelle | Simplifier, rationnels et opposés, produits et quotients de fractions, expressions, problèmes |
| A3 (S01) Représentations d'un nombre | réduite | Puissances d'exposant positif, racine carrée ; puissances de 10 et écriture scientifique en 3e |
| A4 (S05) Calcul littéral | gardée | Formules, pairs et impairs, distributivité, démonstrations, ax + b = c, mise en équation, tableur |
| B1 (S11) Transformations géométriques | réduite | Translation seule ; rotation et triangles égaux sortent |
| B2 (S12) Géométrie plane | refondue | Droite des milieux, cercle circonscrit au triangle rectangle, rectangle sans équerre, Pythagore ; Thalès et cosinus en 3e |
| B3 (S13) Représentation en trois dimensions | réduite | Pyramide et cône : reconnaître, patrons, volumes ; sections et repérage sortent |
| C1 (S06) Données | refondue | Moyenne pondérée, médiane, étendue, valeurs extrêmes, comparaison, tableur |
| C2 (S07) Probabilités | étendue | Notations ensemblistes, contraire, deux épreuves, fluctuation |
| D1 (S09) Fonctions | étendue | Programmes de calcul, dépendance, représentations |
| D2 (S08) Proportionnalité | refondue | Grandeurs quotients, rapports et ratios, quatrième proportionnelle, partage, pourcentages, coefficient multiplicateur |
| E1 (S14) Algorithmique et programmation | gardée | Conditions, variables, écrire et modifier un programme |

S02 (Comparaison de nombres), S04 (Divisibilité et nombres premiers) et S10 (Calcul de grandeurs) sont retirées du cycle (15 novembre 2026) : leurs contenus sont reclassés (A2, A3, B3, D2) ou archivés (X02, X04, X10).

## Cohérence interne

- **Objectifs** : {nobj} objectifs hors « Cours », {npar} parties, un objectif « Cours » par partie ; un objectif = une phrase avec un seul verbe d'action ; critères F et A propres à chaque objectif ; critère E commun.
- **Couverture** : les 69 objectifs et les 39 automatismes de l'annexe 2 sont rattachés une fois chacun (tableau « Contrôle de couverture »).
- **Contenus** : 187 exercices N11 réutilisés sur 269, 31 exercices de 5e et de 3e à adapter, 31 fiches de résumé sur 54 à partir d'une méthode N11, 121 cartes existantes rattachées (inventaire de l'étape 3, § 5).
- **Non vérifié** : la justesse mathématique des exercices réutilisés n'a pas été contrôlée exercice par exercice ; les exercices marqués « à vérifier » dans l'inventaire le seront à l'écriture des lots.

## Questions à trancher

Tranchées du 13 au 15 novembre 2026 (étapes 1 et 2, `DECISIONS_CYCLE4.md`) : budget, parties en semaines entières, évaluations à 10 min par objectif, dernière séquence non évaluée, cartes créées au niveau où la notion est un objectif, tableur et GeoGebra intégrés aux séquences, thèmes = domaines du programme, codes A1, arithmétique dans A2.

Restent les vingt points de l'inventaire de l'étape 3 (§ 6), avec leur réponse par défaut ; les cinq qui touchent ce document :

1. **Activité de découverte** : une par partie (objectif « Cours »). *Par défaut : oui* (16).
2. **Cible d'exercices** : 3 EN, 3 AP, 2 EX par objectif de 2 séances ou plus ; 2, 2, 1 pour un objectif d'une séance. *Par défaut : oui.*
3. **Cartes des automatismes de 5e** écrites dans les lots de 4e avant le référentiel de 5e. *Par défaut : oui.*
4. **Tests courts** : un par partie, sur les cartes de la partie. *Par défaut : oui* (16).
5. **Évaluation de B3** écrite même si le plan indicatif ne l'évalue pas. *Par défaut : oui.*

## Structure proposée

Douze séquences, {npar} parties, {nobj} objectifs. Chaque partie garde un objectif « Cours » ((p − 1) × 10 + 1 : 01, 11), non répété ici, intitulé « Connaître le cours » : fiche de cours et activité de découverte, 1 séance. Les objectifs de la partie p sont numérotés à partir de (p − 1) × 10 + 2. Le critère E vaut « Utilise ce savoir-faire pour résoudre un problème ». Sous chaque objectif : « Notions à expliquer » (un code N10, N11 ou N12 désigne une notion déjà écrite, à reprendre ou à adapter ; « rappel 5e » une notion de 5e rappelée dans la fiche) ; « Exercices » par série affichée EN, AP, EX (codes internes F, A, E ; « (F) » = mention facultatif ; « à adapter » = exercice d'un autre niveau à réécrire ; « n à créer ») ; « Cartes d'automatisme » (code d'une carte existante, recopiée dans la séquence de l'objectif ; « 4e » = carte à créer, notion de 4e ; « à créer en 5e » = automatisme de l'annexe 2, notion de 5e). Les codes d'atomes sont ceux de la base après migration.

### Ordre de progression

Référentiel et progression sont disjoints (décision du 13 novembre 2026) : ce document n'impose aucun ordre. Le plan indicatif des évaluations (étape 2) suppose l'ordre A1-P1, A2-P1, A2-P2, B1-P1, A3-P1, A4-P1, B2-P1, A4-P2, D2-P1, B2-P2, D2-P2, C1-P1, E1-P1, C2-P1, D1-P1, B3-P1, qui respecte les dépendances ci-dessous.

### Contraintes de progression

Dépendances entre séquences (étape 2), sous la forme « objectif → objectif dont il dépend : raison » :

- A2-03 → A1-03 : signe d'un quotient pour −a/b = −(a/b).
- A2-04 → A1-02 : signe d'un produit de fractions.
- A2-12 → A1-04 : priorités et enchaînements.
- A3-02 → A1-02 : puissances d'un nombre négatif.
- A4-03 → A1-02 : développer avec des coefficients négatifs.
- A4-12 → A1-04 : résoudre ax + b = c avec des relatifs.
- D2-03 → A2-02 : simplifier un rapport.
- D2-04 → A4-12 : a/b = c/d ⇔ ad = bc.
- A2-13 ↔ D2-05 : partage d'une quantité, à relier (pas de dépendance stricte).
- C2-03 → A2 : calculs de fractions.
- C2-05 → C1-02 et E1-03 : fréquences ; simulation avec une variable qui compte.
- D1-02 → A1-04 : vocabulaire d'un programme de calcul.
- D1-03 → A4-12 : remonter un programme par une équation.
- D1-04 → A4-02 : produire une formule.
- B2-02 → B1-02 : parallélogramme ; demi-tour (carte A22).
- B2-12 → A3-05 : racine carrée.
- B3-03 → B2-12, D2-04 et A2-02 : patron de la pyramide (Pythagore), patron du cône (proportionnalité, simplification par π).
- A4-14 → E1-03 : si la résolution approchée passe par un programme.

Dépendances internes aux séquences (étape 2) :

- A1-02 → Distributivité numérique (5e) : la règle des signes s'appuie dessus dès A1, comme le propose le document « Exemples » (décision du 14 novembre 2026).
- A1-04 → A1-02, A1-03.
- A2-03 → A1-03 (signe d'un quotient).
- A2-04 → A1-02 (signe d'un produit).
- A2-05 → A2-04.
- A2-12 → A2-04, A2-05, A1-04.
- A2-13 → A2-12 ; lien avec D2-05 (partage proportionnel).
- A3-02 → A1-02 (signe d'une puissance d'un négatif).
- A3-03 → A3-02.
- A3-04 → A3-02.
- A3-06 → A3-05.
- A4-03 → A1-02 (signes).
- A4-04 → A4-03.
- A4-12 → A1-04.
- A4-13 → A4-12.
- A4-14 → A4-12 ; E1 (variable, boucle) si on passe par un programme.
- C1-04 → C1-02, C1-03.
- C1-05 → C1-02, C1-03.
- C1-06 → C1-02, C1-03.
- C2-03 → A2 (calculs de fractions).
- C2-04 → C2-03.
- C2-05 → C1 (fréquences), E1-03 (simulation).
- D2-03 → A2-02 (simplifier un rapport).
- D2-04 → A4-12 (équation).
- D2-05 → D2-03.
- D2-13 → D2-12.
- D1-02 → A1-04.
- D1-03 → A4-12.
- D1-04 → A4-02.
- D1-05 → D1-04.
- B1-04 → B1-02.
- B2-02 → B1-03 (parallélogramme) ; la démonstration utilise le demi-tour.
- B2-04 → B2-03.
- B2-12 → A3-05 (racine carrée).
- B2-13 → B2-12.
- B3-03 → B2-12 (pyramide), D2-04 et A2-02 (cône).
- E1-04 → E1-02, E1-03.
- E1-05 → E1-02.

Dépendances relevées à l'inventaire de l'étape 3 :

- A3-05 → B2-12 : l'exercice N11/A1/F08 (diagonale d'un carré d'aire 36) demande Pythagore pour sa seconde question ; sans B2-12, garder la première question seulement.
- D1-04 → A4-02 : N11/D2/A08 (aire en fonction de la position d'un point) demande une formule littérale.
- C2-05 → E1-03 : simulation par programme (ou par tableur, sans dépendance).
- B3-04 → D2-02 : N11/D2/E10 (cornet de glace) et la masse volumique (N11/D2/E11) relient volume et grandeur quotient, en prolongement seulement.

## A1 — Calcul numérique

*Thème A — Nombres et calculs* · titre court de 4e : « Nombres relatifs : produits et quotients » · ancien code S03

### Partie 1 — Produits et quotients de relatifs

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » A1-01 (1 séance). Évaluation : séance d'évaluation n° 2 du plan indicatif.

**A1-02 · Multiplier deux nombres relatifs**

- F : « Calcule le produit de deux relatifs dont un seul est négatif. » · A : « Calcule un produit de plusieurs relatifs en déterminant d'abord son signe. »
- Notions à expliquer : « Opposé d'un nombre » (N10/A1/C04, rappel 5e) ; « Distributivité de la multiplication par rapport à l'addition » (N11/A4/C02) ; à écrire : « Produit de deux nombres relatifs : règle des signes » (nouvelle, démontrée par la distributivité).
- Exercices : EN : N11/A1/A05, 2 à créer ; AP : N11/A1/F01, N11/A1/A01, N11/A1/A02 (F) ; EX : N11/A1/A03, N11/A1/E02. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/A1/CA8, « Signe d'un produit de relatifs (procédure) » (4e), « Produit de deux relatifs (calcul paramétré) » (4e), « Tables de multiplication (A03) » (à créer en 5e), « Multiplier et diviser par 10, 100, 1 000 (A04 = A12) » (à créer en 5e), « Multiplication comme addition itérée (A06) » (à créer en 5e).

**A1-03 · Diviser deux nombres relatifs**

- F : « Calcule le quotient de deux entiers relatifs. » · A : « Détermine le signe d'un quotient en écriture fractionnaire et le relie au produit. »
- Notions à expliquer : — ; à écrire : « Quotient de deux nombres relatifs » (nouvelle) ; partie division de M1/FR1.
- Exercices : EN : N11/A1/F03, N11/A1/F02, 1 à créer ; AP : N11/A1/A04, 2 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Signe d'un quotient de relatifs » (4e), « Multiplications à trou (A05) » (à créer en 5e).

**A1-04 · Calculer un enchaînement d'opérations avec des relatifs**

- F : « Calcule une expression à deux opérations avec des relatifs en respectant les priorités. » · A : « Calcule une expression avec parenthèses et nomme sa nature (somme, différence, produit, quotient) ; traduit un programme de calcul en une expression. »
- Notions à expliquer : « Résultats des opérations arithmétiques : somme, différence, produit, quotient » (N10/A1/C03, rappel 5e) ; « Priorités opératoires » (rappel 5e, à écrire) ; à écrire : rien d'autre.
- Exercices : EN : 3 à créer ; AP : N11/A1/F09, 2 à créer ; EX : N11/A1/E01, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N10/A1/CA5, N10/A1/CA6, N10/A1/CA3, N10/A1/CA4, N10/A3/CA9, N10/A3/CA17, « Somme et différence de relatifs (A01) » (à créer en 5e).

## A2 — Nombres rationnels et arithmétique

*Thème A — Nombres et calculs* · titre court de 4e : « Nombres rationnels » · ancien code S15

### Partie 1 — Fractions, nombres rationnels et quotients

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » A2-01 (1 séance). Évaluation : séance d'évaluation n° 3 du plan indicatif.

**A2-02 · Simplifier une fraction**

- F : « Simplifie une fraction dont les deux termes sont dans une même table. » · A : « Simplifie une fraction en plusieurs étapes ou en une seule à l'aide d'un diviseur commun. »
- Notions à expliquer : « Multiple et diviseur d'un entier » (N10/A2/C01, rappel 5e) ; à écrire : rien (fractions égales : méthode M4 devenue M1).
- Exercices : EN : N11/A2/F01, N11/A2/F02, 1 à créer ; AP : N11/A2/A03, N11/A2/F03, 1 à créer ; EX : N11/A2/E01, N11/A2/E02, N11/A2/A02 (F). Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/A2/CA2, N11/A2/CA3, N11/A2/CA1, N10/A2/CA3, N10/A2/CA4.

**A2-03 · Écrire un nombre rationnel et son opposé**

- F : « Reconnaît qu'un quotient d'entiers relatifs est un nombre rationnel et écrit −a/b = a/(−b) = −(a/b). » · A : « Classe des nombres en entiers, décimaux, rationnels non décimaux. »
- Notions à expliquer : « Nombre rationnel » (N10/A3/C05, à adapter : quotient d'entiers relatifs) ; à écrire : « Opposé d'un nombre rationnel » (nouvelle).
- Exercices : EN : 3 à créer ; AP : 3 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N10/A3/CA8, « −a/b = a/(−b) = −(a/b) » (4e), « Entier, décimal ou rationnel non décimal ? » (4e), « Une fraction est un quotient (A09) » (à créer en 5e).

**A2-04 · Multiplier des fractions**

- F : « Calcule le produit de deux fractions et la fraction d'un nombre. » · A : « Calcule et représente la fraction d'une fraction, d'une quantité. »
- Notions à expliquer : — ; à écrire : « Produit de deux fractions » (nouvelle) ; « Fraction d'une quantité » (rappel 6e) ; partie produit de M3/FR3.
- Exercices : EN : N11/A1/F06, 2 à créer ; AP : N11/A1/A08, 2 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/A1/CA4, « Fraction d'une fraction (schéma) » (4e), « Fraction d'un nombre = produit (A10) » (à créer en 5e).

**A2-05 · Diviser des fractions**

- F : « Donne l'inverse d'un nombre et d'une fraction avec la notation 1/a. » · A : « Divise une fraction par une fraction en multipliant par l'inverse et simplifie le résultat. »
- Notions à expliquer : « Inverse d'un nombre non nul » (N11/A1/C01) ; « Inverse d'une fraction non nulle » (N11/A1/C02) ; à écrire : « Quotient de deux fractions » (nouvelle) ; partie quotient de M3/FR3.
- Exercices : EN : 3 à créer ; AP : N11/A1/A09, N11/A1/F07, 1 à créer ; EX : N11/A1/A10, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/A1/CA1, N11/A1/CA2, N11/A1/CA3, N11/A1/CA5.

### Partie 2 — Calculs et problèmes avec des fractions

1 semaine, 3 séances d'apprentissage, dont l'objectif « Cours » A2-11 (1 séance). Évaluation : séance d'évaluation n° 4 du plan indicatif.

**A2-12 · Calculer une expression avec des fractions**

- F : « Calcule une expression à deux opérations sur des fractions. » · A : « Calcule une expression avec parenthèses et priorités sur des fractions. »
- Notions à expliquer : « Priorités opératoires » (rappel 5e) ; « Addition et soustraction de fractions » (rappel 5e) ; à écrire : rien (M2/FR2 et M3/FR3 en rappel).
- Exercices : EN : N11/A1/F05, N11/A1/F04 (F), N11/A2/F04 (F) ; AP : N11/A1/A06, N11/A1/A07, N11/A2/A04 (F) ; EX : N11/A1/E05, N11/A2/E03. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/A1/CA6, N11/A1/CA7, N10/A1/CA8, N10/A1/CA9, « Priorités avec des fractions » (4e).

**A2-13 · Résoudre un problème avec des fractions**

- F : « Résout un problème à une étape avec une opération sur des fractions. » · A : « Résout un problème à plusieurs étapes (fraction d'un reste, partage), avec un schéma en barres si besoin. »
- Notions à expliquer : « Schéma en barres » (rappel 5e) ; à écrire : « Fraction d'un reste » (nouvelle, exemple de la fiche).
- Exercices : EN : 3 à créer ; AP : N11/A1/E06, 2 à créer ; EX : N11/A1/E03, N11/A1/E04. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Fraction d'un reste (schéma en barres) » (4e).

## A3 — Représentations d'un nombre

*Thème A — Nombres et calculs* · titre court de 4e : « Puissances et racine carrée » · ancien code S01

### Partie 1 — Puissances et racine carrée

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » A3-01 (1 séance). Évaluation : séance d'évaluation n° 5 du plan indicatif.

**A3-02 · Calculer une puissance d'exposant positif**

- F : « Écrit un produit de facteurs égaux sous forme de puissance et calcule a^n pour de petits n. » · A : « Calcule une puissance d'un relatif ou d'une fraction et utilise a⁰ = 1. »
- Notions à expliquer : « Puissances d'un nombre » (N11/A3/C01) ; « Notation carré et cube : $a^2$, $a^3$ » (N10/A4/C06, rappel 5e) ; à écrire : rien (M1/FR1 sans les puissances de 10 d'exposant négatif).
- Exercices : EN : N11/A3/F02, N11/A3/F04, 1 à créer ; AP : N11/A3/A01, N11/A3/F03, 1 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/A3/CA1, N11/A3/CA2, N11/A3/CA3, N11/A3/CA4, N10/A4/CA4, N11/A3/CA5, N11/A3/CA7, « Puissance d'un négatif : signe » (4e).

**A3-03 · Multiplier des puissances**

- F : « Calcule a^m × a^n sur des exemples et l'écrit a^(m+n). » · A : « Utilise a^m × a^n = a^(m+n) et (ab)^n = a^n b^n pour simplifier un calcul. »
- Notions à expliquer : — ; à écrire : « Produit de puissances d'un même nombre » et « Puissance d'un produit » (nouvelles) ; fiche à écrire.
- Exercices : EN : 3 à créer ; AP : 3 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « a^m × a^n = a^(m+n) » (4e), « (ab)^n = a^n × b^n » (4e).

**A3-04 · Résoudre un problème avec des puissances**

- F : « Résout un problème de comptage d'une situation répétée. » · A : « Résout un problème à plusieurs étapes (grains de riz, doublements). »
- Notions à expliquer : « Puissances d'un nombre » (N11/A3/C01) ; à écrire : rien.
- Exercices : EN : 3 à créer ; AP : N11/A3/E04, N11/X02/E03, 1 à créer ; EX : N11/A3/E02, N11/A3/E03. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : aucune.

**A3-05 · Déterminer la racine carrée d'un nombre positif**

- F : « Donne la racine carrée d'un carré parfait jusqu'à 144 et le côté d'un carré d'aire donnée. » · A : « Utilise la calculatrice pour une valeur exacte ou approchée et l'emploie dans une situation géométrique. »
- Notions à expliquer : « Racine carrée d'un nombre positif » (N11/A3/C05) ; « Liste des carrés parfaits de 1 à 144 » (N11/A3/C06) ; à écrire : rien.
- Exercices : EN : N11/A3/F11, N11/A3/F13, 1 à créer ; AP : N11/A1/F08, 2 à créer ; EX : N11/A3/E10, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/A3/CA10, N11/A3/CA11, N11/A3/CA12, « Carrés des entiers de 0 à 12 (A11 = A15) » (à créer en 5e).

**A3-06 · Encadrer la racine carrée d'un entier**

- F : « Encadre la racine carrée d'un entier inférieur à 144 par deux entiers consécutifs. » · A : « Encadre le côté d'un carré d'aire donnée et contrôle avec la calculatrice. »
- Notions à expliquer : « Liste des carrés parfaits de 1 à 144 » (N11/A3/C06) ; à écrire : rien.
- Exercices : EN : N11/A3/F14, 2 à créer ; AP : N11/A3/A10, 2 à créer ; EX : N11/A3/E12, N11/A1/E07. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/A3/CA13.

## A4 — Calcul littéral

*Thème A — Nombres et calculs* · titre court de 4e : « Calcul littéral et équations » · ancien code S05

### Partie 1 — Expressions littérales

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » A4-01 (1 séance). Évaluation : séance d'évaluation n° 6 du plan indicatif.

**A4-02 · Produire une formule et tester sa vraisemblance**

- F : « Écrit une formule d'aire ou de périmètre d'une figure simple et la teste sur une valeur. » · A : « Écrit un nombre pair 2n, impair 2n + 1, et une formule pour un motif ; réfute une formule par un contre-exemple. »
- Notions à expliquer : « Expression littérale » (N10/A4/C03, rappel 5e) ; à écrire : « Nombre pair, nombre impair : 2n, 2n + 1 » (nouvelle) ; « Contre-exemple » (rappel 5e) ; fiche à écrire.
- Exercices : EN : 3 à créer ; AP : N11/A4/A03, 2 à créer ; EX : N11/A4/E02, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N10/A4/CA5, N10/A4/CA3, « Pair 2n, impair 2n + 1 » (4e), « Double, triple, moitié, successeur… (A20) » (à créer en 5e).

**A4-03 · Développer, factoriser et réduire une expression**

- F : « Développe k(a + b) et réduit une expression du type 2x² − 3x + x². » · A : « Factorise une somme, développe −(4x − 2) et réduit une expression avec parenthèses. »
- Notions à expliquer : « Distributivité de la multiplication par rapport à l'addition » (N11/A4/C02) ; « Formes développée et factorisée d'une expression » (N11/A4/C03) ; « Forme réduite d'une expression littérale » (N10/A4/C04, rappel 5e) ; à écrire : « Opposé d'une expression : −(a + b) » (nouvelle) ; M1/FR1 en rappel.
- Exercices : EN : N11/A4/F03, N11/A4/F04, N11/A4/F01 (F) ; AP : N11/A4/F02, N11/A4/A04, 1 à créer ; EX : N11/A4/E03, N11/A4/E04. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/A4/CA2, N11/A4/CA3, N11/A4/CA4, N11/A4/CA5, N11/A4/CA8, N10/A4/CA6, N10/A4/CA8, « Opposé d'une expression −(a + b) » (4e).

**A4-04 · Démontrer avec le calcul littéral**

- F : « Démontre que deux programmes de calcul donnent le même résultat. » · A : « Démontre une propriété générale (somme de trois entiers consécutifs, multiple de 3). »
- Notions à expliquer : « Démonstration avec une expression littérale » (rappel 5e) ; à écrire : rien.
- Exercices : EN : N11/A4/F06, N11/A4/F07, 1 à créer ; AP : N11/A4/A06, N11/A4/A07, 1 à créer ; EX : N11/A4/E01, N11/A4/E05, N11/A4/E07. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Démontrer : choisir une lettre, développer, conclure » (4e).

### Partie 2 — Équations

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » A4-11 (1 séance). Évaluation : séance d'évaluation n° 8 du plan indicatif.

**A4-12 · Résoudre une équation du type ax + b = c**

- F : « Résout ax + b = c avec des entiers positifs et vérifie la solution. » · A : « Résout ax + b = c avec des relatifs et verbalise les étapes. »
- Notions à expliquer : « Équation » (N11/A4/C01) ; « Indéterminée, inconnue » (N10/A4/C01, rappel 5e) ; à écrire : M7/FR7 à étendre à ax + b = c.
- Exercices : EN : N11/A4/A09, N11/A4/F08 (F), 1 à créer ; AP : N11/A4/E08, 2 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/A4/CA1, N11/A4/CA6, N11/A4/CA7, « Résoudre ax + b = c (procédure) » (4e), « Résoudre ax + b = c (calcul paramétré) » (4e).

**A4-13 · Mettre un problème en équation et le résoudre**

- F : « Met en équation un problème qui conduit à ax + b = c et le résout. » · A : « Met en équation et résout un problème du type ax + b = cx + d, puis contrôle le résultat. »
- Notions à expliquer : « Équation » (N11/A4/C01) ; à écrire : rien.
- Exercices : EN : N11/A4/A01, 2 à créer ; AP : N11/A4/F05, N11/A4/A02, N11/A4/A08 ; EX : N11/A4/E06, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Mettre en équation : les quatre étapes » (4e).

**A4-14 · Résoudre une équation avec un tableur ou un algorithme**

- F : « Teste des valeurs au tableur pour approcher une solution. » · A : « Encadre une solution par balayage (tableur ou programme) et formule une conjecture. »
- Notions à expliquer : — ; à écrire : « Formule de tableur, recopie » (rappel 5e, synthèse § 8 point 13) ; fiche à écrire.
- Exercices : EN : 3 à créer ; AP : 3 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Balayage : encadrer une solution » (4e).

## B1 — Transformations géométriques

*Thème B — Espace et géométrie* · titre court de 4e : « Translations et parallélogrammes » · ancien code S11

### Partie 1 — Translation

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » B1-01 (1 séance). Évaluation : séance d'évaluation n° 4 du plan indicatif.

**B1-02 · Transformer une figure par une translation**

- F : « Construit l'image d'une figure par une translation sur quadrillage. » · A : « Construit l'image sur papier blanc ou avec un logiciel, et identifie une translation dans une frise ou un pavage. »
- Notions à expliquer : « Translation : direction, longueur et sens de translation » (N11/B1/C01) ; à écrire : rien.
- Exercices : EN : N11/B1/F01, N11/B1/F02, 1 à créer ; AP : N11/B1/F03, N11/B1/A03, N11/B1/A01 (F) ; EX : N11/B1/A02, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/B1/CA1, N11/B1/CA5, N10/B1/CA4, N10/B1/CA7, N11/B1/CA8, « Dire si deux figures sont images par une symétrie (A30) » (à créer en 5e), « Images dans une configuration (A31) » (à créer en 5e).

**B1-03 · Relier translation et parallélogramme**

- F : « Reconnaît le parallélogramme formé par un point, son image et un autre point et son image. » · A : « Utilise la translation pour justifier un parallélisme ou une égalité d'angles. »
- Notions à expliquer : « Définitions équivalentes d'un parallélogramme » (N10/B2/C10, rappel 5e) ; « Angles correspondants » (N10/B2/C04, rappel 5e) ; à écrire : « Translation et parallélogramme » (nouvelle) ; M6/FR6 sans les rotations.
- Exercices : EN : N11/B1/F08, 2 à créer ; AP : 3 à créer ; EX : N11/B1/E07, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/B1/CA6, N10/B2/CA10, N10/B2/CA11, N10/B2/CA12, N10/B2/CA13, « ABB'A' est un parallélogramme » (4e).

**B1-04 · Utiliser les propriétés de conservation de la translation**

- F : « Utilise la conservation des longueurs et des angles pour compléter une figure. » · A : « Justifie une longueur ou un angle par la conservation. »
- Notions à expliquer : « Propriétés de conservation des rotations et des translations » (N11/B1/C03, translation seule) ; à écrire : fiche à écrire.
- Exercices : EN : 3 à créer ; AP : N11/B1/A06, 2 à créer ; EX : N11/B1/E01, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/B1/CA3.

## B2 — Géométrie plane

*Thème B — Espace et géométrie* · titre court de 4e : « Triangles » · ancien code S12

### Partie 1 — Droite des milieux et triangle rectangle

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » B2-01 (1 séance). Évaluation : séance d'évaluation n° 7 du plan indicatif.

**B2-02 · Utiliser les théorèmes de la droite des milieux**

- F : « Utilise le théorème des milieux pour justifier un parallélisme. » · A : « Utilise les trois théorèmes pour calculer une longueur ou montrer qu'un point est un milieu. »
- Notions à expliquer : « Centre de symétrie d'un parallélogramme et diagonales » (N10/B2/C11, rappel 5e) ; à écrire : « Théorèmes de la droite des milieux » (nouvelle) ; fiche à écrire.
- Exercices : EN : 3 à créer ; AP : 3 à créer ; EX : N11/B2/A09, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N10/B2/CA8, N10/B2/CA9, « Droite des milieux : parallélisme » (4e), « Droite des milieux : longueur moitié » (4e), « Parallèle par un milieu : autre milieu » (4e), « Médianes, bissectrices (A34) » (à créer en 5e).

**B2-03 · Caractériser un triangle rectangle par son cercle circonscrit**

- F : « Trouve le centre du cercle circonscrit à un triangle rectangle. » · A : « Démontre qu'un triangle inscrit dans un demi-cercle est rectangle. »
- Notions à expliquer : « Médiatrices d'un triangle » (N10/B2/C08, rappel 5e) ; à écrire : « Triangle rectangle et cercle circonscrit » (nouvelle) ; fiche à écrire.
- Exercices : EN : 3 à créer ; AP : 3 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Centre du cercle circonscrit = milieu de l'hypoténuse » (4e), « Triangle inscrit dans un demi-cercle » (4e).

**B2-04 · Construire un rectangle sans équerre**

- F : « Construit un rectangle au compas en suivant un programme. » · A : « Justifie sa construction par les diagonales ou le cercle circonscrit. »
- Notions à expliquer : — ; à écrire : rien (notion de B2-03).
- Exercices : EN : 3 à créer ; AP : 3 à créer ; EX : N11/B2/E03, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : aucune.

### Partie 2 — Théorème de Pythagore

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » B2-11 (1 séance). Évaluation : séance d'évaluation n° 10 du plan indicatif.

**B2-12 · Calculer une longueur avec le théorème de Pythagore**

- F : « Calcule l'hypoténuse d'un triangle rectangle. » · A : « Calcule un côté de l'angle droit, valeur exacte ou arrondie. »
- Notions à expliquer : « Théorème de Pythagore, réciproque et contraposée » (N11/B2/C01) ; à écrire : rien.
- Exercices : EN : N11/B2/F02, N11/B2/F01, N11/B2/F04, N11/B2/F03 (F) ; AP : N11/B2/A02, N11/B2/A03, N11/B2/A01, N11/A1/A11 (F) ; EX : N11/B2/E02, N11/B2/E01. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/B2/CA1, N11/B2/CA2, N11/B2/CA4, N11/B2/CA9, N11/B2/CA11, N11/B2/CA17, N11/B2/CA18.

**B2-13 · Démontrer qu'un triangle est rectangle ou non**

- F : « Utilise la réciproque pour prouver qu'un triangle est rectangle. » · A : « Rédige une preuve par la contraposée, en employant le mot, et distingue réciproque et contraposée. »
- Notions à expliquer : « Théorème de Pythagore, réciproque et contraposée » (N11/B2/C01) ; à écrire : « Réciproque, contraposée, raisonnement par l'absurde » (nouvelle).
- Exercices : EN : N11/B2/F05, N11/B2/F06, N11/B2/F07 (F) ; AP : N11/B2/A04, N11/B2/A05, N11/B2/F08 ; EX : N11/B2/E04, N11/B2/E05. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/B2/CA3, N11/B2/CA12, N11/B2/CA13, « Réciproque et contraposée : laquelle ? » (4e).

## B3 — Représentation en trois dimensions

*Thème B — Espace et géométrie* · titre court de 4e : « Représentation de l'espace » · ancien code S13

### Partie 1 — Pyramides et cônes

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » B3-01 (1 séance). Évaluation : aucune dans le plan indicatif (dernière séquence de l'année).

**B3-02 · Reconnaître une pyramide et un cône de révolution**

- F : « Reconnaît pyramides et cônes parmi des solides et nomme leurs éléments. » · A : « Décrit le cône comme obtenu par rotation d'un triangle rectangle. »
- Notions à expliquer : « Perspective cavalière » (N10/B3/C01, rappel 5e) ; à écrire : « Pyramide, cône de révolution » (nouvelle) ; fiche à écrire.
- Exercices : EN : N11/B3/F04, N11/B3/F03, 1 à créer ; AP : 3 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/B3/CA4, N10/B3/CA3, « Pyramide et cône : sommet, base, hauteur » (4e), « Base d'un prisme en perspective (A28) » (à créer en 5e).

**B3-03 · Relier perspective cavalière et patron d'un solide**

- F : « Associe un patron et une perspective de pyramide ou de cône. » · A : « Construit le patron d'une pyramide (avec Pythagore) ou d'un cône (angle proportionnel au périmètre). »
- Notions à expliquer : « Patron d'une pyramide, d'un cône de révolution » (N11/B3/C02) ; « Patron d'un pavé droit, d'un cylindre, d'un prisme droit » (N10/B3/C02, rappel 5e) ; à écrire : rien.
- Exercices : EN : N11/B3/F02, N11/B3/F05 (F), 1 à créer ; AP : N11/B3/A02, N11/B3/A04, 1 à créer ; EX : N11/B3/E02, N11/B3/E04 (F). Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/B3/CA2, N11/B3/CA5, « Patron du cône : angle du secteur » (4e).

**B3-04 · Calculer le volume d'une pyramide et d'un cône**

- F : « Calcule le volume d'une pyramide ou d'un cône avec V = aire de base × hauteur ÷ 3. » · A : « Retrouve une dimension à partir du volume et relie les formules du pavé et de la pyramide. »
- Notions à expliquer : « Volume d'une pyramide, d'un cône » (N11/B3/C04) ; « Volume d'un pavé droit, d'un prisme droit, d'un cylindre de révolution » (N10/B3/C04, rappel 5e) ; à écrire : rien.
- Exercices : EN : N11/B3/F06, N11/B3/F08, 1 à créer ; AP : N11/B3/F07, N11/B3/A05, N11/B3/A07, N11/B3/A08, N11/B3/A06 (F) ; EX : N11/B3/E06, N11/B3/E05, N11/D2/E10, N11/B3/E01 (F). Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/B3/CA7, N11/B3/CA8, N11/B3/CA9, N11/B3/CA10, N11/B3/CA11, N11/B3/CA12, N11/B3/CA13, N11/B3/CA14, N11/B3/CA16, N10/B2/CA14.

## C1 — Traitement, représentation et interprétation des données

*Thème C — Organisation et gestion de données et probabilités* · titre court de 4e : « Statistiques » · ancien code S06

### Partie 1 — Indicateurs d'une série

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » C1-01 (1 séance). Évaluation : séance d'évaluation n° 12 du plan indicatif.

**C1-02 · Calculer une moyenne pondérée**

- F : « Calcule une moyenne pondérée à partir d'un tableau d'effectifs. » · A : « Construit le tableau d'effectifs à partir de données brutes ou d'un diagramme en barres, puis calcule la moyenne. »
- Notions à expliquer : « Étendue et moyenne d'une série statistique » (N10/C1/C04, rappel 5e : moyenne) ; à écrire : « Moyenne pondérée » (nouvelle) ; fiche à écrire.
- Exercices : EN : N10/C1/F03 (à adapter), N10/C1/F04 (à adapter), 1 à créer ; AP : N11/C1/A01, N10/C1/A03 (à adapter), N10/C1/A04 (à adapter), N10/C1/A05 (à adapter) ; EX : N10/C1/E03 (à adapter), N10/C1/E04 (à adapter). Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N10/C1/CA4, N10/C1/CA6, « Moyenne pondérée (procédure) » (4e), « Effectif manquant (A36) » (à créer en 5e).

**C1-03 · Déterminer une médiane et une étendue**

- F : « Détermine la médiane et l'étendue d'une petite série donnée en liste. » · A : « Les interprète, l'étendue étant lue sur un tableau ou un diagramme (en barres, circulaire). »
- Notions à expliquer : « Médiane d'une série statistique » (N11/C1/C01) ; « Étendue et moyenne d'une série statistique » (N10/C1/C04, étendue : la notion de 5e est scindée) ; à écrire : rien.
- Exercices : EN : N11/C1/F01, N11/C1/A03, 1 à créer ; AP : N11/C1/A02, 2 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/C1/CA1, N11/C1/CA2, N10/C1/CA3, N10/C1/CA5, N10/C1/CA2.

**C1-04 · Prévoir l'effet d'une valeur extrême**

- F : « Recalcule moyenne et médiane après l'ajout d'une valeur. » · A : « Explique sans calcul pourquoi la moyenne change plus que la médiane. »
- Notions à expliquer : — ; à écrire : « Sensibilité de la moyenne aux valeurs extrêmes » (nouvelle) ; fiche à écrire.
- Exercices : EN : 3 à créer ; AP : 3 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Moyenne ou médiane : laquelle bouge ? » (4e).

**C1-05 · Résoudre un problème avec des indicateurs**

- F : « Compare deux séries à l'aide d'un indicateur donné. » · A : « Compare deux séries présentées différemment ; complète une série soumise à des contraintes. »
- Notions à expliquer : — ; à écrire : rien (notions de C1-02 et C1-03).
- Exercices : EN : N12/C1/F06 (à adapter), N12/C1/F07 (à adapter), 1 à créer ; AP : N11/C1/E02, N12/C1/A05 (à adapter), 1 à créer ; EX : N11/C1/E01, N11/C1/E04, N12/C1/E05 (à adapter). Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : aucune.

**C1-06 · Calculer des indicateurs avec un tableur**

- F : « Utilise les fonctions SOMME, MOYENNE, MAX, MIN du tableur. » · A : « Utilise MEDIANE et NB et interprète les résultats. »
- Notions à expliquer : — ; à écrire : « Formule de tableur, recopie » (rappel 5e) ; fiche à écrire.
- Exercices : EN : 3 à créer ; AP : 3 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Fonctions MOYENNE, MEDIANE, MAX, MIN » (4e).

## C2 — Probabilités

*Thème C — Organisation et gestion de données et probabilités* · titre court de 4e : « Probabilités » · ancien code S07

### Partie 1 — Évènements et expériences

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » C2-01 (1 séance). Évaluation : séance d'évaluation n° 14 du plan indicatif.

**C2-02 · Décrire des évènements avec les notations ensemblistes**

- F : « Écrit l'univers et un évènement sous forme d'ensemble d'issues. » · A : « Détermine complémentaire, réunion, intersection et évènement impossible, et les verbalise. »
- Notions à expliquer : « Issue, événement » (N10/C2/C02, rappel 5e) ; « Événement certain, événement impossible » (N11/C2/C01) ; à écrire : « Univers, réunion, intersection, complémentaire, ensemble vide » (nouvelle) ; M1/FR1 à réécrire.
- Exercices : EN : N11/C2/F01, 2 à créer ; AP : N11/C2/A01, 2 à créer ; EX : N11/C2/E01, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/C2/CA1, « Univers, évènement : notation {…} » (4e), « Réunion, intersection, complémentaire » (4e).

**C2-03 · Calculer la probabilité d'un évènement et de son contraire**

- F : « Calcule une probabilité comme somme des probabilités des issues. » · A : « Calcule la probabilité de l'évènement contraire, d'une réunion ou d'une intersection simple. »
- Notions à expliquer : « Événements contraires » (N11/C2/C02) ; « Somme des probabilités d'une expérience aléatoire » (N11/C2/C03) ; à écrire : M3/FR3 et M4/FR4 en rappel.
- Exercices : EN : N11/C2/F03, N11/C2/A02, 1 à créer ; AP : N11/C2/A03, N11/C2/A04, 1 à créer ; EX : N11/C2/E02, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/C2/CA2, N11/C2/CA3, N11/C2/CA5, N11/C2/CA6, N11/C2/CA4.

**C2-04 · Calculer des probabilités dans une expérience à deux épreuves**

- F : « Liste les issues d'une expérience à deux épreuves dans un tableau. » · A : « Utilise un tableau ou un arbre, justifie l'équiprobabilité et calcule des probabilités. »
- Notions à expliquer : « Expérience aléatoire à deux épreuves » (N12/C2/C01) ; « Arbre des probabilités, nœud, branche, chemin » (N12/C2/C02, sans probabilités sur les branches) ; à écrire : fiche à écrire (N12/C2/M1 (N12/S07/M1), FR1 en appui).
- Exercices : EN : N11/C2/F02, N12/C2/F01 (à adapter), N12/C2/F02 (à adapter) ; AP : N11/C2/E04, N12/C2/A01 (à adapter), N12/C2/A02 (à adapter) ; EX : N11/C2/E03, N12/C2/E01 (à adapter), N12/C2/E02 (à adapter). Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Issues d'une expérience à deux épreuves : tableau » (4e), « Arbre des issues » (4e).

**C2-05 · Comparer fréquences observées et probabilité**

- F : « Observe la fluctuation des fréquences sur des séries de même taille. » · A : « Compare un diagramme de fréquences et un diagramme de probabilités, avec une simulation. »
- Notions à expliquer : « Effectif, fréquence d'une valeur » (N10/C1/C03, rappel 5e) ; à écrire : « Fluctuation d'échantillonnage » (nouvelle) ; fiche à écrire (N12/C2/M2 (N12/S07/M2), FR2 en appui).
- Exercices : EN : N11/C2/F04, N12/C2/F03 (à adapter), 1 à créer ; AP : N12/C2/A03 (à adapter), 2 à créer ; EX : N12/C2/E03 (à adapter), N12/C2/E04 (à adapter). Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Fréquence observée ≠ probabilité : fluctuation » (4e).

## D1 — Fonctions

*Thème D — Proportionnalité, fonctions* · titre court de 4e : « Fonctions et programmes de calcul » · ancien code S09

### Partie 1 — Programmes de calcul et dépendance

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » D1-01 (1 séance). Évaluation : séance d'évaluation n° 15 du plan indicatif.

**D1-02 · Appliquer un programme de calcul**

- F : « Applique un programme de calcul à deux étapes à un nombre. » · A : « L'applique à une variable x et écrit l'expression obtenue. »
- Notions à expliquer : « Variable » (N10/D1/C01, rappel 5e) ; à écrire : « Programme de calcul » (nouvelle) ; fiche à écrire.
- Exercices : EN : N11/D1/F02, 2 à créer ; AP : N11/A4/A05, 2 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/D1/CA1, N11/D1/CA2, N11/D1/CA3, N11/D1/CA4, N10/A3/CA10, N10/A3/CA18, « Programme de calcul → expression » (4e).

**D1-03 · Retrouver le nombre de départ d'un programme de calcul**

- F : « Remonte un programme simple en effectuant les opérations inverses. » · A : « Retrouve le nombre de départ par une équation. »
- Notions à expliquer : — ; à écrire : « Programme de calcul » (voir D1-02).
- Exercices : EN : 3 à créer ; AP : 3 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Remonter un programme : opérations inverses » (4e).

**D1-04 · Exprimer une grandeur en fonction d'une autre**

- F : « Écrit une formule simple (périmètre, prix) en fonction d'une variable. » · A : « Écrit une formule pour une situation géométrique (aire restante d'un rectangle découpé). »
- Notions à expliquer : « Variables dépendantes » (N10/D1/C02, rappel 5e) ; à écrire : rien.
- Exercices : EN : N11/D1/F01, 2 à créer ; AP : N11/D1/A01, N11/D2/A08, 1 à créer ; EX : N11/D1/E01, N11/D1/E02. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/D1/CA5, N11/D1/CA6.

**D1-05 · Représenter et interpréter la dépendance de deux grandeurs**

- F : « Construit le graphique à partir d'un tableau de valeurs. » · A : « Passe d'une représentation à l'autre (formule, tableau, graphique) et interprète. »
- Notions à expliquer : « Repère du plan; abscisse et ordonnée d'un point » (N11/D1/C01) ; à écrire : rien.
- Exercices : EN : N11/D1/F03, N11/D1/F04, 1 à créer ; AP : N11/D1/A02, N11/D1/A03, 1 à créer ; EX : N11/D1/E03, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Lire une image, un antécédent sur un graphique » (4e).

## D2 — Proportionnalité

*Thème D — Proportionnalité, fonctions* · titre court de 4e : « Proportionnalité, ratios et pourcentages » · ancien code S08

### Partie 1 — Rapports, ratios et grandeurs quotients

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » D2-01 (1 séance). Évaluation : séance d'évaluation n° 9 du plan indicatif.

**D2-02 · Calculer avec des grandeurs quotients**

- F : « Calcule une vitesse, un prix unitaire ou une consommation avec son unité. » · A : « Convertit une grandeur quotient (km/h en m/s) et lui donne du sens. »
- Notions à expliquer : « Grandeurs composées : grandeur-produit, grandeur-quotient » (N11/D2/C03, grandeurs quotients seulement) ; à écrire : rien.
- Exercices : EN : N11/D2/F10, N11/D2/A05, N11/D2/F12 (F) ; AP : N11/D2/A09, N11/D2/A10, 1 à créer ; EX : N11/D2/E11, N11/D2/E07, N11/D2/E05. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/D2/CA7, N11/D2/CA8, N11/D2/CA9, N11/D2/CA10.

**D2-03 · Comparer deux grandeurs avec un rapport ou un ratio**

- F : « Compare deux quantités par leur rapport et écrit un ratio a : b. » · A : « Traduit « a, b, c sont proportionnels à 2, 3, 7 » par des rapports égaux ou le ratio 2 : 3 : 7. »
- Notions à expliquer : « Ratio » (N10/D2/C04, à étendre à trois nombres) ; à écrire : « Rapport de deux grandeurs » (nouvelle) ; fiche à écrire.
- Exercices : EN : N11/D2/F03, 2 à créer ; AP : 3 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N10/D2/CA5, « Rapport et ratio a : b : c » (4e).

**D2-04 · Déterminer une quatrième proportionnelle**

- F : « Calcule une quatrième proportionnelle par la procédure de son choix. » · A : « Utilise a/b = c/d ⇔ ad = bc à bon escient. »
- Notions à expliquer : « Égalité des produits en croix » (N11/D2/C01) ; « Passage à l'unité » (N10/D2/C02, rappel) ; « Linéarité de la proportionnalité » (N10/D2/C03, rappel) ; à écrire : rien.
- Exercices : EN : N11/D2/F02, N11/D2/F05, 1 à créer ; AP : N11/D2/A04, N11/D2/A02, N11/D2/A03 (F), N11/D2/F09 (F) ; EX : N11/D2/E09, N11/D2/E03, N11/D2/E04. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/D2/CA1, N11/D2/CA3, N11/D2/CA4, N11/D2/CA5, N11/D2/CA6.

**D2-05 · Partager une quantité proportionnellement**

- F : « Partage une quantité en deux parts selon un ratio, avec un schéma en barres. » · A : « Partage en trois parts ou retrouve les parts connaissant l'une d'elles. »
- Notions à expliquer : « Ratio » (N10/D2/C04) ; à écrire : « Partage proportionnel » (nouvelle) ; fiche à écrire (N10/D2/M3 (N10/S08/M3) en appui).
- Exercices : EN : N10/D2/F07 (à adapter), 2 à créer ; AP : N10/D2/A06 (à adapter), 2 à créer ; EX : N10/D2/E06 (à adapter), 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Partager selon un ratio » (4e).

### Partie 2 — Pourcentages

1 semaine, 3 séances d'apprentissage, dont l'objectif « Cours » D2-11 (1 séance). Évaluation : séance d'évaluation n° 11 du plan indicatif.

**D2-12 · Calculer avec des pourcentages**

- F : « Applique un pourcentage et calcule un pourcentage dans un groupe. » · A : « Calcule le pourcentage d'un caractère dans la réunion de deux groupes. »
- Notions à expliquer : « Pourcentage » (N10/A3/C02, rappel 5e) ; à écrire : fiche à écrire (N10/D2/M5 (N10/S08/M5) en appui).
- Exercices : EN : N11/D2/A06, N11/D2/F04, N10/D2/F10 (à adapter) ; AP : N11/D2/F06, N11/D2/A07, N10/D2/A08 (à adapter) ; EX : N10/D2/E08 (à adapter), N10/D2/E09 (à adapter). Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N10/A3/CA4, N10/D2/CA7, « Compléter 20 % de 120 = … (A39) » (à créer en 5e).

**D2-13 · Utiliser un coefficient multiplicateur**

- F : « Multiplie par 1,15 pour augmenter de 15 % et par 0,8 pour diminuer de 20 %. » · A : « Retrouve le pourcentage d'évolution à partir du coefficient et enchaîne deux évolutions. »
- Notions à expliquer : « C\oe fficient multiplicateur » (N12/D2/C01) ; « Taux d'évolution » (N12/D2/C02, en partie) ; à écrire : rien.
- Exercices : EN : N11/D2/F07, N12/D2/F03 (à adapter), 1 à créer ; AP : N11/D2/E06, N12/D2/A03 (à adapter), 1 à créer ; EX : N11/D2/E02, N12/D2/E02 (à adapter). Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : « Coefficient multiplicateur » (4e), « Augmenter, diminuer de t % » (4e).

## E1 — Algorithmique et programmation

*Thème E — La pensée informatique* · titre court de 4e : « Algorithmique et programmation » · ancien code S14

### Partie 1 — Conditions, variables et programmes

2 semaines, 6 séances d'apprentissage, dont l'objectif « Cours » E1-01 (1 séance). Évaluation : séance d'évaluation n° 13 du plan indicatif.

**E1-02 · Écrire une instruction conditionnelle**

- F : « Écrit une condition simple avec <, > ou = et l'utilise dans un « si … alors ». » · A : « Utilise « si … alors … sinon » pour afficher un message selon la valeur saisie. »
- Notions à expliquer : « Instructions conditionnelles » (N10/E1/C11, à adapter) ; à écrire : fiche à écrire.
- Exercices : EN : 3 à créer ; AP : 3 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/E1/CA4, « Condition : vraie ou fausse ? » (4e).

**E1-03 · Utiliser une variable dans un programme**

- F : « Crée une variable, lui donne une valeur et l'affiche. » · A : « Utilise une variable pour accumuler dans une boucle (compter les 6 sur 1 000 lancers). »
- Notions à expliquer : « Variables » (N11/E1/C02) ; à écrire : rien.
- Exercices : EN : N11/E1/F02, N11/E1/F03, 1 à créer ; AP : N11/E1/A03, 2 à créer ; EX : N11/E1/E02, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/E1/CA1, N11/E1/CA3, N11/E1/CA5, N11/E1/CA6.

**E1-04 · Écrire un programme pour résoudre un problème**

- F : « Écrit un programme court à partir d'un algorithme donné. » · A : « Écrit en autonomie un programme qui répond à un objectif (tracé, calcul, jeu). »
- Notions à expliquer : « Événements » (N11/E1/C01) ; « Mise au point d'un programme : tests et corrections » (N10/E1/C13, rappel 5e) ; à écrire : rien.
- Exercices : EN : N11/E1/F01, 2 à créer ; AP : N11/E1/A01, N11/E1/A02, 1 à créer ; EX : N11/E1/E01, 1 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : N11/E1/CA2.

**E1-05 · Modifier un programme pour changer son comportement**

- F : « Ajoute une instruction simple à un programme donné. » · A : « Ajoute une condition ou une boucle pour modifier un programme (tracé de polygones). »
- Notions à expliquer : — ; à écrire : fiche à écrire.
- Exercices : EN : 3 à créer ; AP : 3 à créer ; EX : 2 à créer. Remédiation : 1 à écrire (premier EN).
- Cartes d'automatisme : aucune.

## Cartes d'automatisme (progression principale)

Décision du 14 novembre 2026 (7 h 57) : une carte se crée au niveau où la notion est un objectif, puis elle est reprise au niveau suivant. Au modèle « Fiches » de 4e, les cartes sont dans la progression principale : chaque carte est rattachée à un objectif (lien objectif ↔ carte), elle entre dans la boîte de Leitner quand la partie est faite, et le test court de la partie la contrôle. Il n'y a pas de référentiel de mises en route.

| Séquence | Cartes existantes rattachées (4e / reprises de 5e) | Cartes à créer (4e / automatismes de 5e) |
| --- | --- | --- |
| A1 | 0 / 7 | 3 / 5 |
| A2 | 7 / 8 | 5 / 2 |
| A3 | 5 / 6 | 3 / 1 |
| A4 | 4 / 8 | 7 / 1 |
| C1 | 4 / 3 | 3 / 1 |
| C2 | 4 / 2 | 5 / 0 |
| D2 | 8 / 4 | 4 / 1 |
| D1 | 2 / 6 | 3 / 0 |
| B1 | 4 / 7 | 1 / 2 |
| B2 | 10 / 2 | 6 / 1 |
| B3 | 3 / 11 | 2 / 1 |
| E1 | 6 / 0 | 1 / 0 |
| **Total** | **57 / 64** | **43 / 15** |

Total : 179 cartes (100 de 4e, 79 reprises de 5e), soit 3,3 par objectif. Les cartes de 4e sont celles que la 3e reprendra (synthèse du cycle, § 2). Une carte existante d'une autre séquence ou d'un autre niveau est recopiée dans la séquence de l'objectif.

## Contrôle de couverture du programme

Chaque objectif (O) et chaque automatisme (A) du programme de 4e est rattaché une seule fois : l'objectif à un objectif du référentiel, l'automatisme à l'objectif qui porte sa carte (contrôle de l'étape 2, script `col4/scripts/gen_etape2.py`, codes convertis en A1).

| Code | Objectif ou automatisme du programme (abrégé) | Objectif de référentiel |
| --- | --- | --- |
| O01 | Multiplier deux nombres relatifs : d’abord dans le cas où un seul des facteurs… | A1-02 |
| O02 | Diviser deux nombres relatifs | A1-03 |
| O03 | Savoir calculer un enchainement d’opérations avec des nombres relatifs | A1-04 |
| O04 | Utiliser le vocabulaire (somme, quotient, etc.) à partir d’un enchainement… | A1-04 |
| O05 | Simplifier une fraction | A2-02 |
| O06 | Définir la notion de nombre rationnel : le quotient de deux nombres entiers… | A2-03 |
| O07 | Exprimer l’opposé d’un nombre rationnel | A2-03 |
| O08 | Calculer le produit de nombres rationnels | A2-04 |
| O09 | Calculer et représenter la fraction d’une fraction, d’un nombre, d’une quantité | A2-04 |
| O10 | Définir l’inverse d’un nombre et connaitre sa notation | A2-05 |
| O11 | Déterminer l’inverse d’une fraction | A2-05 |
| O12 | Diviser des fractions | A2-05 |
| O13 | Calculer la valeur d’expressions comportant plusieurs opérations avec des… | A2-12 |
| O14 | Résoudre des problèmes mobilisant les opérations sur les fractions : addition,… | A2-13 |
| O15 | Définir les puissances d’exposant positif d’un nombre a | A3-02 |
| O16 | Multiplier des puissances d’exposant entier naturel d’un même nombre entre elles | A3-03 |
| O17 | Multiplier des puissances d’un même exposant entier naturel de deux nombres… | A3-03 |
| O18 | Résoudre des problèmes faisant intervenir des puissances | A3-04 |
| O19 | Comprendre et connaitre la définition de la racine carrée d’un nombre positif | A3-05 |
| O20 | Encadrer la racine carrée d’un entier par deux nombres entiers consécutifs | A3-06 |
| O21 | Produire des formules et tester leur vraisemblance : aires de formes… | A4-02 |
| O22 | Connaitre et utiliser la distributivité simple pour développer et factoriser… | A4-03 |
| O23 | Utiliser le calcul algébrique pour produire des démonstrations | A4-04 |
| O24 | Résoudre une équation du premier degré du type a𝑥 + b = c | A4-12 |
| O25 | Mettre en équation un problème et le résoudre à l’aide d’une équation du… | A4-13 |
| O26 | Formuler des conjectures à l’aide d’un algorithme ou d’un tableur pour résoudre… | A4-14 |
| O27 | Reconnaitre des solides (pyramide, cône de révolution) | B3-02 |
| O28 | Construire et mettre en relation différentes représentations des solides (pavé… | B3-03 |
| O29 | Connaitre le volume de la pyramide et du cône de révolution | B3-04 |
| O30 | Comprendre l’effet d’une translation | B1-02 |
| O31 | Faire le lien avec les parallélogrammes, les angles | B1-03 |
| O32 | Connaitre et utiliser les propriétés de conservations des translations | B1-04 |
| O33 | Connaitre les trois théorèmes relatifs à la droite des milieux dans un triangle | B2-02 |
| O34 | Connaitre le théorème de Pythagore, sa réciproque, sa contraposée | B2-12 |
| O35 | Mener un travail de logique sur la réciproque et la contraposée | B2-13 |
| O36 | Caractériser un triangle rectangle à l’aide de son cercle circonscrit, par son… | B2-03 |
| O37 | Déterminer le centre du cercle circonscrit d’un triangle rectangle | B2-03 |
| O38 | Construire des rectangles sans équerre | B2-04 |
| O39 | Calculer une moyenne pondérée dans le cas d’une série discrète de petits… | C1-02 |
| O40 | Déterminer une médiane et l’interpréter dans le cas d’une série de petit… | C1-03 |
| O41 | Calculer et interpréter l’étendue d’une série présentée sous forme de données… | C1-03 |
| O42 | Comprendre l’évolution de la médiane et de la moyenne quand on ajoute une… | C1-04 |
| O43 | Résoudre des problèmes faisant intervenir les différents indicateurs | C1-05 |
| O44 | Résoudre des problèmes de comparaison de séries statistiques | C1-05 |
| O45 | Utiliser le tableur pour calculer une moyenne, une médiane et l’étendue d’une… | C1-06 |
| O46 | Utiliser le vocabulaire et les notations ensemblistes pour décrire une… | C2-02 |
| O47 | Définir : complémentaire, réunion, intersection, ensemble vide (évènement… | C2-02 |
| O48 | Calculer la probabilité d’un évènement et de l’évènement contraire | C2-03 |
| O49 | Exemples simples d’expériences aléatoires à deux épreuves (par exemple, lancer… | C2-04 |
| O50 | À partir de la répétition d’une expérience aléatoire, réalisée matériellement… | C2-05 |
| O51 | Observer la fluctuation des fréquences pour un nombre de répétitions fixé de… | C2-05 |
| O52 | Utiliser des grandeurs quotients, avec ou sans unités | D2-02 |
| O53 | Comparer deux nombres ou deux grandeurs à l’aide de leur rapport ou ratio | D2-03 |
| O54 | Exprimer la proportionnalité entre deux suites de nombres par des égalités de… | D2-03 |
| O55 | Déterminer une quatrième proportionnelle | D2-04 |
| O56 | Calculer avec des pourcentages | D2-12 |
| O57 | Rendre compte d’une augmentation ou une diminution exprimée en pourcentages au… | D2-13 |
| O58 | Définir le coefficient multiplicateur | D2-13 |
| O59 | Résoudre des problèmes de partage proportionnel | D2-05 |
| O60 | Savoir appliquer un programme de calcul à deux (plusieurs) étapes à un nombre… | D1-02 |
| O61 | Savoir retrouver le nombre de départ après avoir remonté un programme de calcul… | D1-03 |
| O62 | Produire une formule littérale représentant la dépendance d’une grandeur en… | D1-04 |
| O63 | Représenter l’expression d’une grandeur en fonction d’une autre par un graphique | D1-05 |
| O64 | Comprendre la dépendance d’une grandeur en fonction d’une autre | D1-05 |
| O65 | Représenter des conditions simples | E1-02 |
| O66 | Écrire des instructions conditionnelles | E1-02 |
| O67 | Manipuler une variable | E1-03 |
| O68 | Écrire un programme simple donné pour réaliser un objectif ou résoudre un… | E1-04 |
| O69 | Modifier un programme donné pour changer son comportement | E1-05 |
| A01 | Manipulation de sommes et différences de nombre relatifs | A1-04 |
| A02 | Opposé d’un nombre, somme des opposés | A1-04 |
| A03 | Entretien des tables de multiplication | A1-02 |
| A04 | Multiplier et diviser par 10, 100, 1 000 | A1-02 |
| A05 | Compléter des multiplications à trou : 5 × ... = 3 ; faire le lien entre… | A1-03 |
| A06 | Multiplication comme addition itérée : 3 + 3 + 3 + 3 = 4 × 3 | A1-02 |
| A07 | Addition et soustraction de fractions de dénominateurs quelconques mais simples | A2-12 |
| A08 | Comparaison de fractions | A2-02 |
| A09 | Savoir qu’une fraction est aussi le quotient 3/7 : (le nombre, qui, multiplié… | A2-03 |
| A10 | Savoir que prendre la fraction d’un nombre revient à multiplier la fraction par… | A2-04 |
| A11 | Connaitre et reconnaitre les carrés parfaits des entiers de 0 à 12 | A3-05 |
| A12 | Multiplier et diviser par 10, 100, 1 000 ; savoir compléter 1 200 = 1,2 × … | A3-05 |
| A13 | Puissances simples : 2² = 4 ; 2³ = 8 ; 3³ = 27 | A3-02 |
| A14 | 10² = 100 ; 10³ = 1 000 | A3-02 |
| A15 | Donner les carrés des nombres entiers compris entre 0 et 12 | A3-05 |
| A16 | Donner la valeur d’expressions numériques simples | A4-02 |
| A17 | Résoudre des équations du type a𝑥 = c et 𝑥 + b = c, où a, b et c sont des… | A4-12 |
| A18 | Écrire 3 × 𝑥 sous la forme 3𝑥 et savoir que 3𝑥 c’est 3 × 𝑥 | A4-02 |
| A19 | Connaitre et utiliser : 1 × 𝑥 = 𝑥 ; 𝑥 + 𝑥 = 2𝑥 ; 𝑥 × 𝑥 = 𝑥² ; 3𝑥 + 2𝑥 = 5𝑥 ; 3𝑥… | A4-03 |
| A20 | Donner le double, le triple, la moitié, le prédécesseur, le successeur, le… | A4-02 |
| A21 | Tester si un nombre vérifie une égalité | A4-12 |
| A22 | Construire le symétrique d’un point par demi-tour | B1-02 |
| A23 | Placer sur une droite graduée un point dont l’abscisse est un nombre relatif | A1-04 |
| A24 | Repérer un nombre relatif sur une droite graduée | A1-04 |
| A25 | Dans le plan muni d’un repère orthogonal : • lire les coordonnées d’un point… | D1-02 |
| A26 | Reconnaitre les solides : cube, pavé, cylindre, prisme droit | B3-02 |
| A27 | Connaitre et utiliser les formules du volume d’un cube, d’un pavé, d’un prisme,… | B3-04 |
| A28 | Reconnaitre la base d’un prisme donné en perspective cavalière | B3-02 |
| A29 | Savoir calculer l’aire des figures planes usuelles : triangle, rectangle, disque | B3-04 |
| A30 | Dire si des figures planes sont images l’une de l’autre par une symétrie axiale… | B1-02 |
| A31 | Dans une configuration donnée, déterminer les images de figures, de droites, de… | B1-02 |
| A32 | Reconnaitre un parallélogramme à l’aide de sa définition ou d’une propriété… | B1-03 |
| A33 | Reconnaitre un parallélogramme particulier à partir de ses propriétés… | B1-03 |
| A34 | Reconnaitre des droites remarquables, y compris dans les triangles particuliers… | B2-02 |
| A35 | Calculer une moyenne pour un très petit nombre de valeurs | C1-02 |
| A36 | Calculer un effectif manquant dans un tableau pour un petit nombre de valeurs | C1-02 |
| A37 | Calculer une fréquence simple | C1-03 |
| A38 | Déterminer a % de c quand a vaut 100, 50, 25, 10, 1 | D2-12 |
| A39 | Compléter : 20 % de 120 = … ; 30 = × 1 000 | D2-12 |

## Récapitulatif : contenu prévu

- **Principal** : 12 séquences, 16 parties, 54 objectifs hors « Cours » (+ 16 « Connaître le cours »), 74 séances d'objectifs et 16 séances de cours, soit 90 séances d'apprentissage.
- **Fiches** : 54 fiches de résumé, une par objectif (31 à partir d'une méthode N11, 23 à écrire) ; 16 cartes mentales, une par partie.
- **Exercices** : 187 réutilisés de N11, 31 adaptés de N10 et N12, 228 à créer (cible 3 EN, 3 AP, 2 EX par objectif) ; 54 remédiations ; 16 activités de découverte.
- **Cartes d'automatisme** : 121 existantes rattachées, 58 à créer.
- **Documents** : 15 travaux personnels (dont 7 avec tableur, GeoGebra ou Scratch), 21 activités complémentaires, 16 tests courts sur 10 (sujets A et B).
- **Évaluations** : 16 évaluations de partie (15 dans le plan indicatif, plus B3), sujets A et B, 10 min par objectif évalué.

## Table de correspondance (codes d'objectifs de l'étape 2)

| Étape 2 | Ce document | Intitulé |
| --- | --- | --- |
| S03-02 | A1-02 | Multiplier deux nombres relatifs |
| S03-03 | A1-03 | Diviser deux nombres relatifs |
| S03-04 | A1-04 | Calculer un enchaînement d'opérations avec des relatifs |
| S15-02 | A2-02 | Simplifier une fraction |
| S15-03 | A2-03 | Écrire un nombre rationnel et son opposé |
| S15-04 | A2-04 | Multiplier des fractions |
| S15-05 | A2-05 | Diviser des fractions |
| S15-12 | A2-12 | Calculer une expression avec des fractions |
| S15-13 | A2-13 | Résoudre un problème avec des fractions |
| S01-02 | A3-02 | Calculer une puissance d'exposant positif |
| S01-03 | A3-03 | Multiplier des puissances |
| S01-04 | A3-04 | Résoudre un problème avec des puissances |
| S01-05 | A3-05 | Déterminer la racine carrée d'un nombre positif |
| S01-06 | A3-06 | Encadrer la racine carrée d'un entier |
| S05-02 | A4-02 | Produire une formule et tester sa vraisemblance |
| S05-03 | A4-03 | Développer, factoriser et réduire une expression |
| S05-04 | A4-04 | Démontrer avec le calcul littéral |
| S05-12 | A4-12 | Résoudre une équation du type ax + b = c |
| S05-13 | A4-13 | Mettre un problème en équation et le résoudre |
| S05-14 | A4-14 | Résoudre une équation avec un tableur ou un algorithme |
| S06-02 | C1-02 | Calculer une moyenne pondérée |
| S06-03 | C1-03 | Déterminer une médiane et une étendue |
| S06-04 | C1-04 | Prévoir l'effet d'une valeur extrême |
| S06-05 | C1-05 | Résoudre un problème avec des indicateurs |
| S06-06 | C1-06 | Calculer des indicateurs avec un tableur |
| S07-02 | C2-02 | Décrire des évènements avec les notations ensemblistes |
| S07-03 | C2-03 | Calculer la probabilité d'un évènement et de son contraire |
| S07-04 | C2-04 | Calculer des probabilités dans une expérience à deux épreuves |
| S07-05 | C2-05 | Comparer fréquences observées et probabilité |
| S08-02 | D2-02 | Calculer avec des grandeurs quotients |
| S08-03 | D2-03 | Comparer deux grandeurs avec un rapport ou un ratio |
| S08-04 | D2-04 | Déterminer une quatrième proportionnelle |
| S08-05 | D2-05 | Partager une quantité proportionnellement |
| S08-12 | D2-12 | Calculer avec des pourcentages |
| S08-13 | D2-13 | Utiliser un coefficient multiplicateur |
| S09-02 | D1-02 | Appliquer un programme de calcul |
| S09-03 | D1-03 | Retrouver le nombre de départ d'un programme de calcul |
| S09-04 | D1-04 | Exprimer une grandeur en fonction d'une autre |
| S09-05 | D1-05 | Représenter et interpréter la dépendance de deux grandeurs |
| S11-02 | B1-02 | Transformer une figure par une translation |
| S11-03 | B1-03 | Relier translation et parallélogramme |
| S11-04 | B1-04 | Utiliser les propriétés de conservation de la translation |
| S12-02 | B2-02 | Utiliser les théorèmes de la droite des milieux |
| S12-03 | B2-03 | Caractériser un triangle rectangle par son cercle circonscrit |
| S12-04 | B2-04 | Construire un rectangle sans équerre |
| S12-12 | B2-12 | Calculer une longueur avec le théorème de Pythagore |
| S12-13 | B2-13 | Démontrer qu'un triangle est rectangle ou non |
| S13-02 | B3-02 | Reconnaître une pyramide et un cône de révolution |
| S13-03 | B3-03 | Relier perspective cavalière et patron d'un solide |
| S13-04 | B3-04 | Calculer le volume d'une pyramide et d'un cône |
| S14-02 | E1-02 | Écrire une instruction conditionnelle |
| S14-03 | E1-03 | Utiliser une variable dans un programme |
| S14-04 | E1-04 | Écrire un programme pour résoudre un problème |
| S14-05 | E1-05 | Modifier un programme pour changer son comportement |
