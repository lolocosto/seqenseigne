# Redémarrage v0.54.0 — les deux référentiels internes de 6e (principal et mises en route)

## Besoin (Laurent, 25 octobre 2026)

> « Maintenant que toutes les séquences sont complètes, on peut créer les 2 référentiels
> internes de 6e. Ensuite on passera aux progressions. »

C'est Laurent qui crée les référentiels **dans l'appli** (jamais d'écriture directe en base).
L'appli doit savoir le faire proprement pour les deux ; la marche à suivre est dans
`SP/livraison_v0540/marche_a_suivre.md`, l'audit dans `SP/livraison_v0540/audit_referentiels.md`.

## 1. Constats de l'audit (v0.53.3)

- Un référentiel interne créé dans l'appli n'avait **aucun instantané** de sa structure
  (`referentiel_sequences / _objectifs / _themes` jamais remplis pour une coquille) : son export,
  sa publication et ses parties côté classe étaient vides.
- L'éligibilité du principal comptait les **22 tests courts** des mises en route (évaluations du
  niveau) ; l'arbre de l'atelier montrait aussi M01–M07 et X01–X16.
- Verrouiller un référentiel de mises en route `2026b` aurait **annulé le principal `2026`**
  (concurrents de même niveau et année, tous types confondus).
- Rien pour un référentiel de mises en route interne : pas de documents, pas de durée de
  partie, bouton « Valider la séquence » d'une Mnn appliquant la règle F/A du principal,
  progression de MER de la classe limitée aux référentiels externes.
- Contenu : **aucun blocage** (tous les atomes, les 20 séquences et les 40 évaluations et tests
  passent leurs contrôles ; tout est « en cours »).

## 2. Décisions

- **RI1 — Périmètre selon le type** (`services/referentiels_internes.py`,
  `sequences_du_perimetre`, `evaluations_du_perimetre`) : principal = séquences du niveau
  sauf archives `Xnn` et mises en route `Mnn` ; mises en route (`type_ref = 'mer'`) = les `Mnn`.
  Arbre (`arbre_du_niveau(conn, niveau, type_ref)`), atomes et évaluations de l'éligibilité
  (`referentiel_validation`), instantané, trace (`_trace_evaluations`). Au cycle 4 il n'y a ni
  Xnn ni Mnn : rien ne change.
- **RI2 — Instantané complet au verrouillage** (`ecrire_instantane`) : thèmes, séquences,
  parties (libellé), objectifs (critères, séances, fin de cycle, type connaissance/capacité) du
  périmètre, écrits **avant** la trace ; colonne `referentiel_niveaux.instantane = 'atelier'`
  (migration idempotente, '' par défaut) ; recalculé à chaque verrouillage, retiré entier au
  déverrouillage. Un référentiel dont l'instantané vient d'ailleurs (import historique,
  N11_v2025) garde l'ancien mécanisme (`peupler_snapshot_parties`).
- **RI3** — Numéro de séquence dans l'instantané : celui du cycle (S01 → 1) ; mise en route :
  son numéro (M03 → 3, pas 203).
- **RI4** — Durée d'une partie de mise en route = somme des séances de ses objectifs (bloc de N
  séances côté classe) ; principal : la durée saisie, comme avant.
- **RI5** — Modèle « Fiches » : chaque séquence du périmètre doit être **validée** dans
  l'atelier pour que le référentiel soit éligible (`details.sequences_non_validees`, raison
  « n séquence(s) non validée(s) dans l'atelier : … ») ; « Notions et méthodes » inchangé.
- **RI6** — Catalogue « mises en route » (`gabarits_documents.catalogue_type(gabarit,
  type_ref)`, `catalogue_du_referentiel`) pour un référentiel MER au modèle Fiches :
  `mer_fiches_cours_6e` (version, 1 ou 2 par A4), `mer_seances_6e` (version, 2/3/4 par A4),
  `mer_tests_courts_6e` (sujet, version, 1 ou 2 par A4), `mer_activites_6e` (version),
  `mer_dossiers_6e`. Une cible **par partie** (`N09/M03/p1`), par test court (`…/p1/T1`) ;
  producteurs = `mises_en_route_6e.generer_document_mer` (mêmes PDF que l'onglet « Rendu
  PDF »). Péremption : `peremption_atomes`. Autres catalogues inchangés.
- **RI7** — Format d'échange **1.4** : un document compilé dont la cible porte sa partie est
  rangé dans `partie.documents` ; déclaré seulement par un tel référentiel (versions et
  empreintes des référentiels existants inchangées). `doc/format_referentiel.md` à jour.
