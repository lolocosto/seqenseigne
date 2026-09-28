# seqenseigne — Cas d'usage utilisateur

**Version 0.10.7 — 2 mai 2026 · Laurent Coste**

Parcours utilisateur, scénario par scénario, du point de vue d'un
enseignant qui utilise seqenseigne. Sert de base aux futures FAQ et
visites guidées de l'application.

---

## Table des matières

1. [Démarrage](#1-démarrage)
2. [Rédaction d'une notion](#2-rédaction-dune-notion)
3. [Rédaction d'une méthode et d'une fiche de résumé](#3-rédaction-dune-méthode-et-dune-fiche-de-résumé)
4. [Rédaction d'un exercice](#4-rédaction-dun-exercice)
5. [Assemblage d'une séquence-niveau](#5-assemblage-dune-séquence-niveau)
6. [Réutilisation d'un exo en révision](#6-réutilisation-dun-exo-en-révision)
7. [Modification d'un atome déjà placé](#7-modification-dun-atome-déjà-placé)
8. [Génération de PDF](#8-génération-de-pdf)
9. [Import de contenus existants](#9-import-de-contenus-existants)
10. [Diagnostic des atomes orphelins](#10-diagnostic-des-atomes-orphelins)
11. [Suivi de classe](#11-suivi-de-classe)
12. [Pièges et résolutions courantes](#12-pièges-et-résolutions-courantes)

---

## 1. Démarrage

### Première utilisation

1. Lancer `lancer.bat` (Windows) ou `python3 -m flask run` (Linux).
2. Ouvrir un navigateur sur `http://localhost:5000`.
3. L'application affiche l'onglet « Conception » avec les ateliers
   atomiques. Si la BDD est vide, l'auto-import a déjà chargé les
   référentiels C03/C04 (cycles, thèmes, séquences).

### Sélection du contexte

En haut de la barre latérale des ateliers atomiques, deux sélecteurs
filtrent l'ensemble des atomes affichés :

- **Niveau** : N09, N10, N11 ou N12.
- **Séquence** : S01..S14 (les séquences disponibles dépendent du
  niveau via `sequences_par_niveau`).

Tous les atomes nouvellement créés héritent de ce contexte (champs
`niveau` et `sequence`). Avant de cliquer sur « Nouveau », vérifier
que le bon couple est sélectionné.

---

## 2. Rédaction d'une notion

### Scénario : créer la notion « Fonction linéaire » pour N11/S08

1. Sélectionner **N11 / S08** dans les filtres.
2. Cliquer sur l'onglet « Notion » de la sidebar.
3. Bouton **Nouveau**.
4. Saisir le titre : « Fonction linéaire ».
5. Saisir le corps :

   ```latex
   On dit qu'une fonction $f$ est linéaire s'il existe un nombre
   réel $a$ tel que pour tout $x$, $f(x) = ax$.
   ```

6. Optionnellement, ajouter des sections :
   - Section « Notation » : `$f(x) = ax$, où $a$ est le coefficient
     directeur.`
   - Section « Cas particulier » : `Si $a = 0$, $f$ est la fonction
     nulle.`

7. Bouton **Enregistrer** (ou `Ctrl+S`).

### Comportement v0.10.7

- La notion hérite automatiquement de `niveau=N11` et `sequence=S08`.
- Elle apparaît dans la sidebar avec l'identifiant `N11/S08`.
- À ce stade, **aucun badge d'objectif** n'apparaît : la notion
  n'est pas encore liée à un objectif. Pour la lier, il faut
  passer par l'atelier d'assemblage (voir [section 5](#5-assemblage-dune-séquence-niveau)).

### Garde de sortie (v0.10.6)

Si vous quittez l'atelier (clic sur un autre atome, changement
d'onglet) avant d'enregistrer, une modale apparaît :

> Modifications non enregistrées
> [Annuler] [Quitter sans enregistrer] [Enregistrer et quitter]

---

## 3. Rédaction d'une méthode et d'une fiche de résumé

### Scénario : rédiger « Calculer une image par une fonction linéaire »

#### Méthode

1. Sélectionner N11 / S08, onglet « Méthode ».
2. Bouton **Nouveau**, titre : « Calculer une image par une fonction
   linéaire ».
3. Corps : description générale + sections (étapes, exemples,
   contre-exemples).
4. **Critères F/A/E** :
   - F = « Calcule l'image d'un nombre entier par une fonction
     donnée par une formule simple. »
   - A = « Calcule l'image d'un nombre rationnel ou pour une formule
     comportant des fractions. »
   - E = « Détermine une formule à partir d'une situation décrite,
     puis calcule des images. »
5. Optionnellement, **notions associées** : sélectionner « Fonction
   linéaire » dans le sélecteur dédié.
6. Marqueur **Fin de cycle** : N (par défaut). Cocher seulement si la
   méthode est attendue jusqu'à la fin du cycle 4 (3ème).
7. Enregistrer.

#### Fiche de résumé

L'atelier Fiche de résumé s'utilise une fois la méthode liée à un
objectif (voir section 5).

1. Une fois la méthode posée dans une partie, ouvrir la zone d'édition
   de l'objectif depuis l'atelier d'assemblage.
2. Bouton **Créer la fiche de résumé** → ouvre l'atelier Fiche.
3. Remplir le titre, le rappel court, l'exemple-type.
4. Enregistrer.

**Cardinalité 1-1-1** : 1 fiche = 1 méthode = 1 objectif. Pas de
fiche pour les objectifs « Connaître le cours ».

---

## 4. Rédaction d'un exercice

### Scénario : créer un exercice de série A pour N11/S08

1. Sélectionner N11 / S08, onglet « Exercice ».
2. Bouton **Nouveau**.
3. Choisir la série : **F**, **A**, **E**, **EA** ou **R**.
   (Pour un exo destiné à l'évaluation principale, série **A**.)
4. Optionnellement, donner un nom : « Tarif piscine ».
5. Bloc **Variables** (LaTeX libre, optionnel) :

   ```latex
   \xintdefiivar{a}{randrange(2,9)}
   \xintdefiivar{b}{randrange(10,30)}
   ```

6. **Énoncé** :

   ```latex
   Le tarif d'entrée à la piscine est de \xintifboolexpr{a>5}{\a}
   {2\a} euros pour les adultes et \b euros pour les enfants.
   Calculer le prix d'une famille de 2 adultes et 3 enfants.
   ```

7. **Corrigé** (toujours obligatoire — un exercice n'est jamais
   sauvegardé sans corrigé) :

   ```latex
   Prix = $2 \times \a + 3 \times \b$ = …
   ```

8. Enregistrer.

### v0.10.7 : pas de zone « Objectifs associés »

L'exercice n'est pas encore lié à un objectif. Pour le lier, il
faut passer par l'atelier d'assemblage et le déposer dans une zone
F/A/E/R/EA d'un objectif de la séquence cible.

Une fois lié, le badge `02` (ou similaire) apparaît dans la sidebar
de l'atelier Exercice à droite de cet exo.

---

## 5. Assemblage d'une séquence-niveau

### Scénario : structurer N11/S08 en parties et y placer les atomes

1. Onglet « Assemblage » dans la barre principale.
2. Sélectionner N11 / S08 → l'atelier d'assemblage charge l'objet
   complet de la séquence-niveau.
3. **Découpage en parties** :
   - Bouton **+ Partie** pour créer une nouvelle partie.
   - Numéroter automatiquement (1, 2, 3, …).
   - Une partie ne peut être supprimée que si elle est vide.

### Création des objectifs

Dans chaque partie, l'objectif `01` (Connaître le cours) est créé
automatiquement quand la partie est créée. Pour ajouter un objectif
« exo » :

1. Bouton **+ Objectif** dans la partie.
2. Le code est attribué automatiquement (`02`, `03`, …).
3. Saisir le **nom** (verbe d'action court : « Calculer », « Tracer »…).

### Liaison méthode → objectif

1. Survoler la zone « Méthode » de l'objectif.
2. Cliquer sur **Choisir une méthode**.
3. Le sélecteur n'affiche que les méthodes de **N11/S08** (scope
   v0.10.7).
4. Choisir la méthode → elle est liée à l'objectif. Cardinalité 1-1
   méthode → objectif : si vous tentez de lier la même méthode à un
   second objectif, vous obtiendrez une erreur 409 :

   > La méthode … est déjà liée à l'objectif … Une méthode ne peut
   > être liée qu'à un seul objectif.

### Liaison notions → objectif

Plusieurs notions peuvent être liées au même objectif (cardinalité
N-N). Toujours dans le scope de la séquence courante.

1. Survoler la zone « Notions » de l'objectif (sauf pour `01`,
   `11`, `21`, … : la zone est absente).
2. Cliquer sur **+ Notion**.
3. Le sélecteur n'affiche que les notions de **N11/S08**.

### Drop d'exercices

Sur chaque objectif (sauf `01`, `11`, `21`…), des zones F, A, E
permettent de déposer des exercices :

1. Glisser-déposer depuis la sidebar « Exercices » vers la zone
   F, A ou E.
2. La règle de scope par série :
   - **F, A, E** : tout exercice de la séquence courante.
   - **R** : seulement les exos `A` provenant d'une séquence
     présente dans les **précédences** de la séquence courante.
   - **EA** : seulement les exos `EA` de la séquence courante.

### Auto-sauvegarde

Tout drop, retrait, changement de critère ou de nom dans l'atelier
d'assemblage est **immédiatement persisté**. Pas de bouton
« Enregistrer » nécessaire. Une perte de connexion ou un crash
navigateur ne perd que la dernière action en cours.

---

## 6. Réutilisation d'un exo en révision

### Scénario : utiliser un exo `A` de N10/S04 comme révision en N11/S03

#### Préalable

La séquence N11/S03 doit avoir N10/S04 dans ses **précédences**.
Pour la déclarer :

1. Atelier d'assemblage de N11/S03.
2. Zone « Précédences » de la sidebar latérale.
3. Bouton **+ Précédence**.
4. Choisir N10/S04 dans le sélecteur.

#### Drop de l'exo

1. Atelier d'assemblage de N11/S03.
2. Sur l'objectif cible, zone **R**.
3. Glisser un exercice depuis le catalogue (avec filtre
   « Exos disponibles en révision » qui montre les exos `A` des
   précédences déclarées).
4. L'exo apparaît dans la zone R, et dans la sidebar de l'atelier
   Exercice il porte maintenant un badge externe `N11·S03·02`
   (= utilisé par l'objectif 02 de N11/S03 en plus de son objectif
   d'origine en N10/S04).

#### Visualisation

Dans la sidebar de l'atelier Exercice :

- Pour un exo de la séquence courante : badges au format `02` (chip
  neutre).
- Pour un exo utilisé dans une autre séquence : badges au format
  `N11·S03·02` (chip plus pâle, italique).

---

## 7. Modification d'un atome déjà placé

### Scénario : corriger une faute de frappe dans une notion en cours

1. Sidebar de l'atelier « Notion », filtrer N11/S08.
2. Cliquer sur la notion à corriger → l'éditeur charge son contenu.
3. Modifier le titre, le corps ou les sections.
4. Le badge **modifié** apparaît dans la sidebar.
5. Enregistrer (ou `Ctrl+S`).

### Que se passe-t-il pour les liaisons ?

- La modification du **contenu** (titre, corps, sections) se propage
  automatiquement à tous les objectifs qui utilisent cette notion
  (puisque la liaison se fait par ID).
- Si vous **changez le scope** (par exemple, passer une notion de
  N11/S08 à N11/S09) **et** que la notion est déjà liée à des
  objectifs de N11/S08 : la modification ne sera **pas refusée**
  côté backend, mais les liaisons existantes deviennent
  incohérentes au regard de la règle de scope. À éviter — il vaut
  mieux créer une nouvelle notion dans la séquence cible.

---

## 8. Génération de PDF

### 8.1 Aperçu d'un atome

Dans tout atelier (Exercice, Notion, Méthode, Fiche), un onglet
**Rendu PDF** affiche le PDF compilé de l'atome dans une iframe.

- 1ère consultation : compile via `pdflatex` (3 passes), 5 à 15
  secondes selon la taille de l'atome.
- Consultations suivantes : cache disque, instantané.
- Si l'atome n'est pas validé : filigrane « ÉPREUVE » sur le rendu.

### 8.2 LaTeX généré

Pour examiner le LaTeX produit (debug ou copier-coller dans un
autre document) : bouton **LaTeX généré** dans la toolbar de
l'atelier → modale qui affiche le `.tex` complet (préambule + corps).

### 8.3 Compilation par lot

1. Onglet « Compilation par lot » (icône engrenage).
2. Filtres : niveau, séquence, type d'atome, état (valider,
   modifié, en cours).
3. Bouton **Lancer la compilation**.
4. Barre de progression. Erreurs affichées par atome avec lien
   « Ouvrir l'atelier » pour corriger.

### 8.4 (À venir v0.11) PDF de séquence complète

Génération d'un livret PDF complet de N11/S03, avec sélecteurs
optionnels :
- avec/sans cours
- avec/sans fiches de résumé
- avec/sans corrigés.

---

## 9. Import de contenus existants

### 9.1 Scanner d'import (`scanner_vers_v2`)

Si vous avez déjà des contenus en LaTeX au format livrets de
séquence, le scanner d'import les peuple dans la BDD :

1. Onglet **Admin** → section **Import**.
2. Sélectionner le dossier source (par défaut `data/SequencesDB/`).
3. Bouton **Scanner**.
4. Le scanner :
   - Parcourt les `.tex` des livrets de séquence.
   - Extrait les notions, méthodes, exercices.
   - Crée les liaisons `objectif_exos` depuis les exercices déclarés
     dans les livrets.
   - Renseigne les champs `niveau`, `sequence`, `fichier` pour
     traçabilité.

### 9.2 Import de fiches `.tex` (v0.10.5.2)

1. Onglet **Admin** → section **Fiches de résumé**.
2. Bouton **Importer un fichier `.tex`**.
3. Le parser détecte les `\begin{flashcard}{...}...\end{flashcard}`.
4. Pour chaque flashcard détectée, l'utilisateur valide la
   correspondance avec un objectif existant.

---

## 10. Diagnostic des atomes orphelins

### Scénario : avant une grosse refonte, faire le ménage

Le script CLI v0.10.7 liste les notions et méthodes potentiellement
orphelines :

```bash
python3 -m scripts.lister_atomes_orphelins
```

Sortie :

```
=== Notions orphelines (3) ===
STATUTS               NIVEAU  SEQUENCE  ID         TITRE                  FICHIER
SANS_SCOPE,SANS_LIEN                    no_xxx111  Vieille notion legacy
SANS_LIEN             N11     S03       no_yyy222  Notion isolée          n.tex
SANS_LIEN             N11     S04       no_zzz333  Notion en doublon      n.tex
…
=== Méthodes orphelines (1) ===
…
```

Deux types d'orphelins :

- **SANS_SCOPE** : pas de `(niveau, sequence)` posés. Cause typique :
  atome créé dans une vieille version, ou import avant l'ajout du
  scope. À corriger en éditant l'atome (poser le scope manuellement)
  ou en supprimant si non réutilisable.
- **SANS_LIEN** : aucune liaison vers un objectif. Cause typique :
  atome rédigé mais pas encore intégré dans une séquence. Pas
  forcément à supprimer (peut être un brouillon).

À terme (v0.14), un onglet d'administration intégrera ce diagnostic
et permettra d'opérer le nettoyage en UI.

---

## 11. Suivi de classe

(Hors périmètre v0.10.7, déjà implémenté en v0.6.3c. Synthèse
brève pour mémoire.)

### Création d'une classe

1. Onglet « Suivi » → sous-onglet « Classes ».
2. Bouton **+ Classe**, saisir nom, niveau, année.
3. Importer la liste d'élèves depuis CSV ou en saisie manuelle.

### Saisie d'évaluations

1. Onglet « Suivi » → sous-onglet « Évaluations ».
2. Choisir la classe et la session d'évaluation.
3. Pour chaque élève, saisir son niveau de maîtrise (I/F/A/E) sur
   chaque objectif évalué.

### Progression annuelle

Affichage d'un tableau récapitulatif des compétences acquises au
fil de l'année, avec calcul automatique des moyennes pondérées.

---

## 12. Pièges et résolutions courantes

### « La méthode ne s'affiche pas dans le sélecteur de l'objectif »

Cause possible : la méthode appartient à une autre séquence.

Solution : vérifier le `(niveau, sequence)` de la méthode dans
l'atelier Méthode. Si elle est de la mauvaise séquence, soit la
recréer dans la bonne séquence, soit poser le scope correct via
l'éditeur (champs niveau/sequence dans l'API mais pas encore
exposés en UI dans v0.10.7 — utiliser le script de modification
manuelle de la BDD ou attendre v0.14).

### « La méthode est déjà liée à l'objectif … »

Erreur HTTP 409. Cause : la cardinalité 1-1 méthode → objectif est
violée.

Solution :
1. Aller sur l'objectif qui détient déjà la méthode (mentionné dans
   le message d'erreur).
2. Détacher la méthode (zone Méthode → croix).
3. La rattacher à l'objectif souhaité.

### « L'exo R ne peut pas être placé : sa séquence d'origine ne figure pas dans les précédences »

Erreur 409. Cause : tentative de réutiliser un exo `A` d'une
séquence non déclarée comme précédence.

Solution :
1. Aller dans la zone « Précédences » de la sidebar de l'atelier
   d'assemblage.
2. Ajouter la séquence d'origine de l'exo en précédence.
3. Refaire le drop.

### « Le rendu PDF échoue avec une erreur LaTeX »

Diagnostic : ouvrir le bouton **LaTeX généré** pour examiner le
code produit, et regarder les logs `pdflatex` dans
`appli/data/cache_rendus/<hash>.log`.

Causes fréquentes :
- Caractère spécial non échappé dans l'énoncé (`%`, `&`, `_`).
- Variable `xint` mal définie.
- Référence à une commande non chargée dans le préambule.

### « Les longues lignes ne wrappent pas dans la zone d'édition »

Plus une cause de problème depuis v0.10.7 : toutes les zones de
saisie wrappent désormais automatiquement (CSS `pre-wrap` +
`overflow-wrap: anywhere`). Les retours à la ligne explicites sont
préservés ; les lignes très longues sont cassées visuellement sans
scroll horizontal.

### « Mes modifications dans l'atelier ne sont pas conservées »

Causes possibles :
- Vous avez quitté l'atelier sans enregistrer (depuis v0.10.6, une
  modale de garde s'affiche normalement — vérifier qu'elle n'a pas
  été masquée par votre navigateur).
- Pour l'atelier d'assemblage : auto-save activée, donc tout est
  conservé immédiatement. Si une action n'a pas été persistée,
  chercher une erreur dans la console JS.

### « Le filigrane ÉPREUVE apparaît sur mes PDF »

Cause : l'atome n'est pas en état « validé ».

Solution : ouvrir l'atelier de l'atome, vérifier le badge d'état en
sidebar (modifié, validé, en cours), et le passer à « validé » si
le contenu est définitif.
