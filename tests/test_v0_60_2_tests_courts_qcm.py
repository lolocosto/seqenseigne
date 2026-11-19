"""tests/test_v0_60_2_tests_courts_qcm.py — v0.60.2

Tests courts de 4e en QCM (décisions 16 et 17 du 18 novembre ; signalement
de Laurent du 18 novembre, 22 h 39 : « 16 validé, 16 en échec —
bareme_qcm_manquant »). Chaque test nomme ce qu'il protège :

  Q1 un exercice QCM importé reçoit son barème QCM (bonne réponse = points
     d'une question, partielle 0, mauvaise 0) : sans lui, la validation
     d'une évaluation notée est refusée ;
  Q2 le réimport des mêmes lots sur un test court en cours (état de Laurent
     après la v0.60.1) pose les champs manquants et rien d'autre ; un second
     réimport ne change plus rien ;
  Q3 points d'une question : points / nombre de questions, 1 pt par défaut
     (avec avertissement) quand ils ne se répartissent pas ;
  R4 une évaluation validée identique au lot n'est plus une anomalie ;
  FIG figure absente du lot mais déjà dans images (appli) : signalée, pas une anomalie ;
  D16-17 plus d'avertissement « un test court est sur 10 » ni « pas de
     bonus » ; bonus de 1 pt contrôlé pour les évaluations du cycle 4 seulement.
"""
from __future__ import annotations

import sqlite3

import pytest

from outils import import_lot6e as imp
from services import evaluations as svc_eval
from tests.test_v0_52_0_import_lot6e import base as base_v052  # noqa: F401
from tests.test_v0_60_0_version2_fiches import _imp, _lot, _paire, b4  # noqa: F401
from tests.test_v0_59_0_ref4e_fiches import (  # noqa: F401
    _archiver,
    _table_reduite,
    base,
    base4e,
)

TC = "Test court --- Produits"


def _qcm(n: int) -> str:
    lignes = "\n".join(r"\midrule \seqQcmQuestion{Q%d} & \seqCaseCocher[x]{a} & "
                       r"\seqCaseCocher{b} \\" % k for k in range(1, n + 1))
    return "\\begin{seqQcm}[nbReps=2,explication=non]\n" + lignes + "\n\\bottomrule\n\\end{seqQcm}"


def _test_court_qcm(n1=3, n2=2, pts=None):
    """Test court comme ceux des lots de 4e : un exercice QCM par objectif,
    1 pt par question (une question par carte), total = nombre de questions,
    pas de bonus."""
    p1, p2 = pts or (n1, n2)
    latex = ("\\seqExoEval{Multiplier}{%g pts --- A1-02}\n%s\n"
             "\\seqExoEval{Diviser}{%g pts --- A1-03}\n%s\n" % (p1, _qcm(n1), p2, _qcm(n2)))
    return [{"titre": TC, "sujet": s, "partie": 1, "latex": latex,
             "bareme": [["A1-02", p1], ["A1-03", p2]], "total": p1 + p2} for s in ("A", "B")]


