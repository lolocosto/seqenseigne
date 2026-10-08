# Redémarrage v0.51.2 — Paquet de publication

Troisième étape du chantier « séparer l'appli en 2 » (cadrage :
`doc/redemarrage_v0_51_0.md`). Formats : `doc/format_referentiel.md`,
`doc/format_paquet.md`.

## Retour sur le premier export réel (N11_v2025, v0.51.1)

Export valide (14 séquences, 19 parties, 76 objectifs, 14 livrets de
séquence avec sha256), mais :
- accents LaTeX non convertis (`\'E`, `\oe uvre`) → corrigé
  (`services/texte_latex.py` : accents, `\c{c}`, lettres `\oe`…) ; profite
  aussi à la synthèse Pronote ;
- tous les objectifs en « capacité » : dans les internes, le type n'est pas
  saisi → règle de position (1er objectif de la partie = connaissance) ;
- publications figées produites par la v0.51.1 : régénérées au prochain
  export (`EXPORTEURS_PERIMES`), rien n'ayant été importé ;
- 20 documents compilés sans PDF (planches de cartes, livrets annuels) :
  normal pour ce référentiel → retirés du JSON, mentionnés au rapport ;
- durées à 0 : données figées telles quelles (voir ROADMAP : passe sur le
  figeage et les éditeurs).

## Décisions validées

- Un paquet (zip) regroupe un ou plusieurs référentiels, un JSON chacun.
- Durée d'une partie = **somme des séances de ses objectifs** (la
  progression en déduit des semaines selon les séances par semaine du
  niveau) ; la valeur saisie sur la partie est exportée pour information
  (`nb_seances_saisie`), l'écart est signalé (vérification, rapport).
- Documents compilés sans PDF : non publiés, signalés.

## Code

- `services/format_referentiel.py` : documents compilés sans PDF retirés
  (`omis`, conservé à côté d'une publication figée dans `omis.json`) ;
  `nb_seances` = somme des objectifs, `nb_seances_saisie` ; contrôle de
  cohérence ; bilan : `documents_sans_pdf`, `parties_ecart` ; type des
  objectifs internes ; `EXPORTEURS_PERIMES`.
- `schemas/referentiel-1.json` : `nb_seances_saisie` remplace
  `nb_seances_objectifs` (format 1.0 non encore importé ailleurs).
- `services/texte_latex.py` : accents et lettres LaTeX.
- `services/paquet_publication.py` (nouveau) : `lister_publiables`,
  `creer` (zip, manifeste, dédoublonnage par sha256, contrôles, journal),
  `journal`, `verifier` (pour l'import v0.51.3) ; table `publications`
  (migration dans `persistence/sqlite_store.py`).
- `routes/publication.py` : `GET /api/publication/publiables`,
  `POST /api/publication/paquet`, `GET /api/publication/journal` ; la
  vérification renvoie aussi les documents sans PDF.
- `templates/index.html`, `static/tableau_bord.js`, `static/app.css` : tuile
  « Publication » (profil atelier).
- `static/referentiel_unifie.js` : la vérification affiche documents sans PDF
  et écarts de durée.

## Tests

- `tests/test_v0_51_2_paquet.py` : publiables, contenu et manifeste, rapport,
  dédoublonnage, journal et « modifié depuis », refus (non publiable,
  fichier disparu, PDF modifié après figeage), détection d'altération,
  routes, profil classe.
- `tests/test_v0_51_1_format_referentiel.py` : accents, type des objectifs
  internes, régénération des publications 0.51.1, durée = somme.
- Parcours navigateur (profil atelier) : tuile, cocher, création et
  téléchargement du paquet, résumé.

## Suite

- v0.51.3 : import du paquet dans le profil classe (vérification complète,
  structure en lecture seule, rapport des changements, documents orphelins).
