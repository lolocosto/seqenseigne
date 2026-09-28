# v0.19 — Phase 0 : audit de correspondance référentiel ↔ progression

Document d'analyse, **sans code**. Objectif : cartographier ce qu'un
référentiel verrouillé contient en base, ce que l'écran de progression
manipule aujourd'hui, et lister correspondances + divergences (notamment les
références mortes à SequenceDB et au système « versions distribuées »).

---

## 1. Le référentiel verrouillé (source de vérité cible)

Modèle d'état (README v0.15.3) :
`en_cours → valide → verrouille → utilise` (+ `annule`). Seul un référentiel
`verrouille` (ou `utilise`) est exploitable par une progression ; pour le
modifier, l'utilisateur doit le déverrouiller, ce qui le rend inutilisable en
progression.

Arborescence en base (tables `referentiel_*`) :

| Table | Colonnes clés | Rôle |
|---|---|---|
| `referentiel_niveaux` | id, niveau, version, date_debut/fin, description, **etat** | L'entité racine versionnée + son état |
| `referentiel_themes` | referentiel_id, code, nom, couleur | Thèmes du référentiel |
| `referentiel_sequences` | referentiel_id, code, numero, nom, theme_code | Séquences |
| `referentiel_objectifs` | referentiel_id, seq_code, code, nom, fin_cycle, critere_f/a/e, **partie_numero**, **nb_seances** | Objectifs, avec n° de partie et **nombre de séances prévu** |
| `referentiel_documents` | id, referentiel_id, type_document, options(JSON), ordre, compile_ok/date/log | **Les livrets distribués** (ex-« versions distribuées ») + leur état de compilation |

Points saillants pour la progression :
- **`referentiel_objectifs.nb_seances`** : le nombre de séances **prévu** par
  objectif → base du futur comptage « prévu vs réalisé » (fonctionnalité
  v0.19.1+).
- **`referentiel_objectifs.partie_numero`** : rattache l'objectif à une partie
  de séquence (les créneaux portent déjà `partie_debut`/`partie_fin`).
- **`referentiel_documents`** : remplace conceptuellement le bloc « Versions
  distribuées aux élèves » de l'écran progression.

État des données (extrait) : N10/N11/N12 ont plusieurs référentiels
`verrouille` (2021→2025) + un `en_cours` récent. N09 n'a pas encore de
référentiel listé dans `referentiel_niveaux` (à confirmer avec Laurent —
peut-être normal à ce stade).

---

## 2. La progression aujourd'hui (état réel)

Tables :

| Table | Colonnes | Observations |
|---|---|---|
| `progressions` | id, niveau, annee, etablissement_id, **source**, referentiel_id, etat | `referentiel_id` **existe déjà** (lien établi). `source='sequencesdb'` = trace de l'ancien modèle (à retirer). |
| `creneaux` | id, progression_id, seq_code, partie_debut/fin, partie, periode, date_debut/fin, revisions, ordre | Pas de lien direct aux objectifs ; le rattachement passe par seq_code + partie. |
| `creneau_objectifs_seances` | creneau_id, obj_code, **nb_seances** | **VIDE** — prévu pour le réalisé par objectif, jamais peuplé. |
| `creneau_objectifs_exos` | creneau_id, obj_code, exos_F/A/E | **VIDE** — idem. |

Écran (`stab-progression`, templates/index.html) :
- Bandeau sélection (année / établissement / niveau) → **fonctionne**.
- Création : `progOuvrirDialogueCreation` → choix d'un référentiel via
  `/api/referentiels?niveau=` → POST `/api/progression/<niveau>`. **La
  création est déjà branchée sur le référentiel** (bon point de départ).
- Calendrier semainier + formulaire d'ajout de créneau → présents.
- **« Objectifs de ce créneau »** (`#prog-objectifs-list`) : zone à réalimenter
  depuis `referentiel_objectifs` (aujourd'hui logique floue / héritée).
- **« Versions distribuées aux élèves »** (bloc `liv-*`, `creerVersion`,
  routes `/api/versions`) : **système parallèle obsolète**. Faisait des
  snapshots de livrets ; ce rôle est désormais tenu par
  `referentiel_documents`.

---

## 3. Correspondances et divergences

| Concept écran progression | Source actuelle (morte/floue) | Source cible (référentiel verrouillé) | Action Phase 1 |
|---|---|---|---|
| Séquences du niveau | SequenceDB / mixte | `referentiel_sequences` (du referentiel_id de la progression) | Lire depuis le référentiel lié |
| Objectifs d'un créneau | flou (`creneau.objectifs`) | `referentiel_objectifs` filtrés par seq_code + partie | Réalimenter `#prog-objectifs-list` |
| Thèmes / couleurs | mixte | `referentiel_themes` | Aligner |
| « Versions distribuées » | `/api/versions` + `liv-*` (snapshots) | `referentiel_documents` (livrets du référentiel) | Retirer le bloc, ou le remplacer par un affichage en lecture seule des documents du référentiel |
| `progressions.source='sequencesdb'` | colonne héritée | — | Neutraliser / ignorer (suppression colonne = plus tard, recréation table) |
| Nb séances prévu | absent de l'écran | `referentiel_objectifs.nb_seances` | Exposer (prépare v0.19.1 comptage) |

Imports morts repérés :
- `routes/progression.py` ligne 8 :
  `from importers.sequencesdb import lire_sequencesdb, importer_classe_historique, suivi_historique_vers_niveaux`
  → à auditer : ces imports servent-ils encore au **suivi historique**
  (import des anciennes données) ou peuvent-ils être retirés du chemin de
  création/édition de progression ?

---

## 4. Fonctionnalités nouvelles (v0.19.1+, hors réalignement)

Repérées avec Laurent, à spécifier en sessions dédiées :
1. **Semaines A/B** (nombre de créneaux différent selon la semaine).
2. **Séance supprimée / déplacée** (statut par créneau/séance).
3. **Comptage automatique** des séances réellement programmées + **écart**
   avec `referentiel_objectifs.nb_seances` (prévu).
4. (autres à émerger).

---

## 5. Questions ouvertes pour cadrer la Phase 1 (réalignement)

- **Q-P1.1** — « Objectifs de ce créneau » : un créneau couvre
  `partie_debut`→`partie_fin` d'une séquence. Les objectifs affichés doivent-ils
  être **tous** les `referentiel_objectifs` dont `partie_numero` ∈ [debut, fin]
  pour ce `seq_code` ? Ou un sous-ensemble choisi par l'utilisateur ?
- **Q-P1.2** — « Versions distribuées aux élèves » : on **retire** purement le
  bloc (les livrets se gèrent dans l'atelier référentiel), ou on le **remplace**
  par un affichage lecture seule des `referentiel_documents` du référentiel lié
  à la progression ?
- **Q-P1.3** — Les progressions existantes ont `source='sequencesdb'`. On
  garde la colonne (ignorée) pour la v0.19.0 et on la nettoiera plus tard
  (recréation de table), ou on la traite maintenant ?
- **Q-P1.4** — Que faire d'une progression liée à un référentiel qui serait
  **déverrouillé** ensuite (repassé `en_cours`) ? Bloquer l'édition de la
  progression ? Afficher un avertissement ? (lié à l'état `utilise`.)
- **Q-P1.5** — `importers.sequencesdb` : encore nécessaire pour le suivi
  historique (onglet « Suivi des séquences »), ou retirable du flux progression ?
