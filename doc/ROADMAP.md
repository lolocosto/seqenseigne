# Roadmap seqenseigne — chantiers en attente

Ce fichier suit les chantiers ouverts, mis en pause ou planifiés. Il complète
les notes `redemarrage_vX.md` (qui documentent chaque livraison faite).

## En pause — à reprendre

### Import des données historiques (classe par classe)

**Déjà importé** : 4e3 2021-22 (N11_v2021, v0.19.1.5), 5e2 2021-22 (N10_v2021,
v0.19.1.7), 5e2 2022-23 (N10_v2022, v0.19.1.9), 3e3 2022-23 (N12_v2022,
v0.19.1.10), 5e1 2023-24 (N10_v2023, v0.19.1.13).

**Vérifié / consolidé** : audit d'alignement + livrets (`verifier_referentiels`,
v0.19.1.8/.11) ; cohérence des états `verrouille → utilise`
(`coherence_etats_referentiels`, v0.19.1.12).

**À REPRENDRE ET FINIR — 4e3 2023-24 (N11_v2023)** : chantier interrompu. La
structure FIGÉE des objectifs de `N11_v2023` en base est **désynchronisée des
livrets PDF 2023-24** (numérotation et nombre d'objectifs différents sur ~12/14
séquences). Cause probable : déverrouillage manuel ayant re-lié la structure
figée au modèle vivant 2025. Rappel : deux structures parallèles indépendantes
(vivante en construction / figée verrouillée-utilisée) ; ici seule la figée de
`N11_v2023` est concernée. Décision en attente : restaurer depuis les PDF
(lourd + re-mapping du suivi élève, risqué) OU laisser tel quel et ne traiter
que parties/dates/séances/état. S07/S13 sans livret. **Rien codé pour cette
classe** — laissé en l'état sur décision de l'auteur.

**Livraison « modèle plan de travail par séquence »** (identifiée) : pour copier
les plans PDF par séquence/partie dans les référentiels figés, il faut un type
de document « plan par séquence » puis étendre `verifier_referentiels.py`.

Classes jumelles (4e4/4e6, 3e8/5e4) : inutiles (progressions partagées).

## Planifié / en cours — Progressions « à la séance »

Mises en route + automatismes (Leitner). Voir
`doc/cadrage_mises_en_route_automatismes.md`. Prioritaire.

La saisie de l'emploi du temps de l'enseignant s'est imposée comme socle : le
nombre de séances/semaine ne suffit pas, il faut connaître les créneaux réels.
Découpage réel des livraisons :

- **Livraison 1 (v0.19.1.15)** : modèle & préférences (rythme A/B par classe +
  types de mise en route extensibles). **Faite.**
- **Livraison 2 (v0.19.1.16)** : grille horaire par établissement (créneaux
  M1..M4 / S1..S4, défauts Hautes Ourmes). **Faite.**
- **Livraison 3 (v0.19.1.17)** : EDT de l'enseignant (`edt_creneaux` : quels
  créneaux M1..S4, quel jour, semaine A/B/AB, `usage`), comptage séances/semaine
  dérivé. **Faite.**