def _conn(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


def _baremes(c, titre=TC):
    return [tuple(r) for r in c.execute(
        "SELECT x.type_format, ee.bareme_points, ee.bareme_qcm_ok, ee.bareme_qcm_partiel, "
        "ee.bareme_qcm_ko FROM evaluations e JOIN evaluation_exercices ee ON "
        "ee.evaluation_id = e.id JOIN exercices x ON x.id = ee.exercice_id "
        "WHERE e.niveau = 'N11' AND e.titre = ? ORDER BY ee.ordre", (titre,))]


def _valider(c, titre=TC):
    ev_id = c.execute("SELECT id FROM evaluations WHERE niveau = 'N11' AND titre = ?",
                      (titre,)).fetchone()[0]
    svc_eval.valider_evaluation(c, ev_id)
    c.commit()


def _avec_tc(**kw):
    def modif(lot):
        lot["tests_courts"] = _test_court_qcm(**kw)
    return modif


# ── Q1 ───────────────────────────────────────────────────────────────────────

def test_q1_test_court_qcm_importe_est_validable_bareme_un_point_par_question(b4, tmp_path,
                                                                            capsys):
    out = _imp(b4, _lot(tmp_path, _avec_tc()), capsys)
    c = _conn(b4)
    # bareme_points = total de l'exercice (sujets, barème par objectif) ;
    # bonne réponse = 1 pt par question, partielle et mauvaise = 0.
    assert _baremes(c) == [("qcm", 3.0, 1.0, 0.0, 0.0), ("qcm", 2.0, 1.0, 0.0, 0.0)]
    assert f"évaluation « {TC} » : créée" in out and "QCM : 2 exercice(s)" in out
    _valider(c)                                     # v0.60.1 : bareme_qcm_manquant
    assert c.execute("SELECT etat_code FROM evaluations WHERE titre = ?",
                     (TC,)).fetchone()[0] == "valide"


def test_q1_sans_bareme_qcm_la_validation_est_refusee_cause_du_signalement(b4, tmp_path,
                                                                         capsys):
    _imp(b4, _lot(tmp_path, _avec_tc()), capsys)
    c = _conn(b4)
    c.execute("UPDATE evaluation_exercices SET bareme_qcm_ok = NULL, bareme_qcm_partiel = NULL, "
              "bareme_qcm_ko = NULL")
    with pytest.raises(svc_eval.ValidationPedagogiqueErreur) as e:
        _valider(c)
    assert {r["code"] for r in e.value.details["raisons"]} == {"bareme_qcm_manquant"}


# ── Q2 ───────────────────────────────────────────────────────────────────────

def test_q2_reimport_des_memes_lots_repare_un_test_court_en_cours_et_rien_d_autre(
        b4, tmp_path, capsys):
    lots = _lot(tmp_path, _avec_tc())
    _imp(b4, lots, capsys)
    c = _conn(b4)
    # État de Laurent après l'import v0.60.1 : barème QCM absent, test court en cours.
    c.execute("UPDATE evaluation_exercices SET bareme_qcm_ok = NULL, bareme_qcm_partiel = NULL, "
              "bareme_qcm_ko = NULL")
    c.commit()

    def cliche():
        return {t: sorted(map(tuple, c.execute(f"SELECT * FROM {t}")))
                for t in ("exercices", "objectif_exos", "evaluation_objectifs",
                          "cartes_automatisme", "objectifs")}
    avant = cliche()
    # L'essai à blanc ne demande rien à repasser (le test court est en cours).
    capsys.readouterr()
    assert imp.main(["--niveau", "N11", "--db", str(b4), "--lots", str(lots)]) == 0
    assert "== À repasser en cours" not in capsys.readouterr().out
    out = _imp(b4, lots, capsys)
    c = _conn(b4)
    assert f"évaluation « {TC} » : mise à jour" in out
    assert _baremes(c) == [("qcm", 3.0, 1.0, 0.0, 0.0), ("qcm", 2.0, 1.0, 0.0, 0.0)]
    assert cliche() == avant                        # rien d'autre ne bouge
    out = _imp(b4, lots, capsys)                    # idempotence
    assert f"évaluation « {TC} » : inchangée" in out
    _valider(_conn(b4))


def test_q2_evaluation_validee_identique_au_lot_pas_d_anomalie_liens_ev_au_meme_rang(
        b4, tmp_path, capsys):
    def modif(lot):
        lot["evaluations"] = _paire("Évaluation --- Produits", bonus=1, pts=(12, 8))
        lot["tests_courts"] = _test_court_qcm()
    lots = _lot(tmp_path, modif)
    _imp(b4, lots, capsys)
    c = _conn(b4)
    rangs = sorted(map(tuple, c.execute("SELECT * FROM objectif_exos WHERE serie = 'EV'")))
    _valider(c, "Évaluation --- Produits")
    c.execute("UPDATE evaluation_exercices SET bareme_qcm_ok = NULL, bareme_qcm_partiel = NULL, "
              "bareme_qcm_ko = NULL WHERE evaluation_id = (SELECT id FROM evaluations "
              "WHERE titre = ?)", (TC,))
    c.commit()
    out = _imp(b4, lots, capsys)
    anomalies = out.split("== Anomalies")[1].split("==")[0]
    assert "validée dans le module Évaluations" not in anomalies
    assert "« Évaluation --- Produits » : validée, identique au lot — non modifiée" in out
    # Les exercices du test court ne passent pas devant ceux de l'évaluation validée.
    c = _conn(b4)
    assert sorted(map(tuple, c.execute("SELECT * FROM objectif_exos WHERE serie = 'EV'"))) == rangs
    _valider(c)


# ── Q3 ───────────────────────────────────────────────────────────────────────

def test_q3_points_d_une_question_repartis_sinon_un_point_avec_avertissement():
    assert imp.bareme_qcm(_qcm(4), 4) == ((1.0, 0.0, 0.0), "")
    assert imp.bareme_qcm(_qcm(4), 2) == ((0.5, 0.0, 0.0), "")       # pas de 0,5
    (ok, _, _), motif = imp.bareme_qcm(_qcm(3), 5)
    assert ok == 1.0 and "5 pts pour 3 question(s)" in motif
    (ok, _, _), motif = imp.bareme_qcm(r"\begin{seqQcm}\end{seqQcm}", 2)
    assert ok == 1.0 and "non repérées" in motif
    # \seqQcmQuestionX (autre macro) n'est pas une question.
    assert imp.bareme_qcm(_qcm(2) + r"\seqQcmQuestionX{}", 2)[0][0] == 1.0


def test_q3_exercice_standard_bareme_qcm_non_touche(b4, tmp_path, capsys):
    def modif(lot):
        lot["evaluations"] = _paire("Évaluation --- Produits", bonus=1, pts=(12, 8))
    _imp(b4, _lot(tmp_path, modif), capsys)
    assert {b[0] for b in _baremes(_conn(b4), "Évaluation --- Produits")} == {"standard"}
    assert {b[2:] for b in _baremes(_conn(b4), "Évaluation --- Produits")} == {(None, None, None)}


# ── D16-17 ───────────────────────────────────────────────────────────────────

def test_d17_test_court_ni_sur_10_ni_bonus_signales_total_somme_des_questions(b4, tmp_path,
                                                                            capsys):
    out = _imp(b4, _lot(tmp_path, _avec_tc(n1=9, n2=6)), capsys)
    assert "un test court est sur 10" not in out
    assert f"test court « {TC} » : pas de bonus" not in out
    assert f"évaluation « {TC} »" in out and "total 15" in out


@pytest.mark.parametrize("niveau, bonus, attendu", [
    ("N11", 0, ["S évaluation « E » : pas de bonus (règle : 1 pt)"]),
    ("N11", 1, []),
    ("N09", 2, []),                                  # 6e : bonus de 2 pts, rien
])
def test_d16_bonus_controle_pour_les_evaluations_du_cycle_4_seulement(monkeypatch, niveau,
                                                                      bonus, attendu):
    monkeypatch.setattr(imp, "NIVEAU", niveau)
    exos = [{"points": 19, "bonus": False}] + ([{"points": bonus, "bonus": True}] if bonus else [])
    r = imp.Rapport()
    imp.controler_evaluation("S", "E", "evaluation", exos, r)
    assert r.avertissements == attendu
    r = imp.Rapport()
    imp.controler_evaluation("S", "T", "test_court", exos, r)
    assert r.avertissements == []                    # tests courts : aucun contrôle


# ── FIG — figure d'origine déjà présente dans images\ (coordinateur, 18 nov.) ─
# Les lots rétablissent les images d'origine des exercices repris
# (\includegraphics avec le nom de fichier de la base, ex. N11S04E07_enonce.png),
# que Laurent a déjà chez lui : le lot ne les fournit pas.

def test_fig_figure_absente_du_lot_mais_presente_dans_images_signalee_sans_anomalie(tmp_path):
    lot_dir = tmp_path / "A1"
    (lot_dir / "figures").mkdir(parents=True)
    images = tmp_path / "images"
    images.mkdir()
    (images / "N11S04E07_enonce.png").write_bytes(b"png d'origine")
    r = imp.Rapport()
    imp.copier_figures([{"sequence": "A1", "_dossier": lot_dir}],
                       {"A1": {"N11S04E07_enonce.png"}}, images, r, ecrire=True)
    assert r.anomalies == []
    assert r.figures == ["N11S04E07_enonce.png : déjà présente dans images "
                         "(non fournie par le lot)"]
    assert (images / "N11S04E07_enonce.png").read_bytes() == b"png d'origine"   # intacte


def test_fig_figure_introuvable_partout_reste_une_anomalie(tmp_path):
    lot_dir = tmp_path / "A1"
    (lot_dir / "figures").mkdir(parents=True)
    images = tmp_path / "images"
    images.mkdir()
    r = imp.Rapport()
    imp.copier_figures([{"sequence": "A1", "_dossier": lot_dir}],
                       {"A1": {"absente.png"}}, images, r, ecrire=True)
    assert r.anomalies == ["A1 : figure manquante absente.png"]
    assert r.figures == []
