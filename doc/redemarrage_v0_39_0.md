# Redémarrage v0.39.0 — Plans de classe hebdomadaires

Troisième livraison du chantier « plans de classe »
(`doc/cadrage_plans_de_classe.md`).

## Décisions validées

- Onglet **Planification › Plans de classe** : choix de la classe, navigation
  par semaine, salle (sélecteur seulement si la classe a cours dans plusieurs
  salles cette semaine-là). Salles proposées = salles des cours **en classe
  entière** de la semaine (demi-groupes : plus tard, noté en ROADMAP).
- Un plan par (classe, salle, semaine). Semaines passées : lecture seule ;
  semaine en cours : corrigeable ; semaines futures : préparables.
- **Reconduction** : une semaine sans plan affiche la dernière semaine saisie
  de la même classe dans la même salle (« Reconduit du … ») ; imposés repris,
  libres **à confirmer** (grisés, en italique) ; un clic sur l'élève le
  confirme, « Tout confirmer » confirme tout. Rien n'est écrit tant qu'on ne
  modifie pas. « Annuler le plan de la semaine » revient à la reconduction.
- **Saisie** : clic élève puis place (place occupée → échange), glisser-déposer
  entre liste et plan ; déposé dans la liste = retiré. Placé = **libre** par
  défaut, case « Placé par l'enseignant (imposé) » dans la fiche. Chaque action
  est enregistrée aussitôt. Échap désélectionne.
- **Aléatoire pur** : imposés conservés, tous les autres répartis au hasard sur
  les places restantes, en imposé.
- Élève sorti : disparaît ; élève arrivé : non placé ; numéro de place absent
  de la version de la salle de la semaine : non placé + avertissement.
- Étiquette « Prénom N. » (plus de lettres du nom si prénoms identiques).
- **Impression** (LaTeX/TikZ, une page par classe) : plan avec noms si au moins
  un élève est placé (imposés en gras, à confirmer en italique, places vides
  numérotées en gris, non placés listés) ; sinon plan numéroté seul.
  « Imprimer ce plan » ou « Imprimer les plans de la salle » (toutes les
  classes qui y ont cours cette semaine).

## Code

- Migration additive : `plans_classe`, `plan_placements` (schéma porté par
  `services/plans_classe.py`).
- `services/plans_classe.py` : `lire`, `enregistrer`, `reinitialiser`,
  `aleatoire` (pure), `salles_de_la_semaine`, `eleves_de_la_semaine`,
  `etiquettes`, `plans_de_la_salle`.
- `services/plan_classe_pdf.py` : génération TikZ + compilation pdflatex
  (sans paquet hors base : article, inputenc, fontenc, geometry, tikz).
- `routes/plans_classe.py` : `/api/plans-classe` (GET/PUT/DELETE),
  `/salles`, `/aleatoire`, `/pdf`.
- `static/plans_classe.js` + onglet dans `templates/index.html` et
  `static/app.js` (atelier `plans`, rechargé au changement d'année ou
  d'établissement).

## Tests

- pytest `tests/test_v0_39_0_plans_classe.py` (17), dont compilation PDF réelle.
- Parcours navigateur (6EME3, 23 élèves, salle 302) : placement par clic, par
  glisser, aléatoire, semaine suivante reconduite, bascule imposé/libre,
  libres à confirmer, avertissement de place disparue, PDF de la salle.

## Déploiement

Décompresser ;
`..\outils\python\python.exe .\outils\verifier_md5.py --racine . --manifest MANIFEST.md5`.
Redémarrer (migration automatique), Ctrl+Shift+R. Prérequis : salles
renseignées dans l'EdT (v0.38).
