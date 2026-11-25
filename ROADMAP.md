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

## Séparation en deux outils (v0.51, en cours)

Appli locale « atelier » (conception de tous les référentiels, LaTeX) et appli
en ligne « classe » (suivi, sans LaTeX), un seul code, trois profils.
- v0.51.0 : profils complet / atelier / classe (fait).
- v0.51.1 : format JSON des référentiels (schéma versionné, documenté) — base
  de la future API (fait).
- v0.51.2 : paquet de publication (JSON + PDF compilés + fichiers externes,
  empreintes, rapport) ; tuile « Publication » au tableau de bord atelier
  (fait).
- Passe « durées » (validée, en partie faite) : la durée d'une partie est la
  somme des séances de ses objectifs. Faits : export (v0.51.2), éditeur des
  référentiels externes et MER — durée calculée, en lecture seule (v0.51.4).
  Reste : figeage des internes, progression principale et Progression de
  MER en semaines (semaines = séances ÷ séances par semaine du niveau).
- v0.51.4 : atelier — codes de séquence recalculés tant que le référentiel
  est en conception ; documents déplaçables ; durée de partie calculée (fait).
- v0.51.5 : thèmes dans l'éditeur des référentiels externes et MER
  (codes A, B… en conception, couleur, séquences regroupées par thème,
  alerte « sans thème ») (fait).
- v0.51.6 : structures modèles (fait ; cadrage validé : modèles du même type
  seulement — principal ↔ principal, MER ↔ MER — plus le programme du cycle
  pour les principaux ; programme du cycle = une partie par séquence, 0
  séance, ou les parties de l'atelier de conception quand elles existent ;
  documents jamais copiés ; détection de doublon : un nouveau référentiel
  identique à un existant est signalé — pour reconduire, la progression de
  l'année suivante se base sur le même référentiel). Demande initiale : proposer les structures connues du niveau (thèmes → séquences
  → parties → objectifs, arbre dépliable) ; en choisir une préremplit le
  référentiel, ensuite utilisable tel quel (ajout des documents) ou modifié
  (réordonner, ajouter, supprimer à tous les niveaux) ; ou partir de vide en
  définissant tout, **thèmes compris** (absents aujourd'hui des référentiels
  externes). Objectif : la structure complète dans le JSON publié, pour le
  suivi et la création des progressions.
- v0.51.3 : import côté classe (structure en lecture seule, rapport des
  changements, documents orphelins signalés) (fait).
- Retour d'usage classe → atelier (validé, v0.51.8) : référentiel utilisé,
  date de début du premier créneau de chaque séquence planifiée, parties de
  MER posées — sans donnée d'élève, ni classe, ni établissement ; verrous
  jamais perdus ; remplace la
  lecture directe des progressions par l'atelier (verrou des séquences
  commencées, état « utilisé »). Par fichier ou boîte aux lettres (v0.51.9).
