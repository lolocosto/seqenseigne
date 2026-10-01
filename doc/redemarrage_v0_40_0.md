# Redémarrage v0.40.0 — Sexe des élèves, aléatoire mixte, places AESH

Dernière livraison du chantier « plans de classe »
(`doc/cadrage_plans_de_classe.md`).

## Décisions validées

- **Sexe** (M, F ou non renseigné) : colonne `eleves.sexe`. L'import CSV
  (export Pronote) lit la colonne `Sexe` et **complète aussi les élèves déjà
  présents** (nom + prénom, casse ignorée), sans rien changer d'autre ; les
  valeurs non reconnues sont ignorées. Aucune autre colonne n'est lue (date de
  naissance, projet d'accompagnement jamais importés). Saisie manuelle :
  sélecteur M / F / — dans la liste des élèves de la classe (Gestion › Classe).
- **Voisinage** : deux places du même îlot qui partagent un côté (pas la
  diagonale ; une place isolée n'a pas de voisine). Sur la 302 : 31 paires.
- **Aléatoire mixte** : imposés et places AESH conservés ; meilleur de 300
  tirages puis 3 000 échanges entre élèves non imposés, en maximisant le nombre
  de paires garçon-fille voisines ; élèves sans sexe = neutres ; élèves placés
  en imposé. Deux boutons : « Aléatoire » et « Aléatoire mixte ».
- **Places AESH** : réservées par l'enseignant (pastille « + Place AESH » puis
  une place libre ; clic sur une place AESH puis une autre place libre pour la
  déplacer ; « Libérer la place »). Reconduites comme les imposés. Besoin de la
  semaine = maximum du nombre d'AESH des séances de la classe dans la salle
  (détail en info-bulle sur « AESH : n/besoin ») ; avertissement s'il en
  manque. Jamais touchées par l'aléatoire. Les binômes AESH-élève se font en
  plaçant l'élève à côté (imposé) : les accompagnés ne sont pas modélisés.
- **Impression** : « AESH » sur les places réservées.

## Code

- Migration : `eleves.sexe`, table `plan_reservations`.
- `services/eleves_sexe.py` (normalisation, saisie, import) ;
  `routes/classes.py` : import enrichi, `PUT /api/eleves/<id>/sexe`.
- `services/plans_classe.py` : `aesh_de_la_semaine`, réservations dans
  `lire` / `enregistrer` / `reinitialiser`, `voisins`, `partagent_un_cote`,
  `score_mixite`, `aleatoire_mixte` ; `aleatoire(..., reservees=)`.
- `routes/plans_classe.py` : `PUT` avec `reservations`, `aleatoire` avec
  `mode` = `pur` | `mixte`.
- `services/plan_classe_pdf.py`, `static/plans_classe.js`, `static/app.js`
  (sexe dans la liste des élèves), `static/app.css`.

## Tests

- pytest `tests/test_v0_40_0_mixte_aesh.py` (13) — CSV d'import synthétique
  (jamais de vraie liste d'élèves dans le dépôt).
- Parcours navigateur : 6EME3 (23 élèves, 12 F / 11 M), place AESH réservée,
  aléatoire mixte → 15 paires voisines occupées, toutes mixtes.

## Déploiement

Décompresser ;
`..\outils\python\python.exe .\outils\verifier_md5.py --racine . --manifest MANIFEST.md5`.
Redémarrer (migration automatique), Ctrl+Shift+R. Puis réimporter l'export
Pronote de chaque classe pour renseigner le sexe des élèves existants.
