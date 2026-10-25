"""tests/test_v0_53_1_mer_parties.py — v0.53.1

Mises en route de 6e en parties (décisions de Laurent du 22 octobre 2026,
doc/redemarrage_v0_53_1.md) :

1. MR1 révisé : une partie par objectif (ou paire liée), codes de la règle du
   principal, lus dans ref6e_v2 (« — partie n ») ;
2. I-MR7 : restructuration des séquences importées avec l'ancienne structure
   (une partie, M01-01…04) en gardant objectifs, exercices, liens et tests ;
3. MR3 révisé : une fiche de cours par partie ; P1 : libellé de partie ;
4. MR5 révisé : documents par partie ; P3 : un test court par partie ;
5. MR6 révisé : validation par partie, affichée dans l'atelier (route /mer).

Base de test reconstruite à chaque test (jamais de base réelle).
"""

from __future__ import annotations

import copy
import json
import re
import sqlite3
from pathlib import Path

import pytest

from app import create_app
from outils import import_lot6e as imp
from outils import import_lot6e_mer as imp_mer
from services import mises_en_route_6e as mer
from tests.test_v0_53_0_mises_en_route import (_appliquer, _conn, _dump, _ecrire_lot, _essai,
                                               _lot, base)  # noqa: F401  (fixture)

ICI = Path(__file__).resolve().parent
LOT_ANCIEN = ICI / "donnees_v0_53_0" / "lot6e" / "M01" / "M01.json"


# ── 1. Référentiel : parties et codes ───────────────────────────────────────

def test_ref6e_v2_donne_une_partie_par_objectif_sauf_les_paires_liees_de_m02_m03_m05():
    ref = imp_mer.referentiel_mer()
    parties = {k: [(o["code"], o["partie"]) for o in s["objectifs"]] for k, s in ref.items()}
    assert parties["M01"] == [("M01-02", 1), ("M01-12", 2), ("M01-22", 3), ("M01-32", 4)]
    assert parties["M02"] == [("M02-02", 1), ("M02-12", 2), ("M02-13", 2), ("M02-22", 3),
                              ("M02-32", 4)]
    assert parties["M03"][2:] == [("M03-22", 3), ("M03-23", 3)]
    assert parties["M05"][2:] == [("M05-22", 3), ("M05-23", 3)]
    assert parties["M06"] == [("M06-02", 1)]
    assert {k: s["parties"] for k, s in ref.items()} == {
        "M01": [1, 2, 3, 4], "M02": [1, 2, 3, 4], "M03": [1, 2, 3], "M04": [1, 2, 3, 4],
        "M05": [1, 2, 3], "M06": [1], "M07": [1, 2, 3]}


def test_codes_des_mises_en_route_suivent_la_regle_du_principal_car_01_reste_le_cours():
    for s in imp_mer.referentiel_mer().values():
        rangs: dict = {}
        for o in s["objectifs"]:
            r = rangs.setdefault(o["partie"], 0)
            assert o["code"][-2:] == imp_mer.code_attendu(o["partie"], r), o["code"]
            rangs[o["partie"]] = r + 1
            assert not o["code"].endswith("1")          # (p-1)1 réservé au Cours


def test_table_des_anciens_codes_de_ref6e_v2_est_la_correspondance_par_rang_de_l_import():
    """La restructuration (I-MR7) recode au rang ; la table « Anciens codes »
    du paragraphe du 22 octobre doit dire exactement la même chose."""
    texte = (imp.REFERENTIEL.parent / "ref6e_v2.md").read_text(encoding="utf-8")
    par = re.search(r"Anciens codes : (.+?)\n", texte).group(1)
    ref = imp_mer.referentiel_mer()
    attendu = {k: imp_mer.anciens_codes(s) for k, s in ref.items()}
    assert attendu["M01"] == {"01": "02", "02": "12", "03": "22", "04": "32"}
    assert "M01-01 → M01-02, M01-02 → M01-12, M01-03 → M01-22, M01-04 → M01-32" in par
    for seq, morceau in (("M02", "M02-01 → 02, 02 → 12, 03 → 13, 04 → 22, 05 → 32"),
                         ("M03", "M03-01 → 02, 02 → 12, 03 → 22, 04 → 23"),
                         ("M05", "M05-01 → 02, 02 → 12, 03 → 22, 04 → 23")):
        assert morceau in par
        assert ", ".join(f"{a} → {b}" for a, b in attendu[seq].items()) == \
            morceau.replace(f"{seq}-01", "01")
    assert attendu["M04"] == attendu["M01"] and "M04 et M07 : 01 → 02, 02 → 12, 03 → 22, " \
        "04 → 32" in par
    assert list(attendu["M07"].items()) == [("01", "02"), ("02", "12"), ("03", "22")]
    assert attendu["M06"] == {"01": "02"} and "M06-01 → M06-02" in par


