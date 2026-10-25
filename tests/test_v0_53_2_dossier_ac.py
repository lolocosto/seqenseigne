"""tests/test_v0_53_2_dossier_ac.py — v0.53.2

Décisions de Laurent du 25 octobre 2026 (doc/redemarrage_v0_53_2.md) :

1. E1 — échappement LaTeX commun des chaînes de la base (anomalie : π brut
   du critère F de M04-22, plan de la partie 3 non compilé) ;
2. D-DOS — dossier enseignant par partie (plan, fiche complète, corrigés des
   exercices de séance, tests courts corrigés A et B) ;
3. D-AC / I-MR8 — activités complémentaires (série AC) dans une mise en
   route, hors contrôle MR6 ;
4. référentiel du 25 octobre (critère F de S10-02, dépendances) ;
5. bonus d'un test court : 1 point, sinon anomalie à corriger dans le lot.

Base de test reconstruite à chaque test (jamais de base réelle).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from outils import import_lot6e as imp
from outils import import_lot6e_mer as imp_mer
from services import mises_en_route_6e as mer
from services.latex_texte import UNICODE_CONNUS, UNICODE_LATEX, texte_latex, unicode_latex
from tests.test_v0_53_0_mises_en_route import (_appliquer, _conn, _dump, _ecrire_lot, _essai,
                                               _lot, base)  # noqa: F401  (fixture)

APPLI = Path(__file__).resolve().parent.parent
CRITERE_PI = "Calcule le périmètre d'un cercle dont on connaît le diamètre, avec π ≈ 3,14."


# ── 1. E1 Échappement commun ────────────────────────────────────────────────

def test_pi_et_approx_du_critere_de_m04_22_deviennent_des_commandes_sures():
    t = unicode_latex(CRITERE_PI)
    assert "π" not in t and "≈" not in t
    assert r"\ensuremath{\pi} \ensuremath{\approx} 3,14" in t


def test_chaine_sans_caractere_inconnu_de_pdflatex_inchangee_donc_meme_tex_cycle4_et_principal():
    # Une chaîne qui compilait (ASCII, accents, caractères que le noyau LaTeX
    # convertit lui-même) ressort identique : le .tex du cycle 4 et du
    # principal de 6e ne change pas.
    s = r"Écrire $\frac{3}{4}$ ; n°1, 3 × 2, 12 ÷ 4, 90°, m², cm³, ½ « ok » \ieme & 10 \%"
    assert unicode_latex(s) == s
    for c in UNICODE_CONNUS:
        assert c not in UNICODE_LATEX


def test_texte_simple_echappe_les_speciaux_mais_pas_les_indices_d_une_formule():
    assert texte_latex("10 % & #3 a_b") == r"10 \% \& \#3 a\_b"
    assert texte_latex(r"$x_1$ et déjà \% échappé") == r"$x_1$ et déjà \% échappé"
    assert texte_latex(None) == "" and unicode_latex("") == ""


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex absent")
def test_toutes_les_conversions_compilent_en_texte_et_en_formule_et_les_connus_en_texte(tmp_path):
    tous = "".join(UNICODE_LATEX)
    corps = ("Texte : " + unicode_latex(" ".join(tous)) + " collé : " + unicode_latex(tous)
             + " formule : $" + unicode_latex(" ".join(tous)) + "$ connus : " + UNICODE_CONNUS
             + " " + texte_latex("10 % & # _ " + CRITERE_PI))
    (tmp_path / "t.tex").write_text(
        r"\documentclass{article}\usepackage[T1]{fontenc}\usepackage[utf8]{inputenc}"
        r"\begin{document}" + corps + r"\end{document}", encoding="utf-8")
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "t.tex"], cwd=tmp_path,
                       capture_output=True)
    assert r.returncode == 0, r.stdout.decode("utf-8", "replace")[-1500:]


def test_tout_le_corps_d_un_document_6e_passe_par_l_echappement_commun(base):
    from services.livret_sequence_6e import document
    c = _conn(base)
    tex = document(c, "N09", "essai", [r"\textbf{" + CRITERE_PI + "}", "$2πr$"], False)
    corps = tex.split(r"\begin{document}")[1]
    assert "π" not in corps and r"$2\ensuremath{\pi}r$" in corps


def test_plan_de_mise_en_route_echappe_critere_avec_pi_et_pourcentage(base, tmp_path):
    lot = _lot()
    lot["objectifs"][0]["criteres"] = {"F": CRITERE_PI, "A": "Calcule 10 % d'une table."}
    _appliquer(base, _ecrire_lot(tmp_path / "l", lot))
    tex = mer.generer_document_mer(_conn(base), "N09", "M01", {"document": "plan",
                                                                "partie": 1})
    assert r"avec \ensuremath{\pi} \ensuremath{\approx} 3,14" in tex
    assert r"Calcule 10 \% d'une table" in tex
    assert "π" not in tex


# ── 2 et 3. Activités complémentaires (I-MR8, D-AC) ─────────────────────────

AC = {"titre": "Le tour de la roue", "objectif": "M01-22",
      "latex": r"\seqTitreComplementSix{Le tour de la roue}{Mise en route 1}" "\n"
               r"Une roue de 60 cm de diamètre : son tour ? \seqACompleter{188 cm}",
      "corrige": r"$60\times3{,}14=188{,}4$.", "origine": "création"}


def _lot_ac(*acs) -> dict:
    lot = _lot()
    lot["activites_complementaires"] = [dict(a) for a in acs]
    return lot


def test_activite_complementaire_importee_en_serie_ac_et_reliee_a_son_objectif(base, tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot_ac(AC)))
    c = _conn(base)
    r = c.execute("SELECT id, titre, num FROM exercices WHERE niveau='N09' AND sequence='M01' "
                  "AND serie_code='AC'").fetchall()
    assert [(x["titre"], x["num"]) for x in r] == [("Le tour de la roue", 1)]
    s = mer.lire_sequence_mer(c, "N09", "M01")
    assert [a["code"] for a in mer.partie_de(s, 3)["activites"]] == ["AC01"]
    assert mer.partie_de(s, 3)["activites"][0]["objectifs"] == ["M01-22"]


def test_cle_objectifs_au_format_des_lots_s_acceptee_aussi(base, tmp_path):
    a = dict(AC)
    del a["objectif"]
    a["objectifs"] = ["M01-32"]
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot_ac(a)))
    s = mer.lire_sequence_mer(_conn(base), "N09", "M01")
    assert [x["code"] for x in mer.partie_de(s, 4)["activites"]] == ["AC01"]


def test_activite_sans_objectif_et_travail_personnel_signales(base, tmp_path):
    a = dict(AC)
    del a["objectif"]
    lot = _lot_ac(a)
    lot["travaux_personnels"] = [{"titre": "TP", "latex": "x"}]
    r = _essai(base, _ecrire_lot(tmp_path / "l", lot))
    assert any("AC01" in x and "sans objectif" in x for x in r.anomalies)
    assert any("travaux_personnels" in x and "n'existe pas" in x for x in r.anomalies)


def test_activites_complementaires_hors_controle_mr6(base, tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    avant = mer.valider_sequence_mer(_conn(base), "N09", "M01")
    _appliquer(base, _ecrire_lot(tmp_path / "l2", _lot_ac(AC, dict(AC, titre="Deux"))))
    apres = mer.valider_sequence_mer(_conn(base), "N09", "M01")
    assert apres == avant


def test_import_des_activites_idempotent(base, tmp_path):
    lots = _ecrire_lot(tmp_path / "l", _lot_ac(AC))
    _appliquer(base, lots)
    d1 = _dump(base)
    _appliquer(base, lots)
    assert _dump(base) == d1


def test_plan_de_la_partie_liste_ses_activites_complementaires(base, tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot_ac(AC)))
    c = _conn(base)
    p3 = mer.generer_document_mer(c, "N09", "M01", {"document": "plan", "partie": 3})
    assert r"\item AC01 --- Le tour de la roue (M01-22)" in p3
    p1 = mer.generer_document_mer(c, "N09", "M01", {"document": "plan", "partie": 1})
    assert "AC01" not in p1


def test_document_activite_rendu_comme_au_principal_eleve_et_corrige(base, tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot_ac(AC)))
    c = _conn(base)
    el = mer.generer_document_mer(c, "N09", "M01", {"document": "activite", "partie": 3})
    assert r"\setcounter{seqComplSix}{0}" in el and r"\seqTitreComplementSix{Le tour" in el
    assert r"\seqVersionCorrigee" not in el.split(r"\begin{document}")[1]
    co = mer.generer_document_mer(c, "N09", "M01", {"document": "activite", "partie": 3,
                                                     "version": "corrigee"})
    assert r"\seqVersionCorrigee" in co and r"\seqLocExplication{$60\times" in co
    with pytest.raises(mer.MiseEnRouteErreur):
        mer.generer_document_mer(c, "N09", "M01", {"document": "activite", "partie": 1})


def test_activites_des_mises_en_route_absentes_du_catalogue_du_principal(base, tmp_path):
    from services.documents_6e import atomes_de_la_serie
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot_ac(AC)))
    assert atomes_de_la_serie(_conn(base), "N09", "AC") == []


# ── 2. Dossier enseignant (D-DOS) ───────────────────────────────────────────

def test_dossier_d_une_partie_dans_l_ordre_plan_fiche_corriges_tests_a_b_activites(base,
                                                                                   tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot_ac(AC)))
    tex = mer.generer_document_mer(_conn(base), "N09", "M01", {"document": "dossier",
                                                                "partie": 3})
    corps = tex.split(r"\begin{document}")[1]
    assert corps.lstrip().startswith(r"\seqVersionCorrigee")
    assert "dossier enseignant -- page \\thepage" in corps
    i_plan = corps.index("Plan de séquence (enseignant)")
    i_fiche = corps.index(r"\seqVersionComplete")
    i_corr = corps.index("Corrigés des exercices de séance")
    i_a = corps.index("Sujet A")
    i_b = corps.index("Sujet B")
    i_ac = corps.index(r"\seqTitreComplementSix{Le tour")
    assert i_plan < i_fiche < i_corr < i_a < i_b < i_ac
    # Une partie seulement, et pas d'autre en-tête de page que celui du dossier.
    assert "M01-02" not in corps and corps.count(r"\fancyhead") == 1


def test_dossier_corriges_dans_l_ordre_des_seances_et_exercice_sans_corrige_signale(base,
                                                                                    tmp_path):
    lot = _lot()
    sans = next(e for e in lot["exercices_seance"] if e["objectif"] == "M01-02")
    sans["corrige"] = ""
    _appliquer(base, _ecrire_lot(tmp_path / "l", lot))
    tex = mer.generer_document_mer(_conn(base), "N09", "M01", {"document": "dossier",
                                                                "partie": 1})
    seances = [e["seance"] for e in lot["exercices_seance"] if e["objectif"] == "M01-02"]
    pos = [tex.index(f"Séance {n} ---") for n in seances]
    assert pos == sorted(pos)
    assert "Pas de corrigé rédigé : réponses sur la planche corrigée." in tex


def test_dossier_de_toute_la_sequence_partie_par_partie(base, tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    tex = mer.generer_document_mer(_conn(base), "N09", "M01", {"document": "dossier"})
    for n in (1, 2, 3, 4):
        assert f"Mise en route 1 --- Calcul mental --- partie {n}" in tex
    assert tex.count("Sujet A") >= 4 and tex.count("Sujet B") >= 4


def test_documents_existants_gardes_et_dossier_ajoute():
    assert mer.DOCUMENTS_MER[:4] == ("fiche_cours", "planche", "test_court", "plan")
    assert "dossier" in mer.DOCUMENTS_MER and "activite" in mer.DOCUMENTS_MER


def test_route_du_livret_compile_le_dossier_en_tex(base, tmp_path):
    from app import create_app
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    c = create_app(base.parent, profil="atelier").test_client()
    r = c.post("/api/v2/livret-sequence/N09/M01/rendu-tex",
               json={"options": {"mer": {"document": "dossier", "partie": 2}}})
    assert r.status_code == 200 and b"dossier enseignant" in r.data


# ── 4. Référentiel du 25 octobre ────────────────────────────────────────────

def test_critere_f_de_s10_02_transcrit_du_referentiel_du_25_octobre():
    ref = json.loads((APPLI / "outils" / "objectifs_6e.json").read_text(encoding="utf-8"))
    o = next(o for p in ref["parties"]["S10"] for o in p["objectifs"] if o["code"] == "02")
    assert o["critere_F"] == "Lit une donnée dans un tableau déjà filtré ou un diagramme en barres."


def test_ref6e_v2_porte_les_deux_dependances_du_25_octobre():
    t = (APPLI / "outils" / "ref6e_v2.md").read_text(encoding="utf-8")
    assert "- M03-12 → M04-12 :" in t and "- M05-12 → S06-03 :" in t
    assert "« Aire et unité d'aire » (rappel, expliquée dans la fiche M04, partie 2)" in t


def test_critere_change_d_un_objectif_existant_mis_a_jour_et_signale(base):
    c = _conn(base)
    r = imp.Rapport()
    sn = imp._seq_niveau(c, "S10", r)
    pid = imp._partie(c, sn["id"], 1, "S10", r)
    d = {"nom": "Filtrer", "critere_F": "Lit une donnée dans un tableau ou un diagramme en "
                                         "barres.", "critere_A": "A", "critere_E": "E"}
    imp._objectif(c, sn["id"], pid, "02", d, r, "S10-02")
    d2 = dict(d, critere_F="Lit une donnée dans un tableau déjà filtré ou un diagramme en "
                           "barres.")
    oid, etat = imp._objectif(c, sn["id"], pid, "02", d2, r, "S10-02")
    assert etat == "mis à jour"
    assert any(i.startswith("S10-02 : objectif mis à jour") and "critère F" in i
               for i in r.infos)


# ── 5. Bonus d'un test court ────────────────────────────────────────────────

def test_bonus_de_test_court_lu_dans_le_sujet_different_de_1_est_une_anomalie(base, tmp_path):
    lot = _lot()
    ev = lot["evaluations"][0]
    # Bonus de 2 points dans le sujet, barème du lot non renseigné.
    import re
    ev["latex"] = re.sub(r"(\\seqExoEval\{Bonus[^}]*\}\{)\s*1\s*pts?",
                         r"\g<1>2 pts", ev["latex"], count=1)
    if "2 pts" not in ev["latex"]:
        pytest.skip("jeu de test sans exercice bonus dans le sujet")
    ev.pop("bareme", None)
    r = _essai(base, _ecrire_lot(tmp_path / "l", lot))
    assert any("bonus de 2 point(s)" in a and "à corriger dans le lot" in a for a in r.anomalies)


def test_bonus_de_1_point_sans_signalement(base, tmp_path):
    r = _essai(base, _ecrire_lot(tmp_path / "l", _lot()))
    assert not any("bonus de" in a for a in r.anomalies + r.infos)
    assert imp_mer.BONUS_TEST_COURT == 1


def test_titre_d_exercice_de_seance_avec_pourcentage_echappe_planche_et_dossier(base, tmp_path):
    # Cas réel (M02, assemblage v0.53.2) : « Passer par 10 % ou 1 % » coupait
    # \seqPartieSix{…} des corrigés rédigés (le reste de la ligne en commentaire).
    lot = _lot()
    lot["exercices_seance"][0]["titre"] = "Passer par 10 % ou 1 %"
    _appliquer(base, _ecrire_lot(tmp_path / "l", lot))
    c = _conn(base)
    for opts in ({"document": "planche", "partie": 1, "version": "corrigee"},
                 {"document": "dossier", "partie": 1}):
        tex = mer.generer_document_mer(c, "N09", "M01", opts)
        assert "Passer par 10 % ou 1 %" not in tex
        assert r"Passer par 10 \% ou 1 \%" in tex


def test_foreach_sans_accolades_dans_un_corrige_signale_car_le_point_virgule_y_est_deja_actif(
        base, tmp_path):
    # Cas réel (M04 AC02, assemblage v0.53.2) : dans l'argument de
    # \seqLocExplication, « \foreach \x in {…} \fill …; » ne compile pas
    # (« ; » actif de babel) ; avec accolades autour du corps, il compile.
    mauvais = dict(AC, corrige=r"\begin{tikzpicture}\foreach \x in {0,...,3} "
                               r"\fill (\x,0) circle (1pt);\end{tikzpicture}")
    bon = dict(AC, titre="Bon", corrige=r"\begin{tikzpicture}\foreach \x in {0,...,3} "
                                        r"{\fill (\x,0) circle (1pt);}\end{tikzpicture}")
    r = _essai(base, _ecrire_lot(tmp_path / "l", _lot_ac(mauvais, bon)))
    signales = [a for a in r.anomalies if "foreach sans accolades" in a]
    assert len(signales) == 1 and "Le tour de la roue" in signales[0]
