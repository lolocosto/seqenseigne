# Redémarrage v0.41.0 — Suite de tests au vert (dettes, lot 1)

Première livraison de la revue des dettes techniques (v0.41.x).

## Décisions validées

- **D1 — Années scolaires** : `test_courante_vide_si_fichier_absent` attendait
  une chaîne vide alors que `courante()` se replie volontairement sur l'année
  calculée depuis la date → renommé `test_courante_repli_sur_la_date_si_fichier_absent`
  et comparé à `annee_scolaire_de_date()`. Le test de route compare au contenu
  de `config/annees_scolaires.json` au lieu de « 2025-2026 » en dur. Ajout d'un
  test paramétré de la bascule en septembre (dates fixes).
- **D2 — `tests/test_v0_29_0_verso_miroir.py` supprimé** : il testait
  `_miroir_horizontal_verso`, fonction Python supprimée quand le miroir des
  versos est passé côté LaTeX (v0.32.4). Il cassait la collecte pytest.
  Suppression manuelle : `MANIFEST_SUPPRESSIONS.md`.
- **D3 — `tests_js/deeplink_atelier_defini.test.js`** : chemin relatif au
  fichier de test au lieu d'un chemin absolu.
- **D4 — pdf.js versionné** : `.gitignore` n'exclut plus `static/vendor/` ;
  `push-to-github.html` (hors dépôt) corrigé de même. Les 14 tests
  `test_v0_16_viewer_pdfjs.py` échouaient sur tout clone du dépôt faute des
  fichiers `static/vendor/pdfjs/`.

## Résultats

- vitest : 20 fichiers, 220 tests, **0 échec** (contre 1 fichier en échec).
- pytest : 4031 réussis, 9 ignorés, 14 échecs = uniquement
  `test_v0_16_viewer_pdfjs.py`, qui passeront dès que `static/vendor/pdfjs/`
  sera dans le dépôt (les fichiers ne sont que sur le poste de l'auteur).
  Plus aucune erreur de collecte : la suite se lance sans `--ignore`.

## À savoir sur push-to-github.html

L'outil crée un commit **additif** (`base_tree`) : il ajoute ou remplace les
fichiers fournis mais ne supprime jamais rien sur GitHub. Toute suppression
listée dans `MANIFEST_SUPPRESSIONS.md` doit aussi être faite dans le dépôt
(interface web de GitHub).

## Déploiement

1. Supprimer à la main le fichier listé dans `MANIFEST_SUPPRESSIONS.md`.
2. Décompresser ; vérifier avec `verifier_md5.py`.
3. Pousser avec le push-to-github.html corrigé, en incluant
   `static/vendor/pdfjs/`. Supprimer `tests/test_v0_29_0_verso_miroir.py` sur
   GitHub.
4. Contrôle local : `pytest tests/test_v0_16_viewer_pdfjs.py` doit passer.
