r"""services/render_carte_centralise.py — v0.15.2.2

Module central de rendu d'une carte d'automatisme selon son contexte
d'utilisation. Cf. cadrage v0.15.2 (option C1) : un seul point de vérité
pour le rendu d'une carte, peu importe le document englobant (atelier
isolé, récap, planche).

Refonte v0.15.2.2
-----------------
La nouvelle API LaTeX (paquet seqenseigne-carte-automatisme v0.15.2.2)
unifie fixe et paramétré :

- `\seqCarteAutomatisme[opts]{recto}{verso}` — atelier isolé.
- environnement `seqCarteRecap` + `\seqCarteRecapAjouteCarte[opts]{vars}{recto}{verso}`
  — récap (variables, recto, verso tous écrits via flux séparés).
- `\seqCartePlanche[opts]{vars}{recto}{verso}` — planche (vars vide pour
  carte fixe, peuplé pour carte paramétrée). Une seule macro pour les deux.

Toutes les variables xint sont évaluées par xintexpr côté LaTeX (plus
de substitution Python, cf. cadrage P1=alpha). Le partage des valeurs
entre recto et verso est garanti par les flux d'écriture côté .dtx
(fichiers auxiliaires `recaprecto.tex`/`recapverso.tex` pour le récap,
`plancherecto.tex`/`plancheverso.tex` pour la planche), pas par
substitution Python.

API
---
Trois fonctions wrapper, une par contexte :

- `rendre_carte_isole(conn, carte)` : retourne `{corps}` pour l'atelier
  de prévisualisation d'une carte (utilise `\seqCarteAutomatisme`).
  Le préambule du document doit appeler `\seqInitCartes` après
  `\begin{document}` (responsabilité de l'appelant).
- `rendre_carte_recap(conn, carte, fin_ligne)` : retourne `{appel}` à
  insérer dans un environnement `seqCarteRecap`. `fin_ligne=True` pour
  la 4e carte de chaque ligne, `False` sinon.
- `rendre_carte_planche(conn, carte)` : retourne `{appel}` = un appel
  à `\seqCartePlanche` (vars vide si fixe, peuplé si paramétré).

Utilitaires partagés (`resoudre_code_couleur`, `resoudre_libelle_type_pedago`,
`_echapper_valeur_option`) sont définis ici et utilisés par les wrappers
ainsi que par render_carte.py (rétrocompatibilité).
"""
from __future__ import annotations
import sqlite3

from services.planche_suffixation import (
    extraire_noms_variables,
    suffixer_noms,
    suffixe_cellule,
)


# ── Constantes ──────────────────────────────────────────────────────────────

LIBELLE_TYPE_PEDAGO = {
    'definition':     'Définition',
    'propriete':      'Propriété',
    'reconnaissance': 'Reconnaissance',
    'calcul':         'Calcul',
    'procedure':      'Procédure',
}

CODE_COULEUR_DEFAUT = 'nombres'


# ── Lookups BDD ─────────────────────────────────────────────────────────────

def resoudre_code_couleur(conn: sqlite3.Connection,
                          niveau: str,
                          sequence: str) -> str:
    r"""Renvoie le code_couleur symbolique du thème de la séquence.

    Pipeline JOIN :
      param_niveaux (niveau → cycle_code)
      → sequences_du_cycle (cycle_code + code → theme_id)
      → themes (id → code_couleur)

    Retourne `CODE_COULEUR_DEFAUT` si la séquence est introuvable ou
    si son thème n'a pas de code_couleur.
    """
    row = conn.execute("""
        SELECT t.code_couleur
        FROM param_niveaux pn
        JOIN sequences_du_cycle sdc
             ON sdc.cycle_code = pn.cycle_code
            AND sdc.code = ?
        LEFT JOIN themes t
             ON t.id = sdc.theme_id
        WHERE pn.code = ?
        LIMIT 1
    """, (sequence, niveau)).fetchone()
    if not row or not row[0]:
        return CODE_COULEUR_DEFAUT
    valeur = (row[0] if isinstance(row, tuple) else row['code_couleur']) \
             if hasattr(row, 'keys') else row[0]
    valeur = (valeur or '').strip()
    return valeur or CODE_COULEUR_DEFAUT


def resoudre_libelle_type_pedago(type_pedago: str) -> str:
    """Renvoie le libellé en clair pour un code de type pédagogique."""
    return LIBELLE_TYPE_PEDAGO.get(
        type_pedago,
        (type_pedago or '').capitalize() or 'Carte',
    )


