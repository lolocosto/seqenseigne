r"""services/livret_cartes_planches.py — v0.15.2.2

Génération de Planches de cartes d'automatisme (vue élève) en A4 paysage.

Document destiné à être imprimé recto-verso (bord court, sans miroir
horizontal, cf. cadrage v0.15.2 P4) et découpé en cartes par les élèves.
Pour chaque carte du niveau :

- Page recto avec 16 copies de la même carte en grille 4×4
  (chaque copie a un tirage de paramètres indépendant pour les cartes
  paramétrées, via xintReplicate côté .dtx).
- Page verso avec les 16 réponses correspondantes (mêmes tirages que le
  recto correspondant, via les flux d'écriture du fichier auxiliaire).

Stratégie v0.15.2.3 — pré-tirage suffixé
----------------------------------------
Refonte de la génération des planches pour éliminer le `\edef` aveugle
(qui expansait et cassait les macros fragiles : `\degre`, `\seqFrac`,
l'environnement `seqColEnum`, `\,`, ...) et corriger la corruption
`@if vmode` observée. Le tirage et la composition sont découplés :

- Pour une carte paramétrée, chaque variable est tirée 16 fois et figée
  sous un nom suffixé `nom_01`..`nom_16` (un tirage par cellule). Ces 16
  blocs sont écrits dans `tirages.tex` (côté .dtx), `\input` AVANT les
  planches. Le contenu des cellules référence `nom_NN` et est écrit en
  `\unexpanded` : aucune macro fragile n'est jamais expansée. Plus aucun
  `\robustify` n'est requis pour les planches.
- Pour une carte fixe : pas de tirage, 16 cellules identiques.

La suffixation est faite côté Python (cf. `services/planche_suffixation`),
sur la base des noms RÉELLEMENT déclarés dans le champ `variables` (pas
sur une convention de nommage présumée), donc robuste quel que soit le
nommage.

Interface paquet (v0.15.2.3)
----------------------------
`\seqCartePlanche[opts]{tirages}{16×\seqCelluleRecto}{16×\seqCelluleVerso}`
Le .dtx gère la grille 4×4 (séparateurs), les flux d'écriture et les
`\input`. Python fournit exactement 16 cellules à plat.

API
---
generer_livret_cartes_planches(conn, niveau, options=None) -> str
    Retourne le source .tex complet (documentclass + préambule + document).

Préambule
---------
Identique au récap : seqenseigne-core, seqenseigne-theme,
seqenseigne-carte-automatisme (qui amènent transitivement geometry pour
A4 paysage, tcolorbox avec ses options, tabularray, xintexpr).
"""
from __future__ import annotations

import sqlite3

from services.render_carte_centralise import rendre_carte_planche


# ── Constantes ──────────────────────────────────────────────────────────────

LIBELLES_NIVEAUX = {
    'N09': '6\\ieme{}',
    'N10': '5\\ieme{}',
    'N11': '4\\ieme{}',
    'N12': '3\\ieme{}',
}

# Version du paquet attendue pour la génération de ce livret. Émise en
# commentaire en tête du .tex pour faciliter le debug.
VERSION_API_PAQUET = '2026/05/28 v0.15.2.3'


# ── Lecture des cartes du niveau ─────────────────────────────────────────────

def _lire_cartes_du_niveau(conn: sqlite3.Connection,
                            niveau: str,
                            sequence: str | None = None) -> list[dict]:
    """Lit les cartes du niveau, à l'état 'valide', triées par séquence
    puis par numéro de carte.

    Si `sequence` est fourni (ex. 'S03'), restreint aux cartes de cette
    séquence (découpage des planches par séquence, v0.15.2.4). Par défaut
    (`None`), retourne toutes les cartes du niveau (rétrocompatibilité).
    """
    if sequence is None:
        cur = conn.execute("""
            SELECT id, niveau, sequence, num, type_pedago, type_tech,
                   titre, recto, verso, variables, ordre
              FROM cartes_automatisme
             WHERE niveau = ? AND etat_code = 'valide'
             ORDER BY sequence, CAST(num AS INTEGER), ordre
        """, (niveau,))
    else:
        cur = conn.execute("""
            SELECT id, niveau, sequence, num, type_pedago, type_tech,
                   titre, recto, verso, variables, ordre
              FROM cartes_automatisme
             WHERE niveau = ? AND sequence = ? AND etat_code = 'valide'
             ORDER BY sequence, CAST(num AS INTEGER), ordre
        """, (niveau, sequence))
    return [dict(r) for r in cur.fetchall()]


