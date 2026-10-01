r"""
services/livret_recap_cours.py — Génération du Livret de cours d'un niveau.

Produit le source LaTeX d'un livret agrégeant **toutes les notions et
méthodes d'un niveau**, organisé par thème → séquence → Connaissances /
Savoir-faire, avec une numérotation continue (Notion 1..N, Méthode 1..M).

Indépendant de Flask : prend une connexion sqlite3 et un code de niveau,
retourne une chaîne .tex prête à être compilée par pdflatex.

API
---
generer_recap_cours(conn, niveau) -> str
    Retourne le source .tex complet (documentclass + préambule + document).

Architecture
------------
On réutilise au maximum services.latex_rendu_atome :
- generer_corps_notion / generer_corps_methode pour produire le corps de
  chaque atome dans son environnement seqNotion / seqMethode habituel.
- detecter_paquets_tex_manquants + extraire_utilisations + construire_preambule
  pour bâtir un préambule sur mesure couvrant toutes les macros utilisées
  par les atomes agrégés (sinon on chargerait \\usepackage{seqenseigne}
  complet, lent à compiler).

Différences avec un rendu d'atome individuel :
- Numérotation **continue** : on supprime les \\setcounter{NotionNum}{...}
  et \\setcounter{MethodeNum}{...} émis par les générateurs de corps, pour
  laisser les compteurs s'incrémenter naturellement de Notion 1 à Notion N
  sur tout le document.
- Page de garde, table des matières, structuration en sections par thème
  et sous-sections par séquence (titre uniquement, le contenu pédagogique
  reste celui de chaque atome).
"""

from __future__ import annotations

import re
import sqlite3

from services.latex_rendu_atome import (
    Atome,
    charger_atome,
    detecter_options_paquet,
    detecter_paquets_tex_manquants,
    resoudre_theme,
    resoudre_macros_csv,
    generer_corps_notion,
    generer_corps_methode,
)
from services.preambule_atome import construire_preambule
from services.paquet_parseur import extraire_utilisations
from services.param_niveaux import lire_cycle


# ── Constantes de structure ──────────────────────────────────────────────────

# Libellés LaTeX des niveaux (page de garde) : constante unique (v0.41.3).
from services.param_niveaux import LIBELLES_NIVEAUX_LATEX as LIBELLES_NIVEAUX  # noqa: E402

# Regex pour neutraliser les setcounter émis par generer_corps_*
_RE_SETCOUNTER_NOTION = re.compile(r'\\setcounter\{NotionNum\}\{[^}]*\}\s*\n?')
_RE_SETCOUNTER_METHODE = re.compile(r'\\setcounter\{MethodeNum\}\{[^}]*\}\s*\n?')


# ── Récupération des données ─────────────────────────────────────────────────

# v0.15.5 — `_cycle_du_niveau` local supprimé. Le cycle d'un niveau se lit
# désormais via `services.param_niveaux.lire_cycle`, source unique de vérité
# (table `param_niveaux`). L'ancienne implémentation faisait une jointure
# `sequences_par_niveau × sequences_du_cycle` + `LIMIT 1` SANS filtre cycle,
# qui remontait C03 pour N10/N12 quand un code de séquence (ex. S01) existe
# à la fois en C03 et C04. Cf. test_v0_15_5_cycle_du_niveau.



def _lire_themes_du_cycle(conn: sqlite3.Connection,
                           cycle_code: str) -> list[dict]:
    """Liste les thèmes du cycle, dans l'ordre d'affichage."""
    cur = conn.execute("""
        SELECT id, code, nom, description, code_couleur, ordre
        FROM themes
        WHERE cycle_code = ?
        ORDER BY ordre
    """, (cycle_code,))
    return [dict(r) for r in cur.fetchall()]


def _lire_sequences_du_theme(conn: sqlite3.Connection,
                              theme_id: str) -> list[dict]:
    """Liste les séquences appartenant au thème (par theme_id), par numéro
    croissant."""
    cur = conn.execute("""
        SELECT code, numero, nom
        FROM sequences_du_cycle
        WHERE theme_id = ?
        ORDER BY numero
    """, (theme_id,))
    return [dict(r) for r in cur.fetchall()]


def _lire_notions_de_sequence(conn: sqlite3.Connection,
                               niveau: str, sequence: str) -> list[dict]:
    """Notions du couple (niveau, séquence), par num_connaissance croissant."""
    cur = conn.execute("""
        SELECT id FROM notions
        WHERE niveau = ? AND sequence = ?
        ORDER BY CAST(num_connaissance AS INTEGER)
    """, (niveau, sequence))
    return [{'id': r['id']} for r in cur.fetchall()]


