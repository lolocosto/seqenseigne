"""services/planning_mer_tex.py — v0.26.1

Génère le source LaTeX du planning de progression MER en « frise
chronologique » A3 paysage, sur le même modèle que le planning des automatismes.
Sous chaque date : le libellé de la partie MER travaillée ce jour-là (avec son
rang n/N), ou « férié » / ∅ (indisponibilité), ou « — » si la progression est
épuisée.

Entrée : blocs produits par services.planning_mer_detaille.assembler.
"""

from __future__ import annotations


def _esc(s: str) -> str:
    s = str(s or "")
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
                 ("}", r"\}"), ("~", r"\textasciitilde{}"),
                 ("^", r"\textasciicircum{}")):
        s = s.replace(a, b)
    return s


def _case_jour(jour: dict) -> str:
    date_txt = _esc(jour.get("jour_court", ""))
    cr = jour.get("creneau_code", "")
    if cr:
        date_txt = date_txt + r" \textbf{" + _esc(cr) + r"}"
    kind = jour.get("kind")
    if kind == "ferie":
        contenu = r"\textit{\footnotesize férié}"
    elif kind == "indispo":
        contenu = r"{\large $\varnothing$}"
    elif kind == "seance":
        if jour.get("epuise"):
            contenu = r"\textit{\footnotesize --}"
        else:
            lib = _esc(jour.get("mer_libelle", ""))
            rang = jour.get("mer_rang", 0)
            nb = jour.get("mer_nb", 0)
            compteur = (r"{\scriptsize (" + str(rang) + "/" + str(nb) + ")}"
                        if rang and nb else "")
            contenu = r"{\scriptsize " + lib + r"}\\" + compteur
    else:
        contenu = ""
    return (r"\parbox[t]{2.7cm}{\linespread{1}\selectfont\centering "
            r"\fbox{\footnotesize " + date_txt + r"}\\[1pt]"
            + contenu + r"}")


def _bande_vacances(nom: str) -> str:
    return (r"\par\medskip\noindent\rule{\linewidth}{0.5pt}\par"
            r"\smallskip\centerline{\small\textbf{\textit{" + _esc(nom)
            + r"}}}\smallskip\noindent\rule{\linewidth}{0.5pt}\par\medskip")


def generer_planning_tex(classe_nom: str, annee: str, ref_nom: str,
                         blocs: list) -> str:
    corps_parts = []
    for b in blocs:
        if b.get("type") == "vacances":
            corps_parts.append(_bande_vacances(b.get("nom", "Vacances")))
        elif b.get("type") == "periode":
            cases = [_case_jour(j) for j in b.get("jours", [])]
            corps = "%\n\\hspace{2mm}\\penalty0 ".join(cases)
            corps_parts.append(
                r"{\sloppy\setlength{\baselineskip}{40pt}\noindent "
                + corps + r"\par}")
    corps = "\n".join(corps_parts)

    sous_titre = (r" --- réf. " + _esc(ref_nom)) if ref_nom else ""
    return (
        r"\documentclass[a3paper,landscape,11pt]{article}"
        r"\usepackage[utf8]{inputenc}"
        r"\usepackage[T1]{fontenc}"
        r"\usepackage[french]{babel}"
        r"\usepackage{amssymb}"
        r"\usepackage[margin=1cm]{geometry}"
        r"\setlength{\parindent}{0pt}"
        r"\pagestyle{empty}"
        r"\begin{document}"
        r"\begin{center}"
        r"{\LARGE\textbf{Planning de progression MER}}\par"
        r"\vspace{2pt}{\large " + _esc(classe_nom) + r" --- ann\'ee "
        + _esc(annee) + sous_titre + r"}\par"
        r"\vspace{3pt}{\small Sous chaque date : la partie travaill\'ee "
        r"(rang dans la partie). $\varnothing$ = indisponible.}"
        r"\end{center}\vspace{8pt}"
        + corps +
        r"\end{document}"
    )


def generer_planning_theorique_tex(niveau: str, annee: str, ref_nom: str,
                                   parties: list) -> str:
    """Planning THÉORIQUE (niveau) : les parties posées avec leur plage de
    numéros de séance (sans dates réelles). Une ligne par partie."""
    lignes = []
    debut = 1
    for p in parties:
        nb = int(p.get("nb_seances", 0) or 0)
        fin = debut + nb - 1
        plage = f"séances {debut}" + (f"–{fin}" if nb > 1 else "")
        seq = _esc(p.get("sequence_nom", "") or p.get("sequence_code", ""))
        lignes.append(
            r"\item \textbf{" + _esc(p.get("libelle", "")) + r"} "
            r"{\small(" + seq + r")} \hfill {\small " + plage
            + r" \quad (" + str(nb) + r" séance" + ("s" if nb > 1 else "")
            + r")}")
        debut = fin + 1
    total = debut - 1
    corps = ("\\begin{itemize}\n" + "\n".join(lignes) + "\n\\end{itemize}"
             if lignes else r"\textit{Aucune partie posée.}")
    sous = (r" --- réf. " + _esc(ref_nom)) if ref_nom else ""
    return (
        r"\documentclass[a4paper,11pt]{article}"
        r"\usepackage[utf8]{inputenc}\usepackage[T1]{fontenc}"
        r"\usepackage[french]{babel}\usepackage[margin=2cm]{geometry}"
        r"\pagestyle{empty}\begin{document}"
        r"\begin{center}{\LARGE\textbf{Progression MER — planning théorique}}\par"
        r"\vspace{2pt}{\large niveau " + _esc(niveau) + r" --- ann\'ee "
        + _esc(annee) + sous + r"}\par\vspace{2pt}"
        r"{\small Total : " + str(total) + r" séance(s). Les dates réelles "
        r"dépendent de l'emploi du temps de chaque classe.}\end{center}"
        r"\vspace{8pt}" + corps + r"\end{document}"
    )
