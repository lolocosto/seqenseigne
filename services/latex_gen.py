"""
services/latex_gen.py — Génération du source LaTeX d'un livret de séquence.
Aucune dépendance Flask ni I/O.
"""

from __future__ import annotations


def generer_livret_tex(niveau: str, seq: str,
                       raw_seq: dict, seq_data: dict) -> str:
    """
    Génère le texte LaTeX complet d'un livret depuis les données YAML.

    niveau   : ex. "N11"
    seq      : ex. "S01"
    raw_seq  : dict brut extrait du YAML (paquets, prerequis, notions avec fichier…)
    seq_data : dict normalisé (objectifs avec exercices)
    """
    lines = []
    niveau_prec = f"N{int(niveau[1:]) - 1:02d}"   # N11 → N10

    # ── En-tête ────────────────────────────────────────────────────────────────
    lines.append(r"\documentclass[a4paper,11pt]{article}")
    lines.append(r"\usepackage{seqenseigne}")
    for pkg in raw_seq.get("paquets_supplementaires", []):
        lines.append(pkg)
    lines.append("")
    lines.append(r"\begin{document}")

    # ── Chemins et données ────────────────────────────────────────────────────
    lines.append(f"\t\\seqDefChemin{{{{../exercices}}{{../../{niveau_prec}/exercices}}}}")
    lines.append(r"\t\seqSetDataPath{../../}")
    lines.append(r"\t\seqLoadData")
    lines.append(f"\t\\seqSetCodeNiveau{{{niveau}}}\\seqSetCodeSequence{{{seq}}}")
    lines.append(r"\t\seqTitreLivret[corriges=non]")
    lines.append(f"\t\\seqTableauPrerequis[niveau={niveau},sequence={seq}]")

    # ── Révisions (seqSerieExos{0}) ───────────────────────────────────────────
    rev_exos = raw_seq.get("prerequis", {}).get("exercices_revision", [])
    if rev_exos:
        lines.append(r"\t\begin{seqSerieExos}{0}")
        for n in sorted(rev_exos):
            lines.append(f"\t\t\\input{{{niveau_prec}{seq}A{n:02d}.tex}}")
        lines.append(r"\t\end{seqSerieExos}")

    # ── Objectifs ─────────────────────────────────────────────────────────────
    lines.append(
        f"\t\\seqTitreSection{{Objectifs}}"
        f"\\seqTableauObjectifs[niveau={niveau},sequence={seq}]"
    )

    # ── Notions / méthodes ────────────────────────────────────────────────────
    obj_notions = [
        n["fichier"]
        for obj in raw_seq.get("objectifs", [])
        for n in obj.get("notions", [])
        if isinstance(n, dict) and "fichier" in n
    ]
    if obj_notions:
        lines.append(r"\t\seqTitreSection{Cours}")
        for f in obj_notions:
            lines.append(f"\t\\input{{{f}}}")
    else:
        lines.append(r"\t\seqTitreSection{Connaissances}\input{Include/Connaissances.tex}")
        lines.append(r"\t\seqTitreSection{Savoir-faire}\input{Include/Savoir-faire.tex}")

    # ── Exercices par série ───────────────────────────────────────────────────
    exos_F, exos_A, exos_E, exos_AP = [], [], [], []
    for obj in seq_data["objectifs"]:
        if obj.get("is01"):
            continue
        ex = obj["exercices"]
        exos_F.extend(ex.get("fondamental", ex.get("F", [])))
        exos_A.extend(ex.get("avancé",      ex.get("A", [])))
        exos_E.extend(ex.get("exploration", ex.get("E", [])))
        exos_AP.extend(ex.get("approche",   ex.get("AE", [])))

    exos_F  = sorted(set(exos_F))
    exos_A  = sorted(set(exos_A))
    exos_E  = sorted(set(exos_E))
    exos_AP = sorted(set(exos_AP))

    if exos_F:
        lines.append(r"\t\begin{seqSerieExos}{1}")
        for n in exos_F:
            lines.append(f"\t\t\\input{{{niveau}{seq}F{n:02d}.tex}}")
        lines.append(r"\t\end{seqSerieExos}")

    if exos_A:
        lines.append(r"\t\begin{seqSerieExos}{2}")
        for n in exos_A:
            lines.append(f"\t\t\\input{{{niveau}{seq}A{n:02d}.tex}}")
        lines.append(r"\t\end{seqSerieExos}")

    if exos_AP:
        lines.append(r"\t\begin{seqSerieExos}{4}")
        for n in exos_AP:
            lines.append(f"\t\t\\input{{{niveau}{seq}AE{n:02d}.tex}}")
        lines.append(r"\t\end{seqSerieExos}")

    if exos_E:
        lines.append(r"\t\begin{seqSerieExos}{3}")
        for n in exos_E:
            lines.append(f"\t\t\\input{{{niveau}{seq}E{n:02d}.tex}}")
        lines.append(r"\t\end{seqSerieExos}")

    lines.append(r"\t\seqAfficheAnnexes")
    lines.append(r"\t\seqAfficheCorriges")
    lines.append(r"\end{document}")

    return "\n".join(lines)
