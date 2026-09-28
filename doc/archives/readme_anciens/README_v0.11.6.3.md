# seqenseigne — patch v0.11.6.3

**Phase B** : alignement de la disposition de la boîte de titre dans les
sections corrigés et remédiation, en miroir de la nouvelle disposition de
la boîte principale livrée en v0.11.6.2.

**Cette livraison inclut tout v0.11.6.1 et v0.11.6.2** — donc en partant
d'une appli v0.11.6, ce zip est complet.

## Ce qui change par rapport à v0.11.6.2

### Côté paquet uniquement

Trois macros internes du module `core-exos` reformatées pour produire la
même boîte de titre 2 lignes (numéro+objectif / titre) que `seqExercice` :

- `\seq@ecrit@corrige@Exo` (entêtes des sections corrigés en fin de livret)
- `\seq@ecrit@remediation@enonce` (entêtes des énoncés de remédiation)
- `\seq@ecrit@remediation@corrige` (entêtes des corrigés de remédiation)

Disposition produite désormais (dans les 4 contextes — boîte principale,
section corrigés, section énoncés remédiation, section corrigés
remédiation) :

```
┌────────────────────────────────────────────────┐
│ Exercice N                       Objectif XX   │  ← ligne 1
│ Titre de l'exercice                            │  ← ligne 2 (si fourni)
│ Remédiation p. XX                              │  ← ligne 3 (boîte princ. uniquement)
└────────────────────────────────────────────────┘
```

La ligne 3 « Remédiation p. XX » n'apparaît **que** dans la boîte
principale, pas dans les sections corrigés/remédiation (où ça n'aurait
pas de sens — on est déjà arrivé sur la page).

### Côté Python : aucune modif vs v0.11.6.2

Les services Python étaient déjà prêts en v0.11.6.2 (l'option `obj=...`
passée à `seqExercice` est consommée par les 3 helpers `\seq@ecrit@...`
au moment de leur exécution, qui se trouve dans le scope de `seqExercice`
où `\cmdseq@exercice@obj` est encore défini).

## Validation

Je n'avais pas pu tester en v0.11.6.2 par crainte de la mécanique
`\immediate\write` + `\unexpanded` + `\@charlb`/`\@charrb` qui demandait
une compilation LaTeX réelle pour valider. **Pour cette livraison v0.11.6.3,
j'ai installé TeX Live + tabularray + lmodern + babel-french dans mon
environnement et compilé un MWE qui exerce les 3 zones touchées** :

- 1 série fondamentale avec 3 exercices (avec/sans objectif, avec/sans
  titre, avec/sans remédiation, avec/sans cadre de réponse)
- Compilation 2 passes pour stabiliser les `\pageref`

Résultat : **4 pages bien formées, alignement visuel parfait entre les 4
contextes**. Le PDF généré est inclus dans cette archive sous
`exemple_validation.pdf` (4 pages, ~100 Ko).

## Fichiers livrés

```
paquet/seqenseigne-core-exos.dtx        # 3 macros @write reformatées
paquet/seqenseigne-core-exos.sty        # idem (synchronisé)
paquet/seqenseigne-theme.dtx            # \seqStyleObjectifsHeader (v0.11.6.2)
paquet/seqenseigne-theme.sty            # idem (v0.11.6.2)

scripts/peuplement_14_paquet_vers_base.py   # v0.11.6.1
services/preambule_atome.py                 # v0.11.6.1
services/latex_rendu_atome.py               # v0.11.6.2
services/livret_sequence.py                 # v0.11.6.2
services/livret_recap_exos.py               # v0.11.6.2

tests/test_paquet_peuplement.py             # v0.11.6.1
tests/test_paquet_parseur.py                # v0.11.6.1
tests/test_latex_rendu_atome.py             # v0.11.6.2
tests/test_livret_sequence.py               # v0.11.6.2
tests/test_route_livret_sequence.py         # v0.11.6.2

exemple_validation.pdf                      # preuve de compilation, 4 pages
```

## Procédure

1. **Côté paquet** : décompresser à la racine du dépôt seqenseigne ; les 4
   fichiers `paquet/*` doivent venir aux côtés des autres `.dtx`/`.sty`
   du paquet. (Tu peux choisir d'appliquer le `.dtx` et regénérer le
   `.sty` via `seqenseigne.ins`, ou prendre les deux directement — les
   deux versions sont synchronisées.)

2. **Côté appli** : décompresser à la racine de `appli/`. Si tu as déjà
   v0.11.6.2 en place, **les fichiers `services/`, `scripts/` et
   `tests/` sont identiques à v0.11.6.2** — pas de changement Python
   pour cette Phase B. Tu peux les écraser sans risque, ou ne décompresser
   que `paquet/`.

3. **Réimporter le paquet** depuis l'admin de l'appli (rapport doit
   toujours montrer 5 fichiers, 0 règle orpheline).

4. **Recompiler** un livret avec exercices ayant objectif(s), titre, et
   au moins une remédiation. Vérifier que les 4 contextes (boîte
   principale, section corrigés, section énoncés remed, section corrigés
   remed) ont la même disposition.

## Tests

- Suite Python complète : **1785 passed** (inchangé vs v0.11.6.2 — pas de
  modif Python dans cette Phase B).
- Test LaTeX réel : compilation 2 passes d'un MWE qui exerce les 3
  zones touchées, **0 erreur, 4 pages stables**. PDF inclus.

## Pour le CHANGELOG / mémoire

Suggestion de note `recent_updates` :

> v0.11.6.3 — Phase B : alignement des entêtes des sections corrigés et
> remédiation sur la nouvelle disposition de la boîte de titre principale
> livrée en v0.11.6.2 (numéro+objectif ligne 1, titre ligne 2). Touche
> les 3 macros internes \seq@ecrit@corrige@Exo,
> \seq@ecrit@remediation@enonce et \seq@ecrit@remediation@corrige du
> module core-exos. Aucune modif côté appli (les services Python étaient
> déjà prêts en v0.11.6.2 — l'option obj= passée à seqExercice est
> automatiquement disponible dans le scope des helpers @write). Validation
> par compilation LaTeX réelle (MWE 4 pages exerçant les 4 contextes,
> 0 erreur, 2 passes stables). 1785 tests Python (inchangé).