def test_codes_mnn_cites_dans_ref6e_v2_existent_apres_la_renumerotation_du_22_octobre():
    """Dépendances, liens et tables de couverture renumérotés : tout code Mnn-nn
    cité (hors « ancien … » et table des anciens codes) est un objectif de la
    section « Mises en route »."""
    texte = (imp.REFERENTIEL.parent / "ref6e_v2.md").read_text(encoding="utf-8")
    codes = {o["code"] for s in imp_mer.referentiel_mer().values() for o in s["objectifs"]}
    cites = {c for l in texte.splitlines() if "Anciens codes" not in l
             for c in re.findall(r"(?<!ancien )\b(M0\d-\d\d)", l)}
    assert cites and cites <= codes, sorted(cites - codes)


def test_objectifs_6e_json_garde_s01_a_s13_seulement_car_les_mnn_sont_lues_dans_ref6e_v2():
    ref = imp.charger_referentiel()
    assert not any(k.startswith("M") for k in ref["parties"])
    assert "22 octobre 2026" in ref["source"]


def test_ref6e_v2_sans_marque_de_partie_reste_lu_en_une_partie(tmp_path):
    f = tmp_path / "ref.md"
    f.write_text("## Mises en route\n\n### M09 — Essai (2 exercices, un par séance)\n\n"
                 "*Thème A — Nombres*\n\n- M09-01 · Faire (2 séances)\n", encoding="utf-8")
    r = imp_mer.referentiel_mer(f)["M09"]
    assert r["parties"] == [1] and r["objectifs"][0]["partie"] == 1


# ── 2. Migration de la colonne libelle (P1) ─────────────────────────────────

def test_colonne_libelle_des_parties_ajoutee_une_seule_fois(tmp_path):
    c = sqlite3.connect(tmp_path / "x.db")
    c.execute("CREATE TABLE sequence_parties (id TEXT PRIMARY KEY, sequence_par_niveau_id "
              "TEXT, numero INTEGER)")
    c.execute("INSERT INTO sequence_parties VALUES ('p', 's', 1)")
    assert mer.migrer(c) is True
    assert mer.migrer(c) is False
    assert c.execute("SELECT libelle FROM sequence_parties").fetchone()[0] == ""


def test_base_de_l_appli_a_la_colonne_libelle_au_demarrage(base):
    assert mer.colonne_libelle_presente(sqlite3.connect(base))


# ── 3. Import au format v2 ───────────────────────────────────────────────────

