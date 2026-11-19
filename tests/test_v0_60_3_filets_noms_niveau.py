"""tests/test_v0_60_3_filets_noms_niveau.py — v0.60.3 (doc/redemarrage_v0_60_3.md)

1. FILETS — signalement du 19 novembre : les filets intérieurs des tableaux disparaissaient
   sur les cellules colorées (en-tête rose du tableau des sommes, 4e C2, AE01). Cause : le
   tableau « Suivi par objectif » de la page de garde (module seqenseigne-style6e) faisait
   \\arrayrulecolor{black!30}, global avec colortbl (\\gdef\\CT@arc@) malgré le groupe de la
   boîte : tous les tableaux suivants du document avaient des filets gris clair à 30 %.
   v0.16 : couleur sauvée et rétablie autour du tableau de suivi ; même fuite (locale, au
   niveau du document) corrigée dans \\seqTableauObjectifs (module data v1.2).
2. NOMS — Laurent : « les livrets, corrections enseignant et plans de travail sont nommés
   avec "6e" même en 4e ». Noms des PDF et libellés des cibles du modèle Fiches au niveau
   réel ; clés de types (nom interne du module, partagées avec l'appli de classe) et
   identifiants de cibles inchangés ; 6e inchangée ; ancien nom lu en secours puis supprimé
   à la recompilation.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import style6e  # noqa: E402
from services import referentiel_documents_compilation as rdc  # noqa: E402
from tests.test_v0_52_2_documents_6e import app_6e  # noqa: E402,F401

PAQUET = Path(__file__).parent.parent / "paquet"
DTX6 = PAQUET / "seqenseigne-style6e.dtx"
STY6 = PAQUET / "seqenseigne-style6e.sty"
DTXD = PAQUET / "seqenseigne-data.dtx"
STYD = PAQUET / "seqenseigne-data.sty"
SERVICES = Path(__file__).parent.parent / "services"


def _src(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── 1. FILETS ───────────────────────────────────────────────────────────────

def test_filets_le_tableau_de_suivi_retablit_la_couleur_des_filets_d_avant_lui():
    """\\arrayrulecolor est global avec colortbl : sauver \\CT@arc@ avant la boîte et le
    rétablir globalement après (le groupe de la boîte ne suffit pas)."""
    for f in (DTX6, STY6):
        src = _src(f)
        debut = src.index("\\cs_new_protected:Npn \\__seqsix_suivi_composer:Nn")
        code = src[debut:src.index("\\dim_const:Nn \\c__seqsix_suivi_case_dim", debut)]
        sauve = code.index("\\cs_set_eq:NN \\__seqsix_suivi_filets_sauves: \\CT@arc@")
        boite = code.index("\\__seqsix_suivi_composer_boite:Nn #1 {#2}")
        retabli = code.index("\\cs_gset_eq:NN \\CT@arc@ \\__seqsix_suivi_filets_sauves:")
        assert sauve < boite < retabli, f.name
        # le gris clair du suivi reste dans la boîte (rendu du suivi inchangé)
        assert code.index("\\arrayrulecolor{black!30}") > retabli


def test_filets_module_v0_16_et_version_citee_par_l_appli():
    assert style6e.VERSION == "v0.16"
    for f in (DTX6, STY6):
        assert "v0.16 seqenseigne : style des documents de 6e" in _src(f)
    assert "\\changes{v0.16}{2026/11/19}" in _src(DTX6)


def test_filets_tableau_d_objectifs_du_module_data_couleur_dans_le_groupe_de_center():
    """\\seq@rule@color est un \\def local : posé avant \\begin{center}, il restait en vigueur
    pour la suite du document."""
    for f in (DTXD, STYD):
        src = _src(f)
        debut = src.index("\\newcommand{\\seqTableauObjectifs}")
        code = src[debut:src.index("\\end{xltabular}", debut)]
        assert code.index("\\begin{center}") < code.index("\\seq@rule@color{\\seq@couleuri@vif}")
    assert "v1.2 seqenseigne data module" in _src(STYD)


def test_filets_aucune_autre_commande_globale_de_couleur_de_filets_dans_le_paquet():
    """Inventaire (v0.60.3) : seul le tableau de suivi change la couleur des filets ; aucun
    \\rowcolors, \\doublerulesepcolor ni changement de \\arrayrulewidth. Une nouvelle
    occurrence doit être rendue locale (sauver / rétablir \\CT@arc@) puis ajoutée ici."""
    occurrences = {}
    for f in sorted(PAQUET.glob("*.dtx")):
        code = "\n".join(l for l in _src(f).splitlines() if not l.lstrip().startswith("%"))
        code = re.sub(r"(?<!\\)%.*", "", code)                     # commentaires de fin
        for m in re.finditer(r"\\(arrayrulecolor|rowcolors|doublerulesepcolor)\b|"
                             r"\\setlength\{?\\arrayrulewidth|\\(?:g|x)def\\CT@arc@",
                             code):
            occurrences.setdefault(f.name, []).append(m.group(0))
    assert occurrences == {"seqenseigne-style6e.dtx": ["\\arrayrulecolor"]}


def _compiler(tmp_path: Path, corps: str) -> str:
    (tmp_path / "t.tex").write_text(
        "\\documentclass[11pt,a4paper]{article}\\usepackage[T1]{fontenc}"
        "\\usepackage[utf8]{inputenc}\\usepackage[french]{babel}\\usepackage{amssymb}"
        "\\usepackage{geometry}\\usepackage{seqenseigne-style6e}"
        "\\geometry{a4paper,margin=1.5cm,top=2cm,bottom=2cm}\\makeatletter"
        "\\newcommand{\\montrefilets}[1]{\\typeout{FILETS #1=\\meaning\\CT@arc@}}"
        "\\makeatother\\begin{document}" + corps + "\\end{document}", encoding="utf-8")
    env = dict(os.environ, TEXINPUTS=f".:{PAQUET}//:")
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "t.tex"], cwd=tmp_path,
                   capture_output=True, env=env, timeout=300)
    return (tmp_path / "t.log").read_text(encoding="latin-1")


SUIVI = ("\\seqSuiviObjectifsSix{\\seqPartieSuiviSix{Partie 1}"
         "{C2-02/{Décrire des évènements},C2-03/{Calculer une probabilité}}}")
TABLEAU = ("\\begin{tabular}{|c|c|}\\hline\\rowcolor{seqSixEnteteTab}$+$ & 1\\\\ \\hline "
           "\\textbf{1} & \\seqLocCellule{2}\\\\ \\hline\\end{tabular}")


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex absent")
def test_filets_noirs_dans_un_tableau_ordinaire_apres_la_page_de_suivi(tmp_path):
    """Le cas du signalement : page de garde de suivi, puis tableau à en-tête coloré."""
    log = _compiler(tmp_path, "\\montrefilets{avant}" + SUIVI + "\\montrefilets{apres}"
                    + TABLEAU + "\\montrefilets{fin}")
    assert not re.search(r"^! ", log, re.M), log[-2000:]
    vus = dict(re.findall(r"^FILETS (\w+)=(.*)$", log, re.M))
    assert vus["avant"] == "\\relax"                    # défaut de colortbl : noir
    assert vus["apres"] == vus["fin"] == "\\relax"      # v0.60.2 : \color {black!30}
    assert "black!30" not in vus["apres"]


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex absent")
def test_filets_une_couleur_choisie_avant_le_suivi_est_retrouvee_apres(tmp_path):
    log = _compiler(tmp_path, "\\arrayrulecolor{blue}" + SUIVI + "\\montrefilets{apres}")
    vus = dict(re.findall(r"^FILETS (\w+)=(.*)$", log, re.M))
    assert "blue" in vus["apres"] and "black!30" not in vus["apres"]


# ── 2. NOMS ─────────────────────────────────────────────────────────────────

class _Conn:
    """Connexion minimale : param_niveaux absente (lire_nom_court lève)."""

    def execute(self, *a, **k):
        raise rdc.sqlite3.OperationalError("no such table: param_niveaux")


@pytest.mark.parametrize("niveau,attendu", [("N09", "6e"), ("N10", "5e"), ("N11", "4e"),
                                            ("N12", "3e"), ("N99", "N99")])
def test_noms_niveau_du_fichier_en_ascii_meme_sans_table_des_niveaux(niveau, attendu):
    assert rdc.niveau_fichier(_Conn(), niveau) == attendu


def test_noms_racine_seul_le_suffixe_du_module_change_et_la_6e_garde_son_nom():
    assert rdc.noms_cible("livret_sequence_6e", "4e", "__N11__C2") == {
        "nom_fichier": "livret_sequence_4e__N11__C2.pdf",
        "noms_anciens": ["livret_sequence_6e__N11__C2.pdf"]}
    assert rdc.noms_cible("corriges_6e", "6e", "__N09__A1") == {
        "nom_fichier": "corriges_6e__N09__A1.pdf"}               # 6e : rien ne change
    assert rdc.noms_cible("mer_tests_courts_6e", "5e", "__N10__M01__p1__T1")["nom_fichier"] \
        == "mer_tests_courts_5e__N10__M01__p1__T1.pdf"
    # les types du cycle 4 (et récap / planches du modèle Fiches) n'ont pas de suffixe
    assert rdc.racine_fichier("livret_cartes_planches", "4e") == "livret_cartes_planches"


def test_noms_plus_aucun_6e_code_en_dur_dans_les_noms_et_titres_des_documents_fiches():
    """Hors du nom interne du module (seqenseigne-style6e) et des clés de types."""
    motifs = (r'nom_fichier[^\n]*f"[a-z_]*6e__', r"'Livret 6e'", r"'Corrigés 6e'",
              r"'Plan de travail 6e'", r'titre = f"[^"]* 6e —', r'f"[A-Z][^"]* 6e — ')
    for f in ("referentiel_documents_compilation.py", "documents_evaluation_v2.py",
              "livret_sequence_6e.py", "plan_travail_6e.py", "cartes_mentales.py",
              "render_evaluation.py", "documents_6e.py", "rendu_atome_6e.py",
              "mises_en_route_6e.py"):
        src = (SERVICES / f).read_text(encoding="utf-8")
        for m in motifs:
            assert not re.search(m, src), (f, m)


def _ref_4e(app):
    """Référentiel principal de 4e au modèle Fiches, une séquence C2 ; livret et
    corrigés (annuel + par séquence) dans « Documents à publier »."""
    with app.json_store._conn() as c:
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, "
                  "gabarit_documents) VALUES ('R11F', 'N11', '2027', 'en_cours', 'sixieme')")
        c.execute("INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres) "
                  "VALUES ('sn11c2', 'N11', 'C2', '')")
        for i, (t, o) in enumerate((("livret_sequence_6e", {"actif": True}),
                                    ("corriges_6e", {"actif": True, "decoupage": "les_deux"}),
                                    ("plans_travail_6e", {"actif": True}))):
            c.execute("INSERT INTO referentiel_documents (id, referentiel_id, type_document, "
                      "ordre, options) VALUES (?, 'R11F', ?, ?, ?)",
                      (f"d{i}", t, i + 1, json.dumps(o)))
        c.commit()


def test_noms_cibles_du_modele_fiches_en_4e_portent_4e_et_gardent_leur_identifiant(app_6e):
    _ref_4e(app_6e)
    with app_6e.json_store._conn() as c:
        livret = rdc.lister_cibles_document(c, "d0", "R11F", "livret_sequence_6e")
        corr = rdc.lister_cibles_document(c, "d1", "R11F", "corriges_6e")
        plan = rdc.lister_cibles_document(c, "d2", "R11F", "plans_travail_6e")
    assert [(x["cible_id"], x["nom_fichier"], x["libelle"]) for x in livret] == [
        ("N11/C2", "livret_sequence_4e__N11__C2.pdf", "Livret 4e N11/C2")]
    assert livret[0]["noms_anciens"] == ["livret_sequence_6e__N11__C2.pdf"]
    assert [(x["cible_id"], x["nom_fichier"]) for x in corr] == [
        ("unique", "corriges_4e.pdf"), ("N11/C2", "corriges_4e__N11__C2.pdf")]
    assert corr[1]["libelle"] == "Corrigés 4e N11/C2"
    assert plan[0]["nom_fichier"] == "plans_travail_4e__N11__C2.pdf"
    for x in livret + corr + plan:                 # nom accepté par la route des PDF figés
        assert re.fullmatch(r"[A-Za-z0-9_\-]+\.pdf", x["nom_fichier"])


def test_noms_documents_de_6e_inchanges_ni_ancien_nom_ni_libelle_modifie(app_6e):
    """PDF figés de 2026-2027, publications envoyées à l'appli de classe : mêmes noms."""
    with app_6e.json_store._conn() as c:
        cibles = (rdc._cibles_6e(c, "fictif", "N09", "livret_sequence_6e")
                  + rdc._cibles_evaluations_6e(c, "N09")
                  + rdc._cibles_documents_6e(c, "N09", "travaux_personnels_6e"))
        assert len(cibles) >= 3
        for x in cibles:
            assert "_6e__N09__" in x["nom_fichier"] and "noms_anciens" not in x, x
            assert " 4e" not in x["libelle"]


