# Redémarrage v0.45.0 — Observables par niveau (Paramétrage › Observables)

Quatrième livraison du chantier « suivi en séance » (ROADMAP).

## Décisions validées

- Deux colonnes **Valoriser** / **Sanctionner**, par **niveau** (sélecteur
  Niveau de la barre ; SEGPA = niveau séparé le jour où il existera).
- Ajout en bas de colonne : observable **commun**, sans période. Ligne :
  libellé, badge « individuel », période, « masqué pour n élèves » /
  « attribué à n élèves ». Désactivés regroupés (repliés), réactivables.
- **Détail** (clic) : libellé (renommage autorisé même après usage),
  portée commun / individuel, période du / au facultative, ordre ↑ ↓,
  désactiver ; **élèves concernés** : « Masqué pour » (commun) ou
  « Attribué à » (individuel), chacun avec période et **commentaire**
  facultatifs ; « + élève » parmi les élèves des classes du niveau (année
  active).
- Changer la portée d'un observable qui a des élèves concernés est refusé
  (« masqué pour » et « attribué à » n'ont pas le même sens).
- **Copier depuis** un autre niveau : observables communs actifs seulement,
  sans exceptions ; un libellé déjà présent n'est pas dupliqué.
- **Aperçu** de la liste effective d'un élève aujourd'hui, limité aux élèves
  qui ont des exceptions.
- Liste effective d'un élève à une date : communs actifs en période, moins
  ceux qui lui sont masqués (en période), plus les individuels actifs en
  période qui lui sont attribués (en période).

## Code

- Migration : tables `observables`, `observable_exceptions` (schéma porté
  par `services/observables.py`).
- `services/observables.py`, `routes/observables.py`
  (`/api/observables…`, dont `/api/observables/effectifs` qui servira à
  l'observation en séance), `static/observables.js`, panneau
  `stab-observables`, `static/app.css`.
- `static/app.js` : ouverture de l'onglet et changement de niveau.

## Correctif au passage

- Début de séance et Observation ont le sélecteur Niveau (v0.42.1), mais un
  changement de niveau ou d'établissement n'y refiltrait pas la liste des
  classes (seul Compétences était aiguillé) : corrigé dans
  `onNiveauChangeGlobal` et `onEtabChangeGlobal`.

## Tests

- pytest `tests/test_v0_45_0_observables.py` (8).
- Suite complète : pytest 4111 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur : 4e — trois observables par section, « Bavardage »
  masqué pour un élève (« Aménagement (PAP) »), « Téléphone sorti »
  individuel attribué à un élève jusqu'au 06/11 (« Fiche de suivi »),
  aperçu de la liste d'un élève.
