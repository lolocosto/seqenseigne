# Redémarrage v0.48.1 — Livret de fiches de résumé par séquence

Nouveau découpage de la série v0.48 (validé) : v0.48.0 retour / délai sur les
associations (livrée) ; **v0.48.1 fiches de résumé par séquence** ; v0.48.2
référentiel externe de même structure qu'un interne, utilisable par la
progression principale ; v0.48.3 documents externes portant leur séance /
retour / délai et documents de MER.

## Décisions validées

- Les livrets sont par séquence, donc les fiches de résumé aussi (pas par
  partie).
- Option **Découpage** du document « Livret de fiches » (Conception de
  référentiel › documents) : un livret annuel (comportement actuel, par
  défaut), un livret par séquence, ou les deux.
- Un livret de séquence = les fiches de cette séquence, précédées d'un
  en-tête « Fiches de résumé — S05 Nom de la séquence — Classe de … — version »
  (ni page de garde ni table des matières). Fichier
  `livret_fiches__N11__S05.pdf`. L'option « complètes / à compléter » vaut
  pour les deux formes.
- Dans la progression principale, « Fiches de résumé — S05 » apparaît dans
  « Cette séquence » des documents à associer (à associer à la séance 1 du
  créneau, « à faire », « pour la fin du créneau » — v0.48.0). Les
  associations existantes au livret annuel restent valides.

## Code

- `services/referentiel_documents.py` : option `decoupage_fiches`
  (`annuel` | `par_sequence` | `les_deux`).
- `services/referentiel_documents_compilation.lister_cibles_document` :
  cibles du livret de fiches selon le découpage (une par séquence ayant des
  fiches).
- `services/orchestrateur_compilation.py` : la séquence de la cible est
  transmise au générateur.
- `services/livret_fiches.generer_livret_fiches(..., sequence=None)` :
  filtrage et en-tête de séquence.
- `static/atelier_referentiel.js` : radios « Découpage ».

## Tests

- pytest `tests/test_v0_48_1_fiches_par_sequence.py` (6).
- Suite complète : pytest 4140 réussis, 0 échec ; vitest 225 réussis.
- À vérifier chez l'auteur : compilation réelle d'un livret de séquence
  (paquet LaTeX local).
