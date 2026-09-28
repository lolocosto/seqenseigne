# Redémarrage v0.13.5.1.6 — Hygiène (suite) : CONVENTIONS + GOTCHAS + lancer.bat

Date : 10 mai 2026
Périmètre : 3 fichiers nouveaux ou modifiés (hors `appli_inventaire.txt` régénéré)

---

## Contexte

Suite à la livraison v0.13.5.1.5.1 qui a stabilisé l'hygiène de
livraison (fix encodage cp1252 + `outils/verifier_md5.py`), on
capitalise pour rendre **l'environnement de travail auto-documenté** :

1. `CONVENTIONS.md` consolide toutes les conventions techniques (BDD,
   services, routes, UI, tests, LaTeX, livraison) pour qu'une nouvelle
   session Claude n'ait plus à les re-redécouvrir.
2. `GOTCHAS.md` catalogue les pièges connus avec diagnostic et solution
   pour qu'on ne repasse plus 2 sessions sur un problème déjà résolu.
3. `lancer.bat` intègre la vérification d'intégrité MD5 obligatoire au
   démarrage, qui bloque le serveur si l'arborescence diverge de
   `appli_inventaire.txt`.

---

## 1. `appli/doc/CONVENTIONS.md` (nouveau)

Document de référence cartographiant **tout** ce qui se répète :

