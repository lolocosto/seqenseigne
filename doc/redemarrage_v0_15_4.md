# Redémarrage v0.15.4 — Doc refondue + JSON dépliable + nettoyage UI

## Plan livré (3 chantiers)

### 1. UI : JSON complètement dépliable dans le bloc « Données verrouillées »

Avant (v0.15.3), seuls les nœuds de premier niveau étaient affichés (séquences, objectifs avec compteurs « 9 exo, 1 fiche »). Désormais tout est navigable :

- Référentiel : métadonnées complètes (id, niveau, version, dates, description, état)
- Thèmes : code + nom + couleur
- Séquences :
  - Prérequis listés
  - Parties dépliables :
    - **Cartes d'automatisme** (numéros, types, titres)
    - **Révisions** : niveau/séquence/numéro/série + titre si dispo
    - **Approche** : idem
    - **Objectifs** :
      - Critères F/A/E (« à consolider », « satisfaisant », « très bon »)
      - Nombre de séances, marqueur fin-de-cycle
      - **Méthodes** : numéro + titre
      - **Notions** : numéro + titre
      - **Exercices** : groupés par série (fondamental, avancé, exploration) avec leurs numéros et titres
      - **Fiches de résumé** (sur l'objectif Cours uniquement) : numéros + titres
- Évaluations
- Documents : type + provenance + cibles avec noms de fichiers

Implémentation : `static/atelier_referentiel.js`, fonctions `atelRefRenduTraceComplete` / `atelRefRenduSequence` / `atelRefRenduPartie` / `atelRefRenduObjectif`. Tout en `<details>/<summary>` natifs HTML, pas de framework.

### 2. UI : suppression du bloc « Éléments à inclure » de l'atelier d'assemblage

Comme tu l'as signalé, ce bloc faisait double emploi avec la configuration migrée dans le référentiel quelques versions plus tôt.

Supprimé :
- `_rendreBlocElementsAInclure()` (~ 70 lignes) dans `static/atelier_seqniv_assemblage.js`
- `window.seqnivAsmMajElementsAInclure()` (~ 40 lignes)
- 3 sites d'appel à cette dernière
- L'ensemble des classes CSS `.elem-incl-*` (~ 65 lignes) dans `static/app.css`
- Commentaires obsolètes mis à jour dans le HTML et le JS

Pas d'impact backend : les payloads envoyés à `services.livret_sequence.normaliser_options` prennent leurs valeurs par défaut (`getCheck()` retourne `true` quand l'input n'existe pas → tout inclus).

### 3. Doc : refonte complète + archivage

#### Refonte des 6 canoniques

| Fichier | Avant | Après |
|---|---|---|
| `README.md` | 343 l. (v0.13.7.4) | 104 l. (v0.15.4) — vision, archi, stack, état, démarrage, roadmap |
| `INDEX.md` | 182 l. (v0.13.7.4) | 62 l. (v0.15.4) — carte de la doc avec archives |
| `CONVENTIONS.md` | 494 l. (v0.13.5.1.6) | 126 l. (v0.15.4) — livraison, style, tests, stockage |
| `GOTCHAS.md` | 321 l. (v0.13.5.1.6) | 238 l. (v0.15.4) — pièges classés par domaine |
| `DETTE_TECHNIQUE.md` | 148 l. | 126 l. (v0.15.4) — bugs, chantiers, améliorations |
| `NETTOYAGE.md` | 29 l. | 46 l. (v0.15.4) — code mort, aliases rétrocompat |

Toutes mises à jour pour refléter l'état v0.15.3 du modèle d'état, les nouveaux outils CLI, et les conventions de livraison établies au fil des sessions.

#### Script d'archivage `outils/archiver_docs.py`

Catégorise les ~ 215 notes obsolètes et les déplace dans `doc/archives/<categorie>/` :

| Sous-dossier | Contenu | Estimation |
|---|---|---|
| `redemarrages_anciens/` | Notes de livraison v0.5 → v0.14 | 115 |
| `readme_anciens/` | README de chantiers R1-R4 + versions v0.5-0.11 | 43 |
| `patches/` | Notes de patch d'anciennes versions | 27 |
| `chantiers/` | Notes du chantier 14 (closed) | 5 |
| `notes/` | Notes ponctuelles (fix cache USB, recapcours, …) | 4 |
| `archives_cdc_doc/` | Anciennes versions du CDC / doc technique / use cases | 7 |
| `scoping/` | Notes de cadrage de chantiers livrés | 1 |
| `pilotage/` | Finalisations, reprises de session | 2 |

Mode `--dry-run` pour preview, idempotent (relance OK), génère un `INDEX_ARCHIVES.md` récap.

**Important : à exécuter chez toi pour appliquer l'archivage :**

```powershell
..\outils\python\python.exe outils\archiver_docs.py --doc-dir .\doc --dry-run    # preview
..\outils\python\python.exe outils\archiver_docs.py --doc-dir .\doc              # exécution
```

Le ZIP de livraison ne pré-archive PAS pour toi (sinon il pèserait des MB inutilement) — c'est l'outil qui le fait chez toi.

## Tests

**v0.15.4 : 3671 passed, 7 skipped, 0 failed** (+15 par rapport à v0.15.3).

### Nouveau fichier

`tests/test_v0_15_4_archiver_docs.py` (15 tests) :
- 12 tests de catégorisation par pattern de nom
- 3 tests bout-en-bout (dry-run, archivage réel, idempotence, index généré)

## Fichiers livrés

### Code (`seqenseigne_v0_15_4.zip`)

| Fichier | Type |
|---|---|
| `appli/static/atelier_referentiel.js` | Modifié (JSON dépliable complet) |
| `appli/static/atelier_seqniv_assemblage.js` | Modifié (suppression bloc) |
| `appli/static/app.css` | Modifié (suppression CSS orphelin) |
| `appli/templates/index.html` | Modifié (commentaires obsolètes) |
| `appli/outils/archiver_docs.py` | Nouveau (script d'archivage) |
| `appli/tests/test_v0_15_4_archiver_docs.py` | Nouveau (tests script) |
| `appli/doc/INDEX.md` | Refondu |
| `appli/doc/README.md` | Refondu |
| `appli/doc/CONVENTIONS.md` | Refondu |
| `appli/doc/GOTCHAS.md` | Refondu |
| `appli/doc/DETTE_TECHNIQUE.md` | Refondu |
| `appli/doc/NETTOYAGE.md` | Refondu |
| `appli/doc/redemarrage_v0_15_4.md` | Nouveau (ce document) |

## Vérification

```powershell
.\outils\python\python.exe outils\verifier_md5.py --racine . --manifest MANIFEST.md5
.\outils\python\python.exe -m pytest tests/ -q
# Attendu : 3671 passed, X skipped, 0 failed
```

Ensuite, lance l'archivage des docs :

```powershell
..\outils\python\python.exe outils\archiver_docs.py --doc-dir .\doc --dry-run
..\outils\python\python.exe outils\archiver_docs.py --doc-dir .\doc
```

Et tu verras `doc/` se réduire de ~ 230 fichiers à 6 + ~ 20 notes v0.15. Le reste sera dans `doc/archives/`.

## Prochaines pistes

(Rappel)

1. **Compléter l'import N11_v2025** avec les 13 PDFs restants (avec la regex corrigée v0.15.2.12.2).
2. **Parser le `.tex` plan de travail** pour enrichir la trace (objectif → notions via codes C01/C02).
3. **Atelier suivi de classe** : câbler `verrouille → utilise`.
4. **Atelier assemblage séquence-dans-niveau** : bug `_cycle_du_niveau`.
5. **CRUD cycle/niveaux/thèmes/séquences**.
6. **Pour la 6ème (N06)** : structure des docs des collègues.
