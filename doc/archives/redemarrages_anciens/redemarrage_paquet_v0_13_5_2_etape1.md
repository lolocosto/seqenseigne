# Redémarrage — Paquet LaTeX v0.13.5.2 étape 1

> Livraison du 8 mai 2026.
> Refonte du paquet `seqenseigne` pour préparer l'évolution v0.13.5.2 :
> extraction des évaluations dans un module dédié, déménagement du
> modèle Bilan 2021 vers `legacy`, regroupement de l'environnement
> `qcm` avec les autres macros d'exercices.
>
> **Étape 1 sur 5** du plan de refonte arrêté en session de scoping.
> Régression zéro garantie : aucune macro renommée, aucune signature
> modifiée. Voir section « Bugs latents corrigés au passage ».

## Périmètre de cette livraison

### Nouveau module

- `seqenseigne-core-eval.dtx` (et `.sty` généré) — module d'évaluation,
  extrait depuis `core.dtx`. Hébergera les futures évolutions cadrées
  pour v0.13.5.2 (renommages, suppression `numSeq/titreSeq/niveauDiff`,
  ajout `seqEvalObjectifs`/`seqEvalCriteres`, etc.) qui interviendront
  aux étapes suivantes.

### Modules modifiés

- `seqenseigne-core.dtx` : allégé de ~490 lignes. Plus aucune macro
  d'évaluation, de bilan ou de QCM. Conserve `\newwrite\corrfileeval`
  comme primitif partagé entre `core-eval` et `legacy`. Des commentaires
  de pointage explicitent où trouver les macros déménagées.
- `seqenseigne-core-exos.dtx` : reçoit l'environnement `qcm` et les
  helpers QCM partagés (compteurs `i`, `AlphCode`, `QcmItemNumCnt`,
  commande `\repCodes`). C'est cohérent avec le fait qu'un QCM est un
  format particulier d'exercice, utilisable en livret comme en
  évaluation.
- `seqenseigne-legacy.dtx` : reçoit le bloc complet du modèle Bilan 2021
  (`\seqBilan`, `\seqBilanItemAlea`, `\seqBilanCorrigeExo`,
  `\seqAfficheCorrigesBilan`, `\seqBilanObjectifsItem`,
  `\seqBilanRAZExoNum`, environnements `seqBilanObjectifs`,
  `seqBilanQCM`, `seqBilanExo`, compteur `seqBilanExoNum`). Le modèle
  Bilan 2021 n'est plus le modèle de référence pour les nouvelles
  évaluations mais reste fonctionnel pour la recompilation
  d'anciens documents.
- `seqenseigne.sty` (pivot) : ajout de `\RequirePackage{seqenseigne-core-eval}`
  entre `core-exos` et `legacy`. Mise à jour de l'option `ltxdoc` pour
  passer aux quatre modules.
- `seqenseigne.ins` : ajout de la ligne de génération pour
  `seqenseigne-core-eval.sty`.

## Régression zéro

À l'issue de l'étape 1, l'API publique du paquet est strictement
identique à celle d'avant la refonte :

- Toutes les macros publiques `\titreEval`, `\seqBilan`,
  `\seqEvalBaremeItem`, `\seqEvalQCMItem`, `\corrigeExoEval`,
  `\seqEvalAfficheCorriges`, `\seqBilanItemAlea`,
  `\seqBilanCorrigeExo`, `\seqAfficheCorrigesBilan`,
  `\seqBilanObjectifsItem`, `\seqBilanRAZExoNum` conservent leur nom et
  leur signature.
- Tous les environnements publics `qcm`, `seqEvalBareme`,
  `seqEvalExercice`, `seqBilanQCM`, `seqBilanExo`, `seqBilanObjectifs`
  conservent leur nom et leur signature.
- Tous les compteurs publics `ExoEvalNum`, `seqBilanExoNum`,
  `QcmItemNumCnt`, `i`, `AlphCode` conservent leur nom.

Les anciens `.tex` qui compilaient avec le paquet précédent
compileront toujours avec ce paquet refait, à l'exception près signalée
dans la section suivante.

## Bugs latents corrigés au passage

Trois bugs latents du code original ont été corrigés au passage,
parce qu'ils étaient incompatibles avec une réorganisation du code :

1. **`\newwrite\corrfileeval` dans le corps de `\titreEval`**
   (anciennement ligne 896 du `core.dtx`). Un `\newwrite` dans une
   commande gaspille un slot à chaque appel et plante après ~256
   invocations. Dans une session normale d'usage, ça n'arrivait jamais
   en pratique. Le `\newwrite` est désormais déclaré une seule fois,
   globalement, dans `core.dtx`.

