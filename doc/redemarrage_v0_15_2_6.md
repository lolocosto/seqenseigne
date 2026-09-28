# Redémarrage v0.15.2.6 — Compteur de pages + péremption ciblée

Deux chantiers bundlés dans cette version, comme demandé par Laurent :
1. **Compteur de pages pdflatex** (option C de la session v0.15.2.5) —
   signal de vie en temps quasi-réel pendant la compilation d'une cible.
2. **Péremption ciblée par type de document** — fini les documents
   marqués `perime` alors que rien de pertinent n'a changé.

## Contexte de départ

v0.15.2.5 deployée et validée par Laurent : compilation des planches
N10 fonctionne (14 cibles, ~25-30s chacune). Pas de blocage. Mais
signal de vie trop espacé : 25-30s entre deux ticks de la barre, ça
paraît figé.

## Chantier 1 — Compteur de pages

### Principe

pdflatex émet `[N]` dans son log au moment du shipout de la page N.
On parse la **dernière occurrence** et on l'expose via le statut de
compilation. L'UI poll à 700ms : l'utilisateur voit le numéro de page
changer ~à chaque seconde pendant la compilation d'une cible.

### Choix de conception

- **Parser ultra-léger** (`services/log_pdflatex_parser.py`) :
  `re.findall(rb'\[(\d+)\]', data)`, dernier match, point. Faux positifs
  sans impact car le numéro change vers la vraie page suivante dès
  qu'elle est shippée.
- **Lecture en bytes** : robuste aux encodages incohérents qu'on
  rencontre dans les logs MiKTeX (Windows-1252 + UTF-8 selon les paquets).
- **Pas de tail incrémental** : on relit le fichier en entier à chaque
  appel. Coût négligeable (log < 1 Mo, polling 700ms).
- **Lazy** : aucun thread, aucun polling backend. Le parsing se fait
  seulement quand l'UI appelle `/statut`, dans `lire_statut()`. Aucun
  travail en arrière-plan.
- **3-pass pdflatex** : MiKTeX écrase le `.log` à chaque passe → le
  dernier `[N]` est toujours la page de la passe en cours. Exactement
  ce qu'on veut afficher.

### Câblage statut → UI

Le worker stocke `cible_en_cours_key` et `dossier_artefacts` dans le
statut à chaque démarrage de cible. `lire_statut(doc_id)` enrichit le
dict renvoyé avec `page_courante` en lisant le `.log` correspondant
(s'il existe).

Le statut a maintenant 3 nouveaux champs (initialisés à `None`) :

| Champ | Type | Sens |
|---|---|---|
| `cible_en_cours_key` | str | clé filesystem de la cible (ex. `N10_S07`) |
| `dossier_artefacts` | str | dossier où chercher le `.log` |
| `page_courante` | int \| None | page produite la plus récente (None si pas encore de marqueur) |

### Côté UI

`static/atelier_referentiel.js` — fonction `_atlRefMajProgress` : ajoute
un suffixe ` (page N)` au texte de progression quand `page_courante > 0`.
Aucun nouveau composant, juste un suffixe au libellé d'étape.

Exemples de texte produit :
- Avant : `7/14 — Compilation : Planches N10/S07`
- Après : `7/14 — Compilation : Planches N10/S07 (page 28)`

## Chantier 2 — Péremption ciblée

### Avant / après

| Cas | Avant v0.15.2.6 | Après v0.15.2.6 |
|---|---|---|
| Modifier une notion → livret de cartes | `perime` ❌ | `ok` ✅ |
| Modifier une carte → livret de séquence | `perime` ❌ | `ok` ✅ |
| Modifier un exercice → évaluation | `perime` (correct) | `perime` ✅ |
| Modifier un exo → livret_plans | `perime` (déjà incorrect) | `ok` ✅ |

### Mapping `type_document → tables d'atomes` (décisions Laurent)

| Type | Tables pertinentes |
|---|---|
| `livret_sequence` | notions, methodes, exercices |
| `livret_exercices` | exercices |
| `livret_cours` | notions, methodes |
| `livret_fiches` | fiches_resume |
| `livret_plans` | **aucune** |
| `livret_corriges` | exercices |
| `evaluation` | exercices |
| `livret_cartes_recap` | cartes_automatisme |
| `livret_cartes_planches` | cartes_automatisme |

Mapping dans `services/peremption_atomes.py` (dict en dur, décision
architecturale). Un test nommé exhaustif (`test_mapping_couvre_tous_
les_types_document`) garantit qu'AUCUN type de `TYPES_DOCUMENT` n'est
absent du mapping : si quelqu'un ajoute un nouveau type sans le mapper,
les tests échouent.

### Granularité : par document (pas par cible)

Le `compile_date` est stocké par document, pas par cible. Conséquence
acceptée : si une carte de S03 change après compile, **tout** le document
`livret_cartes_planches` passe à `perime`, même si seule la cible
N10/S03 nécessite re-compile. Pour aller plus fin, il faudrait
introduire une table `referentiel_documents_cibles` avec un
`compile_date` par cible — non fait dans ce delta.

### Limites assumées (TODO documenté)

Deux types ont des dépendances **hors atomes** que cette version ne
capture pas encore :

- `livret_plans` dépend de l'assemblage de séquence (atelier en cours,
  chantier 2 de la roadmap globale).
