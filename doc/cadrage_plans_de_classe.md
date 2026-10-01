# Cadrage — Salles, plans de salle, plans de classe (chantier v0.37 → v0.40)

Validé avec l'auteur début octobre 2026. Objectif final : le suivi en séance
(fiches de suivi hebdomadaires appuyées sur le plan de classe).

## Usage visé (pratique de classe flexible)

- Certains élèves sont placés d'autorité, les autres choisissent leur place ;
  l'enseignant note les places sur le plan et elles valent **toute la semaine**.
- Les places ne se valent pas (table haute, « pas devant »…) d'où l'intérêt du
  plan hebdomadaire. Plus tard : îlots à destination (travail, aide…), places
  surnuméraires, ressources de classe flexible liées à l'élève (casques,
  culbutos, pédaliers).

## Découpage

| Version | Contenu |
|---|---|
| v0.37.0 | Salles (par établissement), éditeur libre de plan, versions, archivage, import TikZ de la 302 |
| v0.38 | EdT versionné (effet à partir d'un lundi ≥ semaine prochaine, sans rétroactivité) ; salle et nombre d'AESH par case |
| v0.39 | Plans de classe hebdomadaires, reconduction, échange de 2 élèves, aléatoire pur, impression PDF |
| v0.40 | Sexe à l'import élèves, aléatoire mixte, réservation des places AESH |
| Plus tard | Remplacements ponctuels (classe d'un collègue, autre salle), groupes (demi-classes, options : (c) pour l'instant, (b) à terme), îlots à destination, responsive/tablette |

## Salles et plans de salle (v0.37.0)

- Bouton « Salles » sur la carte établissement ; éditeur en panneau plein écran.
- Les salles appartiennent à l'établissement, sans année. Peu de salles
  (mono-utilisateur) ; une salle peut être archivée (« non utilisée cette
  année ») et réactivée.
- Plan **libre** : une place = un emplacement d'une personne (forme/hauteur
  indifférentes, affichée 60×40 cm), positionnée et tournée (pas de 5°),
  regroupée en îlots ; aimantation bord à bord ; tableau en haut (repère
  dessiné). Pas de bureau du professeur.
- Numérotation automatique, stable : un numéro n'est jamais réattribué.
- « Salle utilisée » = affectée à au moins une case d'EdT (v0.38).
  - Non utilisée : édition en place, suppression possible.
  - Utilisée : modification = nouvelle version datée d'un lundi au choix,
    au plus tôt la semaine prochaine ; versions futures modifiables et
    supprimables ; en vigueur et passées figées ; suppression interdite.
- Voisinage (v0.40 : mixte, AESH) : déduit des îlots.

## EdT (v0.38)

- Versions datées (lundi ≥ semaine prochaine, pas de rétroactivité).
- Par case : salle (facultative), nombre d'AESH présents. Un AESH peut
  accompagner plusieurs élèves : on réserve autant de places que d'AESH.
- Points à traiter : `affectation_seance.edt_creneau_id`, numérotation continue
  des séances (`projection_seances`), planification hebdo, progressions.

## Plans de classe (v0.39)

- Un plan par (classe, salle, semaine). Placement « imposé » ou « libre ».
- Reconduction : la semaine sans saisie reprend la précédente sans copie en
  base ; la copie naît à la première modification. Imposés et libres repris
  (les libres en proposition).
- Plan en vigueur corrigeable sur place ; nouvelle version pour une date future.
- Élève sorti (date de sortie) : place libérée ; élève arrivé : « non placé ».
  Places vides et élèves non placés autorisés.
- Changement de version de salle : l'élève garde sa place si son numéro existe
  encore, sinon « non placé » + avertissement.
- Outils : échange de 2 élèves, aléatoire pur ; impression PDF (sans réseau ou
  par choix). Saisie dans l'appli par défaut.

## Données élèves (v0.40)

- Import Pronote (copier-coller CSV : Numero, Nom, Prenom, DateNaissance,
  PrenomUsage, Sexe, Classe de rattachement, Projet d'accompagnement,
  Option 1..12) : lire `Sexe` (M/F) et compléter les élèves existants.
- **Ne jamais importer** « Projet d'accompagnement » (PAI, données de santé) ni
  la date de naissance.
