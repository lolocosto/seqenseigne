# Redémarrage v0.51.13 — Corrections après la bascule, tuiles du tableau de bord

## Décisions (validées)

- **Résidus retirés** des deux bases, contenu sauvegardé en JSON
  (`sauvegardes\retrait_residus_<date>.json`) : `items_texte` (remplacée par
  `atome_sections` en v0.6.4) et `objectifs_v2` (remplacée par `objectifs`
  en v0.14.7). La migration v0.15.0.1 (réconciliation objectifs ←
  objectifs_v2), à l'origine du message « FOREIGN KEY constraint failed »
  de la bascule, est retirée. Une table encore visée par une clé étrangère
  n'est pas retirée (signalé au démarrage).
- **Bascule** : le ménage final ne rouvre plus la base (plus de faux message
  « tables de l'autre côté non vides, gardées »).
- **Système › Base de données** : chaque appli n'affiche que ses compteurs
  (conception côté atelier, suivi côté classe ; tout en profil complet).
- **Écran Échanges** (Système › Administration › Échanges, les deux applis) :
  détail de la publication (atelier : liste à cocher, journal) ou du retour
  d'usage (classe), boîte aux lettres, identité et correspondant, et les
  imports à la main (retours d'usage côté atelier, référentiels côté classe),
  qui n'ont plus de sous-onglet à eux.
- **Tuiles simplifiées** : Publication (comptes à jour / à publier / en
  attente de retour / à vérifier, dernier paquet, boîte aux lettres, « Publier
  les N à publier », Détails) ; Retour d'usage (référentiels importés et
  utilisés, dernier paquet reçu, dernier retour envoyé, boîte aux lettres,
  « Créer le retour d'usage n° N », Détails).
- **Nouvelles tuiles de l'appli de classe**, dans l'ordre : Journée, Classes,
  Établissements, Retour d'usage. « Séances de la semaine » est remplacée par
  Journée.
  - Journée : grille du jour sur le modèle de Planification hebdo
    (créneaux de la première à la dernière séance, pastilles des classes,
    type de séance, indisponibilité, vacances, férié) ; clic → détail de la
    séance ; ‹ › (week-end sauté, bornes de l'année), « Aujourd'hui » ; lien
    vers Planification hebdo à la semaine du jour affiché.
  - Classes (année active) : nom → Paramétrage › Classes (liste des
    élèves) ; effectif ; lien « plan » si un plan de classe est saisi →
    Planification › Plans de classe sur la classe.
  - Établissements : salles non archivées ; lien « plan » si le plan de la
    salle a des places → éditeur du plan (modifiable).

## Code

- `services/retraits.py` (`retirer_residus`), `persistence/sqlite_store.py`
  (migration v0.15.0.1 retirée), `services/bascule.py` (`_finir`).
- `services/tableau_bord.py` (`etablissements_et_salles`,
  `classes_de_l_annee`), `routes/tableau_bord.py`
  (`/api/tableau-bord/etablissements`, `/api/tableau-bord/classes`, profil
  classe), `services/profils.py`.
- `static/tdb_tuiles.js` (nouveau : Journée, Classes, Établissements),
  `static/tableau_bord.js` (résumés ; détails rendus dans l'écran Échanges),
  `static/echanges.js` (`echangesInit`), `static/import_publication.js`,
  `static/app.js` (sous-onglet Échanges, compteurs de la base),
  `static/app.css`, `templates/index.html`.
- La route `/api/tableau-bord/seances-semaine` reste (plus affichée).
- Tests : `tests/test_v0_51_13_tableau_bord.py`,
  `tests_js/tdb_tuiles.test.js` ; `tests/test_v0_14_7_renommage.py`
  (réconciliation remplacée par le retrait), `tests/test_v0_51_11_retraits.py`,
  `tests/test_v0_51_12_bascule.py` (pas de faux message).
