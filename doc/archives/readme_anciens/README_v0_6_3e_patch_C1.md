# seqenseigne v0.6.3e — patch C1 « peuplement du référentiel complet en base »

Ce patch fait évoluer la structure de données SQLite pour que le
**référentiel complet** (objectifs, méthodes, notions, exercices,
livrets, liaisons) soit peuplé de manière relationnelle en base,
à partir des sources existantes (YAML, JSON, plans de travail LaTeX).

**État :** livré, 463 tests pytest verts (0 régression).

---

## 1. Contexte

Avant v0.6.3e, la base SQLite contenait :
- les **entités** (802 exercices, 166 notions, 156 méthodes, 42 livrets) migrées depuis les JSON historiques via le bouton *Admin → Base de données → Lancer la migration* ;
- mais **pas les liaisons relationnelles** (`exercice_objectifs`, `methode_notions`, `livret_exercices`, `livret_revisions` toutes vides).

Trois causes :
1. Le schéma SQL n'avait pas les métadonnées de traçabilité (niveau, séquence, num, fichier) sur les atomes.
2. `ecrire_exercices` dans le store lisait la mauvaise clé (`objectifs` au lieu de `objectifs_codes` fournie par le scanner).
3. La liaison méthode ↔ notion n'est pas dans les fichiers `Methode_*.tex` : elle est dans les `N1X_Plan_de_travail.tex` (un par niveau).

Ce patch corrige tout ça.

---

## 2. Ce qui est livré

### 2.1 Évolution du schéma SQL (`persistence/schema.sql`)

Colonnes ajoutées :

| Table | Nouvelles colonnes |
|---|---|
| `notions` | `niveau`, `sequence`, `num_connaissance`, `fichier` |
| `methodes` | `niveau`, `sequence`, `num_methode`, `num_objectif`, `fichier` |
| `exercices` | `niveau`, `sequence`, `num`, `serie_code`, `fichier` |
| `objectifs` | `niveau`, `sequence`, `nom`, `est_nouveau`, `obj_precedent_id` |

Nouvelle table :

- `livret_revisions` (exercices de révision hérités du niveau N-1 pour un livret)

7 index ajoutés sur les colonnes `(niveau, sequence, …)` et `fichier`.

### 2.2 Fix des méthodes d'écriture du store (`persistence/sqlite_store.py`)

4 méthodes `ecrire_*` et 1 nouvelle :

- **`ecrire_objectifs` (nouvelle)** — crée les objectifs comme atomes pédagogiques de premier ordre à partir de `referentiel_objectifs`. Stratégie UPSERT : préserve `methode_id`, `est_nouveau`, `obj_precedent_id` entre deux runs. Appelée avant les autres.
- **`ecrire_notions`** — insère les métadonnées `niveau`/`sequence`/`num_connaissance`/`fichier`.
- **`ecrire_methodes`** — insère les métadonnées, lie l'objectif créé via `(niveau, sequence, num_objectif)`. Compat legacy préservée pour les méthodes sans métadonnées.
- **`ecrire_exercices`** — insère les métadonnées, résout `objectifs_codes` en FK vers `objectifs.id` via `(niveau, sequence, code)`.
- **`ecrire_livrets_importes`** — peuple `livret_exercices` (en résolvant aussi `objectif_id` via `exercice_objectifs`) et `livret_revisions` (depuis `prerequis.exercices_revision`).

### 2.3 Parseur de plans de travail (`importers/scanner_plan_de_travail.py`)

Nouvelle fonction `parse_plan_de_travail_file()` qui lit un fichier `N1X_Plan_de_travail.tex` et en extrait la grammaire :

```latex
\seqSetCodeSequence{S01}
\seqBoiteTitrePlan[titre={\seqSequenceGetNom (1\iere{} partie)}]
\begin{boitePaleNoBreak}{\textbf{Révisions}}
    \begin{seqColItem}[...] \item Révision: 1,2,3,4,5 \end{seqColItem}
\end{boitePaleNoBreak}
\seqPlanObjectif{02}
    {   \og \seqConnaissanceGetNom{01} \fg{}}
    {2,3,4}{1}{2,3,4}
```

