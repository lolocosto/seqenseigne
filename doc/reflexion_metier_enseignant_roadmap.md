# Le métier d'enseignant : synthèse et pistes fonctionnelles pour seqenseigne

Document de réflexion (non technique). Objectif : partir du métier réel
d'enseignant (surtout maths collège, mais pas seulement) pour identifier des
fonctionnalités pertinentes à ajouter dans **Conception de référentiel** et
**Suivi de classe**, et en tirer une roadmap.

Trois angles ont été explorés : (1) ce que l'institution attend, (2) ce que les
enseignants disent de leur quotidien, (3) ce que proposent les logiciels
existants. Chaque angle est résumé, puis croisé avec ce que seqenseigne fait
déjà, pour dégager des pistes.

---

## 1. Ce que l'institution attend

Le **référentiel des compétences professionnelles** (BO du 25 juillet 2013,
14 compétences communes + compétences spécifiques) structure le métier autour
de grands blocs :

- **Maîtriser les savoirs disciplinaires** et leur didactique.
- **Construire, mettre en œuvre et animer** des situations d'enseignement tenant
  compte de la diversité des élèves.
- **Organiser et assurer un mode de fonctionnement du groupe** favorisant
  l'apprentissage.
- **Évaluer les progrès et les acquisitions** des élèves (évaluation formative
  et sommative, positionnement par rapport aux attendus).
- **Coopérer** au sein d'une équipe, avec les parents, les partenaires.
- **S'engager dans une démarche de développement professionnel** (analyse de sa
  pratique).

Points saillants pour un logiciel :
- l'**évaluation par compétences** est institutionnalisée (LSU au collège :
  positionnement par domaines/composantes du socle) ;