def _lire_methodes_de_sequence(conn: sqlite3.Connection,
                                niveau: str, sequence: str) -> list[dict]:
    """Méthodes du couple (niveau, séquence), par num_methode croissant."""
    cur = conn.execute("""
        SELECT id FROM methodes
        WHERE niveau = ? AND sequence = ?
        ORDER BY CAST(num_methode AS INTEGER)
    """, (niveau, sequence))
    return [{'id': r['id']} for r in cur.fetchall()]


# ── Génération du corps d'un atome (sans setcounter de numérotation) ────────

def _generer_corps_notion_continu(atome: Atome) -> str:
    """Comme generer_corps_notion mais en supprimant le \\setcounter local.

    Permet une numérotation continue à l'échelle du livret entier au lieu
    d'un reset par séquence.

    On désactive aussi l'émission de \\seqInitAnnexes / \\seqAfficheAnnexes
    par atome : avec 100+ atomes dans un livret, chaque \\seqInitAnnexes
    appelle \\newwrite et TeX limite à 16 streams ouverts simultanément
    (« No room for a new \\write »). Le livret recap émet un seul cycle
    global init/affiche en début/fin de document, ce qui suffit pour les
    rares atomes qui utilisent \\seqAnnexe (3 méthodes en N11/S04 et N12/S04
    au moment d'écrire ces lignes). Effet de bord : leurs annexes sont
    accumulées dans un même AnnList.tex global et affichées à la toute fin
    du livret, au lieu de juste après leur méthode — comportement cohérent
    avec un livret papier classique.
    """
    tex = generer_corps_notion(atome, inclure_init_annexes=False)
    return _RE_SETCOUNTER_NOTION.sub('', tex)


def _generer_corps_methode_continu(atome: Atome) -> str:
    """Comme generer_corps_methode mais en supprimant le \\setcounter local.

    Cf. _generer_corps_notion_continu pour la justification de
    inclure_init_annexes=False.
    """
    tex = generer_corps_methode(atome, inclure_init_annexes=False)
    return _RE_SETCOUNTER_METHODE.sub('', tex)


# ── Génération principale ────────────────────────────────────────────────────

