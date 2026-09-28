r"""
services/livret_corriges.py — v0.13.6.5.2

Génération du Livret de corrigés d'exercices d'un niveau.

Livret enseignant qui ne contient que les **corrigés** (champ `corrige`
de la table exercices), organisés par séquence × série.

API
---
generer_livret_corriges(conn, niveau, options, ...) -> str

Options reconnues (depuis le catalogue v0.13.6.4)
-------------------------------------------------
- `inclure_serie_r_ae` : bool (défaut True)
- `inclure_serie_f`    : bool (défaut True)
- `inclure_serie_a`    : bool (défaut False)
- `inclure_serie_e`    : bool (défaut False)

Mapping vers les codes de série en BDD :
- inclure_serie_r_ae → serie_code IN ('R', 'AE')
- inclure_serie_f    → serie_code = 'F'
- inclure_serie_a    → serie_code = 'A'
- inclure_serie_e    → serie_code = 'E'

Architecture
------------
- Lecture directe du champ `corrige` (pas de passage par la machinerie
  \seqAfficheCorriges du paquet, qui nécessite la phase d'émission des
  énoncés). Approche simple et lisible.
- Structure : thème → séquence → série → exos numérotés.
- Construction du préambule via construire_preambule (comme recap_cours),
  basée sur l'analyse des macros utilisées dans les champs `corrige`.
"""
from __future__ import annotations

import sqlite3

from services.latex_rendu_atome import (
    Atome,
    detecter_options_paquet,
    detecter_paquets_tex_manquants,
    resoudre_macros_csv,
)
from services.preambule_atome import construire_preambule
from services.paquet_parseur import extraire_utilisations
from services.param_niveaux import lire_cycle


LIBELLES_NIVEAUX = {
    'N09': '6\\ieme{}',
    'N10': '5\\ieme{}',
    'N11': '4\\ieme{}',
    'N12': '3\\ieme{}',
}

# Ordre canonique des séries pour l'affichage : R/AE en premier
# (révisions), puis F (formation), A (entre F et E), E (entraînement).
ORDRE_SERIES = ['R', 'AE', 'F', 'A', 'E']

# Libellés affichés par série dans le livret
LIBELLES_SERIES = {
    'R':  'Révisions',
    'AE': 'Révisions / activités d\'entrée',
    'F':  'Série F (formation)',
    'A':  'Série A',
    'E':  'Série E (entraînement)',
}


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


def _series_a_inclure(options: dict) -> list[str]:
    """Liste des codes de série à inclure, dans l'ordre canonique.

    Mapping :
      inclure_serie_r_ae → 'R', 'AE'
      inclure_serie_f    → 'F'
      inclure_serie_a    → 'A'
      inclure_serie_e    → 'E'
    """
    series: list[str] = []
    if options.get('inclure_serie_r_ae', True):
        series.extend(['R', 'AE'])
    if options.get('inclure_serie_f', True):
        series.append('F')
    if options.get('inclure_serie_a', False):
        series.append('A')
    if options.get('inclure_serie_e', False):
        series.append('E')
    # Tri canonique
    return [s for s in ORDRE_SERIES if s in series]


def _lire_exos_corriges(conn: sqlite3.Connection,
                         niveau: str, sequence: str,
                         serie_code: str) -> list[dict]:
    """Lit les exos avec leur corrigé pour (niveau, séquence, série),
    triés par num croissant.

    v0.13.6.5.2.1 — Récupère aussi le champ `variables` qui contient
    les définitions xint (\\xintdefiivar ...). Ces définitions doivent
    être émises au top du document avant les `\\xintiieval{...}` qui les
    utilisent dans les corrigés.

    Ne retourne que les exos dont `corrige` est non vide (un exo sans
    corrigé serait incohérent pour ce livret).
    """
    cur = conn.execute("""
        SELECT id, num, corrige, variables
          FROM exercices
         WHERE niveau = ? AND sequence = ? AND serie_code = ?
           AND corrige IS NOT NULL AND TRIM(corrige) <> ''
         ORDER BY CAST(num AS INTEGER)
    """, (niveau, sequence, serie_code))
    return [dict(r) for r in cur.fetchall()]


# ── Génération principale ────────────────────────────────────────────────────