def test_noms_titre_du_tex_au_niveau_reel():
    from services import livret_sequence_6e as l6

    class C:
        def execute(self, *a):
            return SimpleNamespace(fetchone=lambda: ("4ème",))
    assert l6.niveau_court(C(), "N11") == "4e"
    src = (SERVICES / "livret_sequence_6e.py").read_text(encoding="utf-8")
    assert 'f"Livret de séquence {niveau_court(conn, niveau)} — ' in src


def test_noms_pdf_compile_avant_la_v0_60_3_servi_sous_le_nouveau_nom(app_6e):
    """Pas de recompilation nécessaire pour retrouver un PDF déjà compilé (N2)."""
    _ref_4e(app_6e)
    dossier = Path(app_6e.json_store.data_dir) / "referentiels" / "R11F"
    dossier.mkdir(parents=True)
    (dossier / "livret_sequence_6e__N11__C2.pdf").write_bytes(b"%PDF-1.4 ancien")
    r = app_6e.test_client().get("/api/referentiels/R11F/documents/d0/pdf?cible=N11/C2")
    assert r.status_code == 200 and r.data == b"%PDF-1.4 ancien"
    assert "livret_sequence_4e__N11__C2.pdf" in r.headers.get("Content-Disposition", "")


def test_noms_publication_et_pdf_figes_trouvent_l_ancien_nom(app_6e, tmp_path):
    from services.format_referentiel import _pdf_compile
    base = tmp_path / "referentiels" / "R"
    (base / "_verrouille" / "pdfs").mkdir(parents=True)
    (base / "_verrouille" / "pdfs" / "corriges_6e__N11__C2.pdf").write_bytes(b"%PDF fige")
    f = _pdf_compile(tmp_path, "R", "corriges_4e__N11__C2.pdf", True,
                     ["corriges_6e__N11__C2.pdf"])
    assert f["nom"] == "corriges_6e__N11__C2.pdf"      # la publication relit ce fichier
    assert rdc.trouver_pdf(base / "_verrouille" / "pdfs",
                           {"nom_fichier": "corriges_4e__N11__C2.pdf",
                            "noms_anciens": ["corriges_6e__N11__C2.pdf"]}) is not None
    from services.referentiel_figeage import copier_pdfs
    src = tmp_path / "src"
    src.mkdir()
    (src / "corriges_6e__N11__C2.pdf").write_bytes(b"%PDF actif")
    res = copier_pdfs({"documents": [{"cibles": [{
        "nom_fichier": "corriges_4e__N11__C2.pdf",
        "noms_anciens": ["corriges_6e__N11__C2.pdf"]}]}]}, src, tmp_path / "fige")
    assert res["echecs"] == []
    assert (tmp_path / "fige" / "pdfs" / "corriges_4e__N11__C2.pdf").read_bytes() == b"%PDF actif"


