r"""services/livret_cartes_recap.py — v0.15.2.2

Génération du Récap des cartes d'automatisme d'un niveau.

Document de référence pour l'enseignant : grille 4 colonnes de recto suivie
de la grille 4 colonnes des versos correspondants. Toutes les cartes du
niveau sont placées dans un **unique** environnement `seqCarteRecap`
(option A du cadrage v0.15.2.2), triées par séquence puis numéro.

Nouvelle stratégie v0.15.2.2
----------------------------
Refonte complète sur la nouvelle API du paquet seqenseigne-carte-automatisme
v0.15.2.2 :

- Plus de substitution Python des variables paramétrées (cf. cadrage P1=alpha).
  Les variables xint sont insérées telles quelles dans le bloc `#2` de
  `\seqCarteRecapAjouteCarte` ; xintexpr évalue côté LaTeX, et le partage
  des valeurs entre recto et verso est assuré par la macro elle-même
  (qui exécute le bloc variables dans un même groupe utilisé pour les
  deux flux d'écriture `recaprecto.tex` et `recapverso.tex`).
- Plus de structure 8 cartes/page (4 rectos + 4 versos + 4 rectos + 4 versos).
  La nouvelle API écrit tous les rectos sur une suite de pages, suivie de
  tous les versos sur une suite de pages.
- Plus de groupement visuel par séquence : un seul `seqCarteRecap`.
  L'ordre interne (sequence, num) préserve toutefois la cohérence logique.

API
---
generer_livret_cartes_recap(conn, niveau, options=None) -> str
    Retourne le source .tex complet (documentclass + préambule + document).

Préambule
---------
Le préambule statique charge seqenseigne-core, seqenseigne-theme et
seqenseigne-carte-automatisme (qui amène transitivement tcolorbox,
tabularray, xintexpr, geometry). Aucune réacquisition de ces paquets
ne doit être tentée (option clash garantie).
"""
from __future__ import annotations

import sqlite3

from services.render_carte_centralise import rendre_carte_recap, rendre_ligne_recap


# ── Constantes ──────────────────────────────────────────────────────────────

# Libellés LaTeX des niveaux (page de garde) : constante unique (v0.41.3).
from services.param_niveaux import LIBELLES_NIVEAUX_LATEX as LIBELLES_NIVEAUX  # noqa: E402

# 4 colonnes dans l'environnement seqCarteRecap (cf. .dtx ligne 387 :
# `\begin{tblr}{*{4}{X[c]}}`). Position de la dernière colonne d'une
# ligne pour positionner finLigne=oui.
CARTES_PAR_LIGNE = 4

# Nombre maximum de cartes par bloc `seqCarteRecap`. Un bloc produit une
# paire de pages (recto + verso). Au-delà, le tblr de l'environnement
# déborderait sur la page suivante (la version actuelle du paquet
# `seqenseigne-carte-automatisme` ne gère pas de saut de page interne).
# Cf. v0.15.2.2 Q1 D : on émet plusieurs environnements `seqCarteRecap`
# successifs, un par bloc de 16 cartes.
# Doit être un multiple de CARTES_PAR_LIGNE.
CARTES_PAR_BLOC = 16
assert CARTES_PAR_BLOC % CARTES_PAR_LIGNE == 0

# Version du paquet attendue pour la génération de ce livret. Émise en
# commentaire en tête du .tex pour faciliter le debug (savoir quelle
# API a produit ce source).
VERSION_API_PAQUET = '2026/05/26 v0.15.2.2'


# ── Lecture des cartes du niveau ─────────────────────────────────────────────

def _lire_cartes_du_niveau(conn: sqlite3.Connection,
                            niveau: str) -> list[dict]:
    """Lit toutes les cartes du niveau, à l'état 'valide', triées
    par séquence puis par numéro de carte (puis ordre en discriminant).
    """
    cur = conn.execute("""
        SELECT id, niveau, sequence, num, type_pedago, type_tech,
               titre, recto, verso, variables, ordre
          FROM cartes_automatisme
         WHERE niveau = ? AND etat_code = 'valide'
         ORDER BY sequence, CAST(num AS INTEGER), ordre
    """, (niveau,))
    return [dict(r) for r in cur.fetchall()]


# ── Préambule ───────────────────────────────────────────────────────────────

def _preambule_livret_cartes() -> str:
    r"""Préambule statique pour le livret récap des cartes.

    Le paquet seqenseigne-carte-automatisme charge transitivement :
    - seqenseigne-core (qui charge xintexpr, tabularray)
    - seqenseigne-theme (qui charge tcolorbox avec ses options requises)
    - geometry (positionne A4 paysage)

    On ajoute siunitx (utilisé par certaines cartes pour les unités) et
    les paquets standards d'un document LaTeX en français.
    """
    return r"""\documentclass[10pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[french]{babel}
\usepackage{lmodern}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{xcolor}
\usepackage{siunitx}
\usepackage{seqenseigne-core}
\usepackage{seqenseigne-theme}
\usepackage{seqenseigne-carte-automatisme}
"""


