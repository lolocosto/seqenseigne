# Redémarrage v0.22.2 — Placement des parties : début auto, fin facilitée, période héritée

Trois améliorations du placement des parties dans l'atelier Progression.
Purement front (2 fichiers).

## 1. Date de début automatique

Quand on pose une partie (clic sur une partie non encore placée), sa date de
début est positionnée d'emblée sur le **premier lundi disponible** :

- le **premier lundi de l'année scolaire** si aucune partie n'est encore
  positionnée ;
- sinon, le **premier lundi (hors semaine entièrement en vacances) strictement
  après la fin du dernier créneau daté**.

Le créneau est donc créé daté (début = fin = ce lundi), prêt à ajuster, au lieu
d'être « à dater ». Un message confirme la date (« Créneau ajouté au jj/mm »).

## 2. Sélecteur de date de fin positionné sur le début

À l'ouverture du détail d'un créneau, le sélecteur de **date de fin** reçoit un
`min` égal à la date de début. Le calendrier natif s'ouvre alors au bon mois
(plus besoin de faire défiler jusqu'au semestre 2 pour les séquences tardives),
et une fin antérieure au début est empêchée. Le `min` est recalé si la date de
début change.

## 3. Période héritée

À la pose d'une partie, la **période** (Semestre 1 / Semestre 2 / Fin d'année)
est reprise de celle du **dernier créneau daté**. On enchaîne ainsi les
séquences d'un même semestre sans re-saisir la période à chaque fois.

## Fichiers

- `static/atelier_progression.js` : `_prochainLundiDisponible`,
  `_periodeDerniereSequence`, `_dateFrCourte`, `_syncMinFin` ; `poserPartie`
  crée le créneau daté + période héritée ; `selectionnerCreneau` fixe le `min`
  du champ fin.
- `templates/index.html` : `onchange` du champ début appelle aussi `_syncMinFin`.

## Tests

- vitest : 193 passed (0 régression). Syntaxe OK.
- Logique vérifiée : progression vide → 1er lundi de l'année ; après une partie
  finissant le 02/10 → lundi 05/10, période héritée « Sem1 ».

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Purement front. Se déploie
par-dessus la v0.22.1.
