# Chantier 14 — Rendu LaTeX d'un atome isolé

## Session 2 — Génération du `.tex` d'un atome isolé

### Objectif de la session

Produire, à partir d'un atome stocké en BDD (exercice, notion, méthode),
un fichier `.tex` complet et autonome qui compile en isolation avec
`pdflatex` en quelques secondes — contre 3 minutes pour un livret.

### Ce qui est livré

#### Module `services/latex_rendu_atome.py`

Service pur, 0 dépendance externe, importable par Flask et par les scripts.

API principale :

```python
generer_tex_atome(conn, type_atome, atome_id, racine_sources=None) -> str
```

Où `type_atome ∈ {'exercice', 'notion', 'methode'}` et `racine_sources` est
le dossier racine des `.tex` sources (pour localiser les `NXX_SYY_params.tex`).

### Décisions architecturales

Cinq points structurants ont été tranchés :

**1. Classe de document** : `\documentclass[11pt,a4paper]{article}` +
`\usepackage{seqenseigne}` avec options activées selon les macros utilisées.

**2. Options du paquet** : analyse statique du texte de l'atome →
- `[geometrie]` si au moins une macro de tkz-euclide, tkz-base ou tkz-tab
- `[scratch]` si au moins une macro de scratch3

**3. Thème de la séquence** : lu depuis `referentiel_themes.couleur` via
la séquence de l'atome. Les 5 thèmes valides sont `nombres`, `donnees`,
`grandeurs`, `geometrie`, `algorithmique`. Fallback `gris` si introuvable.

**4. Macros CSV-dépendantes** : résolues par substitution Python avant
génération. `\seqObjectifGetNom{02}` → « Utiliser les fractions » (valeur
depuis `objectifs.nom`). Placeholders lisibles (`[OBJ-02]`) si introuvable.

**5. Fichiers de paramètres de séquence** (`NXX_SYY_params.tex`) :
cherchés sur disque dans plusieurs conventions d'arborescence, inclus via
`\input` si trouvés. C'est ici que vivent les macros tkz partagées entre
exercices d'une même séquence (ex. `\tkzFExoVII` pour N12-S11).

### Pipeline de génération

```
charger_atome(conn, type, id)        ← lit les champs depuis exercices/notions/methodes
  ↓
detecter_options_paquet(conn, atome) ← analyse des macros → ['geometrie'], ['scratch']...
  ↓
resoudre_theme(conn, niveau, seq)    ← couleur depuis referentiel_themes
  ↓
resoudre_macros_csv(conn, texte, ...) ← substitue \seqObjectifGetNom et 7 autres getters
  ↓
trouver_params_sequence(racine, niv, seq) ← localise NXX_SYY_params.tex sur disque
  ↓
collecter_reecritures(conn, ...)     ← récupère les contenu_atome de statut='reecrit'
  ↓
generer_corps(atome)                 ← dispatch vers seqExercice / seqNotion / seqMethode
  ↓
Assemblage final                     ← documentclass + préambule + document + corps
```

### Getters CSV supportés

| Macro | Substitution |
|---|---|
| `\seqObjectifGetNom{code}` | Nom de l'objectif depuis `objectifs.nom` |
| `\seqObjectifGetFinCycle{code}` | 'O' ou 'N' depuis `objectifs.est_nouveau` |
| `\seqSequenceGetNom{code}` | Nom depuis `referentiel_sequences.nom` |
| `\seqSequenceGetNumero{code}` | Numéro depuis `referentiel_sequences.numero` |
| `\seqSequenceGetTheme{code}` | Code thème depuis `referentiel_sequences.theme_code` |
| `\seqThemeGetNom{code}` | Nom depuis `referentiel_themes.nom` |
| `\seqNiveauGetNomCourt{code}` | `N10 → 5e`, `N11 → 4e`, `N12 → 3e` |
| `\seqNiveauGetNomLong{code}` | `N10 → Cinquième`, etc. |
| `\seqConnaissanceGetNom{code}` | Titre depuis `notions.titre` |

Argument vide (`{}`) → utilise la séquence/niveau courants de l'atome.

### Signatures respectées

Le code respecte les signatures réelles du paquet :

- `\begin{seqExercice}[nom=…, obj=…]` (un argument optionnel, clés via `\define@cmdkey`)
- `\begin{seqNotion}{titre}{corps}` (2 args obligatoires, numéro par compteur)
- `\begin{seqMethode}{titre}{corps}` (idem)

