# Redémarrage v0.51.4 — Atelier : codes, documents, durées

Demandes de l'auteur après les premiers usages de l'atelier de conception
des référentiels externes (principal et MER). Éditeur :
`static/referentiel_pe.js` ; service : `services/referentiel_principal_externe.py`.

## Décisions (validées)

- **Codes de séquence** (S01… / M01… pour une MER) : recalculés d'après le
  rang au **déplacement** et à la **suppression**, tant que le référentiel est
  **en conception** = conçu ici (pas `origine='publication'`), utilisé par
  aucune progression (principale ou de MER), jamais publié (absent du
  journal `publications`). Ensuite les codes ne changent plus (créneaux,
  parties posées `rid|seq|num`, appli en ligne) ; le réordonnancement ne
  change que le rang. L'éditeur affiche la règle en cours.
  Recodage en deux temps (codes provisoires `~Sxx`) dans toutes les tables
  portant `(referentiel_id, seq_code)`, clés étrangères différées
  (`PRAGMA defer_foreign_keys`).
- **Déplacer un document attaché** : menu « déplacer vers… » (documents
  annuels, chaque séquence, chaque partie). Refusé une fois le document
  **marqué distribué** dans le suivi de séance (`seance_documents` :
  `auto:<fid>:…`, `automer:<fid>`, association manuelle `<id>` / `mer:<id>`
  dont `doc_ref` = le fichier) — badge « distribué » à la place du menu.
  La séance de distribution est effacée hors d'une partie, conservée d'une
  partie à l'autre (alerte si elle dépasse la durée de la nouvelle partie) ;
  retour et délai conservés ; l'identifiant ne change pas (associations
  intactes). Route : `PUT /api/referentiels-principaux-externes/fichiers/<fid>/rattachement`
  (structure : écriture atelier seulement).
- **Durée d'une partie** = somme des séances de ses objectifs : affichage
  seul (plus de saisie, ni à l'ajout de partie) ; recalculée à chaque
  ajout / modification / suppression d'objectif ; `modifier_partie` refuse ;
  **migration** : toutes les parties des référentiels externes conçus ici
  sont recalculées au démarrage (une partie sans objectif vaut 0).
- Q5 (éditeur des internes ?) : réponse de l'auteur = nouveau chantier
  « structures modèles à la création » (voir `doc/ROADMAP.md`).

## Code

- `services/referentiel_principal_externe.py` : `est_publie`,
  `en_conception`, `recoder_sequences`, `recalculer_parties`,
  `fichier_distribue`, `deplacer_fichier` ; `lire` expose `en_conception` et
  `distribue` par fichier ; `deplacer_sequence` renvoie `{recode}`.
- `routes/referentiel_principal_externe.py` : route `rattachement`.
- `static/referentiel_pe.js`, `static/app.css` : durée en lecture seule,
  menu de déplacement, mention de la règle des codes.
- Tests : `tests/test_v0_51_4_atelier_conception.py` ; tests v0.48.2,
  v0.48.5, v0.49.0, v0.49.1, v0.51.2 adaptés (durées par les objectifs,
  codes recalculés).