→ dict Python avec `blocs[].objectifs[].notions_codes` (`["01"]`).

### 2.4 Scripts (`scripts/peuplement_*`)

| Script | Rôle |
|---|---|
| `peuplement_01_migrer_schema.py` | Ajoute colonnes/tables à une base **pré-v0.6.3e** (idempotent). Ne fait rien sur une base nouvelle (schéma déjà complet). |
| `peuplement_02_repeupler.py` | Relance `migrer_depuis_json` avec les ecrire\_\* corrigés. Peuple toutes les liaisons relationnelles. |
| `peuplement_03_deduire_liaisons.py` | Produit `config/liaisons_objectifs.yaml` avec les liaisons N→N-1 triviales pré-remplies (même code, même séquence entre niveaux) + les autres marquées `a_completer: true`. |
| `peuplement_04_appliquer_liaisons.py` | Applique les décisions du YAML (`est_nouveau` / `precedent`) en base. |
| `peuplement_05_plans_de_travail.py` | Lit les `N1X_Plan_de_travail.tex` et peuple `methode_notions`. |

### 2.5 Tests pytest (`tests/test_peuplement_*`)

62 tests couvrant :
- schéma (11) : migration initiale, idempotence, cas limites
- repeuplement (18) : chaque ecrire\_\* + intégration `migrer_depuis_json`
- plans de travail (21) : parseur + application en base
- liaisons N→N-1 (12) : déduction + application + chaîne complète

---

## 3. Procédure d'installation

Cette section décrit comment appliquer le patch sur votre instance
existante.

### 3.1 Prérequis

- Base `appli/data/seqenseigne.db` présente (peut être vide ou déjà migrée)
- Fichiers JSON historiques dans `appli/data/` (notions, methodes, exercices, livrets_importes)
- Fichiers `N10_Plan_de_travail.tex`, `N11_Plan_de_travail.tex`, `N12_Plan_de_travail.tex` accessibles
- Python avec PyYAML installé

### 3.2 Déploiement des fichiers

Copier les fichiers du patch dans l'arborescence de l'appli :

```
appli/persistence/schema.sql           (remplacé)
appli/persistence/sqlite_store.py      (remplacé)
appli/persistence/ids.py               (remplacé — ajoute nouveau_id_objectif)
appli/importers/scanner_plan_de_travail.py  (nouveau)
appli/scripts/peuplement_01_migrer_schema.py        (nouveau)
appli/scripts/peuplement_02_repeupler.py            (nouveau)
appli/scripts/peuplement_03_deduire_liaisons.py     (nouveau)
appli/scripts/peuplement_04_appliquer_liaisons.py   (nouveau)
appli/scripts/peuplement_05_plans_de_travail.py     (nouveau)
appli/tests/test_peuplement_schema.py               (nouveau)
appli/tests/test_peuplement_repeupler.py            (nouveau)
appli/tests/test_peuplement_plans_de_travail.py     (nouveau)
appli/tests/test_peuplement_liaisons.py             (nouveau)
```

### 3.3 Exécution des scripts dans l'ordre

```powershell
cd appli

# Étape 1 — Migration de schéma (ajoute colonnes/tables manquantes si besoin)
..\outils\python\python.exe scripts\peuplement_01_migrer_schema.py

# Étape 2 — Repeuplement des tables relationnelles depuis les JSON
..\outils\python\python.exe scripts\peuplement_02_repeupler.py

# Étape 3 — Peuplement des liaisons methode_notions depuis les plans de travail
# (ajuster le chemin si les plans ne sont pas dans ..\reference)
..\outils\python\python.exe scripts\peuplement_05_plans_de_travail.py ^
    --chemin ..\reference

# Étape 4 — Déduire les liaisons triviales obj N → obj N-1
..\outils\python\python.exe scripts\peuplement_03_deduire_liaisons.py

# Étape 5 — Éditer appli\config\liaisons_objectifs.yaml à la main
# Pour chaque entrée avec `a_completer: true`, choisir :
#   - soit remplacer par `precedent: {niveau: N10, sequence: S03, code: 12}`
#     si l'objectif a un équivalent N-1 non trivial
#   - soit remplacer par `est_nouveau: true`
#     si l'objectif est nouveau à ce niveau

# Étape 6 — Appliquer les liaisons
..\outils\python\python.exe scripts\peuplement_04_appliquer_liaisons.py
```