def generer_livret_corriges(conn: sqlite3.Connection,
                              niveau: str,
                              options: dict | None = None,
                              tikz_libraries: list[str] | None = None,
                              tblr_libraries: list[str] | None = None) -> str:
    """Génère le source .tex complet du livret de corrigés.

    Parameters
    ----------
    conn : sqlite3.Connection
    niveau : str
        Code de niveau ('N09', 'N10', 'N11', 'N12').
    options : dict, optional
        Format plat du catalogue v0.13.6.4. Clés reconnues :
          - inclure_serie_r_ae (défaut True)
          - inclure_serie_f    (défaut True)
          - inclure_serie_a    (défaut False)
          - inclure_serie_e    (défaut False)
    tikz_libraries, tblr_libraries : voir construire_preambule.
    """
    options = options or {}
    series_inclues = _series_a_inclure(options)

    # 1. Récupérer la structure thèmes → séquences → série → corrigés.
    cycle_code = lire_cycle(conn, niveau)
    themes = _lire_themes_du_cycle(conn, cycle_code)

    structure = []   # [{theme, sequences:[{sequence, series:[{code, exos}]}]}]
    tous_textes = []  # pour le préambule

    for theme in themes:
        sequences = _lire_sequences_du_theme(conn, theme['id'])
        seqs_avec_corriges = []
        for seq in sequences:
            series_bloc = []
            for serie in series_inclues:
                exos = _lire_exos_corriges(conn, niveau, seq['code'], serie)
                if not exos:
                    continue
                # Résoudre les getters CSV dans les corrigés et
                # récupérer les définitions xint (\xintdefiivar etc.)
                # qui doivent être émises au top du document avant le
                # premier \xintiieval qui les utilise (v0.13.6.5.2.1).
                exos_resolus = []
                for ex in exos:
                    corrige_resolu = resoudre_macros_csv(
                        conn, ex['corrige'], niveau, seq['code'])
                    variables = ex.get('variables') or ''
                    exos_resolus.append({
                        'id':        ex['id'],
                        'num':       ex['num'],
                        'corrige':   corrige_resolu,
                        'variables': variables,
                    })
                    tous_textes.append(corrige_resolu)
                    # v0.15.1.1 — Inclure aussi les `variables` dans
                    # l'agrégat de textes pour que `extraire_utilisations`
                    # détecte les macros référencées par les définitions
                    # utilisateur (typiquement un `\newcommand{\myDef}{...
                    # \begin{boitePaleNoBreak}...}` qui utilise un env
                    # défini dans un paquet seqEnseigne — sans cet ajout,
                    # `boitePaleNoBreak` n'apparaît pas dans envs_utilises
                    # et n'est pas inlinée dans le préambule, ce qui fait
                    # échouer la compilation). Pattern aligné sur
                    # livret_sequence.py (lignes 898-900).
                    if variables:
                        tous_textes.append(variables)
                series_bloc.append({'code': serie, 'exos': exos_resolus})
            if series_bloc:
                seqs_avec_corriges.append({
                    'sequence': seq,
                    'series':   series_bloc,
                })
        if seqs_avec_corriges:
            structure.append({'theme': theme, 'sequences': seqs_avec_corriges})

    # 2. Construire le préambule sur mesure (analyse des macros utilisées
    #    dans les corrigés).
    texte_global = '\n'.join(tous_textes)
    macros_utilisees, envs_utilises = extraire_utilisations(texte_global)
    atome_global = Atome(
        id='_livret_corriges_',
        type_atome='exercice',  # exercice : profil de macros le plus complet
        niveau=niveau,
        sequence='',
        fichier='',
        corps=texte_global,
    )
    options_paq = detecter_options_paquet(conn, atome_global)
    paquets_manquants = detecter_paquets_tex_manquants(conn, atome_global)

    preambule = construire_preambule(
        conn, 'exercice',
        macros_utilisees, envs_utilises,
        options_atome=options_paq,
        paquets_tex_supplementaires=paquets_manquants,
        tikz_libraries=tikz_libraries,
        tblr_libraries=tblr_libraries,
    )

    # 3. Assemblage du .tex
    L: list[str] = []
    L.append(r'%% Livret de corrigés d\'exercices — généré pour rendu agrégé.')
    L.append(f'%% Niveau : {niveau}')
    series_str = ', '.join(series_inclues)
    L.append(f'%% Séries incluses : {series_str}')
    L.append('')
    L.append(r'\documentclass[a4paper,11pt,twoside]{article}')
    L.append('')
    L.append(preambule.texte)
    L.append('')
    L.append(r'\usepackage{titlesec}')
    L.append(r'\usepackage{fancyhdr}')
    L.append(r'\usepackage{lastpage}')
    L.append('')
    L.append(r'\geometry{vmargin=70pt,hmargin=50pt,headheight=50pt,'
             r'headsep=15pt,footskip=20pt}')
    L.append('')
    # En-têtes / pieds (aligné sur recap_cours)
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
    # Format des titres
    L.append(
        r'\titleformat{\section}[frame]{\normalfont}'
        r'{\filright\footnotesize\enspace SECTION \thesection\enspace}'
        r'{30pt}{\huge\bfseries\filcenter}')
    L.append(
        r'\titleformat{\subsection}[block]{\normalfont\sffamily}'
        r'{\thesubsection}{.5em}'
        r'{\titlerule[2pt]\\[1em]\bfseries\sc\Large\filcenter}'
        r'[\vspace{2ex}\titlerule]')
    L.append(
        r'\titleformat{\subsubsection}{\normalfont\bfseries}'
        r'{\thesubsubsection}{1em}{}')
    L.append('')
    L.append(r'\setcounter{tocdepth}{2}')
    L.append('')
    L.append(r'\begin{document}')
    L.append('')
    # Fallbacks pour \theHxxx (hyperref non chargé dans le préambule)
    L.append(r'\providecommand{\theHExoNum}{\theExoNum}')
    L.append('')
    L.append(r'\seqCreeCompteurs')
    L.append(r'\seqSetCodeNiveau{' + niveau + '}')
    L.append('')

    # 4. Page de garde
    L.extend(_page_de_garde(niveau, structure, series_inclues))

    # 5. Table des matières
    L.append(r'\thispagestyle{empty}')
    L.append(r'\tableofcontents')
    L.append(r'\newpage')
    L.append('')

    # 6. Pour chaque thème, section avec sous-sections par séquence,
    #    et sous-sous-sections par série.
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

            for serie_bloc in sb['series']:
                libelle = LIBELLES_SERIES.get(serie_bloc['code'],
                                               f"Série {serie_bloc['code']}")
                L.append(f"\\subsubsection{{{libelle}}}")
                L.append('')

                # v0.13.6.5.2.1 — Émettre les définitions xint
                # (\xintdefiivar ...) AVANT la liste des corrigés.
                # Sans ça, les \xintiieval{N10S01A01_numA} dans les
                # corrigés référencent des variables non définies.
                # Pattern aligné sur livret_sequence.py (l. ~1068).
                variables_emises = False
                for ex in serie_bloc['exos']:
                    if ex.get('variables'):
                        L.append(ex['variables'])
                        variables_emises = True
                if variables_emises:
                    L.append('')

                # Liste des corrigés
                L.append(r'\begin{description}')
                for ex in serie_bloc['exos']:
                    L.append(f"  \\item[Exercice {ex['num']}.]\\quad")
                    L.append(ex['corrige'])
                    L.append('')
                L.append(r'\end{description}')
                L.append('')

    L.append(r'\end{document}')
    return '\n'.join(L)


# ── Page de garde ────────────────────────────────────────────────────────────

def _page_de_garde(niveau: str, structure: list[dict],
                    series_inclues: list[str]) -> list[str]:
    libelle_niveau = LIBELLES_NIVEAUX.get(niveau, niveau)
    series_str = ', '.join(series_inclues)
    L = [r'\thispagestyle{empty}']
    L.append(r'\begin{center}')
    L.append(r'\vspace*{2em}')
    L.append(r'{\Huge\bfseries Livret de corrigés d\'exercices}\\[2em]')
    L.append(r'{\Large Collège — Document enseignant}\\[1em]')
    L.append(rf'{{\LARGE Classe de {libelle_niveau}}}\\[1em]')
    L.append(rf'{{\large \emph{{Séries : {series_str}}}}}\\[3em]')
    L.append(r'\end{center}')
    L.append('')
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
    return texte or ''
