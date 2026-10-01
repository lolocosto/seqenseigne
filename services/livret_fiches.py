r"""
services/livret_fiches.py — v0.13.6.5.2

Génération du Livret de fiches de résumé d'un niveau.

Produit le source LaTeX d'un livret agrégeant **toutes les fiches de
résumé d'un niveau**, organisé par thème → séquence.

API
---
generer_livret_fiches(conn, niveau, options, ...) -> str
    Retourne le source .tex complet (documentclass + préambule + document).

Options reconnues (depuis le catalogue v0.13.6.4)
-------------------------------------------------
- `version_fiches` : 'completes' | 'a_completer'
    - 'a_completer' (défaut) : les \acompleter{...} apparaissent comme des
      trous soulignés (version élève à imprimer et compléter).
    - 'completes' : on redéfinit \acompleter pour qu'il affiche la valeur
      en clair (version prof, fiches complètes utilisables comme antisèche).

Architecture
------------
Pattern strictement aligné sur services/livret_recap_cours.py :
  - charger_atome(conn, 'fiche', id) pour chaque fiche
  - generer_corps_fiche pour produire le bloc seqBoiteContenuFlashcard
  - extraire_utilisations / detecter_paquets_tex_manquants pour le préambule
  - structure thème → séquence avec page de garde et table des matières
"""
from __future__ import annotations

import sqlite3

from services.latex_rendu_atome import (
    Atome,
    charger_atome,
    detecter_options_paquet,
    detecter_paquets_tex_manquants,
    resoudre_macros_csv,
    generer_corps_fiche,
)
from services.preambule_atome import construire_preambule
from services.paquet_parseur import extraire_utilisations
from services.param_niveaux import lire_cycle


# ── Constantes ───────────────────────────────────────────────────────────────

# Libellés LaTeX des niveaux (page de garde) : constante unique (v0.41.3).
from services.param_niveaux import LIBELLES_NIVEAUX_LATEX as LIBELLES_NIVEAUX  # noqa: E402


# ── Récupération de la structure ─────────────────────────────────────────────

# v0.15.5 — `_cycle_du_niveau` local supprimé. Le cycle d'un niveau se lit
# désormais via `services.param_niveaux.lire_cycle`, source unique de vérité
# (table `param_niveaux`). L'ancienne jointure `sequences_par_niveau ×
# sequences_du_cycle` + `LIMIT 1` SANS filtre cycle remontait C03 pour
# N10/N12 quand un code de séquence existe en C03 et C04.
# Cf. test_v0_15_5_cycle_du_niveau.


def _lire_themes_du_cycle(conn: sqlite3.Connection,
                           cycle_code: str) -> list[dict]:
    cur = conn.execute("""
        SELECT id, code, nom, description, code_couleur, ordre
          FROM themes
         WHERE cycle_code = ?
         ORDER BY ordre
    """, (cycle_code,))
    return [dict(r) for r in cur.fetchall()]


def _lire_sequences_du_theme(conn: sqlite3.Connection,
                              theme_id: str) -> list[dict]:
    cur = conn.execute("""
        SELECT code, numero, nom
          FROM sequences_du_cycle
         WHERE theme_id = ?
         ORDER BY numero
    """, (theme_id,))
    return [dict(r) for r in cur.fetchall()]


def _lire_fiches_de_sequence(conn: sqlite3.Connection,
                               niveau: str, sequence: str) -> list[dict]:
    """Fiches du couple (niveau, séquence), par id (les fiches n'ont pas
    de num_xxx, donc ordre déterministe par id).
    """
    cur = conn.execute("""
        SELECT id FROM fiches_resume
         WHERE niveau = ? AND sequence = ?
         ORDER BY id
    """, (niveau, sequence))
    return [{'id': r['id']} for r in cur.fetchall()]


# ── Génération principale ────────────────────────────────────────────────────