def test_import_v2_pose_les_parties_et_leurs_libelles(base, tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    c = _conn(base)
    rows = c.execute("SELECT p.numero, p.libelle, o.code FROM sequence_parties p JOIN "
                     "sequences_par_niveau s ON s.id=p.sequence_par_niveau_id LEFT JOIN "
                     "objectifs o ON o.partie_id=p.id WHERE s.sequence_code='M01' "
                     "ORDER BY p.numero").fetchall()
    assert [tuple(r) for r in rows] == [(1, "Tables de multiplication", "02"),
                                        (2, "Compléments entiers", "12"),
                                        (3, "Complément décimal à 1", "22"),
                                        (4, "Arrondis", "32")]


def test_fiche_de_cours_de_partie_attachee_aux_objectifs_de_sa_partie_et_sans_objectif(base,
                                                                                      tmp_path):
    """MR3 révisé (P2) : comme la fiche de cours du principal l'est au
    « Cours » — objectif_id NULL (pas une fiche de résumé d'objectif)."""
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    c = _conn(base)
    rows = c.execute("SELECT f.titre, f.objectif_id, o.code FROM fiches_resume f JOIN "
                     "objectif_fiches x ON x.fiche_id=f.id JOIN objectifs o ON "
                     "o.id=x.objectif_id WHERE f.sequence='M01' ORDER BY o.code").fetchall()
    assert [tuple(r) for r in rows] == [("Tables de multiplication", None, "02"),
                                        ("Compléments entiers", None, "12"),
                                        ("Complément décimal à 1", None, "22"),
                                        ("Arrondis", None, "32")]


def test_lot_au_format_de_la_v0_53_0_refuse_car_une_fiche_de_cours_par_partie(base, tmp_path):
    ancien = json.loads(LOT_ANCIEN.read_text(encoding="utf-8"))
    avant = _dump(base)
    r = _essai(base, _ecrire_lot(tmp_path / "l", ancien))
    assert any("format de la v0.53.0" in a and "non importé" in a for a in r.anomalies)
    assert _dump(base) == avant


def test_import_v2_signale_partie_differente_du_referentiel_et_test_sur_deux_parties(base,
                                                                                    tmp_path):
    lot = _lot()
    lot["objectifs"][1]["partie"] = 1
    ev = lot["evaluations"][0]
    ev["bareme"] = [["M01-02", 4], ["M01-12", 4], ["Bonus", 2]]
    r = _essai(base, _ecrire_lot(tmp_path / "l", lot))
    txt = "\n".join(r.anomalies)
    assert "M01-12 : partie 1 dans le lot, 2 dans le référentiel (référentiel retenu)" in txt
    assert "objectifs de plusieurs parties (1, 2) — un test court par partie" in txt


def test_import_v2_partie_sans_test_court_signalee(base, tmp_path):
    lot = _lot()
    lot["evaluations"] = [e for e in lot["evaluations"] if e["partie"] != 3]
    r = _essai(base, _ecrire_lot(tmp_path / "l", lot))
    assert any("partie(s) sans test court dans le lot : 3" in a for a in r.anomalies)


# ── 4. Restructuration de l'ancienne structure (I-MR7) ──────────────────────

def _ref_ancien(ref: dict) -> dict:
    """Référentiel d'avant le 22 octobre : M01-01…04 dans une seule partie."""
    r = copy.deepcopy(ref)
    m = r["M01"]
    for i, o in enumerate(m["objectifs"], start=1):
        o["code"], o["partie"] = f"M01-{i:02d}", 1
    m["parties"] = [1]
    return r


def _lot_ancien_en_v2() -> dict:
    """Le lot de test de la v0.53.0 (M01-01…04, une fiche de séquence) mis
    dans l'enveloppe v2 pour le réimporter comme la v0.53.0 l'avait fait."""
    a = json.loads(LOT_ANCIEN.read_text(encoding="utf-8"))
    a["parties"] = [{"numero": 1, "titre": "", "fiche_cours": a.pop("fiche_cours")}]
    for o in a["objectifs"]:
        o["partie"] = 1
    return a


@pytest.fixture
def base_ancienne(base, tmp_path, monkeypatch):
    """Base dans l'état de la v0.53.0 (cas de Laurent) : M01 importé en une
    partie, codes 01…04, fiche de séquence (attachée à aucun objectif),
    test court « Tables et compléments »."""
    vrai = imp_mer.referentiel_mer()
    monkeypatch.setattr(imp_mer, "referentiel_mer", lambda *a, **k: _ref_ancien(vrai))
    _appliquer(base, _ecrire_lot(tmp_path / "ancien", _lot_ancien_en_v2()))
    c = sqlite3.connect(base)
    c.execute("DELETE FROM objectif_fiches WHERE fiche_id IN (SELECT id FROM fiches_resume "
              "WHERE sequence='M01')")
    c.execute("UPDATE sequence_parties SET libelle=''")
    c.commit()
    c.close()
    monkeypatch.setattr(imp_mer, "referentiel_mer", lambda *a, **k: vrai)
    return base


def _etat(db) -> dict:
    c = _conn(db)
    objs = {r["id"]: (r["code"], r["numero"]) for r in c.execute(
        "SELECT o.id, o.code, p.numero FROM objectifs o JOIN sequence_parties p ON "
        "p.id=o.partie_id JOIN sequences_par_niveau s ON s.id=p.sequence_par_niveau_id "
        "WHERE s.sequence_code='M01'")}
    liens = sorted((r[0], r[1]) for r in c.execute(
        "SELECT oe.exercice_id, oe.objectif_id FROM objectif_exos oe JOIN exercices e ON "
        "e.id=oe.exercice_id WHERE e.sequence='M01' AND oe.serie='MR'"))
    exos = sorted((r[0], r[1], r[2]) for r in c.execute(
        "SELECT id, serie_code, num FROM exercices WHERE sequence='M01'"))
    return {"objectifs": objs, "liens": liens, "exercices": exos}


def test_base_ancienne_reproduit_la_v0_53_0(base_ancienne):
    e = _etat(base_ancienne)
    assert sorted(e["objectifs"].values()) == [("01", 1), ("02", 1), ("03", 1), ("04", 1)]
    s = mer.lire_sequence_mer(_conn(base_ancienne), "N09", "M01")
    assert len(s["fiches_sans_partie"]) == 1


def test_restructuration_garde_objectifs_exercices_et_liens_sans_changer_un_numero(
        base_ancienne):
    """R2 et demande de Laurent : pas de suppression-recréation. Mêmes
    identifiants d'objectifs, d'exercices MR et EV, mêmes liens ; seuls
    codes et parties changent."""
    avant = _etat(base_ancienne)
    c = sqlite3.connect(base_ancienne)
    r = imp.Rapport()
    imp.executer(c, [], imp.charger_referentiel(), r, base_ancienne.parent / "images", False)
    c.commit()
    c.close()
    apres = _etat(base_ancienne)
    assert set(apres["objectifs"]) == set(avant["objectifs"])
    assert {avant["objectifs"][k][0]: v for k, v in apres["objectifs"].items()} == {
        "01": ("02", 1), "02": ("12", 2), "03": ("22", 3), "04": ("32", 4)}
    assert apres["liens"] == avant["liens"] and apres["exercices"] == avant["exercices"]
    assert any("M01-01 → M01-02 (partie 1)" in x for x in r.seq("M01")["lignes"])
    j = r.journal["restructuration"][0]
    assert j["sequence"] == "N09/M01" and len(j["objectifs"]) == 4


def test_restructuration_sans_lot_essai_a_blanc_puis_idempotente(base_ancienne):
    avant = _dump(base_ancienne)
    r = imp.essai_a_blanc(base_ancienne, [], imp.charger_referentiel(),
                          base_ancienne.parent / "images")
    assert any("restructurée en 4 partie(s)" in x for x in r.seq("M01")["lignes"])
    assert _dump(base_ancienne) == avant
    for _ in range(2):
        c = sqlite3.connect(base_ancienne)
        imp.executer(c, [], imp.charger_referentiel(), imp.Rapport(),
                     base_ancienne.parent / "images", False)
        c.commit()
        c.close()
        if _ == 0:
            une = _dump(base_ancienne)
    assert _dump(base_ancienne) == une


def test_restructuration_puis_lot_v2_fiche_de_sequence_et_ancien_test_retires(base_ancienne,
                                                                             tmp_path):
    lots = _ecrire_lot(tmp_path / "v2", _lot())
    _appliquer(base_ancienne, lots)
    c = _conn(base_ancienne)
    s = mer.lire_sequence_mer(c, "N09", "M01")
    assert s["fiches_sans_partie"] == []
    assert [p["fiche"]["titre"] for p in s["parties"]] == [
        "Tables de multiplication", "Compléments entiers", "Complément décimal à 1", "Arrondis"]
    assert [t["titre"] for t in s["tests"]] == [
        "Test court --- Tables de multiplication", "Test court --- Compléments entiers",
        "Test court --- Complément décimal à 1", "Test court --- Arrondis"]
    assert [t["partie"] for t in s["tests"]] == [1, 2, 3, 4]
    assert mer.valider_sequence_mer(c, "N09", "M01", s)["valide"]
    c.close()
    une = _dump(base_ancienne)
    _appliquer(base_ancienne, lots)
    assert _dump(base_ancienne) == une


def test_restructuration_refusee_si_un_element_est_valide(base_ancienne):
    c = sqlite3.connect(base_ancienne)
    c.execute("UPDATE exercices SET etat_code='valide' WHERE sequence='M01' AND "
              "serie_code='MR' AND num=2")
    c.commit()
    avant = _etat(base_ancienne)
    r = imp.Rapport()
    imp.executer(c, [], imp.charger_referentiel(), r, base_ancienne.parent / "images", False)
    c.commit()
    c.close()
    assert _etat(base_ancienne) == avant
    assert any("élément(s) validé(s) (MR02) : rien n'est touché" in a for a in r.anomalies)


def test_restructuration_ignore_une_structure_inconnue_et_le_signale(base_ancienne):
    c = sqlite3.connect(base_ancienne)
    c.execute("UPDATE objectifs SET code='09' WHERE code='04'")
    c.commit()
    r = imp.Rapport()
    imp.executer(c, [], imp.charger_referentiel(), r, base_ancienne.parent / "images", False)
    c.close()
    assert any("ni l'ancienne structure" in a for a in r.anomalies)


# ── 5. Documents par partie (MR5 révisé) ────────────────────────────────────

@pytest.fixture
def conn_v2(base, tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    return _conn(base)


def test_planche_d_une_partie_ne_contient_que_ses_seances(conn_v2):
    tex = mer.generer_document_mer(conn_v2, "N09", "M01", {"document": "planche",
                                                            "partie": 2})
    assert tex.count(r"\begin{seqBande}") == 2
    assert "séance 3 --- M01-12" in tex and "séance 4 --- M01-12" in tex
    assert "M01-02" not in tex


def test_fiche_de_cours_d_une_partie_seule(conn_v2):
    tex = mer.generer_document_mer(conn_v2, "N09", "M01", {"document": "fiche_cours",
                                                            "partie": 3})
    assert tex.count(r"\begin{seqFicheResumeSix}") == 1
    assert r"\seqTitreFicheSix{Mise en route 1 --- Calcul mental --- partie 3}" in tex
    assert r"\begin{seqFicheResumeSix}{Complément décimal à 1}" in tex
    tout = mer.generer_document_mer(conn_v2, "N09", "M01", {"document": "fiche_cours"})
    assert tout.count(r"\clearpage") == 3


def test_test_court_choisi_par_partie_avec_la_partie_en_sous_titre(conn_v2):
    tex = mer.generer_document_mer(conn_v2, "N09", "M01", {"document": "test_court",
                                                            "partie": 4, "sujet": "A"})
    assert r"\seqTitreEvalSix{Test court --- Arrondis}" in tex
    assert "Mise en route 1, partie 4 --- Sujet A" in tex
    assert r"\seqBaremeCompetences{M01-32/{10},Bonus/{1}}" in tex


def test_plan_d_une_partie_et_plan_de_toute_la_sequence(conn_v2):
    p4 = mer.generer_document_mer(conn_v2, "N09", "M01", {"document": "plan", "partie": 4})
    assert "M01-32" in p4 and "M01-02" not in p4
    assert "Mise en route 1 --- Calcul mental --- partie 4" in p4
    tout = mer.generer_document_mer(conn_v2, "N09", "M01", {"document": "plan"})
    assert tout.count(r"\seqPartieSix{Partie ") == 4
    assert r"\seqPartieSix{Partie 1 --- Tables de multiplication}" in tout


def test_route_du_livret_accepte_la_partie_en_query_string(base, tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    c = create_app(base.parent, profil="atelier").test_client()
    r = c.get("/api/v2/livret-sequence/N09/M01/rendu-tex?document=planche&partie=1")
    assert r.status_code == 200 and r.get_data(as_text=True).count(r"\begin{seqBande}") == 2
    r = c.get("/api/v2/livret-sequence/N09/M01/rendu-tex?document=planche&partie=7")
    assert r.status_code == 400


# ── 6. Validation par partie (MR6 révisé) et route /mer ─────────────────────

def test_validation_par_partie_fiche_manquante_et_partie_sans_test(conn_v2):
    c = conn_v2
    fid = mer.lire_sequence_mer(c, "N09", "M01")["parties"][1]["fiche"]["id"]
    c.execute("DELETE FROM objectif_fiches WHERE fiche_id=?", (fid,))
    c.execute("DELETE FROM fiches_resume WHERE id=?", (fid,))
    t3 = [t for t in mer.tests_courts(c, "N09", "M01") if t["partie"] == 3][0]
    c.execute("DELETE FROM evaluation_objectifs WHERE evaluation_id=?", (t3["id"],))
    c.execute("DELETE FROM evaluation_exercices WHERE evaluation_id=?", (t3["id"],))
    c.execute("DELETE FROM evaluations WHERE id=?", (t3["id"],))
    v = mer.valider_sequence_mer(c, "N09", "M01")
    assert not v["valide"]
    assert v["parties"][2]["erreurs"] == ["partie 2 : pas de fiche de cours"]
    assert "partie 3 : aucun test court" in v["parties"][3]["avertissements"]
    assert v["parties"][1]["erreurs"] == []


def test_ancienne_fiche_de_sequence_signalee_par_la_validation(conn_v2):
    from services import fiches_resume as svc
    svc.creer_fiche(conn_v2, niveau="N09", sequence="M01", titre="Vieille fiche",
                    sections=[{"titre": "A", "items": ["x"]}])
    v = mer.valider_sequence_mer(conn_v2, "N09", "M01")
    assert any("« Vieille fiche » attachée à aucune partie" in a for a in v["avertissements"])


def test_route_mer_donne_parties_et_controle_pour_l_atelier(base, tmp_path):
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    c = create_app(base.parent, profil="atelier").test_client()
    r = c.get("/api/v2/livret-sequence/N09/M01/mer")
    assert r.status_code == 200
    d = r.get_json()
    assert [p["titre"] for p in d["parties"]] == [
        "Partie 1 --- Tables de multiplication", "Partie 2 --- Compléments entiers",
        "Partie 3 --- Complément décimal à 1", "Partie 4 --- Arrondis"]
    assert d["parties"][0]["objectifs"] == ["M01-02"] and d["parties"][0]["exercices"] == 2
    assert d["validation"]["valide"] is True
    assert c.get("/api/v2/livret-sequence/N09/S01/mer").status_code == 400
    assert c.get("/api/v2/livret-sequence/N09/M02/mer").status_code == 404


def test_route_mer_est_une_route_de_l_atelier_absente_du_profil_classe(base, tmp_path):
    c = create_app(base.parent, profil="classe").test_client()
    assert c.get("/api/v2/livret-sequence/N09/M01/mer").status_code == 404


def test_titre_de_partie_sans_libelle_reprend_l_objectif_unique():
    p = {"numero": 2, "libelle": "", "objectifs": [{"nom": "Convertir des aires"}]}
    assert mer.titre_partie(p) == "Partie 2 --- Convertir des aires"
    assert mer.titre_partie({"numero": 3, "libelle": "", "objectifs": [{}, {}]}) == "Partie 3"


def test_exercice_de_test_court_a_environnement_ouvert_hors_de_lui_signale(base, tmp_path):
    """Cas réel (lot M06 du 22 octobre) : deux exercices côte à côte dans des
    minipage ouvertes avant le premier \\seqExoEval ; le rendu découpe le
    sujet par exercice : « Extra \\endgroup » à la compilation."""
    lot = _lot()
    for ev in lot["evaluations"][:2]:
        ev["latex"] = (r"\begin{minipage}{0.5\linewidth}" + ev["latex"].replace(
            r"\seqExoEval{Bonus", r"\end{minipage}\hfill\begin{minipage}{0.4\linewidth}"
            r"\seqExoEval{Bonus") + r"\end{minipage}")
    r = _essai(base, _ecrire_lot(tmp_path / "l", lot))
    txt = [a for a in r.anomalies if "hors de l'exercice" in a]
    assert len(txt) == 4 and "environnement(s) minipage" in txt[0]     # 2 exercices × 2 sujets
    assert imp_mer.exercices_desequilibres(imp, _lot()["evaluations"][0]["latex"]) == []


# ── 7. Format d'un exercice sur la planche (F1), bandeau (P5), bonus ───────

def test_format_lu_dans_le_lot_sinon_deduit_des_notes_sinon_quart():
    assert mer.format_depuis_lot({"format": "demi"}) == ("demi", "lot")
    assert mer.format_depuis_lot({"format": "A5"}) == ("quart", "invalide")
    assert mer.format_depuis_lot({"notes": "Exercice à figure : demi-A4."}) == ("demi", "notes")
    assert mer.format_depuis_lot({"notes": "Sans figure : quart d'A4."}) == ("quart", "défaut")
    assert mer.format_depuis_lot({}) == ("quart", "défaut")


def test_planche_met_les_demi_a4_a_deux_par_feuille_sans_melanger_les_formats(base, tmp_path):
    """Lot M04 : quarts d'A4 et demi-A4 à figure mélangés ; une feuille ne
    porte qu'un format (découpe au massicot)."""
    lot = _lot()
    lot["exercices_seance"][1]["format"] = "demi"
    lot["exercices_seance"][6]["notes"] = "Exercice à figure : demi-A4."
    _appliquer(base, _ecrire_lot(tmp_path / "l", lot))
    c = _conn(base)
    assert [r[0] for r in c.execute("SELECT num FROM exercices WHERE sequence='M01' AND "
                                    "format_planche='demi' ORDER BY num")] == [2, 7]
    tex = mer.generer_document_mer(c, "N09", "M01", {"document": "planche", "par_page": 4})
    q, d = tex.index(r"\begin{seqPlancheFiches}{4}"), tex.index(r"\begin{seqPlancheFiches}{2}")
    assert q < d and tex[q:d].count(r"\begin{seqBande}") == 6
    assert tex[d:].count(r"\begin{seqBande}") == 2 and "séance 2 ---" in tex[d:]
    p1 = mer.generer_document_mer(c, "N09", "M01", {"document": "planche", "partie": 2})
    assert r"\begin{seqPlancheFiches}{2}" not in p1


def test_bandeau_mise_en_route_hors_m01_car_calcul_mental_est_le_titre_de_m01():
    assert mer.titre_bandeau("M01") is None
    assert mer.titre_bandeau("M04") == "MISE EN ROUTE"
    s = {"code": "M04", "nom": "Calcul de grandeurs", "parties": [],
         "exercices": [{"code": "MR01", "seance": 1, "enonce": "x", "objectif": "M04-02"}]}
    L = mer.corps_planche(s, 4, "eleve")
    assert r"\seqDefinirTitreCM{MISE EN ROUTE}" in L
    s["code"] = "M01"
    assert not any("seqDefinirTitreCM" in x for x in mer.corps_planche(s, 4, "eleve"))


def test_test_court_dont_le_bareme_hors_bonus_n_est_pas_sur_10_signale(base, tmp_path):
    lot = _lot()
    for ev in lot["evaluations"][:2]:
        ev["bareme"] = [["M01-02", 9], ["Bonus", 2]]
    r = _essai(base, _ecrire_lot(tmp_path / "l", lot))
    assert any("barème 9 points hors bonus" in a for a in r.anomalies)
    # v0.53.2 (décision du 25 octobre 2026) : bonus de 1 point ; un bonus de 2
    # est désormais une anomalie à corriger dans le lot (avant : information).
    assert any("bonus de 2 point(s)" in a and "à corriger dans le lot" in a for a in r.anomalies)
    assert not any("bonus de" in i for i in r.infos)


def test_module_v0_10_fournit_les_macros_des_lots_car_macros_locales_ne_sont_pas_importees():
    from services import style6e
    appli = Path(__file__).resolve().parent.parent
    dtx = (appli / "paquet" / "seqenseigne-style6e.dtx").read_text(encoding="utf-8")
    sty = (appli / "paquet" / "seqenseigne-style6e.sty").read_text(encoding="utf-8")
    assert "v0.11 seqenseigne" in dtx and "v0.11 seqenseigne" in sty   # v0.53.3 : v0.11 (tableau de conversion)
    for m in ("seqDefinirTitreCM", "seqLocItemGeo"):
        assert m in style6e.MACROS
        assert "\\DescribeMacro{\\" + m + "}" in dtx
        assert re.search(r"\\changes\{v0\.10\}\{[^}]*\}\{\\cs\{" + m + r"\}", dtx)
        assert "\\NewDocumentCommand{\\" + m + "}" in sty
    # Argument long (\providecommand du lot M05) : un item peut contenir \par.
    assert "\\NewDocumentCommand{\\seqLocItemGeo}{+m}" in sty
    assert imp_mer.macros_definies(r"\providecommand{\seqLocItemGeo}[1]{x}") == ["seqLocItemGeo"]


def test_ligne_de_reference_sans_marqueur_ne_colle_pas_le_code_a_hfill():
    """Lots M04, M05 : exercice sans calculatrice précisée → « \\hfillMR07 »,
    macro inconnue, planche non compilée."""
    s = {"code": "M05", "nom": "Géométrie", "parties": []}
    ligne = mer._ligne_reference(s, {"code": "MR07", "seance": 7, "objectif": "M05-12",
                                     "calculatrice": "", "ordinateur": ""})
    assert r"\hfill{}MR07" in ligne and r"\hfillMR" not in ligne


def test_test_court_au_titre_d_une_autre_sequence_non_importe_car_l_import_ne_serait_plus_idempotent(
        base, tmp_path):
    """Cas réel (assemblage du 22 octobre) : « Test court --- Aires » en M03 et
    en M04 ; une évaluation est retrouvée par son titre : chaque import
    réécrivait celle de l'autre séquence."""
    _appliquer(base, _ecrire_lot(tmp_path / "l", _lot()))
    autre = copy.deepcopy(_lot())
    autre["sequence"] = "M07"
    for o, code in zip(autre["objectifs"][:3], ("M07-02", "M07-12", "M07-22")):
        o["code"] = code
    autre["objectifs"] = autre["objectifs"][:3]
    rep = {"M01-02": "M07-02", "M01-12": "M07-12", "M01-22": "M07-22"}
    autre["exercices_seance"] = [dict(e, objectif=rep[e["objectif"]])
                                 for e in autre["exercices_seance"] if e["objectif"] in rep]
    autre["parties"] = autre["parties"][:3]
    autre["evaluations"] = [dict(e, bareme=[[rep[e["bareme"][0][0]], 10], ["Bonus", 1]],
                                 latex=e["latex"].replace(e["bareme"][0][0], rep[e["bareme"][0][0]]))
                            for e in autre["evaluations"] if e["bareme"][0][0] in rep]
    autre["evaluations_retirees"] = ["Test court --- Arrondis"]
    lots = _ecrire_lot(tmp_path / "l2", autre)
    r = _essai(base, lots)
    assert any("« Test court --- Tables de multiplication » non importé : ce titre est celui "
               "d'une évaluation de M01" in a for a in r.anomalies)
    assert any("« Test court --- Arrondis » : c'est une évaluation de M01, gardée" in a
               for a in r.anomalies)
    _appliquer(base, lots)
    une = _dump(base)
    _appliquer(base, lots)
    assert _dump(base) == une
    c = _conn(base)
    assert [t["titre"] for t in mer.tests_courts(c, "N09", "M01")][-1] == "Test court --- Arrondis"
