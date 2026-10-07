# Redémarrage v0.49.0 — Un seul modèle pour les référentiels externes (étape B)

Plan validé (étude de l'unification des référentiels) : A (composants
communs) devient inutile, l'auteur recréant son unique référentiel externe
de MER (pas de migration de données) ; **B** (ce lot) : MER externes dans la
structure figée ; puis v0.49.1 (ex-v0.48.7 : documents de MER — séance,
retour, délai dont « fin de la partie de MER », placement automatique,
panneau « documents à distribuer » de la Progression de MER) ; **C** onglet
unique « Référentiel » (filtres niveau, année, type, source ; groupage dans
cet ordre pour les filtres sans valeur) ; **D** découpage progressif du
détail interne.

## Décisions validées

- **D1** — Créer un référentiel externe de MER produit un référentiel figé
  `type_ref='mer'`, `source='externe'` (id `M<année>_<niveau><lettre>`, nom
  calculé « 6e — 2026-2027 — MER »), avec **le même éditeur** que les
  principaux. Codes de séquence **M01, M02…** (jamais confondus avec S01…).
- **D2** — Compléments du modèle (utiles aux deux types) : **libellé de
  partie** facultatif (correction toujours permise) ; **documents annuels**
  (rattachés au référentiel).
- **Au moins un objectif « capacité » par partie** (ce qu'on évalue à la
  fin) : alerte visible sur le référentiel et sur la partie, non bloquante
  (un externe reste utilisable incomplet).
- **D3** — Progression de MER : nouvelle source `fige` ; les parties posées
  sont désignées par `<référentiel>|<séquence>|<numéro>` ; planning, mises en
  route, début de séance et synthèse inchangés. Une séquence de MER est
  verrouillée dès qu'une de ses parties est posée ; le référentiel passe
  « utilisé ».
- **D4** — Ancien modèle de MER en retrait : plus de création ; les anciens
  référentiels restent lisibles (« — ancien modèle ») et sélectionnables dans
  la Progression de MER (« (ancien modèle) ») jusqu'à leur recréation ; leur
  suppression du code viendra après feu vert.

## Code

- Migration : colonne `referentiel_parties.libelle`.
- `services/referentiel_principal_externe.py` : `creer(..., type_ref)`,
  préfixe M, `est_utilise` / `sequence_commencee` pour la MER,
  `libeller_partie`, documents annuels (`seq_code=''`), alertes,
  `parties_mer`, `partie_mer`.
- `services/progression_mer.py` : source `fige` (résolution, parties
  disponibles).
- Routes : `type=` (principal | mer | tous), `type_ref` à la création,
  `PUT …/parties/<n>/libelle`, `POST …/<id>/documents-annuels` ; nom du
  référentiel figé dans le PDF du planning de MER.
- `static/referentiel_pe.js` (création unique, libellé de partie, documents
  annuels, alertes), `static/progression_mer.js` (référentiels figés de MER,
  source transmise), `static/app.css`.

## Tests

- pytest `tests/test_v0_49_0_mer_modele_fige.py` (4).
- Suite complète : pytest 4165 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur : création d'une MER (« Calcul mental »), séquence M01,
  partie « Série 2 », alerte « capacité » ; référentiel proposé et partie
  disponible dans la Progression de MER.
