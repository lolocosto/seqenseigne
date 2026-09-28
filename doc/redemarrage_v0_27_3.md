# Redémarrage v0.27.3 — Décalage : logique métier rapatriée côté serveur

Rapatrie le calcul du décalage de progression (semaines neutralisées) du client
(JS) vers le serveur (Python). Le JS ne calcule plus la règle métier : il
demande le résultat et l'affiche. Premier pas du chantier « logique métier
intégralement côté serveur ».

## Principe

Frontière retenue : les **règles de gestion** au serveur ; le JS garde la
**présentation** (dessin du calendrier, couleurs, marqueurs).

## Ce qui change

- **Nouveau service** : `services/decalage_progression.calculer_pour_classe`
  applique les décalages (semaines neutralisées) et renvoie les créneaux
  recalculés + la liste des semaines neutralisées et leur motif.
- **Nouvelle route** : `GET /api/classes/<id>/progression-realisee` — retourne
  ces données pour une classe (progression de son niveau, décalages, vacances).
- **Client allégé** (`atelier_progression.js`) : en vue « réalisée » d'une
  classe, l'atelier charge la progression réalisée depuis le serveur et se
  contente d'afficher (transparence des semaines neutralisées, marqueur
  « ⤵ Décalage : <motif> »). Les méthodes de calcul JS
  (`_appliquerNeutralisations`, `_semainesNeutralisees`, etc.) sont supprimées.
- **Dette morte retirée** : la fonction globale `appliquerDecalagesJS`
  (`app.js`) est supprimée (plus de logique de décalage dupliquée en JS).

Le comportement visible est identique à v0.27.2 (mêmes résultats), mais la règle
n'existe plus qu'à un seul endroit.

## Inventaire pour la suite

`doc/inventaire_logique_metier_js.md` recense la logique métier qui subsiste en
JS (ex. `_semainesTouchees`, `anneeScolaireCourante`) et propose une méthode de
migration écran par écran. À traiter dans les versions suivantes.

## Fichiers

- `services/decalage_progression.py` : `lundis_annee`, `calculer_pour_classe`.
- `routes/decalage_progression.py` : route `progression-realisee`.
- `static/atelier_progression.js` : chargement serveur + affichage (plus de
  calcul).
- `static/app.js` : suppression de `appliquerDecalagesJS`.
- `doc/inventaire_logique_metier_js.md` (nouveau).

## Tests

- `tests/test_v0_21_4_decalage_progression.py` : 6 passed (cas A/B/C, union,
  copie). vitest : 193 passed. Route vérifiée (200, créneaux +
  semaines_neutralisees). Calcul serveur vérifié sur le cas réel S03
  (14 → 02/10 ; semaines 07 « Sortie », 21 « Voyage à Nantes »).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.27.2. Comportement identique, logique désormais serveur.
