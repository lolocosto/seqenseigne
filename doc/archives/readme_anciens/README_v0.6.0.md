# seqenseigne v0.6.0 — Référentiels versionnés

Livraison majeure introduisant les **référentiels versionnés** : chaque
classe importée conserve la structure pédagogique (thèmes, séquences,
objectifs, critères) qui était en vigueur l'année où elle a été évaluée,
au lieu d'être recalée sur le référentiel courant.

## Pourquoi

Auparavant, l'UI affichait toujours les objectifs du YAML courant du
niveau, quelle que soit la classe et son année. Conséquence observée sur
la 4e6 de 2021-2022 : Romane Chailloux apparaissait avec des "I" sur les
objectifs 12 et 13, alors qu'à l'époque ces objectifs s'appelaient 05 et
06 et qu'elle y avait d'excellents résultats. Le suivi historique stockait
les bons codes (`05`, `06`) mais l'UI cherchait des valeurs pour les codes
actuels (`12`, `13`) et affichait "non évalué" par défaut.

Le problème était structurel, pas un simple bug d'import : il fallait un
modèle de données qui conserve la structure pédagogique de chaque année.

## Modèle de données (schéma v3)

Quatre nouvelles tables :

- **`referentiel_niveaux`** (`id`, `niveau`, `version`, `date_debut`,
  `date_fin`, `description`, `verrouille`) — un référentiel = une photo
  datée de la structure d'un niveau.
- **`referentiel_themes`** (`referentiel_id`, `code`, `nom`, `couleur`) —
  thèmes propres à ce référentiel.
- **`referentiel_sequences`** (`referentiel_id`, `code`, `numero`, `nom`,
  `theme_code`) — séquences avec leur thème.
- **`referentiel_objectifs`** (`referentiel_id`, `seq_code`, `code`, `nom`,
  `fin_cycle`, `critere_f`, `critere_a`, `critere_e`) — objectifs avec
  leurs critères d'évaluation.

Et une colonne ajoutée à `progressions` : **`referentiel_id`** (FK vers
`referentiel_niveaux`). Chaque progression pointe désormais vers le
référentiel qui s'applique à la classe.

La migration v2→v3 se fait automatiquement au démarrage (sans perte de
données). Les progressions existantes en base v2 se retrouvent sans
référentiel associé — c'est cohérent puisque vous partez d'une base
vierge pour la réimporter.

## Règles de gestion

**Un référentiel importé est verrouillé d'office.** S'il a servi à
évaluer des élèves, modifier ses objectifs changerait rétroactivement les
résultats stockés. Tout référentiel créé par l'importeur a `verrouille=1`.

**Détection d'équivalence par clé canonique.** À l'import, si plusieurs
classes d'une même année ont le même contenu (mêmes thèmes, séquences,
codes et noms d'objectifs), elles partagent le même référentiel plutôt
que d'en créer N copies. La comparaison ignore les variations de casse,
d'accents, d'espaces et de ponctuation finale.

**Granularité par niveau.** Les objectifs N10 et N11 sont différents pour
la même séquence, donc chaque niveau a son propre référentiel
(`N10_v2024-2025`, `N11_v2024-2025`, etc.). Les classes 5e1 et 5e2 d'une
même année partagent typiquement `N10_v2024-2025`.

**Id lisible** : `{niveau}_v{version}` où `version` est l'année scolaire
(ex: `N11_v2021-2022`). Si un deuxième référentiel avec contenu différent
doit être créé pour la même année (rare), un suffixe `b`, `c`, … est
ajouté.

## Import : ce qui change

L'importeur (route `/api/import/historique` et script
`importer_arborescence.py`) construit maintenant un référentiel depuis le
`SequencesDB/` de chaque classe. Trois étapes :

1. Extraction des thèmes (`cycle4-themes.csv`), séquences
   (`cycle4-sequences.csv`), objectifs (`N{niveau}S{XX}Objectifs.csv`)
   depuis le `SequencesDB/` de la classe.
2. Recherche d'un référentiel équivalent déjà en base. Si trouvé →
   réutilisation, ID noté dans la progression. Sinon → création et
   verrouillage immédiat.
3. La progression enregistre son `referentiel_id`.

Le script CLI affiche maintenant l'ID du référentiel utilisé par chaque
classe, et fait un récap final groupant les classes par référentiel :

