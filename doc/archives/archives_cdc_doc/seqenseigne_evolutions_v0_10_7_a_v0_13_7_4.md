# seqenseigne — Évolutions v0.10.7 → v0.13.7.4

> Document de transition — mai 2026
> Auteur : Laurent Coste (rédigé avec Claude)

Ce document **complète** les trois documents principaux qui sont restés en
version v0.10.7 :

- `seqenseigne_cdc_v0_10_7.md` — Cahier des charges
- `seqenseigne_doc_technique_v0_10_7.md` — Documentation technique
- `seqenseigne_usecases_v0_10_7.md` — Cas d'usage

Pour comprendre l'état actuel de seqenseigne, il faut **lire d'abord ces
trois docs** (qui restent globalement valides sur la pédagogie et les
principes), puis **consulter ce document** pour les évolutions
intervenues depuis. C'est une mesure transitoire : à terme, ces trois
docs devraient être réécrites.

Ce document est organisé **par grand thème** plutôt que par version,
parce que c'est ce qui est utile à quelqu'un qui veut comprendre l'état
actuel. Pour la chronologie détaillée par version, consulter les notes
`redemarrage_v0_*.md` correspondantes.

---

## Table des matières

1. [Vue d'ensemble des grandes étapes](#1-vue-densemble-des-grandes-étapes)
2. [Évolutions du modèle pédagogique](#2-évolutions-du-modèle-pédagogique)
3. [Évolutions des ateliers](#3-évolutions-des-ateliers)
4. [Évolutions du paquet LaTeX et de la chaîne de rendu](#4-évolutions-du-paquet-latex-et-de-la-chaîne-de-rendu)
5. [Évolutions du backend](#5-évolutions-du-backend)
6. [Évolutions du frontend](#6-évolutions-du-frontend)
7. [Évolutions de l'outillage et de la livraison](#7-évolutions-de-loutillage-et-de-la-livraison)
8. [Pointage doc-par-doc — ce qui doit être mis à jour](#8-pointage-doc-par-doc)

---

## 1. Vue d'ensemble des grandes étapes

Entre v0.10.7 (2 mai 2026) et v0.13.7.4 (18 mai 2026), 15 jours
d'évolution intense découpés en 6 grandes étapes :

| Étape | Versions | Thème principal |
|---|---|---|
| **A — Livret de séquence** | v0.11 | Production du PDF de séquence complet, remédiation, sélection fine des prérequis |
| **B — Plans de travail** | v0.12 | Plans de travail par séquence + livret annuel niveau, harmonisation ateliers, refonte assemblage |
| **C — Référentiel BdD** | v0.13.0–.1 | Table `param_niveaux`, substitution des tables hardcodées |
| **D — Livrets affinés + référentiels millésimés** | v0.13.2–.4 | Refonte sections prérequis/objectifs, atelier Référentiel |
| **E — Évaluations + design system + hygiène** | v0.13.5 | Atelier Évaluation, design system, CONVENTIONS/GOTCHAS |
| **F — Cartes + publication + refonte OO** | v0.13.6 | Cartes d'automatisme, catalogue de documents publiables, refonte OO des 5 ateliers, uniformisation `nom`→`titre` |
| **G — Garde de sortie + éditeur LaTeX** | v0.13.7 | Modale de sortie unifiée, éditeur LaTeX intégré avec barre d'outils contextuelle, générateurs QCM/Liste, navigateur d'images |

---

## 2. Évolutions du modèle pédagogique

### 2.1 Nouveaux types d'atomes

Le cdc v0.10.7 listait **4 types** : notion, méthode, exercice, fiche
de résumé. Aujourd'hui s'ajoutent :

- **Carte d'automatisme** (v0.13.6.2.3+) : atome recto/verso pour
  l'entraînement à la mémorisation et aux automatismes calculatoires.
  Liée à un objectif (refonte du lien en v0.13.6.13).
- **Évaluation** (v0.13.5.2+) : ensemble d'exercices avec barème,
  couvrant des objectifs précis. Validation pédagogique et
  dévalidation, calcul de couverture, liaisons évaluation ↔ objectifs.

Soit **6 atomes** au total.

### 2.2 Référentiels millésimés

Le cdc v0.10.7 supposait des référentiels statiques (CSV C04 importé une
fois). En v0.13.5.x, introduction d'un **atelier Référentiel** avec
versioning par millésime. Permet de figer un état des séquences /
objectifs / cartes pour une année scolaire donnée et de comparer entre
millésimes.

### 2.3 Remédiation

Ajoutée en v0.11 comme zone optionnelle de l'exercice :
`énoncé de remédiation` + `corrigé de remédiation`. Quasi-obligatoire
pour la série F, optionnelle (mais conseillée) pour la série A, non
pertinente pour la série E.

### 2.4 Mises en route / automatismes (à venir)

Concepts identifiés mais **non encore spécifiés ni implémentés**. Prévus
pour v0.15+. À traiter dans une session dédiée.

### 2.5 Sections aplatissables (fiches)

Les fiches de résumé existaient en v0.10.7 mais leur composition à
partir d'éléments **aplatissables** d'autres atomes a été affinée. La
réintroduction propre d'« Initialiser depuis » via
`/api/v2/fiches/<id>/atomes-aplatissables` est prévue (retirée
temporairement en v0.13.6.16).

---

## 3. Évolutions des ateliers

### 3.1 Refonte OO des 5 ateliers atomes (v0.13.6.6+)

C'est sans doute le **changement architectural le plus important** depuis
v0.10.7.

**Avant** : chaque atelier avait son propre fichier JS de plusieurs
centaines de lignes, avec beaucoup de duplication entre eux (chargement
de liste, ouverture d'un item, sauvegarde, suppression).

**Après** (v0.13.6.6 puis migration des 5 ateliers en v0.13.6.7.x) :

```
AtelierEditeur                     (static/ateliers/atelier_editeur.js)
  ├─ AtelierAtomique               (notion, méthode, exercice)
  ├─ AtelierFiche                  (fiche de résumé)
  └─ AtelierCarte                  (carte d'automatisme)
```

La classe parente `AtelierEditeur` factorise `chargerListe`, `ouvrirItem`
(GET unitaire), `nouvelItem` (POST-direct via `_payloadCreation()`,
overridable), `sauvegarder` (PATCH), `supprimer`. Les sous-classes ne
font qu'ajuster ce qui leur est spécifique.

`AtelierExercice` surcharge `nouvelItem` pour intercepter la modale de
sélection de série (F/A/E/AE).

`AtelierEvaluation` (v0.13.5.2.4) est dans la même famille, séparée des
atomes proprement dits (portée niveau et non séquence).

### 3.2 Atelier d'assemblage (v0.12.3.0+)

L'atelier d'assemblage de séquence-niveau a été refondu en v0.12.3.0 :
port des fonctionnalités essentielles d'**editv2** (l'éditeur v2
historique) dans l'atelier d'assemblage, puis suppression effective
d'editv2 en v0.12.3.1.

Ajouts depuis v0.10.7 :
- Onglets **Édition** / **Rendu PDF** (v0.11.4) avec basculement
- Tree « Éléments à inclure » : Cours / Exercices, avec cases « toujours »
  grisées pour les blocs structurels
- Splitter redimensionnable pour la sidebar

### 3.3 Atelier Référentiel (v0.13.5.x)

Nouveau. Tableau de bord visuel d'un référentiel pour une année donnée :
arbre des séquences, objectifs, cartes d'automatisme, avec badges
colorés (v0.13.5.1.3) indiquant le statut (placé, validé, etc.).

Évolutions successives : refonte du rendu (v0.13.5.1.2), badges
(v0.13.5.1.3), objectifs « Cours » allégés (v0.13.5.1.4).

### 3.4 Catalogue de documents publiables (v0.13.6.4)

Nouvel atelier qui catalogue tous les documents PDF publiables (livret
de séquence, livret annuel de plans de travail, fiches de résumé,
livret annuel de fiches, etc.) avec compilation centralisée
(v0.13.6.5.1).

### 3.5 Atelier Carte d'automatisme (v0.13.6.2.3+)

Nouveau. Édition recto/verso, peuplement initial pour N10 puis pour
les autres niveaux. Refonte du lien carte → objectif (v0.13.6.13).

### 3.6 Atelier Évaluation (v0.13.5.2.4)

Nouveau. Sélection d'exercices avec calcul de couverture des objectifs,
barème, liaisons évaluation ↔ objectifs. Déduction automatique du
`type_format` (v0.13.5.2.3) à partir de l'énoncé.

### 3.7 Multi-sélection et menu contextuel (v0.13.6.8)

Sélection multiple dans les listes d'ateliers, menu contextuel (clic
droit) pour les actions de masse.

### 3.8 Bouton « Reprendre titre objectif » (v0.13.6.11)

Bouton qui recopie le titre de l'objectif courant dans le champ titre
de l'atome en cours d'édition.

### 3.9 Uniformisation `exercices.nom` → `exercices.titre` (v0.13.6.12)

Renommage de la colonne pour cohérence avec les autres atomes
(notion, méthode, etc. qui ont tous un champ `titre`).

### 3.10 Garde de sortie unifiée (v0.13.7.0a–e)

Refonte complète de la détection « champ modifié » et de la modale qui
demande à l'utilisateur s'il veut sauvegarder, jeter ou annuler avant
de quitter un item.

**Approche** : snapshot-based (capture des valeurs au chargement de
l'item, comparaison à la sortie). Modale unifiée à 3 boutons pour les
5 ateliers, en remplacement des modales hétérogènes précédentes.

Effets de bord positifs :
- Factorisation `_enregistrer_routes_atome(bp, type_atome, segment_url,
  creer, modifier, supprimer, ...)` dans `routes/atomes.py` qui réduit
  la route layer de ~700 à ~280 lignes
- Convention POST/PATCH stricte sur les 5 ateliers (v0.13.7.0e.2)
- POST sans niveau/séquence dans le corps (envoyés par
  `_payloadCreation` côté JS), PATCH strict pour les modifications

### 3.11 Éditeur LaTeX intégré (v0.13.7.1+)

**Nouveau chantier majeur en cours**. Modale plein écran avec :

- **Onglet Outils** (v0.13.7.1) : barre d'outils contextuelle. 9
  contextes (variables, exo-enonce, exo-corrige, notion-corps,
  methode-corps, fiche-section, carte-recto, carte-verso,
  theme-description). 14 groupes de boutons (maths_inline, listes,
  mise_en_page, completer, boites_pedago, etc.). Chaque contexte
  affiche un sous-ensemble pertinent de groupes.
- **Onglet Tout le paquet** (v0.13.7.1) : navigation dans les
  définitions du paquet seqenseigne (4 fichiers exposés : Cœur, Thème,
  Exercices, Cartes), avec filtrage des macros structurelles
  (v0.13.7.2.1).
- **Onglet Aides** : ressources d'aide.

Évolutions cumulatives :
- v0.13.7.2 : engrenage de configuration des groupes affichés
  (persistance localStorage par contexte)
- v0.13.7.2.1 : distinction structurel/contenu (macros que l'app ajoute
  automatiquement vs macros que l'utilisateur insère)
- v0.13.7.3 : wrapping de sélection avec marqueur `•` (convention
  Texmaker), générateurs QCM et Liste avec mini-modales paramétrables
- v0.13.7.4 : navigateur d'images depuis `data/images/` (vue liste +
  vue grille avec miniatures, recherche live), élargissement des
  mini-modales (+50%)
- v0.13.7.5 (prévu) : générateur de tableau `tblr`

---

## 4. Évolutions du paquet LaTeX et de la chaîne de rendu

### 4.1 Service `paquet_parseur.py` (cohérent avec doc technique v0.10.7)

Le parseur `.dtx` → `paquet_definitions` était déjà en place en v0.10.7
mais a reçu deux **hotfixes critiques** en v0.13.7.2.2/.3 :

- **v0.13.7.2.2** : reconnaissance de `\define@choicekey` (xkeyval). Sans
  ce fix, la clé `explication` de l'environnement `seqQcm` n'était pas
  indexée → erreur xkeyval à la compilation.
- **v0.13.7.2.3** : détection des compteurs LaTeX référencés par leur
  **nom textuel** (sans backslash) dans `\setcounter{NOM}`, `\stepcounter`,
  `\value`, `\forloop`, `\arabic`, `\roman`, `\alph`, `\Alph`, `\Roman`,
  `\refstepcounter`, `\addtocounter`. Sans ce fix, le compteur
  `seq@qcm@alphcode` du `seqQcm` n'était pas tiré dans le préambule.

**Dette importante à surveiller** : la fonction `analyser_corps` stocke
désormais **deux conventions** dans `macros_appelees` : des noms avec
backslash (les macros classiques) ET des noms sans backslash (les
compteurs). Toute refonte de ce champ doit préserver cette dualité,
sinon `seqQcm` et toute construction utilisant `\forloop` replanteront.

### 4.2 Service `preambule_atome.py`

Inchangé en architecture (fermeture transitive). Mais sa qualité
d'output dépend fortement de `paquet_parseur` (cf. ci-dessus).

Documentation des wrappers : `WRAPPER_COMMUN` et `WRAPPER_PAR_TYPE` ont
été enrichis. Voir aussi la liste sœur `MACROS_STRUCTURELLES` de
`services/paquet_expose.py` (v0.13.7.2.1) qui partage la sémantique mais
sert une finalité UI distincte.

### 4.3 Service `livret_sequence.py` (étendu)

Le livret de séquence existait en v0.10.7 mais a reçu de nombreuses
améliorations en v0.11.x–v0.13.x :
- Section remédiation pour les exercices (v0.11)
- Refonte des sections prérequis et objectifs (v0.13.2)
- 4 améliorations demandées par retour d'usage (v0.13.3)
- Ordre Révisions → Cours → F/A/E
- `\seqInitCorriges`, `\seqInitAnnexes` en début + `\seqAfficheAnnexes`,
  `\seqAfficheCorriges` en fin
- `\clearpage` avant chaque section, `\cleardoublepage` avant Fiches

### 4.4 Nouveau service `paquet_expose.py` (v0.13.7.1)

Filtre les définitions du paquet pour l'onglet « Tout le paquet » de
l'éditeur LaTeX. Expose seulement 4 fichiers source (Cœur, Thème,
Exercices, Cartes), 3 types LaTeX (command, environment, tcolorbox),
en excluant les macros internes (nom contenant `@`).

Liste `MACROS_STRUCTURELLES` (v0.13.7.2.1) : 30 macros que l'app ajoute
automatiquement et qu'on filtre par défaut, avec case à cocher pour
afficher (utilisateur expert).

### 4.5 Nouveau service `images_navigateur.py` (v0.13.7.4)

Liste les images de `data/images/` (flat, hash SHA256, dédupliquées).
Extensions reconnues : png, jpg, jpeg, pdf. Filtre les fichiers cachés
et les sous-dossiers.

### 4.6 Catalogue de documents publiables (v0.13.6.4)

Nouveau service `services/cataloque_publication.py` qui inventorie les
types de documents PDF publiables et leur statut de compilation.
Couplé à un service de compilation centralisé (v0.13.6.5.1.1) qui
unifie la gestion des erreurs.

### 4.7 Plans de travail (v0.12)

Génériques (v0.12.0) puis livret annuel des plans de travail à portée
Niveau (v0.12.1). Pas dans le cdc v0.10.7.

---

## 5. Évolutions du backend

### 5.1 Architecture en blueprints

Le `app.py` était déjà modulaire en v0.10.7. Depuis, beaucoup de
nouveaux blueprints ont été ajoutés :

- `routes/paquet.py` (v0.13.7.1) : `GET /api/paquet/definitions`
- `routes/images.py` (v0.13.7.4) : `GET /api/images`, `GET /api/images/preview/<nom>`
- `routes/evaluations.py` (v0.13.5.2)
- `routes/referentiel.py` (v0.13.5.x)
- `routes/cartes.py` (v0.13.6.2+)
- `routes/catalogue.py` (v0.13.6.4)
- `routes/plans_travail.py` (v0.12)
- etc.

### 5.2 Table BdD `param_niveaux` (v0.13.0)

Nouvelle table qui amorce automatiquement les paramètres par niveau
(noms courts, codes, etc.). Substitution progressive des tables
hardcodées par lectures BdD en v0.13.1.

### 5.3 Schéma de validation d'état rationalisé (v0.13.6.8.2)

Refonte du backend pour les actions de validation/dévalidation des
atomes, avec wrappers `valider_carte`/`devalider_carte` (v0.13.6.8.2.1).

### 5.4 Harmonisation backend (v0.13.6.15) puis frontend (v0.13.6.16)

Refonte en deux étapes du contrat liste pour les 5 atomes :
- v0.13.6.15 (backend uniquement, UI temporairement cassée) : unification
  du contrat de liste à 6 clés `{id, titre, num, code, etat_code,
  liens}`, ajout de GET unitaires `/api/notions/<id>`, `/api/methodes/<id>`,
  `/api/exercices/<id>`
- v0.13.6.16 (frontend) : alignement sur le contrat backend

### 5.5 Migration `exercices.nom` → `exercices.titre` (v0.13.6.12)

Migration du schéma + propagation dans les services + correctifs des
tests (v0.13.6.12.3, .4).

### 5.6 Refonte du lien carte → objectif (v0.13.6.13)

Avant : lien indirect via la séquence + le numéro d'objectif local.
Après : foreign key directe vers la table `objectifs`.

### 5.7 Modèle v2 et modèle legacy

Le **modèle v2** (parties + objectifs) introduit en v0.10 reste central.
La doc technique v0.10.7 le décrit correctement.

À nettoyer en v0.14 : table `exercice_objectifs` (héritage legacy),
fichier `services/edition_progression.py` mort, variable JS
`ATL_OBJ_CAT`, route `/api/objectifs`, table `objectifs` dans son rôle
historique. Voir [README.md section 7.2 — roadmap v0.14](README.md).

---

## 6. Évolutions du frontend

### 6.1 Refonte OO des ateliers (cf. section 3.1)

Le changement structurel le plus important. Voir aussi
`atelier_editeur.js` (classe parente) et la documentation associée dans
la mémoire technique de Claude.

### 6.2 Design system (v0.13.5.1)

Adapté du design system « Parcours Avenir » (v0.67) : police Inter,
palette bleu #2E5090, variables CSS unifiées.

Principe (v0.11.4+) : classes `.atl-cadre` / `.atl-cadre--compact` /
`.atl-cadre-titre` pour TOUS les cadres d'atelier. Pas de doublons
`.xxx-bloc` par atelier.

### 6.3 Éditeur LaTeX intégré (v0.13.7.1+)

Voir section 3.11 plus haut. C'est un module JS dédié
(`static/editeur_latex.js`, ~900 lignes en v0.13.7.4) avec son JSON
de configuration (`static/data/toolbar_seqenseigne.json`).

### 6.4 Mini-modale générique (v0.13.7.2 puis étendue)

Une structure DOM unique réutilisée pour 4 types :
- `config-groupes` (engrenage v0.13.7.2)
- `qcm` (générateur QCM v0.13.7.3)
- `liste` (générateur Liste v0.13.7.3)
- `image` (navigateur d'images v0.13.7.4)
- `tableau` (placeholder, v0.13.7.5)

Le dispatch se fait via `data-type`.

### 6.5 Auto-sauvegarde (atelier d'assemblage)

Mentionnée en v0.10.7 (cdc section 5.4). Toujours d'actualité,
fonctionne comme prévu.

### 6.6 Conventions JS récentes

- `ATL_FILTRE_NIVEAU` / `ATL_FILTRE_SEQ` partagés entre ateliers
  (toujours valable)
- Persistance des préférences UI via localStorage (v0.13.7.2+) :
  visibilité des groupes, affichage des macros structurelles,
  vue liste/grille du navigateur d'images

---

## 7. Évolutions de l'outillage et de la livraison

### 7.1 Conventions de livraison (v0.13.5.1.6)

Documents `CONVENTIONS.md` et `GOTCHAS.md` livrés en v0.13.5.1.6. Ces
documents devraient être consultables à la racine du dépôt (à
vérifier).

### 7.2 `lancer.bat` (v0.13.5.1.5–.6)

Plusieurs ajustements pour gérer les caractères spéciaux et le parsing
cmd.exe.

### 7.3 MANIFEST.md5 (convention récente)

Chaque ZIP de livraison inclut un `MANIFEST.md5` à la racine avec les
chemins préfixés par `appli/`. Permet la vérification post-déploiement
via `verifier_md5.py`.

### 7.4 Tests pytest

Suite enrichie en continu. **3285 passed** en v0.13.7.4 (vs ~2500 en
v0.10.7 estimé).

### 7.5 Outil `lister_atomes_orphelins.py`

Existait en v0.10.7 (cf. doc technique section 10.1). À intégrer dans
l'UI admin en v0.14 (cf. roadmap).

### 7.6 Outil `purger_fiches.py` (v0.11.1.x)

Script CLI pour vider sélectivement les fiches de résumé avec filtres
`--niveau` / `--sequence`, dry-run par défaut, confirmation interactive
`'OUI'`, cascade FK propre. À étendre à tous les types d'atomes en
v0.14.

---

## 8. Pointage doc-par-doc

Ce qui suit indique, **section par section**, ce qui est encore valide
dans les 3 docs principales v0.10.7 et ce qui doit être mis à jour.
C'est une checklist pour la réécriture future.

### 8.1 `seqenseigne_cdc_v0_10_7.md`

| Section | État | Mise à jour requise |
|---|---|---|
| 1.1 Origine et public cible | ✅ valide | — |
| 1.2 Pédagogie sous-tendue | ✅ valide | — |
| 1.3 Trois parties complémentaires | ⚠ à compléter | Partie 3 partiellement réalisée (livret de séquence, livret annuel plans de travail) |
| 2.1 Hiérarchie des données de référence | ✅ valide | Ajouter les référentiels millésimés (v0.13.5.x) |
| 2.2 Atomes pédagogiques | ⚠ à compléter | Ajouter cartes d'automatisme et évaluations |
| 2.3 Numérotation des objectifs | ✅ valide | — |
| 2.4 Barème de maîtrise | ✅ valide | — |
| 2.5 Séries d'exercices | ⚠ à compléter | Ajouter la remédiation (v0.11) |
| 3.1 Ateliers de conception | ⚠ à étendre | Ajouter atelier Carte, atelier Évaluation, atelier Référentiel, atelier Catalogue |
| 3.2 Atelier d'assemblage séquence-niveau | ⚠ à reformuler | Refondu en v0.12.3.0 (port editv2). Onglets Édition/PDF (v0.11.4) |
| 3.3 Génération de PDF | ⚠ à compléter | Livret de séquence opérationnel, plans de travail, catalogue de documents publiables |
| 3.4 Suivi de classe | ✅ valide (hors périmètre) | — |
| 4. Règles métier verrouillées | ✅ valide majoritairement | Section 4.3 (cardinalité 1-1 méthode→objectif) : vérifier face à la refonte v0.13.6.13 lien carte→objectif |
| 5.1 Atomes autonomes | ✅ valide | — |
| 5.2 Modèle universel à 2 niveaux | ✅ valide | — |
| 5.3 LaTeX comme format pivot | ✅ valide | — |
| 5.4 Auto-sauvegarde | ✅ valide | — |
| 5.5 Compilation tolérante + filigrane | ✅ valide | — |
| 5.6 Intégration CSV référentiels | ⚠ à étendre | Plus seulement CSV : `param_niveaux` BdD (v0.13.0), référentiels millésimés (v0.13.5.x) |
| 6. Hors-scope | ⚠ à revoir | Plusieurs items hors-scope sont devenus en-scope ou planifiés (cartes, évaluations, éditeur LaTeX) |
| 7. Glossaire | ⚠ à enrichir | Termes nouveaux : carte d'automatisme, évaluation, référentiel millésimé, atelier d'assemblage v2, garde de sortie, éditeur LaTeX, mini-modale, snippet structurel, document publiable |

### 8.2 `seqenseigne_doc_technique_v0_10_7.md`

| Section | État | Mise à jour requise |
|---|---|---|
| 1. Vue d'ensemble | ✅ globalement valide | Tests : 3285 (v0.13.7.4) |
| 2. Architecture | ⚠ à étendre | Nouvelles arborescences `routes/`, services additionnels (cf. section 4 du présent doc) |
| 3.1 Données de référence | ⚠ à compléter | Ajouter `param_niveaux` (v0.13.0), tables référentiel millésimé |
| 3.2 Atomes pédagogiques | ⚠ à compléter | Ajouter cartes_automatisme, evaluations, exercice_remediation |
| 3.3 Modèle v2 | ✅ valide | — |
| 3.4 Tables legacy / dépréciées | ⚠ à étendre | Plus de tables à déprécier : `exercice_objectifs`, `objectifs` legacy (cf. roadmap v0.14) |
| 3.5 Suivi de classe | ✅ valide | — |
| 4.1 `v2_edition.py` | ✅ valide | — |
| 4.2 `v2_lecture.py` | ✅ valide | — |
| 4.3 `liaisons_atomes.py` | ✅ valide | — |
| 4.4 `atomes.py` | ⚠ à compléter | Refonte avec hooks de validation pédagogique pour création POST-direct (v0.13.6.16) |
| 4.5 `latex_rendu_atome.py` / `compilateur_pdf.py` | ✅ globalement valide | Détails sur le filigrane, les variables, etc. à reverifier |
| 4.6 `fiches_import.py` | ✅ valide | — |
| 4.7 `preferences.py` | ✅ valide | — |
| 5.1 Structure générale frontend | ⚠ à étendre | Architecture OO des ateliers (v0.13.6.6+) |
| 5.2 Modules JavaScript | ⚠ à étendre | Nouveaux modules : `atelier_editeur.js`, `editeur_latex.js`, `atelier_carte.js`, `atelier_evaluation.js`, etc. |
| 5.3 Variables d'état globales | ⚠ à compléter | Ajouter les préférences localStorage de l'éditeur LaTeX |
| 5.4 Conventions JS | ⚠ à compléter | Conventions OO (classe parente, surcharge), conventions de mini-modales |
| 5.5 Sidebar badges | ⚠ à étendre | Badges colorés v0.13.5.1.3 |
| 6.1 Atomes (CRUD direct) | ⚠ à compléter | Routes unitaires GET (v0.13.6.15), endpoint contrats unifiés |
| 6.2 Modèle v2 | ✅ valide | — |
| 6.3 Format d'erreur homogène | ✅ valide | — |
| 7.1 Pipeline de rendu | ✅ valide | — |
| 7.2 Filigrane ÉPREUVE | ✅ valide | — |
| 7.3 Variables paramétrées | ✅ valide | — |
| 7.4 Compilation par lot | ⚠ à étendre | Service de compilation centralisé (v0.13.6.5.1.1), catalogue de documents publiables |
| 8.1 SqliteStore | ✅ valide | — |
| 8.2 Stratégie diff-based | ✅ valide | — |
| 8.3 Migrations de schéma | ⚠ à compléter | Migrations notables : `param_niveaux`, `cartes_automatisme`, `evaluations`, `exercices.nom→titre` |
| 9. Tests | ⚠ chiffres à jour | 3285 (v0.13.7.4) |
| 10. Outillage | ⚠ à compléter | Ajouter `purger_fiches.py` (v0.11.1.x) |
| 11. Décisions techniques | ✅ valides | Toutes confirmées |

**Nouvelles sections à ajouter** :
- **Paquet LaTeX et chaîne `.dtx` → BdD** : `paquet_parseur.py`,
  `paquet_expose.py`, `preambule_atome.py`. Avec mention de la dualité
  des conventions dans `macros_appelees` (cf. section 4.1 du présent
  document, dette à surveiller).
- **Éditeur LaTeX intégré** : architecture, contextes, mini-modale
  générique, conventions de snippet (marqueur `•`, snippets spéciaux
  comme `__NAVIGATEUR_IMAGES__`).
- **Navigateur d'images** : `images_navigateur.py`, routes `/api/images*`,
  sécurité de la route preview (3 niveaux de validation).

### 8.3 `seqenseigne_usecases_v0_10_7.md`

| Section | État | Mise à jour requise |
|---|---|---|
| 1. Démarrage | ✅ valide | — |
| 2. Rédaction d'une notion | ⚠ à compléter | Ajouter l'usage de l'éditeur LaTeX intégré (v0.13.7+) |
| 3. Rédaction méthode + fiche | ⚠ à compléter | Idem : usage de l'éditeur LaTeX |
| 4. Rédaction exercice | ⚠ à compléter | Ajouter la zone remédiation (v0.11), l'usage des générateurs QCM/Liste (v0.13.7.3) |
| 5. Assemblage séquence-niveau | ⚠ à reformuler | Onglets Édition/PDF, refonte v0.12.3.0 |
| 6. Réutilisation exo en révision | ✅ valide | — |
| 7. Modification atome déjà placé | ✅ valide | — |
| 8. Génération de PDF | ⚠ à étendre | Plans de travail, livret annuel niveau, catalogue de documents publiables, livret de séquence complet |
| 9. Import de contenus existants | ✅ valide | — |
| 10. Diagnostic atomes orphelins | ✅ valide | Sera intégré dans l'UI admin en v0.14 |
| 11. Suivi de classe | ✅ valide | — |
| 12. Pièges et résolutions | ⚠ à enrichir | Ajouter pièges courants liés aux nouveaux ateliers (carte, évaluation, référentiel) et à l'éditeur LaTeX |

**Nouveaux scénarios à ajouter** :
- Rédaction d'une carte d'automatisme
- Construction d'une évaluation
- Navigation dans le tableau de bord d'un référentiel
- Création d'un livret annuel des plans de travail
- Compilation d'un document du catalogue publiable
- Utilisation de l'éditeur LaTeX (wrapping de sélection, générateurs,
  navigateur d'images)
- Diagnostic après un import : que faire si le compteur de l'environnement
  `seqQcm` n'est pas tiré (cas réel rencontré en v0.13.7.2.2/.3)

---

## Conclusion

Les **principes pédagogiques et le socle technique** définis en v0.10.7
restent **largement valides**. Les évolutions s'accumulent sur :

1. **L'élargissement du périmètre fonctionnel** (cartes d'automatisme,
   évaluations, plans de travail, catalogue de documents publiables)
2. **L'enrichissement de la rédaction LaTeX** (éditeur intégré,
   générateurs, navigateur d'images)
3. **Le polissage architectural** (refonte OO des ateliers,
   harmonisation des contrats backend, factorisation des routes)
4. **L'outillage de livraison** (CONVENTIONS, GOTCHAS, MANIFEST.md5)

La **refonte des 3 docs principales** demanderait probablement 2-3
journées de travail dédié et devrait être faite en une fois (pour
éviter qu'elles redéviennent obsolètes par incréments). Cette synthèse
sert d'inventaire des changements à intégrer le moment venu.
