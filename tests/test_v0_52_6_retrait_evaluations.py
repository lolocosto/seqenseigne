"""tests/test_v0_52_6_retrait_evaluations.py — v0.52.6

Retrait d'évaluations par l'outil d'import (`outils/import_lot6e.py`,
clé `evaluations_retirees` des lots recomposés) : décision de Laurent du
19 octobre 2026, une évaluation sur 20 par séquence, tests courts réservés
aux mises en route. Chaque test nomme la décision qu'il protège
(doc/redemarrage_v0_52_6.md) :

- R1 retirer avant d'importer (évaluations listées non validées, puis
  exercices EV devenus orphelins non validés, avec leurs liens) ;
- R2 un numéro EV occupé n'est jamais réattribué (numéro de queue) ;
- R3 liens EV d'un atome réécrit remis à son objectif ;
- R4 évaluation validée : ses exercices EV ne sont pas touchés.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_v0_52_0_import_lot6e import (  # noqa: E402,F401
    _conn, _dump, _lot_s01, _md5, base, imp)

TABLES = ("exercices", "objectif_exos", "evaluations", "evaluation_exercices",
          "evaluation_objectifs")

ANCIENNE = ("Évaluation --- Nombres", [("Valeur des chiffres", 5, "S01-02", "Énoncé V."),
                                      ("Un quotient", 3, "S01-12", "Énoncé Q.")])
TEST_COURT = ("Test court --- Fractions", [("Fractions égales", 4, "S01-12", "Énoncé F.")])
# Recomposée : EV01 identique (réutilisé), EV02 et EV03 changent de sens.
NOUVELLE = ("Évaluation --- Nombres et fractions",
            [("Valeur des chiffres", 5, "S01-02", "Énoncé V."),
             ("Fractions égales", 4, "S01-12", "Énoncé F2."),
             ("Bonus : Qui suis-je ?", 2, "S01-02", "Énoncé bonus.")])


def _latex(titre, exos, sujet):
    corps = [r"\seqTitreEvalSix{" + titre + "}{Sujet " + sujet + "}"]
    for t, pts, obj, txt in exos:
        corps.append(r"\seqExoEval{" + t + "}{" + f"{pts} pts --- {obj}" + "}\n"
                     + txt.replace("Énoncé", f"Énoncé {sujet}"))
    return "\n\n".join(corps)


def _evaluation(titre, exos):
    bareme: dict = {}
    for t, pts, obj, _ in exos:
        cle = "Bonus" if t.startswith("Bonus") else obj
        bareme[cle] = bareme.get(cle, 0) + pts
    return [{"titre": titre, "sujet": s, "bareme": [[k, v] for k, v in bareme.items()],
             "latex": _latex(titre, exos, s)} for s in ("A", "B")]


def _lot(tmp_path, nom, evaluations, retirees=None):
    d = _lot_s01(tmp_path / nom)
    f = d / "S01" / "S01.json"
    lot = json.loads(f.read_text(encoding="utf-8"))
    lot["evaluations"] = [x for t, e in evaluations for x in _evaluation(t, e)]
    if retirees is not None:
        lot["evaluations_retirees"] = retirees
    f.write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")
    return d


def _ancien(tmp_path):
    return _lot(tmp_path, "ancien", [ANCIENNE, TEST_COURT])


def _recompose(tmp_path, evaluations=(NOUVELLE,)):
    return _lot(tmp_path, "nouveau", list(evaluations), [ANCIENNE[0], TEST_COURT[0]])


def _appliquer(db, lots):
    assert imp.main(["--db", str(db), "--lots", str(lots), "--apply", "--yes"]) == 0


def _essai(db, lots):
    return imp.essai_a_blanc(db, imp.charger_lots(lots), imp.charger_referentiel(),
                             db.parent / "images")


def _ev(c):
    return {r["num"]: r for r in c.execute(
        "SELECT * FROM exercices WHERE niveau='N09' AND sequence='S01' AND serie_code='EV'")}


def _liens_ev(c):
    return [tuple(r) for r in c.execute(
        "SELECT e.num, o.code FROM objectif_exos oe JOIN exercices e ON e.id=oe.exercice_id "
        "JOIN objectifs o ON o.id=oe.objectif_id WHERE oe.serie='EV' ORDER BY e.num, o.code")]


def _compo(c, titre):
    return [r[0] for r in c.execute(
        "SELECT x.num FROM evaluations e JOIN evaluation_exercices ee ON ee.evaluation_id=e.id "
        "JOIN exercices x ON x.id=ee.exercice_id WHERE e.niveau='N09' AND e.titre=? "
        "ORDER BY ee.ordre", (titre,))]


def test_r1_evaluations_retirees_puis_orphelins_ev_retires_avant_l_import(base, tmp_path):
    """Une évaluation sur 20 par séquence : les anciennes sont retirées, les
    EV qui ne servent plus et ont changé de sens sont retirés avec leurs
    liens ; l'EV identique au même numéro est réutilisé (même id)."""
    _appliquer(base, _ancien(tmp_path))
    c = _conn(base)
    ev01_avant, ev02_avant = _ev(c)[1]["id"], _ev(c)[2]["id"]
    c.close()
    _appliquer(base, _recompose(tmp_path))
    c = _conn(base)
    assert [r[0] for r in c.execute("SELECT titre FROM evaluations WHERE niveau='N09'")] \
        == [NOUVELLE[0]]
    ev = _ev(c)
    assert sorted(ev) == [1, 2, 3]
    assert ev[1]["id"] == ev01_avant                      # identique : réutilisé
    assert ev[2]["id"] != ev02_avant                      # changé de sens : recréé
    assert ev[2]["enonce"] == "Énoncé A F2." and ev[3]["titre"].startswith("Bonus")
    assert _liens_ev(c) == [(1, "02"), (2, "12")]         # bonus : aucun lien
    assert _compo(c, NOUVELLE[0]) == [1, 2, 3]
    assert c.execute("SELECT COUNT(*) FROM evaluation_exercices ee LEFT JOIN evaluations e ON "
                     "e.id=ee.evaluation_id WHERE e.id IS NULL").fetchone()[0] == 0