- Protocole d'échange (validé, sur le modèle des datagrammes acquittés) :
  identité de chaque instance (identifiant, nom), lien un atelier ↔ une
  appli en ligne, en-tête (émetteur, destinataire, numéro d'ordre, accusé),
  réception dans l'ordre (trou refusé, numéros manquants à redemander),
  archive et renvoi, retrait de l'archive à l'acquittement ; états de
  synchronisation par référentiel (synchronisé, modifié depuis la
  publication, publication en attente, en retard, désynchronisé).
  - v0.51.7 : protocole appliqué aux paquets (fait).
  - v0.51.8 : retour d'usage (classe → atelier) sur ce protocole ;
    acquittements ; états de synchronisation (fait, `doc/format_usage.md`).
- v0.51.9 : boîte aux lettres (fait) — dossier d'entrée relevé au
  démarrage puis périodiquement (5 min par défaut), copie de chaque envoi
  dans un dossier de sortie, mode confirmation / automatique, tampon de
  réception (un envoi hors séquence attend le manquant). Échange asynchrone :
  les deux applis n'ont pas à tourner en même temps.
- v0.51.10 : retours du premier essai (fait) — réglages des échanges dans
  Système › Préférences › Échanges ; plus d'import manuel de retour d'usage
  dans l'atelier (boîte aux lettres seulement) ; pas de retour d'usage sans
  référentiel importé ; base partagée expliquée.
- v0.51.11 : retraits (fait) — ancien modèle de MER (`referentiel_externe*`)
  et anciens livrets (`livrets_de_sequence`, `livret_revisions`, `versions`,
  `versions_classes`), contenu sauvegardé en JSON ; onglet Administration ›
  « Import retours d'usage » dans l'atelier.
- v0.51.12 : bascule (fait ; répartition validée table par table : 43 tables
  classe, 33 atelier, 18 des deux côtés ; dossiers `data_atelier\` et
  `data_classe\`, `data\` intact) — rôle de chaque base, structures absentes
  de chaque côté (gardes sur les lectures croisées), outil (aperçu,
  sauvegarde, paquet n° 1, retour d'usage, nettoyage), tests des données
  attendues côté classe (titres, noms et PDF des documents, cases du suivi).
- v0.51.13 : tableau de bord (fait) — tuiles Publication / Retour d'usage
  simplifiées (détail dans un écran dédié), tuiles Établissements (salles,
  lien « plan »), Classes (liste des élèves, lien « plan »), Journée (modèle
  de la planification hebdo, flèches de navigation).
- v0.51.14 : résumé des séances (fait) — planification hebdo et tuile Journée
  (MER, principale, documents) ; Journée → Début de séance, Observation,
  Travail, Compétences.
- v0.51.16 : échange automatique par API (fait) — l'atelier appelle l'appli
  de classe (adresse + jeton à expiration, montré une fois), envoi immédiat
  des paquets, retours d'usage produits et rapatriés automatiquement,
  secours par dossiers ; cible multi-enseignants : appli de classe
  multi-utilisateur (plus tard).
- v0.52.x : mise en ligne — compte unique (mot de passe haché, second
  facteur), HTTPS, VPS. Transport des envois entre le PC et le serveur (la
  boîte aux lettres rend inutile l'API générale prévue au départ) — à
  choisir : dossier synchronisé (Syncthing, Nextcloud…, sans code) ou API
  réduite à la boîte aux lettres (« déposer », « relever », jeton), l'atelier
  poussant ses paquets et rapatriant les retours à chaque relève.
- Tableau de bord atelier : pilotage de la conception (état des
  référentiels, compilation, publication) à enrichir dès la v0.51.2.
- Import suivi (classes historiques) : profil complet seulement, à retirer
  après la bascule.
- Multi-utilisateur (collègues) : plus tard, chantier à part.

## Documents imprimables sans LaTeX (v0.50, terminé)

But : outil « classe » sans distribution LaTeX (préalable à la mise en ligne).
- v0.50.0 : plannings automatismes / MER / aperçu théorique en HTML (fait).
- v0.50.1 : plans de classe en SVG (fait).
- v0.50.2 : retrait des générateurs `.tex` hors ateliers et des routes `.pdf` (fait).
- Plus tard, si un téléchargement direct de PDF devient nécessaire en ligne :
  WeasyPrint côté serveur sur les mêmes gabarits HTML.

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

## Ateliers atomiques — petits manques repérés (inventaire v0.56.3, 13 nov. 2026)

- v0.61.0 — **Encarts** devenus des atomes (atelier « Encart ») : pas encore dans la
  Recherche ni dans le rendu par lot (comme les cartes mentales pour le second).

Voir `inventaire_ateliers.md` de la livraison v0.56.3.
- Atelier **Exercice**, mode « toutes les séquences » : la liste n'indique pas la
  séquence de chaque exercice (les autres ateliers l'affichent).
- **Rendu par lot** : n'inclut pas les cartes mentales (ni option « sans cache »,
  cf. v0.56.2).
- Atelier **Exercice** : règle CSS du mode côte-à-côte visant un identifiant
  disparu (`#atl-exo-form`) — sans effet visible, à nettoyer.

## Référentiels internes de 6e et progression 2027-2028 (13 nov. 2026)

- Aucun référentiel interne de 6e dans la base de l'atelier au 13 novembre
  (X2026_N09 externe et M2026_N09 seulement). Création par l'appli selon la
  marche à suivre v0.54.0 mise à jour (validation des atomes, des séquences,
  création principal + MER, documents, verrouillage, publication).
- Ensuite : chantier « progressions » (séances par objectif, placement des
  MER, bascule depuis M2026_N09, dépendances, tuile matériel) pour construire
  la progression 6e 2027-2028.

## Référentiel de 4e — nouveau programme (rentrée 2027), modèle Fiches (13 nov. 2026)

- Programme : arrêté du 18 février 2026 (BO n° 10 du 5 mars 2026), en 4e à la
  rentrée 2027-2028.
- Modèle « Fiches de cours » avec **cartes d'automatisme** dans la progression
  principale (pas de référentiel de MER séparé).
- Méthode du référentiel de 6e : structure en séquences (créer / supprimer) →
  parties → objectifs détaillés (`ref4e`) → réutilisation (notions, méthodes,
  fiches de résumé → fiches de cours et cartes mentales ; exercices ; cartes
  d'automatisme) → création (activités de découverte, activités
  complémentaires, TP, tests courts, évaluations).
- N11_v2025 reste intouchable (en classe cette année).
- **Version 1 livrée (v0.59.0, 16 novembre)** : archivage de la structure de 2025 de N11,
  import des lots de 4e (`--niveau N11`), cartes rattachées aux objectifs (niveau de
  création gardé), année et option « cartes » du référentiel interne, titres courts
  (`doc/redemarrage_v0_59_0.md`). Ensuite : les 12 lots de 4e (un par séquence), écrits
  d'après `col4/ref4e_v1.md` et l'inventaire de l'étape 3, importés et validés.
- **Version 2 — v0.60 (avant la rentrée 2027, avec le chantier des progressions)** —
  découpée en deux livraisons :
  - **v0.60.0 livrée (18 novembre)** (`doc/redemarrage_v0_60_0.md`) : document de rituels
    d'automatismes et séances d'évaluation calculé depuis un **ordre des parties saisi**
    dans l'atelier Référentiel (aucune progression ordonnée n'existe dans l'atelier ;
    décisions P0 à P7 : cartes nouvelles la semaine qui suit la partie, rappels à 1 et
    4 semaines puis toutes les 6 semaines, réactivation des cartes des années précédentes
    au début de la partie, séance d'évaluation toutes les deux semaines, 50 min et
    5 objectifs au plus, au moins une semaine après la partie, dernière séquence non
    évaluée) ; type d'évaluation « test court » (clé `tests_courts` des lots, tests courts
    déjà importés reconnus par leur titre) ; durée d'une évaluation (10 min par objectif) ;
    correctifs d'import B6 à B10 (activités sous « Cours » + outil de migration, variables,
    durée de la partie sans calculatrice, titres échappés, bonus de 1 point) ; essai de
    l'archivage de N10 ; ajoutés (étape 3 de la 5e) : import `--niveau N10` (F1),
    avertissement de l'archivage pour les référentiels non figés (F2), niveau de création
    des cartes corrigible dans l'atelier et par l'import (F3) ;
  - **v0.60.1 livrée (18 novembre)** (`doc/redemarrage_v0_60_1.md`) : cartes de la partie
    dans le plan de travail Fiches (E9) ; titre court saisi dans l'atelier ; avertissement
    « objectif sans carte » (propriété `sans_carte` lue dans les lots) ; document « Tests
    courts » (option cartes, cartes évaluées dans le corrigé) et document « séance
    d'évaluation » ; tests courts placés dans les séances au choix de l'enseignant ; mode
    de mise en route du référentiel principal (décision 18, format d'échange 1.7) ; bonus
    1 pt sur le cycle 4 ; bloc « Carte mentale » retiré du Rendu PDF de l'assemblage ;
    atelier Exercice (séquence en « toutes les séquences », `#atl-exercice-form`) ; rendu
    par lot avec cartes mentales et « Sans cache » ; traces S… (externe documenté en S01…,
    exemples « A1 », `/api/admin/cycle/importer` protégé) ; réimport sûr des évaluations
    et tests courts (R5 à R7), multisélection du module Évaluations, accord « pt » ;
  - **v0.60.2 livrée (18 novembre, soir)** (`doc/redemarrage_v0_60_2.md`) : tests courts en
    QCM (barème QCM posé par l'import, réimport qui répare, plus de contrôle « sur 10 » ni
    de bonus pour un test court ; figure d'origine déjà dans images non bloquante) ; cadre des rituels retiré de l'atelier Référentiel (voir
    « Progressions : rituels et séances d'évaluation » ci-dessous) ;
  - **v0.60.3 livrée (19 novembre)** (`doc/redemarrage_v0_60_3.md`) : filets des tableaux
    (couleur du tableau de suivi qui fuyait, `seqenseigne-style6e` v0.16, `seqenseigne-data`
    v1.2) ; noms des PDF et libellés du modèle Fiches au niveau réel (6e inchangée) ;
    reste possible : renommer les clés internes des types (`livret_sequence_6e`…, jamais
    affichées) — migration de `referentiel_documents` et des références `type|cible` côté
    classe, sans gain visible aujourd'hui ;
  - restent : durée affichée sur chaque sujet (aujourd'hui : en-tête de la séance
    d'évaluation et module Évaluations) ; planches de cartes par partie ; tests courts
    retirés du document « Évaluations » quand le document « Tests courts » est publié (à
    trancher) ; saisie du mode de mise en route dans l'éditeur d'un référentiel externe
    (aujourd'hui : création et barre du référentiel choisi) ;
  - plus tard, avec le chantier des progressions côté classe : voir ci-dessous.

### Progressions : rituels et séances d'évaluation (décision du 18 novembre, 22 h 39)

Le cadre « Rituels d'automatismes et séances d'évaluation (progression) » de l'atelier
Référentiel (v0.60.0 à v0.60.1) n'y a pas sa place : il relève des **progressions**, donc
du **suivi de classe**. Retiré de l'interface en v0.60.2 ; à reconstruire côté classe :
- **rituels d'automatismes** : cartes nouvelles après la partie où la notion est enseignée,
  puis **rappels espacés** jusqu'en juin (Leitner à l'oral en mise en route), réactivation
  des cartes des années précédentes au début des séquences qui en ont besoin
  (décisions 10 et 17) ;
- **séances d'évaluation par classe** : jour choisi pour chaque classe d'après son **emploi
  du temps** (créneaux réels, projection séance → date déjà en place), une séance toutes
  les deux semaines, 50 min et 5 objectifs au plus, au moins une semaine après la fin de la
  séquence (règles P2 à P5 de la v0.60.0) ;
- **tests courts possibles à l'écrit** (QCM, un par partie, sur les cartes de la partie) au
  lieu de Leitner, « n cartes, 6 séances pour les connaître, puis évaluation » : choix
  Leitner / écrit et rappels intégrés ou non quand on cale la progression (décision 17) ;
- l'ordre des parties viendra de la progression ordonnée par semaines de la classe, pas
  d'une saisie dans l'atelier ; cartes de la partie au début de séance (rappel Leitner).

Gardé pour ce chantier : `services/progression_rituels.py` (calendrier, document .tex,
séance d'évaluation), routes `/api/progression-rituels/…`, producteur `rituels_progression`
de l'orchestrateur, données saisies (ordre des parties, paramètres jour d'évaluation,
cartes du document, tests courts placés ou non, délai). Ancienne interface : fonctions
`atelRefRituels*` de `static/atelier_referentiel.js` en v0.60.1 (0abb41f).

  - archivage de la structure de 2025 de N10 et N12 (même outil) au moment des
    référentiels de 5e et de 3e : outil essayé sur N10 en v0.60.0 (copie de la base) ;
    `outils/objectifs_5e.json` viendra avec le référentiel de 5e.

## Thèmes communs et codes A1 (cycles 3 et 4) — migration en deux livraisons (15 nov. 2026)

Décisions 6 à 9 du cycle 4 (thèmes = domaines du programme, A à F communs aux deux
cycles ; codes de séquences A1) ; plan `plan_migration_themes_codes.md` validé le
15 novembre (22 h 41), N11_v2025 et 2025_N11b figés et publiés.
- **v0.57.0 livrée** : code tolérant aux codes A1, aucune donnée migrée
  (`doc/redemarrage_v0_57_0.md`) ; table `outils/correspondance_codes_2027.json`.
- Usage de la v0.57.0 : écourté (feu vert du 16 novembre, 7 h 36 : livrets compilés,
  référentiel de cette année figé, PDF disponibles).
- **v0.58.0 livrée** (16 novembre) : outil `outils/migrer_themes_codes_2027.py` (essai à
  blanc, `--apply`, `--annuler`, idempotent, sauvegarde, journal, empreinte de ce qui
  n'est jamais touché), reclassement `outils/reclassement_2027.json`, fichiers LaTeX du
  cycle 4, correctif des outils de lots (`doc/redemarrage_v0_58_0.md`). Données de
  départ non réécrites (décision M8 : l'atelier lit ses copies de `data_atelier\`) ;
  `.dbtex` non régénérés (lus seulement par les livrets compilés à la main).
- **Jour de migration** (Laurent) : sauvegardes, essai à blanc, `--apply`, contrôles
  (marche à suivre de la livraison v0.58.0).
- Ensuite : nouveaux référentiels 2027 (5e, 4e, 6e ; 3e en 2028) saisis en codes A1,
  PDF compilés, verrouillés et publiés avant la rentrée.
