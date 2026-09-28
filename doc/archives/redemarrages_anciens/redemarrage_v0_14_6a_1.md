# Redémarrage v0.14.6.a.1 — Hotfix Windows UTF-8

## Diagnostic

Sortie des tests v0.14.6.a chez Laurent (Windows 10/11, Python 3.13.5) :
14/19 tests en échec, tous avec le même symptôme :

```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'
  in position 70: character maps to <undefined>
```

`\u2192` est la flèche `→` utilisée dans les titres comme « v1 → v2 ».
Sur Windows, `sys.stdout` utilise par défaut `cp1252` (charmap) qui ne
contient pas les caractères Unicode au-delà du Latin-1 étendu :

- `─` (U+2500) caractères de cadre
- `→` (U+2192) flèche
- `✓` (U+2713) coche
- `✗` (U+2717) croix
- `⚠` (U+26A0) avertissement

Dès que `print()` rencontre un de ces caractères, exception
`UnicodeEncodeError` non capturée → exit code 1.

Pourquoi ça marchait chez moi (Linux) et pourquoi `audit_v1_v2.py`
v0.14.5 marchait en exécution directe chez Laurent :

- **Linux** : `sys.stdout.encoding` est `utf-8` par défaut → pas
  d'erreur, même avec les caractères les plus exotiques
- **Windows en exécution directe via PowerShell** : selon la version
  de Windows et la session PowerShell, l'encodage console peut être
  UTF-8 (PowerShell 7+ avec `chcp 65001`) ou cp1252 (Windows
  PowerShell 5.1 par défaut). Laurent a probablement eu de la chance
  avec audit_v1_v2 en exécution directe.
- **Subprocess pytest** : `subprocess.run(..., text=True)` ouvre les
  pipes avec l'encodage par défaut Windows (cp1252) **indépendamment**
  de l'encodage console du parent. C'est plus strict — d'où le crash
  systématique dans les tests.

## Correctif (3 niveaux)

### 1. Forcer UTF-8 dans stdout des scripts

Tout en haut de `scripts/migrer_v1_vers_v2.py` et
`scripts/audit_v1_v2.py`, juste après les imports :

```python
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
```

`reconfigure(encoding=...)` existe depuis Python 3.7 ; sur Linux/Mac
c'est sans effet (déjà UTF-8). Le `try/except` est un filet de
sécurité pour les flux non standards (PYTHONIOENCODING déjà forcé,
redirection vers fichier exotique, etc.). En cas d'échec on continue
silencieusement — pire des cas : les caractères apparaissent dégradés
mais le script s'exécute jusqu'au bout.

### 2. Forcer UTF-8 dans subprocess.run des tests

Dans les 6 appels à `subprocess.run(...)` des fichiers de tests
v0.14.5 (audit) et v0.14.6.a (migration), ajouter `encoding="utf-8"` :

```python
# Avant
subprocess.run(cmd, capture_output=True, text=True, timeout=30)

# Après
subprocess.run(cmd, capture_output=True, text=True,
               encoding="utf-8", timeout=30)
```

Le test décode alors le stdout enfant comme UTF-8 — cohérent avec ce
que le script écrit grâce au correctif 1.

### 3. Tests existants restent en place

Les 19 tests v0.14.6.a et les 21 tests v0.14.5 ne changent pas dans
leur sémantique ; seul `encoding="utf-8"` est ajouté aux subprocess.

## Validation

### Sur Linux (mon environnement)

```
python -m pytest tests/test_v0_14_5_audit_v1_v2.py \
                 tests/test_v0_14_6a_migration_v1_vers_v2.py -q
```

Résultat : **40 passed**.

Suite complète : **3536 passed, 5 skipped, 0 failed** (inchangé vs
v0.14.6.a sur Linux).

### Test Windows simulé

J'ai forcé `PYTHONIOENCODING=cp1252` au lancement du script pour
reproduire l'environnement Windows :

```
$ PYTHONIOENCODING=cp1252 python3 scripts/migrer_v1_vers_v2.py --help
usage: migrer_v1_vers_v2.py [-h] [--db DB] [--ecrire]

Migration v1 → v2 des objectifs (...)
Exit : 0
```

Et un dry-run :

```
$ PYTHONIOENCODING=cp1252 python3 scripts/migrer_v1_vers_v2.py --db test.db
──────────────────────────────────────────────────────────────────────
  Liaisons exercice→objectif à créer en v2 — 0
──────────────────────────────────────────────────────────────────────
  DRY-RUN — aucune écriture effectuée
Exit : 0
```

Les caractères `─`, `→` s'affichent correctement et le script termine
avec exit 0.

## Fichiers livrés

```
MODIFIÉS (correctifs UTF-8)
  appli/scripts/audit_v1_v2.py                       (+12 lignes au début)
  appli/scripts/migrer_v1_vers_v2.py                 (+12 lignes au début)
  appli/tests/test_v0_14_5_audit_v1_v2.py            (3 appels patchés)
  appli/tests/test_v0_14_6a_migration_v1_vers_v2.py  (3 appels patchés)

NOUVEAUX
  appli/doc/redemarrage_v0_14_6a_1.md                (ce document)
```

Pas de nouveau test : les 40 tests existants couvrent maintenant le
chemin UTF-8 sur toutes les plateformes (puisqu'ils utilisent
`encoding="utf-8"` côté subprocess et le `reconfigure()` côté script).

## À tester chez toi

### 1. Relancer les tests

```
cd appli
python -m pytest tests/test_v0_14_5_audit_v1_v2.py ^
                 tests/test_v0_14_6a_migration_v1_vers_v2.py -v
```

Attendu : **40 passed** (21 audit + 19 migration). Plus aucun
`UnicodeEncodeError`.

### 2. Relancer le dry-run sur ta vraie BDD

```
python -m scripts.migrer_v1_vers_v2
```

Cette fois la sortie complète doit s'afficher (avec les `─`, `→`,
`✓`, etc.). M'envoyer le rapport.

### 3. Si tout est cohérent → écriture

```
python -m scripts.migrer_v1_vers_v2 --ecrire
```

Cette fois aussi la sortie complète doit s'afficher. Vérifier qu'un
backup a été créé dans `data/backups/`.

### 4. Re-audit

```
python -m scripts.audit_v1_v2
```

Doit afficher « ✓ Aucun obstacle détecté ».

## Note de dette technique

J'aurais dû tester l'aspect Windows-compatibilité dès v0.14.5
(le script d'audit avait les mêmes caractères Unicode). Mea culpa.

Le `reconfigure(encoding="utf-8")` au début de tout script Python qui
imprime des caractères non-ASCII est désormais une **convention** à
appliquer systématiquement dans les futurs scripts seqenseigne.

Pareil pour le `encoding="utf-8"` dans `subprocess.run` quand on
décode du stdout d'un sous-process Python.