def generer_livret_fiches(conn: sqlite3.Connection,
                            niveau: str,
                            options: dict | None = None,
                            tikz_libraries: list[str] | None = None,
                            tblr_libraries: list[str] | None = None) -> str:
    """Génère le source .tex complet du livret de fiches de résumé.

    Parameters
    ----------
    conn : sqlite3.Connection
    niveau : str
        Code de niveau ('N09', 'N10', 'N11', 'N12').
    options : dict, optional
        Format plat du catalogue v0.13.6.4. Clés reconnues :
          - `version_fiches` ∈ {'completes', 'a_completer'} (défaut: 'a_completer')
    tikz_libraries, tblr_libraries : voir construire_preambule.
    """
    options = options or {}
    version_fiches = options.get('version_fiches', 'a_completer')

    # 1. Récupérer la structure thèmes → séquences → fiches
    cycle_code = lire_cycle(conn, niveau)
    themes = _lire_themes_du_cycle(conn, cycle_code)

    structure = []   # [{theme, sequences:[{sequence, fiches_corps}]}]
    tous_textes_atomes = []

    for theme in themes:
        sequences = _lire_sequences_du_theme(conn, theme['id'])
        seqs_avec_fiches = []
        for seq in sequences:
            fiches_ids = _lire_fiches_de_sequence(conn, niveau, seq['code'])
            fiches_corps = []
            for f in fiches_ids:
                atome = charger_atome(conn, 'fiche', f['id'])
                atome.corps = resoudre_macros_csv(
                    conn, atome.corps, atome.niveau, atome.sequence)
                tex = generer_corps_fiche(atome)
                fiches_corps.append(tex)
                tous_textes_atomes.append(
                    (atome.corps or '') + (atome.variables or '') + tex)
            if fiches_corps:
                seqs_avec_fiches.append({
                    'sequence': seq,
                    'fiches':   fiches_corps,
                })
        if seqs_avec_fiches:
            structure.append({'theme': theme, 'sequences': seqs_avec_fiches})

    # 2. Construire le préambule sur mesure.
    texte_global = '\n'.join(tous_textes_atomes)
    macros_utilisees, envs_utilises = extraire_utilisations(texte_global)
    atome_global = Atome(
        id='_livret_fiches_',
        type_atome='fiche',
        niveau=niveau,
        sequence='',
        fichier='',
        corps=texte_global,
    )
    options_paq = detecter_options_paquet(conn, atome_global)
    paquets_manquants = detecter_paquets_tex_manquants(conn, atome_global)

    preambule = construire_preambule(
        conn, 'fiche',
        macros_utilisees, envs_utilises,
        options_atome=options_paq,
        paquets_tex_supplementaires=paquets_manquants,
        tikz_libraries=tikz_libraries,
        tblr_libraries=tblr_libraries,
    )

    # 3. Assemblage du .tex
    L: list[str] = []
    L.append(r'%% Livret de fiches de résumé — généré pour rendu agrégé.')
    L.append(f'%% Niveau : {niveau}')
    L.append(f'%% Version : {version_fiches}')
    L.append('')
    L.append(r'\documentclass[a4paper,11pt,twoside]{article}')
    L.append('')
    L.append(preambule.texte)
    L.append('')
    # Paquets supplémentaires
    L.append(r'\usepackage{titlesec}')
    L.append(r'\usepackage{fancyhdr}')
    L.append(r'\usepackage{lastpage}')
    L.append('')
    L.append(r'\geometry{vmargin=70pt,hmargin=50pt,headheight=50pt,'
             r'headsep=15pt,footskip=20pt}')
    L.append('')
    # En-têtes
    L.append(r'\pagestyle{fancy}')
    L.append(r'\fancyhf{}')
    L.append(r'\lhead{\leftmark}')
    L.append(r'\rhead{\rightmark}')
    L.append(r'\rfoot{Page \thepage/\pageref{LastPage}}')
    L.append(r'\lfoot{Le \today}')
    L.append(r'\renewcommand{\sectionmark}[1]{\markboth{#1}{}}')
    L.append(r'\renewcommand{\subsectionmark}[1]{\markright{#1}}')
    L.append(r'\renewcommand{\headrulewidth}{0.4pt}')
    L.append(r'\renewcommand{\footrulewidth}{0pt}')
    L.append('')
    # Format des titres (aligné sur recap_cours)
    L.append(
        r'\titleformat{\section}[frame]{\normalfont}'
        r'{\filright\footnotesize\enspace SECTION \thesection\enspace}'
        r'{30pt}{\huge\bfseries\filcenter}')
    L.append(
        r'\titleformat{\subsection}[block]{\normalfont\sffamily}'
        r'{\thesubsection}{.5em}'
        r'{\titlerule[2pt]\\[1em]\bfseries\sc\Large\filcenter}'
        r'[\vspace{2ex}\titlerule]')
    L.append('')
    L.append(r'\setcounter{tocdepth}{2}')
    L.append('')
    L.append(r'\begin{document}')
    L.append('')
    L.append(r'\providecommand{\theHExoNum}{\theExoNum}')
    L.append(r'\providecommand{\theHNotionNum}{\theNotionNum}')
    L.append(r'\providecommand{\theHMethodeNum}{\theMethodeNum}')
    L.append('')
    L.append(r'\seqCreeCompteurs')
    L.append(r'\seqSetCodeNiveau{' + niveau + '}')
    L.append('')

    # Mode prof : redéfinir \acompleter pour qu'il affiche la valeur.
    # Le défaut (élève) est un trait souligné, posé par preambule_atome.
    if version_fiches == 'completes':
        L.append(r"%% Mode prof : \acompleter affiche la valeur en clair.")
        L.append(r"\renewcommand{\acompleter}[1]{#1}")
        L.append('')

    # 4. Page de garde
    L.extend(_page_de_garde(niveau, structure, version_fiches))

    # 5. Table des matières
    L.append(r'\thispagestyle{empty}')
    L.append(r'\tableofcontents')
    L.append(r'\newpage')
    L.append('')

    # 6. Pour chaque thème, section avec sous-sections par séquence.
    for bloc in structure:
        theme = bloc['theme']
        L.append(r'\cleardoublepage')
        L.append(f"\\seqSetColorsTheme{{{theme['code_couleur']}}}")
        L.append(f"\\section{{{_echapper(theme['nom'])}}}")
        if theme.get('description'):
            L.append(theme['description'])
        L.append('')

        for sb in bloc['sequences']:
            seq = sb['sequence']
            L.append(f"\\seqSetCodeSequence{{{seq['code']}}}")
            L.append(f"\\subsection{{{_echapper(seq['nom'])}}}")
            L.append('')
            for tex in sb['fiches']:
                L.append(tex)
                L.append('')

    L.append(r'\end{document}')
    return '\n'.join(L)


