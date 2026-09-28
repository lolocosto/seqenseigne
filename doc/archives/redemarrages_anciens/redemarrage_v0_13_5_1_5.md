# Redémarrage v0.13.5.1.5 — Hygiène de livraison

Date : 10 mai 2026
Périmètre : 1 fix de bug + 1 nouvel outil

---

## Contexte

Faisant suite à la session de diagnostic du 10 mai (2 fichiers
`latex_rendu_atome.*` tronqués chez Laurent depuis une livraison
antérieure, qui faisaient échouer 11 tests pendant la discussion 25),
on règle deux dettes :

1. **Bug d'encodage cp1252 sur `scripts/migrer_methodes_objectifs.py`**
   (20 tests rouges sur Windows depuis v0.12.4, classé v0.14 dans la
   roadmap mais traité dès maintenant)
2. **Industrialisation du contrôle d'intégrité** par MD5 (priorité
   haute issue de l'analyse roadmap section 6)

---

## 1. Fix `scripts/migrer_methodes_objectifs.py`

### Problème

Sur Windows, Python hérite par défaut de la locale système (cp1252 sur
un Windows français standard). Quand le script est exécuté via
`subprocess.run` avec `capture_output=True` (cas des tests pytest qui
font `_executer_script(...)`), `stdout` et `stderr` sont alors en
cp1252 et le moindre caractère Unicode dans un `print()` (par exemple
la flèche `→` utilisée dans les résumés) plante avec
`UnicodeEncodeError`.

Symptôme : 20 tests rouges dans `tests/test_migrer_methodes_objectifs.py`,
tous avec la même cause :

```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'
```

### Fix

Ajout en tête de script (juste après les imports) :

```python
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
```

