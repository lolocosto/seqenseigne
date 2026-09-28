# Redémarrage v0.19.1.2 — Navigation « Suivi de classe » harmonisée sur le pattern Référentiel

Refonte de la navigation de l'onglet **Suivi de classe** pour qu'elle adopte
exactement le pattern à 2 barres de la zone **Conception de référentiel**
(`tab-ateliers`) : barre de portées + barre de sous-ateliers, sélecteurs
contextuels alignés à droite de la barre 1, et réutilisation du design-system
d'items pour la barre latérale de l'atelier Progression.

Suite des retours sur la livraison v0.19.1.1.

## Décisions appliquées

- **D1 — Navigation à 2 barres.** La `.sub-tabs` plate (Progression / Suivi des
  séquences / Gestion des classes) est remplacée par :
  - **Barre 1 (portées)** : `Suivi annuel` · `Gestion` + zone sélecteurs à
    droite (`#suivi-portee-selecteurs`, `margin-left:auto`).
  - **Barre 2 (sous-ateliers)** : *Suivi annuel* → `Progression` ·
    `Suivi de classe` ; *Gestion* → `Classe` · `Établissement`.
  Mêmes balises (`<div class="toolbar" …>`), mêmes boutons `.vbtn`, même style
  que la zone Référentiel. Visibilité des boutons d'atelier par classe
  `.suivi-grp-<portée>` (calque de `.atl-grp-<portée>`).
- **D2 — Module JS dédié `suivi*`** (décision A-i : pas de mutualisation avec
  `atel*`, zones DOM et sélecteurs distincts). `SUIVI_PORTEES`,
  `suiviPorteeSwitch`, `suiviSwitch`, `suiviRenderSelecteurs`, `suiviInit`.
  Mémorisation localStorage : `suivi-portee-active`, `suivi-atelier-actif`.
- **D3 / B — Sélecteurs contextuels en barre 1**, au même endroit et style que
  l'atelier Référentiel (label inline discret + `select` compact, classe
  `.suivi-sel`) :
  - *Progression* → **Année · Établissement · Niveau · Référentiel** ;
  - *Suivi de classe* → **Année · Classe** (la classe détermine déjà
    établissement et niveau ; on ne recâble pas la logique de suivi, hors
    périmètre) ;
  - *Gestion* → aucun sélecteur.
  Mécanisme : les `<select>` existants (IDs inchangés : `#prog-sel-*`,
  `#annee-sel`, `#classe-sel`) sont conservés dans des **pools cachés**
  (`#prog-selecteurs-pool`, `#suivi-selecteurs-pool`) et **déplacés** dans la
  barre 1 par `suiviRenderSelecteurs` selon l'atelier actif (puis renvoyés à
  leur pool). Les IDs et handlers sont préservés → aucune logique métier
  touchée.
