# Redémarrage v0.43.2 — Début effectif des mises en route, MER « non faite »

Retour d'usage : les automatismes ont démarré tard dans l'année, ce qui
décalait tout le planning ; et une mise en route peut ne pas être faite
« sans raison particulière » (hors indisponibilité).

## Décisions validées

- **D1 — Début effectif des mises en route**, par classe × année
  (`affectation_config.mer_date_debut`), saisi dans Planification › Mises en
  route (« Début effectif des mises en route », bouton « Dès la rentrée »
  pour l'effacer). Les séances antérieures ne comptent pas : la séance n° 1
  (enveloppes de la séance 1, ou séance 1 de la progression de MER) est la
  première à partir de cette date.
- **D2 — « Mise en route non faite »** dans Suivi › Début de séance : case +
  commentaire facultatif. Cocher crée l'exception MER de la date (motif =
  commentaire, ou « Mise en route non faite ») ; décocher la supprime ;
  recocher met à jour le motif. La mise en route prévue glisse à la séance
  suivante et toute la suite se décale (même mécanisme que les exceptions
  existantes, visibles et supprimables dans Mises en route).
- **D3 — Limite assumée** : une exception porte sur une date ; deux séances
  de la classe le même jour sont concernées ensemble.
- **D4 — Affichage** : case cochée → « Mise en route non faite — <motif> —
  reportée à la séance suivante » ; avant le début effectif → « Mises en
  route à partir du jj/mm ».

## Code

- `services/affectation.py` : `Neutralisations` (ensemble des dates
  d'exception dont le test d'appartenance couvre aussi toute date antérieure
  au début effectif) renvoyé par `dates_exceptions` → tous les consommateurs
  (`repartir_mer`, `affecter` : Leitner, progression de MER, planning affecté,
  planification hebdo, début de séance) appliquent le début effectif sans
  changer leurs appels ; `lire_date_debut`, `definir_date_debut`,
  `exception_du_jour`, `marquer_non_faite`.
- Migration : colonne `affectation_config.mer_date_debut`.
- `routes/affectation.py` : la config renvoie / accepte `date_debut` (un
  corps qui ne porte que la date ne modifie pas le mode).
- `services/seance.py` + `routes/seance.py` : `mise_en_route` enrichie
  (`active`, `non_faite`, `date_debut`), `PUT /api/seance/mer-non-faite`.
- `static/mer.js`, `static/seance.js`, `templates/index.html`, `static/app.css`.

## Tests

- pytest `tests/test_v0_43_2_mer_debut_non_faite.py` (7) : sémantique des
  neutralisations, décalage de la numérotation par le début effectif, date
  invalide, config sans toucher au mode, cocher / décaler / recocher /
  décocher, routes.
- Suite complète : pytest 4096 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur : 4EME3 lundi 05/10 M4, séance 13 (enveloppe 1) → non
  faite (« Exercice incendie ») → reportée ; décocher la rétablit.
