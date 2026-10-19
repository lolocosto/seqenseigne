"""tests/test_v0_52_3_retours.py — v0.52.3

Retours de Laurent sur la v0.52.2 (doc/redemarrage_v0_52_3.md) :

  1. une activité d'approche enregistrée dans l'atelier changeait de code
     (AE03 → EA01) et quittait la liste ; outil de réparation (A2) ;
  2. l'onglet « Rendu PDF » du module Évaluations restait figé (route
     d'information de cache ; le JS est testé par vitest) ;
  3. rendu d'atome des exercices de 6e au format de l'équipe (A1, A3, A4) ;
  4. plan de travail de séquence de 6e au format de l'équipe (P1 à P5).

Chaque test nomme la décision qu'il protège.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app  # noqa: E402
from outils import reparer_series_approche as rep  # noqa: E402
from services import atomes  # noqa: E402
from tests.test_v0_52_1_gabarits_documents import peupler_cycle4  # noqa: E402
from tests.test_v0_52_2_documents_6e import SQL_SIXIEME_DOCS  # noqa: E402
from tests.test_v0_52_0_import_lot6e import _lot_s01, base, imp  # noqa: E402,F401


@pytest.fixture
def app_6e(data_dir):
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as c:
        c.executescript(SQL_SIXIEME_DOCS)
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, gabarit_documents) "
                  "VALUES ('R09', 'N09', '2026', 'en_cours', 'sixieme')")
        c.commit()
    return app


@pytest.fixture
def app_c4(data_dir):
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as c:
        peupler_cycle4(c)
        c.commit()
    return app


# ── 1. Activités d'approche ──────────────────────────────────────────────────

def test_approche_a_le_code_AE_de_la_base_et_non_EA_sinon_l_activite_quitte_la_liste():
    assert atomes._SERIE_VERS_CODE["approche"] == "AE"
    liste, ex, err = atomes.creer_exercice([], {"serie": "approche", "niveau": "N09",
                                                "sequence": "S01"})
    assert err is None and (ex["serie_code"], ex["num"]) == ("AE", 1)


def test_enregistrer_une_activite_garde_son_code_et_son_numero_car_l_import_la_retrouve_par_eux(
        app_6e):
    c = app_6e.test_client()
    r = c.patch("/api/exercices/a2", json={"serie": "approche", "corrige": "bidon",
                                           "enonce": "Activité 2"})
    assert r.status_code == 200
    assert (r.get_json()["serie_code"], r.get_json()["num"]) == ("AE", 2)
    liste = c.get("/api/exercices?niveau=N09&sequence=S01").get_json()
    assert [x["code"] for x in liste if x["id"] == "a2"] == ["AE02"]


def test_meme_serie_renvoyee_ne_renumerote_jamais_meme_si_le_code_diverge():
    liste = [{"id": "x", "serie": "approche", "serie_code": "AE", "num": 3, "niveau": "N09",
              "sequence": "S01"}]
    old = dict(atomes._SERIE_VERS_CODE)
    try:
        atomes._SERIE_VERS_CODE["approche"] = "ZZ"          # mapping divergent
        _, ex, _ = atomes.modifier_exercice(liste, "x", {"serie": "approche"})
    finally:
        atomes._SERIE_VERS_CODE.clear()
        atomes._SERIE_VERS_CODE.update(old)
    assert (ex["serie_code"], ex["num"]) == ("AE", 3)


def test_un_vrai_changement_de_serie_renumerote_toujours_dans_la_nouvelle_serie():
    liste = [{"id": "x", "serie": "approche", "serie_code": "AE", "num": 3, "niveau": "N09",
              "sequence": "S01"},
             {"id": "y", "serie": "fondamental", "serie_code": "F", "num": 4, "niveau": "N09",
              "sequence": "S01"}]
    _, ex, _ = atomes.modifier_exercice(liste, "x", {"serie": "fondamental"})
    assert (ex["serie_code"], ex["num"]) == ("F", 5)


def _base_reparation(tmp_path) -> Path:
    db = tmp_path / "seqenseigne.db"
    c = sqlite3.connect(db)
    c.executescript("""
        CREATE TABLE exercices (id TEXT PRIMARY KEY, serie TEXT, niveau TEXT, sequence TEXT,
            num INTEGER, serie_code TEXT, etat_code TEXT, mtime TEXT);
        CREATE TABLE partie_exos_revision_approche (partie_id TEXT, type TEXT,
            exercice_id TEXT, ordre INTEGER, origin_niveau TEXT, origin_seq TEXT,
            origin_serie TEXT, origin_num INTEGER);
        CREATE TABLE objectif_exos (objectif_id TEXT, serie TEXT, exercice_id TEXT,
            ordre INTEGER, origin_num INTEGER, PRIMARY KEY (objectif_id, serie, exercice_id));
        INSERT INTO exercices VALUES
            ('ok1', 'approche', 'N09', 'S01', 1, 'AE', 'en_cours', ''),
            ('abime3', 'approche', 'N09', 'S01', 1, 'EA', 'en_cours', ''),
            ('abime5', 'approche', 'N09', 'S01', 2, 'EA', 'valide', ''),
            ('pris4', 'approche', 'N09', 'S01', 4, 'AE', 'en_cours', ''),
            ('abime4', 'approche', 'N09', 'S01', 3, 'EA', 'en_cours', ''),
            ('nouveau', 'approche', 'N09', 'S01', 4, 'EA', 'en_cours', ''),
            ('sans_code', '', 'N09', 'S01', NULL, '', 'en_cours', ''),
            ('f_relie', 'fondamental', 'N09', 'S01', 1, 'F', 'en_cours', '');
        INSERT INTO partie_exos_revision_approche VALUES
            ('p1', 'EA', 'abime3', 1, 'N09', 'S01', 'AE', 3),
            ('p1', 'EA', 'abime4', 2, 'N09', 'S01', 'AE', 4),
            ('p1', 'EA', 'sans_code', 3, 'N09', 'S01', 'AE', NULL),
            ('p1', 'EA', 'f_relie', 4, 'N09', 'S01', 'F', 1);
        INSERT INTO objectif_exos VALUES ('o1', 'EA', 'abime5', 1, 5);
    """)
    c.commit()
    c.close()
    return db


def test_reparation_rend_le_numero_d_origine_lu_dans_les_liens_sinon_le_prochain_libre(tmp_path):
    db = _base_reparation(tmp_path)
    c = sqlite3.connect(db)
    plan = rep.diagnostiquer(c)
    apres = {r["id"]: r["apres"] for r in plan["reparations"]}
    assert apres["abime3"] == "approche / AE03"            # origin_num de la partie
    assert apres["abime5"] == "approche / AE05"            # origin_num de l'objectif
    assert apres["abime4"] == "approche / AE06"            # AE04 pris : prochain libre
    assert next(r for r in plan["reparations"] if r["id"] == "abime4")["conflit"]
    assert set(apres) == {"abime3", "abime4", "abime5", "nouveau", "sans_code"}
    # Un exercice relié comme activité mais rangé en F est signalé, pas modifié.
    assert any("f_relie" in s for s in plan["signales"])


def test_reparation_essai_a_blanc_n_ecrit_rien_puis_apply_sauvegarde_et_est_idempotent(tmp_path):
    db = _base_reparation(tmp_path)
    avant = db.read_bytes()
    assert rep.main(["--db", str(db)]) == 0
    assert db.read_bytes() == avant
    assert rep.main(["--db", str(db), "--apply", "--yes"]) == 0
    sauvegardes = list((tmp_path / "sauvegardes").glob("avant_reparation_approche_*.db"))
    assert len(sauvegardes) == 1
    d = sqlite3.connect(sauvegardes[0])
    assert d.execute("SELECT COUNT(*) FROM exercices WHERE serie_code = 'EA'").fetchone()[0] == 4
    d.close()
    c = sqlite3.connect(db)
    assert c.execute("SELECT COUNT(*) FROM exercices WHERE serie_code = 'EA'").fetchone()[0] == 0
    assert c.execute("SELECT serie FROM objectif_exos WHERE exercice_id='abime5'").fetchone()[0] == "AE"
    assert c.execute("SELECT niveau, sequence, serie_code, num FROM exercices GROUP BY 1, 2, 3, 4 "
                     "HAVING COUNT(*) > 1").fetchall() == []
    assert rep.diagnostiquer(c)["reparations"] == []


def test_scenario_activite_abimee_par_l_ancienne_interface_reparee_avant_reimport_sans_doublon(
        base, tmp_path):
    """Ordre de déploiement : réparation AVANT le réimport des lots, sinon
    l'import (clé niveau, séquence, code, numéro) crée un doublon."""
    lots = _lot_s01(tmp_path / "lots")
    assert imp.main(["--db", str(base), "--lots", str(lots), "--apply", "--yes"]) == 0
    app = create_app(base.parent, profil="atelier")
    c = sqlite3.connect(base)
    ae3 = c.execute("SELECT id FROM exercices WHERE niveau='N09' AND sequence='S01' AND "
                    "serie_code='AE' AND num=3").fetchone()[0]
    nb_ae = c.execute("SELECT COUNT(*) FROM exercices WHERE serie_code='AE'").fetchone()[0]
    c.close()
    # Ce qu'écrivait l'ancienne interface en enregistrant AE03 (v0.52.2 :
    # mapping 'approche' → 'EA', prochain numéro de cette « série »).
    assert app.test_client().patch(f"/api/exercices/{ae3}", json={
        "serie": "approche", "corrige": "bidon"}).status_code == 200
    c = sqlite3.connect(base)
    c.execute("UPDATE exercices SET serie_code='EA', num=1 WHERE id=?", (ae3,))
    c.commit()
    c.close()
    # Sans réparation, l'import créerait un doublon.
    ref = imp.charger_referentiel()
    rapport = imp.essai_a_blanc(base, imp.charger_lots(lots), ref, base.parent / "images")
    assert "activités AE [créé : 1" in rapport.texte()
    # Réparation, puis réimport.
    assert rep.main(["--db", str(base), "--apply", "--yes"]) == 0
    assert imp.main(["--db", str(base), "--lots", str(lots), "--apply", "--yes"]) == 0
    c = sqlite3.connect(base)
    assert c.execute("SELECT serie_code, num FROM exercices WHERE id=?", (ae3,)).fetchone() == ("AE", 3)
    assert c.execute("SELECT COUNT(*) FROM exercices WHERE serie_code='AE'").fetchone()[0] == nb_ae
    assert c.execute("SELECT niveau, sequence, serie_code, num FROM exercices GROUP BY 1, 2, 3, 4 "
                     "HAVING COUNT(*) > 1").fetchall() == []
    # Le corrigé du lot remplace le corrigé « bidon » (exercice non validé).
    assert c.execute("SELECT corrige FROM exercices WHERE id=?", (ae3,)).fetchone()[0] != "bidon"


