r"""services/planche_suffixation.py — v0.15.2.3

Suffixation des variables xint pour les planches de cartes d'automatisme.

Contexte
--------
Une planche affiche 16 copies indépendantes d'une même carte paramétrée,
chacune avec un tirage de valeurs différent. Pour figer ces 16 tirages
sans recourir à un `\edef` (qui expanserait et casserait les macros
fragiles comme `\degre`, `\seqFrac`, l'environnement `seqColEnum`), on
adopte la stratégie « pré-tirage suffixé » :

1. Pour chaque cellule i (01..16), on génère un bloc de tirage où chaque
   variable `v` déclarée par `\xintdefiivar`/`\xintdeffloatvar` est
   renommée `v_i`. Ces 16 blocs sont écrits dans un fichier auxiliaire
   `tirages.tex` qui est `\input` AVANT les planches : toutes les
   variables suffixées y sont donc définies.

2. Le contenu (recto/verso) de la cellule i est réécrit pour référencer
   `v_i` au lieu de `v`. Ce contenu est écrit en `\unexpanded` dans les
   flux des planches : aucune macro fragile n'est jamais expansée.

La suffixation repose sur l'extraction des noms RÉELLEMENT déclarés dans
le bloc variables (pas sur une convention de nommage présumée), donc
elle est robuste quel que soit le nommage choisi par l'enseignant.

Sécurité de substitution
-------------------------
La substitution est « mot entier » : un nom court (`p`) n'est jamais
substitué à l'intérieur d'un nom long (`prix`). On utilise des
lookarounds excluant les caractères de mot xint `[A-Za-z0-9_]`, et on
traite les noms du plus long au plus court par prudence supplémentaire.

API
---
extraire_noms_variables(bloc_variables) -> list[str]
suffixer_noms(texte, noms, suffixe) -> str
suffixe_cellule(i) -> str  (01..16, zéro-padé)
"""
from __future__ import annotations

import re

# Déclarations xint qui introduisent une variable nommée.
# \xintdefiivar NOM := ... ;   \xintdeffloatvar NOM := ... ;
# (\xintdefvar existe aussi mais n'est pas utilisé dans le corpus ;
#  on le gère par robustesse.)
_RE_DECLARATION = re.compile(
    r'\\xintdef(?:ii|float|)var\s+([A-Za-z][A-Za-z0-9_]*)\s*:='
)


def extraire_noms_variables(bloc_variables: str) -> list[str]:
    r"""Extrait les noms de variables déclarés par \xintdef*var.

    Renvoie la liste des noms dans l'ordre d'apparition, sans doublon.

    Exemple
    -------
    >>> extraire_noms_variables(
    ...     r'\xintdefiivar a := 5; \xintdefiivar b := a + 1;')
    ['a', 'b']
    """
    noms = []
    vus = set()
    for m in _RE_DECLARATION.finditer(bloc_variables or ''):
        nom = m.group(1)
        if nom not in vus:
            vus.add(nom)
            noms.append(nom)
    return noms


def suffixer_noms(texte: str, noms: list[str], suffixe: str) -> str:
    r"""Renomme chaque nom de `noms` en `nom_suffixe` dans `texte`,
    en substitution « mot entier ».

    Un nom de variable xint est délimité par des caractères hors
    `[A-Za-z0-9_]`. On exclut donc ces caractères en lookbehind et
    lookahead, ce qui empêche par exemple de transformer `prix` quand on
    substitue `p`.

    Les noms sont traités du plus long au plus court (ceinture +
    bretelles : la regex mot-entier suffit déjà, mais l'ordre évite tout
    recouvrement pathologique).

    Exemple
    -------
    >>> suffixer_noms(r'$\xinttheiiexpr p\relax$ et prix',
    ...               ['p', 'prix'], '07')
    '$\\xinttheiiexpr p_07\\relax$ et prix_07'
    """
    out = texte
    for nom in sorted(noms, key=len, reverse=True):
        pat = re.compile(
            r'(?<![A-Za-z0-9_])' + re.escape(nom) + r'(?![A-Za-z0-9_])'
        )
        out = pat.sub(nom + '_' + suffixe, out)
    return out


def suffixe_cellule(i: int) -> str:
    """Suffixe de cellule, zéro-padé sur 2 chiffres (01..16).

    Le format décimal zéro-padé est compatible xint (vérifié : un nom de
    variable peut contenir des chiffres tant qu'il ne commence pas par un
    chiffre ; ici le nom de base commence toujours par une lettre, donc
    `nom_01` est valide).
    """
    return f'{i:02d}'
