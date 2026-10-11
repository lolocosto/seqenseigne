# Redémarrage v0.51.5 — Thèmes des référentiels externes et MER

Première des deux livraisons « structures modèles » (la seconde, v0.51.6,
crée un référentiel à partir d'un modèle ; cadrage dans `doc/ROADMAP.md`).
Jusqu'ici l'éditeur des référentiels externes et MER n'avait pas de thèmes :
le bloc `structure.themes` du JSON publié était vide.

## Décisions (validées)

- Un référentiel principal **et** un référentiel de MER ont des thèmes,
  aussi nécessaires l'un que l'autre ; ils se recouvrent en général, sans
  obligation (ex. toute la géométrie en MER).
- Les séquences d'un même thème sont **regroupées** dans le référentiel,
  dans l'ordre des thèmes ; les séquences sans thème viennent en dernier
  (alerte non bloquante, comme « aucun thème »).
- Thème : code (A, B…), nom, couleur (slugs partagés avec les internes :
  nombres, grandeurs, geometrie, donnees, algorithmique, noir_gris), ordre
  (nouvelle colonne `referentiel_themes.ordre`).
- Codes de thème recalculés d'après le rang tant que le référentiel est en
  conception (même règle que les codes de séquence, v0.51.4) ; ensuite
  figés, un nouveau thème prend la première lettre libre.
- Opérations : ajouter, renommer / recolorer (toujours), monter / descendre
  (le thème emporte ses séquences), supprimer (ses séquences passent « sans
  thème », après confirmation) ; changer le thème d'une séquence (refusé si
  elle est commencée) la place à la fin de son nouveau thème ; une séquence
  se déplace à l'intérieur de son thème ; « + séquence » dans chaque groupe.

## Code

- `services/referentiel_principal_externe.py` : `COULEURS_THEMES`,
  `lister_themes`, `ajouter_theme`, `modifier_theme`, `deplacer_theme`,
  `supprimer_theme`, `affecter_theme`, `_ordonner_sequences`,
  `_recoder_themes` ; `ajouter_sequence(…, theme_code)` ; `lire` expose
  `themes`, `alertes_themes`, `couleurs_themes`.
- `routes/referentiel_principal_externe.py` : `…/<rid>/themes` (POST),
  `…/themes/<code>` (PUT, DELETE), `…/themes/<code>/deplacer`,
  `…/sequences/<code>/theme` (PUT).
- `services/format_referentiel.py`, `persistence/sqlite_store.py` : thèmes
  triés par ordre ; `services/import_publication.py` : ordre importé.
- `static/referentiel_pe.js`, `static/app.css` : bloc Thèmes, groupes par
  thème, sélecteur de thème par séquence.
- Tests : `tests/test_v0_51_5_themes.py`.
