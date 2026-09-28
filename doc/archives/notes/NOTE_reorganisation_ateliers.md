# v0.10 — Réorganisation des ateliers en 4 portées

**Date** : 29 avril 2026

## Ce qui a été fait

Refonte de la barre de navigation des ateliers en **2 niveaux** :

- **Ligne 1** : portée (Séquence / Niveau / Cycle / Généraux) + sélecteurs
  contextuels alignés à droite
- **Ligne 2** : ateliers de la portée sélectionnée

Les sélecteurs sont contextuels : ils n'apparaissent que pour la portée
courante, et leurs valeurs sont **mémorisées par portée en localStorage**.
Quand on change de portée, on retrouve les sélections précédentes pour
cette portée.

## Mapping portée → ateliers → sélecteurs

| Portée | Ateliers | Sélecteurs |
|---|---|---|
| **Séquence** | Notion, Méthode, Exercice, Séquence, Fiche de résumé | niveau + séquence |
| **Niveau** | Récap cours, Récap exos, Plans de travail | niveau |
| **Cycle** | Thème, Découpage en séquences | cycle |
| **Généraux** | Rendu par lot | (aucun) |

## Renommages effectués

- « Séquence (niveau) » → **« Séquence »** (en portée Séquence)
- « Séquence (cycle) » → **« Découpage en séquences »** (en portée Cycle)

## Nouveaux ateliers (placeholders)

4 panneaux ajoutés en placeholder, à remplir lors de sessions futures :

- **Fiche de résumé** (portée Séquence) — édition par séquence des fiches
  flashcard (cf. modèle `N10_Fiches_de_resume.tex`)
- **Récap cours** (portée Niveau) — livret annuel agrégeant notions/méthodes
- **Récap exos** (portée Niveau) — livret annuel d'exercices avec corrigés
  (cf. modèle `N10_Exercices_corriges.tex`)
- **Plans de travail** (portée Niveau) — plan annuel + un par séquence
  (cf. modèle `N10_Plan_de_travail.tex`)

## Détails d'implémentation

### Mémorisation localStorage

Trois clés utilisées :
- `atl-portee-active` : portée active (`sequence`/`niveau`/`cycle`/`generaux`)
- `atl-portee-sel-sequence` : JSON `{niveau, sequence}` pour la portée Séquence
- `atl-portee-sel-niveau` : JSON `{niveau}` pour la portée Niveau
- `atl-portee-sel-cycle` : JSON `{cycle}` pour la portée Cycle

Au reload, l'état est restauré automatiquement.

### Suppression du sélecteur "Tous les niveaux/séquences"

D'après votre choix, on **force** un niveau et une séquence — plus de
"Tous". Valeurs par défaut : `N10` / `S01` pour la portée Séquence.

### Synchronisation avec les variables existantes

Les variables globales `ATL_FILTRE_NIVEAU` et `ATL_FILTRE_SEQ` (utilisées
par `atelFiltrerAtomes`) sont **automatiquement pilotées** par les
sélecteurs de portée. Les listes des sidebars Exercice/Notion/Méthode se
filtrent donc comme avant, sans changement de leur logique interne.

Pour la portée Cycle : les selects `atl-theme-cycle-sel` et
`atl-seqcycle-cycle-sel` (cachés mais conservés en DOM pour compatibilité
avec `ateliers_theme.js` et `ateliers_seqcycle.js`) sont synchronisés
avec le sélecteur de portée et déclenchent leur événement `change`
habituel pour recharger les listes des sidebars.

### Auto-bascule de portée

Si `atelSwitch('exercice')` est appelé depuis l'extérieur (par exemple
ouverture directe d'un atome via lien) alors qu'on est dans une autre
portée, la portée bascule automatiquement vers celle qui contient
l'atelier demandé. Évite l'incohérence visuelle (boutons de portée Niveau
visibles alors qu'on regarde un exercice).

### Suppression des barres de filtres internes

Les 3 barres `atl-filtre-bar` des sidebars Exercice/Notion/Méthode ont
été supprimées (les sélecteurs de portée les remplacent). Les 2 barres
Cycle de Thème et Découpage sont **cachées** (`display:none`) mais leur
DOM est préservé pour la compatibilité.

## Comportement attendu côté UX

- **À l'ouverture de l'onglet Ateliers** : restauration de la portée
  mémorisée (par défaut Séquence), du premier atelier de cette portée,
  et des sélections précédentes.
- **Cliquer sur un onglet de portée** : fait apparaître ses ateliers,
  ses sélecteurs (avec les valeurs mémorisées), et active son premier
  atelier.
- **Changer un sélecteur** : sauvegarde immédiate en localStorage,
  re-filtrage des listes courantes, sans toucher aux sélections
  des autres portées.
- **Reload navigateur** : tout est restauré (portée + sélections).

## Tests

### Tests backend

`pytest tests/test_routes.py tests/test_services.py tests/test_R1_routes.py`
→ **103 passed**, aucune régression.

### Tests fonctionnels frontend (jsdom)

J'ai vérifié manuellement avec jsdom :
- Switch portée → boutons et groupes correctement basculés
- Sélecteurs présentés selon la portée (2 pour séquence, 1 pour niveau, 1 pour cycle, 0 pour généraux)
- Changement utilisateur du sélecteur → mémorisation localStorage OK
- Reload (nouvelle instance jsdom + import localStorage) → portée
  et sélections restaurées
- Auto-bascule de portée via `atelSwitch` → fonctionne

### Validation visuelle à faire de votre côté

Pas d'environnement avec navigateur ici, donc à valider par vous :
- Mise en page (espacements, lisibilité, alignement des sélecteurs à droite)
- Comportement réel des sidebars Notion/Méthode/Exercice quand on change
  niveau ou séquence
- Comportement des panneaux Thème et Découpage quand on change le cycle

## Fichiers livrés

- `templates/index.html` : barre de navigation refondue + 4 placeholders
- `static/app.js` : nouvelle logique de portée

## Hors scope (à faire plus tard)

- **Contenu des 4 ateliers placeholders** (Fiche de résumé, Récap cours,
  Récap exos, Plans de travail) — le plus gros chantier reste à faire,
  mais désormais ces ateliers ont leur place dans l'UI
- **Corrigés Scratch S14 N12** (A02 = bataille navale, E02 = Euclide,
  E03 = RSA) — toujours en attente d'une session dédiée
- **Migration N11/N12** des notions/méthodes (suite v0.9 prévue à la
  session 1 de la v0.10)
- **Nettoyage du paramètre `racine_sources`** de `generer_tex_atome`
  (devenu inutile depuis le fix cache USB)

## Pour reprendre

Au prochain démarrage, dire :
> « Reprenons la v0.10. Les ateliers sont réorganisés en 4 portées
> (Séquence / Niveau / Cycle / Généraux). Le prochain chantier est
> [au choix] : Récap cours / Récap exos / Plans de travail / Fiche de
> résumé / Scratch S14. »