- **Section 0** : Stack technique + lexique niveaux/cycles
- **Section 1** : BDD SQLite (familles de tables, conventions FK, accès dans services/routes)
- **Section 2** : Services Python (organisation, naming, hiérarchie d'exceptions, sentinelles PATCH)
- **Section 3** : Routes Flask (blueprints, codes HTTP, body/retours JSON)
- **Section 4** : Frontend (design system `atl-*`, primitives `atelier_atome_generique.js`, naming IDs)
- **Section 5** : Tests pytest (fixtures, classes par catégorie, subprocess UTF-8)
- **Section 6** : LaTeX (modules `.dtx`, macros `\seq*` publiques vs `\seq@*` privées, pattern tabularray)
- **Section 7** : Livraison (format ZIP, MANIFEST.md5, procédures côté Laurent et Claude)
- **Section 8** : Versionnage
- **Section 9** : Documentation

À joindre désormais à chaque session avec le `redemarrage_*.md` courant.

---

## 2. `appli/doc/GOTCHAS.md` (nouveau)

Catalogue des 20 pièges techniques rencontrés sur le projet, avec
diagnostic et solution :

1. Encodage Windows cp1252 vs UTF-8 — écriture (fix v0.13.5.1.5)
2. Encodage Windows cp1252 vs UTF-8 — lecture subprocess (fix v0.13.5.1.5.1)
3. Windows CRLF — conversion silencieuse à l'écriture (fix v0.13.5.1.5.1)
4. Fichier Python tronqué sans erreur de syntaxe (diag du 10 mai)
5. `vwcol` avec `[lines=N]` plante en compilation agrégée (v0.8.6)
6. `\xdef` vs `\gdef` dans les caches de filtre LaTeX (~v0.6)
7. `\makeatletter` interdit dans les `.tex` utilisateur
8. Compilation web 2-pass vs CLI 1-pass — `\pageref{LastPage}=??` (ouvert)
9. SQLite — `Promise.all` casse les FK (~v0.10.x)
10. DELETE+INSERT bulk casse les FK aux scans suivants
11. Calendrier scolaire — API `population:Élèves` cache des vacances (v0.6.3)
12. Timezone Paris pour comparaison de dates (v0.6.3)
13. `referentiel_*` tables = archives historiques, pas la base active
14. Onglet d'atelier qui ne s'affiche plus après refactor HTML (v0.6.2)
15. Import historique multi-classes — UUID écrasés (v0.6.x)
16. Génération d'ID classe — collisions silencieuses (v0.6.x)
17. Hash-based idempotence des images
18. `objectifs_v2.methode_id` absent chez Laurent — workaround pérenne
19. Antivirus / OneDrive — corruption silencieuse de fichiers
20. ZIPs Claude — `__pycache__` et `.pytest_cache` parasites

À joindre à chaque session avec `CONVENTIONS.md`.

---

## 3. `lancer.bat` (modifié)

### Avant

```batch
@echo off
cd /d "%~dp0"
echo.
echo  seqenseigne
echo  Ouvrir : http://localhost:5000
echo.
..\outils\python\python.exe app.py
pause
```

Le `lancer.bat` historique est dans `appli/` et appelle
`..\outils\python\python.exe app.py` (Python portable au-dessus de
`appli/`). On garde ce placement.

### Après

Le nouveau `lancer.bat` reste dans `appli/`. Il :

1. Vérifie l'existence de `appli\appli_inventaire.txt` et de
   `appli\outils\verifier_md5.py`. Sort en 2 si absent.
2. Lance `verifier_md5.py --silencieux`. Capture le code retour.
3. Si retour = 2 (erreur de lecture du manifest) → message d'erreur,
   exit 2, pas de serveur lancé.
4. Si retour = 1 (divergence détectée) → relance `verifier_md5` en mode
   verbeux pour afficher le détail, message d'erreur explicatif des 3
   causes possibles + solutions, exit 1, pas de serveur lancé.
5. Si retour = 0 (intégrité OK) → message [OK] puis démarrage normal.

### Option de bypass

Pour les cas de développement actif où la divergence est attendue
(édition locale en cours, base saine connue) :

```
.\lancer.bat --skip-verify
```

ou

```
.\lancer.bat --no-verify
```

→ saute la vérification, lance directement le serveur avec un message
d'avertissement.

### Procédure recommandée après chaque livraison validée

```powershell
# 1. Deployer le ZIP (decompression a la racine de seqenseigne/)
# 2. Verifier MD5 de la livraison via le MANIFEST.md5 fourni :
cd D:\Enseignement\seqenseigne
.\outils\python\python.exe appli\outils\verifier_md5.py ^
   --racine . --manifest MANIFEST.md5
# 3. Lancer pytest, valider qu'il n'y a plus d'echec
cd appli
..\outils\python\python.exe -m pytest tests/ -q
# 4. Regenerer la reference d'integrite pour le prochain lancer.bat :
..\outils\python\python.exe outils\verifier_md5.py ^
   --racine . --generer --manifest appli_inventaire.txt
# 5. Lancer normalement (lancer.bat est dans appli/) :
.\lancer.bat
```

---

## 4. `appli/appli_inventaire.txt` (mis à jour)

L'inventaire actuel chez toi (du 7 mai) est obsolète : il référence
des tailles d'avant v0.13.5.1.4 et v0.13.5.2.1. Cette livraison
inclut un nouveau `appli_inventaire.txt` calculé à partir de l'**état
courant** après application de :

- `seqenseigne-recup-latex_rendu_atome.zip`
- `seqenseigne-v0.13.5.1.5.zip`
- `seqenseigne-v0.13.5.1.5.1.zip`
- la présente livraison `seqenseigne-v0.13.5.1.6.zip`

Soit 202 entrées (les ~195 originaux + 4 nouveaux fichiers de
v0.13.5.1.5 + 3 docs nouveaux de v0.13.5.1.6).

Tu pourras te lancer directement après dépôt — le premier
`.\lancer.bat` devrait afficher `✅ ... aucune divergence`.

---

## Fichiers livrés

| Fichier | Action |
|---|---|
| `appli/doc/CONVENTIONS.md` | Nouveau (~21 Ko) |
| `appli/doc/GOTCHAS.md` | Nouveau (~14 Ko) |
| `lancer.bat` | Modifié (en remplacement, à la racine du dépôt) |
| `appli/appli_inventaire.txt` | Mis à jour (incluant tous les fichiers livrés depuis v0.13.5.1.4) |
| `appli/doc/redemarrage_v0_13_5_1_6.md` | Ce doc |

MD5 et tailles dans `MANIFEST.md5` à la racine du ZIP.

---

## Validation

Aucun test ajouté ou modifié dans cette livraison — c'est de la
documentation et du tooling.

`pytest tests/ -q` doit toujours afficher `2112 passed, 5 skipped, 0
failed` après application.

`.\lancer.bat` doit afficher :

```
 seqenseigne

 Verification d'integrite des fichiers...
 [OK] Integrite verifiee

 Demarrage du serveur sur http://localhost:5000
```

---

## Suite

On peut désormais reprendre la **v0.13.5.2** (transitions auto
`en_cours ↔ valide` via hooks dans les routes de validation d'atomes)
dans de bonnes conditions :

- Référence d'intégrité opérationnelle
- Conventions et gotchas consultables en début de session
- Procédure de livraison robuste (Claude self-check + Laurent verify
  automatique au démarrage)

Pour la prochaine session, joindre simplement :

1. Le redemarrage le plus récent (`redemarrage_v0_13_5_1_6.md` puis
   `redemarrage_v0_13_5_2_X.md` quand on y sera)
2. `appli/doc/CONVENTIONS.md`
3. `appli/doc/GOTCHAS.md`

Pas besoin de joindre l'arborescence — sauf si on attaque un fichier
qu'on n'a pas en mémoire.
