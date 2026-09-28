# seqenseigne — Cahier des charges

**Version 0.10.7 — 2 mai 2026 · Laurent Coste**

Ce document décrit la vision pédagogique, le périmètre fonctionnel et
les règles métier de **seqenseigne**. Il sert de référence pour
toute évolution future et pour les futures FAQ / visites guidées.

---

## 1. Vision et contexte

### 1.1 Origine et public cible

seqenseigne est un système pédagogique conçu pour un enseignant de
mathématiques en collège (cycle 4 : 5ème, 4ème, 3ème). Il vise à
unifier en un même outil :

- la **conception** des contenus (notions, méthodes, exercices,
  objectifs, fiches de résumé) ;
- l'**assemblage** de ces contenus en séquences cohérentes (livrets
  de séquence, plans de travail, fiches annuelles) ;
- le **suivi** des élèves au fil de l'année (progressions, évaluations,
  bulletins).

L'enseignant cible exerce dans un environnement contraint :
PC scolaires sans droits d'administration, fonctionnement depuis une
clé USB portable, pas d'accès réseau garanti, pas de Perl, pas
d'installation possible.

### 1.2 Pédagogie sous-tendue

Le système assume un modèle pédagogique précis :

- **Apprentissage par séquences thématiques** plutôt que par
  chapitres linéaires.
- **Progression spiralaire** : un même thème (par ex. « fractions »)
  est repris de niveau en niveau avec des objectifs renforcés.
- **Évaluation par compétences** sur 4 niveaux de maîtrise (I/F/A/E
  pour Insuffisant / Fondamental / Avancé / Excellence) plutôt que
  par notes brutes.
- **Différenciation** par séries d'exercices : Fondamental, Avancé,
  Exploration, Approche, Révision.
- **Réutilisation des exercices d'évaluation** d'un niveau précédent
  comme exercices de révision dans le niveau suivant.

### 1.3 Trois parties complémentaires

seqenseigne est structuré en trois parties qui cohabitent dans la
même application web :

1. **Suivi de classe** (Partie 1) — gestion des élèves, périodes,
   absences, évaluations, progressions annuelles. **Implémentée**.
2. **Conception des atomes pédagogiques** (Partie 2) — édition des
   notions/méthodes/exercices/objectifs/fiches, et leur assemblage
   en séquences-niveau. **En cours, socle stable depuis v0.10**.
3. **Production de documents** (Partie 3) — génération de PDFs
   (livrets de séquence, plans de travail, livrets annuels). En
   partie réalisée (rendu atomique) ; assemblages complets prévus
   v0.11–v0.12.

---

## 2. Modèle pédagogique

### 2.1 Hiérarchie des données de référence

```
Cycle (C03 = 6ème, C04 = 5/4/3ème)
└── Niveau (N09=6e, N10=5e, N11=4e, N12=3e)
    └── Séquence par niveau (14 par niveau, S01..S14)
        └── Partie (1, 2, 3… découpage interne)
            └── Objectif
                ├── Notions associées (N-N)
                ├── Méthode liée (1-1)
                ├── Fiche de résumé liée (1-1)
                └── Exercices F/A/E/R/EA (N-N pour les exos)
```

### 2.2 Atomes pédagogiques

Un atome est une unité indépendante, identifiée et autonome, avec
sa propre fiche d'édition.

| Atome | Description | Cardinalité avec objectif |
|---|---|---|
| **Notion** | Concept (ex. « fonction linéaire »). Synonyme : connaissance. | N-N (limité au scope séquence) |
| **Méthode** | Savoir-faire (ex. « simplifier une fraction »). Inclut critères F/A/E. | 1-1 (limité au scope séquence) |
| **Exercice** | Énoncé paramétré + corrigé toujours présent. | N-N (sans contrainte de scope) |
| **Fiche de résumé** | Carte mémoire élève (1 page A6). | 1-1 (1 fiche = 1 méthode = 1 obj) |
| **Objectif** | Compétence évaluée. Créé implicitement quand une méthode est posée dans une séquence. | — (le pivot) |

### 2.3 Numérotation des objectifs

Chaque objectif a un **code à 2 chiffres** local à sa séquence-niveau :

- **Convention canonique** : `code = (numero_partie - 1) * 10 +
  position_dans_partie`.
- Exemples :
  - Partie 1 : `01` (Connaître le cours), `02`, `03`, …
  - Partie 2 : `11` (Connaître le cours), `12`, `13`, …
- L'objectif `01`, `11`, `21`, … est l'objectif « Connaître le cours »
  automatiquement présent dans chaque partie. Il n'a pas de méthode
  associée et ses critères sont fixes (notes, fiches, oral).