Les compteurs `NotionNum`, `MethodeNum`, `SerieExosNum`, `ExoNum` sont
initialisés correctement à `num - 1` pour que `\refstepcounter` en entrée
d'environnement produise le bon numéro.

### Validation

**Tests pytest** : 41 tests, tous verts.

- `TestChargerAtome` : 5 tests — chargement des 3 types + erreurs.
- `TestDetecterOptions` : 4 tests — sans, tkz, scratch, les deux.
- `TestResoudreTheme` : 4 tests — thème connu, inconnu, vide.
- `TestResoudreMacrosCsv` : 8 tests — les 9 getters + arguments vides.
- `TestTrouverParamsSequence` : 5 tests — conventions standard/alternative, absences.
- `TestCollecterReecritures` : 2 tests.
- `TestGenererCorps` : 7 tests — structure des 3 types d'environnements, compteurs.
- `TestGenererTexAtome` : 6 tests — bout en bout, options, CSV résolus, `\input` params.

**Test de compilation réelle** : un atome `N10S01F01.tex` a été généré
par le service et soumis à `pdflatex`. La compilation charge correctement
`seqenseigne.sty`, `seqenseigne-core.sty`, `seqenseigne-data.sty` et leurs
dépendances (datetime, geometry, fancyhdr, multicol, pifont, enumitem…)
sans erreur de syntaxe dans le `.tex` généré. La compilation échoue
ensuite sur l'absence de `lmodern.sty` dans l'environnement de test, ce
qui ne concerne pas le `.tex` produit mais l'installation TeX Live.

Validation de compilation complète à faire chez toi en session 3 ou en
amont de la session 3.

### Résultats sur la vraie BDD

Sur la base Laurent (1 124 atomes) :

```
[exercice N10S01F01.tex] \usepackage{seqenseigne}            ← plain
[exercice N10S01F01.tex] \seqSetColorsTheme{nombres}
[exercice N10S10A03.tex] \usepackage[geometrie]{seqenseigne} ← tkz détecté
[exercice N10S10A03.tex] \seqSetColorsTheme{grandeurs}
[exercice N11S09F01.tex] \usepackage{seqenseigne}            ← stats, pas géométrie
[exercice N11S09F01.tex] \seqSetColorsTheme{donnees}
```

Détection des options + thèmes : validée.

Résolution des getters CSV : `N12_S14_Methode_03.tex` contient
`\seqObjectifGetNom{03}` → substitué automatiquement par « Écrire et
mettre au point un jeu utilisant des instructions conditionnelles… ».

### Points ouverts pour la session 3 (compilation PDF)

- Compilation effective via `subprocess pdflatex` dans `/tmp` avec timeout.
- Cache PDF par `hash(tex)` pour éviter de recompiler un atome déjà vu.
- Extraction des erreurs pdflatex (numéro de ligne, message) pour affichage.
- Route Flask `POST /api/atomes/<id>/rendu-pdf` avec streaming du PDF.
- Détermination précise du chemin `racine_sources` depuis la config Flask
  (nouvelle variable d'environnement ou champ de configuration).

### Points ouverts pour la session 4 (UI)

- Bouton « Voir le rendu » dans les ateliers Notion/Méthode/Exercice.
- Affichage inline du PDF (iframe) ou bouton de téléchargement.
- Affichage des erreurs de compilation avec highlight sur la ligne concernée.

### Limitation actuelle

L'appel à `collecter_reecritures(conn, set())` passe un ensemble vide de
macros utilisées et retourne **toutes** les réécritures connues. Ce n'est
pas un problème correctif (ces réécritures sont des neutralisations qu'on
veut toujours émettre en atomique), mais une optimisation possible en
session 3+ : si la liste de réécritures devient longue, la filtrer
finement selon les macros appelées par l'atome réduirait la taille du
préambule.

### Fichiers créés

```
services/latex_rendu_atome.py       (service pur, 400 lignes)
tests/test_latex_rendu_atome.py     (41 tests)
doc/chantier_14_session_2.md        (ce fichier)
```

Aucun fichier existant modifié.

### État global du chantier 14

| Session | Objectif | Statut |
|---|---|---|
| 1 | Schéma + peuplement + vérification de couverture | ✓ Livrée |
| 2 | Génération du .tex d'un atome isolé | ✓ Livrée (cette session) |
| 3 | Compilation PDF + cache + route Flask | À faire |
| 4 | UI bouton « Voir le rendu » | À faire |

Tests globaux du chantier : 109 verts (68 session 1 + 41 session 2).
