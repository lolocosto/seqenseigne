# Redémarrage v0.51.6 — Structures modèles à la création

Seconde livraison « structures modèles » (la première, v0.51.5, a ajouté les
thèmes à l'éditeur). Création dans Conception › Niveau › Référentiel,
source « Externe ».

## Décisions (validées)

- **Modèles du même type seulement** : principal ↔ principal, MER ↔ MER (une
  MER n'a ni fiches de résumé, ni cartes, ni livret complet : 5-10 min par
  séance). Pour un principal, en plus : le **programme du cycle**.
- **Programme du cycle** : thèmes et séquences du cycle du niveau (tables du
  cycle, repli sur `<cycle>_themes.csv` / `_sequences.csv` quand elles sont
  vides), objectifs du niveau ; parties de l'atelier de conception quand
  elles existent, sinon **une partie par séquence** avec tous ses objectifs,
  **0 séance**. Premier objectif d'une partie = « connaissance ». Critères :
  F ← maîtrise fragile, A ← satisfaisante, E ← très bonne (« - » = vide).
- **Référentiels existants** du niveau et du type (internes et externes,
  toutes années), sauf annulés et vides.
- Le modèle recopie la structure : thèmes (couleur reprise si connue),
  séquences et leur thème, libellés de parties, objectifs (nom, type,
  critères F/A/E, séances) ; textes sans LaTeX ; codes recalculés ; le
  nouveau référentiel est en conception, entièrement modifiable.
  **Les documents ne sont jamais copiés** ; « Créé à partir de : … » est
  conservé (`referentiel_niveaux.cree_depuis`).
- **Doublons** : un référentiel externe dont le contenu (structure +
  documents : empreinte de chaque fichier, point d'attache, type, placement)
  est identique à un autre du même niveau et du même type est signalé dans
  l'éditeur (non bloquant). Reconduire un référentiel = baser la progression
  de l'année suivante sur le même référentiel, pas en créer un nouveau.
- Aperçu : choisir une structure affiche l'arbre dépliable (thèmes ▸
  séquences ▸ parties ▸ objectifs, séances) à droite, avec « Créer à partir
  de ce modèle ».

## Code

- `services/modeles_referentiel.py` (nouveau) : `lister`, `modele`,
  `appliquer`, `creer`, `empreinte_contenu`, `doublons`.
- `services/referentiel_principal_externe.py` : colonnes `cree_depuis`
  (référentiel) et `sha256` (fichier, calculée à l'ajout, sinon à la
  première comparaison).
- `routes/referentiel_principal_externe.py` : `GET …/modeles?niveau=&type=`,
  `POST …` accepte `modele` ; `GET …/<rid>` renvoie `doublons`.
- `templates/index.html`, `static/referentiel_unifie.js`,
  `static/referentiel_pe.js`, `static/app.css` : sélecteur de structure,
  aperçu, alerte de doublon.
- Tests : `tests/test_v0_51_6_modeles.py`.
