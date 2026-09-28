# seqenseigne — Patch R4b : corrections du peuplement v2

Corrige trois bugs du scanner `R4b` initial détectés au déploiement :

1. **Perte systématique d'objectifs** : quand un plan de travail existait
   pour une séquence et ne listait pas tous les objectifs, les objectifs
   non mentionnés étaient perdus (155 au lieu de 245 chez toi).

2. **Doublons sur `objectif_exos`** : le peuplement était fait deux fois
   (depuis `livret_exercices` + depuis le plan), d'où 1567 exos au lieu
   de 731 attendus.

3. **Compteur incorrect** : `INSERT OR IGNORE` incrémentait le compteur
   même quand l'insertion était ignorée par contrainte d'unicité.

**Status** : 4 nouveaux tests de régression, **706 verts** au total
(702 + 4), 0 régression.

## Stratégie réparée

Une règle simple, unique :

> **La base est la source de vérité pour les objectifs et leurs exos.
> Le plan de travail sert uniquement à décider dans quelle partie va
> chaque objectif.**

Algorithme :
1. Charger **tous** les objectifs de `(niveau, seq_code)` depuis la
   table `objectifs`
2. Si un plan est disponible, construire un mapping
   `code_objectif → numéro_partie` (via les blocs du plan)
3. Les objectifs non listés dans le plan vont dans la partie 1 par défaut
4. Créer les parties nécessaires et y placer chaque objectif
5. Peupler `objectif_exos` **une seule fois** depuis `livret_exercices`

## Fichiers livrés

| Fichier | Changement |
|---|---|
| `appli/services/scanner_vers_v2.py` | Réécriture de `_peupler_une_sequence` ; suppression des fonctions `_peupler_partie_depuis_base`, `_peupler_partie_depuis_plan`, `_peupler_revisions`, `_ajouter_objectif_exo_si_absent` (obsolètes) ; ajout de `_ensure_partie` et `_ensure_partie_cached` ; fix de `_inserer_objectif_exo` (utilisation de `rowcount`). |
| `appli/tests/test_R4b_scanner_vers_v2.py` | Ajout d'une classe `TestRegressions` avec 4 tests qui auraient dû attraper les bugs. |

## Déploiement

### 1. Déposer les 2 fichiers

Remplace `appli/services/scanner_vers_v2.py` et
`appli/tests/test_R4b_scanner_vers_v2.py` par ceux du ZIP.

### 2. Relancer le peuplement (base existante)

```powershell
cd D:\Enseignement\seqenseigne\appli
..\outils\python\python.exe scripts\peuplement_13_v2_depuis_base.py `
    --plans-dir D:\Enseignement\seqenseigne\reference\sequences `
    --niveaux N10,N11,N12
```

Le script est idempotent, il purge + repeuple proprement.

**Chiffres attendus cette fois** :
- `sequences_par_niveau` : 42 (14 × 3) — inchangé
- `parties` : entre 42 et 60 selon les plans
- `objectifs_v2` : **245** (ou légèrement différent si ta base a évolué)
- `objectif_exos` : **~731** (ou légèrement différent)

Important : les totaux `objectifs_v2` et `objectif_exos` doivent être
**du même ordre** que tes anciens compteurs legacy :

```powershell
..\outils\python\python.exe -c "import sqlite3; c=sqlite3.connect('data/seqenseigne.db'); print('legacy objectifs:', c.execute('SELECT COUNT(*) FROM objectifs').fetchone()[0]); print('v2 objectifs:', c.execute('SELECT COUNT(*) FROM objectifs_v2').fetchone()[0]); print('legacy exos:', c.execute('SELECT COUNT(*) FROM livret_exercices').fetchone()[0]); print('v2 exos:', c.execute('SELECT COUNT(*) FROM objectif_exos').fetchone()[0])"
```

Ces deux paires doivent être égales.

### 3. Vérifier

```powershell
..\outils\python\python.exe -m pytest tests -q
# Attendu : 682 verts chez toi (tu étais à 678 + 4 nouveaux)
```

### 4. Re-vérifier avec la requête de diagnostic

```powershell
..\outils\python\python.exe -c "import sqlite3; c=sqlite3.connect('data/seqenseigne.db'); c.row_factory=sqlite3.Row; legacy=c.execute('SELECT niveau, sequence, COUNT(*) as n FROM objectifs GROUP BY niveau, sequence ORDER BY niveau, sequence').fetchall(); v2=c.execute('SELECT sn.niveau, sn.sequence_code, COUNT(ov.id) as n FROM sequences_par_niveau sn LEFT JOIN sequence_parties sp ON sp.sequence_par_niveau_id=sn.id LEFT JOIN objectifs_v2 ov ON ov.partie_id=sp.id GROUP BY sn.niveau, sn.sequence_code').fetchall(); m={(v[0],v[1]):v[2] for v in v2}; discrepances=[(r[0],r[1],r[2],m.get((r[0],r[1]),0)) for r in legacy if m.get((r[0],r[1]),0) != r[2]]; print('OK : tout correspond' if not discrepances else f'DISCREPANCES: {discrepances}')"
```

Sortie attendue : `OK : tout correspond`
