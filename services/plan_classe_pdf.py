"""services/plan_classe_pdf.py — v0.39.0

Impression des plans de classe (LaTeX/TikZ, une page par classe) :
  - si au moins un élève est placé : les noms sur les places (imposés en gras,
    placements à confirmer en italique, places vides avec leur numéro en gris),
    élèves non placés listés sous le plan ;
  - sinon : le plan avec les numéros de place seulement, pour noter à la main.

Mêmes conventions que l'éditeur de salle : cm, y vers le bas, tableau en
haut, angle en degrés sens horaire. TikZ a l'axe y vers le haut et les angles
dans le sens trigonométrique : on prend -y et -angle.
"""

from __future__ import annotations
import math
import subprocess
import tempfile
from pathlib import Path

L, H = 60.0, 40.0          # cm, taille d'une place
LARGEUR_MAX, HAUTEUR_MAX = 17.0, 21.0   # cm disponibles sur la page

_ECHAPPEMENTS = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
                 "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
                 "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


class PdfErreur(Exception):
    pass


def echapper(s: str) -> str:
    return "".join(_ECHAPPEMENTS.get(c, c) for c in (s or ""))


def _coins(p):
    a = math.radians(p["angle"] or 0)
    ca, sa = math.cos(a), math.sin(a)
    return [(p["x"] + u * ca - v * sa, p["y"] + u * sa + v * ca)
            for u, v in ((-L / 2, -H / 2), (L / 2, -H / 2), (L / 2, H / 2), (-L / 2, H / 2))]


def _dateFr(iso: str) -> str:
    a, m, j = iso.split("-")
    return f"{j}/{m}/{a}"


def page_tikz(plan: dict) -> str:
    """Code LaTeX d'une page (plan d'une classe pour une semaine)."""
    places = plan["places"]
    titre = (f"Plan de la salle {echapper(plan['salle']['nom'])} --- "
             f"{echapper(plan['classe']['nom'])} --- semaine du "
             f"{_dateFr(plan['lundi'])}")
    if not places:
        return (f"\\section*{{{titre}}}\n"
                "Le plan de cette salle n'a pas encore de places.\n")
    pts = [c for p in places for c in _coins(p)]
    xmin, xmax = min(x for x, _ in pts), max(x for x, _ in pts)
    ymin, ymax = min(y for _, y in pts), max(y for _, y in pts)
    s = min(LARGEUR_MAX / max(xmax - xmin, 1), HAUTEUR_MAX / max(ymax - ymin + 40, 1))
    X = lambda x: (x - xmin) * s
    Y = lambda y: -(y - ymin) * s
    noms = {e["id"]: e["etiquette"] for e in plan["eleves"]}
    par_num = {p["numero"]: p for p in plan["placements"]}
    avec_noms = bool(par_num)
    lignes = [f"\\section*{{{titre}}}",
              "\\begin{center}\\begin{tikzpicture}"]
    # Tableau, centré au-dessus du plan.
    larg = min(300.0, (xmax - xmin) * 0.5) * s
    cx = X((xmin + xmax) / 2)
    yt = Y(ymin) + 0.9
    lignes.append(f"\\fill[gray!70] ({cx - larg / 2:.3f},{yt:.3f}) rectangle "
                  f"({cx + larg / 2:.3f},{yt + 0.18:.3f});")
    lignes.append(f"\\node[font=\\footnotesize, gray] at ({cx:.3f},{yt - 0.25:.3f}) {{Tableau}};")
    lw, lh = L * s, H * s
    for p in places:
        x, y, a = X(p["x"]), Y(p["y"]), -(p["angle"] or 0)
        lignes.append(f"\\draw[rotate around={{{a:.1f}:({x:.3f},{y:.3f})}}] "
                      f"({x - lw / 2:.3f},{y - lh / 2:.3f}) rectangle "
                      f"({x + lw / 2:.3f},{y + lh / 2:.3f});")
        pl = par_num.get(p["numero"])
        if pl:
            nom = noms.get(pl["eleve_id"], "?")
            if " " in nom:
                prenom, reste = nom.split(" ", 1)
                txt = f"{echapper(prenom)}\\\\{echapper(reste)}"
            else:
                txt = echapper(nom)
            if pl["statut"] == "impose":
                txt = f"\\textbf{{{txt}}}"
            elif not pl.get("confirme", 1):
                txt = f"\\textit{{{txt}}}"
            lignes.append(f"\\node[font=\\tiny, align=center, text width={lw:.3f}cm, "
                          f"inner sep=0pt] at ({x:.3f},{y:.3f}) {{{txt}}};")
        else:
            couleur = ", gray" if avec_noms else ""
            lignes.append(f"\\node[font=\\scriptsize{couleur}] at ({x:.3f},{y:.3f}) "
                          f"{{{p['numero']}}};")
    lignes.append("\\end{tikzpicture}\\end{center}")
    if avec_noms:
        non = [echapper(noms[e]) for e in plan["non_places"] if e in noms]
        if non:
            lignes.append("\\noindent\\textbf{Non placés :} " + " ; ".join(non) + "\\par")
        lignes.append("\\noindent{\\footnotesize\\textbf{Gras} : placé par "
                      "l'enseignant ; \\textit{italique} : place libre à confirmer.}")
    return "\n".join(lignes)


def document(plans: list[dict]) -> str:
    pages = "\n\\newpage\n".join(page_tikz(p) for p in plans) or \
        "Aucun plan de classe pour cette salle cette semaine."
    return ("\\documentclass[11pt]{article}\n"
            "\\usepackage[utf8]{inputenc}\n\\usepackage[T1]{fontenc}\n"
            "\\usepackage[a4paper,margin=1.5cm]{geometry}\n"
            "\\usepackage{tikz}\n\\pagestyle{empty}\n"
            "\\begin{document}\n" + pages + "\n\\end{document}\n")


def compiler(tex: str, pdflatex: str | None, timeout: int = 60) -> bytes:
    if not pdflatex:
        raise PdfErreur("pdflatex introuvable : impossible de produire le PDF.")
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "plan.tex").write_text(tex, encoding="utf-8")
        try:
            proc = subprocess.run([pdflatex, "-interaction=nonstopmode",
                                   "-halt-on-error", "plan.tex"],
                                  cwd=d, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise PdfErreur(f"Compilation interrompue après {timeout} s.")
        pdf = d / "plan.pdf"
        if proc.returncode != 0 or not pdf.is_file():
            log = (d / "plan.log").read_text(encoding="utf-8", errors="replace") \
                if (d / "plan.log").is_file() else ""
            erreurs = [l for l in log.splitlines() if l.startswith("!")][:3]
            raise PdfErreur("Échec de la compilation LaTeX. " + " ".join(erreurs))
        return pdf.read_bytes()