# ── Page de garde ────────────────────────────────────────────────────────────

def _page_de_garde(niveau: str, structure: list[dict],
                    version_fiches: str) -> list[str]:
    libelle_niveau = LIBELLES_NIVEAUX.get(niveau, niveau)
    sous_titre = ('Version complète' if version_fiches == 'completes'
                  else 'À compléter')
    L = [r'\thispagestyle{empty}']
    L.append(r'\begin{center}')
    L.append(r'\vspace*{2em}')
    L.append(r'{\Huge\bfseries Livret de fiches de résumé}\\[2em]')
    L.append(r'{\Large Collège}\\[1em]')
    L.append(rf'{{\LARGE Classe de {libelle_niveau}}}\\[1em]')
    L.append(rf'{{\large \emph{{{sous_titre}}}}}\\[3em]')
    L.append(r'\end{center}')
    L.append('')
    # Liste des séquences
    if structure:
        L.append(r'\begin{itemize}')
        for bloc in structure:
            for sb in bloc['sequences']:
                seq = sb['sequence']
                L.append(f"  \\item {_echapper(seq['nom'])}")
        L.append(r'\end{itemize}')
        L.append('')
    L.append(r'\newpage')
    L.append('')
    return L


# ── Utilitaires ──────────────────────────────────────────────────────────────

def _echapper(texte: str) -> str:
    """Échappement minimal pour titre LaTeX (aligné sur recap_cours)."""
    return texte or ''
