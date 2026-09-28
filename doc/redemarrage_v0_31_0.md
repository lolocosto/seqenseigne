# Redémarrage v0.31.0 — Filtre « Non rattachés » dans les ateliers d'atomes

Ajoute un filtre « Non rattachés » aux 5 ateliers d'atomes (exercice, notion,
méthode, fiche, carte) : afficher les atomes qui ne sont liés à aucun objectif
(pas de pastille « Sxx obj yy »). Socle pour la future tuile « Éléments non
rattachés » du tableau de bord (v0.31.1).

## Définition du rattachement (5 types)

Un atome est **rattaché** s'il est lié à au moins un objectif ; **non rattaché**
sinon. Les liens sont déjà calculés par le service (`enrichir_liste_atomes` →
champ `liens` de chaque atome), qui couvre les 5 types :
- exercice, notion, carte : tables de liaison N-N (`objectif_exos`,
  `objectif_notions`, `objectif_cartes`) ;
- fiche : `fiches_resume.objectif_id` ;
- **méthode** : rattachement 1-1 via `objectifs.methode_id` (pas de table
  dédiée — une méthode = un objectif).

Aucun changement de service/route nécessaire : le champ `liens` distingue déjà
rattaché (`liens` non vide) de non rattaché (`liens` vide).

## Filtre dans les ateliers

- Un bouton **« Non rattachés »** est ajouté à la barre de filtres de chaque
  atelier (à côté de Tous / En cours / Validé). C'est un **toggle**
  (clic = activer, second clic = désactiver).
- Il pose la variable globale `ATL_FILTRE_RATTACHEMENT` et re-rend la liste. Le
  filtrage (dans `filtrerListe`) ne garde que les atomes dont `liens` est vide.
- Se cumule avec le filtre d'état (ex. « Non rattachés » + « En cours »).
- Fonctionne pour les 5 ateliers, carte comprise (elle hérite du filtre via
  `super.filtrerListe`).

## Fichiers

- `static/atelier_editeur.js` : `filtrerListe` applique le filtre non-rattaché.
- `static/atelier_etat_edition.js` : `atelAtomeFiltrerRattachement` (toggle +
  re-rendu par type, carte incluse).
- `templates/index.html` : bouton « Non rattachés » dans les 5 ateliers.

## Tests

- `node --check` (exit 0) sur les 3 fichiers JS. vitest : 193 passed. 5 boutons
  présents. Logique de filtrage vérifiée (liens vides → non rattachés).
- Vérifié sur la base réelle : N10 → exercices 26 non rattachés, notions 27,
  cartes 9, méthodes/fiches 0 (toutes rattachées).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.30.3.2.

## Suite (v0.31.1)

Tuile « Éléments non rattachés » du tableau de bord (comptage par niveau/type) +
action : cliquer un type ouvre l'atelier, toutes séquences, filtre
« Non rattachés » pré-activé (comme la tuile « atomes en cours »).