### 2.4 Barème de maîtrise

Fixe pour tous les objectifs :

| Code | Libellé | Points /20 | Description |
|------|---------|------------|-------------|
| `I` | À consolider | 4 | Critère par défaut, non explicité |
| `F` | Maîtrise satisfaisante | 10 | Critère personnalisé par méthode |
| `A` | Très bonne maîtrise | 16 | Critère personnalisé par méthode |
| `E` | Excellence | 20 | Critère personnalisé par méthode |

Pour l'objectif « Connaître le cours », les critères sont fixes :

- F = « A noté la trace écrite en classe. »
- A = « A complété les fiches de résumé. »
- E = « Sait résumer le cours à l'oral. »

(Modifiables globalement via les **préférences** depuis v0.10.5.2.)

### 2.5 Séries d'exercices

| Code | Libellé | Rôle pédagogique |
|---|---|---|
| `F` | Fondamental | Activités d'apprentissage du cours |
| `A` | Avancé | Évaluation principale |
| `E` | Exploration | Activités de prolongement / dépassement |
| `EA` ou `AE` | Approche | Activités d'introduction d'un objectif |
| `R` | Révision | Réutilisation d'un exo `A` d'une séquence n-1 |

**Règle de provenance des exos `R`** : les exercices `R` d'une
séquence-niveau sont nécessairement issus de la série `A` d'une
séquence figurant dans les **précédences** de la séquence courante.

**Règle de provenance des exos `EA`** : les exercices `EA` sont
nécessairement de la série `EA`/`AE` de la séquence-niveau elle-même.

---

## 3. Périmètre fonctionnel

### 3.1 Ateliers de conception

Quatre ateliers atomiques, accessibles depuis l'onglet « Conception » :

1. **Atelier Exercice** : édition de l'énoncé, du corrigé, des
   variables aléatoires (xint), de la série, du nom.
2. **Atelier Notion** : édition du titre, du corps, des sections
   (modèle universel à 2 niveaux : titre + items).
3. **Atelier Méthode** : idem notion, plus critères F/A/E, notions
   associées, marqueur fin de cycle.
4. **Atelier Fiche de résumé** : édition d'une fiche A6 attachée à
   un objectif (1 fiche = 1 méthode = 1 obj).

Chaque atelier offre :

- une sidebar listant tous les atomes du même type (filtrables par
  niveau/séquence et par état d'édition) ;
- un éditeur central avec onglets « Édition » et « Rendu PDF » ;
- un panneau d'**aperçu LaTeX** accessible via une modale ;
- une **garde de sortie** en cas de modifications non sauvegardées
  (depuis v0.10.6) ;
- un **badge d'état** dans la sidebar (modifié / validé / en cours).

### 3.2 Atelier d'assemblage de séquence-niveau

L'atelier central qui orchestre tous les atomes en une séquence
cohérente (5e/4e/3e × S01..S14 = 42 séquences).

- Découpage en **parties** (renumérotation, ajout, suppression,
  conditionnée à la non-vacuité).
- Édition des objectifs (code, nom, méthode liée, critères F/A/E,
  notions associées, fiche de résumé liée).
- Drop d'exercices dans les zones F/A/E/R/EA (contraintes de scope
  pour R et EA).
- Gestion des **précédences** entre séquences-niveau.
- Auto-sauvegarde immédiate (tout drop est persisté).

### 3.3 Génération de PDF

- **Atomes individuels** (notion, méthode, exo, fiche) : aperçu
  rendu inline dans l'atelier via une iframe PDF.
- **Compilation par lot** : modal qui affiche la liste de tous les
  PDFs à compiler (atomes + bientôt livrets) avec barre de progression.
- **Compilation tolérante** : si un atome n'est pas encore validé,
  un filigrane « ÉPREUVE » est appliqué.

### 3.4 Suivi de classe (Partie 1, hors périmètre v0.10.7)

Implémenté depuis v0.6.3c :

- Gestion des classes, des élèves, périodes pédagogiques.
- Saisie des absences et évaluations par session.
- Calcul automatique des progressions annuelles.
- Bulletins et tableaux récapitulatifs PDF.

---

## 4. Règles métier verrouillées

### 4.1 Cardinalités

| Relation | Cardinalité | Validation |
|---|---|---|
| Notion ↔ Objectif | N-N | scope séquence imposé |
| Méthode ↔ Objectif | 1-1 | scope + cardinalité 1-1 imposés (v0.10.7) |
| Fiche de résumé ↔ Méthode | 1-1 | UI : 1 fiche = 1 méthode = 1 obj |
| Exercice ↔ Objectif | N-N | aucune contrainte de scope |

