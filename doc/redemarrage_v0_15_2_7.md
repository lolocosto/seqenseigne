# Redémarrage v0.15.2.7 — Bugfix compteur de pages (workdir persistant)

## Contexte

v0.15.2.6 déployée et validée pour la péremption ciblée ✅. **MAIS le
compteur de pages ne fonctionnait pas** : Laurent rapporte que le
numéro ne change pas pendant la compilation, et donne l'impression
d'afficher *« le nombre total de pages du doc »*.

## Diagnostic

`v0.15.2.6` lisait le log à l'emplacement
`_artefacts/<doc_id>/<cible_key>.log`. Or pdflatex compile dans un
`tempfile.TemporaryDirectory()` éphémère ; l'artefact log n'est créé
qu'**après** la fin de la compilation par l'orchestrateur (copie depuis
la string `res.log_complet`).

Conséquences observées :

| Cas | Lecture du log | Affichage UI |
|---|---|---|
| Premier compile de la cible | Artefact absent | `page_courante = None` → rien |
| Compiles suivants | Artefact = log du compile **précédent** | Figé sur la dernière page de la compilation précédente |

C'est exactement ce que Laurent décrivait : « le nombre total de pages
du doc qui est affiché » correspond en fait à la dernière page de la
compilation précédente.

## Fix : workdir persistant pour pdflatex

Approche : remplacer le `tempfile.TemporaryDirectory()` éphémère par un
**workdir au chemin connu**, persistant entre la fin de pdflatex et la
lecture par `lire_statut()`. Le `atome.log` y est rempli progressivement
par pdflatex — lisible en direct par le compteur de pages UI.

### Choix de conception

1. **Workdir sous `tempfile.gettempdir()`** (typiquement `/tmp` ou
   `C:\Users\...\Temp`), pas sous `dossier_artefacts`.
   Justification : Laurent fait tourner l'app depuis une clé USB ;
   `dossier_artefacts` est sur l'USB (lent). `tempfile.gettempdir()`
   pointe sur le disque interne (50-100× plus rapide). On évite la
   pénalité USB pour les I/O intensives de pdflatex.
2. **Discrimination par `doc_id` + `cible_key`** : pas de collision
   entre documents ni entre cibles d'un même document.
3. **Nettoyage en début d'appel** (`shutil.rmtree` + `mkdir`) : pas
   d'accumulation de `.aux`/`Corriges/` entre runs.
4. **Optionnel** : si appelé sans `workdir`, comportement historique
   (`TemporaryDirectory` éphémère). Préserve tous les appels existants
   (tests, scripts) sans modification.

### Architecture

```
referentiel_documents_compilation.py
  └─ worker loop
       calcule chemin_log_courant = orch.chemin_log_courant_cible(...)
       _maj_statut(..., chemin_log_courant=str(chemin_log_courant))
       │
       └─ orchestrateur_compilation.compiler(...)
            calcule workdir = orch.chemin_workdir_cible(...)
            compiler_atome(..., workdir=workdir)
            │
            └─ compilateur_pdf.compiler_atome(..., workdir=Path|None)
                 with _ouvrir_workdir(workdir) as tmpdir:
                     # tmpdir = workdir si fourni, sinon TempDir éphémère
                     # pdflatex y écrit atome.log progressivement
                     subprocess.run(['pdflatex', 'atome.tex'], cwd=tmpdir)

[en parallèle, sur poll UI]
referentiel_documents_compilation.lire_statut(doc_id)
  └─ lit s['chemin_log_courant']
       progression_courante(Path(s['chemin_log_courant']))
       ajoute s['page_courante'] = N au statut retourné
```

### Nouvelles helpers dans orchestrateur_compilation

| Fonction | Rôle |
|---|---|
| `chemin_workdir_cible(dossier_artefacts, cible_key)` | Workdir persistant pour pdflatex (sous tempdir) |
| `chemin_log_courant_cible(dossier_artefacts, cible_key)` | `workdir/atome.log` (LIVE log) |

### Nouvelle helper dans compilateur_pdf

| Fonction | Rôle |
|---|---|
| `_ouvrir_workdir(workdir)` | Context manager : si `workdir=None` → tempdir éphémère ; sinon nettoie+crée+yield+persiste |

### Statut : nouveau champ `chemin_log_courant`

