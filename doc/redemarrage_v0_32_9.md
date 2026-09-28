# Redémarrage v0.32.9 — Correctif liste docs vide + redimensionnement fonctionnel

Corrige deux points de la v0.32.8.

## Bug 1 — liste des documents à distribuer vide

`progDocsCharger` faisait un `return` prématuré : la ligne
`const bloc = document.getElementById('prog-docs-saisie')` avait été supprimée
lors d'une édition précédente, donc `bloc` était `undefined` → `if (!bloc)
return` → le sélecteur n'était jamais rempli. Restaurée.

Vérifié : à la sélection d'un créneau (ex. S03), le sélecteur contient bien
« Livret de séquence — S03 » et « Planches de cartes d'automatisme — S03 », plus
les documents annuels.

## Bug 2 — panneau non réductible

`resize: horizontal` (v0.32.8) plaçait la poignée en bas-droite : inutilisable
pour réduire un panneau collé à droite. Remplacé par une vraie **poignée de
redimensionnement** (drag) entre le calendrier et le panneau détail : on la tire
horizontalement (vers la gauche pour élargir le détail, vers la droite pour
l'inverse). Largeur bornée (240px – 70vw), mémorisée par session
(localStorage), et poignée visible uniquement quand le détail du créneau est
affiché.

## Fichiers

- `static/progression_doc.js` : `bloc` restauré ; poignée de redimensionnement
  (`progPoigneeStart` + move/stop + restauration) ; `progSyncPoignee`.
- `static/atelier_progression.js` : appel de `progSyncPoignee` aux
  affichages/masquages du détail.
- `templates/index.html` : élément `prog-poignee` entre calendrier et détail.
- `static/app.css` : `.prog-poignee` (masquée par défaut) ; `.prog-detail`
  sans resize CSS.

## Tests

- `node --check` (exit 0) sur les deux JS. vitest : 193 passed. Remplissage du
  sélecteur vérifié en simulation (ctx S03 → docs remontent).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.32.8.
