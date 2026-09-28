# Redémarrage v0.15.2.9 — Fix regex parser + figeage complet

Deux livrables dans cette version :
1. **Fix regex parser pdflatex** — corrige le bug rapporté par Laurent
   sur les planches de cartes (compteur de pages absent).
2. **Action de figeage complète (B2)** — suite logique de la
   v0.15.2.8 (auto-validation B1).

## Partie 1 — Fix regex parser pdflatex

### Bug v0.15.2.8 — diagnostic terrain Laurent

> *« Pour le livret d'exercices, j'ai bien eu l'affichage de la progression
> du nombre de pages compilées, mais pas pour les planches de cartes
> d'automatisme. »*

Investigation : tous les documents passent par le même flux (`orch.compiler`
→ `compiler_atome`). Le code est déjà factorisé.

**Cause** : pdflatex écrit pour la première page
```
[1\n\n{/var/lib/texmf/fonts/map/pdftex/updmap/pdftex.map}]
```
(la carte des polices est embarquée DANS le marqueur de page 1).
L'ancienne regex stricte `\[(\d+)\]` ne matchait PAS ce cas.

Pour `livret_exercices`, la page 2 arrivait en quelques secondes →
compteur visible. Pour `livret_cartes_planches`, la première page
(16 tcolorbox) prend 15-20 s → l'UI restait silencieuse tout ce temps,
donnant l'impression de plantage.

### Fix

Une ligne dans `services/log_pdflatex_parser.py` :

```python
# Avant :
_RE_PAGE = re.compile(rb'\[(\d+)\]')

# Après :
_RE_PAGE = re.compile(rb'\[(\d+)(?![\d.a-zA-Z])')
```

Le negative-lookahead capture `[N` suivi de tout caractère qui n'est
ni chiffre, ni point, ni lettre — couvre `[1\n{...}]`, `[1]`, `[1{}`
tout en rejetant `[1pt]` (warning), `[1.5]` (ratio), `[Lab12]` /
`[Sec1.2]` (références).

Tous les tests v0.15.2.6 originaux passent encore (rétrocompat totale)
+ 8 nouveaux tests dans `tests/test_v0_15_2_9_log_parser_first_page.py`
qui verrouillent les nouveaux cas et les faux positifs à ne pas
matcher.

## Partie 2 — Action de figeage (B2)

### Périmètre

Suite logique de la v0.15.2.8 (auto-validation lazy + bouton manuel) :
- v0.15.2.8 : un référentiel devient automatiquement `valide` quand
  tous ses atomes/évals/docs sont validés.
- v0.15.2.9 : le bouton « Figer » fait maintenant un figeage **complet**
  (et non plus minimal).

### Layout figé

```
data/referentiels/<ref_id>/
    _artefacts/<doc_id>/<cible_key>.{tex,log,pdf}   (sources actives)
    <nom_fichier>.pdf                                (PDFs métier actifs)
    _fige/                                            ← NOUVEAU
        trace.json                                    structure complète
        pdfs/<nom_fichier>.pdf                        copies figées
```