```
  ✓ 2024-2025 / Collège Les Hautes Ourmes / 5e1 — 25 élèves · 18 créneaux · ref=N10_v2024-2025
  …

  Référentiels utilisés : 3
    N10_v2024-2025 ← 2 classe(s)
    N11_v2024-2025 ← 2 classe(s)
    N12_v2024-2025 ← 1 classe(s)
```

## Admin / Base de données

L'écran Admin montre maintenant beaucoup plus d'information :

**Atomes pédagogiques** (comme avant)
- Notions · Méthodes · Exercices · Livrets

**Suivi** (nouveau)
- Classes · Élèves · Progressions · Créneaux · Niveaux saisis · Exos cochés

**Référentiels versionnés** (nouveau)
- Liste détaillée : ID · Niveau · Version · État (verrouillé/modifiable)

## Ce qui n'est pas encore dans v0.6.0

Ce qui vient en **v0.6.1** (prochaine livraison) :

- L'UI consomme le bon référentiel pour chaque classe. Aujourd'hui elle
  continue de lire le YAML courant pour construire les grilles — donc
  Romane reste affichée avec des "I" malgré les référentiels en base.
  La v0.6.1 modifiera `services/sequences.py` pour charger les séquences
  depuis le référentiel associé à la progression de la classe.

Ce qui reste à faire plus tard (noté en roadmap) :

- **Compléter les référentiels historiques avec leurs atomes pédagogiques** :
  pouvoir rattacher a posteriori notions, méthodes, exercices aux
  séquences d'un référentiel historique. Un atome utilisé dans un
  référentiel verrouillé deviendrait lui-même verrouillé.

## Tests

**308 tests verts** (295 précédents + 13 nouveaux dans
`test_referentiels.py`), aucune régression.

Les nouveaux tests couvrent :
- Création / lecture / listing / verrouillage d'un référentiel.
- Détection d'équivalence avec variations (casse, accents, ponctuation).
- Non-équivalence quand un code d'objectif change (le cas Romane).
- Non-équivalence entre niveaux différents.
- Construction d'un référentiel depuis un `SequencesDB/` minimal.
- Import multi-classes : même contenu → un seul référentiel créé ;
  contenus différents → deux référentiels distincts avec suffixe.

## Fichiers modifiés par rapport à v0.5.5

```
appli/persistence/schema.sql            ← schéma v3 (4 nouvelles tables)
appli/persistence/sqlite_store.py       ← méthodes référentiels + migration v2→v3
appli/importers/sequencesdb.py          ← paramètre `store` + rattachement progression
appli/importers/referentiel_builder.py  ← NOUVEAU, extraction depuis SequencesDB
appli/routes/progression.py             ← passe `store=js` à l'import
appli/services/admin.py                 ← statut_bdd enrichi (suivi + référentiels)
appli/services/classes.py               ← (inchangé depuis v0.5.5, inclus pour cohérence)
appli/static/app.js                     ← UI Admin enrichie (suivi + référentiels)
appli/templates/index.html              ← (inchangé, inclus pour cohérence)
appli/importer_arborescence.py          ← passe store, affiche ref, récap final
appli/tests/test_referentiels.py        ← NOUVEAU, 13 tests
```

## Déploiement

**Important : vous aviez prévu d'effacer la base et de tout réimporter.
C'est le chemin recommandé.**

1. Dézipper l'archive à la racine de `D:\Enseignement\seqenseigne\`.
2. Supprimer la base existante :
   ```
   del data\seqenseigne.db
   del data\seqenseigne.db-wal
   del data\seqenseigne.db-shm
   ```
3. Réimporter l'arborescence :
   ```
   python importer_arborescence.py --racine D:\Enseignement_old
   ```
4. Vérifier : Admin / Base de données doit montrer les référentiels
   créés (un par niveau × année dans le cas général).

Si vous préférez conserver la base existante, la migration v2→v3 se
fait automatiquement mais vos progressions n'auront pas de référentiel
associé — vous devrez les réimporter classe par classe pour qu'elles en
acquièrent un.

## Tests manuels recommandés

1. Lancer l'import complet et vérifier dans le résumé que :
   - Les classes d'une même année × même niveau partagent le même
     référentiel.
   - Les classes de 2021-2022 et 2024-2025 d'un même niveau ont des
     référentiels distincts (les objectifs ont été renumérotés).
2. Ouvrir l'appli, aller dans Admin / Base de données, cliquer sur
   "État actuel" : vérifier que la section Référentiels apparaît et que
   tout est verrouillé.
