# Redémarrage — Paquet LaTeX v0.13.5.2 étape 4

> Livraison du 9 mai 2026.
> Nouvel environnement `seqEvalObjectifs` pour l'affichage de la grille
> de critères de maîtrise des objectifs évalués.
>
> **Étape 4 sur 5** du plan de refonte. Pure addition fonctionnelle,
> aucune rupture API par rapport à l'étape 3.

## Périmètre de cette livraison

### Nouvel environnement `seqEvalObjectifs`

**Cas d'usage** : éval en mode de notation `criteres` ou `note_criteres`
(cf. scoping §2.4). Pour les modes `note` ou `aucun`, l'appli ne génère
pas ce tableau — il n'a pas de raison d'être sans critères de maîtrise.

**Usage côté `.tex`** :

```latex
\begin{seqEvalObjectifs}
    \seqEvalObjectifsItem{Obj. 02}{Pour les nombres décimaux, passer
        de l'écriture décimale à l'écriture fractionnaire et inversement.}
    \seqEvalObjectifsItem{Obj. 04}{Calculer le PGCD de deux nombres
        entiers par soustractions successives.}
    \seqEvalObjectifsItem{Obj. 07}{Reconnaître et utiliser le théorème
        de Thalès dans une configuration directe.}
\end{seqEvalObjectifs}
```

**Rendu** : tableau à 6 colonnes dans une `boitePaleVariable` :
- 1 colonne `code` (ratio 2)
- 1 colonne `intitulé` (ratio 5)
- 4 colonnes de cases à cocher (ratio 1 chacune) avec en-têtes
  `Insuffisant`, `À consolider`, `Satisfaisant`, `Très bon`
- Titre fusionné « Niveaux de maîtrise des objectifs évalués »

L'enseignant coche manuellement le niveau atteint pour chaque
objectif après correction de la copie de l'élève.

### Conventions retenues

**Sur la signature de `\seqEvalObjectifsItem`** : `{<code>}{<intitulé>}`
où le `<code>` est un agrégat fourni par l'appli, par exemple :
- `Obj. 02` si tous les objectifs évalués viennent de la même séquence
- `Séq. S03 Obj. 13` pour identifier la séquence d'origine quand
  plusieurs séquences sont concernées

L'agrégation est une **décision pédagogique de l'appli**, pas du paquet.

**Sur la limite à un seul tableau** : pas d'environnement séparé
`seqEvalCriteres` distinct de `seqEvalObjectifs`. Si on veut juste la
liste des objectifs sans critères, on ne génère rien — la valeur
ajoutée d'afficher les objectifs sans critères de maîtrise n'a pas
été identifiée comme pertinente côté pédagogie.

**Sur les cases à cocher** : `\ding{113}` (carré creux du paquet
pifont, déjà chargé pour la dinglist du QCM). Pas de nouvelle
dépendance.

### `seqEvalBareme` reste inchangé pour l'item langue française

Le scoping prévoit un item « Présentation et usage de la langue
française » optionnel dans le barème (cf. scoping §2.2). Côté paquet,
rien à ajouter : l'environnement `seqEvalBareme` accepte déjà
n'importe quel `\seqEvalBaremeItem`. C'est l'appli qui injecte cet
item conditionnellement à la fin de la liste :

```latex
\begin{seqEvalBareme}
    \seqEvalBaremeItem{Exercice I}{4 points}
    \seqEvalBaremeItem{Exercice II}{4 points}
    \seqEvalBaremeItem{Présentation et usage de la langue française}{1 point}
\end{seqEvalBareme}
```

## Vérifications côté Linux (sandbox)

- Génération `.sty` depuis `.dtx` via `tex seqenseigne.ins` : OK.
- Présence du nouveau `\newenvironment{seqEvalObjectifs}` et
  de `\newcommand{\seqEvalObjectifsItem}` dans le `.sty` généré.

## À tester côté Windows / MiKTeX portable

Un fichier `test_etape4.tex` est livré dans le ZIP. Il teste :
- Page de titre avec barème incluant l'item langue française
- Tableau d'objectifs avec critères de maîtrise (3 objectifs)
- Exercices classiques et QCM (intégration avec étapes précédentes)

Points à vérifier visuellement :
- Le tableau d'objectifs s'affiche entre le barème et les exercices
- Le titre « Niveaux de maîtrise des objectifs évalués » est fusionné
  sur les 6 colonnes
- Le sous-titre « Objectif » fusionne les 2 premières colonnes
- Les 4 cases à cocher s'affichent à droite de chaque ligne
- L'intitulé long de l'objectif passe à la ligne dans sa colonne
  (alignement gauche, ratio 5)

## Fin du plan v0.13.5.2 paquet ?

Étape 4 = dernière étape prévue dans le plan de refonte du paquet.

Si tu confirmes que tout fonctionne, le paquet est prêt pour le
versant appli de v0.13.5.2 :
- v0.13.5.2 (côté appli) : atome Évaluation, schéma BDD, atelier UI
- v0.13.5.3 : génération `.tex` depuis BDD via les macros qu'on
  vient de finaliser

Côté paquet, il restera à traiter :
- Sous-version dédiée `core-exos` (passage à 4 flags indépendants
  R/AE, F, A, E pour les corrigés). Avant la partie appli qui
  consomme le « Livret de corrigés d'exos » (v0.13.5.6).

## Fichiers livrés

```
paquet/
├── seqenseigne.sty                   (inchangé depuis étape 3)
├── seqenseigne.ins                   (inchangé)
├── seqenseigne-core.dtx              (inchangé depuis étape 2)
├── seqenseigne-core-exos.dtx         (inchangé depuis étape 2 patch v3)
├── seqenseigne-core-eval.dtx         (modifié : ajout seqEvalObjectifs)
├── seqenseigne-legacy.dtx            (inchangé depuis étape 2)
├── seqenseigne-data.dtx              (inchangé)
├── seqenseigne-theme.dtx             (inchangé)
├── seqenseigne-flashcard.dtx         (inchangé)
└── seqenseigne-doc.dtx               (inchangé)
test_etape4.tex                       (NOUVEAU : fichier de test)
```

Plus les `.sty` correspondants, regénérés depuis les `.dtx` par
`docstrip`.

---

*Fin du redémarrage étape 4.*
