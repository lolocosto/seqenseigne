# Redémarrage v0.51.19 — Fiches de résumé : zones d'exemple par zone de texte

## Besoin

Une fiche trop chargée ne laisse plus de place à la boîte « Exemples »
finale (qui remplit le bas de la page). Plutôt que de couper la fiche en
deux (on garde une fiche par objectif), chaque zone de texte peut avoir sa
propre zone d'exemple, et une fiche peut s'étendre sur plusieurs pages.

## Décisions (validées)

- Réorganisation des fiches (changement d'ordre) : abandonnée, devenue
  inutile ; si besoin plus tard, motif ↑/↓ existant pour la cohérence.
- **D1** `atome_sections.exemple_lignes` (NULL = pas de zone), utilisé par
  les fiches seulement ; `fiches_resume.exemple_fin_page` (défaut 1).
  Colonnes ajoutées au démarrage (`fiches_resume.migrer`) et dans
  `schema.sql`.
- **D2** Atelier Fiche : sous chaque zone de texte, « Inclure une zone
  d'exemple » + hauteur en lignes (défaut 6, de 1 à 40, refus 400 sinon) ;
  même présentation que le « Cadre de réponse » des exercices. Pour la
  fiche : « Ajouter une zone exemple jusqu'au bas de page » (cochée par
  défaut).
- **D3** Rendu : boîte « Exemples » de N lignes (espace blanc, pour écrire
  ou tracer) juste après la zone ; les boîtes ne se coupent pas, une boîte
  qui ne tient plus passe à la page suivante. Case de fin de page
  décochée : `\newpage` à la place de la boîte finale (la fiche suivante
  commence toujours sur une nouvelle page). Livret de séquence :
  `\cleardoublepage` entre fiches conservé (fiche de 2 pages = recto-verso).
- **D4** Fiche sans zone et case cochée : rendu strictement identique à
  avant (testé).
- **D5** Limite : une zone de texte plus haute qu'une page reste
  impossible (boîtes non sécables) ; la répartir en deux zones.

## Code

- `services/fiches_resume.py` : `migrer`, `normaliser_exemple_lignes`,
  `ZoneExempleInvalide` ; création / lecture / modification (validation
  avant remplacement des sections).
- `routes/fiches_resume.py` : `exemple_fin_page` (POST, PATCH), erreur 400
  `zone_exemple_invalide`.
- `services/latex_rendu_atome.py` : `Atome.exemple_fin_page`, lecture
  tolérante de `exemple_lignes`, `generer_corps_fiche` (un seul point de
  rendu pour l'atelier, le livret de séquence et le livret de fiches).
- `persistence/sqlite_store.py` (migration), `persistence/schema.sql`.
- `static/atelier_fiche.js`, `templates/index.html`.
- Tests : `tests/test_v0_51_19_fiches_zones_exemple.py` (14),
  `tests_js/atelier_fiche_zones_exemple.test.js` (10).

## Déploiement

Aucun changement de paquet. Les colonnes sont ajoutées au premier
démarrage ; les fiches existantes gardent leur rendu.
