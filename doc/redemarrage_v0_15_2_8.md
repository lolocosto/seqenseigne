# Redémarrage v0.15.2.8 — Passe pdflatex + auto-validation référentiel

Deux parties dans cette version :
1. **Partie A** : numéro de passe pdflatex en plus du compteur de pages
   (suite v0.15.2.7 : « ça bouge, mais pas assez »).
2. **Partie B1** : auto-validation lazy des référentiels + bouton
   manuel + diagnostic UI. **Le figeage proprement dit (B2) reste pour
   v0.15.2.9** — découpage volontaire pour valider B1 sur le terrain
   avant d'engager le snapshot.

## Décisions Laurent

1. **Auto-validation** : Mix lazy + bouton manuel — recalcul automatique
   à l'ouverture de la liste des référentiels, plus un bouton
   « Revérifier l'éligibilité » pour forcer la réévaluation.
2. **Au figeage** (v0.15.2.9) : snapshot léger — copie des PDF +
   **trace JSON** (= structure complète des séquences et évaluations,
   identité des atomes utilisés ; le contenu pédagogique reste dans
   les PDF).
3. **Périmètre des assemblages** : approche métier — tout ce qui est
   nécessaire pour le suivi annuel (séquences et évaluations complètes).
4. **Découpage v0.15.2.8 / v0.15.2.9** : B1 (auto-validation) puis B2
   (action de figeage).

## Partie A — Passe pdflatex

### Mécanique

- `compiler_atome(..., on_passe_demarree=callable)` : nouveau param
  optionnel. La callback reçoit 1 puis 2 avant chaque
  `_lancer_pdflatex()`. Une callback qui lève est silencieusement avalée
  (ne casse jamais la compile).
- `orchestrateur_compilation.compiler(..., on_passe_demarree=...)`
  propage la callback.
- Worker compilation : fournit une callback `_maj_passe(num)` qui pose
  `passe_courante=num` ET `page_courante=None` dans le statut (reset
  du compteur de pages entre passes — pdflatex écrase le `.log`).
- Statut enrichi de deux nouveaux champs : `passe_courante` (1 ou 2)
  et `passes_total` (= 2, constante exposée pour affichage UI).

### Côté UI

`atelier_referentiel.js` — `_atlRefMajProgress` :
- Affichage : `5/14 — Compilation : Planches N10/S05 (passe 2/2, page 17)`
- Fallback : si seulement `page_courante` connu (cas test/compat),
  on retombe sur `(page N)` comme en v0.15.2.7.

## Partie B1 — Auto-validation lazy

### Règle métier (Laurent)

Un référentiel passe automatiquement en `valide` quand TOUS ces
critères sont vrais :

