# patch v0.10.2 — Précédences au niveau séquence + import C03

**Date** : 1 mai 2026

**Périmètre** : modèle de précédences au niveau séquence-niveau,
auto-import du cycle 3 (C03) en lecture-seule, validation backend stricte
de la provenance des exos R/EA, UI d'ajout/retrait de précédences dans
l'atelier d'assemblage.

**Score tests** : 1555/1555 passent (4 skipped historiques inchangés).
33 nouveaux tests dans `test_v0_10_2_precedences.py`.

---

## Vue d'ensemble

Cette livraison apporte trois changements complémentaires :

1. **Précédences au niveau séquence**. Une séquence-niveau (ex N11/S03)
   peut maintenant déclarer une ou plusieurs précédences (ex N10/S03,
   ou C03/S03). Les précédences servent à **filtrer les exos de
   révision** placables sur les parties de la séquence.

2. **Import du cycle 3 (C03) en lecture-seule** au démarrage. Si les CSV
   `C03_themes.csv`, `C03_sequences.csv` sont présents dans `data/` et
   que C03 n'est pas en BDD, ils sont importés automatiquement. Idempotent.

3. **Validation backend stricte de la provenance** des exos placés en
   révision (R) et approche (EA) sur les parties d'une séquence. Plus
   de tolérance silencieuse — le backend rejette désormais tout exo
   dont la provenance ne convient pas.

---

## 1 — Précédences au niveau séquence

### Schéma BDD

Nouvelle table `sequence_par_niveau_precedences` :

```sql
CREATE TABLE sequence_par_niveau_precedences (
    sequence_par_niveau_id TEXT NOT NULL
        REFERENCES sequences_par_niveau(id) ON DELETE CASCADE,
    precedent_niveau       TEXT NOT NULL,    -- 'N10', 'C03', etc.
    precedent_seq          TEXT NOT NULL,    -- 'S03'
    ordre                  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (sequence_par_niveau_id, precedent_niveau, precedent_seq)
);
```

La table existante `partie_precedences` (au niveau partie) est
**conservée** pour rétrocompatibilité avec l'éditeur v2 historique. Les
deux modèles coexistent pour l'instant. À long terme, `partie_precedences`
pourrait être migrée vers ce nouveau modèle puis supprimée.

### Service — `services/v2_edition.py`

- `lister_precedences_sequence(conn, sn_id)` → liste triée
- `ajouter_precedence_sequence(conn, sn_id, niveau, seq)` → 409 si
  doublon, 400 si circulaire (sn → sn) ou champs vides
- `retirer_precedence_sequence(conn, sn_id, niveau, seq)` → 404 si
  inexistante ; recompacte les `ordre` après suppression

### Routes — `routes/v2_edition.py`

| Méthode | URL | Rôle |
|---|---|---|
| GET | `/api/v2/sequences-par-niveau/<sn_id>/precedences` | Lister |
| POST | `/api/v2/sequences-par-niveau/<sn_id>/precedences` | Ajouter |
| DELETE | `/api/v2/sequences-par-niveau/<sn_id>/precedences/<niveau>/<seq>` | Retirer |

### Réponse v2_lecture enrichie

`GET /api/v2/sequences-par-niveau/<niveau>/<seq>` renvoie maintenant la
clé `precedences` au top-level, en plus des clés existantes :
```json
{
  "sequence_par_niveau": {...},
  "parties": [...],
  "etat_ui": {...},
  "precedences": [
    {"precedent_niveau": "N10", "precedent_seq": "S03", "ordre": 1}
  ]
}
```

### UI — bloc Précédences dans l'atelier d'assemblage

Sous le header de séquence (« N11 S03 Fractions »), un nouveau bloc
compact :

```
Précédences :  [N10 / S03  ✕]  [+ Ajouter]
```

- Liste horizontale de pills (chip avec ✕ à droite) pour chaque
  précédence déclarée.
- Bouton « + Ajouter » qui révèle un mini-formulaire avec deux selects :
  - **Niveau** : C03 / N10 / N11 / N12 (codé en dur, extensible)
  - **Séquence** : alimenté dynamiquement depuis
    `GET /api/cycles/<C03|C04>/sequences` selon le niveau choisi.