- **Livraison 4 (v0.19.1.18)** : projection séance→date+heure (EDT × calendrier
  vacances/fériés). **Faite.** Fonction pure `projection_seances.projeter` +
  route `/api/classes/<id>/projection`. Borne basse systématique au 1er
  septembre (les données officielles ne contiennent jamais les vacances d'été
  de début d'année scolaire). L'API remonte `vacances_absentes` +
  `avertissements` ; **l'affichage de cette alerte dans l'UI reste à faire**
  (quand l'interface des progressions sera construite).
- **Livraison 5 (v0.19.1.19)** : règle d'affectation des mises en route /
  automatismes aux séances. **Faite.** Deux modes par classe/année :
  `par_seance` (affectation case par case de l'EDT, défaut neutre = tout
  `aucun`) et `par_repartition` (motif cyclique). Valeurs : `automatisme`
  (→ L7), `progression` (→ L6), `aucun` (réservées), ou `mer:<id>` (étiquette
  personnalisée pointant un `preferences_items type_mise_en_route`, contenu géré
  hors logiciel). Exceptions ponctuelles (dates → `aucun`, ex. évaluation).
  Fonction pure `affectation.affecter` + endpoint composé
  `/api/classes/<id>/planning-affecte` (projection + affectation). La projection
  L4 expose désormais `edt_creneau_id` par séance.
- Livraison 6 : progression de séquences de mise en route (nb de séances fixe).
- Livraison 7 : ordonnancement Leitner (enveloppes à réviser par séance d'auto).
- Puis : UI intuitive (une fois le modèle stabilisé).
- Ultérieur : convergence vers le référentiel (verrouillage/utilisation).

### Cadré mais non codé (à traiter plus tard)

- **Archivage EDT + grille horaire des années passées** (décision Qc, L3) : la
  cohérence est garantie sur l'année courante ; pour les années passées, prévoir
  un mécanisme qui fige l'EDT **avec** la grille horaire, embarqué avec la
  progression (sur le modèle des référentiels millésimés). Non implémenté.
- **Traitement fin des groupes** (L3) : les 3ᵉ ont des heures en demi-classe
  (`usage` demi_classe_A/_B, groupe_option, groupe_horaire_ordinaire) — à terme
  une même séance répétée pour 2 groupes doit compter **une seule fois** dans
  les progressions. Il y a différentes raisons d'avoir des groupes, à ne pas
  toutes traiter pareil. Pour l'instant, seul `usage='classe_entiere'` est
  compté ; les autres usages sont saisis/affichés mais non comptés.

## Cœur v0.19.1 (non terminé)

- Drag-drop parties → calendrier (transport typé seqniv).
- Changement de référentiel support d'une progression (purge créneaux,
  confirmation, restreint à `en_cours`, rétrogradation de l'ancien référentiel).

## Décalages de progression (v0.21.4+)

- **Résorption des débordements** (à cadrer) : quand les décalages par classe
  repoussent la progression au-delà de la fin de l'année scolaire, proposer des
  stratégies : supprimer un décalage, réorganiser la progression, ou retirer une
  séquence « moins importante ». Pour l'instant on affiche le débordement sans
  le résorber.
- **Option 2 (plan B)** : si l'option 3 (progression commune + décalages par
  classe dérivés) rencontre des blocages, basculer vers « progression théorique
  commune + progression réalisée par classe ». Le modèle de décalages actuel
  peut servir de base à cette bascule.
- **v0.21.5** : vue « progression annuelle réalisée » par classe (sélecteur de
  classe → décalages appliqués) + bouton « décaler pour cette classe » depuis
  une indisponibilité de portée « classes ».

## Mises en route — automatismes (v0.22.x) et suite

- **Filtrage de la liste des classes** (année / établissement / niveau) : la
  liste peut devenir longue (plusieurs années × niveaux × classes). À traiter
  dans sa propre version (candidat : avec les correctifs UX / v0.23.x). Sans
  rapport direct avec les MER.
- **Tableau de bord hebdomadaire** : vue synthétique du contenu de chaque séance
  de la semaine (automatismes : enveloppes à réviser ; progression : séquence en
  cours), en un coup d'œil. À cadrer.
- **Panachage automatismes / progression** : sélectionner sur l'EdT quelles
  séances sont « automatisme » et lesquelles sont « progression » (mode
  `panache`). À planifier (dépend de l'affectation des séances).
- **Progression de séquences de mise en route** (mode `progression`) : v0.24.x.

## Chantier UX — réorganisation du Suivi annuel (à cadrer quand le périmètre sera stable)

Observation (usage réel) : le Suivi annuel mêle trois natures de choses :
- **enseignant** : EdT, indisponibilités de l'enseignant ;
- **planification théorique par niveau** : progressions de MER, progression
  principale ;
- **suivi réel par classe** : indisponibilités de classe, plannings réels (MER,
  progression), suivi des évaluations.

Une réorganisation de l'UI selon ces axes est envisageable, MAIS à ne mener
qu'une fois le périmètre fonctionnel stabilisé (après le panachage, en usage
réel sur une année) : la bonne structure émergera de l'usage, pas de la théorie.
En attendant, on ajoute les fonctionnalités là où c'est cohérent localement,
sans grande réorganisation.

## SEGPA (à cadrer)

Les classes SEGPA suivent des programmes différents des classes ordinaires.
Comme référentiels et progressions diffèrent, elles doivent être traitées comme
des **niveaux distincts** (pas comme des classes d'un niveau ordinaire). À
prendre en compte dans la gestion des niveaux quand le besoin se présentera
(remarque de l'utilisateur, chantier panachage v0.28).

## v0.29 — Bug impression recto-verso des cartes d'automatismes

En recto-verso paysage avec retournement sur le bord court, l'ordre des rectos
est inversé par rapport aux versos : chaque verso ne tombe pas derrière son
recto. À corriger dans la génération LaTeX des planches d'atomes/cartes
(ordre/miroir des pages verso, ou option d'imposition). Signalé après impression
réelle de la séquence S03.

## v0.35+ — Homogénéisation des sélecteurs (étape B)

- B1 (v0.35.0, FAIT) : Gestion ralliée au pool partagé (filtres en dur retirés).
- B2 (v0.36, à faire) : unifier la Conception (sequence/cycle dynamiques).

### Détail initial :

Objectif : un moteur de sélecteurs unique et homogène (présentation + code) entre
Suivi, Planification et Conception. Aujourd'hui : 3 mécanismes parallèles —
`suiviRenderSelecteurs` (pool de labels, Suivi/Planif), `atelRenderSelecteursPortee`
(crée les selects en JS, Conception), et filtres codés en dur dans la Gestion.
À faire : fusionner en un seul moteur déclaratif, retirer les filtres en dur de
la Gestion (les brancher sur le pool partagé). L'étape A (v0.34) a déjà rendu le
Suivi cohérent avec la Planification (mêmes sélecteurs etab/niveau/classe).

## Plans de classe — suites notées pendant le chantier v0.37–v0.40

- v0.40.0 (livrée) : sexe à l'import élèves, aléatoire mixte, places AESH.
- Modéliser les élèves accompagnés par un AESH (placement automatique du
  binôme) si le besoin se confirme.
- Plans de classe pour les **demi-groupes et groupes** (aujourd'hui seuls les
  cours en classe entière ouvrent un plan) ; suppose de modéliser
  l'appartenance des élèves aux groupes.
- **Préférence** « statut par défaut d'un élève placé » (libre / imposé) :
  certains collègues imposent tout le plan.
- Remplacements ponctuels (classe d'un collègue, autre salle).
- Classe flexible : îlots à destination, places surnuméraires, ressources
  (casques, culbutos, pédaliers) attribuées à l'élève.
- Usage au doigt (tablette, responsive) pour le suivi en séance.

## Réorganisation de la navigation (à cadrer)

- Créer un onglet principal **Configuration** regroupant la partie Gestion
  du Suivi (Classe, Établissement) et l'actuel onglet Administration.

## Suivi en séance (chantier ouvert oct. 2026)

Découpage validé : v0.42 navigation (Paramétrage, Système ; Suivi › Début de
séance, Observation, Compétences) ; v0.43 Début de séance (séance en cours,
mise en route affichée, absences) ; v0.44 documents (prévus et ponctuels —
administratifs, sorties —, remise, rattrapage des absents, reste dû) ;
v0.45 observables par niveau (communs ou individuels, périodes, exceptions
masquer/attribuer) ; v0.46 observation sur le plan de classe ; v0.47 retours
attendus et travail à faire (fait / rendu).

Notés pour plus tard :
- Signaler facilement que le prévu d'une séance a été chamboulé (MER non
  faite, séance raccourcie…) et replanifier en conséquence.
- Raccourci « séance en cours » depuis le tableau de bord.
- Processus complet de conservation / purge des données en fin d'année
  scolaire (absences, observations, sanctions : données de mineurs).
- Application tablette pour l'enseignant (saisie en classe au doigt).
- Séances hors cours en classe entière (demi-groupes, remplacements).
- Documents associés à la progression de MER (câblage de l'association,
  puis distribution en début de séance comme les documents principaux).

## Mode d'emploi et conduite assistée (à cadrer après le suivi en séance)

- Mode d'emploi rédigé, en partie intégré aux écrans : infobulles, accès
  direct aux rubriques d'aide de l'écran et aux rubriques connexes.
- Deux modes :
  - **conduite assistée** : l'appli propose les actions selon le moment de
    l'année (rentrée → construction des progressions ; début de séquence →
    distribution des documents ; début de séance → appel ; fin de période →
    préparation du conseil de classe…) et pour la conception des
    référentiels ;
  - **expert** : tout en manuel (fonctionnement actuel).
- Suppose de modéliser le calendrier de l'année (périodes, conseils de
  classe).
- Les **types explicites des documents** (v0.48.3, v0.48.5) servent de
  déterminant : savoir ce qu'on fait de chaque document dans la progression
  (distribuer, faire faire, évaluer) sans le deviner d'après son nom ; avec
  les thèmes, envisager de **proposer une progression** (spiralée, par
  exemple).

## Mode « pur externe » (sans LaTeX)

- Préférence « Désactiver la construction de référentiels en LaTeX » : masque
  toute la partie LaTeX (écrans de conception interne, compilation, tuiles du
  tableau de bord, préférences et administration liées). Objectif : rendre
  l'appli accessible aux collègues qui ne connaissent pas LaTeX ou y sont
  réfractaires (référentiels externes uniquement).

## Changement de salle exceptionnel (hors EdT)

- Besoin : utiliser ponctuellement une autre salle sans changer l'EdT (ex. :
  salle multimédia, quand elle est disponible, pendant la séquence S14).
- Dans la planification hebdo : changer la salle d'une séance (ou d'une série
  de séances) d'une classe, y compris vers une salle **pas encore déclarée**
  dans le paramétrage de l'établissement → création à la volée du nom de la
  salle (sans plan) ; pour lui associer un plan de salle, passer par
  Paramétrage › Établissement › Salles.
- À cadrer : portée (une séance, plusieurs, « jusqu'à la fin de la
  séquence ») ; effet sur le plan de classe (plan de la semaine dans la salle
  de remplacement, ou liste alphabétique si la salle n'a pas de plan) ;
  affichage dans le Début de séance / l'Observation ; une salle créée à la
  volée devient-elle « utilisée » (non supprimable) ?

## Référentiel interne de MER (LaTeX)

- Concevoir les documents LaTeX propres aux mises en route : activités de
  5-10 min en début de séance ; fiches de cours (2 par page), séries de calcul
  mental (5 questions, score /5), corrigés et tests (/10) séparés — modèles
  fournis par l'auteur (oct. 2026). Probablement de nouveaux ateliers. Le type
  « MER » des référentiels internes est ouvert dès v0.48.3.
