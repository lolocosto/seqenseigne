r"""services/latex_texte.py — v0.53.2

Échappement LaTeX **commun** des chaînes venues de la base et insérées en
texte dans un document (plan, dossier, livret, fiche…) : intitulés et
critères d'objectifs, titres d'exercices, de fiches, de tests, libellés de
parties, messages de contrôle.

Décision E1 (doc/redemarrage_v0_53_2.md) — anomalie du 25 octobre 2026 :
le plan de séquence de M04 (partie 3) ne compilait pas, « Unicode character
π (U+03C0) », venu du critère F de M04-22 (« … avec π ≈ 3,14 ») inséré tel
quel. Deux corrections possibles :

  - déclarer les caractères par `\newunicodechar` dans le préambule commun
    (`construire_preambule`) : **écarté**, le préambule de tous les
    documents changerait, or le cycle 4 et le principal de 6e doivent
    produire exactement le même `.tex` qu'en v0.53.1 ;
  - **retenu** : convertir, à l'insertion, les caractères Unicode courants
    que pdfLaTeX (inputenc utf8) ne connaît pas en commandes sûres en mode
    texte comme en mode mathématique (`\ensuremath{\pi}`…). Une chaîne qui
    compilait ne change pas (aucun de ces caractères), donc le `.tex` du
    cycle 4 et du principal reste identique ; une chaîne qui ne compilait
    pas est réparée.

Les caractères que le noyau LaTeX convertit déjà lui-même (inputenc utf8,
codages T1/TS1) restent tels quels : × ÷ ° ² ³ ½ ¼ ¾ ± · µ € … ’ « » → ←
‰ (commandes `\texttimes`, `\textdiv`, `\textdegree`, `\texttwosuperior`,
`\textonehalf`… posées par LaTeX) ; un test vérifie qu'ils compilent.

Deux niveaux :

  - `unicode_latex(s)` : la seule conversion Unicode (rien d'autre ne
    change) ; branchée sur les points d'insertion existants des livrets,
    fiches et plans (cycle 4 et 6e), qui laissent passer le LaTeX
    volontaire des intitulés ;
  - `texte_latex(s)` : en plus, `& % # _` échappés hors des formules
    `$…$` (texte simple : plan et dossier des mises en route, contrôle) ;
    une commande déjà échappée (`\%`) n'est pas doublée.
"""

from __future__ import annotations

import re

# Caractères que pdfLaTeX (inputenc utf8) refuse (« Unicode character … not
# set up for use with LaTeX ») → commande sûre en texte et en mathématiques.
_M = r"\ensuremath{%s}"
UNICODE_LATEX: dict[str, str] = {
    # Nombres et relations
    "π": _M % r"\pi", "Π": _M % r"\Pi",
    "≈": _M % r"\approx", "≃": _M % r"\simeq", "∼": _M % r"\sim", "≡": _M % r"\equiv",
    "≠": _M % r"\neq", "≤": _M % r"\leq", "≥": _M % r"\geq",
    "⩽": _M % r"\leq", "⩾": _M % r"\geq",
    "−": _M % "-", "∓": _M % r"\mp", "⋅": _M % r"\cdot", "∗": _M % "*",
    "∞": _M % r"\infty", "√": _M % r"\surd",
    "∈": _M % r"\in", "∉": _M % r"\notin", "∅": _M % r"\emptyset",
    "⊂": _M % r"\subset", "∩": _M % r"\cap", "∪": _M % r"\cup",
    # Géométrie
    "⊥": _M % r"\perp", "∥": _M % r"\parallel", "∠": _M % r"\angle",
    "△": _M % r"\triangle", "′": _M % "{}'", "″": _M % "{}''",
    # Flèches (→ et ← sont connues de LaTeX)
    "↔": _M % r"\leftrightarrow", "⇒": _M % r"\Rightarrow", "⇔": _M % r"\Leftrightarrow",
    "⇐": _M % r"\Leftarrow", "↦": _M % r"\mapsto",
    # Fractions (½ ¼ ¾ sont connues)
    "⅓": _M % r"\frac{1}{3}", "⅔": _M % r"\frac{2}{3}", "⅕": _M % r"\frac{1}{5}",
    "⅛": _M % r"\frac{1}{8}", "⅒": _M % r"\frac{1}{10}",
    # Lettres grecques courantes (μ grec ≠ µ micro, connu)
    "α": _M % r"\alpha", "β": _M % r"\beta", "γ": _M % r"\gamma", "δ": _M % r"\delta",
    "ε": _M % r"\varepsilon", "θ": _M % r"\theta", "λ": _M % r"\lambda", "μ": _M % r"\mu",
    "ρ": _M % r"\rho", "σ": _M % r"\sigma", "φ": _M % r"\varphi", "ω": _M % r"\omega",
    "Δ": _M % r"\Delta", "Σ": _M % r"\Sigma", "Ω": _M % r"\Omega",
}
# Exposants et indices (² ³ sont connus).
for _i, _c in zip((0, 1, 4, 5, 6, 7, 8, 9), "⁰¹⁴⁵⁶⁷⁸⁹"):
    UNICODE_LATEX[_c] = _M % ("{}^{%d}" % _i)
for _i, _c in enumerate("₀₁₂₃₄₅₆₇₈₉"):
    UNICODE_LATEX[_c] = _M % ("{}_{%d}" % _i)
UNICODE_LATEX["⁻"] = _M % "{}^{-}"
UNICODE_LATEX["⁺"] = _M % "{}^{+}"

# Connus du noyau (inputenc utf8, T1/TS1) : laissés tels quels (test).
UNICODE_CONNUS = "×÷°²³½¼¾±·µ€…’«»→←‰"

_RE_UNICODE = re.compile("[" + re.escape("".join(UNICODE_LATEX)) + "]")


def unicode_latex(s: str | None) -> str:
    """Caractères Unicode inconnus de pdfLaTeX → commandes sûres ; rien
    d'autre ne change (chaîne sans ces caractères : identique)."""
    if not s:
        return s or ""
    return _RE_UNICODE.sub(lambda m: UNICODE_LATEX[m.group(0)], s)


_RE_SPECIAUX = re.compile(r"(?<!\\)([&%#_])")


def texte_latex(s: str | None) -> str:
    r"""Texte simple venu de la base → LaTeX : conversion Unicode
    (`unicode_latex`) et `& % # _` échappés hors des formules `$…$` (une
    formule garde ses indices `x_1`) ; un caractère déjà échappé (`\%`)
    n'est pas doublé."""
    if not s:
        return ""
    morceaux = re.split(r"((?<!\\)\$[^$]*(?<!\\)\$)", s)
    out = []
    for i, m in enumerate(morceaux):
        out.append(m if i % 2 else _RE_SPECIAUX.sub(r"\\\1", m))
    return unicode_latex("".join(out))
