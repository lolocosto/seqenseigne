# Redémarrage v0.42.0 — Navigation : Paramétrage, Système, Suivi en séance

Première livraison du chantier « suivi en séance » (découpage : ROADMAP,
section « Suivi en séance »).

## Décisions validées

- **Barre principale** : Tableau de bord · Suivi · Planification · Conception
  de référentiel · **Paramétrage** · **Système**.
  - **Paramétrage** (le pédagogique) : Classe, Établissement (salles
    comprises), **Observables** (panneau d'attente, contenu en v0.45). C'est
    l'ex-portée « Gestion » de l'onglet Suivi.
  - **Système** (l'appli elle-même) : barre Administration / Préférences ;
    le sous-onglet choisi est mémorisé.
- **Suivi** : **Début de séance** (attente, v0.43–v0.44), **Observation**
  (attente, v0.46), **Compétences** (ex-« Suivi de classe », inchangé).
  Plus de boutons de portée « Suivi de classe / Gestion ».

## Code

- `templates/index.html` : boutons `data-tab="parametrage"` et
  `data-tab="systeme"` ; `<main id="tab-systeme">` (barre) ; boutons
  d'ateliers `debut`, `observation`, `observables` ; panneaux d'attente.
- `static/app.js` :
  - `SUIVI_PORTEES` : suivi = [debut, observation, suivi] ; gestion =
    [classe, etab, observables] ; `SUIVI_PORTEE_ONGLET` (portée → onglet
    principal) : l'onglet principal en surbrillance suit la portée, y compris
    lors des bascules par code (`sousOnglet`, `gestionAllerEtablissements`) ;
  - « Paramétrage » partage `tab-classe` (portée gestion) comme
    « Planification » ; « Suivi » force la portée suivi ;
  - `systemeSwitch(admin|preferences)`, `_prefInitialiser()` (reprend le
    chargement des Préférences fait auparavant à l'entrée de l'onglet).
- `static/tableau_bord.js` : « Paramètres » ouvre Système › Préférences.
- Lien « Sélectionnez une classe, ou créez-en une dans l'onglet… » : pointe
  vers Paramétrage (il visait un onglet `classes` qui n'existait plus).

## Tests

- vitest `suivi_navigation.test.js` mis à jour (+3) : rangée de portées
  masquée, défaut Début de séance, panneau Observables, onglet principal qui
  suit la portée, bascule Système mémorisée.
- Parcours navigateur : chaque onglet principal, sous-onglets visibles,
  Système › Préférences, raccourci du tableau de bord.
