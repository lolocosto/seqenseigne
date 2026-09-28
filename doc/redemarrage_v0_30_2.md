# Redémarrage v0.30.2 — Ateliers d'atomes : option « Toutes les séquences »

Étend les 5 ateliers d'atomes (exercice, notion, méthode, carte, fiche) avec une
option « — Toutes les séquences — » dans le sélecteur de séquence : on voit alors
tous les atomes du niveau, groupés par séquence. Socle pour l'action fine de la
tuile du tableau de bord (v0.30.3).

## Contenu

- Le sélecteur de séquence des ateliers d'atomes propose « — Toutes les
  séquences — » (valeur vide), en tête.
- En ce mode : la liste (sidebar) affiche tous les atomes du niveau, **groupés
  par séquence** (sous-titres S01, S02… collants).
- La **création est désactivée** en mode toutes séquences (message explicite) :
  c'est une vue de consultation/finition ; pour créer, choisir une séquence
  précise.
- Le comportement historique (une séquence) est inchangé.

## Couches modifiées

- `services/atomes_liste.py` : `lister_atomes_sequence` — séquence désormais
  optionnelle (vide = toutes séquences du niveau) ; chaque atome porte sa
  `sequence` (pour le regroupement). Requêtes unifiées par type.
- Routes liste (séquence optionnelle) : `routes/atomes.py` (générique),
  `routes/fiches_resume.py`, `routes/cartes_automatisme.py` (routes dédiées).
- `static/atelier_editeur.js` : `chargerListe` (séquence optionnelle),
  `rendreSidebar` (regroupement par séquence), message de création adapté.
- `static/app.js` : `atelRafraichirSelectSequence` ajoute l'option « toutes les
  séquences ».

## Tests

- `tests/test_v0_30_2_toutes_sequences.py` : 3 passed (une séquence ; toutes
  séquences du niveau avec exclusion des autres niveaux ; niveau obligatoire).
- pytest (atomes/liste/carte/fiche) : 1500 passed. vitest : 193 passed.
- Vérifié sur la base réelle, les 5 types en mode toutes séquences (N12 :
  notion 24, méthode 42, exercice 279, carte, fiche 36) et non-régression (une
  séquence : exercice S01 = 13).

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Se déploie
par-dessus la v0.30.1.

## Suite (v0.30.3)

Brancher l'action fine de la tuile « Atomes à finaliser » : cliquer « 279
exercices » (3ème) ouvre l'atelier exercices, toutes séquences, filtre « en
cours » pré-activé.