- Validation → POST ; succès → rafraîchissement de l'atelier.

---

## 2 — Auto-import du cycle 3 (C03)

### Nouveau service `services/cycle_auto_import.py`

Au démarrage de l'application (`create_app`), pour chaque cycle connu
(`C03`, `C04`) :

- Si les CSV `<code>_themes.csv` et `<code>_sequences.csv` sont présents
  dans `data/` ET que le cycle n'est pas encore en BDD → on lance
  `importer_cycle()`.
- Si le cycle est déjà en BDD → on ne fait rien (idempotence).
- Si les CSV sont absents → on saute en silence.
- Toute erreur est journalisée sur `stderr` mais ne bloque pas le
  démarrage de l'app.

### Conséquences pratiques

Au prochain démarrage de l'application après déploiement :

- **Si `data/C03_themes.csv` et `data/C03_sequences.csv` sont présents**
  dans le dossier data de Laurent (ils le sont d'après les fichiers
  fournis) → C03 est importé automatiquement avec ses 3 thèmes
  (Nombres et Calculs, Grandeurs et mesures, Espace et géométrie) et
  ses 16 séquences.

- **C04 reste comme avant**, déjà importé manuellement par Laurent.

- **Les `connaissances` et `objectifs` C03 ne sont pas importés** —
  prévu en roadmap après le CRUD du découpage de cycle.

### Tests adaptés

`test_R1_routes` partait du principe que la table `cycles` était vide au
démarrage. Avec l'auto-import, ce n'est plus le cas. Adaptations :

- `test_lister_cycles_vide_au_depart` → renommé en
  `test_lister_cycles_apres_demarrage` : C04 est désormais présent.
- `test_importer_cycle_basique` et `test_importer_idempotent` : les POST
  manuels deviennent des UPDATE plutôt que des INSERT.
- Conftest : ajout de la colonne `Description` (vide) au CSV de test
  C04, requise par `cycle_import.py`.

---

## 3 — Validation backend stricte des exos R/EA

### Règles métier appliquées

Lors d'un POST sur `/api/v2/parties/<id>/exos-revision-approche` :

#### Pour `type='EA'` (approche) :
- L'exercice DOIT appartenir à la séquence-niveau courante (même
  `niveau` et même `sequence_code`).
- L'exercice DOIT avoir `serie_code='EA'`.

#### Pour `type='R'` (révision) :
- L'exercice DOIT avoir `serie_code='A'`.
- La séquence d'origine de l'exercice (son `niveau`/`sequence`) DOIT
  figurer dans les précédences de la séquence-niveau courante.

### Nouvelles exceptions / codes HTTP 409

| Code | Cas |
|---|---|
| `exo_approche_hors_sequence` | EA d'une autre séquence |
| `exo_approche_mauvaise_serie` | EA mais série ≠ EA |
| `exo_revision_mauvaise_serie` | R mais série ≠ A |
| `exo_revision_hors_precedences` | R mais provenance hors précédences |

### Origin_* remplis automatiquement

Les paramètres `origin_niveau`, `origin_seq`, `origin_serie`,
`origin_num` du payload **sont ignorés** depuis v0.10.2. Le backend les
remplit lui-même depuis les métadonnées de l'exercice. Le client n'a
plus à les fournir, ce qui simplifie l'UI et garantit la cohérence.

La signature de la fonction reste compatible (les paramètres sont
acceptés mais ignorés) pour ne casser aucun appel existant.

### Tests adaptés

