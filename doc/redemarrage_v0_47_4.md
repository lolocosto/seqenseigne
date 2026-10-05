# Redémarrage v0.47.4 — Sélecteurs de Mises en route et filtre des classes

Retour d'usage (suite de v0.47.3) : l'onglet Planification › Mises en route
n'avait pas de sélecteur Niveau ; la liste des classes restait filtrée sur le
niveau choisi dans un autre onglet, d'où l'obligation d'en changer ailleurs.

Corrections (`static/app.js`, `static/mer.js`) :
- **Mises en route** : sélecteurs Établissement, **Niveau**, Classe ; le
  niveau filtre la liste des classes ET la table d'activation des MER ; un
  changement de niveau recharge l'écran.
- `buildClasseSel` :
  - le filtre Niveau ne s'applique que si l'onglet affiche ce sélecteur ;
  - l'établissement utilisé est celui du sélecteur affiché
    (`#suivi-etab-global`, `SUIVI_ETAB_ACTIF`) et non plus `#prog-sel-etab`
    (masqué hors Progression principale) : la liste des classes pouvait
    montrer des classes d'un autre établissement que celui affiché.
- Changement d'**année** ou d'**établissement** global : Mises en route et
  Progression de MER rechargent la liste des classes (de la bonne année) et
  leur contenu (ils n'étaient pas rafraîchis).

Comprend la v0.47.3 (refiltrage à l'ouverture et au changement de niveau).

Vérifié dans un navigateur : Mises en route, Hautes Ourmes N11 → 4EME3,
4EME4 (liste et table) ; N09 → 6EME3, 6EME8 ; Progression de MER cohérente.
vitest 225 réussis ; pytest 4129 réussis.