### Trace JSON — schéma v1

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
      "exercices":  [{"exercice_id","ordre","bareme_points"}],
      "objectifs":  [{"objectif_id"}]
  }],
  "documents": [{
      "id","type_document","options","compile_date",
      "cibles": [{"cible_id","libelle","nom_fichier","chemin_pdf"}]
  }]
}
```

**Principe** : identité (ids + métadonnées clés pour le suivi annuel
futur), PAS le contenu pédagogique (texte des énoncés, démos, etc.)
qui reste dans les PDF figés.

**Chemins PDF** : relatifs au dossier `_fige` (`pdfs/livret_...pdf`).
Le dossier est ainsi déplaçable.

### Nouveau service `services/referentiel_figeage.py`

| Fonction | Rôle |
|---|---|
| `generer_trace(conn, ref_id, lister_cibles)` | Construit la trace JSON complète |
| `copier_pdfs(trace, dossier_source, dossier_cible)` | Copie les PDF actifs ; rapport `{copies, echecs}` |
| `figer_complet(conn, ref_id, dossier_ref, lister_cibles, ...)` | Action complète : éligibilité → trace → copie PDF → transition d'état |

Le service réutilise :
- `services.referentiels.figer_minimal` pour la transition d'état + annulation des concurrents.
- `services.referentiel_validation.evaluer_eligibilite_validation`
  pour valider l'éligibilité avant de toucher au disque.

### Workflow `figer_complet`

1. Vérifier éligibilité → `ValueError` avec raisons si non éligible.
2. Vérifier état == `valide` → `ValueError` sinon.
3. Lister concurrents (suffixes antérieurs). Si présents et
   `force_confirme=False` → renvoie `confirmation_requise: True` sans
   toucher au disque ni à la BDD.
4. Créer `<ref>/_fige/trace.json`.
5. Copier les PDFs actifs vers `<ref>/_fige/pdfs/`.
6. Appliquer la transition d'état + annulation des concurrents
   (déléguée à `figer_minimal`).

Retour en succès :
```json
{
  "confirmation_requise": false,
  "ref": {"id","niveau","version","etat":"fige","date_debut"},
  "concurrents_annules": [...],
  "fige": {
    "dossier": ".../_fige",
    "trace": ".../_fige/trace.json",
    "nb_pdfs_copies": 14,
    "echecs_copie": []
  }
}
```

### Route `POST /api/referentiels/<id>/figer`

Étendue pour appeler `figer_complet`. Codes HTTP :
- **200** + résultat normal en succès ou en `confirmation_requise`.
- **404** si référentiel introuvable.
- **409** si état != valide OU si non éligible (message indique les raisons).

### Côté UI

`atelRefFiger()` (handler existant) déjà adapté au double appel
(`force_confirme=false` puis `true` après confirmation). v0.15.2.9 met
à jour le message final pour surfacer :
- chemin de la trace,
- nombre de PDFs copiés,
- éventuels échecs de copie avec leur raison.

(Pas de nouvelle vue de la trace JSON dans cette version — chantier
ultérieur pour une consultation humaine.)

## Tests

**v0.15.2.9 : 3605 passed, 6 skipped, 0 failed** (+28 par rapport à v0.15.2.8).

### Nouveaux fichiers

| Fichier | Nb | Couverture |
|---|---|---|
| `tests/test_v0_15_2_9_log_parser_first_page.py` | 8 | Cas réel pdflatex `[1\n{path}]`, faux positifs `[1pt]`/`[1.5]`/`[Lab12]`, retours mixtes warning + page |
| `tests/test_v0_15_2_9_figeage.py` | 15 | Structure trace, sections (themes, sequences, atomes_utilises, evaluations, documents), copie PDF, refus si non éligible/non valide, succès → état fige + trace écrite, gestion concurrents avec/sans force_confirme |
| `tests/test_v0_15_2_9_figeage_route.py` | 5 | 404/409/200, trace écrite sur disque, message d'erreur lisible |

## Fichiers livrés

| Fichier | Type |
|---|---|
| `appli/services/log_pdflatex_parser.py` | Modifié (regex fix) |
| `appli/services/referentiel_figeage.py` | Nouveau |
| `appli/routes/referentiels.py` | Modifié (figer → figer_complet) |
| `appli/static/atelier_referentiel.js` | Modifié (msg succès enrichi) |
| `appli/tests/test_v0_15_2_9_log_parser_first_page.py` | Nouveau |
| `appli/tests/test_v0_15_2_9_figeage.py` | Nouveau |
| `appli/tests/test_v0_15_2_9_figeage_route.py` | Nouveau |
| `appli/doc/redemarrage_v0_15_2_9.md` | Nouveau |

Pas de `.dtx`/`.sty`, pas de changement BDD : tout en backend Python + un
mini-ajustement JS.

## Vérification

```powershell
.\outils\python\python.exe outils\verifier_md5.py --racine . --manifest MANIFEST.md5
.\outils\python\python.exe -m pytest -q
# Attendu : 3605 passed, 6 skipped, 0 failed
```

## Effet attendu côté UI

### Compilation des planches
Le compteur de pages doit maintenant fonctionner DÈS la première page :
```
3/14 — Compilation : Planches N10/S03 (passe 1/2, page 1)
3/14 — Compilation : Planches N10/S03 (passe 1/2, page 4)
3/14 — Compilation : Planches N10/S03 (passe 1/2, page 8)
```

### Action « Figer »
Après confirmation :
```
Référentiel "2025_N10" figé avec succès.

Trace : /data/referentiels/2025_N10/_fige/trace.json
PDFs copiés : 14
```
Le dossier `data/referentiels/<ref_id>/_fige/` contient désormais :
- `trace.json` (~quelques Ko)
- `pdfs/<nom_fichier>.pdf` (chaque PDF actif copié)

## Pistes pour les sessions suivantes

### Roadmap directe
- **Utilisation des référentiels figés** pour construire des
  **progressions annuelles** (chantier futur de la roadmap globale).
- **Vue de consultation de la trace** (un onglet « Référentiel figé »
  qui affiche en lecture le contenu de `trace.json` de façon humaine).
- **Atelier assemblage séquence-dans-niveau** (EN COURS dans userMemories)
  — bug `_cycle_du_niveau` qui résout C03 pour N10/N12.
- **Diagnostic perf tcolorbox** (piste D v0.15.2.5).

### Roadmap globale (rappel userMemories)
- v0.13 — CRUD cycles/niveaux/thèmes/séquences ; remplacer
  `_NOM_COURT_NIVEAU` par lecture DB ; import C03 complet
- v0.14 — Admin refonte + nettoyage (supprimer `exercice_objectifs`,
  `edition_progression.py`, JS `ATL_OBJ_CAT`, route `/api/objectifs`,
  table `objectifs`)
- v0.15 — Progressions annuelles adaptées aux nouvelles refs ; reprise
  suivi classes
- v0.15+ — Concepts « mise en route » et « automatisme »

### Dette technique active
- **livret_plans et evaluation péremption « hors atomes »** (TODO
  v0.15.2.6) — à câbler quand l'atelier assemblage exposera ses mtimes
- **3-full cleanup série R** — supprimer `objectif_exos.origin_*`,
  propager SELECT/INSERT
- **Bug `_cycle_du_niveau`** (v0.12.1.1) — résout C03 pour N10/N12
- **`atelChargerObjectifs` 5 erreurs console** au démarrage
- **Workdirs orphelins** dans `tempfile.gettempdir()/seqenseigne_workdir/`
- **Q2/Q3 chantier v1** (post v0.14.7) — `services/v2_lecture` /
  `v2_edition`, routes `/api/v2/*`, classes `V2*Erreur`