# ── Page de garde ───────────────────────────────────────────────────────────

def _page_de_garde(niveau: str, cartes: list[dict]) -> list[str]:
    libelle_niveau = LIBELLES_NIVEAUX.get(niveau, niveau)
    n = len(cartes)
    return [
        r'\thispagestyle{empty}',
        r'\begin{center}',
        r'\vspace*{4em}',
        r"{\Huge\bfseries Récap des cartes d'automatisme}\\[2em]",
        r'{\Large Document enseignant}\\[1em]',
        rf'{{\LARGE Classe de {libelle_niveau}}}\\[3em]',
        rf'{{\large {n} cartes au total}}',
        r'\end{center}',
        r'\clearpage',
    ]


# ── Génération principale ────────────────────────────────────────────────────

def generer_livret_cartes_recap(conn: sqlite3.Connection,
                                  niveau: str,
                                  options: dict | None = None,
                                  tikz_libraries: list[str] | None = None,
                                  tblr_libraries: list[str] | None = None
                                  ) -> str:
    """Génère le source .tex du récap cartes pour un niveau.

    Toutes les cartes valides du niveau sont triées par séquence puis
    numéro (cadrage v0.15.2.2 Q1=A), puis découpées en blocs de 16 cartes
    maximum. Chaque bloc est émis dans un environnement `seqCarteRecap`
    indépendant qui produit 1 paire de pages (recto + verso). Cette
    découpe est nécessaire car le `tblr` interne de l'environnement ne
    gère pas de saut de page automatique.

    `finLigne=oui` est positionné toutes les 4 cartes pour structurer la
    grille en 4 colonnes, ainsi que sur la dernière carte de chaque bloc
    (au cas où elle ne tomberait pas sur un multiple de 4).

    Parameters
    ----------
    conn : sqlite3.Connection
    niveau : str
        Code niveau (ex. 'N10').
    options : dict | None
        Réservé pour évolutions futures (formats, filtres). Ignoré
        actuellement.
    tikz_libraries, tblr_libraries : list[str] | None
        Réservés pour cohérence d'API avec les autres générateurs de
        livrets. Ignorés ici (les cartes n'utilisent ni tikz ni tblr
        au niveau du livret englobant).
    """
    cartes = _lire_cartes_du_niveau(conn, niveau)
    preambule = _preambule_livret_cartes()

    nb_blocs = (len(cartes) + CARTES_PAR_BLOC - 1) // CARTES_PAR_BLOC

    L: list[str] = []
    L.append(rf"%% Récap des cartes d'automatisme — vue enseignant.")
    L.append(f'%% Niveau : {niveau}')
    L.append(f'%% {len(cartes)} cartes — grille 4 colonnes, '
             f'{CARTES_PAR_BLOC} cartes par paire de pages.')
    L.append(f'%% {nb_blocs} paire(s) de pages (1 paire = 1 page rectos + '
             f'1 page versos).')
    L.append(f'%% API paquet seqenseigne-carte-automatisme : {VERSION_API_PAQUET}')
    L.append('')
    L.append(preambule)
    L.append(r'\pagestyle{empty}')
    L.append('')
    L.append(r'\begin{document}')
    L.append('')
    L.append(r'\seqInitCartes')
    L.append('')
    L.extend(_page_de_garde(niveau, cartes))
    L.append('')

    if cartes:
        idx_ligne_global = 0
        for num_bloc in range(nb_blocs):
            debut = num_bloc * CARTES_PAR_BLOC
            fin = min(debut + CARTES_PAR_BLOC, len(cartes))
            cartes_du_bloc = cartes[debut:fin]
            n_bloc = len(cartes_du_bloc)

            L.append(f'%% Paire de pages {num_bloc + 1}/{nb_blocs} '
                     f'(cartes {debut + 1} à {fin})')
            L.append(r'\begin{seqCarteRecap}')
            # v0.32.4 — Une ligne = 4 cartes via seqCarteRecapAjouteLigneCartes
            # (rectos dans l'ordre, versos en miroir → recto-verso aligné).
            # idx_ligne_global assure des noms de macro recto/verso uniques.
            for k in range(0, n_bloc, CARTES_PAR_LIGNE):
                ligne = cartes_du_bloc[k:k + CARTES_PAR_LIGNE]
                rendu = rendre_ligne_recap(conn, ligne, idx_ligne=idx_ligne_global)
                L.append('  ' + rendu['appel'])
                idx_ligne_global += 1
            L.append(r'\end{seqCarteRecap}')
            L.append('')
    else:
        L.append(r'\begin{center}\textit{Aucune carte au niveau ' + niveau + r'.}\end{center}')

    L.append(r'\end{document}')
    return '\n'.join(L)
