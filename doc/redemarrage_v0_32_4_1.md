# Redémarrage v0.32.4.1 — Récap cartes : recto/verso via macros \long\def

Corrige l'erreur de compilation du récap (« Paragraph ended before
…@versoUn was complete ») en contournant la limitation `\setkeys` sur le `\par`.

## Cause (rappel)

La nouvelle macro `\seqCarteRecapAjouteLigneCartes` reçoit recto/verso comme
clés xkeyval (`rectoUn={...}`), lues par `\setkeys`. Or le contenu recto/verso
peut contenir `\par` (texte riche). Même en rendant la macro `\long`
(`\NewDocumentCommand{+O{} +m}`) et les clés `\long` (`\define@key` +
`\long\def`), `\setkeys` capture la valeur de façon non-`\long` → le `\par`
casse. Passer recto/verso en arguments dépasserait la limite `#9` de TeX.

## Correctif (côté appli — Piste 2)

`rendre_ligne_recap` ne passe plus le contenu recto/verso brut en option. Pour
chaque carte, il :
1. définit le contenu dans une macro `\long\def\seqRecapL<ligne><pos><R|V>{…}`
   (dans le bloc `#2` de la macro, exécuté au début) ;
2. passe le NOM de cette macro en option (`rectoUn=\seqRecapL…`).

Le nom ne contient pas de `\par`, donc `\setkeys` ne casse pas ; le flux écrit
`\unexpanded{<nom>}` et le contenu (avec `\par`) est développé à la relecture.
Les noms sont uniques par ligne (index de ligne global encodé en lettres), sinon
la relecture différée du flux prendrait la dernière définition pour toutes les
lignes.

Aucune modification supplémentaire du paquet n'est nécessaire : le .sty actuel
(macro `+O{} +m`, clés recto/verso en `\long\def`, suffixes
typepedago/couleur par carte) convient.

## Fichiers

- `services/render_carte_centralise.py` : `rendre_ligne_recap` (Piste 2) +
  `_nom_macro_recap` (noms uniques).
- `services/livret_cartes_recap.py` : passe un index de ligne global.

## Tests

- pytest : 3905 passed, 7 skipped. vitest : 192 passed.
- Vérifié sur la base réelle : N11 (114 cartes) → 29 lignes, 232 `\long\def`
  tous uniques (pas de collision) ; aucun `\par` dans les options `[...]` ; le
  `\par` du verso S01 C1 est bien dans son `\long\def`.

## Déploiement

Décompresser ; `python -m outils.verifier_md5`. Aucune migration. Nécessite le
paquet à jour (déjà installé). Recompiler le récap : la compilation doit passer,
et l'impression recto-verso « bord court » doit être alignée.