# ── Échappement xkeyval ─────────────────────────────────────────────────────

def _echapper_valeur_option(valeur: str) -> str:
    """Échappe une valeur pour option clé=valeur xkeyval (accolades systématiques)."""
    return '{' + str(valeur) + '}'


# ── Helpers internes ────────────────────────────────────────────────────────

def _variables_xint(carte: dict) -> str:
    r"""Renvoie le bloc \xintdef*var de la carte, ou '' si la carte est
    fixe ou n'a pas de variables.

    Le contenu du champ `variables` est inséré littéralement (pas
    d'échappement, pas de modification) : c'est du LaTeX brut destiné
    au bloc `#2` de `\seqCarteRecapAjouteCarte` ou `\seqCartePlanche`.
    """
    if carte.get('type_tech') == 'parametree':
        v = (carte.get('variables') or '').strip()
        if v:
            return v
    return ''


def _options_communes(carte: dict, *, code_couleur: str,
                       libelle_type: str | None = None) -> list[str]:
    """Construit la liste d'options communes à toutes les macros publiques :
    niveau, sequence, num, typepedagolibelle, codecouleur.
    """
    libelle = libelle_type if libelle_type is not None \
              else resoudre_libelle_type_pedago(carte.get('type_pedago', ''))
    return [
        f"niveau={carte['niveau']}",
        f"sequence={carte['sequence']}",
        f"num={carte['num']}",
        f"typepedagolibelle={_echapper_valeur_option(libelle)}",
        f"codecouleur={_echapper_valeur_option(code_couleur)}",
    ]


# ── Fonction wrapper : ISOLÉ (atelier de prévisualisation) ────────────────

def rendre_carte_isole(conn: sqlite3.Connection, carte: dict) -> dict:
    r"""Rend une carte pour le contexte « atelier isolé » (prévisualisation).

    Utilise `\seqCarteAutomatisme` qui place recto et verso côte à côte
    sur une seule page d'aperçu. L'appelant est responsable d'avoir
    appelé `\seqInitCartes` après `\begin{document}` (cette fonction ne
    l'émet pas, pour permettre plusieurs cartes dans un même document).

    Pour une carte paramétrée, les variables sont placées dans un groupe
    `{...}` englobant l'appel, pour que les `\xintdefiivar` ne fuient pas
    et que recto/verso partagent le même tirage.

    Returns
    -------
    dict
        - 'corps' : str — code LaTeX prêt à mettre dans le \begin{document},
          incluant éventuellement le groupe pour les variables.
    """
    code_couleur = resoudre_code_couleur(conn, carte['niveau'],
                                          carte['sequence'])
    libelle_type = resoudre_libelle_type_pedago(carte.get('type_pedago', ''))

    opts = _options_communes(carte, code_couleur=code_couleur,
                              libelle_type=libelle_type)
    if carte.get('titre'):
        opts.append(f"nom={_echapper_valeur_option(carte['titre'])}")
    options_str = ', '.join(opts)

    appel = (
        f'\\seqCarteAutomatisme[{options_str}]\n'
        f'{{{carte["recto"]}}}\n'
        f'{{{carte["verso"]}}}\n'
    )

    variables = _variables_xint(carte)
    if variables:
        corps = (
            '{%\n'
            + variables + '%\n'
            + appel
            + '}\n'
        )
    else:
        corps = appel

    return {'corps': corps}


# ── Fonction wrapper : RÉCAP ──────────────────────────────────────────────

def rendre_carte_recap(conn: sqlite3.Connection,
                        carte: dict,
                        *,
                        fin_ligne: bool = False) -> dict:
    r"""Rend une carte pour le contexte « récap » (à l'intérieur d'un
    environnement `seqCarteRecap`).

    Émet 1 appel `\seqCarteRecapAjouteCarte[opts]{vars}{recto}{verso}`.
    La macro côté `.dtx` écrit recto et verso dans 2 flux séparés
    (`recaprecto.tex`/`recapverso.tex`) pour produire 2 pages distinctes,
    avec partage automatique des valeurs paramétrées entre les deux.

    Parameters
    ----------
    carte : dict
        Carte avec champs niveau, sequence, num, type_pedago, type_tech,
        recto, verso, variables, titre.
    fin_ligne : bool, défaut False
        Si True, ajoute l'option `finLigne=oui` : la macro insère `\\`
        après cette carte (fin de rang dans le tblr 4 colonnes).

    Returns
    -------
    dict
        - 'appel' : str — `\seqCarteRecapAjouteCarte[opts]{vars}{recto}{verso}`
    """
    code_couleur = resoudre_code_couleur(conn, carte['niveau'],
                                          carte['sequence'])

    opts = _options_communes(carte, code_couleur=code_couleur)
    if fin_ligne:
        opts.append('finLigne=oui')
    options_str = ', '.join(opts)

    variables = _variables_xint(carte)

    appel = (
        f'\\seqCarteRecapAjouteCarte[{options_str}]'
        f'{{{variables}}}'
        f'{{{carte["recto"]}}}'
        f'{{{carte["verso"]}}}'
    )

    return {'appel': appel}