- `evaluation` dépend de l'assemblage d'évaluation (quels exercices
  composent l'éval).

Pour cette version, ces dépendances sont **hors scope de la péremption
ciblée par atomes**. Elles seront naturellement câblées quand les
ateliers d'assemblage exposeront leurs propres mtimes (chantier suivant
de la roadmap).

### Helper deprecated

`_max_mtime_atomes_du_niveau` (dans
`referentiel_documents_compilation.py`) est conservé pour rétrocompat
des scripts éventuels, marqué `.. deprecated::`. N'est plus appelé par
`etat_effectif_document` qui utilise maintenant
`max_mtime_atomes_pertinents`.

## Tests

**v0.15.2.6 : 3538 passed, 6 skipped, 0 failed** (+33 par rapport à v0.15.2.5).

Nouveaux fichiers de tests nommés :

| Fichier | Nb | Couverture |
|---|---|---|
| `test_v0_15_2_6_log_pdflatex_parser.py` | 10 | Parser (absent, vide, multi-pages, bytes invalides, 3-pass, dossier au lieu de fichier…) |
| `test_v0_15_2_6_peremption_atomes.py` | 15 | Mapping exhaustif + verrouillage des choix + max_mtime + intégration `etat_effectif_document` |
| `test_v0_15_2_6_statut_page_courante.py` | 8 | `lire_statut` enrichissement, copie défensive, évolution au fil de la compile, changement de cible |

## Fichiers livrés

| Fichier | Type |
|---|---|
| `appli/services/log_pdflatex_parser.py` | Nouveau |
| `appli/services/peremption_atomes.py` | Nouveau |
| `appli/services/referentiel_documents_compilation.py` | Modifié |
| `appli/static/atelier_referentiel.js` | Modifié |
| `appli/tests/test_v0_15_2_6_log_pdflatex_parser.py` | Nouveau |
| `appli/tests/test_v0_15_2_6_peremption_atomes.py` | Nouveau |
| `appli/tests/test_v0_15_2_6_statut_page_courante.py` | Nouveau |
| `appli/doc/redemarrage_v0_15_2_6.md` | Nouveau |

Pas de `.dtx`/`.sty` : aucune nouvelle macro paquet.

## Vérification du delta

```powershell
.\outils\python\python.exe outils\verifier_md5.py --racine . --manifest MANIFEST.md5
.\outils\python\python.exe -m pytest -q
# Attendu : 3538 passed, 6 skipped, 0 failed
```

## Effet attendu côté UI

**Pendant la compilation des planches N10** (14 cibles, ~25-30s chacune,
soit ~6 minutes au total) :

- Barre de progression : 14 ticks (un par séquence terminée).
- Texte courant : `5/14 — Compilation : Planches N10/S05 (page 17)`.
- Le numéro de page change toutes les ~1 s grâce au polling 700 ms.
- L'utilisateur a un signal de vie continu : on ne se demande plus si
  l'app est plantée.

**Pour la liste des documents périmés** :

- Les livrets de cartes ne sont plus marqués `perime` quand on touche
  une notion ou un exercice.
- Inversement, les livrets de cours/séquence/exercices ne sont plus
  marqués `perime` quand on modifie une carte d'automatisme.
- `livret_plans` ne passe jamais à `perime` par les atomes (statut quo
  jusqu'au câblage assemblage).

## Pistes pour les sessions suivantes (rappel)

Du `redemarrage_prochaine_session.md`, encore à faire :

- **Chantier 3 — Figeage du référentiel** : copier l'état courant des
  données de référence dans des tables `referentiel_*` millésimées.
- **Atelier assemblage séquence-dans-niveau** (EN COURS dans userMemories) :
  reprendre. Câblera naturellement l'assemblage dans la péremption
  (TODO documentés ci-dessus).
- **Diagnostic perf tcolorbox** (piste D) : pourquoi 25-30s pour
  ~270 tcolorbox ? Si on peut diviser par 2-3, ça change tout. Chantier
  propre à découpler.
