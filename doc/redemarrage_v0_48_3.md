# Redémarrage v0.48.3 — Types des documents attachés (référentiels externes)

Demande : typer les documents attachés pour mieux organiser la séquence ;
un document par ligne avec son type à côté ; liste extensible dans les
préférences système.

Renumérotation de la suite : v0.48.4 harmonisation des écrans interne /
externe ; v0.48.5 fichiers externes portant séance / retour / délai +
documents de MER.

## Décisions

- Types par défaut : Livret d'exercices, Livret de séquence, Livret de cours,
  Évaluation, Travail personnel, Activité complémentaire.
- Système › Préférences › « Référentiels externes › Types de documents » :
  ajouter, renommer, réordonner, désactiver (un type désactivé n'est plus
  proposé mais reste sur les fichiers qui l'ont).
- Référentiel principal externe : chaque fichier (de séquence ou de partie)
  sur sa ligne, avec un sélecteur de type à côté. Le type se modifie toujours,
  même pour une séquence commencée (c'est du classement).
- Le type préfixe le libellé du fichier dans les documents associables de la
  progression (« Livret d'exercices : exos.pdf »).

## Code

- Migration : table `types_documents` (types par défaut), colonne
  `referentiel_fichiers.type_id`.
- `services/referentiel_principal_externe.py` : `lister_types`,
  `ajouter_type`, `modifier_type`, `deplacer_type`, `typer_fichier` ;
  `type_libelle` dans les fichiers lus.
- `routes/referentiel_principal_externe.py` : `/api/types-documents…`,
  `PUT /api/referentiels-principaux-externes/fichiers/<id>/type`.
- `services/progression_doc.py` : libellé préfixé par le type.
- `static/referentiel_pe.js`, `templates/index.html` (préférences),
  `static/app.js` (chargement), `static/app.css`.

## Tests

- pytest `tests/test_v0_48_3_types_documents.py` (3).
- Suite complète : pytest 4150 réussis, 0 échec ; vitest 225 réussis.
- Parcours navigateur : deux fichiers typés (séquence, partie), liste des
  types dans les préférences.