# ── Fonction wrapper : LIGNE de RÉCAP (v0.32.4 — recto/verso aligné) ──────────

_POS = ['Un', 'Deux', 'Trois', 'Quatre']


def _nom_macro_recap(idx_ligne: int, pos: str, rv: str) -> str:
    r"""Nom de macro LaTeX unique pour un recto/verso d'une ligne de récap.
    rv ∈ {'R','V'}. Ex. \seqRecapLineTroisRU pour la ligne 3, position Un, recto.
    Uniquement des lettres (contrainte des noms de macro TeX)."""
    lettres = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    # idx en base 26 alphabétique pour rester un nom de commande valide.
    n = idx_ligne
    suf = ""
    while True:
        suf = lettres[n % 26] + suf
        n //= 26
        if n == 0:
            break
    return f"\\seqRecapL{suf}{pos}{rv}"


def rendre_ligne_recap(conn: sqlite3.Connection, cartes: list,
                       idx_ligne: int = 0) -> dict:
    r"""Rend une LIGNE de 1 à 4 cartes pour le récap enseignant, via la macro
    `\seqCarteRecapAjouteLigneCartes` : les 4 rectos dans l'ordre, les 4 versos
    en miroir, pour un recto-verso « bord court » aligné.

    Le contenu recto/verso peut contenir des `\par` (texte riche). Comme les
    clés xkeyval `recto*/verso*` sont lues par `\setkeys` de façon non-`\long`,
    on ne passe PAS le contenu brut en option : on le définit d'abord dans une
    macro `\long\def` (dans le bloc variables #2, exécuté au début de la macro),
    puis on passe le NOM de cette macro en option (`rectoUn=\seqRecapL...`). Le
    nom ne contient pas de `\par`, donc `\setkeys` ne casse pas ; le flux écrit
    `\unexpanded{<nom>}` et le contenu est développé à la relecture.

    Les noms de macro sont UNIQUES par ligne (idx_ligne) : sinon la relecture
    différée du flux prendrait la dernière définition pour toutes les lignes.

    Options particularisées par carte : sequence, num, typepedagolibelle,
    codecouleur (courtes, passées directement) ; recto/verso via macro nommée.
    Seul `niveau` est commun. Une ligne < 4 cartes complète par du vide.
    """
    if not cartes:
        return {'appel': ''}
    niveau = cartes[0]['niveau']
    opts = [f"niveau={niveau}"]
    defs_macros = []       # \long\def des recto/verso (bloc #2)
    variables_blocs = []   # variables xint des cartes paramétrées (bloc #2)

    for i in range(4):
        pos = _POS[i]
        if i < len(cartes):
            c = cartes[i]
            code_couleur = resoudre_code_couleur(conn, c['niveau'], c['sequence'])
            libelle = resoudre_libelle_type_pedago(c.get('type_pedago', ''))
            opts.append(f"sequence{pos}={c['sequence']}")
            opts.append(f"num{pos}={c['num']}")
            opts.append(f"typepedagolibelle{pos}={_echapper_valeur_option(libelle)}")
            opts.append(f"codecouleur{pos}={_echapper_valeur_option(code_couleur)}")
            recto_txt, verso_txt = c['recto'], c['verso']
            v = _variables_xint(c)
            if v:
                variables_blocs.append(v)
        else:
            # Position vide : num doit rester un nombre valide (0), sinon
            # \seqCarteRecto/\seqCarteVerso lève « Missing number ». Le contenu
            # recto/verso vide (macros vides) rend la cellule visuellement vide.
            opts.append(f"sequence{pos}={cartes[0]['sequence']}")
            opts.append(f"num{pos}=0")
            opts.append(f"typepedagolibelle{pos}={{}}")
            opts.append(f"codecouleur{pos}={{nombres}}")
            recto_txt, verso_txt = '', ''
        # recto/verso via macro \long\def (contourne le \par dans \setkeys).
        nom_r = _nom_macro_recap(idx_ligne, pos, 'R')
        nom_v = _nom_macro_recap(idx_ligne, pos, 'V')
        defs_macros.append(f'\\long\\def{nom_r}{{{recto_txt}}}')
        defs_macros.append(f'\\long\\def{nom_v}{{{verso_txt}}}')
        opts.append(f"recto{pos}={nom_r}")
        opts.append(f"verso{pos}={nom_v}")

    options_str = ', '.join(opts)
    # Bloc #2 : d'abord les \long\def, puis les variables xint.
    bloc2 = '%\n'.join(defs_macros + variables_blocs)
    appel = (
        f'\\seqCarteRecapAjouteLigneCartes[{options_str}]'
        f'{{{bloc2}}}'
    )
    return {'appel': appel}

