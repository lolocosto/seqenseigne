r"""
services/paquet_parseur.py — Parseur des fichiers .sty du paquet seqenseigne.

Extrait les définitions LaTeX (\newcommand, \newenvironment, \newtcolorbox,
\define@cmdkey, \newcounter, \newcolumntype, \newif) et analyse leurs
corps pour détecter les dépendances internes (macros appelées, environnements
utilisés).

Conçu spécifiquement pour les .sty du paquet seqenseigne. Les parseurs LaTeX
généralistes (TexSoup, pylatexenc) ne tiennent pas sur ce type de code
(timeout ou erreurs sur les \begin{...} dans les corps de \newenvironment).

Aucune dépendance externe. Importable par Flask et les scripts.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field


# ── Prétraitement : supprimer les commentaires LaTeX ───────────────────────────

def strip_comments(src: str) -> str:
    r"""Supprime les commentaires LaTeX (% hors \%) ligne par ligne.

    Conserve les retours à la ligne pour que les numéros de lignes
    restent cohérents avec l'original.
    """
    out = []
    for line in src.split('\n'):
        i = 0
        while i < len(line):
            if line[i] == '%' and (i == 0 or line[i - 1] != '\\'):
                break
            i += 1
        out.append(line[:i])
    return '\n'.join(out)


# ── Extraction d'arguments balancés ────────────────────────────────────────────

def extract_balanced(src: str, start: int,
                     open_char: str, close_char: str) -> tuple[str, int]:
    r"""Extrait le contenu entre open_char et close_char à partir de start
    (qui doit pointer sur open_char).

    Retourne (contenu_sans_délimiteurs, position_juste_après_close_char).
    Gère l'imbrication et les caractères échappés \\{, \\}, \\[, \\].
    """
    if src[start] != open_char:
        raise ValueError(
            f"attendu '{open_char}' à la position {start}, trouvé {src[start]!r}"
        )
    depth = 1
    i = start + 1
    begin = i
    while i < len(src):
        c = src[i]
        if c == '\\' and i + 1 < len(src):
            # sauter le caractère échappé
            i += 2
            continue
        if c == open_char:
            depth += 1
        elif c == close_char:
            depth -= 1
            if depth == 0:
                return src[begin:i], i + 1
        i += 1
    raise ValueError(f"délimiteur '{open_char}' non fermé à partir de {start}")


def _skip_whitespace(src: str, pos: int) -> int:
    """Avance pos au premier caractère non-blanc."""
    while pos < len(src) and src[pos] in ' \t\n\r':
        pos += 1
    return pos


# ── Lecture d'arguments selon une signature ────────────────────────────────────
#
# Codes de signature :
#   *  : étoile optionnelle (renvoie '*' ou None)
#   {  : argument obligatoire entre {...} (renvoie str ou nom de commande)
#   [  : argument optionnel entre [...] (renvoie str ou None)

def _read_args(src: str, pos: int, signature: str) -> tuple[list, int]:
    """Lit une séquence d'arguments selon `signature`.

    Retourne (liste_arguments, position_après_dernier).
    Pour les arguments '{', accepte aussi la forme \\nom (sans accolades).
    """
    args = []
    for slot in signature:
        pos = _skip_whitespace(src, pos)
        if pos >= len(src):
            args.append(None)
            continue

        if slot == '*':
            if src[pos] == '*':
                args.append('*')
                pos += 1
            else:
                args.append(None)

        elif slot == '{':
            if src[pos] == '{':
                content, pos = extract_balanced(src, pos, '{', '}')
                args.append(content)
            elif src[pos] == '\\':
                # Cas \newcommand\foo{...}
                m = re.match(r'\\([A-Za-z@]+|[^A-Za-z])', src[pos:])
                if m:
                    args.append(m.group(0))
                    pos += m.end()
                else:
                    args.append(None)
            else:
                args.append(None)

        elif slot == '[':
            if src[pos] == '[':
                content, pos = extract_balanced(src, pos, '[', ']')
                args.append(content)
            else:
                args.append(None)

        else:
            raise ValueError(f"Slot de signature inconnu : {slot!r}")

    return args, pos


# ── Primitives reconnues avec leur signature ───────────────────────────────────

PRIMITIVES = {
    'newcommand':            ('command',     '*{[[{'),
    'renewcommand':          ('command',     '*{[[{'),
    'providecommand':        ('command',     '*{[[{'),
    'DeclareRobustCommand':  ('command',     '*{[[{'),
    'newenvironment':        ('environment', '{[[{{'),
    'renewenvironment':      ('environment', '{[[{{'),
    'NewEnviron':            ('environment', '{[{'),
    'newtcolorbox':          ('tcolorbox',   '[{[{'),
    'newcounter':            ('counter',     '{['),
    'newcolumntype':         ('columntype',  '{[{'),
    'newif':                 ('if',          '{'),
}


# ── Structure d'une définition extraite ────────────────────────────────────────

@dataclass
class Definition:
    type_latex: str           # 'command' | 'environment' | 'tcolorbox' | ...
    nom: str                  # ex. '\seqFrac', 'seqNotion', 'boiteTitreGen'
    args_spec: str            # signature LaTeX ex. '[2]' ou '[2][]'
    corps: str                # corps principal (pour env : début)
    corps_fin: str            # uniquement pour \newenvironment (fin)
    texte_complet: str        # texte source complet (pour diff / conservation)
    fichier_source: str       # nom du .sty dont vient la définition
    ligne_debut: int          # 1-indexé
    macros_appelees: set[str] = field(default_factory=set)
    environnements_utilises: set[str] = field(default_factory=set)

    def depend_sur(self) -> set[str]:
        r"""Ensemble des noms de dépendances (macros + environnements).

        Les macros gardent leur \\ de préfixe. Les environnements non.
        """
        return set(self.macros_appelees) | set(self.environnements_utilises)


# ── Parseur principal ──────────────────────────────────────────────────────────

def parser_sty(src: str, fichier_source: str = '') -> list[Definition]:
    """Parse un fichier .sty et retourne la liste des définitions trouvées."""
    src_clean = strip_comments(src)
    defs: list[Definition] = []

    i = 0
    while i < len(src_clean):
        if src_clean[i] != '\\':
            i += 1
            continue

        m = re.match(r'\\([A-Za-z@]+)', src_clean[i:])
        if not m:
            i += 1
            continue

        motclef = m.group(1)
        if motclef not in PRIMITIVES:
            i += m.end()
            continue

        type_latex, sig = PRIMITIVES[motclef]
        debut_absolu = i
        ligne = src_clean[:i].count('\n') + 1
        arg_start = i + m.end()

        try:
            args, fin = _read_args(src_clean, arg_start, sig)
        except ValueError:
            i = arg_start
            continue

        d = _construire_definition(
            type_latex, args, src_clean, debut_absolu, fin,
            fichier_source, ligne,
        )
        if d is not None:
            analyser_corps(d)
            defs.append(d)

        i = fin

    # Cas particulier : \define@cmdkey[prefix]{famille}{cle}[default]{action}
    # La regex initiale capturait prefix/famille/cle mais s'arrêtait là — sans
    # capturer l'action obligatoire {...} qui suit. Résultat : `texte_complet`
    # tronqué, et au moment de l'inlining dans le préambule d'un atome, xkeyval
    # consommait silencieusement les tokens suivants comme s'ils étaient l'action,
    # corrompant la définition suivante (typiquement la 2e \define@cmdkey).
    #
    # On utilise _read_args avec la signature '[{{[{' :
    #   [  prefix optionnel (avec [...])
    #   {  famille obligatoire
    #   {  cle obligatoire
    #   [  default optionnel
    #   {  action obligatoire
    for m in re.finditer(r'\\define@cmdkey\b', src_clean):
        debut = m.start()
        ligne = src_clean[:debut].count('\n') + 1
        try:
            args, fin = _read_args(src_clean, m.end(), '[{{[{')
        except (ValueError, IndexError):
            continue
        prefix = (args[0] or '').strip()
        famille = (args[1] or '').strip()
        cle = (args[2] or '').strip()
        if not famille or not cle:
            continue
        # Nom synthétique : \cmdseq@famille@cle (convention seqenseigne)
        nom = f'\\cmd{prefix}@{famille}@{cle}' if prefix else f'\\cmd{famille}@{cle}'
        d = Definition(
            type_latex='cmdkey',
            nom=nom,
            args_spec='[]',
            corps='',
            corps_fin='',
            texte_complet=src_clean[debut:fin],
            fichier_source=fichier_source,
            ligne_debut=ligne,
        )
        defs.append(d)

    # v0.13.7.2.2 — Cas particulier : \define@choicekey, analogue à
    # \define@cmdkey. Sans ce traitement, la fermeture transitive du
    # préambule d'atome ne tire pas la définition de la clé (qui pourtant
    # apparaît dans macros_appelees sous le nom \cmd<prefix>@<famille>@<cle>),
    # et un \setkeys ultérieur signale une clé inconnue à la compilation.
    #
    # Signature xkeyval :
    #   \define@choicekey[<prefix>]{<famille>}{<cle>}[<store>]{<choix>}[<default>]{<action>}
    #
    # _read_args avec la signature '[{{[{[{' :
    #   [  prefix optionnel
    #   {  famille obligatoire
    #   {  cle obligatoire
    #   [  store optionnel (variables \val \nr typiquement)
    #   {  choix obligatoire (liste de valeurs séparées par virgules)
    #   [  default optionnel
    #   {  action obligatoire
    #
    # Le nom synthétique généré est le même que pour cmdkey, et le type
    # reste 'cmdkey' : c'est ainsi que la fermeture transitive et le
    # filtrage côté UI (cf. services.paquet_expose) traitent ces clés de
    # manière homogène. Type spécifique non créé pour éviter une nouvelle
    # branche dans le routage de paquet_definitions.
    for m in re.finditer(r'\\define@choicekey\b', src_clean):
        debut = m.start()
        ligne = src_clean[:debut].count('\n') + 1
        try:
            args, fin = _read_args(src_clean, m.end(), '[{{[{[{')
        except (ValueError, IndexError):
            continue
        prefix = (args[0] or '').strip()
        famille = (args[1] or '').strip()
        cle = (args[2] or '').strip()
        if not famille or not cle:
            continue
        nom = f'\\cmd{prefix}@{famille}@{cle}' if prefix else f'\\cmd{famille}@{cle}'
        d = Definition(
            type_latex='cmdkey',
            nom=nom,
            args_spec='[]',
            corps='',
            corps_fin='',
            texte_complet=src_clean[debut:fin],
            fichier_source=fichier_source,
            ligne_debut=ligne,
        )
        defs.append(d)

    return defs


def _construire_definition(type_latex: str, args: list,
                           src: str, debut: int, fin: int,
                           fichier_source: str, ligne: int) -> Definition | None:
    """Construit une Definition à partir des arguments bruts parsés."""
    nom = ''
    args_spec = ''
    corps = ''
    corps_fin = ''

    if type_latex == 'command':
        # args = [etoile, nom, nbargs, default, body]
        nom_raw = args[1] or ''
        nom = nom_raw if nom_raw.startswith('\\') else '\\' + nom_raw.lstrip('\\')
        args_spec = _format_args_spec(args[2], args[3])
        corps = args[4] or ''

    elif type_latex == 'environment':
        nom = args[0] or ''
        if len(args) == 5:
            args_spec = _format_args_spec(args[1], args[2])
            corps = args[3] or ''
            corps_fin = args[4] or ''
        elif len(args) == 3:
            args_spec = _format_args_spec(args[1], None)
            corps = args[2] or ''

    elif type_latex == 'tcolorbox':
        # args = [options, nom, nbargs, body]
        nom = args[1] or ''
        args_spec = _format_args_spec(args[2], None)
        corps = args[3] or ''

    elif type_latex == 'counter':
        nom = args[0] or ''

    elif type_latex == 'columntype':
        nom = args[0] or ''
        corps = args[2] or ''

    elif type_latex == 'if':
        # \newif\ifxxx — args[0] = '\\ifxxx'
        nom = args[0] or ''

    if not nom:
        return None

    return Definition(
        type_latex=type_latex,
        nom=nom,
        args_spec=args_spec,
        corps=corps,
        corps_fin=corps_fin,
        texte_complet=src[debut:fin],
        fichier_source=fichier_source,
        ligne_debut=ligne,
    )


def _format_args_spec(nbargs: str | None, default: str | None) -> str:
    """Formate la signature LaTeX : '' | '[n]' | '[n][d]'."""
    if not nbargs:
        return ''
    if default is not None:
        return f'[{nbargs}][{default}]'
    return f'[{nbargs}]'


# ── Analyse des dépendances dans le corps ──────────────────────────────────────

# Primitives LaTeX à NE PAS considérer comme dépendances.
# Liste volontairement exhaustive — on préfère trop large que trop strict
# pour éviter de fausses alertes lors de la vérification de couverture.
PRIMITIVES_LATEX = frozenset({
    # Structure
    'begin', 'end', 'item', 'par',
    # Environnements de listes (primitives LaTeX)
    'enumerate', 'itemize', 'description', 'list', 'trivlist',
    # Conditionnels & logique
    'if', 'else', 'fi', 'ifthenelse', 'ifnum', 'ifdim', 'ifx', 'ifdefined',
    'ifdefstring', 'ifnumcomp', 'ifcsname', 'ifempty', 'isempty', 'equal',
    'AtBeginDocument', 'AtEndDocument',
    # Définitions (définies, pas dépendances)
    'def', 'edef', 'gdef', 'xdef', 'let', 'newcommand', 'renewcommand',
    'providecommand', 'DeclareRobustCommand',
    'newenvironment', 'renewenvironment', 'NewEnviron',
    'newcounter', 'newif', 'newtcolorbox', 'newcolumntype',
    'define', 'setkeys', 'define@cmdkey', 'define@key', 'define@choicekey',
    # Compteurs
    'setcounter', 'addtocounter', 'refstepcounter', 'stepcounter', 'value',
    'arabic', 'roman', 'alph', 'Alph', 'Roman', 'the',
    # Références
    'label', 'ref', 'pageref', 'cite', 'nameref', 'eqref',
    # Arguments / expansion
    'MakeUppercase', 'MakeLowercase', 'unexpanded', 'expandafter', 'noexpand',
    'empty', 'relax', 'protect', 'csname', 'endcsname', 'string', 'meaning',
    # Espacement
    'hfill', 'vfill', 'hspace', 'vspace', 'quad', 'qquad', 'smallskip', 'medskip',
    'bigskip', 'linewidth', 'textwidth', 'columnwidth', 'paperwidth', 'paperheight',
    'textheight', 'lineskip', 'baselineskip', 'noindent', 'indent',
    'nopagebreak', 'pagebreak', 'newpage', 'clearpage', 'newline', 'removelastskip',
    'setlength', 'addtolength', 'parindent', 'columnsep', 'parskip',
    'raggedright', 'raggedleft', 'centering', 'center',
    # Tailles
    'tiny', 'scriptsize', 'footnotesize', 'small', 'normalsize', 'large', 'Large',
    'LARGE', 'huge', 'Huge',
    # Styles
    'textbf', 'textit', 'textrm', 'textsf', 'texttt', 'textsc', 'emph', 'textsl',
    'underline', 'bf', 'it', 'sf', 'tt', 'sc', 'em', 'rm',
    'bfseries', 'itshape', 'rmfamily', 'sffamily', 'ttfamily', 'scshape',
    'upshape', 'mdseries', 'normalfont', 'slshape',
    # Maths
    'frac', 'dfrac', 'tfrac', 'cdot', 'cdots', 'ldots', 'dots', 'vdots',
    'sqrt', 'sum', 'prod', 'int', 'lim', 'max', 'min', 'sup', 'inf',
    'times', 'div', 'pm', 'mp', 'leq', 'geq', 'leqslant', 'geqslant',
    'neq', 'approx', 'equiv', 'sim', 'simeq', 'cong', 'propto',
    'left', 'right', 'big', 'Big', 'bigg', 'Bigg', 'middle',
    'mathbb', 'mathbf', 'mathcal', 'mathrm', 'mathit', 'mathsf', 'mathtt',
    # Trigo / log / fonctions std (définies par amsmath)
    'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
    'arcsin', 'arccos', 'arctan',
    'sinh', 'cosh', 'tanh', 'coth',
    'log', 'ln', 'lg', 'exp', 'det', 'dim', 'ker', 'deg',
    'gcd', 'pgcd', 'ppcm', 'mod',
    'text', 'textnormal',  # amsmath : \text{}
    'iff', 'implies', 'mapsto', 'to', 'rightarrow', 'leftarrow',
    'Rightarrow', 'Leftarrow', 'Leftrightarrow', 'leftrightarrow',
    # Primitives tables/arrays
    'hline', 'cline', 'multicolumn', 'arraybackslash', 'arraystretch',
    'vline', 'rowcolor', 'columncolor', 'cellcolor',
    # Sauts de colonne / spéciaux
    'columnbreak', 'centerline', 'textsuperscript', 'textsubscript',
    'fontfamily', 'selectfont', 'fontsize',
    'checkmark',
    # Ligatures françaises / symboles
    'oe', 'ae', 'aa', 'AA', 'OE', 'AE', 'ss',
    'matrix',  # amsmath / maths généraux
    'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'varepsilon', 'zeta', 'eta',
    'theta', 'vartheta', 'iota', 'kappa', 'lambda', 'mu', 'nu', 'xi',
    'pi', 'varpi', 'rho', 'varrho', 'sigma', 'varsigma', 'tau', 'upsilon',
    'phi', 'varphi', 'chi', 'psi', 'omega',
    'Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta', 'Eta', 'Theta',
    'Iota', 'Kappa', 'Lambda', 'Mu', 'Nu', 'Xi', 'Omicron', 'Pi', 'Rho',
    'Sigma', 'Tau', 'Upsilon', 'Phi', 'Chi', 'Psi', 'Omega',
    'infty', 'partial', 'nabla', 'exists', 'forall', 'in', 'notin', 'ni',
    'subset', 'supset', 'subseteq', 'supseteq', 'cup', 'cap', 'emptyset',
    'angle', 'parallel', 'perp', 'circ', 'triangle', 'square',
    # Accents
    'vec', 'bar', 'hat', 'tilde', 'dot', 'ddot', 'acute', 'grave', 'breve', 'check',
    'overrightarrow', 'overleftarrow', 'overline', 'widehat', 'widetilde',
    # Structure document
    'input', 'include', 'usepackage', 'RequirePackage', 'documentclass',
    'title', 'author', 'date', 'maketitle', 'abstract', 'section', 'subsection',
    'subsubsection', 'chapter', 'paragraph', 'subparagraph', 'appendix',
    'footnote', 'mbox', 'fbox', 'parbox', 'minipage', 'tabular', 'array',
    'multicolumn', 'multirow', 'caption', 'includegraphics',
    # TeX bas niveau
    'strut', 'phantom', 'vphantom', 'hphantom', 'mathstrut',
    'thepage', 'today', 'number', 'numexpr', 'dimexpr',
    'char', 'chardef', 'countdef', 'global', 'long', 'outer',
    'or', 'and', 'not',
    # tcolorbox / couleurs
    'tcblower',
    'color', 'colorbox', 'fcolorbox', 'definecolor', 'textcolor', 'pagecolor',
    # Typographie fr (babel)
    'og', 'fg',
    # Symboles courants
    'backslash', 'bullet', 'star', 'dag', 'ddag', 'ieme',
    # IO
    'write', 'openout', 'closeout', 'immediate', 'newwrite',
    'tcbverbatimwrite',  # défini par tcolorbox, pas par seqenseigne
    'scantokens',
    # hyperref
    'texorpdfstring', 'hyperref',
    # fancyhdr
    'lfoot', 'rfoot', 'lhead', 'rhead', 'chead', 'cfoot', 'fancyhf', 'pagestyle',
    'thispagestyle',
    # datetime
    'datemoisannee',
    # Divers
    'scriptstyle', 'textstyle', 'displaystyle', 'scriptscriptstyle',
    # TeX primitifs supplémentaires
    'break', 'nobreak', 'allowbreak', 'mathstrut',
    'space', 'quad', 'qquad',
    'phantomsection',
})


def analyser_corps(d: Definition) -> None:
    """Remplit d.macros_appelees et d.environnements_utilises.

    Détecte :
    - les macros `\\nom` (pattern direct)
    - les environnements `\\begin{nom}`
    - les compteurs LaTeX référencés par leur nom textuel (sans backslash) :
      `\\setcounter{nom}`, `\\stepcounter{nom}`, `\\refstepcounter{nom}`,
      `\\addtocounter{nom}`, `\\value{nom}`, `\\forloop{nom}`,
      `\\arabic{nom}`, `\\roman{nom}`, `\\alph{nom}`, `\\Alph{nom}`,
      `\\Roman{nom}`. Ces compteurs sont stockés dans macros_appelees
      sans backslash (cohérent avec leur indexation dans
      paquet_definitions par `\\newcounter`).

      v0.13.7.2.3 — Ce dernier point est crucial pour que la fermeture
      transitive tire la définition du compteur quand il est utilisé.
      Sans cela, un environnement comme seqQcm (qui fait
      `\\setcounter{seq@qcm@alphcode}{40}` etc.) générait un préambule
      où le compteur n'était pas déclaré, causant une erreur
      « No counter 'seq@qcm@alphcode' defined ».

      Les compteurs LaTeX standard (page, section, equation, footnote,
      figure, table, chapter…) sont aussi détectés ici mais silencieusement
      ignorés par la fermeture transitive parce qu'ils ne sont pas
      dans la table paquet_definitions.
    """
    corps_total = d.corps + '\n' + d.corps_fin

    for m in re.finditer(r'\\([A-Za-z@]+)', corps_total):
        nom = m.group(1)
        if nom in PRIMITIVES_LATEX:
            continue
        # Exclure aussi les noms trop courts (x, y, i, j utilisés dans \foreach tikz)
        if len(nom) == 1:
            continue
        d.macros_appelees.add('\\' + nom)

    for m in re.finditer(r'\\begin\s*\{([^}]+)\}', corps_total):
        env = m.group(1).strip()
        if env and env not in PRIMITIVES_LATEX:
            d.environnements_utilises.add(env)

    # v0.13.7.2.3 — Détection des compteurs référencés par leur nom textuel.
    # Une seule regex couvre toutes les primitives qui prennent un compteur
    # en 1er argument : \setcounter, \stepcounter, \refstepcounter,
    # \addtocounter, \value, \forloop, \arabic, \roman, \alph, \Alph, \Roman.
    _RE_COMPTEURS = re.compile(
        r'\\(?:setcounter|stepcounter|refstepcounter|addtocounter|value'
        r'|forloop|arabic|roman|alph|Alph|Roman)\s*\{([^}]+)\}'
    )
    for m in _RE_COMPTEURS.finditer(corps_total):
        nom_compteur = m.group(1).strip()
        if nom_compteur:
            d.macros_appelees.add(nom_compteur)


# ── Extraction des \RequirePackage ────────────────────────────────────────────

def extraire_requirepackage(src: str) -> list[tuple[str, str]]:
    """Retourne [(nom_paquet, options), ...] depuis un .sty."""
    src_clean = strip_comments(src)
    out = []
    for m in re.finditer(
        r'\\RequirePackage\s*(?:\[([^\]]*)\])?\s*\{([^}]+)\}',
        src_clean,
    ):
        options = (m.group(1) or '').strip()
        nom = m.group(2).strip()
        out.append((nom, options))
    return out


# ══════════════════════════════════════════════════════════════════════════════
# Détection des dépendances externes dans un texte LaTeX d'atome.
# Ces outils analysent un fragment LaTeX (corps d'exercice, de notion, de
# méthode) pour identifier :
#   - les macros qu'il définit localement (à exclure des dépendances)
#   - les macros/environnements qu'il appelle et dont il dépend
# Ils utilisent MACROS_PAQUETS_EXTERNES pour savoir à quel paquet TeX
# appartient chaque macro courante.
# ══════════════════════════════════════════════════════════════════════════════

# Macros définies par les paquets TeX externes connus (chargés par le core ou
# via les options du paquet). Elles ne sont PAS dans paquet_definitions mais
# sont disponibles à la compilation si le bon \usepackage est émis.
#
# Clé = nom de macro (avec \) ou environnement (sans \), valeur = nom du paquet TeX.
MACROS_PAQUETS_EXTERNES = {
    # tkz-euclide (option [geometrie])
    '\\tkzDefPoint': 'tkz-euclide', '\\tkzDefPoints': 'tkz-euclide',
    '\\tkzDefPointBy': 'tkz-euclide', '\\tkzDefShiftPoint': 'tkz-euclide',
    '\\tkzDefLine': 'tkz-euclide', '\\tkzDefCircle': 'tkz-euclide',
    '\\tkzDefCircleBy': 'tkz-euclide', '\\tkzDefCircleCenter': 'tkz-euclide',
    '\\tkzDefMidPoint': 'tkz-euclide', '\\tkzDefBarycentricPoint': 'tkz-euclide',
    '\\tkzDefPointOnLine': 'tkz-euclide', '\\tkzDefSquare': 'tkz-euclide',
    '\\tkzDefTriangle': 'tkz-euclide',
    '\\tkzInit': 'tkz-euclide', '\\tkzClip': 'tkz-euclide',
    '\\tkzGrid': 'tkz-euclide', '\\tkzAxeX': 'tkz-euclide', '\\tkzAxeY': 'tkz-euclide',
    '\\tkzAxeXY': 'tkz-euclide', '\\tkzDrawX': 'tkz-euclide', '\\tkzDrawY': 'tkz-euclide',
    '\\tkzDrawXY': 'tkz-euclide', '\\tkzLabelX': 'tkz-euclide',
    '\\tkzLabelY': 'tkz-euclide', '\\tkzLabelXY': 'tkz-euclide',
    '\\tkzDrawPoints': 'tkz-euclide', '\\tkzDrawPoint': 'tkz-euclide',
    '\\tkzDrawSegment': 'tkz-euclide', '\\tkzDrawSegments': 'tkz-euclide',
    '\\tkzDrawPolygon': 'tkz-euclide',
    '\\tkzDrawLine': 'tkz-euclide', '\\tkzDrawLines': 'tkz-euclide',
    '\\tkzDrawCircle': 'tkz-euclide', '\\tkzDrawCircles': 'tkz-euclide',
    '\\tkzDrawArc': 'tkz-euclide', '\\tkzDrawSector': 'tkz-euclide',
    '\\tkzDrawTriangle': 'tkz-euclide', '\\tkzDrawSquare': 'tkz-euclide',
    '\\tkzDrawRectangle': 'tkz-euclide',
    '\\tkzLabelPoints': 'tkz-euclide', '\\tkzLabelPoint': 'tkz-euclide',
    '\\tkzLabelSegment': 'tkz-euclide', '\\tkzLabelSegments': 'tkz-euclide',
    '\\tkzLabelAngle': 'tkz-euclide', '\\tkzLabelCircle': 'tkz-euclide',
    '\\tkzMarkSegment': 'tkz-euclide', '\\tkzMarkSegments': 'tkz-euclide',
    '\\tkzMarkAngle': 'tkz-euclide', '\\tkzMarkAngles': 'tkz-euclide',
    '\\tkzMarkRightAngle': 'tkz-euclide', '\\tkzMarkRightAngles': 'tkz-euclide',
    '\\tkzInterLL': 'tkz-euclide', '\\tkzInterCC': 'tkz-euclide',
    '\\tkzInterLC': 'tkz-euclide',
    '\\tkzGetPoint': 'tkz-euclide', '\\tkzGetPoints': 'tkz-euclide',
    '\\tkzGetFirstPoint': 'tkz-euclide', '\\tkzGetSecondPoint': 'tkz-euclide',
    '\\tkzText': 'tkz-euclide', '\\tkzFillPolygon': 'tkz-euclide',
    '\\tkzDrawVector': 'tkz-euclide', '\\tkzDrawVectors': 'tkz-euclide',
    '\\tkzCompass': 'tkz-euclide', '\\tkzCalcLength': 'tkz-euclide',
    '\\tkzFindAngle': 'tkz-euclide',

    # tkz-tab
    '\\tkzTab': 'tkz-tab', '\\tkzTabInit': 'tkz-tab', '\\tkzTabLine': 'tkz-tab',

    # tikz général (dispo dans core, pas en option)
    '\\draw': 'tikz', '\\node': 'tikz', '\\coordinate': 'tikz',
    '\\foreach': 'tikz', '\\addplot': 'pgfplots',
    '\\path': 'tikz', '\\clip': 'tikz', '\\scope': 'tikz',
    '\\fill': 'tikz', '\\shade': 'tikz', '\\filldraw': 'tikz',
    '\\shadedraw': 'tikz', '\\useasboundingbox': 'tikz',
    'tikzpicture': 'tikz', 'scope': 'tikz', 'axis': 'pgfplots',

    # scratch3 (option [scratch])
    '\\ovalnum': 'scratch3', '\\ovalvariable': 'scratch3',
    '\\ovaloperator': 'scratch3', '\\ovalsensing': 'scratch3',
    '\\ovalmoreblocks': 'scratch3',
    '\\blockmove': 'scratch3', '\\blockvariable': 'scratch3',
    '\\blockvariablelocal': 'scratch3', '\\blocklook': 'scratch3',
    '\\blockinit': 'scratch3', '\\blockpen': 'scratch3',
    '\\blockrepeat': 'scratch3', '\\blocksensing': 'scratch3',
    '\\blockmoreblocks': 'scratch3', '\\blockif': 'scratch3',
    '\\blockifelse': 'scratch3', '\\blockcontrol': 'scratch3',
    '\\blockoperator': 'scratch3', '\\blockevents': 'scratch3',
    '\\blocktext': 'scratch3', '\\blocksound': 'scratch3',
    '\\blockmovespecial': 'scratch3', '\\blockmovespecialtext': 'scratch3',
    '\\selectmenu': 'scratch3', '\\selectmove': 'scratch3',
    '\\pickupmenu': 'scratch3', '\\droppointdownx': 'scratch3',
    '\\ovalnumvariable': 'scratch3',
    '\\greenflag': 'scratch3',  # drapeau de départ Scratch
    '\\booloperator': 'scratch3',
    '\\turnleft': 'scratch3', '\\turnright': 'scratch3',
    '\\initmoreblocks': 'scratch3', '\\namemoreblocks': 'scratch3',
    'scratch': 'scratch3', 'scratchblocks': 'scratch3',

    # tabularray (dans core)
    'tblr': 'tabularray', 'xltabular': 'xltabular',
    'longtblr': 'tabularray',
    '\\SetCell': 'tabularray', '\\SetRow': 'tabularray',
    '\\SetCols': 'tabularray', '\\SetHline': 'tabularray',
    '\\SetVline': 'tabularray',
    '\\toprule': 'booktabs', '\\midrule': 'booktabs',
    '\\bottomrule': 'booktabs', '\\cmidrule': 'booktabs',
    '\\addlinespace': 'booktabs',

    # amsmath (dans core)
    '\\cancel': 'cancel', '\\cancelto': 'cancel',
    '\\dfrac': 'amsmath', '\\tfrac': 'amsmath',
    '\\binom': 'amsmath', '\\dbinom': 'amsmath',
    '\\underbrace': 'amsmath', '\\overbrace': 'amsmath',
    'align': 'amsmath', 'align*': 'amsmath',
    'aligned': 'amsmath', 'alignedat': 'amsmath',
    'gather': 'amsmath', 'gather*': 'amsmath', 'gathered': 'amsmath',
    'multline': 'amsmath', 'multline*': 'amsmath',
    'cases': 'amsmath', 'split': 'amsmath',
    'flalign': 'amsmath', 'flalign*': 'amsmath',
    'equation*': 'amsmath',

    # amssymb (dans core)
    '\\mathbb': 'amssymb', '\\leqslant': 'amssymb', '\\geqslant': 'amssymb',
    '\\approx': 'amsmath', '\\simeq': 'amssymb',
    '\\widehat': 'amsmath',

    # pifont (dans theme)
    '\\ding': 'pifont', '\\dingline': 'pifont', '\\dinglist': 'pifont',
    '\\Pisymbol': 'pifont', '\\Piline': 'pifont', '\\Pifill': 'pifont',
    'dinglist': 'pifont',

    # xint / xintexpr (dans core)
    '\\xintdefvar': 'xintexpr', '\\xintdefiivar': 'xintexpr',
    '\\xintdeffloatvar': 'xintexpr',
    '\\xinteval': 'xintexpr', '\\xintiieval': 'xintexpr',
    '\\xintfloateval': 'xintexpr', '\\xintthenum': 'xintexpr',
    '\\xintNum': 'xintexpr', '\\xintFrac': 'xintexpr',

    # enumitem (dans theme)
    'itemize*': 'enumitem', 'enumerate*': 'enumitem',
    'description*': 'enumitem',

    # multicol (dans core)
    'multicols': 'multicol', 'multicols*': 'multicol',

    # eurosym (dans core)
    '\\euro': 'eurosym', '\\EUR': 'eurosym',

    # graphicx / adjustbox (dans theme)
    '\\includegraphics': 'graphicx', '\\adjustbox': 'adjustbox',
    '\\rotatebox': 'graphicx', '\\scalebox': 'graphicx',
    '\\resizebox': 'graphicx', '\\trimbox': 'adjustbox',

    # siunitx : paquet principal pour nombres et unités.
    # `\num{1250}` formate un nombre avec le marqueur décimal configuré
    # (chez l'utilisateur seqenseigne : `\sisetup{output-decimal-marker={,}}`).
    # À noter : `\num` existe aussi dans numprint avec une syntaxe proche —
    # ne jamais le router vers numprint sans vérifier l'usage réel.
    '\\num': 'siunitx',
    '\\si': 'siunitx', '\\SI': 'siunitx',
    '\\sisetup': 'siunitx', '\\ang': 'siunitx', '\\qty': 'siunitx',
    '\\unit': 'siunitx',
    # `\numprint` (macro distincte) reste dans numprint
    '\\numprint': 'numprint',
    # Préfixes d'unités siunitx
    '\\centi': 'siunitx', '\\milli': 'siunitx', '\\kilo': 'siunitx',
    '\\deca': 'siunitx', '\\deci': 'siunitx', '\\hecto': 'siunitx',
    '\\mega': 'siunitx', '\\giga': 'siunitx', '\\tera': 'siunitx',
    '\\micro': 'siunitx', '\\nano': 'siunitx', '\\pico': 'siunitx',
    # Unités siunitx
    '\\metre': 'siunitx', '\\meter': 'siunitx',
    '\\second': 'siunitx', '\\gram': 'siunitx', '\\gramme': 'siunitx',
    '\\ampere': 'siunitx', '\\kelvin': 'siunitx',
    '\\mole': 'siunitx', '\\candela': 'siunitx',

    # xlop — opérations posées (division \opidiv, multiplication, addition...)
    '\\opidiv': 'xlop', '\\opdiv': 'xlop',
    '\\opmul': 'xlop', '\\opadd': 'xlop',
    '\\opsub': 'xlop', '\\opset': 'xlop', '\\opcopy': 'xlop',
    '\\opexport': 'xlop', '\\opimport': 'xlop',
    '\\opgfsqrt': 'xlop',

    # tabularx (hors tabularray, historique)
    'tabularx': 'tabularx',

    # pgf low-level & pgfplots
    '\\pgfmathparse': 'pgf',
    '\\pgfmathresult': 'pgf',
    '\\pgfmathsetmacro': 'pgf',
    '\\pgfmathprintnumber': 'pgf',
    '\\pgfkeys': 'pgf',
    '\\tikzset': 'tikz',
    '\\pgfplotsset': 'pgfplots',
    '\\addlegendentry': 'pgfplots',
    '\\legend': 'pgfplots',
    '\\tick': 'pgfplots',
    '\\nexttick': 'pgfplots',

    # wideparen / arc de cercle sur une expression : \wideparen{AB}
    # v0.9.1 — correction : la macro \wideparen vient du paquet yhmath
    # (Yannis Haralambous), pas d'un paquet "wideparen.sty" qui n'existe
    # pas. Détecté par batch méthodes du 27/04/26 sur N11/S11 (3 atomes).
    '\\wideparen': 'yhmath',

    # pie charts (pgf-pie)
    '\\pie': 'pgf-pie',

    # etoolbox (dans core)
    '\\ifnumequal': 'etoolbox',
    '\\ifnumgreater': 'etoolbox',
    '\\ifnumless': 'etoolbox',
    '\\ifstrequal': 'etoolbox',
    '\\notblank': 'etoolbox',

    # array / booktabs complément
    '\\extrarowheight': 'array',

    # tkz-euclide complément
    '\\tkzShowLine': 'tkz-euclide',
    '\\tkzPointShowCoord': 'tkz-euclide',
    '\\tkzDefPointsBy': 'tkz-euclide',
    '\\tkzDefRandPointOn': 'tkz-euclide',
    '\\tkzDefRectangle': 'tkz-euclide',
    '\\tkzGetLength': 'tkz-euclide',

    # tabularray complément
    '\\tabulinesep': 'tabularray',

    # amssymb complément (symboles logiques)
    '\\wedge': 'amssymb', '\\vee': 'amssymb',

    # wrapfig
    'wrapfigure': 'wrapfig',
    'wraptable': 'wrapfig',

    # scratch3 complément
    '\\blockspace': 'scratch3',
    '\\ovallist': 'scratch3',
    '\\boolsensing': 'scratch3',
    '\\ovalmove': 'scratch3',
    '\\blockinfloop': 'scratch3',
    '\\blocklist': 'scratch3',
    '\\pencolor': 'scratch3',
    '\\blockstop': 'scratch3',

    # vwcol (vertically-aligned multicolumn)
    'vwcol': 'vwcol',

    # babel-french / ordinaux
    '\\ier': 'babel-french',
    '\\iere': 'babel-french',
    '\\iers': 'babel-french',
    '\\ieres': 'babel-french',
    '\\primo': 'babel-french',
    '\\secundo': 'babel-french',

    # amsmath complément
    '\\cfrac': 'amsmath',
    '\\langle': 'amsmath',
    '\\rangle': 'amsmath',
    '\\lbrace': 'amsmath',
    '\\rbrace': 'amsmath',
    '\\mathbin': 'amsmath',
    '\\Box': 'amssymb',
    '\\square': 'amssymb',

    # hyperref
    '\\href': 'hyperref',
    '\\url': 'hyperref',

    # graphicx
    '\\raisebox': 'graphics',
    '\\height': 'graphics',
    '\\width': 'graphics',
    '\\depth': 'graphics',

    # TeX bas niveau (définitions exotiques d'atomes)
    '\\newdimen': 'tex-primitive',

    # misc usuels
    '\\linewidth': 'tex-primitive', '\\textwidth': 'tex-primitive',
    '\\degre': 'babel-french', '\\ieme': 'babel-french',
    '\\primo': 'babel-french', '\\secundo': 'babel-french',

    # forloop (dans core)
    '\\forloop': 'forloop',

    # datetime
    '\\datemoisannee': 'datetime',

    # environ
    '\\BODY': 'environ',
}


def extraire_macros_definies_localement(texte: str) -> set[str]:
    r"""Retourne les noms de macros définies par l'atome lui-même via
    \newcommand\xxx, \newcommand{\xxx}, \providecommand, \def, etc.

    Détecte aussi :
      - les variables d'itération de \foreach \x/\y/\z in {...}  (tikz)
      - les noms de longueur capturés par \tkzGetLength{nom} → \nom
      - les noms récupérés par \tkzGetPoint{nom} → \nom

    Ces macros, définies/utilisées localement par l'atome, ne sont PAS
    des dépendances externes.
    """
    if not texte:
        return set()
    defs = set()

    # \newcommand\xxx  ou  \newcommand{\xxx}
    pat = re.compile(
        r'\\(?:new|renew|provide|DeclareRobust)command\*?\s*'
        r'(?:\{\s*\\([A-Za-z@]+)\s*\}|\\([A-Za-z@]+))'
    )
    for m in pat.finditer(texte):
        nom = m.group(1) or m.group(2)
        if nom:
            defs.add('\\' + nom)

    # \def\xxx ou \edef, \gdef, \xdef
    for m in re.finditer(r'\\(?:def|edef|gdef|xdef)\\([A-Za-z@]+)', texte):
        defs.add('\\' + m.group(1))

    # \pgfmathsetmacro{\xxx}{...}   \pgfmathdeclarefunction[...]{nom}{...}
    # → définit \xxx localement (utilisé en tikz/pgfplots)
    for m in re.finditer(
        r'\\pgfmath(?:setmacro|parse|truncatemacro)\s*\{\s*\\([A-Za-z@]+)\s*\}',
        texte,
    ):
        defs.add('\\' + m.group(1))

    # \foreach \x/\y/\z in {...} (pgf/tikz) — itérateurs locaux
    for m in re.finditer(r'\\foreach\s+((?:\\[A-Za-z]+\s*/?\s*)+)in\b', texte):
        for var in re.finditer(r'\\([A-Za-z@]+)', m.group(1)):
            defs.add('\\' + var.group(1))

    # \tkzGetLength{nom}, \tkzGetPoint{nom}, \tkzGetFirstPoint{nom}, \tkzGetSecondPoint{nom}
    # définissent une macro \nom utilisable ensuite
    for m in re.finditer(
        r'\\tkzGet(?:Length|Point|FirstPoint|SecondPoint)\s*\{([^}]+)\}',
        texte,
    ):
        nom = m.group(1).strip()
        if re.match(r'^[A-Za-z@]+$', nom):
            defs.add('\\' + nom)

    return defs
# ── Analyse d'un contenu LaTeX ────────────────────────────────────────────────

def extraire_utilisations(texte: str) -> tuple[set[str], set[str]]:
    r"""Retourne (macros, environnements) utilisés dans un texte LaTeX.

    Les macros gardent leur \\ de préfixe. Les environnements non.
    Filtre les primitives LaTeX usuelles.

    Subtilité LaTeX : `\\` est un saut de ligne, pas un début de macro.
    La regex `\\([A-Za-z@]+)` appliquée à `\\Il faut` capturerait
    (à tort) `Il`. On pré-remplace donc `\\` par un marqueur neutre avant
    le matching.
    """
    if not texte:
        return set(), set()
    # Neutraliser les \\ (saut de ligne LaTeX) pour qu'ils ne soient pas
    # confondus avec le début d'une macro.
    texte_nettoye = texte.replace('\\\\', '  ')
    macros = set()
    envs = set()
    for m in re.finditer(r'\\([A-Za-z@]+)', texte_nettoye):
        nom = m.group(1)
        if nom in PRIMITIVES_LATEX:
            continue
        if len(nom) == 1:
            continue
        macros.add('\\' + nom)
    for m in re.finditer(r'\\begin\s*\{([^}]+)\}', texte_nettoye):
        env = m.group(1).strip()
        if env and env not in PRIMITIVES_LATEX:
            envs.add(env)
    return macros, envs
