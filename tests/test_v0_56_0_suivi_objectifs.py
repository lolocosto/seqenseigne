"""tests/test_v0_56_0_suivi_objectifs.py — v0.56.0

Module seqenseigne-style6e v0.14 (Laurent, 13 novembre 2026 ; doc/redemarrage_v0_56_0.md) :

1. SUIVI — page de garde du livret 6e (modèle Fiches) : « suivi par objectif », une ligne
   par objectif, cases « Je découvre », « Je m'entraîne », « Je sais faire », note du test
   court sur 10 ; même texte en élève et corrigé ; une page au plus ;
2. fiche de résumé insécable (« quitte à perdre le bas de la page ») ;
3. carte mentale à sa taille naturelle (voir aussi test_v0_55_0) ;
4. \\seqSepColonnesSix, trait entre deux colonnes d'un énoncé (S06 A05) ;
5. la liste de l'appli connaît les nouvelles macros (sinon l'import des lots refuse
   « macro inconnue » et l'analyse des paquets ne charge pas le module).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import style6e  # noqa: E402
from tests.test_v0_52_2_documents_6e import app_6e  # noqa: E402,F401

PAQUET = Path(__file__).parent.parent / "paquet"
DTX = PAQUET / "seqenseigne-style6e.dtx"
STY = PAQUET / "seqenseigne-style6e.sty"
TBLR = ["booktabs", "varwidth"]
NOUVELLES = ("seqSuiviObjectifsSix", "seqPartieSuiviSix", "seqSepColonnesSix")


def _src(p):
    return p.read_text(encoding="utf-8")


def _seq(nb_parties=2, nb_objectifs=2, nom="Opérations"):
    return {"code": "S03", "nom": nom, "theme_couleur": "nombres", "parties": [
        {"numero": n, "libelle": f"Titre {n}", "objectifs": [
            {"code": f"{n}{i}", "nom": f"Objectif {n}.{i}"} for i in range(nb_objectifs)]}
        for n in range(1, nb_parties + 1)]}


# ── 5. Module v0.14 et liste de l'appli ─────────────────────────────────────

def test_module_v0_14_definit_les_nouvelles_macros_et_l_appli_les_connait():
    assert style6e.VERSION == "v0.14"
    assert set(NOUVELLES) <= set(style6e.MACROS)
    for f in (DTX, STY):
        src = _src(f)
        assert "v0.14 seqenseigne" in src
        for m in NOUVELLES:
            assert "\\NewDocumentCommand{\\" + m + "}" in src, (f.name, m)


def test_ancienne_forme_de_la_page_de_garde_gardee_pour_les_tex_deja_produits():
    """Les aperçus des lots et les documents figés appellent encore \\seqPartieCouvertureSix."""
    assert "\\newcommand{\\seqPartieCouvertureSix}[2]" in _src(STY)
    assert "seqPartieCouvertureSix" in style6e.MACROS


# ── 1. SUIVI ────────────────────────────────────────────────────────────────

def test_page_de_garde_une_ligne_de_suivi_par_objectif_rangee_par_partie():
    """Décision de Laurent (13 novembre) : les collègues trouvaient la page de garde vide."""
    from services.livret_sequence_6e import couverture
    tex = couverture(_seq())
    assert r"\seqCouvertureLivretSix*{Opérations}{%" "\n" r"\seqSuiviObjectifsSix{%" in tex
    assert (r"\seqPartieSuiviSix{Partie 1 --- Titre 1}{S03-10/{Objectif 1.0},"
            r"S03-11/{Objectif 1.1}}") in tex
    assert tex.index("Partie 1 ---") < tex.index("Partie 2 ---")
    assert "seqPartieCouvertureSix" not in tex
    assert tex.endswith("}}")                       # \seqSuiviObjectifsSix puis la couverture


def test_tableau_de_suivi_trois_cases_et_note_du_test_court_sur_dix():
    sty = _src(STY)
    debut = sty.index("\\tl_new:N \\l__seqsix_suivi_lignes_tl")
    code = sty[debut:sty.index("\\ExplSyntaxOff", debut)]
    # 13 novembre, 12 h 12 : colonnes renommées (une par série)
    for entete in ("Je~me~suis \\newline entraîné", "J'ai \\newline approfondi",
                   "Je~suis \\newline expert", "Test \\newline court"):
        assert entete in code
    # trois cases par ligne d'objectif, puis la note
    assert code.count("& \\__seqsix_suivi_case:") == 3
    assert "/ \\, 10" in code
    # couleur du thème conservée (en-tête, titres de partie, code de l'objectif)
    assert "\\rowcolor{seqSixTheme}" in code and "\\color{seqSixTheme} #1" in code


def test_cases_vides_aussi_dans_le_corrige_meme_texte_de_couverture(app_6e):
    """Le livret corrigé sert au professeur : le suivi reste à remplir par l'élève, la page de
    garde est la même ; le tableau ne dépend pas de la version (aucun \\ifseq@corrige)."""
    from services.livret_sequence_6e import generer_livret_sequence_6e
    with app_6e.json_store._conn() as c:
        el = generer_livret_sequence_6e(c, "N09", "S01", {"version": "eleve"}, tblr_libraries=TBLR)
        co = generer_livret_sequence_6e(c, "N09", "S01", {"version": "corrigee"},
                                        tblr_libraries=TBLR)

    def garde(t):
        corps = t.split(r"\begin{document}")[1]
        return corps[corps.index(r"\seqCouvertureLivretSix*"):corps.index(r"\clearpage")]
    assert r"\seqSuiviObjectifsSix" in garde(el) and garde(el) == garde(co)
    sty = _src(STY)
    code = sty[sty.index("\\tl_new:N \\l__seqsix_suivi_lignes_tl"):
               sty.index("\\NewDocumentCommand{\\seqSuiviObjectifsSix}")]
    assert "ifseq@corrige" not in code


def test_tableau_resserre_puis_reduit_pour_tenir_sur_une_page_dans_le_code():
    """Jamais deux pages (S03 : 10 objectifs, 4 parties) : on resserre l'interligne, puis la
    police, puis on réduit la boîte à la hauteur restante."""
    sty = _src(STY)
    code = sty[sty.index("\\NewDocumentCommand{\\seqSuiviObjectifsSix}"):]
    code = code[:code.index("\\ExplSyntaxOff")]
    assert code.index("\\small { 2.0 }") < code.index("\\small { 1.6 }") \
        < code.index("\\footnotesize { 1.1 }") < code.index("\\box_resize_to_ht_plus_dp:Nn")
    assert "\\pagegoal - \\pagetotal" in code


GEOMETRIE_6E = "\\geometry{a4paper,margin=1.5cm,top=2cm,bottom=2cm}"


def _compiler(tmp_path, corps):
    (tmp_path / "t.tex").write_text(
        "\\documentclass[11pt,a4paper]{article}\\usepackage[T1]{fontenc}\\usepackage[utf8]{inputenc}"
        "\\usepackage[french]{babel}\\usepackage{amssymb}\\usepackage{geometry}"
        "\\usepackage{seqenseigne-style6e}" + GEOMETRIE_6E
        + "\\renewcommand{\\familydefault}{\\sfdefault}\\begin{document}" + corps
        + "\\end{document}", encoding="utf-8")
    env = dict(os.environ, TEXINPUTS=f".:{PAQUET}//:")
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "t.tex"], cwd=tmp_path,
                       capture_output=True, env=env, timeout=300)
    return r, (tmp_path / "t.log").read_text(encoding="latin-1")


def _pages(log):
    m = re.search(r"Output written on t\.pdf \((\d+) pages?", log)
    return int(m.group(1)) if m else 0


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex absent")
@pytest.mark.parametrize("nb_parties,nb_objectifs", [(4, 3), (5, 8)])
def test_page_de_garde_de_suivi_tient_sur_une_page_meme_tres_chargee(tmp_path, nb_parties,
                                                                      nb_objectifs):
    """S03 a 10 objectifs en 4 parties ; on vérifie 12 et même 40 objectifs : une seule page,
    aucune erreur, aucune boîte trop large."""
    from services.livret_sequence_6e import couverture
    seq = _seq(nb_parties, nb_objectifs)
    for p in seq["parties"]:
        for o in p["objectifs"]:
            o["nom"] = ("Résoudre un problème de division décimale avec un intitulé long, "
                        "sur deux lignes, 0,1, 0,01 ou 0,001")
    r, log = _compiler(tmp_path, couverture(seq))
    assert not re.search(r"^! ", log, re.M), log[-2000:]
    assert "Overfull \\hbox" not in log
    assert _pages(log) == 1


# ── 2. Fiche de résumé insécable ────────────────────────────────────────────

def test_fiche_de_resume_insecable_quitte_a_perdre_le_bas_de_la_page():
    """Laurent : « Le cadre de la fiche de résumé doit être insécable, quitte à perdre le bas
    de la page. Par exemple celui de S01-12 »."""
    sty = _src(STY)
    debut = sty.index("\\NewDocumentEnvironment{seqFicheResumeSix}")
    code = sty[debut:debut + 400]
    assert "unbreakable" in code and ", breakable" not in code


# ── 4. Séparation des colonnes ──────────────────────────────────────────────

def test_separation_des_colonnes_trait_gris_entre_deux_hfill():
    """« Quand l'énoncé d'un exercice est sur plusieurs colonnes, mets une séparation »
    (S06 A05) : la macro remplace le \\hfill entre deux minipages, elle garde donc un \\hfill
    de chaque côté."""
    sty = _src(STY)
    assert ("\\NewDocumentCommand{\\seqSepColonnesSix}{}{%\n"
            "  \\hfill{\\color{black!35}\\vrule width 0.6pt}\\hfill}") in sty


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex absent")
def test_separation_des_colonnes_compile_entre_deux_minipages(tmp_path):
    r, log = _compiler(tmp_path, "\\noindent\\begin{minipage}[t]{0.47\\linewidth}a. 12 + 3"
                       "\\end{minipage}\\seqSepColonnesSix\\begin{minipage}[t]{0.47\\linewidth}"
                       "b. 7 + 8\\end{minipage}")
    assert not re.search(r"^! ", log, re.M) and "Overfull \\hbox" not in log, log[-2000:]
