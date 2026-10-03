# Redémarrage v0.44.0 — Documents du début de séance

Troisième livraison du chantier « suivi en séance » (ROADMAP).

## Décisions validées

- Bloc **Documents** du début de séance, en deux colonnes :
  - **Nouveaux documents** : documents prévus pour la séance (associations de
    la progression principale, placées sur leur séance par le rang dans la
    partie — même calcul que le détail de séance de la planification hebdo),
    plus les documents **ajoutés à la volée** ; coche « distribué ».
  - **À rattraper** : pour chaque élève présent, les documents distribués à
    une séance où il était absent et pas encore donnés ; coche « donné ».
- **Report** : un document non coché « distribué » revient à la séance
  suivante (étiquette « reporté du jj/mm »).
- **Document ajouté à la volée** : libellé + catégorie (administratif,
  sortie, pédagogique), pour **cette séance** ou la **prochaine séance** de
  la classe (cas du document confié par le professeur principal). Ensuite,
  même suivi que les autres. Supprimable (les documents prévus non).
- Pas de documents ponctuels planifiés à l'avance au-delà de la séance
  suivante ; pas de vue « professeur principal ».
- **Mise en service** : le report des documents prévus ne remonte pas avant
  la première séance où le bloc a été ouvert pour la classe
  (`docs_suivi.depuis`, automatique) — pas de déferlement des documents des
  semaines passées.
- Les absents sont lus en direct : marquer un élève absent après avoir coché
  « distribué » le rend redevable.

## Code

- Migration : tables `seance_documents`, `seance_remises`, `docs_suivi`
  (schéma porté par `services/documents_seance.py`).
- `services/documents_seance.py` : `documents_prevus`, `pour_seance`,
  `marquer_distribue`, `ajouter_ponctuel`, `supprimer_ponctuel`,
  `marquer_donne`.
- `services/seance.py` : `lire` renvoie `documents` et `seance_suivante` ;
  `seance_suivante`.
- `routes/seance.py` : `POST /api/seance/document` (`pour` = cette |
  prochaine), `DELETE /api/seance/document/<id>`,
  `PUT /api/seance/document/<id>/distribue`, `PUT /api/seance/document/<id>/donne`.
- `static/seance.js`, `static/app.css`.

## Limites connues

- Les documents associés à la progression de MER ne sont pas encore câblés
  (l'association elle-même n'existe que pour la progression principale).
- Ordre des séances d'une même journée : comparaison des codes de créneau
  (M1 < M2 < … < S1 …), suffisant avec la grille par défaut.

## Tests

- pytest `tests/test_v0_44_0_documents.py` (7) : placement des documents
  prévus, ouverture du suivi, distribution / report / rattrapage, élève encore
  absent, document pour la séance suivante, validations, routes.
- Suite complète : pytest 4103 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur : 4EME3 lundi 05/10 — document ajouté pour cette séance
  et un autre pour la suivante ; distribué avec deux absents ; à la séance du
  09/10, les deux absents apparaissent dans « À rattraper » et le document de
  sortie dans « Nouveaux documents ».