def test_noms_la_compilation_pose_le_nouveau_nom_et_supprime_l_ancien(app_6e, monkeypatch,
                                                                      tmp_path):
    """Pas de fichier orphelin : après recompilation, un seul PDF par cible."""
    _ref_4e(app_6e)
    from services import orchestrateur_compilation as orch
    dossier = Path(app_6e.json_store.data_dir) / "referentiels" / "R11F"
    dossier.mkdir(parents=True)
    (dossier / "livret_sequence_6e__N11__C2.pdf").write_bytes(b"%PDF ancien")
    pdf = tmp_path / "neuf.pdf"
    pdf.write_bytes(b"%PDF neuf")
    vus = []

    def faux_compiler(**k):
        vus.append(k["cible_key"])
        return SimpleNamespace(ok=True, chemin_pdf=pdf, erreurs=[], type_echec=None,
                               duree_ms=1)
    monkeypatch.setattr(orch, "compiler", faux_compiler)
    res = rdc.compiler_document(app_6e.json_store, "d0")
    assert res["compile_ok"]
    assert vus == [orch.slug_cible("N11/C2")]        # clé d'artefact inchangée (N3)
    assert sorted(p.name for p in dossier.glob("*.pdf")) == ["livret_sequence_4e__N11__C2.pdf"]
    assert (dossier / "livret_sequence_4e__N11__C2.pdf").read_bytes() == b"%PDF neuf"