def generer_recap_cours(conn: sqlite3.Connection,
                         niveau: str,
                         tikz_libraries: list[str] | None = None,
                         tblr_libraries: list[str] | None = None) -> str:
    """Génère le source .tex complet du Récap cours pour un niveau.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion à la BDD seqenseigne.
    niveau : str
        Code de niveau ('N09', 'N10', 'N11', 'N12').
    tikz_libraries : list[str], optional
        Bibliothèques tikz à charger via \\usetikzlibrary{...}, transmises
        telles quelles à construire_preambule. Cf. configuration utilisateur
        (Configuration.tikz_libraries()).
    tblr_libraries : list[str], optional
        Bibliothèques tabularray à charger via \\UseTblrLibrary{...}.
        IMPORTANT : 'booktabs' doit y figurer pour que les \\toprule /
        \\midrule / \\bottomrule fonctionnent dans les tableaux des atomes.
        Cf. Configuration.tblr_libraries().

    Returns
    -------
    str
        Source .tex complet, prêt à être compilé.
    """
    # 1. Récupérer la structure thèmes → séquences → atomes
    cycle_code = lire_cycle(conn, niveau)
    themes = _lire_themes_du_cycle(conn, cycle_code)

    # On collecte tous les atomes pour pouvoir, dans un second temps, calculer
    # le préambule (fermeture transitive des macros utilisées). On garde aussi
    # leur corps généré pour le réinjecter dans l'ordre.
    structure = []  # liste de (theme, [(sequence, [notions], [methodes])])
    tous_textes_atomes = []  # pour la détection de paquets

    for theme in themes:
        sequences = _lire_sequences_du_theme(conn, theme['id'])
        seqs_avec_atomes = []
        for seq in sequences:
            notions_ids = _lire_notions_de_sequence(conn, niveau, seq['code'])
            methodes_ids = _lire_methodes_de_sequence(conn, niveau, seq['code'])

            notions_corps = []
            for n in notions_ids:
                atome = charger_atome(conn, 'notion', n['id'])
                # Résoudre les getters CSV (\seqObjectifGetNom, etc.)
                atome.corps = resoudre_macros_csv(
                    conn, atome.corps, atome.niveau, atome.sequence)
                tex = _generer_corps_notion_continu(atome)
                notions_corps.append(tex)
                tous_textes_atomes.append(
                    (atome.corps or '') + (atome.variables or '') + tex)

            methodes_corps = []
            for m in methodes_ids:
                atome = charger_atome(conn, 'methode', m['id'])
                atome.corps = resoudre_macros_csv(
                    conn, atome.corps, atome.niveau, atome.sequence)
                tex = _generer_corps_methode_continu(atome)
                methodes_corps.append(tex)
                tous_textes_atomes.append(
                    (atome.corps or '') + (atome.variables or '') + tex)

            seqs_avec_atomes.append({
                'sequence': seq,
                'notions': notions_corps,
                'methodes': methodes_corps,
            })
        if seqs_avec_atomes:
            structure.append({'theme': theme, 'sequences': seqs_avec_atomes})

    # 2. Construire le préambule sur mesure couvrant toutes les macros
    #    utilisées par les atomes agrégés.
    texte_global = '\n'.join(tous_textes_atomes)
    macros_utilisees, envs_utilises = extraire_utilisations(texte_global)

    # Options du paquet (geometrie, scratch) selon les macros utilisées
    # On simule un Atome global pour réutiliser detecter_options_paquet.
    atome_global = Atome(
        id='_recap_',
        type_atome='exercice',
        niveau=niveau,
        sequence='',
        fichier='',
        corps=texte_global,
    )
    options = detecter_options_paquet(conn, atome_global)
    paquets_manquants = detecter_paquets_tex_manquants(conn, atome_global)

    preambule = construire_preambule(
        conn, 'exercice',
        macros_utilisees, envs_utilises,
        options_atome=options,
        paquets_tex_supplementaires=paquets_manquants,
        tikz_libraries=tikz_libraries,
        tblr_libraries=tblr_libraries,
    )

    # 3. Assemblage du .tex
    lignes: list[str] = []
    lignes.append(r'%% Livret Récap cours — généré pour rendu agrégé.')
    lignes.append(f'%% Niveau : {niveau}')
    lignes.append('')
    lignes.append(r'\documentclass[a4paper,11pt,twoside]{article}')
    lignes.append('')
    lignes.append(preambule.texte)
    lignes.append('')
    # Paquets supplémentaires nécessaires pour le livret (table des matières,
    # entêtes/pieds de page, structure de section).
    lignes.append(r'\usepackage{titlesec}')
    lignes.append(r'\usepackage{fancyhdr}')
    lignes.append(r'\usepackage{lastpage}')
    lignes.append('')
    # Géométrie de la page (marges plus aérées que pour un atome isolé)
    lignes.append(r'\geometry{vmargin=70pt,hmargin=50pt,headheight=50pt,'
                  r'headsep=15pt,footskip=20pt}')
    lignes.append('')
    # Entêtes et pieds de page (cf. modèle N10_Exercices_corriges.tex)
    lignes.append(r'\pagestyle{fancy}')
    lignes.append(r'\fancyhf{}')
    lignes.append(r'\lhead{\leftmark}')
    lignes.append(r'\rhead{\rightmark}')
    lignes.append(r'\rfoot{Page \thepage/\pageref{LastPage}}')
    lignes.append(r'\lfoot{Le \today}')
    lignes.append(r'\renewcommand{\sectionmark}[1]{\markboth{#1}{}}')
    lignes.append(r'\renewcommand{\subsectionmark}[1]{\markright{#1}}')
    lignes.append(r'\renewcommand{\headrulewidth}{0.4pt}')
    lignes.append(r'\renewcommand{\footrulewidth}{0pt}')
    lignes.append('')
    # Format des titres (cf. modèle)
    lignes.append(
        r'\titleformat{\section}[frame]{\normalfont}'
        r'{\filright\footnotesize\enspace SECTION \thesection\enspace}'
        r'{30pt}{\huge\bfseries\filcenter}')
    lignes.append(
        r'\titleformat{\subsection}[block]{\normalfont\sffamily}'
        r'{\thesubsection}{.5em}'
        r'{\titlerule[2pt]\\[1em]\bfseries\sc\Large\filcenter}'
        r'[\vspace{2ex}\titlerule]')
    lignes.append(
        r'\titleformat{\subsubsection}{\normalfont\bfseries}'
        r'{\thesubsubsection}{1em}{}')
    lignes.append('')
    lignes.append(r'\setcounter{tocdepth}{2}')
    lignes.append('')
    lignes.append(r'\begin{document}')
    lignes.append('')
    # Fallbacks pour \theHxxx (hyperref non chargé dans le préambule)
    lignes.append(r'\providecommand{\theHExoNum}{\theExoNum}')
    lignes.append(r'\providecommand{\theHNotionNum}{\theNotionNum}')
    lignes.append(r'\providecommand{\theHMethodeNum}{\theMethodeNum}')
    lignes.append(r'\providecommand{\theHDefinitionNum}{\theDefinitionNum}')
    lignes.append(r'\providecommand{\theHProprieteNum}{\theProprieteNum}')
    lignes.append('')
    lignes.append(r'\seqCreeCompteurs')
    lignes.append(r'\seqSetCodeNiveau{' + niveau + '}')
    # Cycle annexes global : un seul \seqInitAnnexes pour tout le livret
    # (les corps notion/méthode sont générés avec inclure_init_annexes=False
    # pour ne pas saturer la limite de 16 \newwrite de TeX). Le
    # \seqAfficheAnnexes correspondant est émis juste avant \end{document}.
    lignes.append(r'\seqInitAnnexes')
    lignes.append('')

    # 4. Page de garde
    lignes.extend(_page_de_garde(niveau, structure))

    # 5. Table des matières
    lignes.append(r'\thispagestyle{empty}')
    lignes.append(r'\tableofcontents')
    lignes.append(r'\newpage')
    lignes.append('')

    # 6. Pour chaque thème, on émet une section avec sous-sections par séquence.
    for bloc in structure:
        theme = bloc['theme']
        lignes.append(r'\cleardoublepage')
        # Couleurs du thème
        lignes.append(f"\\seqSetColorsTheme{{{theme['code_couleur']}}}")
        lignes.append(f"\\section{{{_echapper(theme['nom'])}}}")
        if theme.get('description'):
            lignes.append(theme['description'])
        lignes.append('')

        for sb in bloc['sequences']:
            seq = sb['sequence']
            lignes.append(f"\\seqSetCodeSequence{{{seq['code']}}}")
            lignes.append(f"\\subsection{{{_echapper(seq['nom'])}}}")
            lignes.append('')

            if sb['notions']:
                lignes.append(r'\subsubsection{Connaissances}')
                lignes.append('')
                for tex in sb['notions']:
                    lignes.append(tex)
                    lignes.append('')

            if sb['methodes']:
                lignes.append(r'\subsubsection{Savoir-faire}')
                lignes.append('')
                for tex in sb['methodes']:
                    lignes.append(tex)
                    lignes.append('')

    # Cycle annexes global : ferme \annfile et inclut AnnList.tex (no-op
    # si aucun atome du livret n'a utilisé \seqAnnexe).
    lignes.append(r'\seqAfficheAnnexes')
    lignes.append(r'\end{document}')
    return '\n'.join(lignes)