13 lignes de patch (commentaire d'explication inclus). `hasattr` parce
que `sys.stdout.reconfigure` n'existe que depuis Python 3.7 et qu'on
préfère ne pas casser le script si jamais il tourne sur un Python
exotique sans cette méthode.

### Vérification

Avant le fix, sur Windows :

```
20 failed, 2072 passed, 5 skipped
```

Après le fix, attendu :

```
0 failed, 2092 passed, 5 skipped
```

(les 20 tests qui plantaient passent au vert)

---

## 2. Nouvel outil `outils/verifier_md5.py`

### Objectif

Détecter en quelques secondes les fichiers tronqués / corrompus / modifiés
dans une arborescence, en comparant à un fichier de référence MD5. Le
diagnostic du 10 mai a pris une session entière à cause d'un fichier
Python tronqué qui restait syntaxiquement valide ; cet outil l'aurait
détecté en une commande.

### Format du fichier de référence

Une ligne par fichier :

```
<md5>  <taille_octets>  <chemin_relatif>
```

Compatible avec :

- la sortie native de `md5sum` (Linux/Git Bash)
- le format historique `appli_inventaire.txt` généré côté Windows par
  `Get-FileHash` (testé)
- le BOM UTF-8 produit par `Out-File -Encoding UTF8` est toléré
- les séparateurs `/` ou `\` sont tous deux acceptés
- les lignes vides et les commentaires `#` sont ignorés

### Modes d'utilisation

```bash
# Vérifier l'arborescence courante contre MANIFEST.md5 (ou
# appli_inventaire.txt) :
python -m outils.verifier_md5

# Avec un fichier de référence spécifique :
python -m outils.verifier_md5 --manifest appli_inventaire.txt

# Spécifier la racine :
python -m outils.verifier_md5 --racine D:\Enseignement\seqenseigne\appli

# Ne signaler que les divergences (pour scripts) :
python -m outils.verifier_md5 --silencieux

# Sortie CSV :
python -m outils.verifier_md5 --csv > rapport.csv

# Régénérer un manifeste (mode inverse) :
python -m outils.verifier_md5 --generer
python -m outils.verifier_md5 --generer --extensions .py,.js,.css,.html,.sql,.bat
```

### Codes de sortie

| Code | Sens |
|---|---|
| 0 | Aucune divergence |
| 1 | Au moins un fichier divergent / manquant / tronqué |
| 2 | Manifeste introuvable, racine inexistante, ou erreur grave |

### Sortie typique

Sur l'arborescence Laurent du 10 mai, avec un manifeste reproduisant
les MD5 attendus de v0.13.4.1 :

```
❌ 2 divergence(s) sur 2 fichier(s) :
     0 manquant(s), 2 taille différente, 0 contenu modifié à taille égale

  TRONQUÉ?  services/latex_rendu_atome.py
            attendu 58461, trouvé 57364 (-1097 octets)

  TRONQUÉ?  tests/test_latex_rendu_atome.py
            attendu 71273, trouvé 64617 (-6656 octets)
```

C'est exactement le diagnostic qui a pris une session entière à établir.

### Tests

`tests/test_verifier_md5.py` — **20 tests** couvrant :

- Lecture du manifeste (5 tests) : format standard, séparateurs `\\`,
  BOM UTF-8, lignes vides/commentaires, lignes pourries
- Détection des divergences (4 tests) : manquant, taille différente,
  taille égale + md5 différent, match complet
- Génération inverse `--generer` (3 tests) : manifest cohérent, filtre
  d'extensions, chemins portables avec `/`
- Codes de sortie (4 tests) : 0/1/2 selon les cas
- Sortie CSV (1 test)
- Mode silencieux (2 tests)
- **Cas réel** (1 test) : reproduction de la troncature d'une fonction
  en milieu de définition (sans return), syntaxe Python valide mais
  fichier tronqué — l'outil détecte par la taille même si Python ne
  voit rien.

Lancer :

```bash
cd appli
..\outils\python\python.exe -m pytest tests/test_verifier_md5.py -v
```

Attendu : `20 passed`.

---

## Procédure recommandée à partir de maintenant

### Pour Laurent — vérification après chaque livraison

À l'avenir, chaque livraison Claude inclura un `MANIFEST.md5` à la
racine du ZIP. Procédure de déploiement :

```powershell
# 1. Décompresser le ZIP à la racine de seqenseigne/
# 2. Vérifier l'intégrité immédiate :
cd appli
..\outils\python\python.exe -m outils.verifier_md5 --manifest MANIFEST.md5
# Attendu : ✅ N fichier(s) vérifié(s) — aucune divergence.
```

Si une divergence est signalée → demander une livraison de récupération
**immédiatement**, sans tenter d'utiliser l'appli avec un fichier corrompu.

### Pour Claude — production des livraisons

Avant tout `present_files` :

1. Calculer les MD5 et tailles des fichiers livrés
2. Écrire `MANIFEST.md5` à la racine du ZIP
3. Vérifier que le ZIP décompressé reproduit ces MD5
4. **Seulement après**, présenter le ZIP

---

## Fichiers livrés (3)

| Fichier | Action | MD5 attendu |
|---|---|---|
| `appli/scripts/migrer_methodes_objectifs.py` | Modifié (fix encodage) | voir MANIFEST.md5 |
| `appli/outils/__init__.py` | Nouveau (vide, package marker) | voir MANIFEST.md5 |
| `appli/outils/verifier_md5.py` | Nouveau | voir MANIFEST.md5 |
| `appli/tests/test_verifier_md5.py` | Nouveau (20 tests) | voir MANIFEST.md5 |

Les MD5 et tailles exacts sont dans `MANIFEST.md5` à la racine du ZIP de
livraison.

---

## Suite

Une fois cette livraison validée chez toi (pytest 0 échec sur les 20
tests anciens + 20 nouveaux tests verts), on peut reprendre la roadmap :

- **v0.13.5.2** : transitions auto `en_cours ↔ valide` via hooks dans
  les routes de validation d'atomes (chantier en cours, prochaine étape)
- ou bien tu choisis de capitaliser ce momentum hygiène et on rédige
  `appli/doc/CONVENTIONS.md` + `appli/doc/GOTCHAS.md` (cf. analyse du
  10 mai). Mais ce n'est pas urgent — la priorité reste l'avancement
  fonctionnel.

---

## Note d'attention

L'entrée mémoire utilisateur qui mentionne le bug encodage à v0.14
peut être actualisée :
> ~~scripts/migrer_methodes_objectifs.py (caractère → U+2192 plante
> cp1252, 20 tests rouges Windows ; fix : sys.stdout.reconfigure
> utf-8).~~ **→ Fait en v0.13.5.1.5**.