def test_r1_retrait_idempotent_le_second_apply_ne_change_rien(base, tmp_path):
    _appliquer(base, _ancien(tmp_path))
    lots = _recompose(tmp_path)
    _appliquer(base, lots)
    etat = _dump(base, TABLES)
    r = _essai(base, lots)
    assert any("à retirer : absente (déjà retirée)" in d for d in r.documents)
    assert not any("orphelin" in d for d in r.documents)
    _appliquer(base, lots)
    assert _dump(base, TABLES) == etat


def test_r1_essai_a_blanc_montre_chaque_retrait_sans_rien_ecrire(base, tmp_path):
    _appliquer(base, _ancien(tmp_path))
    avant = _md5(base)
    r = _essai(base, _recompose(tmp_path))
    assert _md5(base) == avant
    docs = "\n".join(r.documents)
    assert f"« {ANCIENNE[0]} » (n° 1) : retirée (2 exercice(s)" in docs
    assert f"« {TEST_COURT[0]} » (n° 2) : retirée (1 exercice(s)" in docs
    assert "N09/S01/EV02 « Un quotient » : orphelin, retiré" in docs
    assert "N09/S01/EV03 « Fractions égales » : orphelin, retiré" in docs
    assert "EV01 « Valeur" not in docs


def test_r1_journal_garde_les_lignes_retirees_pour_les_restaurer(base, tmp_path):
    _appliquer(base, _ancien(tmp_path))
    c = _conn(base)
    ancienne = dict(c.execute("SELECT * FROM evaluations WHERE titre=?",
                              (ANCIENNE[0],)).fetchone())
    ev02 = dict(_ev(c)[2])
    c.close()
    _appliquer(base, _recompose(tmp_path))
    journaux = sorted((base.parent / "sauvegardes").glob("journal_import_lot6e_*.json"))
    j = json.loads(journaux[-1].read_text(encoding="utf-8"))
    evs = [x for x in j["retraits"] if x["quoi"] == "evaluation"]
    exos = [x for x in j["retraits"] if x["quoi"] == "exercice"]
    assert [x["evaluations"] for x in evs if x["titre"] == ANCIENNE[0]] == [ancienne]
    assert [len(x["evaluation_exercices"]) for x in evs] == [2, 1]
    assert all(x["evaluation_objectifs"] for x in evs)
    rest = next(x for x in exos if x["cle"] == "N09/S01/EV02")
    assert rest["exercices"] == ev02 and rest["objectif_exos"][0]["serie"] == "EV"
    # La sauvegarde .db d'avant l'import contient encore l'ancienne évaluation.
    sauvegardes = sorted((base.parent / "sauvegardes").glob("avant_import_lot6e_*.db"))
    s = _conn(sauvegardes[-1])
    assert s.execute("SELECT COUNT(*) FROM evaluations WHERE titre=?",
                     (ANCIENNE[0],)).fetchone()[0] == 1


