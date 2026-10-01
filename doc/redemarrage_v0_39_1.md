# Redémarrage v0.39.1 — Cadenas des élèves imposés

Retour d'usage sur v0.39.0 : le cadenas d'un élève imposé pouvait dépasser de
sa place et être masqué par la place voisine (dessinée après).

Correctif (`static/plans_classe.js`, `static/app.css`) :
- le cadenas est placé à l'intérieur de la place, dans celui de ses quatre
  coins (rentrés de 7 cm) qui est le plus en haut à droite à l'écran, quelle
  que soit la rotation de la place ;
- tous les cadenas sont dessinés dans un calque après les places : aucune
  place voisine ne peut plus les recouvrir.

Pas de changement côté serveur. Vérifié dans un navigateur (21 imposés, salle
302, places tournées). vitest et pytest des plans de classe inchangés.