PLANCHE_NB_CELLULES = 16


def rendre_carte_planche(conn: sqlite3.Connection,
                          carte: dict) -> dict:
    r"""Rend une carte pour le contexte « planche élève » (16 copies
    indépendantes recto + 16 versos correspondants).

    Stratégie « pré-tirage suffixé » (v0.15.2.3)
    --------------------------------------------
    Pour éviter le `\edef` aveugle (qui expanse et casse les macros
    fragiles `\degre`, `\seqFrac`, l'environnement `seqColEnum`, ...), on
    découple tirage et composition :

      - `#2` : 16 blocs de tirage, un par cellule, où chaque variable est
        renommée `nom_01`..`nom_16`. Ces tirages sont écrits dans
        `tirages.tex` (côté .dtx) et `\input` AVANT les planches.
      - `#3`/`#4` : 16 marqueurs `\seqCelluleRecto{...}` /
        `\seqCelluleVerso{...}`, dont le contenu référence `nom_NN`. Ce
        contenu est écrit en `\unexpanded` (côté .dtx) : aucune macro
        fragile n'est jamais expansée. Plus aucun `\robustify` requis.

    Carte FIXE (pas de variables) : `#2` est vide, et les 16 cellules
    sont des copies identiques du contenu d'origine (sans suffixe).

    Interface .dtx (v0.15.2.3)
    --------------------------
    `\seqCartePlanche[opts]{tirages}{16×\seqCelluleRecto}{16×\seqCelluleVerso}`
    Le .dtx gère la grille 4×4 (séparateurs & / \\), les flux et les
    `\input`. Python fournit exactement 16 cellules à plat.

    Returns
    -------
    dict
        - 'appel' : str — l'appel complet `\seqCartePlanche[...]{...}{...}{...}`
    """
    code_couleur = resoudre_code_couleur(conn, carte['niveau'],
                                          carte['sequence'])
    opts = _options_communes(carte, code_couleur=code_couleur)
    options_str = ', '.join(opts)

    variables = _variables_xint(carte)
    recto = carte['recto'] or ''
    verso = carte['verso'] or ''

    if variables:
        # Carte PARAMÉTRÉE : suffixer pour chaque cellule.
        noms = extraire_noms_variables(variables)
        blocs_tirage = []
        cellules_recto = []
        cellules_verso = []
        for i in range(1, PLANCHE_NB_CELLULES + 1):
            sfx = suffixe_cellule(i)
            blocs_tirage.append(suffixer_noms(variables, noms, sfx))
            r_i = suffixer_noms(recto, noms, sfx)
            v_i = suffixer_noms(verso, noms, sfx)
            cellules_recto.append(f'\\seqCelluleRecto{{{r_i}}}')
            cellules_verso.append(f'\\seqCelluleVerso{{{v_i}}}')
        bloc_tirages = '\n'.join(blocs_tirage)
    else:
        # Carte FIXE : pas de tirage, 16 copies identiques.
        bloc_tirages = ''
        cellules_recto = [f'\\seqCelluleRecto{{{recto}}}'
                          for _ in range(PLANCHE_NB_CELLULES)]
        cellules_verso = [f'\\seqCelluleVerso{{{verso}}}'
                          for _ in range(PLANCHE_NB_CELLULES)]

    bloc_recto = '\n'.join(cellules_recto)
    bloc_verso = '\n'.join(cellules_verso)

    appel = (
        f'\\seqCartePlanche[{options_str}]\n'
        f'{{{bloc_tirages}}}\n'
        f'{{{bloc_recto}}}\n'
        f'{{{bloc_verso}}}\n'
    )

    return {'appel': appel}