### 4.2 Scope séquence pour notions et méthodes

Une notion ou méthode appartient à **sa séquence d'origine** (champs
`niveau` et `sequence`). Toute liaison à un objectif d'une autre
séquence est refusée par le backend (erreurs `NotionHorsSequence`,
`MethodeHorsSequence`, code HTTP 409).

**Tolérance legacy** : si l'atome n'a pas de scope renseigné (champs
vides), la liaison est acceptée — fallback pour les données
historiques importées sans ces métadonnées.

**Héritage à la création** : depuis v0.10.7, une notion ou méthode
créée dans l'UI hérite automatiquement du `(niveau, séquence)` du
contexte courant (filtre actif `ATL_FILTRE_NIVEAU` /
`ATL_FILTRE_SEQ`).

### 4.3 Cardinalité 1-1 méthode → objectif

Une méthode ne peut être liée qu'à **un seul objectif**. Tentative
de réassignation à un autre objectif sans détacher au préalable :
erreur `MethodeDejaLiee` (HTTP 409). L'idempotence est préservée :
réattacher la même méthode au même objectif est un no-op silencieux.

### 4.4 Provenance des exos en révision et approche

- **Exos R** : doivent provenir d'une séquence-niveau présente dans
  les `precedences` de la séquence courante. Erreurs :
  `ExoRevisionHorsPrecedences`, `ExoRevisionMauvaiseSerie`.
- **Exos EA** : doivent appartenir à la séquence-niveau elle-même
  (série `EA`/`AE`). Erreurs : `ExoApprocheHorsSequence`,
  `ExoApprocheMauvaiseSerie`.

### 4.5 Pas de zone Notions sur l'objectif Connaître

Décidé en v0.10.5.3. L'objectif « Connaître le cours » (`01`,
`11`, `21`, …) n'a pas de zone d'édition pour les notions associées,
ni dans l'atelier d'assemblage ni dans la zone d'édition. Justification
pédagogique : les notions sont attachées aux objectifs « exo », qui
sont les compétences évaluées.

### 4.6 Pas de zone Objectifs sur l'atelier Exercice

Décidé en v0.10.7. La liaison exercice ↔ objectif passe exclusivement
par le drop dans l'atelier d'assemblage (table `objectif_exos`). La
zone « Objectifs associés » de l'atelier Exercice (qui écrivait dans
la table legacy `exercice_objectifs`) a été supprimée — elle créait
un chemin de liaison parallèle redondant et déroutant.

### 4.7 Numérotation contrainte

- Code objectif : 2 chiffres, premier chiffre = `numero_partie - 1`.
- Codes uniques dans une partie (mais pas globalement dans la séquence).
- Validation au backend : `CodeObjectifInvalide`,
  `CodeObjectifDejaUtilise`.

### 4.8 Précédences

- Une précédence relie une séquence-niveau à une autre, en marquant
  la dernière comme « connue de l'élève ».
- Conditionne les exos `R` éligibles dans la séquence courante.
- Validation : pas de doublons, pas de cycles (transitivité non
  étendue dans la version actuelle, à valider en v0.13).

---

## 5. Décisions structurantes

### 5.1 Atomes autonomes

Une notion ou méthode existe **indépendamment** de toute séquence : elle
est créée dans son atelier, dotée d'un titre et d'un contenu, puis
**peut** être liée à un objectif. La liaison se fait dans l'atelier
d'assemblage, pas dans l'atelier de l'atome.

