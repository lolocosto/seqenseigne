"""tests/test_v0_54_3_tableau_decimal.py — v0.54.3

Demande de Laurent du 12 novembre 2026 (doc/redemarrage_v0_54_3.md) : les tableaux de
décomposition de la fiche de cours de S01 incluent les classes des millions et des milliards.
Module seqenseigne-style6e v0.12 : \\seqLocTableauDecimal[4]{lignes} (milliards, millions,
milliers, unités, virgule, partie décimale ; 16 cellules par ligne).

Décision D-OPTION : argument optionnel plutôt qu'une macro sœur. La forme sans argument
(lots S01 exercices, S02, S03) garde exactement son code et son rendu : son corps est passé
tel quel dans \\seqLoc@TableauDecimalDeux.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from services import style6e
from services.livret_sequence_6e import GEOMETRIE_6E

APPLI = Path(__file__).resolve().parent.parent
PAQUET = APPLI / "paquet"

# Corps de \seqLocTableauDecimal en v0.11 (seqenseigne v0.54.2), recopié à l'identique.
CORPS_V0_11 = r"""  \begin{center}\renewcommand{\arraystretch}{1.25}\small
  \begin{tabular}{|*{3}{>{\columncolor{seqLocMilliers!45}\centering\arraybackslash}p{0.62cm}|}%
      *{3}{>{\columncolor{seqLocUnites!45}\centering\arraybackslash}p{0.62cm}|}>{\centering\arraybackslash}p{0.2cm}|%
      *{3}{>{\columncolor{seqLocDecimale!60}\centering\arraybackslash}p{0.62cm}|}}
  \hline
  \multicolumn{3}{|c|}{\cellcolor{seqLocMilliers}\bfseries Milliers}&
  \multicolumn{3}{c|}{\cellcolor{seqLocUnites}\bfseries Unités}& &
  \multicolumn{3}{c|}{\cellcolor{seqLocDecimale}\bfseries Partie décimale}\\ \hline
  \seqLoc@rot{centaines}&\seqLoc@rot{dizaines}&\seqLoc@rot{unités}&
  \seqLoc@rot{centaines}&\seqLoc@rot{dizaines}&\seqLoc@rot{unités}& &
  \seqLoc@rot{dixièmes}&\seqLoc@rot{centièmes}&\seqLoc@rot{millièmes}\\ \hline
  #1
  \end{tabular}\end{center}}