- Tous les atomes du niveau (notions, méthodes, exercices, fiches de
  résumé, cartes d'automatisme) sont à `etat_code='valide'`.
- Toutes les évaluations du niveau sont à `etat_code='valide'`.
- Tous les documents actifs du référentiel sont compilés avec succès
  (`compile_ok=1`) ET non périmés (cf. `peremption_atomes`).

Si l'un quelconque de ces critères devient faux après avoir été vrai,
le référentiel retombe à `en_cours` à la prochaine lecture lazy (sauf
s'il est déjà `fige` : état terminal immuable).

### Nouveau service `services/referentiel_validation.py`

| Fonction | Rôle |
|---|---|
| `evaluer_eligibilite_validation(conn, ref_id) → dict` | Diagnostic structuré (lecture seule) : eligible, raisons, details (compteurs par critère) |
| `maj_etat_lazy(conn, ref_id) → str` | Évalue + applique la transition (`en_cours ↔ valide`). Ne touche jamais `fige`/`annule`. |

### Documents inactifs ignorés

Un document avec `options.actif=False` n'entre PAS dans le calcul
d'éligibilité. C'est cohérent avec la sémantique « inactif = pas
souhaité par l'utilisateur ». Évite de bloquer la validation quand
des documents en option sont volontairement laissés non compilés.

### Endpoints (routes/referentiels.py)

| Méthode | Endpoint | Effet |
|---|---|---|
| GET | `/api/referentiels/<id>/eligibilite_validation` | Diagnostic seul (lecture pure) |
| POST | `/api/referentiels/<id>/revalider` | Force recalcul + transition + diagnostic |

### Lazy automatique sur listage

`services.referentiels.lister_par_niveau` appelle `maj_etat_lazy` pour
chaque référentiel `en_cours`/`valide` avant de renvoyer la liste.
Conséquence : un simple `GET /api/referentiels?niveau=N10` (déclenché
à l'ouverture de l'atelier référentiel) suffit à mettre à jour les
états visibles.

### Côté UI

Nouveau bloc `#atl-ref-diag-validation` dans `templates/index.html`,
sous les boutons d'action. Alimenté par `atelRefMajDiagValidation()` :
- Vert pâle + « Référentiel éligible. Tous les atomes, évaluations et
  documents sont validés. » si éligible.
- Orange pâle + liste à puces des raisons de non-éligibilité sinon
  (ex. « 3 exercices non validés », « 1 document périmé »).
- Caché pour `fige` et `annule` (états terminaux).

Nouveau bouton **« Revérifier l'éligibilité »** à côté de Supprimer/Figer.
Disponible pour `en_cours` et `valide`. POST sur `/revalider`,
rechargement liste, conservation de la sélection courante.

## Tests

**v0.15.2.8 : 3577 passed, 6 skipped, 0 failed** (+31 par rapport à v0.15.2.7).

### Nouveaux fichiers

| Fichier | Nb | Couverture |
|---|---|---|
| `tests/test_v0_15_2_8_passe_compilation.py` | 8 | Signature callback, ordre des appels, callback défaillante avalée, statut initial, reset page entre passes |
| `tests/test_v0_15_2_8_validation_referentiel.py` | 15 | Éligibilité OK, chaque critère individuel, libellés des raisons, transitions lazy, intangibilité fige/annule |
| `tests/test_v0_15_2_8_validation_routes.py` | 8 | Routes GET diagnostic / POST revalider / GET liste lazy |

## Fichiers livrés

| Fichier | Type |
|---|---|
| `appli/services/compilateur_pdf.py` | Modifié (callback `on_passe_demarree`) |
| `appli/services/orchestrateur_compilation.py` | Modifié (propagation callback) |
| `appli/services/referentiel_documents_compilation.py` | Modifié (statut + worker callback) |
| `appli/services/referentiels.py` | Modifié (hook lazy dans `lister_par_niveau`) |
| `appli/services/referentiel_validation.py` | Nouveau |
| `appli/routes/referentiels.py` | Modifié (2 endpoints) |
| `appli/static/atelier_referentiel.js` | Modifié (suffixe progression + diag + revalider) |
| `appli/templates/index.html` | Modifié (bouton revalider + bloc diag) |
| `appli/tests/test_v0_15_2_8_passe_compilation.py` | Nouveau |
| `appli/tests/test_v0_15_2_8_validation_referentiel.py` | Nouveau |
| `appli/tests/test_v0_15_2_8_validation_routes.py` | Nouveau |
| `appli/doc/redemarrage_v0_15_2_8.md` | Nouveau (ce document) |

Pas de `.dtx`/`.sty`, pas de changement BDD.

## Vérification

```powershell
.\outils\python\python.exe outils\verifier_md5.py --racine . --manifest MANIFEST.md5
.\outils\python\python.exe -m pytest -q
# Attendu : 3577 passed, 6 skipped, 0 failed
```

## Effet attendu côté UI

### Pendant la compilation
```
5/14 — Compilation : Planches N10/S05 (passe 1/2, page 12)
5/14 — Compilation : Planches N10/S05 (passe 1/2, page 25)
5/14 — Compilation : Planches N10/S05 (passe 2/2, page 3)
5/14 — Compilation : Planches N10/S05 (passe 2/2, page 17)
```

### Sur la page Atelier référentiel
- Encart vert pâle « Référentiel éligible » → bouton Figer apparaît
  (déjà existant en v0.13.5.1 — `figer_minimal`).
- Encart orange pâle « Reste à valider : N exercices, M documents
  périmés… » → bouton Revérifier visible mais Figer caché.
- À la prochaine ouverture de la page, l'état est recalculé sans
  action explicite.

## v0.15.2.9 — Suite (figeage proprement dit)

Reste à faire après validation B1 sur le terrain :

### Trace JSON proposée
```json
{
  "version_schema": 1,
  "date_figeage": "2026-05-30T14:23:45Z",
  "referentiel": {"id","niveau","version","date_debut","date_fin","description"},
  "themes":    [{"code","nom","couleur"}],
  "sequences": [{
      "code","numero","nom","theme_code",
      "parties":    [{"numero","nb_seances_R_AE"}],
      "objectifs":  [{"code","nom","fin_cycle","critere_f/a/e","partie_numero","nb_seances"}],
      "precedents": [{"niveau","sequence","ordre"}],
      "atomes_utilises": {
          "notions":           [{"id","num_connaissance","titre"}],
          "methodes":          [{"id","num_methode","titre"}],
          "exercices":         [{"id","num","serie","titre"}],
          "fiches_resume":     [{"id","num_fiche","titre"}],
          "cartes_automatisme":[{"id","num","type_pedago","titre"}]
      }
  }],
  "evaluations": [{
      "id","numero","ordre","titre","mode_notation",
      "sequences_couvertes": ["S01","S02"],
      "exercices":  [{"exercice_id","ordre","bareme_points"}],
      "objectifs":  [{"objectif_id"}]
  }],
  "documents": [{
      "id","type_document","options","compile_date",
      "cibles": [{"cible_id","libelle","nom_fichier"}]
  }]
}
```

### Action `figer_referentiel(conn, ref_id)`
1. Vérification éligibilité (refuser si non éligible).
2. Création dossier `data/referentiels/<ref_id>/_fige/` (ou similaire).
3. Copie des PDF actifs depuis `_artefacts/` vers `_fige/pdfs/`.
4. Génération `trace.json`.
5. `UPDATE referentiel_niveaux SET etat='fige', date_debut=NOW()`.
6. Annulation des concurrents (déjà géré par `figer_minimal`).

### À cadrer en début de session v0.15.2.9
- Emplacement physique du dossier `_fige` (sous `data/` ?).
- Format des chemins PDF dans la trace : relatif au dossier `_fige`
  ou absolu ?
- Routes/UI : modifier le bouton « Figer » existant pour qu'il
  appelle la version complète (au lieu de `figer_minimal`).
- Tests bout-en-bout : compile → revalide → fige → vérifier
  structure du dossier `_fige`.

## Rappels roadmap & dette technique (à mémoriser entre sessions)

### Roadmap globale
- **v0.15.2.9** — Figeage complet (B2) ← prochaine session
- **Atelier assemblage séquence-dans-niveau** (EN COURS dans userMemories) — bug `_cycle_du_niveau` qui résout C03 pour N10/N12
- **Diagnostic perf tcolorbox** (piste D v0.15.2.5) — pourquoi 25-30 s/séquence
- **v0.13** — CRUD cycles/niveaux/thèmes/séquences (aujourd'hui en lecture seule via CSV) ; remplacer `_NOM_COURT_NIVEAU` par lecture DB ; import C03 complet
- **v0.14** — Admin refonte + nettoyage (supprimer `exercice_objectifs`, `edition_progression.py`, JS `ATL_OBJ_CAT`, route `/api/objectifs`, table `objectifs`) ; diagnostic atomes orphelins
- **v0.15** — Progressions annuelles adaptées aux nouvelles refs ; reprise suivi classes
- **v0.15+** — Concepts « mise en route » et « automatisme »

### Sans version fixée
- Tests JS automatisés (Vitest/Jest)
- Fil d'Ariane (remplacement export/import)
- Internationalisation niveaux (lecture DB, prérequis CRUD cycle v0.13)
- Atelier « Récap livrets » (14 livrets en une fois)
- Rationalisation tracking imports (`SequencesDB` dupliqué)
- Audit 4 sous-chantiers (3a JS, 3b CSS, 3c routes/services, 3d archi)
- Outil de comparaison PDF visuel (`diff-pdf` ou `pdftoppm`+`compare`)
- Signalisation scope visuel des ateliers (Séquence vs Cycle)
- Option compilation dyslexie (xeLaTeX + OpenDyslexic + A3)
- Force PDF iframe (Firefox PC scolaire)

### Dette technique active
- **livret_plans / evaluation péremption « hors atomes »** (TODO v0.15.2.6) — câbler quand atelier assemblage exposera ses mtimes
- **3-full cleanup série R** — supprimer `objectif_exos.origin_*`, propager SELECT/INSERT, évaluer `lister_exos_disponibles_pour_revision`
- **Bug `_cycle_du_niveau`** (v0.12.1.1) — résout C03 pour N10/N12
- **`atelChargerObjectifs` 5 erreurs console** (silencieuses, removal complet v0.14)
- **Workdirs orphelins** dans `tempfile.gettempdir()/seqenseigne_workdir/` (v0.15.2.7) — purge admin si volume gênant
- **Q2/Q3 chantier v1** (post v0.14.7) — `services/v2_lecture` / `v2_edition`, routes `/api/v2/*`, classes `V2*Erreur`
