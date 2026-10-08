"""services/texte_latex.py — v0.51.1

Conversion d'un court texte LaTeX (titre de notion, nom d'objectif, critère,
nom de thème…) en texte lisible, pour l'appli en ligne qui n'a pas LaTeX.

Couvre les tournures courantes des référentiels : mise en forme (\\textbf,
\\emph…), guillemets (\\og … \\fg), espaces (~, \\,), symboles mathématiques
usuels (\\times, \\leqslant, \\neq…), fractions et racines simples,
exposants et indices courts, caractères échappés (\\%, \\&…). Le reste des
commandes est retiré sans casser le texte. Ce n'est pas un moteur LaTeX :
les formules complexes restent lisibles mais approximatives (la source est
conservée à côté dans le format d'échange).
"""

from __future__ import annotations

import re

_SYMBOLES = {
    "times": "×", "div": "÷", "cdot": "·", "pm": "±", "mp": "∓",
    "leqslant": "⩽", "geqslant": "⩾", "leq": "≤", "geq": "≥", "le": "≤", "ge": "≥",
    "neq": "≠", "ne": "≠", "approx": "≈", "simeq": "≃", "equiv": "≡",
    "infty": "∞", "pi": "π", "alpha": "α", "beta": "β", "gamma": "γ",
    "delta": "δ", "Delta": "Δ", "theta": "θ", "lambda": "λ", "mu": "µ",
    "sigma": "σ", "omega": "ω", "Omega": "Ω",
    "in": "∈", "notin": "∉", "subset": "⊂", "cup": "∪", "cap": "∩",
    "emptyset": "∅", "varnothing": "∅", "mathbb": "", "rightarrow": "→",
    "to": "→", "leftarrow": "←", "Rightarrow": "⇒", "Leftrightarrow": "⇔",
    "ldots": "…", "dots": "…", "cdots": "⋯", "degres": "°", "degre": "°",
    "circ": "°", "%": "%", "euro": "€", "og": "« ", "fg": " »",
    "ie": "i.e.", "eg": "e.g.", "oe": "œ", "ae": "æ", "OE": "Œ", "AE": "Æ",
    "S": "§", "quad": " ", "qquad": " ", "newline": " ", "par": " ",
}
_BINAIRES = set("×÷·±∓⩽⩾≤≥≠≈≃≡∈∉⊂∪∩→←⇒⇔")
_EXPOSANTS = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")
_INDICES = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")
_MISE_EN_FORME = r"textbf|textit|emph|underline|textsc|textrm|textsf|texttt|mathrm|" \
                 r"mathbf|mathit|mathsf|text|mbox|hbox|ensuremath|boxed|fbox|operatorname"


def _exposant(m: re.Match) -> str:
    s = m.group(1) if m.group(1) is not None else m.group(2)
    return s.translate(_EXPOSANTS) if all(c in "0123456789+-=()n" for c in s) else "^" + s


def _indice(m: re.Match) -> str:
    s = m.group(1) if m.group(1) is not None else m.group(2)
    return s.translate(_INDICES) if all(c in "0123456789+-=()" for c in s) else "_" + s


def vers_texte(s: str | None) -> str:
    """Texte LaTeX court → texte lisible (Unicode)."""
    s = s or ""
    if not s:
        return ""
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"(?<!\\)%.*$", "", s)                       # commentaires
    # Caractères échappés.
    for a, b in (("\\%", "%"), ("\\&", "&"), ("\\#", "#"), ("\\_", "_"),
                 ("\\$", "\x00DOLLAR\x00"), ("\\{", "\x00AO\x00"),
                 ("\\}", "\x00AF\x00"), ("\\textbackslash{}", "\\")):
        s = s.replace(a, b)
    s = s.replace("\\,", " ").replace("\\;", " ").replace("\\:", " ").replace("\\ ", " ")
    s = s.replace("~", "\u00a0").replace("--", "–")
    for _ in range(4):                                      # imbrications simples
        s = re.sub(r"\\(?:" + _MISE_EN_FORME + r")\s*\{([^{}]*)\}", r"\1", s)
        s = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"\1/\2", s)
        s = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"√(\1)", s)
        s = re.sub(r"\\overline\s*\{([^{}]*)\}", r"\1", s)
        s = re.sub(r"\\vect\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\^\{([^{}]*)\}|\^(\w)", _exposant, s)
    s = re.sub(r"_\{([^{}]*)\}|_(\w)", _indice, s)
    s = s.replace("$", "")

    def _cmd(m: re.Match) -> str:
        sym = _SYMBOLES.get(m.group(1), "")
        if sym in _BINAIRES:                     # opérateurs et relations : espacés
            return f" {sym} "
        return sym + (" " if sym and m.group(2) else "")
    s = re.sub(r"\\([A-Za-z]+)\*?(\s*)(?:\{\})?", _cmd, s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("\x00DOLLAR\x00", "$").replace("\x00AO\x00", "{").replace("\x00AF\x00", "}")
    s = re.sub(r"«\s+", "«\u00a0", s)
    s = re.sub(r"\s+»", "\u00a0»", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def contient_latex(s: str | None) -> bool:
    return bool(s) and vers_texte(s) != re.sub(r"\s+", " ", s).strip()