`test_v0_10_assemblage` avait 3 tests qui passaient sans précédence
déclarée (comportement permissif d'avant). Adaptations :

- `test_ajouter_R_avec_origin` : ajoute la précédence N10/S03 avant.
- `test_meme_exo_R_et_EA_autorise` → renommé en
  `test_R_et_EA_independants_meme_partie` : on n'autorise plus le
  même exo en R et EA, mais on peut placer un exo EA *et* un autre
  exo R dans la même partie.
- `test_parties_montrent_exos_ajoutes` : ajoute la précédence avant.
- `TestRoutes.populated` enrichie d'un exo N10/S03 série A et de la
  précédence N10/S03 sur sn_X, pour permettre les tests R.

---

## Compteur de tests

```
Tests v0.10.2 (nouveau fichier test_v0_10_2_precedences.py) : 33
  - TestPrecedencesSequence (10 tests CRUD)
  - TestValidationApproche (3 tests EA stricte)
  - TestValidationRevision (5 tests R stricte)
  - TestAutoImportCycles (3 tests idempotence)
  - TestV2LectureEnrichie (2 tests integration)
  - TestRoutes (10 tests Flask)

Total suite : 1555 / 1555 (4 skipped historiques).
```

---

## Procédure de test manuel après déploiement

1. **Au démarrage** : vérifier dans les logs que C03 a été importé
   (« Cycle C03 importé automatiquement : 3 thèmes, 16 séquences »).
   Vérifier aussi via Admin > BDD que la table `sequence_par_niveau_precedences`
   existe et est vide.

2. **Atelier Séquence** : ouvrir une N11/S03. Le bloc « Précédences : »
   apparaît sous le header avec « Aucune. » en italique.

3. **Ajouter une précédence** : cliquer « + Ajouter » → choisir Niveau
   N10, Séquence S03 dans le sélecteur (peuplé à la volée), valider.
   La pill « N10 / S03 » apparaît.

4. **Tester la validation R** : ouvrir un objectif et tenter de drag un
   exo de révision. À l'heure actuelle, l'UI ne permet pas encore
   de drag des exos R (sera fait en v0.10.3 — refonte sidebar). Test à
   reporter ou à faire via curl :
   ```bash
   curl -X POST http://localhost:5000/api/v2/parties/<pt_id>/exos-revision-approche \
     -H 'Content-Type: application/json' \
     -d '{"type":"R","exercice_id":"<ex_a_n10_id>"}'
   ```

5. **Retirer la précédence** : cliquer ✕ sur la pill. Confirmation
   automatique, la pill disparaît.

6. **Test cas limite** : tenter d'ajouter N11/S03 en précédence de
   N11/S03 (circulaire). Devrait afficher « Précédence invalide ».

---

## Pas inclus dans v0.10.2 (différé)

- **Refonte de la sidebar pour exposer les exos R/EA selon les
  précédences** : prévu en v0.10.3. Aujourd'hui, l'UI ne montre pas les
  exos disponibles dans la sidebar pour les types R/EA — il faut passer
  par l'éditeur v2 ou des appels directs à l'API.

- **Précédences automatiques au peuplement initial** : pas implémenté.
  Laurent ajoute manuellement les ~28 précédences N11/N12 → N10
  via l'UI.

- **CRUD complet du cycle 3** (modification, suppression de séquences
  C03) : roadmap, après que l'usage de C03 en lecture seule sera
  stabilisé.

---

## Pièges connus / points d'attention

- **CSV C03 doivent être présents au démarrage**. S'ils sont absents,
  l'auto-import est silencieusement sauté ; le sélecteur de séquence
  dans le popover Précédences affichera « Cycle C03 non importé ». Il
  faut alors copier les CSV dans `data/` et redémarrer l'app.

- **Les niveaux du sélecteur sont codés en dur** (C03, N10, N11, N12).
  Si Laurent ajoute un autre niveau (par exemple N09 = CM2), il faudra
  l'ajouter manuellement à la liste dans
  `static/atelier_seqniv_assemblage.js` (méthode
  `_rendreBlocPrecedences`). Devra être généralisé dans la roadmap CRUD.

- **Les origin_* du POST sont ignorés depuis v0.10.2**. Les anciens
  scripts ou clients qui les envoyaient continuent de fonctionner mais
  les valeurs sont écrasées par celles lues depuis l'exercice. C'est
  intentionnel et conforme au principe de séparation des rôles
  (le backend détient la vérité métier, pas le client).

- **Le test `test_meme_exo_R_et_EA_autorise` a été renommé** en
  `test_R_et_EA_independants_meme_partie` pour refléter le nouveau
  contrat : un exo ne peut pas être à la fois EA et R d'une partie
  (puisque chaque type a ses propres contraintes de provenance qui
  s'excluent en pratique). Mais on peut avoir des exos EA *et* d'autres
  exos R dans la même partie.