# ── 2. Rendu PDF du module Évaluations ───────────────────────────────────────

def test_info_cache_d_une_evaluation_depend_du_sujet_car_l_onglet_doit_suivre_la_selection(
        app_6e):
    from services.compilateur_pdf import chemin_pdf_cache, hash_tex
    c = app_6e.test_client()
    r = c.get("/api/evaluations/E6/rendu-pdf/info?sujet=B&version=eleve")
    assert r.status_code == 200 and r.get_json() == {"cache_valide": False}
    tex_b = c.get("/api/evaluations/E6/rendu-tex?sujet=B&version=eleve").get_data(as_text=True)
    pdf = chemin_pdf_cache(app_6e.json_store.data_dir / "cache_rendus", hash_tex(tex_b))
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF")
    assert c.get("/api/evaluations/E6/rendu-pdf/info?sujet=B&version=eleve").get_json() == \
        {"cache_valide": True}
    assert c.get("/api/evaluations/E6/rendu-pdf/info?sujet=A&version=eleve").get_json() == \
        {"cache_valide": False}
    assert c.get("/api/evaluations/inconnue/rendu-pdf/info").status_code == 404


def test_route_info_evaluation_classee_atelier():
    from services import profils
    assert profils.categorie_blueprint("evaluations") == "atelier"