Un objectif est en revanche un atome **dérivé** : il ne peut pas
exister sans être attaché à une partie (et donc à une séquence-niveau).
Sa création est implicite à l'ajout d'une méthode dans une séquence
(et à l'ajout de la méthode automatique pour `01`, `11`, `21`, …).

### 5.2 Modèle universel à 2 niveaux pour le contenu

Notions et méthodes partagent une structure unique :

```
{
  "titre": "...",
  "corps": "préambule LaTeX libre",
  "sections": [
    { "titre": "Section A", "items": ["item1 LaTeX", "item2 LaTeX"] },
    { "titre": "Section B", "items": [...] }
  ]
}
```

Décision prise en v0.6.4 (breaking change) en remplacement des
anciens champs `exemples` / `remarques` / `ordreExRem`. Permet
une expression libre et homogène.

### 5.3 LaTeX comme format pivot

Tous les contenus sont stockés en LaTeX brut (zones d'énoncé,
corrigé, items de section, critères, descriptions de thème, etc.).
Aucune conversion HTML ou Markdown. Justifications :

- Compatibilité directe avec la chaîne de production des livrets PDF.
- Liberté typographique pour les mathématiques.
- Intégration native du package `seqenseigne` (commandes
  personnalisées comme `\seqExercice`, `\seqCorrige`, …).

### 5.4 Auto-sauvegarde dans l'atelier d'assemblage

À l'opposé des ateliers atomiques (qui ont une garde de sortie) :
toute action de drop, retrait, changement de critère ou de nom dans
l'atelier d'assemblage est **persistée immédiatement**. Pas de bouton
« Enregistrer ». Justification : la nature très interactive de cet
atelier (multiples drops successifs).

### 5.5 Compilation tolérante avec filigrane ÉPREUVE

Si un atome n'a pas l'état `validé`, il peut quand même être inclus
dans une compilation, mais avec un filigrane « ÉPREUVE » sur ses
pages. Justifications :

- Permet de visualiser un livret en cours de construction.
- Évite de bloquer la chaîne de production sur une faute de frappe.
- Le filigrane signale visuellement qu'il s'agit d'une version
  intermédiaire.

### 5.6 Intégration des données de référence depuis CSV externes

Les cycles, niveaux, thèmes et séquences sont importés depuis des
CSV externes (`C03_*.csv`, `C04_*.csv`) au démarrage de l'application
(auto-import) si la base est vide pour ce cycle. Cela permet de
versionner ces référentiels indépendamment de l'application.

---

## 6. Hors-scope

Ce que seqenseigne **ne fait pas** et **ne fera pas** dans les
versions à venir :

- **Édition collaborative en ligne** : seqenseigne est un outil
  mono-utilisateur local (clé USB ou poste fixe). Aucune
  synchronisation cloud.
- **Évaluation automatique** : le système ne note pas les copies. Il
  produit les supports d'évaluation (énoncés, corrigés) ; la saisie
  des notes reste manuelle.
- **Chaîne d'authentification d'élèves** : pas de compte élève, pas
  de remise en ligne. Les élèves consomment les PDFs imprimés.
- **Communication parents** : pas d'envoi de bulletins automatique.
  Les bulletins sont des PDFs à imprimer ou exporter par mail
  manuellement.
- **Édition mobile / tablette** : l'UI est optimisée pour un écran
  desktop (≥ 1366px). Pas d'effort de responsivité à prévoir.
- **Conversion HTML / EPUB / Markdown** : seul le format PDF (via
  LaTeX) est ciblé.
- **Gestion d'images** : le scanner d'import récupère les chemins
  d'images depuis les sources LaTeX, mais l'application n'offre pas
  d'éditeur d'images intégré.
- **Versionnage automatique** : les contenus sont édités en place. Le
  versionnage est délégué à git sur le repo source.

---

## 7. Glossaire

| Terme | Définition |
|---|---|
| **Atome pédagogique** | Unité de contenu autonome : notion, méthode, exercice, fiche de résumé. |
| **Cycle** | Regroupement administratif de niveaux (cycle 3 = 6ème, cycle 4 = 5e/4e/3e). |
| **Niveau** | Classe d'élèves : N09=6e, N10=5e, N11=4e, N12=3e. |
| **Séquence** | Unité thématique de l'année (14 séquences par niveau, S01..S14). |
| **Séquence par niveau** | Une séquence donnée pour un niveau donné, par ex. N11/S03. C'est l'objet pivot de l'atelier d'assemblage. |
| **Partie** | Découpage interne d'une séquence-niveau (1, 2, 3…). |
| **Objectif** | Compétence évaluée à l'intérieur d'une partie. Identifié par un code à 2 chiffres. |
| **Connaissance** | Synonyme de **notion** (voir aussi : connaitre vs maîtriser). |
| **Méthode** | Savoir-faire opérationnel, avec critères F/A/E. Une fiche de résumé y est attachée. |
| **Fiche de résumé** | Carte mémoire élève au format A6, attachée à une méthode. |
| **Précédence** | Lien entre deux séquences-niveau pour exprimer que l'une est connue de l'élève au moment d'aborder l'autre. |
| **Plan de travail** | Document à fournir aux élèves listant les travaux à effectuer (à venir v0.11). |
| **Livret de séquence** | PDF imprimable réunissant toutes les ressources d'une séquence-niveau (à venir v0.11). |
| **Livret annuel** | PDF imprimable par niveau, regroupant les fiches de résumé ou les plans de travail de l'année (à venir v0.12). |
| **Référentiel** | Données de référence partagées (cycles, niveaux, thèmes, séquences). À distinguer du **référentiel de niveau** propre à un enseignant (v0.13). |