# ── Préambule ───────────────────────────────────────────────────────────────

def _preambule_livret_planches() -> str:
    r"""Préambule statique pour le livret de planches.

    Identique au récap (même paquet seqenseigne-carte-automatisme, qui
    pose lui-même la géométrie A4 paysage).
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

def _page_de_garde(niveau: str, cartes: list[dict],
                   sequence: str | None = None) -> list[str]:
    libelle_niveau = LIBELLES_NIVEAUX.get(niveau, niveau)
    n = len(cartes)
    if sequence is None:
        sous_titre = rf'{{\LARGE Classe de {libelle_niveau}}}\\[3em]'
    else:
        sous_titre = (
            rf'{{\LARGE Classe de {libelle_niveau} '
            rf'\textemdash{{}} séquence {sequence}}}\\[3em]'
        )
    return [
        r'\thispagestyle{empty}',
        r'\begin{center}',
        r'\vspace*{4em}',
        r"{\Huge\bfseries Planches de cartes d'automatisme}\\[2em]",
        r'{\Large Vue élève — à imprimer recto-verso (bord court) et découper}\\[1em]',
        sous_titre,
        rf'{{\large {n} planches au total}}',
        r'\end{center}',
        r'\clearpage',
    ]


# ── Génération principale ────────────────────────────────────────────────────

def generer_livret_cartes_planches(conn: sqlite3.Connection,
                                     niveau: str,
                                     options: dict | None = None,
                                     sequence: str | None = None,
                                     tikz_libraries: list[str] | None = None,
                                     tblr_libraries: list[str] | None = None
                                     ) -> str:
    """Génère le source .tex du livret de planches pour un niveau.

    Chaque carte produit 1 planche (2 pages : 16 rectos + 16 versos).
    Pour 119 cartes, on obtient 238 pages de planches + 1 page de garde.

    Parameters
    ----------
    conn : sqlite3.Connection
    niveau : str
        Code niveau (ex. 'N10').
    options : dict | None
        Réservé pour évolutions futures (formats, filtres). Ignoré
        actuellement.
    sequence : str | None
        Code séquence (ex. 'S03'). Si fourni, ne génère que les planches
        de cette séquence (découpage par séquence, v0.15.2.4, pour rester
        sous le timeout de compilation). Par défaut (None) : toutes les
        séquences du niveau (rétrocompatibilité — cible 'unique').
    tikz_libraries, tblr_libraries : list[str] | None
        Réservés pour cohérence d'API avec les autres générateurs de
        livrets. Ignorés ici.
    """
    cartes = _lire_cartes_du_niveau(conn, niveau, sequence)
    preambule = _preambule_livret_planches()

    L: list[str] = []
    L.append(rf"%% Planches de cartes d'automatisme — vue élève.")
    L.append(f'%% Niveau : {niveau}')
    if sequence is not None:
        L.append(f'%% Séquence : {sequence} (découpage par séquence)')
    L.append(f'%% {len(cartes)} planches — 1 planche par carte (16 copies recto + 16 versos).')
    L.append(f'%% API paquet seqenseigne-carte-automatisme : {VERSION_API_PAQUET}')
    L.append('')
    L.append(preambule)
    L.append(r'\pagestyle{empty}')
    L.append('')
    L.append(r'\begin{document}')
    L.append('')
    L.append(r'\seqInitCartes')
    L.append('')
    L.extend(_page_de_garde(niveau, cartes, sequence))
    L.append('')

    if cartes:
        for carte in cartes:
            L.append(f"%% Planche {carte['niveau']}/{carte['sequence']}/CA{carte['num']:02d}")
            rendu = rendre_carte_planche(conn, carte)
            L.append(rendu['appel'])
            L.append('')
    else:
        if sequence is None:
            L.append(r'\begin{center}\textit{Aucune carte au niveau ' + niveau + r'.}\end{center}')
        else:
            L.append(r'\begin{center}\textit{Aucune carte pour ' + niveau + '/' + sequence + r'.}\end{center}')

    L.append(r'\end{document}')
    return '\n'.join(L)