# ── 3. Rendu d'atome des exercices de 6e ─────────────────────────────────────

def _tex_atome(app, ex_id, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    r = app.test_client().get(f"/api/atomes/exercice/{ex_id}/rendu-tex" + (f"?{q}" if q else ""))
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_data(as_text=True)


def test_atome_tp_rendu_comme_le_document_du_catalogue_et_non_au_format_cycle4(app_6e):
    from services.documents_6e import generer_document_6e
    tex = _tex_atome(app_6e, "tp1", version="corrigee")
    assert r"\seqTitreTravailSix" in tex and r"\seqVersionCorrigee" in tex
    assert r"\seqCreeCompteurs" not in tex                      # marque du rendu cycle 4
    with app_6e.json_store._conn() as c:
        doc = generer_document_6e(c, "tp1", {"version": "corrigee"})
    assert tex.split(r"\begin{document}")[1] == doc.split(r"\begin{document}")[1]
    assert r"\seqVersionCorrigee" not in _tex_atome(app_6e, "tp1")   # A3 : élève par défaut


def test_atome_ev_sujet_b_avec_son_titre_son_bareme_et_sa_competence(app_6e):
    tex = _tex_atome(app_6e, "ev1", sujet="B")
    assert r"\seqExoEval{Valeur des chiffres de 73}{5 pts --- S01-02}" in tex
    assert "Sujet B1" in tex and "Sujet A1" not in tex
    assert "Sujet A1" in _tex_atome(app_6e, "ev1")


def test_atome_f_6e_seqexosix_avec_sa_remediation_et_son_numero_du_livret(app_6e):
    tex = _tex_atome(app_6e, "f1")
    assert r"\setcounter{seqExoSix}{0}" in tex
    assert r"\begin{seqExoSix}[O]" in tex and r"\begin{seqExoSix}[R]" in tex and "Remède F1" in tex
    tex = _tex_atome(app_6e, "a2")                         # activité, 2e du livret
    assert r"\setcounter{seqActiviteSix}{1}" in tex and r"\begin{seqActiviteSix}" in tex


def test_atome_6e_options_invalides_refusees(app_6e):
    r = app_6e.test_client().get("/api/atomes/exercice/tp1/rendu-tex?version=prof")
    assert r.status_code == 400


def test_archive_xnn_garde_le_rendu_du_cycle4(app_6e):
    assert r"\seqCreeCompteurs" in _tex_atome(app_6e, "tpx")


def test_atome_cycle4_meme_tex_qu_avant_avec_ou_sans_options(app_c4):
    from services.latex_rendu_atome import generer_tex_atome, generer_tex_par_type
    with app_c4.json_store._conn() as c:
        for ex_id in ("ex_f1", "ex_ea1"):
            attendu = generer_tex_atome(c, "exercice", ex_id)
            assert generer_tex_par_type(c, "exercice", ex_id) == attendu
            assert generer_tex_par_type(c, "exercice", ex_id,
                                        options={"version": "corrigee", "sujet": "B"}) == attendu


def test_numeros_du_livret_releves_pendant_l_emission_concordent_avec_le_livret(app_6e):
    from services import livret_sequence_6e as l6
    with app_6e.json_store._conn() as c:
        seq = l6.lire_sequence_6e(c, "N09", "S01")
        opts = l6.normaliser_options({})
        N = l6.numeros_livret(seq, opts)
        lignes = l6.corps_livret(seq, opts)
    # Recompte indépendant sur le texte du livret.
    n, vus = 0, {}
    for ligne in lignes:
        if ligne.startswith(r"\begin{seqExoSix}"):
            n += 1
            code = re.search(r"seqSixGrisTexte\}(\w+)\}\]$", ligne).group(1)
            vus.setdefault(("R" if "[R]" in ligne else "") + code, n)
    assert vus == {**{f"{c}": N.exercices[i] for i, c in (("f1", "F01"), ("aa1", "A01"),
                                                          ("e1", "E01"), ("f2", "F02"))},
                   "RF01": N.remediations["f1"]}
    assert N.activites == {"a1": 1, "a2": 2}


# ── 4. Plan de travail 6e ────────────────────────────────────────────────────

def test_ligne_exercices_marques_de_l_equipe():
    from services.plan_travail_6e import ligne_exercices
    assert ligne_exercices([("O", 1), ("O", 2), ("A", 3), ("A", 4), ("R", 5), ("E", 6)]) == \
        r"1 - 2 - ( 3 - 4 ) - [ 5 ] - \{ 6 \}"


def _plan(app, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    r = app.test_client().get("/api/plans-de-travail/N09/S01/tex" + (f"?{q}" if q else ""))
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_data(as_text=True)


def test_plan_de_travail_6e_au_format_de_l_equipe_depuis_l_atelier(app_6e):
    tex = _plan(app_6e)
    # v0.52.4 (T1) : le niveau vient de \seqNiveauCourt (6e pour N09).
    assert r"\color{seqSixVert}" in tex and r"Livret de séquence \seqNiveauCourt" in tex
    assert r"\renewcommand{\seqNiveauCourt}{6e}" in tex
    assert "S01-02" in tex and "S01-03" in tex and "S01-01" not in tex       # L3 : pas de Cours
    assert r"exercices 1 - [ 2 ] - ( 3 ) - \{ 4 \}" in tex                    # P3
    assert "Activité 1 : Un sudoku" in tex and "Activité 2 : Les grands nombres" in tex
    assert r"\underline{à retenir 1}} : La valeur d'un chiffre" in tex
    assert r"\seqVersionComplete" in tex and "dix chiffres" in tex             # fiche entière
    # P4 : TP relié à S01-02 et S01-03 → après S01-03 ; évaluation en synthèse.
    assert tex.index("Travail personnel n°1") > tex.index(r"\seqPlanMot{S01-03}")
    assert "S01-02 /5, S01-03 /3, bonus /2 --- total /8" in tex
    assert "ramassage et correction des travaux personnels n°1" in tex
    # P5 : rien d'inventé.
    assert "livret p" not in tex and "Manuel" not in tex and "pages)" not in tex
    assert "pt_" not in tex


def test_plan_6e_option_fiches_titre_seulement(app_6e):
    tex = _plan(app_6e, fiches="titre")
    assert "dix chiffres" not in tex and r"\seqVersionComplete" not in tex


def test_plan_de_travail_cycle4_toujours_le_plan_historique_et_gabarit_force(
        app_6e, app_c4, monkeypatch):
    """P1 : un niveau du cycle 4 (R1 → cycle4) garde le générateur historique,
    appelé comme avant ; ?gabarit=cycle4 le force aussi pour la 6e."""
    import routes.plans_de_travail as rpt
    appels = []
    monkeypatch.setattr(rpt, "generer_plan_de_travail_sequence",
                        lambda conn, n, s, **kw: appels.append((n, s, sorted(kw))) or "PLAN C4")
    r = app_c4.test_client().get("/api/plans-de-travail/N11/S01/tex")
    assert r.get_data(as_text=True) == "PLAN C4"
    assert appels == [("N11", "S01", ["tblr_libraries", "tikz_libraries"])]
    assert _plan(app_6e, gabarit="cycle4") == "PLAN C4"


def test_plan_6e_numerote_comme_le_livret_publie_par_le_referentiel(app_6e):
    from services import orchestrateur_compilation as orch
    from services.referentiel_documents_compilation import lister_cibles_document
    with app_6e.json_store._conn() as c:
        c.execute("INSERT INTO referentiel_documents (id, referentiel_id, type_document, options) "
                  "VALUES ('d_liv', 'R09', 'livret_sequence_6e', ?), "
                  "('d_plan', 'R09', 'plans_travail_6e', '{\"actif\": true}')",
                  (json.dumps({"actif": True, "remediations": "aucune"}),))
        cibles = lister_cibles_document(c, "d_plan", "R09", "plans_travail_6e")
        assert [x["cible_id"] for x in cibles] == ["N09/S01"]               # pas d'archive X02
        tex = orch.REGISTRE["plans_travail_6e"](c, {**cibles[0], "referentiel_id": "R09"},
                                                {"actif": True}, [], ["booktabs", "varwidth"])
    assert r"exercices 1 - ( 2 ) - \{ 3 \}" in tex                          # sans remédiation
