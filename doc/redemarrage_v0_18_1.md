# Redémarrage v0.18.1 — Outil Recherche (Outils généraux)

Nouvel atelier **Recherche** dans la portée « Outils généraux » (à côté de
« Rendu par lot »). Recherche transversale sur les cinq types d'atomes
(notion, méthode, exercice, fiche, carte), tous niveaux et toutes séquences,
avec filtres et recherche textuelle libre (option expression régulière).

## Cadrage (décisions nommées D1–D7)

- **D1 — Périmètre du texte cherché**, par type (union des sources) :
  - notion / méthode : `titre` + `corps` + sections (`atome_sections.titre` +
    `atome_section_items.corps`). Les exemples/remarques sont des sections
    titrées « Exemples »/« Remarques » → déjà couverts.
  - fiche : `titre` + sections (`entite_type='fiche_resume'`). Pas de colonne
    `corps` pour les fiches.
  - exercice : `titre` + `enonce` + `corrige` + `variables` + `remed_enonce`
    + `remed_corrige`.
  - carte : `titre` + `recto` + `verso` + `variables`.
  - **Découverte d'audit** : la table `items_texte` est de l'archive **morte**
    (remplacée en v0.6.4 par `atome_sections` — cf. commentaire dans
    `services/latex_rendu_atome.py`). Elle n'est PAS interrogée : la l'inclure
    aurait fait remonter du contenu obsolète.
- **D2 — Explorateur** : champ texte vide ⇒ le filtre texte ne s'applique pas ;
  « Rechercher » liste alors tout ce qui correspond aux filtres
  type/niveau/séquence/état.
- **D3 — Ouverture des 5 types** : `compilBatchOuvrirAtelier` (app.js)
  généralisée. Au lieu des anciennes globales/fonctions hétérogènes
  (notion/methode/exercice uniquement), elle s'appuie désormais sur les objets
  OO `ATELIER_*` (`chargerListe()` + `ouvrirItem()` + propriété `liste`), via
  le mapping `_OUVRIR_ATELIER_MAPPING`. Fiche → sous-onglet `fiche`, carte →
  `carte_automatisme`. **Le Rendu par lot bénéficie aussi de l'extension.**
- **D4 — Sensibilité** : recherche **sensible aux accents** (« médiane » ne
  trouve pas « mediane » — aucune normalisation Unicode), **insensible à la
  casse par défaut**. Le service expose déjà `casse_sensible` pour le futur
  sélecteur de casse côté UI (roadmap).
- **D5 — Regex** : case « expression régulière » ⇒ `re.search` sur le même
  texte agrégé, `re.MULTILINE` (ancrage `^`/`$` ligne par ligne, intuitif),
  `IGNORECASE` selon D4. Regex invalide ⇒ message inline, jamais de 500
  (HTTP 400 `code='regex_invalide'`).
- **D6 — Stratégie** : tout en Python. Les filtres niveau/séquence/état sont
  appliqués en SQL ; le texte des 3 sources est agrégé par atome puis testé
  (substring ou regex). À l'échelle de la base (~1769 atomes), instantané, et
  comportement accents/regex exact.
- **D7 — Résultats** : groupés par type (ordre cours → fiches → cartes),
  une ligne = identifiant lisible + titre + badge état + bouton « Ouvrir »
  (clic simple = ouverture classique). Le Ctrl+clic vers un nouvel onglet
  reste **différé** (cf. roadmap).

## Backend

- **`services/recherche_atomes.py`** (nouveau) — fonction `rechercher(store,
  type, niveau, sequence, etat, texte, regex, casse_sensible)`. Réutilise les
  helpers d'identifiant lisible et `ORDRE_TYPES` de `compilation_batch`.
  Erreurs `RechercheErreur` / `RechercheRegexInvalide` (code string + details).
  Contrat de sortie : dict avec les 5 clés de type (toujours présentes,
  listes possiblement vides) + clé `total`.
- **`routes/recherche.py`** (nouveau) — `GET /api/recherche` (query string).
  Paramètres : `type`, `niveau`, `sequence`, `etat`, `texte`, `regex`,
  `casse_sensible`. Traduit les erreurs en HTTP 400.
- **`app.py`** — enregistrement du blueprint `bp_recherche`.

## Frontend

- **`templates/index.html`** :
  - bouton `#atl-btn-recherche` (classe `.atl-grp-generaux`) à côté du Rendu
    par lot ;
  - panneau `#atl-recherche` : filtres type/niveau/séquence/état + champ texte
    + case « expression régulière » + zone de résultats `#rech-resultats`.
- **`static/app.js`** :
  - `recherche` ajouté à `ATL_PORTEES.generaux.ateliers` et à `ATL_INITS`
    (`rechercheInit`) ;
  - `rechercheInit()` (injection S01..S14, Entrée = lancer),
    `rechercheLancer()` (lecture filtres → `GET /api/recherche` → rendu),
    `rechercheRendre()` (rendu groupé), `escAttrJs()` (échappement onclick) ;
  - `compilBatchOuvrirAtelier(type, id, niveau, sequence)` généralisée aux 5
    types ; les deux derniers arguments (optionnels) positionnent la portée
    Séquence sur le niveau/séquence de l'atome AVANT chargement, car
    `AtelierEditeur.chargerListe()` ne charge que le contexte de filtre
    courant. Le Rendu par lot continue d'appeler sans ces arguments
    (rétrocompatible).

## Tests

- **`tests/test_v0_18_1_recherche_atomes.py`** (20) : explorateur, filtres
  (type/état), périmètre des 3 sources de texte par type, sensibilité aux
  accents, casse, regex (simple/ancrage/casse/invalide), contrat de sortie,
  tri, identifiants.
- **`tests/test_route_recherche.py`** (9) : intégration HTTP (câblage,
  format, accents, état, type, regex valide/invalide).
- **`tests_js/recherche_outil.test.js`** (10) : analyse statique du câblage
  app.js + exécution jsdom de `rechercheRendre`/`escAttrJs` (rendu groupé,
  compteurs, bouton Ouvrir câblé type/id/niveau/séquence, échappement HTML).

**Zéro régression** : `pytest` → 3832 passed, 7 skipped ; `vitest` → 109
passed (12 fichiers).

## Reste différé (roadmap)

- Ctrl+clic « Ouvrir » → nouvel onglet (y compris pour les atomes assemblés
  séquence / évaluation).
- Sélecteur de sensibilité à la casse dans l'UI Recherche (le backend
  l'accepte déjà via `casse_sensible`).
