"""tests/test_v0_53_3_tableau_conversion.py — v0.53.3

Décision de Laurent du 25 octobre 2026 (doc/redemarrage_v0_53_3.md) : une macro
commune de tableau de conversion « pour assurer une mise en forme homogène des
tableaux de conversion » — module seqenseigne-style6e v0.11,
\\seqTableauConversionSix et \\seqLigneConversionSix (forme étoilée : réponse).

Les lots (M03) l'utilisent : l'import doit la reconnaître comme une macro du
module, la compilation doit la trouver dans le .sty livré (régénéré du .dtx),
et la version élève ne doit montrer aucun chiffre d'une ligne réponse.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from outils import import_lot6e as imp
from services import style6e
from tests.test_v0_53_0_mises_en_route import _ecrire_lot, _essai, _lot, base  # noqa: F401

APPLI = Path(__file__).resolve().parent.parent
PAQUET = APPLI / "paquet"
MACROS_TABLEAU = ("seqTableauConversionSix", "seqLigneConversionSix")


def test_macros_du_tableau_de_conversion_dans_le_module_v0_11_et_dans_la_liste_de_l_appli():
    """Sans elles dans MACROS, l'import signalerait le lot M03 (« macros absentes du module ») et
    l'analyse des paquets ne chargerait pas le module pour un atome qui n'utilise qu'un tableau."""
    assert set(MACROS_TABLEAU) <= set(style6e.MACROS)
    assert style6e.VERSION == "v0.11"
    for f in ("seqenseigne-style6e.dtx", "seqenseigne-style6e.sty"):
        src = (PAQUET / f).read_text(encoding="utf-8")
        assert "v0.11 seqenseigne" in src
        for m in MACROS_TABLEAU:
            assert "\\NewDocumentCommand{\\" + m + "}" in src


def test_sty_livre_contient_tout_le_code_du_dtx_pour_le_tableau():
    """Le .sty livré est celui que `tex seqenseigne.ins` produit : le code du .dtx (lignes hors
    commentaire, entre <*package> et </package>) s'y retrouve à l'identique."""
    dtx = (PAQUET / "seqenseigne-style6e.dtx").read_text(encoding="utf-8")
    sty = (PAQUET / "seqenseigne-style6e.sty").read_text(encoding="utf-8")
    debut = dtx.index("% \\subsection{Tableau de conversion (v0.11)}\n% \\begin{macro}")
    code = [l for l in dtx[debut:].splitlines() if l and not l.startswith("%")]
    assert len(code) > 100
    pos = 0
    for l in code:
        pos = sty.index(l, pos)          # dans l'ordre


def test_import_reconnait_les_macros_de_tableau_et_cite_la_version_du_module(base, tmp_path):
    lot = _lot()
    lot["parties"][0]["fiche_cours"]["latex"] += (
        "\n\\centerline{\\seqTableauConversionSix[note]{\\seqLigneConversionSix[x]{0,35}{m}}}")
    lot["exercices_seance"][0]["enonce"] = lot["exercices_seance"][0]["enonce"].replace(
        "\\end{seqCalculMental}",
        "\\seqTableauConversionSix[grandeur=aire]{\\seqLigneConversionSix*{0,0567}{m}}\\par\n"
        "\\end{seqCalculMental}")
    r = _essai(base, _ecrire_lot(tmp_path / "l", lot))
    assert not [a for a in r.anomalies if "macros absentes" in a]
    lot["exercices_seance"][1]["enonce"] += "\\seqTableauDureeSix{}"
    r = _essai(base, _ecrire_lot(tmp_path / "l2", lot))
    absentes = [a for a in r.anomalies if "macros absentes" in a]
    assert absentes and "v0.11" in absentes[0] and "seqTableauDureeSix" in absentes[0]


def _compiler(tmp_path, corps):
    (tmp_path / "t.tex").write_text(
        "\\documentclass{article}\\usepackage[T1]{fontenc}\\usepackage[utf8]{inputenc}"
        "\\usepackage{amssymb}\\usepackage{seqenseigne-style6e}\\begin{document}" + corps
        + "\\end{document}", encoding="utf-8")
    import os
    env = dict(os.environ, TEXINPUTS=f".:{PAQUET}//:")
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "t.tex"], cwd=tmp_path,
                       capture_output=True, env=env)
    return r, (tmp_path / "t.log").read_text(encoding="latin-1")


TABLEAUX = (
    "\\seqTableauConversionSix[prefixes, valeurs, colonne=1.25cm]{}\\par"
    "\\seqTableauConversionSix[note]{\\seqLigneConversionSix[$35$~cm]{0,35}{m}"
    "\\seqLigneConversionSix{812}{cm}}\\par"
    "\\seqTableauConversionSix[grandeur=aire, hectares=ha-a-ca]{"
    "\\seqLigneConversionSix{1,5}{ha}\\seqLigneConversionSix{}{}}\\par"
    "\\seqTableauConversionSix[grandeur=masse]{\\seqLigneConversionSix{1\\,240}{g}}\\par "
    "REPONSES\\seqTableauConversionSix{\\seqLigneConversionSix*{0005,6}{dm}}\\par"
    "\\seqTableauConversionSix[grandeur=aire, compact, colonne=0.7cm]{\\seqLigneConversionSix*{0{,}0567}{m}}")


@pytest.mark.skipif(shutil.which("pdflatex") is None or shutil.which("pdftotext") is None,
                    reason="pdflatex ou pdftotext absent")
@pytest.mark.parametrize("corrige", [False, True])
def test_tableau_de_conversion_compile_et_ligne_reponse_vide_en_version_eleve(tmp_path, corrige):
    """Une ligne réponse (forme étoilée) ne montre ses chiffres qu'en version corrigée : sinon
    l'exercice de séance de M03 donnerait la réponse à l'élève."""
    r, log = _compiler(tmp_path, ("\\seqVersionCorrigee" if corrige else "") + TABLEAUX)
    assert r.returncode == 0 and "! " not in log, log[-2000:]
    txt = subprocess.run(["pdftotext", "-layout", "t.pdf", "-"], cwd=tmp_path, capture_output=True,
                         text=True).stdout
    donnees, reponses = txt.split("REPONSES")
    assert re.search(r"0,\s+3\s+5", donnees) and "kilo" in donnees and re.search(r"1,\s+5", donnees)
    lignes = [l for l in reponses.splitlines() if l.strip() and "km" not in l]
    chiffres = re.findall(r"\d", "\n".join(lignes[:-1]))      # sans en-têtes ni numéro de page
    if corrige:
        assert re.search(r"0\s+0\s+0\s+5,\s+6", reponses) and re.search(r"0,\s+0\s+5\s+6\s+7", reponses)
    else:
        assert chiffres == [], reponses


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex absent")
def test_unite_absente_du_tableau_est_une_erreur_et_chiffres_hors_tableau_un_avertissement(tmp_path):
    r, log = _compiler(tmp_path, "\\seqTableauConversionSix{\\seqLigneConversionSix{3}{ha}}")
    assert "absente du tableau" in log
    r, log = _compiler(tmp_path, "\\seqTableauConversionSix{\\seqLigneConversionSix{123456}{m}}")
    assert r.returncode == 0 and "sortent du tableau" in log.replace("\n", "")
