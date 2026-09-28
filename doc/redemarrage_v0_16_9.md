# Redémarrage v0.16.9 — Régime mixte + état validable de la séquence-niveau

## Contexte

Suite de la migration OO du seqniv (v0.16.7). La note v0.16.7 annonçait « le
branchement de l'appareil verrou/mixte (comme l'évaluation) viendra après ».
L'audit a montré que l'analogie avec l'évaluation ne tenait que partiellement :

- le seqniv a bien des **champs de saisie** (critères F/A/E, nom d'objectif,
  séances, fin-cycle) → un **régime mixte** a du sens ;
- mais la séquence-niveau n'avait **pas d'état validable** (`sequences_par_niveau`
  sans `etat_code`) → il a fallu **créer** cette dimension.

Décisions actées (cadrage de session) :
- **R1/F1** — Régime snapshot pour les champs de saisie de l'objectif OUVERT
  (nom, critères F/A/E, fin-cycle, séances de l'objectif ouvert). Snapshot =
  objectif ouvert seulement, avec garde au changement d'objectif. Les séances
  des objectifs FERMÉS et des PARTIES restent en persistance immédiate.
- **F2** — Au changement d'objectif (ou opération de structure) avec saisie
  non enregistrée : BLOQUER (toast), comme l'évaluation.
- **R2** — Introduire un `etat_code` validable sur la séquence + verrou
  « validé = lecture seule ».
- **D2** — Tout en une livraison.
- **D3** — Hook de validation pédagogique STRICT, 4 règles (cf. ci-dessous).

## Hook de validation (4 règles strictes)

Au passage → 'valide', `_valider_sequence_hook` (services/v2_edition.py) exige :
1. la séquence a au moins une partie ;
2. chaque partie a au moins un objectif « exo » (code ≠ code Cours `{n-1}1`) ;
3. chaque objectif (cours OU exo) a un nom non vide ET les 3 critères F/A/E ;
4. chaque objectif « exo » a au moins un exercice dans CHACUNE des séries
   F, A et E.

En cas d'échec : HTTP 400, code `validation_pedagogique_echec`, `raisons`
listées (affichées en toast côté UI). NB : un audit sur la base actuelle a
montré que 12/42 séquences passent ces règles — les autres sont inachevées
(N11 notamment : critères F vides ; beaucoup d'objectifs sans les 3 séries).
C'est voulu : les règles sont strictes, Laurent complète au fur et à mesure.

## Backend

### Schéma
- `persistence/schema.sql` : `sequences_par_niveau.etat_code TEXT NOT NULL
  DEFAULT 'en_cours'`.
- `persistence/sqlite_store.py` : migration post-DDL idempotente (ADD COLUMN
  si absente) pour les bases existantes.

### Service (`services/v2_edition.py`)
- Exceptions : `EtatSequenceInvalide` (400), `SequenceVerrouillee`
  (409, code `item_verrouille`), `ValidationSequenceErreur`
  (400, code `validation_pedagogique_echec`, avec `raisons`).
- `lire_etat_sequence`, `valider_sequence_niveau` (hook + UPDATE),
  `devalider_sequence_niveau`, `changer_etat_sequence_niveau` (aiguillage).
- `_valider_sequence_hook` (4 règles).
- Verrou : `assert_sequence_modifiable` + variantes `_par_partie` /
  `_par_objectif` (remontent à la séquence). Lèvent `SequenceVerrouillee`
  si l'état est 'valide'. Tolérantes à l'introuvable (ne masquent pas un 404).

### Routes (`routes/v2_edition.py`)
- `PATCH /api/v2/sequences-par-niveau/<id>/etat`  body `{etat_code}`. Ne pose
  PAS de garde (doit pouvoir dévalider).
- Garde `assert_sequence_modifiable_*` insérée en tête des **29 routes** de
  modification de contenu (parties, objectifs, exos, notions, fiches,
  précédences, séances, critères, nom, fin-cycle, réordonnancements,
  déplacements, suppressions). Une séquence validée est entièrement gelée.
- Routes EXEMPTÉES (pas de garde) : lectures, `exos-disponibles*`,
  `etat-ui` (état UI, pas du contenu), et `/etat` elle-même.
- Mapping `_CODE_HTTP` enrichi : `item_verrouille`→409,
  `etat_sequence_invalide`→400, `validation_pedagogique_echec`→400.

### Lecture (`services/v2_lecture.py`)
- `etat_code` exposé dans `sequence_par_niveau`. Lecture TOLÉRANTE : si la
  colonne n'existe pas (vieille base, DDL de test minimal), retombe sur
  'en_cours' (détection via PRAGMA table_info) — évite de casser les bases
  non migrées et les fixtures de test.

## Frontend (`static/atelier_seqniv_assemblage.js` + `index.html` + `app.css`)

### Régime mixte
- Constructeur : `persistanceImmediate: false`.
- `_rendreObjOuvert` : le bloc d'édition de l'objectif ouvert (nom, critères,
  séances, fin-cycle) est enveloppé dans `<form id="liv-atl-form">` ; les
  `onblur`/`onchange` immédiats de CES champs sont retirés (saisie bufferisée),
  remplacés par des `data-champ` lus par `collecterFormulaire()`.
- `collecterFormulaire()` : lit nom/critères/séances/fin-cycle de l'objectif
  ouvert ; renvoie null sans objectif ouvert. La base calcule `modifie` par
  diff snapshot.
- `sauvegarder()` : PATCH groupés (nom, critères, séances, fin-cycle) puis
  snapshot propre + rafraîchit le total de séances de la partie.
- `_installerListenerForm` (re)branché et snapshot pris à chaque `rafraichir`.
- Séances des objectifs FERMÉS (`_rendreObjFerme`) et des PARTIES : conservent
  `onblur` immédiat (`changerSeancesObj`/`changerSeancesPartie`).

### Garde
- `_garderAvantStructure()` : toast + refus si `modifie`. Posée sur `ouvrirObj`,
  `fermerObj`, et les 17 opérations de structure (drop*, retirer*, supprimer*,
  nouvellePartie, activerConnaitre, précédences, dropObj).

### État validable + verrou UI
- Toolbar (`index.html`) : badge d'état, bouton « Enregistrer l'objectif »
  (via `majToolbar` surchargée : visible si objectif ouvert + modifié + non
  verrouillé), bouton « Valider la séquence / Repasser en cours »
  (`basculerEtatSequence`).
- `validerSequence` / `devaliderSequence` : PATCH `/etat`. Sur 400
  pédagogique, toast listant les raisons (aperçu 6 max).
- `_appliquerEtatSequence()` (appelée par `rafraichir`) : libellé/visibilité
  du bouton d'état, badge, `_appliquerVerrouLectureSeule(valide)` sur le form,
  et classe `.asm-verrou-structure` sur le conteneur central.
- `app.css` : `.asm-etat-badge--encours/--valide` + `.asm-verrou-structure`
  (masque/neutralise les contrôles de structure quand validé ; en-têtes
  d'objectif restent cliquables pour consultation).

## Tests

- **pytest** : 3793 passed, 7 skipped, 0 failed (3774 + 19 nouveaux).
  - `tests/test_v0_16_9_etat_sequence_verrou.py` : cycle de vie de l'état,
    4 règles du hook, agrégation des raisons, verrou + variantes.
- **Vitest** : 65 passed (53 + 12 nouveaux).
  - `tests_js/seqniv_regime_mixte.test.js` : collecterFormulaire (avec/sans
    objectif, fin-cycle), snapshot/modifie, garde, _etatSequence, majToolbar
    (masquage save si non modifié / si verrouillé).
  - `tests_js/atelier_seqniv_assemblage.test.js` : assertions persistance
    immédiate mises à jour pour le régime mixte.
- **Syntaxe** : `node --check` OK (JS), `ast.parse` OK (Python).

## À vérifier côté Windows (validation visuelle)

1. Ouvrir un objectif → taper dans nom/critère/séances : le bouton
   « Enregistrer l'objectif » apparaît. Entrée dans le champ séances ne
   soumet pas le form.
2. Tenter d'ouvrir un autre objectif / glisser un exo / supprimer sans
   enregistrer → toast « Enregistrez vos modifications… », action bloquée.
3. Enregistrer → bouton disparaît, total de séances de la partie à jour.
4. Séances d'un objectif FERMÉ et d'une PARTIE : toujours immédiates (onblur).
5. Valider une séquence INCOMPLÈTE → toast listant les raisons (les 4 règles).
6. Valider une séquence COMPLÈTE → badge « Validée (lecture seule) », champs
   grisés, boutons de structure masqués, drag neutralisé. « Repasser en
   cours » reste actif.
7. Tenter une modif via l'API sur une séquence validée → 409 (toast).
8. Les 12 séquences identifiées comme complètes (N10/S01,S02,S04,S07,S08,S09 ;
   N12/S01,S02,S03,S04,S08,S10) doivent valider sans erreur.

## Note

La lecture de séquence est volontairement tolérante à l'absence de `etat_code`
(bases anciennes / fixtures). En fonctionnement normal, la migration post-DDL
ajoute la colonne au démarrage, donc `valider/devalider` trouvent toujours la
colonne quand la route `/etat` est appelée.
