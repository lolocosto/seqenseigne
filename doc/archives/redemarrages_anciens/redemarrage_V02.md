# Redémarrage — projet seqenseigne
_Préparé le 10 avril 2026_

---

## Contexte général

Laurent Coste, enseignant collège (cycle 4).
Niveaux : N10=5ème, N11=4ème, N12=3ème (14 séquences chacun).
Paquet LaTeX custom `seqenseigne` + application Flask de conception pédagogique.
Dépôt : `forge.apps.education.fr/laurentcoste/seqenseigne`
Environnement : clé USB MiKTeX portable x64, Python portable, Windows cmd.

---

## État du paquet LaTeX

### Modifications récentes (à intégrer via `make install`)
- **`seqenseigne-core.dtx`** — plusieurs changements :
  - Option `[geometrie]` : charge `tkz-euclide`, `tkz-base`, `tkz-tab` à la demande
  - Option `[scratch]` : charge `scratch3` à la demande
  - Supprimés : `tabularx`, `amsfonts`, `kvoptions` (0 usage dans le paquet)
  - `amssymb` remis (nécessaire pour `\leqslant` dans les exercices)
  - Fix warnings hyperref : `\theHExoNum`, `\theHNotionNum`, etc. définis dans `seqCreeCompteurs`
- **`seqenseigne.sty`** — options `[geometrie]` et `[scratch]` déclarées et transmises à `core`
- Fichiers dans `/mnt/user-data/outputs/` : `seqenseigne-core.dtx`, `seqenseigne.sty`

### Livrets à mettre à jour (option `[geometrie]`)
```
N10 : S01, S05, S07, S10, S11, S12, S13  →  \usepackage[geometrie]{seqenseigne}
N11 : S03, S09, S10, S11, S12, S13
N12 : S07, S09, S11, S12
Les 25 autres restent \usepackage{seqenseigne}
```
**Script de migration non encore produit** — à faire en début de session.

### Formats précompilés `.fmt` (non encore testés)
Fichiers prêts dans `/mnt/user-data/outputs/` :
- `seqenseigne_fmt.tex` — source du fmt sans géométrie
- `seqenseigne_geo_fmt.tex` — source du fmt avec géométrie
- `Makefile.win` — cible `make fmt` intégrée, règles `compile_livret` / `compile_livret_geo`

Procédure de test :
```bat
make -f Makefile.win install
make -f Makefile.win fmt
make -f Makefile.win N10-S03   ← sans géométrie, doit être ~2min
make -f Makefile.win N10-S12   ← avec géométrie
```

### Migrations N11 / N12 terminées
Archives dans `/mnt/user-data/outputs/` :
- `N11_migration_complete.zip`
- `N12_migration_complete.zip`

---

## État de l'application Flask

### Architecture décidée
```
Ateliers de conception          Gestion de classe
─────────────────────           ─────────────────
Notion (= Connaissance)         Paramétrage (années, établissements, classes, élèves)
Méthode + critères F/A/E        Suivi (classe × progression × objectif × élève)
Exercice + corrigé + variables
Livret (assemblage)
Progression annuelle
```

### Modèle de données
- **Notion** : atome autonome (titre + corps + exemples + remarques)
  - Identifiée par un id court (8 car hex), sans lien intrinsèque à une séquence
  - Affectation séquence/numéro gérée dans l'atelier Livret
- **Méthode** : même structure + notions associées + fin de cycle O/N + critères F/A/E
  - Crée implicitement un **Objectif** lors de l'affectation à une séquence
  - Objectif 01 "Connaître le cours" automatique dans chaque séquence, critères fixes
- **Barème fixe** : I=4pts, F=10pts, A=16pts, E=20pts
- **Exercice** : niveau F/A/E + objectif(s) + variables param + énoncé + corrigé
- Persistence actuelle : CSV + JSON + .tex ; BdD SQLite prévue à terme

### Ateliers déjà prototypés (widgets Claude)
1. **Notion/Connaissance** — liste + éditeur (titre, corps, exemples, remarques permutables)
   → LaTeX : `\begin{seqNotion}{titre}{corps}\exemples\remarques\end{seqNotion}`
2. **Méthode** — même structure + onglet "Objectif/critères" (notions associées, fin de cycle, F/A/E)
   → LaTeX : `\begin{seqMethode}{\seqObjectifGetNom{??}}{...}`

### Nouveau module backend
**`param_evaluator.py`** — évaluateur de blocs `_param.tex` xintexpr :
- Supporte `\xintdefiivar`, `\xintdeffloatvar`, `\xintdefvar`
- `randrange(a,b)`, ternaire `(COND)?{VRAI}{FAUX}`, `\ifnumequal`
- Testé sur `N10S03_param.tex` — tous les tirages corrects
- Fichier : `/mnt/user-data/outputs/param_evaluator.py`

**Nouvelles routes Flask** (dans `app.py`) :
```
POST /api/param/tester    { source, n=5 }  → { tirages, variables }
POST /api/param/variables { source }       → { variables }
```

### Prochaine étape immédiate
**Atelier Exercice** — à coder :
```
Niveau          [F / A / E]
Objectifs       [0..N depuis les méthodes]
─────────────────────────────────────────
Variables       [éditeur code _param.tex]
  → Bouton "Tester" → appel /api/param/tester → affiche N tirages côte à côte
  → Liste des variables détectées (pour autocomplétion dans énoncé/corrigé)
─────────────────────────────────────────
Énoncé          [LaTeX libre]
Corrigé         [LaTeX libre — toujours présent]
─────────────────────────────────────────
Prévisualisation HTML + LaTeX généré
```

---

## Fichiers disponibles dans `/mnt/user-data/outputs/`
```
seqenseigne-core.dtx          paquet modifié (geometrie, scratch, fixes)
seqenseigne.sty               paquet modifié
Makefile.win                  avec fmt et compile_livret_geo
seqenseigne_fmt.tex           source fmt sans géométrie
seqenseigne_geo_fmt.tex       source fmt avec géométrie
param_evaluator.py            évaluateur xintexpr
app.py                        Flask avec routes /api/param/*
N11_migration_complete.zip    livrets N11 migrés
N12_migration_complete.zip    livrets N12 migrés
analyser_paquets.py           analyseur de dépendances LaTeX
N10_S01_profil.tex            livret de profiling pdfelapsedtime
lire_profil.py                script d'analyse du log de profiling
```

---

## Points en suspens
- [ ] Script migration `\usepackage[geometrie]` dans les 17 livrets
- [ ] Test et mesure des `.fmt` précompilés
- [ ] Atelier Exercice (backend prêt, front à construire)
- [ ] Atelier Livret (assemblage des atomes)
- [ ] N09 (6ème) : migration notions/méthodes non encore faite
