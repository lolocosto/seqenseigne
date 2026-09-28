# seqenseigne appli — patch v0.11.6.1

Correctifs pour les deux bugs remontés sur le rendu et la compilation des
exercices avec remédiation.

## Bugs corrigés

### Bug 1 — Compilation des livrets avec remédiation : « Undefined control sequence \seqInitRemediation »

**Cause racine** : le script `peuplement_14_paquet_vers_base.py` ignorait le
fichier `seqenseigne-core-exos.sty`, extrait de `core` en v0.11.5. Toutes les
macros liées aux corrigés et à la remédiation
(`\seqInitCorriges`, `\seqAfficheCorriges`, `\seqCorrige`,
`\seqInitRemediation`, `\seqRemediation`, `\seqCadreReponse`,
`\seqAfficheRemediations`, `\seqAfficheCorrigesRemediation`,
`\seq@ecrit@corrige@Exo`, `\seq@ecrit@corrige@serieExos`) y résident.
N'étant pas peuplées en base, `construire_preambule` ne pouvait pas les
inliner dans le préambule du `atome.tex` généré, d'où l'erreur fatale au
moment où `livret_sequence.py` émettait `\seqInitRemediation` en début de
corps.

C'est aussi la cause des **5 règles orphelines** signalées par le rapport
de peuplement.

### Bug 2 — Rendu atomique d'un exercice : ni cadre de réponse, ni section remédiation

**Cause** : `services/latex_rendu_atome.py:generer_corps_exercice` ne
consommait pas les 4 colonnes `remed_enonce`, `remed_corrige`,
`cadre_reponse_lignes_principal`, `cadre_reponse_lignes_remed` ajoutées en
v0.11.6 (correctement chargées dans `Atome` mais jamais émises). Modèle
d'émission aligné sur
`livret_recap_exos._generer_corps_exercice_continu`.

## Fichiers livrés

```
scripts/peuplement_14_paquet_vers_base.py   # ajout 'seqenseigne-core-exos.sty' à FICHIERS_ORDRE
services/preambule_atome.py                 # ajout 'seqenseigne-core-exos.sty' à _ORDRE_FICHIERS
services/latex_rendu_atome.py               # generer_corps_exercice : cadre + remédiation + sections fin
tests/test_paquet_peuplement.py             # fixture paquet_mini : nouveau .sty minimal
tests/test_paquet_parseur.py                # nouveau test_core_exos_sty_parse + cleanup test_core_sty_parse
```

## Procédure

1. Décompresser cette archive à la racine de `appli/` (les chemins respectent
   l'arborescence existante — il s'agit d'écraser 5 fichiers).
2. Depuis l'admin de l'appli, **réimporter le paquet seqenseigne** :
   le rapport de peuplement doit maintenant lister 5 fichiers
   (core, core-exos, theme, data, legacy) et **0 règle orpheline**.
3. Recompiler un livret de séquence ayant des exercices avec remédiation
   (par ex. N10 S01) : la compilation doit passer.
4. Rendre un exercice ayant `cadre_reponse_lignes_principal > 0` et/ou une
   remédiation : le cadre et le bloc de remédiation doivent apparaître.

## Tests

Suite complète exécutée localement : **1785 passed** (vs 1780 en v0.11.6,
+5 tests sur `test_paquet_parseur.py`).

## Note sur `tests/test_paquet_parseur.py`

Le test `test_core_sty_parse` assertait `\seqCorrige` et `seqExercice` dans
`seqenseigne-core.sty` ; ces deux entrées ont été extraites vers `core-exos`
en v0.11.5 mais le test n'avait pas été mis à jour à l'époque (dette
préexistante, masquée tant qu'on ne touchait pas au reste). Corrigé ici par
nettoyage du test existant et ajout de `test_core_exos_sty_parse`.

## Pour le CHANGELOG / mémoire

Suggestion de note `recent_updates` :

> v0.11.6.1 (correctif) — Le script de peuplement et `preambule_atome` ont
> été mis à jour pour reconnaître `seqenseigne-core-exos.sty` (extrait de
> core en v0.11.5). Sans ça, les macros `\seqInitRemediation`,
> `\seqRemediation`, `\seqCadreReponse` et la famille corrigés n'étaient
> jamais peuplées en base — d'où plantage de compilation des livrets avec
> remédiation et 5 règles orphelines au rapport. Le rendu atomique d'un
> exercice émet désormais aussi le cadre de réponse principal, le bloc
> remédiation, et les sections finales `\seqAfficheRemediations` /
> `\seqAfficheCorrigesRemediation`. 1785 tests.