"""


def _src(nom):
    return (PAQUET / nom).read_text(encoding="utf-8")


def test_module_v0_12_et_tableau_decimal_toujours_dans_la_liste_de_l_appli():
    """Sans la version à jour, l'import citerait une version du module qui n'a pas la forme [4]."""
    assert style6e.VERSION == "v0.12"
    assert "seqLocTableauDecimal" in style6e.MACROS
    for f in ("seqenseigne-style6e.dtx", "seqenseigne-style6e.sty"):
        assert "v0.12 seqenseigne" in _src(f)


@pytest.mark.parametrize("fichier", ["seqenseigne-style6e.dtx", "seqenseigne-style6e.sty"])
def test_forme_sans_option_garde_le_corps_v0_11_pour_ne_pas_changer_les_lots_s01_a_s03(fichier):
    """Les exercices de S01, S02 et S03 écrivent \\seqLocTableauDecimal{…} : leur rendu ne doit
    pas changer. Le corps v0.11 est repris caractère pour caractère, et la macro publique
    renvoie vers lui par défaut (argument optionnel 2)."""
    src = _src(fichier)
    assert "\\newcommand{\\seqLoc@TableauDecimalDeux}[1]{%\n" + CORPS_V0_11 in src
    assert "\\newcommand{\\seqLocTableauDecimal}[2][2]{%" in src
    assert "\\newcommand{\\seqLocTableauDecimal}[1]" not in src


def test_tableau_a_quatre_classes_a_seize_colonnes_et_les_couleurs_des_classes():
    """4 classes × 3 rangs + virgule + 3 rangs décimaux = 16 colonnes ; milliards en blanc comme
    dans \\seqLocTableauNumeration (seqLocMilliards), millions en seqLocMillions."""
    src = _src("seqenseigne-style6e.sty")
    debut = src.index("\\newcommand{\\seqLoc@TableauDecimalQuatre}")
    fin = src.index("\\end{tabular}\\end{center}}", debut)
    bloc = src[debut:fin]
    pre = bloc[bloc.index("\\begin{tabular}"):bloc.index("\\hline")]
    groupes = re.findall(r"\*\{(\d)\}\{>\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}p\{", pre)
    n = sum(int(k) for k in groupes) + pre.count("p{") - len(groupes)
    assert len(groupes) == 5 and n == 16, pre
    assert "\\definecolor{seqLocMilliards}{HTML}{FFFFFF}" in src
    for c in ("seqLocMilliards", "seqLocMillions", "seqLocMilliers", "seqLocUnites", "seqLocDecimale"):
        assert "\\cellcolor{" + c + "}" in bloc
    assert bloc.count("\\seqLoc@rotq{") == 15


def test_sty_livre_contient_le_code_du_dtx_pour_le_tableau_decimal():
    """Le .sty livré est celui que `tex seqenseigne.ins` produit à partir du .dtx."""
    dtx, sty = _src("seqenseigne-style6e.dtx"), _src("seqenseigne-style6e.sty")
    debut = dtx.index("%% \\seqLocTableauDecimal[classes]{lignes} (v0.12)")
    fin = dtx.index("%% --- Hiéroglyphes", debut)
    code = [l for l in dtx[debut:fin].splitlines() if l and not l.startswith("% ")]
    assert len(code) > 40
    pos = 0
    for l in code:
        pos = sty.index(l, pos)


def _compiler(tmp_path, corps):
    (tmp_path / "t.tex").write_text(
        "\\documentclass[11pt,a4paper]{article}\\usepackage[T1]{fontenc}\\usepackage[utf8]{inputenc}"
        "\\usepackage{amssymb}\\usepackage{geometry}\\usepackage{seqenseigne-style6e}"
        + GEOMETRIE_6E + "\\renewcommand{\\familydefault}{\\sfdefault}\\begin{document}" + corps
        + "\\end{document}", encoding="utf-8")
    env = dict(os.environ, TEXINPUTS=f".:{PAQUET}//:")
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "t.tex"], cwd=tmp_path,
                       capture_output=True, env=env)
    return r, (tmp_path / "t.log").read_text(encoding="latin-1")


LIGNE_4 = " & & & & & & & & 5 & 0 & 4 & 8 & , & 3 & 7 & 2\\\\ \\hline"


@pytest.mark.skipif(shutil.which("pdflatex") is None or shutil.which("pdftotext") is None,
                    reason="pdflatex ou pdftotext absent")
def test_tableau_a_quatre_classes_tient_dans_une_fiche_de_cours(tmp_path):
    """Le tableau à 4 classes doit tenir dans la largeur d'une fiche de résumé (géométrie des
    documents de 6e) : aucune boîte trop large, et les noms des classes sont imprimés."""
    r, log = _compiler(tmp_path, "\\seqVersionComplete\\begin{seqFicheResumeSix}{Essai}"
                       "\\seqLocTableauDecimal[4]{" + LIGNE_4 + "}"
                       "\\seqLocTableauDecimal{ & & 5 & 0 & 4 & 8 & , & 3 & 7 & 2\\\\ \\hline}"
                       "\\end{seqFicheResumeSix}")
    assert r.returncode == 0 and "! " not in log, log[-2000:]
    assert "Overfull" not in log
    txt = subprocess.run(["pdftotext", "-layout", "t.pdf", "-"], cwd=tmp_path, capture_output=True,
                         text=True).stdout
    assert txt.count("Milliards") == 1 and txt.count("Millions") == 1
    assert txt.count("Milliers") == 2 and txt.count("Partie décimale") == 2


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex absent")
def test_nombre_de_classes_autre_que_2_ou_4_est_une_erreur(tmp_path):
    """Une valeur inattendue ne doit pas donner silencieusement un tableau faux."""
    r, log = _compiler(tmp_path, "\\seqLocTableauDecimal[3]{ & & 5 & 0 & 4 & 8 & , & 3 & 7 & 2\\\\ \\hline}")
    assert "2 ou 4 classes seulement" in log.replace("\n", "")
