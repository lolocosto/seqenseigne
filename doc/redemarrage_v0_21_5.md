# Redémarrage v0.21.5 — Vue « progression annuelle réalisée » par classe

Deuxième livraison sur l'effet des indisponibilités sur la progression
principale. Rend les décalages visibles et actionnables, selon le vocabulaire
validé :

- **Aucune classe sélectionnée** → « Progression annuelle commune prévue »
  (dates non décalées, comportement d'origine).
- **Une classe sélectionnée** → « Progression annuelle réalisée » (décalages de
  cette classe appliqués à l'affichage).

## Contenu

### Bandeau + sélecteur de classe (dans l'atelier)

Un bandeau au-dessus du calendrier affiche le titre (prévu / réalisé) et un
sélecteur « Vue classe » listant les classes du niveau/année. Le choisir
bascule la vue. Placé dans le panneau de l'atelier (pas dans la barre de
sélecteurs), car il change la *vue* de la progression, pas *quelle* progression.

### Application des décalages (non destructive)

En vue réalisée, les créneaux du calendrier sont décalés par
`appliquerDecalagesJS` (miroir JS de la fonction Python), sans modifier la
progression commune. Cumulatif.

### Panneau « Décalages de la classe »

Sous le bandeau (en vue réalisée) : liste des décalages (date, +N semaines,
motif) avec suppression.

### Décaler depuis une indisponibilité

En vue réalisée, chaque indisponibilité du calendrier porte un contrôle
« décaler [N] sem. ↪ décaler » :
- le décalage part du **début de l'indisponibilité** (ce qui aurait dû être
  travaillé pendant l'indispo glisse, décalant tout ce qui suit) ;
- **N est pré-calculé** = nombre de semaines civiles (lundi→vendredi) touchées
  par l'indisponibilité, et reste **modifiable** dans le champ (une maladie /
  un voyage peut durer plusieurs semaines) ;
- fonctionne pour **toute** indisponibilité (portée « moi » comme « classes ») :
  une absence de l'enseignant peut nécessiter de décaler chaque classe (une par
  une, en visualisant chacune).
- le décalage créé garde `indispo_id` pour la traçabilité.

## Note

Le formulaire de détail d'un créneau édite toujours les dates **réelles** de la
progression commune (pas les dates décalées d'affichage) : on n'édite pas un
décalage via ce formulaire, mais via le panneau des décalages. Les débordements
de fin d'année sont affichés sans être résorbés (roadmap).

## Fichiers

- `templates/index.html` : bandeau prévu/réalisé + sélecteur de classe + zone
  décalages (`prog-vue-bandeau`, `prog-vue-classe`, `prog-decalages`).
- `static/app.js` : `appliquerDecalagesJS` (miroir de la fonction Python).
- `static/atelier_progression.js` : état de vue classe, `_creneauxAffichage`
  (décalés), `_peuplerSelectClasses`, `onVueClasseChange`, `_chargerDecalages`,
  `_majBandeauVue`, `_renderDecalages`, `supprimerDecalage`,
  `decalerDepuisIndispo`, `_semainesTouchees` (pré-calcul), contrôle « décaler »
  sur chaque indispo, appel à l'affichage de la progression.

## Tests

- vitest : 193 passed (0 régression). Syntaxe OK.
- `appliquerDecalagesJS` vérifié identique à la version Python (seuil, cumul,
  non destructif).
- Pré-calcul `_semainesTouchees` vérifié (même semaine → 1 ; à cheval → 2 ; deux
  semaines pleines → 2).
- Flux API vérifié : création d'un décalage depuis une indispo (avec
  `indispo_id`), listing.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration (table
`decalage_progression` déjà créée en v0.21.4). Dans l'atelier Progression :
choisir une classe dans « Vue classe » pour la progression réalisée.

## Suite / roadmap

- Résorption des débordements de fin d'année (supprimer un décalage,
  réorganiser, retirer une séquence).
- Option 2 (progression théorique + réalisée) reste le plan B.
- Chantier MER (v0.22+) : effet automatique des indisponibilités sur la
  progression de MER (décalage de fin pour préserver le nombre de séances).