- **D4 — Barre latérale Progression sur le design-system commun.** Les items
  « parties de séquence » utilisent désormais `.atl-item` + `.atl-item-id`
  (`--compact`, code `S01·P1` monospace) + `.atl-item-titre` (nom, ellipsis) +
  `.atl-item-meta` (compte d'objectifs/séances), avec une pastille d'état
  `.atl-list-item-etat` (« placée » verte / « à dater » orange) identique aux
  autres ateliers. Les badges de semaine réutilisent `.atl-item-meta`. Le
  conteneur passe en `.atl-list`. Suppression des classes maison
  `.prog-partie-item / -titre / -meta / -semaine-badge / -nonplacee`.
- **C — Défaut inchangé** : à l'ouverture, portée *Suivi annuel* → atelier
  *Suivi de classe* (sauf restauration d'un choix mémorisé).
- **D5 — Périmètre strict** : déplacement + restyle uniquement, aucun
  changement fonctionnel. Les panneaux (calendrier, suivi des séquences,
  gestion classes/établissements) sont inchangés, seulement re-parentés sous la
  nouvelle navigation.

## Détails d'implémentation

- **Compatibilité** : l'ancien `sousOnglet(nom)` est conservé comme **shim**
  qui mappe `progression`/`suivi`/`parametrage` vers la nouvelle navigation —
  les appels existants (`selectClasse`, etc.) continuent de fonctionner.
- **Barre de sous-onglets Gestion interne** (`gest-btn-classes` /
  `gest-btn-etabs`) **masquée** : remplacée par la barre 2. Les boutons restent
  dans le DOM (togglés par `gestionSousOnglet`) ; `gestionAllerEtablissements`
  et `AtelierProgression.allerGestionEtabs` passent par `suiviSwitch('etab')`
  pour activer le bon bouton.
- **Hauteur du shell Progression** : l'override `#stab-progression .atl-shell`
  est supprimé ; le panneau utilise la règle globale `.atl-shell`
  (`calc(100vh - 96px)`) comme tous les autres ateliers, sa navigation étant
  désormais identique (2 barres dans `.tab-content`).
- **Initialisation** : `suiviInit()` est appelé au démarrage (l'onglet Suivi de
  classe est actif par défaut) et à chaque entrée dans l'onglet.

## Changements (fichiers)

- `templates/index.html` : remplacement de `.sub-tabs` par les 2 barres
  (`#suivi-portee-row` + `#suivi-portee-selecteurs` ; boutons `.suivi-grp-*`) ;
  sélecteurs Progression sortis de la toolbar vers `#prog-selecteurs-pool` ;
  `#annee-sel`/`#classe-sel` sortis de la barre Suivi vers
  `#suivi-selecteurs-pool` ; barre Gestion interne masquée ; sidebar Progression
  en `.atl-list`.
- `static/app.js` : module `suivi*` (SUIVI_PORTEES, suiviPorteeSwitch,
  suiviSwitch, suiviRenderSelecteurs, suiviInit) ; `sousOnglet` devient un shim ;
  appel `suiviInit()` au démarrage et à l'entrée d'onglet ;
  `gestionAllerEtablissements` via la nav.
- `static/atelier_progression.js` : markup de la barre latérale migré vers
  `.atl-item*` + pastille `.atl-list-item-etat` ; `allerGestionEtabs` via
  `suiviSwitch('etab')`.
- `static/app.css` : `.suivi-sel*` (sélecteurs barre 1, style Référentiel) ;
  `.prog-toolbar*` conservé pour le titre ; suppression de `.prog-sel*` et des
  `.prog-partie-*` (sauf `.prog-partie-badges`, conteneur des badges semaine) ;
  suppression de l'override de hauteur du shell.

## Tests

- `tests_js/suivi_navigation.test.js` (nouveau, 11 cas) : bascule de portée
  (boutons actifs + visibilité), défaut Suivi de classe, Gestion >
  Établissement → `gestionSousOnglet('etabs')`, Progression → `progInit`,
  sélecteurs par atelier (4 prog / 2 suivi / 0 gestion), absence de fuite de
  sélecteurs au va-et-vient, shim `sousOnglet`.

**Zéro régression** : vitest → 183 passed (172 + 11) ; pytest → inchangé
(livraison front uniquement ; sous-ensemble progression backend revérifié :
78 passed).

## Déploiement & vérification

Aucune migration de base. Décompresser le delta sur D:/E:, puis :

    python -m outils.verifier_md5

Dans « Suivi de classe » : vérifier la barre 1 (Suivi annuel / Gestion) et la
barre 2 (sous-ateliers), au style identique à « Conception de référentiel » ;
les sélecteurs en haut à droite (4 pour Progression, 2 pour Suivi de classe) ;
la barre latérale de Progression avec items, code séquence, pastille d'état et
badges de semaine au style des autres ateliers.

## Suite (cœur v0.19.1 restant)

Drag-drop parties → calendrier ; changement de référentiel support (purge des
créneaux, confirmation, restreint à `en_cours`, rétrogradation de l'ancien
référentiel).