- **RI8** — Concurrents au verrouillage : même type seulement.
- **RI9** — Arbre d'une mise en route : fiche de cours de la partie (`objectif_fiches`) et
  exercices de séance (série MR) ; clés `mer`, `exos_MR` pour les Mnn seulement.
- **RI10** — Écran de création : « Référentiel principal » / « Référentiel de mises en route »,
  modèle proposé aux deux internes (description propre aux mises en route), « + Créer » montre
  d'abord un **aperçu** (état de départ « en cours », séquences, parties, objectifs, séances,
  documents, préparation) puis « Confirmer la création » ; route
  `GET /api/referentiels/apercu-creation` (catégorie « atelier »). Détail du référentiel :
  « Type : principal / mises en route » ; le message de verrouillage dit le contenu figé.
- **RI11** — Valider une séquence `Mnn` (atelier d'assemblage) applique MR6 : erreurs
  bloquantes, avertissements non.
- **RI12** — Côté classe, « Progression de MER » propose aussi les référentiels de mises en
  route **internes** verrouillés (route existante `/api/referentiels?type=mer&etats=…`) ; leurs
  parties se posent dans l'ordre voulu ; le panneau « documents » d'une partie interne le dit
  (association avec le chantier des progressions).
- **RI13** — Déverrouiller un référentiel créé dans l'atelier met de côté sa publication
  figée (`_publication/` → `_publication_avant_<date>/`) : sinon le verrouillage suivant
  resservirait l'ancien JSON (« publié une fois pour toutes »). Les autres référentiels :
  inchangé.
- Instantané d'un référentiel importé (ancien mécanisme `peupler_snapshot_parties`) :
  seulement les parties des séquences de son instantané (une séquence du niveau absente —
  archive, mise en route — faisait échouer le verrouillage sur la clé étrangère).
- **Correspondance M2026_N09** : documentée (`SP/livraison_v0540/correspondance_M2026_N09.md`),
  pas exploitée côté classe.

## 3. Appli

- Nouveau : `services/referentiels_internes.py`.
- Modifiés : `services/referentiels.py` (arbre, concurrents), `services/referentiel_validation.py`,
  `services/referentiel_figeage.py`, `services/gabarits_documents.py`,
  `services/referentiel_documents.py`, `services/referentiel_documents_compilation.py`,
  `services/orchestrateur_compilation.py`, `services/peremption_atomes.py`,
  `services/format_referentiel.py`, `services/progression_doc.py`, `services/v2_edition.py`,
  `services/profils.py`, `persistence/sqlite_store.py` (migration), `routes/referentiels.py`,
  `static/referentiel_unifie.js`, `static/atelier_referentiel.js`, `static/progression_mer.js`,
  `templates/index.html`, `doc/format_referentiel.md`.
- Tests : `tests/test_v0_54_0_referentiels_6e.py` (21), `tests_js/referentiels_6e.test.js` (4) ;
  adaptés (changement voulu) : `tests/test_v0_52_1_gabarits_documents.py` (format 1.4),
  `tests/test_v0_15_2_6_peremption_atomes.py` (péremption des types `mer_*_6e`),
  `tests_js/gabarit_documents.test.js` (modèle proposé pour une MER interne).
- Cycle 4, principal de 6e et mises en route : même `.tex` (1 277 sorties comparées) ; export de
  N11_v2025 identique ; seuls les diagnostics d'éligibilité ont trois clés de plus.
- Module LaTeX inchangé ; aucun lot modifié ; aucun outil à lancer.

Résultats : pytest 4 780 passés, 8 ignorés (référence v0.53.3 : 4 759) ; vitest 321/321 ;
essai de bout en bout sur une copie de la base de test (`SP/livraison_v0540/`).

## 4. Reste pour les progressions

- Séances du principal : tous les objectifs de S01–S13 ont 0 séance → parties à 0 séance côté
  classe ; à fixer avant de construire la progression principale.
- Documents d'un référentiel de mises en route interne dans « Progression de MER » (placement
  par séance, retour, délai) ; documents de partie dans la progression principale.
- Passage d'une classe de M2026_N09 au référentiel interne (table de correspondance) : changer
  de référentiel purge aujourd'hui les parties posées.
- Dépendances entre objectifs, période des séquences, matériel/calculatrice par séquence.

## Déploiement (Windows, appli fermée)

1. Sauvegarder `data\seqenseigne.db` (ou Système › Administration › export SQLite).
2. Dézipper à la racine (à côté d'`appli\`) : `appli\…`.
3. Lancer l'appli (`.\lancer.bat` depuis `appli\`) : la colonne `instantane` est ajoutée au
   démarrage. Puis suivre `marche_a_suivre.md`.
