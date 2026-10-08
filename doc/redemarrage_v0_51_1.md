# Redémarrage v0.51.1 — Format d'échange JSON des référentiels

Deuxième étape du chantier « séparer l'appli en 2 » (cadrage :
`doc/redemarrage_v0_51_0.md`). Description complète du format :
`doc/format_referentiel.md` ; schéma : `schemas/referentiel-1.json`.

## Décisions validées

- Un fichier JSON par référentiel (interne / externe, principal / MER),
  autoportant : il décrit la structure qu'il utilise — cycle, niveau, thèmes,
  découpage en séquences **du niveau** — telle qu'au figeage, avec une
  empreinte de structure. Un changement de thèmes ou de découpage = un
  nouveau référentiel ; les publiés gardent leur structure. Un code de
  séquence n'a de sens que dans son référentiel.
- Identifiants stables = clés déjà utilisées côté classe (id du référentiel,
  code de séquence, numéro de partie, code d'objectif, `ref` des documents).
- Pas de LaTeX en ligne : textes convertis en texte lisible, source LaTeX
  conservée dans `…_latex` quand elle diffère.
- Notions et méthodes : **titres seulement** (synthèse Pronote) ; exercices,
  fiches, cartes : portés par les PDF.
- Un référentiel interne verrouillé est **publié une fois pour toutes**
  (première publication conservée et resservie) ; un externe est exporté
  dans son état du moment.
- Le contenu des fichiers voyagera dans le paquet (v0.51.2) ; le JSON en
  donne nom, taille et sha256.
- Retour d'usage classe → atelier (référentiel utilisé, séquences
  commencées, parties de MER posées ; aucune donnée d'élève) : accepté, en
  version à part après l'import (v0.51.3).

## Code

- `services/texte_latex.py` (nouveau) : `vers_texte` (LaTeX court → texte
  Unicode) ; la synthèse Pronote l'utilise aussi désormais
  (`services/synthese_seance._texte`).
- `services/format_referentiel.py` (nouveau) : `construire`, `exporter`
  (publication figée dans `data/referentiels/<id>/_publication/`),
  `empreinte`, `empreinte_structure`, `valider` (schéma + cohérence),
  `bilan`.
- `services/schema_json.py` (nouveau) : validateur JSON Schema minimal (sans
  dépendance pour le Python portable).
- `schemas/referentiel-1.json` (nouveau).
- `routes/publication.py` (nouveau, blueprint `publication`, profil
  atelier) : `GET /api/publication/referentiels/<id>.json`,
  `GET /api/publication/referentiels/<id>/verification` (ne fige rien).
- `services/profils.py`, `app.py` : enregistrement du blueprint.
- `templates/index.html`, `static/referentiel_unifie.js`, `static/app.css` :
  bandeau « Format d'échange » (Exporter (JSON), Vérifier) au-dessus du
  détail du référentiel choisi ; ancien modèle de MER signalé non
  exportable.

## Tests

- `tests/test_v0_51_1_format_referentiel.py` : conversion des textes,
  interne (structure complète, parties, objectifs, critères avec source
  LaTeX, titres des notions et méthodes, livret compilé avec sha256),
  publication figée (atomes modifiés → publication inchangée, état suivi),
  externe (types, placement, fichiers), MER, ancien modèle refusé,
  empreintes, validation (erreurs détectées), conformité au schéma officiel
  (`jsonschema`), routes, profil classe sans la route, vérification sans
  figeage.
- Parcours navigateur (profil atelier) : bandeau, vérification d'un externe
  et d'un interne, ancien modèle.

## Suite

- v0.51.2 : paquet de publication (JSON + PDF compilés + fichiers externes,
  contrôle des sha256, rapport) ; tuile « Publication » au tableau de bord
  atelier.
