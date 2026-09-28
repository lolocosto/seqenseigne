# Patch v0.9.4 — Fix « No room for a new \write » dans le Récap cours

**Date** : 29 avril 2026

## Symptôme

Compilation du Livret Récap cours N10 :

```
! No room for a new \write.
==> Fatal error occurred, no output PDF file produced!
```

À l'inspection du `.tex` généré : 122 occurrences de `\seqAfficheAnnexes`
(et autant de `\seqInitAnnexes`), une paire par notion ou méthode du
livret.

## Cause

Le paquet `seqenseigne` définit `\seqInitAnnexes` ainsi :

```latex
\newcommand{\seqInitAnnexes}{
  \newwrite\annfile
  \immediate\openout\annfile=AnnList.tex
  \immediate\write\annfile{...}
}
```

Or **TeX limite à 16 streams `\write` ouverts simultanément**, et
`\newwrite` n'est jamais libéré (même par `\closeout`, qui ferme le
fichier mais ne rend pas le slot d'allocation). Émettre 122 cycles
`\seqInitAnnexes` … `\seqAfficheAnnexes` épuise donc l'allocation au
17ᵉ atome et fait planter pdflatex.

Côté Python, ces cycles étaient émis par `generer_corps_notion` et
`generer_corps_methode` (`services/latex_rendu_atome.py`), qui les
ajoutent depuis la v0.9.1 — précaution défensive pour les rares atomes
contenant un `\seqAnnexe` (3 méthodes seulement : N11/S04/M01, N11/S04/M02,
N12/S04/M02). Acceptable pour un rendu unitaire (1 cycle par compilation),
catastrophique pour le Récap cours qui agrège tout un niveau dans un
seul document.

## Fix

### `services/latex_rendu_atome.py`

Ajout d'un paramètre `inclure_init_annexes: bool = True` à
`generer_corps_notion` et `generer_corps_methode`. Par défaut `True` :
le rendu unitaire conserve à l'identique le comportement v0.9.1 (et tous
les tests `TestInitAnnexesV091` restent verts). Quand `False`, ces deux
macros ne sont plus émises autour de l'atome.

### `services/livret_recap_cours.py`

- Les wrappers `_generer_corps_notion_continu` et
  `_generer_corps_methode_continu` passent désormais
  `inclure_init_annexes=False`.
- **Un seul** `\seqInitAnnexes` est émis juste après `\seqCreeCompteurs`
  (début du document).
- **Un seul** `\seqAfficheAnnexes` est émis juste avant `\end{document}`.

## Effet de bord assumé

Pour les 3 méthodes qui utilisent réellement `\seqAnnexe` (N11/S04 ×2,
N12/S04 ×1), leurs annexes sont désormais accumulées dans un même
`AnnList.tex` global et affichées **à la toute fin du livret**, plutôt
que juste après leur méthode respective. C'est cohérent avec la
convention « annexes en fin de document » des livrets papier classiques.
Si le placement « collé à l'atome » devient nécessaire, on pourra
alterner `\seqAfficheAnnexes` + `\seqInitAnnexes` à des points
stratégiques (par ex. en fin de chaque thème — 5 cycles, largement sous
la limite des 16).

## Validation

- Tests `tests/test_latex_rendu_atome.py` : **80/80** passent (paramètre
  par défaut = comportement antérieur).
- Tests `test_preambule_atome.py` + `test_compilation_batch.py` :
  **201/201** passent au total sur les modules touchés.
- Génération `generer_recap_cours(conn, 'N10', ...)` : **1 seul**
  `\seqInitAnnexes` et **1 seul** `\seqAfficheAnnexes` dans le body
  (vs 122 + 122 avant fix).

## Application

```bash
cd /chemin/vers/seqenseigne
patch -p1 < patch_v0_9_4_recap_cours_annexes.diff
```

Ou avec git :

```bash
git apply patch_v0_9_4_recap_cours_annexes.diff
```