- la **traçabilité** est exigée dans le second degré (cahier de textes,
  contenus, travail donné — visés par le chef d'établissement) ;
- les **évaluations nationales** (début d'année, désormais tous niveaux) doivent
  être exploitées pour adapter la progression.

## 2. Ce que les enseignants disent de leur quotidien

Le métier déborde très largement les heures devant élèves. Sur ~41 h
hebdomadaires déclarées, environ la moitié seulement est de l'enseignement
direct ; le reste est le **« travail invisible »** :

- **Préparation** (le poste le plus lourd et le plus « compressible ») :
  concevoir des séquences progressives, préparer supports, exercices, matériel,
  transitions ; équilibrer les rythmes sur la semaine.
- **Correction** : non pas seulement noter juste/faux, mais **identifier les
  erreurs, comprendre les difficultés, décider de la suite**. Volume
  largement incompressible.
- **Suivi des élèves** : analyse des résultats, différenciation (élèves DYS,
  allophones, rythmes différents), remédiation, adaptation sans renoncer aux
  objectifs communs.
- **Administratif et coordination** : documents institutionnels, réunions,
  relations familles, bulletins.

Besoins récurrents exprimés :
- **garder une trace de ce qui a réellement été fait** (pour les élèves/familles,
  pour l'institution, pour soi au moment des bilans) ;
- **avoir un canevas de semaine** cohérent (où je pars lundi, où j'arrive
  vendredi) pour ne pas se laisser absorber par les urgences ;
- **mutualiser** entre collègues (drive commun de fiches, séquences partagées) ;
- **gagner du temps sur la préparation** (banques d'exercices, générateurs,
  différenciation facilitée).

## 3. Ce que proposent les logiciels existants

**Pronote / ENT** (gestion de vie scolaire, ~75 % des collèges/lycées) :
- cahier de textes (contenu + travail à faire, reportable dans le parcours) ;
- **notes ET compétences** (alimente le LSU), relevés, bulletins, graphes ;
- vie scolaire (absences, retards, sanctions) ;
- QCM auto-corrigés, ressources jointes ;
- communication (familles, discussions, sondages), rencontres parents-profs ;
- emploi du temps temps réel ; tableau de bord « à la Pronote » (indicateurs).

**SIECLE** (ministère) : cahier de textes, évaluation, vie scolaire ; **LSU**
(positionnement compétences). **Pix** (compétences numériques). **SACoche,
Edumoov, Nota Bene** : suivi par compétences.

**Outils orientés préparation/conception** (le cœur de seqenseigne) :
- **banques d'exercices classés par compétences/domaines**, générateurs
  d'exercices pour la différenciation (Magnard, Édulib, LaboMEP) ;
- **fiches personnalisables** (évaluation, remédiation, différenciation,
  corrigés, « je retiens » adaptés DYS) ;
- **outils de progression par glisser-déposer** (objectifs du programme → blocs
  de séquences ; export PDF ; exemples partagés) — très proche de ce que fait
  déjà seqenseigne pour la progression ;
- **plans de travail** (classe inversée, autonomie, auto-évaluation).

---

## 4. Ce que seqenseigne couvre déjà

- **Conception** : référentiels (internes LaTeX + externes), atomes (notions,
  méthodes, exercices, cartes, fiches), séquences, livrets, plans de travail,
  cartes d'automatisme (Leitner), rendu PDF.
- **Progression** : principale (par semaine) et MER (à la séance), par niveau,
  décalages par classe.
- **Suivi** : EdT, indisponibilités, projection des séances, panachage MER,
  saisie de résultats d'évaluation, tableau de bord naissant.

seqenseigne est donc fort sur la **préparation/conception** (le poste le plus
lourd et le plus compressible) et la **planification** — exactement là où le
besoin enseignant est le plus grand. C'est un positionnement pertinent.

---

## 5. Pistes de fonctionnalités (croisement besoins × existant)

### Côté Conception de référentiel

- **P1. Couverture des compétences / du programme** : visualiser quels
  objectifs du programme (attendus officiels) sont couverts par les
  séquences/atomes existants, et lesquels manquent. Réponds au besoin
  institutionnel (attendus) et au besoin enseignant (ne rien oublier).
- **P2. Différenciation** : marquer des atomes/exercices par niveau de
  difficulté ou public (DYS, approfondissement, remédiation), pour générer des
  variantes de fiches. Besoin fort et récurrent.
- **P3. Banque d'exercices requêtable** : rechercher/filtrer les atomes par
  compétence, domaine, difficulté, type — pour composer vite une fiche ou une
  évaluation.
- **P4. Mutualisation** : import/export de séquences ou d'atomes entre
  collègues (au-delà des référentiels externes déjà en place). À relier au futur
  multi-utilisateur.
- **P5. Réutilisation dans l'évaluation** : composer une évaluation à partir
  d'exercices existants (lien conception → évaluation).

### Côté Suivi de classe

- **P6. Cahier de textes / trace du réalisé** : noter ce qui a été fait à chaque
  séance (contenu + travail donné). Répond à un besoin institutionnel
  (traçabilité) ET enseignant (bilan, mémoire). Complète la progression prévue
  par la progression **réalisée**.
- **P7. Évaluation par compétences** : au-delà des notes, positionner les
  élèves par compétence/objectif (à la LSU). Gros chantier, mais central dans
  l'institution.
- **P8. Analyse des résultats / repérage** : à partir des résultats saisis,
  repérer les élèves ou notions en difficulté (tableaux de synthèse, alertes)
  pour décider de la remédiation. Transforme la saisie en aide à la décision.
- **P9. Exploitation des évaluations nationales** : importer/saisir les
  résultats des évaluations nationales et les croiser avec la progression.
- **P10. Canevas de semaine enrichi** : le tableau de bord « séances de la
  semaine » enrichi de ce qui est à préparer / à corriger (charge de la
  semaine), pour le « où je pars / où j'arrive ».

### Transverse

- **P11. Tableau de bord configurable** (déjà amorcé) : assembler les tuiles
  ci-dessus selon ses priorités.
- **P12. Communication familles / élèves** : hors périmètre actuel (Pronote le
  fait), à ne pas dupliquer sauf besoin précis.

---

## 6. Proposition de roadmap (à discuter)

Priorisation selon **impact sur le travail invisible** (préparation, correction,
suivi) et **cohérence avec le positionnement** de seqenseigne (conception +
planification), sans dupliquer ce que Pronote fait déjà bien (vie scolaire,
communication).

**Court terme (consolider le suivi et le tableau de bord)**
1. Finir les tuiles du tableau de bord : **éléments non rattachés** (P associée
   à la conception), **derniers résultats d'évaluation** (P8 amont).
2. **P6 — Trace du réalisé** (cahier de textes léger) : cocher/annoter ce qui a
   été fait par séance. Fort ratio valeur/effort, complète la progression.
3. **P8 — Analyse des résultats** : synthèses par classe/notion à partir des
   résultats déjà saisis. Réutilise l'existant.

**Moyen terme (renforcer la conception)**
4. **P1 — Couverture du programme** : indicateurs de complétude par rapport aux
   attendus.
5. **P3 — Banque d'exercices requêtable** + **P5 — composer une évaluation**.
6. **P2 — Différenciation** (marquage + variantes de fiches).

**Long terme (chantiers structurants)**
7. **P7 — Évaluation par compétences** (à la LSU).
8. **P4 — Mutualisation** (lié au multi-utilisateur déjà anticipé).
9. **P9 — Évaluations nationales**.

**Volontairement hors périmètre** (sauf besoin précis) : vie scolaire (absences,
sanctions), communication familles, bulletins officiels — bien couverts par
Pronote/ENT ; les dupliquer diluerait le positionnement.

---

## 7. Questions pour décider ensemble

- Le **positionnement** proposé (fort sur conception + planification + suivi
  pédagogique fin, en évitant la vie scolaire / communication déjà couvertes)
  te convient-il, ou veux-tu couvrir aussi ces zones ?
- Dans le court terme, l'ordre **tuiles → trace du réalisé (P6) → analyse des
  résultats (P8)** te semble-t-il le bon ?
- L'**évaluation par compétences (P7)** est un gros morceau très aligné avec
  l'institution : à viser à moyen ou long terme ?

---

## 8. Suivi de séance — retour terrain (collègue maths « bien processée »)

Deux outils papier complémentaires, utilisés en parallèle, **basés sur des
pictogrammes** (peu de texte à écrire — condition de faisabilité confirmée) :

### a) Fiche hebdo « suivi » (A4 portrait, une colonne par séance)
Orientée **traçabilité du réalisé et des manques**.
- Bandeau supérieur : documents distribués, évaluation faite, travail à
  faire / à rendre.
- Une colonne à gauche + une colonne par séance de la semaine.
- Une ligne par élève : absences (⇒ doc à redistribuer la séance suivante,
  éval à rattraper…), travail non fait / non rendu, etc.
C'est de la mémoire administrative et pédagogique (qui a manqué quoi, qui doit
quoi).

### b) Fiche « plan de classe » hebdo
Orientée **placement + attitude**.
- Élèves positionnés selon un besoin (à besoin, accompagné AESH, à séparer, à
  regrouper) ; les autres en placement libre.
- Notation d'attitude par pictogrammes, en positif (participation, aide à un
  autre élève…) et en négatif (place sale/mal rangée, perturbation…) ⇒ nourrit
  une note « attitude en séance ».

### Enseignements pour la conception
- **Deux vues distinctes** : une vue « liste élèves × séances » (suivi/manques)
  et une vue « plan de classe » (placement/attitude). Ne pas les fusionner.
- **Saisie par pictogrammes / gestes**, jamais du texte libre comme mode
  principal.
- Cadence **hebdomadaire par classe**.
- Le plan de classe porte à la fois des **attributs durables** (besoin, AESH, à
  séparer/regrouper, placement) et des **événements ponctuels** (attitude d'une
  séance).
- Débouchés concrets : liste des docs à redistribuer / évals à rattraper (issue
  des absences), note d'attitude (issue des pictos positifs/négatifs).
À cadrer précisément plus tard (modèle de données + ergonomie de saisie mobile).
