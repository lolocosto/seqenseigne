# Redémarrage v0.47.2 — Délai de réalisation du travail

Retour d'usage sur v0.47.x : le délai proposé (prochaine séance, 3 jours,
1 semaine) était trop figé.

Correctif (`static/travail.js`, `static/app.css`) — « Donner du travail » :
- « à la prochaine séance » ;
- « dans … jour(s) » + nombre entier (1 à 60) ;
- « dans … semaine(s) » + nombre entier ;
dans les deux derniers cas, l'échéance est la première séance de la classe
au moins x jours / x semaines après (et, pour un absent, après la date où il
a reçu le travail). Côté serveur, rien ne change : le délai est transmis en
jours (`delai_jours`, semaines × 7).

Parcours navigateur : « Exposé » à rendre dans 2 semaines, donné le 05/10 →
échéance le 19/10.
