# Redémarrage v0.32.6 — Association de documents : UI de saisie + affichage

Deuxième volet : l'interface pour associer des documents à un créneau de la
progression, et l'affichage des documents prévus dans la Planification hebdo.
S'appuie sur le socle backend de la v0.32.5.

## Saisie (atelier Progression principale)

Dans le détail d'un créneau (après sélection dans le calendrier), une section
« Documents à distribuer » :
- liste des documents déjà associés à ce créneau (avec leur rang de séance et un
  bouton retirer) ;
- un sélecteur groupé (Cette séquence / Séquence suivante / Documents annuels) +
  un champ « séance n° » + bouton « associer » ;
- une case « inclure la séquence suivante » qui recharge le sélecteur.

Les documents proposés couvrent les sources existantes : référentiel principal
interne (dont les **planches de cartes d'automatisme**), référentiels externes
(principal et MER), docs annuels.

## Affichage (Planification hebdo)

Le détail d'une séance (au clic) affiche désormais les **documents à
distribuer** : les associations posées au niveau, pour le créneau et le rang de
séance correspondant à cette date/classe. « Aucun document prévu » sinon.

## Fichiers

- `templates/index.html` : section « Documents à distribuer » dans le créneau ;
  inclusion de `progression_doc.js`.
- `static/progression_doc.js` (nouveau) : chargement, sélecteur, ajout,
  suppression.
- `static/atelier_progression.js` : appel de `progDocsCharger` à la sélection
  d'un créneau.
- `services/planification_hebdo.py` : `detail_seance` renvoie
  `docs_a_distribuer`.
- `static/planification_hebdo.js` : affichage des documents dans la modale.

## Tests

- vitest : 193 passed (17 fichiers). Association vérifiée en base (stockage +
  jointure créneau/rang). Détail de séance renvoie `docs_a_distribuer`
  (s'active quand l'EdT projette la séance au bon rang, comme la séquence en
  v0.32.2).

## Dettes préexistantes (NON liées à ce delta, non incluses)

- `tests/test_v0_29_0_verso_miroir.py` : importe une fonction supprimée
  (refactor antérieur) → casse la collecte ; à supprimer/réécrire.
- `tests/test_annees_scolaires.py` (2 cas) : attendent « 2025-2026 » en année
  courante, alors que l'appli calcule l'année d'après la date système
  (« 2026-2027 » ici) — tests dépendants de la date, à corriger.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration (table créée en
v0.32.5). Conception › progression : sélectionner un créneau → section
« Documents à distribuer ». Puis Planification hebdo : cliquer une séance montre
les docs prévus.