2. **`\newcounter{ExoEvalNum}` dans le corps de `\titreEval`**
   (anciennement ligne 922 du `core.dtx`). Un `\newcounter` dans une
   commande plante au deuxième appel de la commande
   (« Counter `ExoEvalNum' already defined »). Pas un problème en
   pratique car `\titreEval` n'est appelé qu'une fois par document. Le
   compteur est désormais déclaré une seule fois, globalement, dans
   `core-eval.dtx`.

3. **`\newcounter{i}`, `\newcounter{AlphCode}`, `\newcommand\repCodes{}`
   dans le corps de l'environnement `qcm`** (anciennement lignes
   1375-1378 du `core.dtx`). Mêmes raisons : redéfinitions à chaque
   ouverture de l'environnement, plantage au deuxième QCM. Ces
   déclarations sont désormais globales en tête de `core-exos.dtx`,
   et l'environnement utilise simplement `\setcounter` et
   `\renewcommand`.

Aucun de ces bugs ne s'était manifesté en usage réel parce que les
documents existants n'ont qu'un seul `\titreEval` et au maximum un
seul `qcm` — mais le rangement plus rigoureux corrige discrètement
ces problèmes.

## Vérifications côté Linux (sandbox)

- Génération `.sty` depuis `.dtx` via `tex seqenseigne.ins` : OK,
  8 fichiers générés, 6003 lignes traitées sans erreur.
- Pas de doublon de `\newcounter` ou `\newwrite` (vérification
  par `grep` sur les `.sty` générés).
- Test de chargement minimal (`\usepackage{seqenseigne}`) bloqué côté
  Linux par `lmodern.sty` indisponible (dépendance externe sans rapport
  avec la refonte).

## À tester côté Windows / MiKTeX portable

- Compilation d'une éval réelle 2019 (par exemple le S01-Arithmétique).
  Aucune macro n'a été renommée donc le `.tex` doit compiler à
  l'identique. Comparer le PDF produit avec le PDF de référence.
- Compilation d'un livret de séquence existant. Le bloc QCM ayant été
  déplacé vers `core-exos`, vérifier qu'un QCM dans une révision (s'il
  y en a) compile correctement.
- Compilation d'un Bilan 2021 si tu en as encore un sous la main, pour
  vérifier que le déménagement vers `legacy` est sans effet.

## Plan de la suite (étapes 2 à 5)

- **Étape 2** : suppression des références mortes au modèle Bilan dans
  `core-eval` (rien ne pointe plus vers `\seqBilan*`), nettoyage des
  options de `\titreEval` qui ne servent plus une fois la nouvelle UI
  appli en place.
- **Étape 3** : renommages — `\titreEval` → `\seqTitreEval`,
  `\corrigeExoEval` → `\seqEvalCorrigeExo`, environnement `qcm` →
  `seqQcm`, `\seqEvalQCMItem` → `\seqQcmItem`, compteur `ExoEvalNum` →
  `seqExoEvalNum`. Rupture de compatibilité assumée pour les `.tex`
  historiques (cf. scoping §1.4).
- **Étape 4** : adaptations — suppression `numSeq`/`titreSeq`/`niveauDiff`
  de `\seqTitreEval`, ajout `bareme=` sur `seqEvalExercice`, scoring
  optionnel sur `seqQcm`, paramètre `nom=` → `titre=` sur
  `seqEvalExercice`.
- **Étape 5** : nouveaux environnements — `seqEvalObjectifs`,
  `seqEvalCriteres`, et item langue française intégré au `seqEvalBareme`.

## Fichiers livrés

```
paquet/
├── seqenseigne.sty                   (modifié : +RequirePackage core-eval)
├── seqenseigne.ins                   (modifié : +ligne génération core-eval)
├── seqenseigne-core.dtx              (allégé : -~490 lignes)
├── seqenseigne-core-exos.dtx         (étoffé : +environnement qcm, helpers)
├── seqenseigne-core-eval.dtx         (NOUVEAU)
├── seqenseigne-legacy.dtx            (étoffé : +bloc Bilan 2021)
├── seqenseigne-data.dtx              (inchangé)
├── seqenseigne-theme.dtx             (inchangé)
├── seqenseigne-flashcard.dtx         (inchangé)
└── seqenseigne-doc.dtx               (inchangé)
```

Plus les `.sty` correspondants, regénérés depuis les `.dtx` par
`docstrip`.

---

*Fin du redémarrage étape 1.*
