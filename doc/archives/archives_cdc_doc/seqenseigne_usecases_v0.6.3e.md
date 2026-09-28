# seqenseigne — Cas d'usage

**Version 0.6.3e — avril 2026 · Laurent Coste**

---

Ce document décrit les cas d'usage de seqenseigne organisés en trois parties :

- **Partie 1 — Suivi de classe** (implémentée, chantier Progression annuelle finalisé en v0.6.3c).
- **Partie 2 — Conception des atomes pédagogiques** (en cours : socle BDD finalisé en v0.6.3e, ateliers opérationnels).
- **Partie 3 — Conception de livrets et progressions** (à venir).

| Identifiant | Titre                                           | Partie                           |
|-------------|-------------------------------------------------|----------------------------------|
| UC-S01      | Créer une classe                                | 1 — Suivi de classe              |
| UC-S02      | Importer une liste d'élèves (Pronote)           | 1 — Suivi de classe              |
| UC-S03      | Saisir les résultats d'une séquence             | 1 — Suivi de classe              |
| UC-S04      | Consulter la progression d'un élève             | 1 — Suivi de classe              |
| UC-S05      | Déclarer une version de livret                  | 1 — Suivi de classe              |
| UC-S06      | Exporter les données                            | 1 — Suivi de classe              |
| UC-S07      | Valider un établissement via UAI                | 1 — Suivi de classe (v0.6.3b)    |
| UC-S08      | Fusionner deux établissements doublons          | 1 — Suivi de classe (v0.6.3b)    |
| UC-S09      | Organiser la progression annuelle               | 1 — Suivi de classe (v0.6.3c)    |
| UC-D01      | Importer la référence LaTeX                     | 2 — Socle BDD (v0.6.3e)          |
| UC-A01      | Créer ou modifier une notion                    | 2 — Atomes pédagogiques          |
| UC-A02      | Créer ou modifier une méthode                   | 2 — Atomes pédagogiques          |
| UC-A03      | Définir les critères d'évaluation d'un objectif | 2 — Atomes pédagogiques          |
| UC-A04      | Créer ou modifier un exercice                   | 2 — Atomes pédagogiques          |
| UC-A05      | Tester les variables paramétrées d'un exercice  | 2 — Atomes pédagogiques          |
| UC-A06      | Parcourir les atomes dans un atelier            | 2 — Atomes pédagogiques (v0.6.3e)|
| UC-T01      | Gérer les thèmes d'un cycle                     | 2 — Référentiels (v0.6.3e)       |
| UC-T02      | Gérer les séquences d'un cycle                  | 2 — Référentiels (v0.6.3e)       |
| UC-T03      | Éditer une séquence pour un niveau              | 2 — Référentiels (v0.6.3e)       |
| UC-L01      | Assembler un livret de séquence                 | 3 — Livrets (à venir)            |
| UC-L02      | Générer le PDF d'un livret                      | 3 — Livrets (à venir)            |
| UC-P01      | Définir la progression annuelle (LaTeX)         | 3 — Progressions (à venir)       |

---

## Partie 1 — Suivi de classe

### UC-S01 — Créer une classe

