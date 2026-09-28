"""services/planning_automatismes_tex.py — v0.24.1

Génère le source LaTeX du planning d'automatismes (Leitner), en « frise
chronologique » A3 paysage :
  - une ligne (retour à la ligne automatique) par période de cours ;
  - chaque date dans une boîte (\\fbox), avec sous elle les enveloppes à réviser
    (①②③④ via pifont), ou « férié », ou ∅ (indisponibilité) ;
  - une bande centrée entre deux barres horizontales pour chaque vacances ;
  - interligne augmenté pour la lisibilité.

Entrée : blocs produits par services.planning_leitner_detaille.assembler.
"""

from __future__ import annotations

_PI = {1: r"\ding{192}", 2: r"\ding{193}", 3: r"\ding{194}", 4: r"\ding{195}"}


def _esc(s: str) -> str:
    s = str(s or "")
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
                 ("}", r"\}"), ("~", r"\textasciitilde{}"),
                 ("^", r"\textasciicircum{}")):
        s = s.replace(a, b)
    return s


def _case_jour(jour: dict) -> str:
    """Une « case » de largeur fixe : date encadrée (\\fbox) en haut, contenu
    (enveloppes / marqueur) en dessous, centrés. Emballée dans une \\parbox de
    largeur fixe pour un alignement régulier et un retour à la ligne propre."""
    date_txt = _esc(jour.get("jour_court", ""))
    cr = jour.get("creneau_code", "")
    if cr:
        date_txt = date_txt + r" \textbf{" + _esc(cr) + r"}"
    kind = jour.get("kind")
    if kind == "seance":
        env = jour.get("enveloppes", [])
        contenu = " ".join(_PI.get(e, str(e)) for e in env) if env else "--"
    elif kind == "ferie":
        contenu = r"\textit{\footnotesize férié}"
    elif kind == "indispo":
        contenu = r"{\large $\varnothing$}"
    else:
        contenu = ""
    # parbox de largeur fixe = colonne régulière ; \fbox autour de la date.
    # Interligne SERRÉ à l'intérieur (linespread 1) pour que les enveloppes
    # restent visuellement collées à LEUR date ; l'air entre rangées est géré
    # au niveau du paragraphe (voir generer_planning_tex).
    return (r"\parbox[t]{2.4cm}{\linespread{1}\selectfont\centering "
            r"\fbox{\footnotesize " + date_txt + r"}\\[1pt]"
            + contenu + r"}")


def _bande_vacances(nom: str) -> str:
    return (r"\par\medskip\noindent\rule{\linewidth}{0.5pt}\par"
            r"\smallskip\centerline{\small\textbf{\textit{" + _esc(nom)
            + r"}}}\smallskip\noindent\rule{\linewidth}{0.5pt}\par\medskip")


def generer_planning_tex(classe_nom: str, annee: str, blocs: list) -> str:
    corps_parts = []
    for b in blocs:
        if b.get("type") == "vacances":
            corps_parts.append(_bande_vacances(b.get("nom", "Vacances")))
        elif b.get("type") == "periode":
            cases = [_case_jour(j) for j in b.get("jours", [])]
            # Les parbox sont séparées par un espace + \penalty0 (autorise la
            # coupure). L'air ENTRE LES RANGÉES vient d'un \baselineskip large :
            # comme chaque case fait ~2 lignes de haut, on met un interligne de
            # rangée confortable sans espacer date↔enveloppes (géré en interne).
            corps = "%\n\\hspace{2mm}\\penalty0 ".join(cases)
            corps_parts.append(
                r"{\sloppy\setlength{\baselineskip}{34pt}\noindent "
                + corps + r"\par}")
    corps = "\n".join(corps_parts)

    return (
        r"\documentclass[a3paper,landscape,11pt]{article}"
        r"\usepackage[utf8]{inputenc}"
        r"\usepackage[T1]{fontenc}"
        r"\usepackage[french]{babel}"
        r"\usepackage{pifont}"
        r"\usepackage{amssymb}"
        r"\usepackage[margin=1cm]{geometry}"
        r"\setlength{\parindent}{0pt}"
        r"\pagestyle{empty}"
        r"\begin{document}"
        r"\begin{center}"
        r"{\LARGE\textbf{Planning des automatismes (Leitner)}}\par"
        r"\vspace{2pt}{\large " + _esc(classe_nom) + r" --- ann\'ee "
        + _esc(annee) + r"}\par"
        r"\vspace{3pt}{\small Enveloppes \`a r\'eviser : "
        r"\ding{192} chaque s\'eance \quad \ding{193} une s\'eance sur deux "
        r"\quad \ding{194} une sur quatre \quad \ding{195} une sur huit "
        r"\quad $\varnothing$ = indisponible}"
        r"\end{center}\vspace{8pt}"
        + corps +
        r"\end{document}"
    )