def test_r1_r2_evaluation_validee_gardee_et_ses_numeros_ev_jamais_reattribues(base, tmp_path):
    """Le test court validé reste intact (EV03 compris) : l'exercice de la
    nouvelle évaluation prévu en EV03 prend le numéro de queue EV04."""
    _appliquer(base, _ancien(tmp_path))
    c = _conn(base)
    c.execute("UPDATE evaluations SET etat_code='valide' WHERE titre=?", (TEST_COURT[0],))
    c.commit()
    ev03 = dict(_ev(c)[3])
    c.close()
    lots = _recompose(tmp_path)
    r = _essai(base, lots)
    assert any(f"« {TEST_COURT[0]} » à retirer, mais validée" in a for a in r.anomalies)
    assert any(f"EV03 utilisé par « {TEST_COURT[0]} » → EV04" in i for i in r.infos)
    _appliquer(base, lots)
    c = _conn(base)
    assert dict(_ev(c)[3]) == ev03
    assert _compo(c, TEST_COURT[0]) == [3]
    assert _compo(c, NOUVELLE[0]) == [1, 2, 4]
    etat = _dump(base, TABLES)
    _appliquer(base, lots)
    assert _dump(base, TABLES) == etat                    # numéro de queue retrouvé


def test_r1_r2_exercice_ev_orphelin_valide_garde_signale_et_numero_occupe(base, tmp_path):
    _appliquer(base, _ancien(tmp_path))
    c = _conn(base)
    c.execute("UPDATE exercices SET etat_code='valide' WHERE niveau='N09' AND sequence='S01' "
              "AND serie_code='EV' AND num=2")
    c.commit()
    c.close()
    lots = _recompose(tmp_path)
    r = _essai(base, lots)
    assert any("EV02 « Un quotient » orphelin mais validé" in a for a in r.anomalies)
    _appliquer(base, lots)
    c = _conn(base)
    ev = _ev(c)
    assert ev[2]["titre"] == "Un quotient" and ev[2]["etat_code"] == "valide"
    # EV02 occupé → numéro de queue EV03 (EV03 ancien, orphelin, retiré) ;
    # le bonus, prévu en EV03, passe en EV04.
    assert _compo(c, NOUVELLE[0]) == [1, 3, 4]
    assert ev[3]["enonce"] == "Énoncé A F2." and ev[4]["titre"].startswith("Bonus")


def test_r3_lien_ev_perime_retire_quand_la_recomposition_reecrit_un_atome(base, tmp_path):
    """Même titre gardé, EV02 change d'objectif (S01-12 → S01-02) : l'atome
    est réécrit sur place et ne reste pas relié à l'ancien objectif."""
    _appliquer(base, _ancien(tmp_path))
    meme_titre = (ANCIENNE[0], [ANCIENNE[1][0], ("Composer", 3, "S01-02", "Énoncé C.")])
    _appliquer(base, _lot(tmp_path, "meme", [meme_titre], [TEST_COURT[0]]))
    c = _conn(base)
    assert _ev(c)[2]["titre"] == "Composer"
    assert _liens_ev(c) == [(1, "02"), (2, "02")]


def test_r4_evaluation_validee_ses_exercices_ev_ne_sont_pas_reecrits(base, tmp_path):
    lots = _recompose(tmp_path)
    _appliquer(base, lots)
    c = _conn(base)
    c.execute("UPDATE evaluations SET etat_code='valide'")
    c.commit()
    c.close()
    etat = _dump(base, TABLES)
    f = lots / "S01" / "S01.json"
    lot = json.loads(f.read_text(encoding="utf-8"))
    for e in lot["evaluations"]:
        e["latex"] = e["latex"].replace("Énoncé", "Nouvel énoncé")
    f.write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")
    r = _essai(base, lots)
    assert any("validée, non modifiée — exercices EV non touchés" in d for d in r.documents)
    _appliquer(base, lots)
    assert _dump(base, TABLES) == etat


def test_deux_apply_dans_la_meme_seconde_n_ecrasent_ni_sauvegarde_ni_journal(base, tmp_path,
                                                                            monkeypatch):
    """Sinon le second --apply remplace la sauvegarde d'avant retrait et le
    journal qui permet de restaurer les évaluations retirées."""
    from datetime import datetime as vrai

    class Fige(vrai):
        @classmethod
        def now(cls, tz=None):
            return vrai(2026, 10, 20, 8, 0, 0)
    monkeypatch.setattr(imp, "datetime", Fige)
    _appliquer(base, _ancien(tmp_path))
    _appliquer(base, _recompose(tmp_path))
    d = base.parent / "sauvegardes"
    assert len(list(d.glob("avant_import_lot6e_*.db"))) == 2
    journaux = sorted(d.glob("journal_import_lot6e_*.json"))
    assert len(journaux) == 2
    assert any("retraits" in json.loads(j.read_text(encoding="utf-8")) for j in journaux)
