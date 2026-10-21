"""tests/test_v0_52_9_deux_parties.py — v0.52.9

Évaluations en deux parties, façon DNB (besoin de Laurent du 20 octobre
2026, doc/redemarrage_v0_52_9.md). Chaque test nomme la décision qu'il
protège :

- D1 coupé en deux seulement si un exercice EV est marqué « interdite » et un
  autre « autorisee » ; sinon .tex de la v0.52.8 au caractère près ;
- D2 partie 1 = exercices « interdite » dans leur ordre, partie 2 = les
  autres ; le bonus suit son marquage ; numérotation continue (N1) ;
- D3 partie 2 sur une nouvelle feuille (page impaire, F1), avec son
  en-tête d'identification et son rappel ;
- D4 durée de la partie 1 = 55 × points partie 1 / total, arrondie aux
  5 min, au moins 10 min, réglable (vide = automatique) ;
- D5 barème unique en tête de la partie 1 ; sujets A et B découpés de même ;
- I3 import de `calculatrice_exercices` (marquage par exercice, réglage
  de l'évaluation remis à '' quand le sujet est coupé).
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import marqueurs_exercices as mq  # noqa: E402
from tests.test_v0_52_0_import_lot6e import (  # noqa: E402,F401
    _conn, _dump, _lot_s01, base, imp)
from tests.test_v0_52_2_documents_6e import app_6e  # noqa: E402,F401
from tests.test_v0_52_6_retrait_evaluations import _evaluation  # noqa: E402

APPLI = Path(__file__).resolve().parent.parent
DONNEES = Path(__file__).parent / "donnees_v0_52_9"


def _marquer(app, **marques):
    with app.json_store._conn() as c:
        for e, v in marques.items():
            c.execute("UPDATE exercices SET calculatrice=? WHERE id=?", (v, e))
        c.commit()


def _tex(app, gabarit="sixieme", **opts):
    from services.render_evaluation import generer_tex_evaluation
    with app.json_store._conn() as c:
        return generer_tex_evaluation(c, "E6", gabarit=gabarit, options=opts)


def _corps(tex: str) -> str:
    return tex[tex.index(r"\begin{document}"):]


def _titres_exos(tex: str) -> list[str]:
    return re.findall(r"\\seqExoEval\{([^}]*)\}", tex)


# E6 (tests/test_v0_52_2_documents_6e) : ev1 « Valeur des chiffres » 5 pts
# S01-02, ev2 « Grands nombres » 3 pts S01-03, ev3 « Bonus : Qui suis-je ? »
# 2 pts (bonus). Total 8.


# ── D1 : déclenchement ───────────────────────────────────────────────────────

def test_d1_coupe_seulement_si_un_ev_interdit_et_un_autre_autorise():
    r = mq.deux_parties
    assert not r([])
    assert not r([{"calculatrice": "interdite"}, {"calculatrice": ""}])
    assert not r([{"calculatrice": "autorisee"}, {"calculatrice": ""}])
    assert not r([{"calculatrice": "interdite"}, {"calculatrice": "interdite"}])
    assert r([{"calculatrice": "interdite"}, {"calculatrice": ""}, {"calculatrice": "autorisee"}])


SCENARIOS = ("sans_marquage", "tout_interdite", "tout_autorisee", "interdite_et_non_marque",
             "autorisee_et_non_marque", "reglage_non_precisee")
MARQUAGES = {
    "sans_marquage": ({}, ""),
    "tout_interdite": ({"ev1": "interdite", "ev2": "interdite", "ev3": "interdite"}, ""),
    "tout_autorisee": ({"ev1": "autorisee", "ev2": "autorisee", "ev3": "autorisee"}, ""),
    "interdite_et_non_marque": ({"ev1": "interdite"}, ""),
    "autorisee_et_non_marque": ({"ev2": "autorisee"}, ""),
    "reglage_non_precisee": ({"ev1": "interdite"}, "non_precisee"),
}


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("sujet", "AB")
@pytest.mark.parametrize("version", ("eleve", "corrigee"))
def test_d1_sans_marquage_mixte_le_sujet_sort_exactement_le_tex_de_la_v0_52_8(
        app_6e, scenario, sujet, version):
    """Fichiers de référence produits par le code de la v0.52.8 (0114936)
    sur la même base : un sujet d'un seul tenant ne change pas d'un
    caractère (mention C1 comprise)."""
    marques, reglage = MARQUAGES[scenario]
    _marquer(app_6e, **marques)
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE evaluations SET calculatrice=? WHERE id='E6'", (reglage,))
        c.commit()
    attendu = (DONNEES / f"e6_{scenario}_{sujet}_{version}.tex").read_text(encoding="utf-8")
    assert _tex(app_6e, sujet=sujet, version=version) == attendu


def test_d1_cycle_4_marquage_mixte_sans_effet_meme_tex_qu_en_v0_52_8(app_6e):
    """Le découpage ne concerne que le gabarit 6e : le rendu du cycle 4 reste
    celui de la v0.52.8, même avec des exercices marqués mixtes."""
    _marquer(app_6e, ev1="autorisee", ev2="interdite")
    attendu = (DONNEES / "e6_cycle4_marquage_mixte.tex").read_text(encoding="utf-8")
    assert _tex(app_6e, gabarit="cycle4") == attendu


def test_d1_seuls_les_exercices_ev_declenchent_le_decoupage(app_6e):
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE exercices SET serie_code='F', calculatrice='interdite' WHERE id='ev1'")
        c.execute("UPDATE exercices SET calculatrice='autorisee' WHERE id='ev2'")
        from services.render_evaluation import parties_evaluation_6e
        assert parties_evaluation_6e(c, "E6") is None


def test_d1_ni_l_option_ni_le_reglage_n_empechent_le_decoupage(app_6e):
    """Le découpage ne dépend que du marquage des exercices ; l'option et le
    réglage ne règlent que la mention d'un sujet d'un seul tenant."""
    _marquer(app_6e, ev1="autorisee", ev2="interdite")
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE evaluations SET calculatrice='interdite' WHERE id='E6'")
        c.commit()
    for opts in ({}, {"calculatrice": "interdite"}, {"calculatrice": "non_precisee"}):
        assert "Partie 2 --- calculatrice autorisée" in _tex(app_6e, **opts)


# ── D2 : répartition, numérotation continue ─────────────────────────────────

def test_d2_partie_1_les_interdits_dans_leur_ordre_partie_2_les_autres_et_numerotation_continue(
        app_6e):
    _marquer(app_6e, ev1="autorisee", ev2="interdite")
    tex = _corps(_tex(app_6e))
    p1, p2 = tex.split(r"\setcounter{page}{1}")
    assert _titres_exos(p1) == ["Grands nombres"]
    assert _titres_exos(p2) == ["Valeur des chiffres", "Bonus : Qui suis-je ?"]   # bonus non marqué
    # N1 : compteur remis à zéro une seule fois (numérotation continue, comme au DNB).
    assert tex.count(r"\setcounter{seqExoEval}{0}") == 1
    # Mentions de calculatrice : celles des bandeaux, plus celle de C1 au sous-titre.
    assert re.findall(r"\\seqTitreEvalSix\{[^}]*\}\{([^}]*)\}", tex) == \
        ["Séquence 1 --- Sujet A"] * 2
    assert "calculatrice interdite" not in tex


def test_d2_le_bonus_suit_son_propre_marquage(app_6e):
    _marquer(app_6e, ev1="autorisee", ev2="interdite", ev3="interdite")
    p1, p2 = _corps(_tex(app_6e)).split(r"\setcounter{page}{1}")
    assert _titres_exos(p1) == ["Grands nombres", "Bonus : Qui suis-je ?"]
    assert _titres_exos(p2) == ["Valeur des chiffres"]
    # Légende du bonus : numéros affichés (Grands nombres = ex. 1, Valeur = ex. 3).
    assert "S01-02 : ex. 3 ; S01-03 : ex. 1." in p1
    assert "Partie 1 : ex. 1 et 2 (3 pts + bonus) ; partie 2 : ex. 3 (5 pts)." in p1


def test_d2_repartition_dans_l_ordre_de_l_evaluation():
    assert [mq.partie_de({"calculatrice": v}) for v in ("interdite", "autorisee", "")] == [1, 2, 2]


# ── D3 : nouvelle feuille, en-tête, rappels ──────────────────────────────────

def test_d3_partie_2_sur_une_nouvelle_feuille_recto_avec_identification_et_rappel(app_6e):
    from services.render_evaluation import SAUT_FEUILLE_PARTIE2
    _marquer(app_6e, ev1="autorisee", ev2="interdite")
    tex = _corps(_tex(app_6e))
    assert tex.count(SAUT_FEUILLE_PARTIE2) == 1
    # F1 : page impaire (recto-verso), verso blanc annoncé, partie 2 en page 1.
    assert r"\ifodd\value{page}" in SAUT_FEUILLE_PARTIE2
    assert "Page laissée blanche" in SAUT_FEUILLE_PARTIE2
    p1, p2 = tex.split(SAUT_FEUILLE_PARTIE2)
    assert p1.count(r"\seqIdentEleve") == 1 and p2.count(r"\seqIdentEleve") == 1
    assert "Partie 1 --- sans calculatrice --- à rendre au bout de 20 min" in p1
    assert "Partie 2 --- calculatrice autorisée" in p2
    assert "--- partie 1 -- page" in p1 and "--- partie 2 -- page" in p2


def test_d3_le_corrige_suit_le_meme_decoupage_et_la_meme_pagination(app_6e):
    _marquer(app_6e, ev1="autorisee", ev2="interdite")
    eleve = _corps(_tex(app_6e))
    corrige = _corps(_tex(app_6e, version="corrigee"))
    assert corrige.startswith(r"\begin{document}" + "\n" + r"\seqVersionCorrigee")
    assert _titres_exos(corrige) == _titres_exos(eleve)
    assert "Partie 2 --- calculatrice autorisée" in corrige
    assert r"\setcounter{page}{1}" in corrige


# ── D4 : durée de la partie 1 ────────────────────────────────────────────────

def test_d4_duree_proportionnelle_aux_points_arrondie_aux_5_min_au_moins_10():
    f = mq.duree_partie1_auto
    assert f(3, 8) == 20            # 20,6 → 20
    assert f(9, 20) == 25           # 24,75 → 25
    assert f(10, 22) == 25          # 25 pile
    assert f(1, 20) == 10           # 2,75 → minimum 10
    assert f(4.5, 22) == 10         # 11,25 → 10
    assert f(20, 20) == 55          # au plus la séance
    assert f(0, 0) == 10


def test_d4_duree_reglee_dans_l_atelier_prime_et_vide_revient_au_calcul(app_6e):
    _marquer(app_6e, ev1="autorisee", ev2="interdite")
    cl = app_6e.test_client()
    ev = cl.get("/api/evaluations/E6").get_json()["evaluation"]
    assert (ev["deux_parties"], ev["duree_partie1"], ev["duree_partie1_auto"]) == (True, None, 20)
    ev = cl.patch("/api/evaluations/E6", json={"duree_partie1": "25"}).get_json()["evaluation"]
    assert ev["duree_partie1"] == 25
    assert "à rendre au bout de 25 min" in _tex(app_6e)
    ev = cl.patch("/api/evaluations/E6", json={"duree_partie1": ""}).get_json()["evaluation"]
    assert ev["duree_partie1"] is None
    assert "à rendre au bout de 20 min" in _tex(app_6e)


@pytest.mark.parametrize("valeur", ("x", "12.5", 0, 500, True))
def test_d4_duree_invalide_refusee_par_la_route(app_6e, valeur):
    r = app_6e.test_client().patch("/api/evaluations/E6", json={"duree_partie1": valeur})
    assert r.status_code == 400 and r.get_json()["code"] == "duree_partie1_invalide"


def test_d4_migration_de_la_colonne_idempotente():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE evaluations (id TEXT PRIMARY KEY, titre TEXT)")
    assert mq.migrer_duree_partie1(c) is True
    assert mq.migrer_duree_partie1(c) is False
    assert mq.colonne_duree_presente(c)


def test_d4_base_de_l_appli_migree_au_demarrage(app_6e):
    with app_6e.json_store._conn() as c:
        assert mq.colonne_duree_presente(c)


# ── D5 : barème unique, sujets A et B ────────────────────────────────────────

def test_d5_bareme_unique_en_tete_de_la_partie_1_meme_objectif_dans_les_deux_parties(app_6e):
    """Un objectif évalué dans les deux parties garde une seule colonne
    (somme des points) : le barème est par compétence, pas par partie."""
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE objectif_exos SET objectif_id='o602', ordre=2 WHERE exercice_id='ev2'")
        c.execute("UPDATE exercices SET calculatrice='autorisee' WHERE id='ev1'")
        c.execute("UPDATE exercices SET calculatrice='interdite' WHERE id='ev2'")
        c.commit()
    tex = _corps(_tex(app_6e))
    assert tex.count(r"\seqBaremeCompetences") == 1
    p1, p2 = tex.split(r"\setcounter{page}{1}")
    assert r"\seqBaremeCompetences{S01-02/{8},S01-03/{0},Bonus/{2}}{8}" in p1
    assert r"\seqBaremeCompetences" not in p2


def test_d5_sujets_a_et_b_meme_decoupage_par_position(app_6e):
    _marquer(app_6e, ev1="autorisee", ev2="interdite")
    for version in ("eleve", "corrigee"):
        a = _corps(_tex(app_6e, sujet="A", version=version))
        b = _corps(_tex(app_6e, sujet="B", version=version))
        pa, pb = a.split(r"\setcounter{page}{1}"), b.split(r"\setcounter{page}{1}")
        assert [len(_titres_exos(x)) for x in pa] == [len(_titres_exos(x)) for x in pb] == [1, 2]
        assert "Sujet B2" in pb[0] or "B2" in pb[0]          # énoncé B de ev2 en partie 1
        assert "Partie 1 --- sans calculatrice" in pb[0]


def test_d2_rendu_d_un_exercice_porte_le_numero_du_sujet_coupe(app_6e):
    from services.rendu_atome_6e import generer_tex_atome_6e
    _marquer(app_6e, ev1="autorisee", ev2="interdite")
    with app_6e.json_store._conn() as c:
        t1 = generer_tex_atome_6e(c, "ev1")
        t2 = generer_tex_atome_6e(c, "ev2")
    assert r"\setcounter{seqExoEval}{1}" in t1       # Exercice 2 (partie 2)
    assert r"\setcounter{seqExoEval}{0}" in t2       # Exercice 1 (partie 1)


def test_d4_plan_de_travail_annonce_le_sujet_en_deux_parties(app_6e):
    from services.plan_travail_6e import generer_plan_travail_6e
    _marquer(app_6e, ev1="autorisee", ev2="interdite")
    with app_6e.json_store._conn() as c:
        tex = generer_plan_travail_6e(c, "N09", "S01")
    assert "en deux parties~: sans calculatrice, ramassée au bout de 20~min" in tex


# ── C3 revu : pas d'avertissement à tort ─────────────────────────────────────

def test_c3_pas_d_avertissement_pour_un_sujet_en_deux_parties(app_6e):
    _marquer(app_6e, ev1="autorisee", ev2="interdite")
    cl = app_6e.test_client()
    ev = cl.patch("/api/evaluations/E6", json={"calculatrice": "interdite"}).get_json()
    assert ev["evaluation"]["calculatrice_avertissement"] == ""
    # Sujet d'un seul tenant : l'avertissement C3 est inchangé.
    _marquer(app_6e, ev2="")
    ev = cl.get("/api/evaluations/E6").get_json()["evaluation"]
    assert "à la main" in ev["calculatrice_avertissement"] and ev["deux_parties"] is False


def test_d1_interface_bloc_sujet_en_deux_parties_et_champ_duree():
    html = (APPLI / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="atl-eval-deux-parties"' in html and 'id="atl-eval-duree-partie1"' in html
    assert "Sujet en deux parties (sans / avec calculatrice)" in html


# ── I3 : import de calculatrice_exercices ───────────────────────────────────

TITRE = "Évaluation --- Nombres"
EXOS = [("Calcul posé", 6, "S01-02", "Énoncé C."), ("Problème", 12, "S01-02", "Énoncé P."),
        ("Bonus : Qui suis-je ?", 2, "S01-02", "Énoncé bonus.")]


def _lot(tmp_path, nom, calculatrice=None, table=None, table_b="meme"):
    lots = _lot_s01(tmp_path / nom)
    f = lots / "S01" / "S01.json"
    lot = json.loads(f.read_text(encoding="utf-8"))
    ev = _evaluation(TITRE, EXOS)
    for e in ev:
        if calculatrice is not None:
            e["calculatrice"] = calculatrice
        if table is not None:
            e["calculatrice_exercices"] = table if (e["sujet"] == "A" or table_b == "meme") \
                else table_b
    lot["evaluations"] = ev
    f.write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")
    return lots


def _etat(db):
    c = _conn(db)
    ev = c.execute("SELECT id, calculatrice FROM evaluations WHERE niveau='N09' AND titre=?",
                   (TITRE,)).fetchone()
    exos = [r[0] for r in c.execute(
        "SELECT x.calculatrice FROM evaluation_exercices ee JOIN exercices x "
        "ON x.id = ee.exercice_id WHERE ee.evaluation_id=? ORDER BY ee.ordre", (ev["id"],))]
    c.close()
    return ev["calculatrice"], exos


def _appliquer(db, lots):
    assert imp.main(["--db", str(db), "--lots", str(lots), "--apply", "--yes"]) == 0


def _essai(db, lots):
    return imp.essai_a_blanc(db, imp.charger_lots(lots), imp.charger_referentiel(),
                             db.parent / "images").texte()


def test_i3_import_marque_chaque_exercice_et_l_essai_annonce_le_decoupage(base, tmp_path):
    lots = _lot(tmp_path, "a", "autorisee", {"1": "interdite"})
    texte = _essai(base, lots)
    assert ("en deux parties : partie 1 sans calculatrice ex. 1 (6 pts, 20 min), "
            "partie 2 calculatrice autorisée ex. 2 et 3 (12 pts + bonus)") in texte
    _appliquer(base, lots)
    # I3 : réglage '' (les mentions viennent de D2), exercices marqués un à un.
    assert _etat(base) == ("", ["interdite", "autorisee", "autorisee"])
    etat = _dump(base, ("evaluations", "exercices", "evaluation_exercices"))
    _appliquer(base, lots)                                        # idempotent
    assert _dump(base, ("evaluations", "exercices", "evaluation_exercices")) == etat


def test_i3_positions_non_listees_heritent_de_la_cle_calculatrice(base, tmp_path):
    _appliquer(base, _lot(tmp_path, "a", "interdite", {"2": "autorisee"}))
    assert _etat(base) == ("", ["interdite", "autorisee", "interdite"])
    # Table retirée : retour au marquage d'un seul tenant (C1 de la v0.52.8).
    _appliquer(base, _lot(tmp_path, "b", "interdite"))
    assert _etat(base) == ("interdite", ["interdite", "interdite", "interdite"])


def test_i3_entrees_invalides_et_tables_differentes_signalees(base, tmp_path):
    lots = _lot(tmp_path, "a", "autorisee", {"1": "interdite", "9": "interdite", "2": "oui"},
                table_b={"2": "interdite"})
    texte = _essai(base, lots)
    assert "position '9' hors du sujet (1 à 3), ignorée" in texte
    assert "calculatrice_exercices[2] = 'oui' inconnue" in texte
    assert "différente aux sujets A et B (celle du sujet A est retenue)" in texte
    _appliquer(base, lots)
    assert _etat(base) == ("", ["interdite", "autorisee", "autorisee"])


def test_i3_evaluation_validee_jamais_modifiee(base, tmp_path):
    _appliquer(base, _lot(tmp_path, "a", "interdite"))
    c = _conn(base)
    c.execute("UPDATE evaluations SET etat_code='valide' WHERE niveau='N09' AND titre=?", (TITRE,))
    c.commit()
    c.close()
    _appliquer(base, _lot(tmp_path, "b", "interdite", {"2": "autorisee"}))
    assert _etat(base) == ("interdite", ["interdite", "interdite", "interdite"])


def test_i3_import_ajoute_la_colonne_duree_d_une_base_v0_52_8(base, tmp_path):
    c = _conn(base)
    c.execute("ALTER TABLE evaluations DROP COLUMN duree_partie1")
    c.commit()
    c.close()
    texte = _essai(base, _lot(tmp_path, "a", "autorisee", {"1": "interdite"}))
    assert "colonne duree_partie1 des évaluations (v0.52.9)" in texte
    c = _conn(base)
    assert not mq.colonne_duree_presente(c)                       # essai : rien écrit
    c.close()