### 3.4 Vérification

```powershell
..\outils\python\python.exe -m pytest tests -q
# Attendu : 463 tests verts
```

---

## 4. Résultats attendus sur la base actuelle

Avant le patch (base au 20 avril 2026) :
- 802 exercices, 166 notions, 156 méthodes, 42 livrets ✅
- 0 exercice_objectifs ❌
- 0 methode_notions ❌
- 0 livret_exercices ❌
- 0 livret_revisions (table inexistante) ❌

Après le patch (mesures effectuées sur la copie de la base Laurent) :
- 245 **objectifs** atomiques créés ✅ (couvrant N10, N11, N12, toutes séquences)
- 731 liaisons `exercice_objectifs` ✅
- 729 lignes `livret_exercices` ✅
- 207 lignes `livret_revisions` ✅
- `methode_notions` peuplé après exécution du script 05

---

## 5. Limitations et suites

### 5.1 Ce qui n'est pas automatisé

- Les **liaisons obj N → obj N-1 non triviales** (changement de code
  entre niveaux, objectif provenant d'une autre séquence) sont signalées
  `a_completer: true` dans le YAML. L'enseignant doit les renseigner à
  la main. Une fois faites, `peuplement_04` les applique.
- Les **critères de maîtrise F/A/E** sur objectifs proviennent soit
  du référentiel (par défaut), soit des méthodes (si la méthode en
  fournit). L'auteur peut retoucher les critères directement dans le
  référentiel si besoin.

### 5.2 Suites prévues

- **Reprise du chantier « édition de progression »** (v0.6.3d, en pause)
  qui s'appuiera sur les nouvelles liaisons pour afficher automatiquement
  les exercices de révision dans le détail d'un créneau.
- **Chantier édition de contenu** : faire évoluer les ateliers Notion /
  Méthode / Exercice pour qu'ils écrivent directement dans la base
  relationnelle (aujourd'hui ils écrivent dans les JSON via `json_store`).
- **Migration des fichiers `.tex` de méthode** pour qu'ils référencent
  explicitement leurs notions via une commande `\seqUseConnaissance{N}`
  (plutôt que de dépendre des plans de travail comme source secondaire).

---

## 6. Rappel des conventions techniques

### 6.1 Numérotation des objectifs et rang

Les codes d'objectif encodent le **rang** dans la séquence :

- `01` à `09` → rang 1
- `11` à `19` → rang 2
- `21` à `29` → rang 3
- etc.

Déduit en Python par `rang = int(code) // 10 + 1 if int(code) >= 10 else 1`.
Pas stocké en base : source de vérité unique (le `code`).

### 6.2 Règle « 1 méthode = 1 objectif »

Stricte. L'objectif est créé **en premier** à partir du référentiel,
puis la méthode se lie via `(niveau, sequence, num_objectif)`. Si
un objectif n'a pas de méthode associée (cas typique des objectifs
« 01 : Connaître le cours »), `objectifs.methode_id` est `NULL`.

### 6.3 Identifiants préfixés

Nouveaux préfixes ajoutés dans `persistence/ids.py` :
- `ob_` pour les objectifs (`nouveau_id_objectif`)

Préfixes existants préservés : `cl_`, `el_`, `pg_`, `cr_`, `rf_`, `no_`, `me_`, `ex_`, `lv_`, `im_`, `et_`.

---

*v0.6.3e — patch C1, livré le 20 avril 2026.*
*Tests : 463 verts (401 existants + 62 nouveaux).*
