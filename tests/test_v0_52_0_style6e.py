"""tests/test_v0_52_0_style6e.py — v0.52.0 (correctif 2)

Livret N09 de Laurent (18 octobre) : « Undefined control sequence
\\seqLocCellule ». Le module seqenseigne-style6e n'est pas importé par
« Import mise en forme » (parseur prévu pour les modules du cycle 4) : il est
chargé en entier par \\usepackage dès qu'une de ses macros est utilisée, et le
dossier du paquet est mis dans le TEXINPUTS. Deux défauts croisés sur le même
livret sont aussi couverts : dossier Remediation/ absent, titre de section de
fiche avec virgule.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from services import style6e
from services.compilateur_pdf import compiler_atome, dossier_paquet_effectif
from services.latex_rendu_atome import Atome, _analyser_paquets_utilises
from services.paquet_parseur import MACROS_PAQUETS_EXTERNES

APPLI = Path(__file__).resolve().parent.parent


def _atome(corps):
    return Atome(id="x", type_atome="exercice", niveau="N09", sequence="S01",
                 fichier="", corps=corps)


def test_macro_du_module_6e_demande_le_paquet_entier_car_le_parseur_ne_le_lit_pas():
    assert _analyser_paquets_utilises(_atome(r"\tikz\node{\seqLocCellule{7}};")) \
        >= {"seqenseigne-style6e"}


def test_environnement_du_module_6e_demande_aussi_le_paquet():
    assert "seqenseigne-style6e" in _analyser_paquets_utilises(
        _atome(r"\begin{seqExoSix}[O] x \end{seqExoSix}"))


def test_atome_du_cycle_4_ne_charge_pas_le_module_6e():
    assert "seqenseigne-style6e" not in _analyser_paquets_utilises(
        _atome(r"\begin{seqExercice} \seqCorrige{x} \end{seqExercice}"))


def test_noms_du_module_6e_ne_masquent_aucune_correspondance_existante():
    """Un nom déjà mappé vers un autre paquet changerait le rendu existant."""
    for nom in style6e.correspondances():
        assert MACROS_PAQUETS_EXTERNES[nom] == style6e.NOM_PAQUET


@pytest.mark.skipif(not (APPLI / "paquet" / "seqenseigne-style6e.dtx").is_file(),
                    reason="module 6e absent du dossier paquet/")
def test_liste_des_noms_identique_au_dtx_du_paquet():
    src = (APPLI / "paquet" / "seqenseigne-style6e.dtx").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.startswith("%"))
    envs = set(re.findall(r"\\(?:NewDocumentEnvironment|newtcolorbox|newenvironment)\{(\w+)\}", code))
    macros = {m for m in re.findall(r"\\(?:NewDocumentCommand|newcommand|DeclareRobustCommand)"
                                    r"\*?\{?\\([A-Za-z@]+)", code) if "@" not in m}
    assert envs == set(style6e.ENVIRONNEMENTS)
    assert macros <= set(style6e.MACROS)


def test_dossier_paquet_par_defaut_a_cote_de_appli(tmp_path):
    (tmp_path / "reference" / "paquet").mkdir(parents=True)
    (tmp_path / "appli").mkdir()
    assert dossier_paquet_effectif(None, tmp_path / "appli") == \
        (tmp_path / "reference" / "paquet").resolve()
    assert dossier_paquet_effectif(None, tmp_path / "x" / "appli") is None
    assert dossier_paquet_effectif(tmp_path / "absent", tmp_path / "appli") is None


def test_compilation_cree_remediation_et_met_le_paquet_dans_texinputs(tmp_path, monkeypatch):
    (tmp_path / "reference" / "paquet").mkdir(parents=True)
    (tmp_path / "appli").mkdir()
    vu = {}

    def faux_run(cmd, **kw):
        cwd = Path(kw.get("cwd"))
        vu["remediation"] = (cwd / "Remediation").is_dir()
        vu["texinputs"] = kw["env"]["TEXINPUTS"]
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr(subprocess, "run", faux_run)
    compiler_atome(r"\documentclass{article}\begin{document}x\end{document}",
                   pdflatex="pdflatex", racine_appli=tmp_path / "appli",
                   workdir=tmp_path / "w")
    assert vu["remediation"]
    assert str((tmp_path / "reference" / "paquet").resolve()) in vu["texinputs"]


def test_titre_de_section_de_fiche_avec_virgule_entre_accolades_les_autres_inchanges():
    from services.latex_rendu_atome import generer_corps_fiche
    a = Atome(id="f", type_atome="fiche", niveau="N09", sequence="S03", fichier="",
              titre="Calcul",
              sections=[{"titre": "1. Multiplier par 10, 100, 1 000", "items": ["x"]},
                        {"titre": "Définition", "items": ["y"]}])
    tex = generer_corps_fiche(a)
    assert "[titre={1. Multiplier par 10, 100, 1 000}]" in tex
    assert "[titre=Définition]" in tex