| UC-S01 — Créer une classe |  |
|---------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Début d'année scolaire ou accueil d'une nouvelle classe |
| Précondition  | Aucune (l'établissement peut être créé à la volée) |
| Résultat      | Classe créée dans la base ; si l'établissement n'existe pas, il est ajouté avec l'état `propose` |

**Flux principal :**

1. Suivi de classe → Gestion des classes → « + Nouvelle »
2. Renseigner : nom, niveau (N09–N12), année scolaire, établissement
3. Valider → la classe apparaît dans la liste

> **⚑** Si l'établissement est nouveau, un bandeau d'alerte invite à le compléter depuis le sous-onglet Établissements.

### UC-S02 — Importer une liste d'élèves (Pronote)

| UC-S02 — Importer une liste d'élèves |  |
|---------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Export CSV Pronote disponible |
| Précondition  | Classe créée (UC-S01) |
| Résultat      | Élèves ajoutés, triés alphabétiquement |

**Flux principal :**

1. Sélectionner la classe → « Importer depuis Pronote (CSV) »
2. Choisir le fichier CSV
3. L'appli lit les colonnes `Nom` et `Prenom`, ignore les doublons

> **⚑** Format CSV attendu : export Pronote standard, colonnes `Nom` et `Prenom`, encodage UTF-8 avec BOM.

### UC-S03 — Saisir les résultats d'une séquence

| UC-S03 — Saisir les résultats d'une séquence |  |
|----------------------------------------------|--|
| Acteur        | Enseignant (après correction des travaux) |
| Déclencheur   | Fin d'une séquence évaluée |
| Précondition  | Classe avec élèves, version de livret active sur la séquence |
| Résultat      | Niveaux écrits en base ; verrouillage automatique du référentiel ET de la progression de la classe |

**Flux principal :**

1. Suivi de classe → Suivi des séquences → choisir la classe → choisir la séquence
2. Vue classe : tableau élèves × objectifs
3. Déplier un objectif (clic sur son en-tête) → les cases d'exercices apparaissent
4. Cocher les exercices réussis (F fondamental / A avancé / E exploration)
5. L'objectif 01 (cours) a 3 cases : notes cahier (F) / fiches résumé (A) / oral prof (E)
6. Clic « Calculer les niveaux » → confirmation → niveaux I/F/A/E calculés automatiquement
7. Ajustement manuel possible via le sélecteur de niveau par objectif

**Règle de déduction automatique :**

- Tous F réussis → niveau F
- Tous F + tous A réussis → niveau A
- Tous F + tous A + tous E réussis → niveau E
- Sinon → niveau I
- Aucun exercice déclaré → NE (Non évalué)

> **⚑** Note équivalente : I=4 pts, F=10 pts, A=16 pts, E=20 pts — moyenne sur tous les objectifs.

> **⚑** Verrouillage auto (v0.6.3c) : dès qu'un niveau est saisi, la progression de la classe passe à l'état `verrouille`. Les créneaux ne sont plus modifiables. Voir UC-S09.

### UC-S04 — Consulter la progression d'un élève

| UC-S04 — Consulter la progression d'un élève |  |
|----------------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Besoin de bilan individuel ou préparation d'entretien |
| Précondition  | Données de suivi saisies pour au moins une séquence |
| Résultat      | Vue complète des niveaux par objectif et par séquence |

**Flux principal :**

1. Suivi des séquences → vue Élève → sélectionner l'élève
2. Toutes les séquences s'affichent avec les niveaux par objectif et la note

### UC-S05 — Déclarer une version de livret

| UC-S05 — Déclarer une version de livret |  |
|------------------------------------------|--|
| Acteur        | Enseignant (avant distribution du livret imprimé) |
| Déclencheur   | Livret finalisé et prêt à distribuer |
| Précondition  | Fichier YAML de la séquence à jour |
| Résultat      | Snapshot en base, lien dans la classe |

**Flux principal :**

1. Livrets → choisir niveau + séquence
2. Renseigner le tag (ex. `2025-09-01`) et une description
3. « Créer le snapshot » → l'appli capture l'état courant des objectifs et exercices
4. Affecter la version à une ou plusieurs classes

> **⚑** Verrouillage : dès qu'un exercice est coché ou un niveau saisi pour une classe × séquence, la version se verrouille. Il n'est plus possible de changer de version active.

### UC-S06 — Exporter les données

| UC-S06 — Exporter les données |  |
|-------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Besoin de sauvegarde ou transfert |
| Précondition  | Données existantes |
| Résultat      | Fichier JSON téléchargé |

**Flux principal :**

1. Bouton « Exporter » (header)
2. Si une classe est sélectionnée : export de cette classe uniquement
3. Sinon : export global (toutes classes + suivi + niveaux)

### UC-S07 — Valider un établissement via UAI (v0.6.3b)

| UC-S07 — Valider un établissement via UAI |  |
|--------------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Besoin de fiabiliser les données d'établissement (académie, ville, adresse) |
| Précondition  | Établissement en état `propose` ; code UAI connu (ex: `0351234A`) |
| Résultat      | Établissement passé en état `valide` avec champs remplis depuis l'annuaire EN |

**Flux principal :**

1. Suivi de classe → Gestion des classes → sous-onglet Établissements
2. Cliquer « Valider avec UAI » sur la carte de l'établissement
3. Saisir le code UAI (8 caractères)
4. L'appli interroge fr-en-annuaire-education, remplit nom/académie/ville/adresse et bascule l'état à `valide`

**Flux alternatif — doublon détecté :**

- Si l'annuaire remonte un nom déjà porté par un autre établissement en base (typique : "Collège des Hautes Ourmes" validé → annuaire dit "Collège Les Hautes Ourmes" → conflit)
- L'API renvoie 409 avec `code=doublon_detecte` et `etab_cible_id`
- L'UI bascule automatiquement sur la proposition de fusion (UC-S08)

> **⚑** Seul prérequis métier : l'académie est nécessaire pour que le calendrier scolaire fonctionne (UC-S09). La validation UAI la remplit automatiquement, mais elle peut aussi être saisie à la main via « Modifier ».

### UC-S08 — Fusionner deux établissements doublons (v0.6.3b)

| UC-S08 — Fusionner deux établissements doublons |  |
|--------------------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Deux établissements représentent la même entité (coquille de saisie typiquement) |
| Précondition  | La source ne doit pas être en état `valide` (pour ne pas perdre de donnée officielle) |
| Résultat      | Classes et progressions de source migrées vers cible ; source supprimée |

**Flux principal :**

1. Gestion des classes → Établissements → cliquer « Fusionner avec… » sur l'établissement à supprimer
2. Choisir la cible dans la liste déroulante
3. Confirmer → migration atomique (classes + progressions) puis suppression de la source
4. Alerte de succès : « N classe(s) migrée(s), M progression(s) »

**Refus possibles (409) :**

- `code=source_validee` — Interdit de supprimer un établissement déjà validé. L'enseignant doit inverser le sens de la fusion.
- `code=conflit_progression` — Source ET cible ont une progression pour la même `(niveau, annee)`. L'enseignant doit supprimer l'une des deux avant de réessayer.

> **⚑** Pas besoin de l'UAI pour fusionner. Le bouton « Fusionner avec… » est disponible sur tous les établissements, dès qu'il en existe au moins 2.

### UC-S09 — Organiser la progression annuelle (v0.6.3c)

| UC-S09 — Organiser la progression annuelle |  |
|---------------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Préparation de l'année scolaire ou ajustement en cours d'année |
| Précondition  | Au moins une classe créée avec un établissement dont l'académie est renseignée |
| Résultat      | Progression avec créneaux placés sur le calendrier semainier, vacances et jours fériés affichés, état suivi (`en_cours` / `valide` / `verrouille`) |

**Flux principal :**

1. Suivi de classe → Progression annuelle
2. Choisir un niveau puis une progression dans le sélecteur
3. Le panneau gauche affiche le calendrier semainier de septembre à août, avec les vacances en rouge et les jours fériés en badges orange
4. Ajouter un créneau via le formulaire à droite : séquence → rangs → livret → dates → période
5. Les créneaux apparaissent en bleu sur la grille, posés sur les semaines correspondantes
6. Badge d'état en haut du panneau : ✏️ En cours / ✓ Validée / 🔒 Verrouillée

**Flux alternatif — académie manquante :**

- Le calendrier est remplacé par un message « Calendrier indisponible sans académie »
- Bandeau d'alerte avec bouton « Aller à la gestion des établissements »
- Tous les contrôles d'édition sont grisés (opacity 0.4, pointer-events none)

**Transitions d'état :**

- `en_cours` → `valide` : bouton « Marquer valide » (manuel)
- `valide` → `en_cours` : bouton « Remettre en cours » (manuel)
- `en_cours` | `valide` → `verrouille` : automatique dès qu'une évaluation est saisie (UC-S03). Non réversible en v0.6.3e.

> **⚑** Vacances scolaires : Toussaint, Noël, Hiver, Printemps viennent de data.education.gouv.fr. Vacances d'été et pont de l'Ascension sont complétés depuis des tables officielles embarquées (arrêtés du Ministère).

> **⚑** Semaines de classe : le calendrier teste le chevauchement sur lundi-vendredi uniquement. Une vacance qui ne touche qu'un samedi ou un dimanche ne colore pas la semaine adjacente.

> **⚑** Dates affichées en heure locale Paris (conversion UTC+2 appliquée côté backend sur les dates de l'API Éducation nationale).

---

## Partie 2 — Conception des atomes pédagogiques

Un atome pédagogique est une unité autonome de contenu : notion, méthode ou exercice. Les atomes sont créés indépendamment de toute séquence. Leur affectation à une séquence (avec numérotation) se fait dans l'atelier Livret.

### UC-D01 — Importer la référence LaTeX (v0.6.3e)

| UC-D01 — Importer la référence LaTeX |  |
|---------------------------------------|--|
| Acteur        | Enseignant (administrateur de sa propre instance) |
| Déclencheur   | Sources LaTeX modifiées ; souhait de synchroniser la BDD |
| Précondition  | Chemin des sources connu (typiquement `D:\Enseignement\seqenseigne\reference\sequences`) |
| Résultat      | Atomes (notions, méthodes, exercices, livrets) et tables v2 peuplés pour les 3 niveaux |

**Flux principal :**

1. Admin → Base de données → **Vider la référence**
   - Préserve le suivi, les classes, les référentiels stables (cycles, thèmes, referentiel_*)
   - Vide les atomes et les tables v2 dans le bon ordre FK
2. Admin → Import référence → saisir le chemin des sources → « Scanner »
   - L'aperçu affiche le nombre d'atomes trouvés par niveau
3. Cliquer « Importer »
   - Les 3 niveaux sont scannés **séquentiellement** (pas en parallèle)
   - Pour chaque niveau : résolution des macros nommantes depuis les CSV, persistance des atomes, peuplement v2
   - Le rapport affiche les atomes importés et les éventuels incidents de macros non résolues

**Étapes internes par niveau :**

1. Résolution des titres de notions/méthodes depuis `C0X_connaissances.csv` / `C0X_objectifs.csv`
2. `ecrire_notions` (dédup par `fichier`)
3. `ecrire_objectifs()` — rehydrate `objectifs` depuis `referentiel_objectifs`
4. `ecrire_methodes` (pose `methode_id` sur les objectifs)
5. `ecrire_exercices` (diff-based, résout les `objectifs_codes` en liaisons)
6. `ecrire_livrets_importes`
7. `peupler_v2_depuis_base(niveau)` — crée `sequences_par_niveau`, `sequence_parties`, `objectifs_v2`, `objectif_exos`

> **⚑** **Scans séquentiels** : les 3 niveaux sont traités l'un après l'autre (boucle `for ... of` côté JS), jamais en parallèle. Un `Promise.all` provoquait des `IntegrityError` FK sur `exercices` / `objectif_exos`.

> **⚑** **Idempotence** : relancer un import sans rien changer est inoffensif — les atomes sont reconnus par leur champ `fichier`, leurs IDs sont préservés, et les liaisons v2 des autres niveaux ne sont pas invalidées.

> **⚑** **Incidents macros** : la carte d'alerte en bas de la page affiche les macros non résolues (fichier + champ + macro + raison). Un zéro ou quasi-zéro est attendu après `nettoyage_6` qui a introduit les CSV de référence pour les connaissances et objectifs.

### UC-A01 — Créer ou modifier une notion

| UC-A01 — Créer ou modifier une notion |  |
|----------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Nouveau concept à enseigner, ou révision d'une notion existante |
| Précondition  | Aucune — une notion est autonome |
| Résultat      | Entrée créée ou mise à jour dans `connaissances.csv` |

**Flux principal :**

1. Atelier Notions → sélectionner une notion existante ou « + Nouvelle »
2. Saisir le titre (court, autonome, sans référence à une séquence)
3. Saisir le corps (définition principale, LaTeX libre)
4. Ajouter des exemples via « + Ajouter un exemple » (LaTeX libre par item)
5. Ajouter des remarques via « + Ajouter une remarque »
6. Permuter les sections Exemples / Remarques si besoin (bouton ⇅)
7. Onglet « LaTeX généré » pour vérifier le rendu du `\begin{seqNotion}...\end{seqNotion}`
8. Enregistrer → mise à jour dans `connaissances.csv`

> **⚑** Le titre doit être compréhensible hors contexte (ex: « Proportion. » et non « La notion de proportion »). Le numéro d'ordre dans la séquence est attribué lors de l'affectation dans l'atelier Livret.

### UC-A02 — Créer ou modifier une méthode

| UC-A02 — Créer ou modifier une méthode |  |
|-----------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Nouveau savoir-faire à enseigner, ou révision |
| Précondition  | Les notions associées doivent exister dans le catalogue (UC-A01) |
| Résultat      | `methodes.csv` mis à jour ; critères disponibles pour le tableau d'objectifs |

**Flux — onglet Édition :**

1. Atelier Méthodes → sélectionner une méthode ou « + Nouvelle »
2. Saisir le titre (intitulé du savoir-faire — deviendra l'intitulé de l'objectif)
3. Saisir le corps, les exemples et les remarques (même structure que la Notion)

**Flux — onglet Objectif / critères :**

4. Indiquer si l'objectif est « fin de cycle » selon le programme officiel (toggle O/N)
5. Associer 0, 1 ou plusieurs notions depuis le catalogue
6. Rédiger les critères d'atteinte pour chaque niveau F (10 pts) / A (16 pts) / E (20 pts)
7. Niveau I (4 pts, « pas de travail évaluable ») fixe et identique pour tous
8. Onglet « LaTeX généré » → vérifier le `\begin{seqMethode}`

> **⚑** Fin de cycle : propriété de l'objectif définie par le programme officiel, indépendante de la séquence ou du niveau où la méthode est traitée. Badge FC affiché dans la sidebar de l'atelier.

### UC-A03 — Définir les critères d'évaluation d'un objectif

| UC-A03 — Définir les critères d'évaluation |  |
|---------------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Préparation de l'évaluation d'une séquence |
| Précondition  | Méthode créée (UC-A02) |
| Résultat      | Critères F/A/E disponibles pour le tableau d'objectifs et la grille de suivi |

Les critères d'évaluation sont définis dans l'onglet « Objectif / critères » de l'atelier Méthode (UC-A02, étapes 4–7). Ce cas d'usage est listé séparément car il répond à un besoin distinct : l'enseignant peut avoir besoin de réviser les critères sans modifier le contenu de la méthode.

**Barème fixe (identique pour tous les objectifs) :**

| Niveau            | Points /20 | Critère                                          |
|-------------------|------------|--------------------------------------------------|
| I — Insuffisant   | 4          | Pas de travail évaluable fourni (fixe)           |
| F — Fondamental   | 10         | Spécifique à chaque objectif — à rédiger         |
| A — Satisfaisant  | 16         | Spécifique à chaque objectif — à rédiger         |
| E — Excellent     | 20         | Spécifique à chaque objectif — à rédiger         |

### UC-A04 — Créer ou modifier un exercice

| UC-A04 — Créer ou modifier un exercice |  |
|-----------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Besoin d'un exercice nouveau pour une série F, A ou E |
| Précondition  | Les objectifs associés doivent exister (UC-A02) |
| Résultat      | Fichier `.tex` de l'exercice créé ou mis à jour, variables dans `_param.tex` |

**Flux principal :**

1. Atelier Exercices → « + Nouvel exercice »
2. Choisir la série : F (10 pts) / A (16 pts) / E (20 pts)
3. Associer 1 ou plusieurs objectifs
4. Zone Variables : saisir le bloc `_param.tex` (expressions xintexpr)
5. Tester les variables via « Tester » (UC-A05)
6. Saisir l'énoncé en LaTeX libre (variables référencées par `\xintiieval{NOM}`)
7. Saisir le corrigé en LaTeX libre (toujours présent)
8. Prévisualisation HTML en temps réel (tikz → placeholder si figure complexe)
9. Onglet « LaTeX généré » → vérifier le `\begin{seqExercice}...\end{seqExercice}`

> **⚑** Le corrigé est obligatoire : il est utilisé dans le document annuel « exercices corrigés ».

> **⚑** Les figures tikz/tkz-euclide ne sont pas prévisualisables en temps réel : un bouton « Compiler » déclenche une compilation PDF du fragment.

### UC-A05 — Tester les variables paramétrées d'un exercice

| UC-A05 — Tester les variables paramétrées |  |
|--------------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Vérification que les expressions aléatoires produisent des nombres cohérents |
| Précondition  | Zone Variables remplie dans l'atelier Exercice (UC-A04) |
| Résultat      | N tirages affichés côte à côte avec les valeurs de chaque variable |

**Flux principal :**

1. Dans l'atelier Exercice, zone Variables → clic sur « Tester » (N = 5 par défaut)
2. POST `/api/param/tester` → serveur Python évalue les xintexpr
3. N jeux de valeurs indépendants s'affichent côte à côte
4. L'enseignant vérifie la cohérence (pas de division par zéro, entiers si attendus, etc.)
5. Si un tirage produit une erreur, le message d'erreur s'affiche dans la colonne concernée

**Syntaxes xintexpr supportées :**

| Syntaxe LaTeX                               | Comportement                                            |
|---------------------------------------------|---------------------------------------------------------|
| `\xintdefiivar NOM := EXPR;`                | Variable entière — arrondie à l'entier le plus proche   |
| `\xintdeffloatvar NOM := EXPR;`             | Variable flottante — arrondie à 4 décimales             |
| `\xintdefvar NOM := EXPR;`                  | Type automatique                                         |
| `randrange(a,b)`                            | Entier aléatoire dans `[a, b[` — re-tiré à chaque tirage |
| `(COND)?{VRAI}{FAUX}`                       | Ternaire xint — condition évaluée, branche choisie et évaluée |
| `\ifnumequal{A}{B}{OUI}{NON}`               | Conditionnel entier                                      |
| `\newcommand\NOM{}`                         | Commande LaTeX — stockée en texte, non évaluée numériquement |

### UC-A06 — Parcourir les atomes dans un atelier (v0.6.3e)

| UC-A06 — Parcourir les atomes |  |
|-------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Recherche rapide d'un atome pour édition ou référence |
| Précondition  | Au moins un import de référence effectué (UC-D01) |
| Résultat      | Atome localisé et ouvert dans l'éditeur central |

**Flux principal :**

1. Ouvrir l'atelier concerné (Notion, Méthode, ou Exercice)
2. La sidebar liste tous les atomes du catalogue
3. Chaque item affiche :
   - **Identification** : format compact `N11/S01/F01` (exercice), `N11/S01/C01` (notion), `N11/S01/O02` (méthode)
   - **Titre** : champ `nom` (exercice) ou `titre` (notion/méthode)
   - **Badge FC** pour les méthodes marquées « fin de cycle »
   - **Badge de série** (F / A / E / AE) pour les exercices
4. Filtrer la liste via la barre de filtres (niveau, séquence, et série pour les exercices)
5. Survoler un item → fond ombré
6. Cliquer → ouvre l'atome dans l'éditeur central, item surligné (état actif)

> **⚑** Si un atome n'a pas encore de titre, « (sans titre) » s'affiche en italique gris — plus de fallback sur le début de l'énoncé ou du corps.

> **⚑** Le hover ombré est cohérent dans tous les ateliers : Notion, Méthode, Exercice, Thèmes (cycle), Séquences de cycle, Séquence (niveau). Classe CSS unifiée `.atl-item`.

---

## Partie 2 — Référentiels et structure (v0.6.3e)

### UC-T01 — Gérer les thèmes d'un cycle

| UC-T01 — Gérer les thèmes d'un cycle |  |
|---------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Création ou ajustement des thèmes du programme |
| Précondition  | Cycle C03 ou C04 configuré |
| Résultat      | Thèmes persistés dans `C0X_themes.csv` et en base, utilisés pour colorer les séquences et pastilles |

**Flux principal :**

1. Atelier Thèmes → choisir un cycle (C03 ou C04)
2. Liste des thèmes existants avec pastille colorée et nombre de séquences associées
3. « + Nouveau thème » : code, nom, couleur (famille), description
4. Sélectionner un thème pour l'éditer ou le supprimer
5. Les thèmes avec séquences associées ne peuvent pas être supprimés sans réaffectation

### UC-T02 — Gérer les séquences d'un cycle

| UC-T02 — Gérer les séquences d'un cycle |  |
|------------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Création ou ajustement des séquences du programme |
| Précondition  | Thèmes du cycle existants (UC-T01) |
| Résultat      | Séquences persistées dans `C0X_sequences.csv` et en base |

**Flux principal :**

1. Atelier Séquences de cycle → choisir un cycle
2. Liste des séquences : pastille du thème + code + nom + nombre d'atomes
3. « + Nouvelle séquence » : code, nom, thème (pastille colorée automatique)
4. Éditer pour modifier ou réaffecter à un autre thème
5. Supprimer possible uniquement si aucun atome n'y est rattaché

### UC-T03 — Éditer une séquence pour un niveau

| UC-T03 — Éditer une séquence pour un niveau |  |
|----------------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Organisation des parties, objectifs et liaisons d'une séquence pour un niveau donné |
| Précondition  | Import de référence effectué (UC-D01) |
| Résultat      | Structure de la séquence (parties, objectifs, liaisons méthodes/exercices) visible et navigable |

**Flux principal :**

1. Atelier Séquence (niveau) → choisir un niveau (N10, N11, N12)
2. Choisir une séquence dans le sélecteur
3. Le panneau affiche les parties de la séquence :
   - Partie 1 : objectifs 01 à 09 (premier chiffre = 0)
   - Partie 2 : objectifs 11 à 19 (premier chiffre = 1)
   - Partie 3 : objectifs 21 à 29 (premier chiffre = 2)
4. Chaque objectif est affiché avec :
   - Son code et nom
   - La méthode associée (lien vers l'atelier Méthode)
   - Les exercices F/A/E liés (séries)

> **⚑** Si l'atelier affiche « N11 / S01 n'est pas peuplé dans le modèle v2 », relancer un import de référence depuis l'admin (UC-D01). Cela rehydrate `objectifs` depuis `referentiel_objectifs` et repeuple la chaîne v2. (Ce bug historique a été corrigé en v0.6.3e via l'appel automatique à `ecrire_objectifs()` dans `scanner_vers_bdd`.)

---

## Partie 3 — Livrets et progressions (à venir)

Les cas d'usage de la Partie 3 sont définis à titre prévisionnel. Leur implémentation interviendra après la finalisation de la Partie 2.

### UC-L01 — Assembler un livret de séquence

| UC-L01 — Assembler un livret de séquence |  |
|-------------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Préparation d'une nouvelle séquence |
| Précondition  | Notions, méthodes et exercices créés (UC-A01 à UC-A04) |
| Résultat      | Fichier `N1X_S01_Livret.tex` généré, YAML mis à jour |

**Flux prévu :**

1. Atelier Livret → choisir niveau + séquence
2. Affecter les notions dans l'ordre (numérotation auto 01, 02…)
3. Affecter les méthodes dans l'ordre → objectifs créés automatiquement
4. Affecter les exercices par objectif et par série (F / A / E)
5. Configurer les révisions (exercices hérités du niveau N-1)
6. Prévisualiser → Valider → génération du `.tex` et mise à jour du YAML

### UC-L02 — Générer le PDF d'un livret

| UC-L02 — Générer le PDF d'un livret |  |
|--------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Livret assemblé, prêt à distribuer |
| Précondition  | UC-L01 terminé, MiKTeX portable disponible |
| Résultat      | PDF du livret généré, lien de téléchargement disponible dans l'appli |

**Flux prévu :**

1. Atelier Livret → bouton « Compiler »
2. L'appli lance `pdflatex` (3 passes) via le `Makefile.win`
3. Format précompilé `.fmt` géométrie utilisé si des figures tikz sont présentes
4. PDF disponible en téléchargement ; erreurs de compilation affichées dans l'appli

### UC-P01 — Définir la progression annuelle (LaTeX)

| UC-P01 — Définir la progression annuelle |  |
|-------------------------------------------|--|
| Acteur        | Enseignant |
| Déclencheur   | Début d'année scolaire ou révision |
| Précondition  | Livrets des 14 séquences du niveau disponibles ; progression organisée via UC-S09 |
| Résultat      | Plan de travail annuel LaTeX généré (`N1X_Plan_de_travail.tex`) |

**Flux prévu :**

1. Depuis le calendrier visuel de UC-S09, bouton « Générer plan de travail LaTeX »
2. L'appli produit un `.tex` qui combine le tableau de progression (séquences × dates) et les plans de travail par créneau
3. `\seqBoiteTitrePlan` + `\seqPlanReperesNiveaux` + `\seqPlanObjectif` par objectif
4. Téléchargement du `.tex`, compilation via UC-L02

> **⚑** UC-S09 (implémenté en v0.6.3c) prépare le terrain : les créneaux et leurs dates sont déjà en base, il reste à les sérialiser en LaTeX.