# ── Page de garde ────────────────────────────────────────────────────────────

def _page_de_garde(niveau: str,
                    structure: list[dict]) -> list[str]:
    """Page de garde simple : titre, niveau, liste des intitulés de séquences.
    Inspirée du modèle Cours_-_année_complète.pdf.
    """
    lignes = [r'\thispagestyle{empty}']
    libelle_niveau = LIBELLES_NIVEAUX.get(niveau, niveau)
    lignes.append(r'\begin{center}')
    lignes.append(r'\vspace*{2em}')
    lignes.append(r'{\Huge\bfseries Livret de cours}\\[2em]')
    lignes.append(r'{\Large Collège}\\[1em]')
    lignes.append(rf'{{\LARGE Classe de {libelle_niveau}}}\\[3em]')
    lignes.append(r'\end{center}')
    lignes.append('')

    # Liste des séquences (intitulés tels quels)
    lignes.append(r'\begin{itemize}')
    for bloc in structure:
        for sb in bloc['sequences']:
            seq = sb['sequence']
            lignes.append(f"  \\item {_echapper(seq['nom'])}")
    lignes.append(r'\end{itemize}')
    lignes.append('')

    lignes.append(r'\newpage')
    lignes.append('')
    return lignes


# ── Utilitaires ──────────────────────────────────────────────────────────────

def _echapper(texte: str) -> str:
    """Échappement minimal pour insertion dans un titre LaTeX.

    Note : on ne fait PAS d'échappement de \\ et de & ici, car les noms
    de séquences et de thèmes peuvent contenir du LaTeX intentionnel
    (\\ieme, par exemple, est dans le référentiel).
    """
    return texte or ''
