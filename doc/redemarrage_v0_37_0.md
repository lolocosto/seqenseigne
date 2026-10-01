# Redémarrage v0.37.0 — Salles et éditeur libre de plan de salle

Première livraison du chantier « plans de classe » (cadrage complet :
`doc/cadrage_plans_de_classe.md`).

## Contenu

- **Modèle** (migration additive, `persistence/sqlite_store.py`, schéma porté
  par `services/salles.py`) : `salles`, `salle_versions`, `salle_places`.
- **Service** `services/salles.py` : CRUD, archivage, versions datées (lundi),
  statuts passée / en vigueur / future, numérotation stable
  (`salles.prochain_numero`, jamais réattribué), règles « salle utilisée ».
  `salle_est_utilisee` lit `edt_creneaux.salle_id` si la colonne existe
  (v0.38) : en v0.37.0 aucune salle n'est utilisée, tout reste éditable.
- **Routes** `routes/salles.py` :
  `GET/POST /api/etablissements/<id>/salles`, `PUT/DELETE /api/salles/<id>`,
  `GET /api/salles/<id>/versions`, `GET/PUT /api/salles/<id>/plan`,
  `DELETE /api/salles/versions/<id>`.
- **Fusion d'établissements** : les salles suivent ; refus (`conflit_salle`)
  si un même nom de salle existe des deux côtés.
- **Interface** : bouton « Salles » sur la carte établissement (liste :
  renommer, Plan, archiver/réactiver, supprimer) ; éditeur plein écran
  `static/salles.js` (SVG) : ajout place / îlot de 2 / îlot de 4, clic = îlot,
  Alt+clic = place seule, Maj+clic = ajout à la sélection, glisser avec
  aimantation bord à bord, flèches (Maj = 10 cm), R / Maj+R = ±5°, ⟳ 90°,
  grouper/dégrouper, Suppr ; tableau dessiné en haut ; sélecteur de versions ;
  « Préparer une nouvelle version » (salle utilisée) ; garde-fou des
  modifications non enregistrées.
- **Logique pure** `static/salles_pur.js` (window.SallesPur) : géométrie,
  rotation d'îlot autour de son centre, aimantation dans le repère d'une place
  tournée (parallèle ou perpendiculaire à 1° près, seuil 8 cm).
- **Import TikZ** : `services/plan_salle_tikz.py` (mini-interpréteur
  tkz-euclide : DefPoints, translation, rotation, DrawPolygon ; 1 unité = 10 cm ;
  îlots = quadrilatères qui se touchent) et outil
  `..\outils\python\python.exe outils\importer_plan_salle_tikz.py plan_salle_302.tex --salle 302 [--etab …] --apply`
  (dry-run par défaut). Résultat sur la 302 : 33 places, îlots 6-4-4-4-4-4-3-2-2.

## Conventions

Unité cm, repère écran (y vers le bas, tableau en haut), (x, y) = centre de la
place, angle du grand côté en degrés sens horaire dans [0, 360). Mêmes
conventions côté Python et JS.

## Tests

- pytest `tests/test_v0_37_0_salles.py` (30) — fixture `tests/fixtures/plan_salle_302.tex`.
- vitest `tests_js/salles_pur.test.js` (18).
- Parcours vérifié dans un navigateur : import 302, glisser + aimantation,
  ajout d'îlot, rotation, enregistrement (numéros 34+), salle simulée
  « utilisée » (lecture seule, nouvelle version au 05/10, suppression refusée).

## Déploiement

1. Décompresser ; `python -m outils.verifier_md5`.
2. Redémarrer l'appli (migration automatique), Ctrl+Shift+R.
3. Import de la 302 (copie de la base d'abord) :
   `python -m outils.importer_plan_salle_tikz chemin\plan_salle_302.tex --salle 302`
   puis la même commande avec `--apply`.

## Dette relevée (non traitée)

- La fusion d'établissements ne migre ni la grille horaire ni l'EdT
  (préexistant).
