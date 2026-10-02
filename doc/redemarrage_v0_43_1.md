# Redémarrage v0.43.1 — Séances du jour toujours visibles (Début de séance)

Retour d'usage : la liste des séances n'apparaissait pas (elle n'était
affichée que si la classe sélectionnée avait plusieurs séances dans la
journée), ni après un changement de date.

Correctif (`static/seance.js`, `templates/index.html`, `static/app.css`) :
- ligne « Séances du jour » toujours affichée sous l'en-tête : **toutes les
  classes** du jour choisi (« M1 · 6EME3 », « M2 · 4EME4 »…), séance affichée
  en surbrillance, séance en cours bordée de vert, séances terminées grisées ;
  « Aucun cours le jj/mm » sinon ;
- un clic ouvre la séance correspondante, même si sa classe n'est pas
  proposée par le sélecteur Classe (filtré par niveau) ; un choix dans le
  sélecteur Classe reprend la main ;
- la liste est rechargée au changement de jour et à « Séance en cours ».

Pas de changement côté serveur (route `GET /api/seance/jour` sans
`classe_id`, déjà livrée en v0.43.0).