Remplace `dossier_artefacts` + `cible_en_cours_key` de v0.15.2.6 (qui
pointaient implicitement sur l'artefact). Maintenant un seul champ
`chemin_log_courant` portant le chemin complet du LIVE log. Plus
clair, moins de calcul côté `lire_statut`.

## Tests

**v0.15.2.7 : 3546 passed, 6 skipped, 0 failed** (+8 par rapport à v0.15.2.6).

### Nouveau fichier `tests/test_v0_15_2_7_log_live_workdir.py`

8 tests nommés protègent le contrat workdir et le bugfix :

| Test | Protège |
|---|---|
| `test_chemin_workdir_cible_est_sous_tempdir` | Choix d'emplacement (perf USB) |
| `test_chemin_workdir_cible_discrimine_par_doc_et_cible` | Pas de collision |
| `test_chemin_log_courant_pointe_sur_atome_log` | Nom de fichier conforme à pdflatex |
| `test_ouvrir_workdir_none_est_ephemere` | Rétrocompat |
| `test_ouvrir_workdir_explicit_persiste` | Persistance post-yield |
| `test_ouvrir_workdir_nettoie_residus` | Pas de pollution `.aux`/`Corriges/` |
| `test_ouvrir_workdir_chemin_inexistant_est_cree` | Robustesse |
| `test_compiler_atome_avec_workdir_ecrit_log_live` | Smoke test bout-en-bout (skippé si pdflatex absent) |

### `tests/test_v0_15_2_6_statut_page_courante.py` adapté

Les 3 tests qui passaient `cible_en_cours_key`+`dossier_artefacts` au
statut sont réécrits pour passer directement `chemin_log_courant`,
reflétant le contrat v0.15.2.7. Tous les autres tests v0.15.2.6
inchangés.

## Fichiers livrés

| Fichier | Type |
|---|---|
| `appli/services/compilateur_pdf.py` | Modifié (workdir context manager + paramètre) |
| `appli/services/orchestrateur_compilation.py` | Modifié (helpers + passage workdir) |
| `appli/services/referentiel_documents_compilation.py` | Modifié (worker + lire_statut + statut_initial) |
| `appli/tests/test_v0_15_2_6_statut_page_courante.py` | Modifié (3 tests adaptés au nouveau contrat) |
| `appli/tests/test_v0_15_2_7_log_live_workdir.py` | Nouveau |
| `appli/doc/redemarrage_v0_15_2_7.md` | Nouveau (ce document) |

Pas de `.dtx`/`.sty`, pas de JS, pas de changement BDD : tout est
backend Python.

## Note sur la propreté des workdirs

Chaque appel à `compiler_atome(workdir=...)` nettoie et recrée son
workdir. Donc **pas d'accumulation inter-runs** pour une même cible.

En revanche, des workdirs orphelins peuvent rester sous
`tempfile.gettempdir()/seqenseigne_workdir/` après suppression d'un
document ou d'une cible. Non bloquant :
- L'OS purge périodiquement `tempfile.gettempdir()` (sur tous les OS).
- Le volume est faible (~quelques MB par cible).
- Si ça devient un problème, on pourra ajouter une purge déclenchable
  depuis l'admin (à la manière de `purger_fiches.py`).

## Vérification

```powershell
.\outils\python\python.exe outils\verifier_md5.py --racine . --manifest MANIFEST.md5
.\outils\python\python.exe -m pytest -q
# Attendu : 3546 passed, 6 skipped, 0 failed
```

## Effet attendu côté UI

Pendant la compilation d'une cible (~25-30s) :

```
5/14 — Compilation : Planches N10/S05 (page 1)
5/14 — Compilation : Planches N10/S05 (page 3)
5/14 — Compilation : Planches N10/S05 (page 7)
5/14 — Compilation : Planches N10/S05 (page 12)
5/14 — Compilation : Planches N10/S05 (page 17)
...
```

Avec polling à 700ms, le numéro change ~à chaque seconde. Plus de
figeage sur un nombre total : l'utilisateur voit que ça avance
réellement.

## Pistes pour la suite (rappel)

Du `redemarrage_prochaine_session.md`, encore à traiter :

- **Chantier 3 — Figeage du référentiel** (tables `referentiel_*` millésimées).
- **Atelier assemblage séquence-dans-niveau** (EN COURS dans userMemories) :
  reprise. Câblera naturellement l'assemblage dans la péremption
  (TODO documentés dans v0.15.2.6 pour `livret_plans` et `evaluation`).
- **Diagnostic perf tcolorbox** (piste D) : 25-30s pour ~270 tcolorbox
  est encore lent. Chiffrer le gain potentiel (lualatex ? tblr
  libraries inutiles ?) — chantier à découpler.
