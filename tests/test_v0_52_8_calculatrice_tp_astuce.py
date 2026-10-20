"""tests/test_v0_52_8_calculatrice_tp_astuce.py — v0.52.8

Décisions de Laurent du 20 octobre 2026 (doc/redemarrage_v0_52_8.md).
Chaque test nomme la décision qu'il protège :

- C1 la mention « calculatrice » du sujet d'une évaluation 6e suit le
  marquage de ses exercices EV (un « autorisée » suffit ; sinon interdite),
  sauf réglage de l'évaluation ; l'import écrit le réglage depuis le lot ;
- C2 l'option du document « Évaluations » passe à « selon l'évaluation »
  (nouveau défaut ; ancien défaut converti une seule fois, référentiel en
  cours seulement) ;
- C3 un réglage contraire aux exercices est signalé dans l'atelier, jamais
  écrasé par lui ;
- T1 les travaux personnels (TP) sortent de « Matériel à prévoir » et des
  données du tableau de bord, mais gardent leur marqueur ;
- A1 astuce `\\seqAstuceSix` du module v0.8, visible élève et corrigé, sans
  marquer l'exercice « ordinateur » ; I2 macro `\\seq…Six` inconnue signalée ;
- O1 critères d'un objectif existant mis à jour et signalés dès l'essai ;
- B2 bonus : hors total, plafonné au total ; la mention de la règle dans le
  titre ne change pas le découpage.
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
from services import marqueurs_exercices as mq  # noqa: E402
from tests.test_v0_52_0_import_lot6e import (  # noqa: E402,F401
    _conn, _dump, _lot_s01, base, imp)
from tests.test_v0_52_2_documents_6e import app_6e  # noqa: E402,F401
from tests.test_v0_52_6_retrait_evaluations import _evaluation  # noqa: E402

APPLI = Path(__file__).resolve().parent.parent
TITRE_EV = "Évaluation --- Nombres"
EXOS_EV = [("Valeur", 10, "S01-02", "Énoncé V."), ("Rang", 10, "S01-02", "Énoncé R.")]
ASTUCE = (r"\seqAstuceSix{Pour mieux comprendre ce que fait le programme, tu peux le "
          r"construire dans Scratch et le tester.}")


def _tex_e6(app, **opts):
    from services.render_evaluation import generer_tex_evaluation
    with app.json_store._conn() as c:
        return generer_tex_evaluation(c, "E6", gabarit="sixieme", options=opts)


def _sous_titre(tex: str) -> str:
    return re.search(r"\\seqTitreEvalSix\{[^}]*\}\{([^}]*)\}", tex).group(1)


# ── C1 : la calculatrice du sujet suit le marquage ───────────────────────────

def test_c1_regle_un_exercice_autorise_suffit_sinon_interdite_comme_avant():
    r = mq.calculatrice_selon_exercices
    assert r([]) == "interdite"                                   # rien de marqué
    assert r([{"calculatrice": ""}, {"calculatrice": "interdite"}]) == "interdite"
    assert r([{"calculatrice": "interdite"}, {"calculatrice": "autorisee"}]) == "autorisee"


def test_c1_sujet_sans_marquage_reste_calculatrice_interdite(app_6e):
    assert _sous_titre(_tex_e6(app_6e)).endswith("calculatrice interdite")


def test_c1_sujet_d_une_evaluation_marquee_autorisee_sort_calculatrice_autorisee(app_6e):
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE exercices SET calculatrice='autorisee' WHERE id IN ('ev1','ev2')")
        c.commit()
    assert _sous_titre(_tex_e6(app_6e)) == "Séquence 1 --- Sujet A --- calculatrice autorisée"
    assert _sous_titre(_tex_e6(app_6e, sujet="B")).endswith("calculatrice autorisée")
    # Une valeur explicite de l'option (rendu, document) s'impose.
    assert _sous_titre(_tex_e6(app_6e, calculatrice="interdite")).endswith(
        "calculatrice interdite")
    # La route de l'atelier, sans option, suit le marquage.
    tex = app_6e.test_client().get("/api/evaluations/E6/rendu-tex").get_data(as_text=True)
    assert "calculatrice autorisée" in _sous_titre(tex)


def test_c1_seuls_les_exercices_ev_comptent(app_6e):
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE exercices SET serie_code='F', calculatrice='autorisee' WHERE id='ev1'")
        assert mq.calculatrice_evaluation(c, "E6")["selon_exercices"] == "interdite"


def test_c1_reglage_de_l_evaluation_prime_sur_les_exercices(app_6e):
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE evaluations SET calculatrice='autorisee' WHERE id='E6'")
        c.commit()
    assert _sous_titre(_tex_e6(app_6e)).endswith("calculatrice autorisée")
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE evaluations SET calculatrice='non_precisee' WHERE id='E6'")
        c.commit()
    assert "calculatrice" not in _sous_titre(_tex_e6(app_6e))


# ── C3 : réglage à la main contraire aux exercices ───────────────────────────

def test_c3_reglage_contraire_aux_exercices_signale_sans_etre_ecrase(app_6e):
    cl = app_6e.test_client()
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE exercices SET calculatrice='autorisee' WHERE id='ev1'")
        c.commit()
    ev = cl.get("/api/evaluations/E6").get_json()["evaluation"]
    assert (ev["calculatrice"], ev["calculatrice_exercices"]) == ("", "autorisee")
    assert ev["calculatrice_avertissement"] == ""
    r = cl.patch("/api/evaluations/E6", json={"calculatrice": "interdite"})
    assert r.status_code == 200
    ev = r.get_json()["evaluation"]
    assert ev["calculatrice"] == "interdite"                     # pas écrasé
    assert "à la main" in ev["calculatrice_avertissement"]
    assert cl.get("/api/evaluations/E6").get_json()["evaluation"]["calculatrice"] == "interdite"
    assert _sous_titre(_tex_e6(app_6e)).endswith("calculatrice interdite")


def test_c3_pas_d_avertissement_quand_aucun_exercice_n_est_marque(app_6e):
    """Sans marquage, un réglage ne contredit aucun exercice."""
    cl = app_6e.test_client()
    ev = cl.patch("/api/evaluations/E6", json={"calculatrice": "autorisee"}).get_json()
    assert ev["evaluation"]["calculatrice_avertissement"] == ""


def test_c3_valeur_inconnue_refusee_par_la_route(app_6e):
    r = app_6e.test_client().patch("/api/evaluations/E6", json={"calculatrice": "oui"})
    assert r.status_code == 400 and r.get_json()["code"] == "calculatrice_invalide"


def test_c3_interface_liste_calculatrice_et_zone_d_avertissement():
    html = (APPLI / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="atl-eval-calculatrice"' in html and 'id="atl-eval-calculatrice-avert"' in html
    assert '<option value="">selon les exercices</option>' in html


# ── C2 : migration et option du document ─────────────────────────────────────

def _base_c2():
    c = sqlite3.connect(":memory:")
    c.executescript("""
        CREATE TABLE evaluations (id TEXT PRIMARY KEY, titre TEXT);
        CREATE TABLE referentiel_niveaux (id TEXT PRIMARY KEY, etat TEXT);
        CREATE TABLE referentiel_documents (id TEXT PRIMARY KEY, referentiel_id TEXT,
                                            type_document TEXT, options TEXT);
        INSERT INTO evaluations VALUES ('e1', 'Probabilité');
        INSERT INTO referentiel_niveaux VALUES ('R1', 'en_cours'), ('R2', 'verrouille');
        INSERT INTO referentiel_documents VALUES
          ('d1', 'R1', 'evaluation_6e', '{"actif": true, "calculatrice": "interdite"}'),
          ('d2', 'R2', 'evaluation_6e', '{"actif": true, "calculatrice": "interdite"}'),
          ('d3', 'R1', 'evaluation_6e', '{"calculatrice": "autorisee"}');
    """)
    return c


def _opt(c, d):
    return json.loads(c.execute("SELECT options FROM referentiel_documents WHERE id=?",
                                (d,)).fetchone()[0])["calculatrice"]


def test_c2_migration_idempotente_ancien_defaut_converti_une_seule_fois():
    c = _base_c2()
    assert mq.migrer_evaluations(c) is True
    assert c.execute("SELECT calculatrice FROM evaluations").fetchone()[0] == ""
    assert _opt(c, "d1") == "selon_evaluation"          # ancien défaut, référentiel en cours
    assert _opt(c, "d2") == "interdite"                 # référentiel verrouillé : intact
    assert _opt(c, "d3") == "autorisee"                 # choix explicite : intact
    # Choix « interdite » fait ensuite par l'enseignant : jamais reconverti.
    c.execute("""UPDATE referentiel_documents SET options='{"calculatrice": "interdite"}'
                 WHERE id='d1'""")
    assert mq.migrer_evaluations(c) is False
    mq.migrer(c)
    assert _opt(c, "d1") == "interdite"


def test_c2_catalogue_defaut_selon_l_evaluation():
    from services import gabarits_documents as gd
    t = gd.type_document("evaluation_6e")
    assert t.options["calculatrice"] == "selon_evaluation"
    assert gd.CALCULATRICE_6E[0] == "selon_evaluation"


def test_c2_base_de_l_appli_migree_au_demarrage(app_6e):
    with app_6e.json_store._conn() as c:
        assert mq.colonne_evaluation_presente(c)


# ── C1 : import ──────────────────────────────────────────────────────────────

def _lot_ev(tmp_path, nom, calculatrice=None):
    lots = _lot_s01(tmp_path / nom)
    f = lots / "S01" / "S01.json"
    lot = json.loads(f.read_text(encoding="utf-8"))
    ev = _evaluation(TITRE_EV, EXOS_EV)
    if calculatrice is not None:
        ev[0]["calculatrice"] = calculatrice
    lot["evaluations"] = ev
    f.write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")
    return lots


def _calc_ev(db):
    c = _conn(db)
    r = c.execute("SELECT calculatrice FROM evaluations WHERE niveau='N09' AND titre=?",
                  (TITRE_EV,)).fetchone()
    c.close()
    return r[0]


def _appliquer(db, lots):
    assert imp.main(["--db", str(db), "--lots", str(lots), "--apply", "--yes"]) == 0


def test_c1_import_ecrit_la_calculatrice_de_l_entree_d_evaluation_et_reste_idempotent(base, tmp_path):
    lots = _lot_ev(tmp_path, "a", "autorisee")
    _appliquer(base, lots)
    assert _calc_ev(base) == "autorisee"
    etat = _dump(base, ("evaluations", "exercices"))
    _appliquer(base, lots)
    assert _dump(base, ("evaluations", "exercices")) == etat
    # Clé retirée : le lot fait foi, le sujet suit de nouveau ses exercices.
    _appliquer(base, _lot_ev(tmp_path, "b"))
    assert _calc_ev(base) == ""


def test_c1_import_ne_touche_pas_une_evaluation_validee(base, tmp_path):
    _appliquer(base, _lot_ev(tmp_path, "a"))
    c = _conn(base)
    c.execute("UPDATE evaluations SET etat_code='valide' WHERE niveau='N09' AND titre=?",
              (TITRE_EV,))
    c.commit()
    c.close()
    _appliquer(base, _lot_ev(tmp_path, "b", "autorisee"))
    assert _calc_ev(base) == ""


def test_c1_import_ajoute_la_colonne_d_une_base_v0_52_7(base, tmp_path):
    c = _conn(base)
    c.execute("ALTER TABLE evaluations DROP COLUMN calculatrice")
    c.commit()
    c.close()
    rapport = imp.essai_a_blanc(base, imp.charger_lots(_lot_ev(tmp_path, "a", "autorisee")),
                                imp.charger_referentiel(), base.parent / "images").texte()
    assert "colonne calculatrice des évaluations (v0.52.8)" in rapport
    assert "calculatrice autorisée" in rapport                   # ligne de l'évaluation
    assert "régler l'option" not in rapport                      # ancienne information
    c = _conn(base)
    assert not mq.colonne_evaluation_presente(c)                 # essai à blanc : rien écrit
    c.close()
    _appliquer(base, _lot_ev(tmp_path, "b", "autorisee"))
    assert _calc_ev(base) == "autorisee"


# ── T1 : travaux personnels hors « Matériel à prévoir » ──────────────────────

def test_t1_plan_6e_tp_marque_hors_encadre_mais_garde_sa_mention(app_6e):
    from services.plan_travail_6e import generer_plan_travail_6e
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE exercices SET ordinateur='scratch' WHERE id='tp1'")
        tex = generer_plan_travail_6e(c, "N09", "S01")
        assert "Matériel à prévoir" not in tex
        assert r"{\small (ordinateur~: Scratch)}" in tex               # ligne du TP
        c.execute("UPDATE exercices SET ordinateur='tableur' WHERE id='ac2'")
        tex = generer_plan_travail_6e(c, "N09", "S01")
    encadre = tex.split("Matériel à prévoir")[1].split(r"\end{tcolorbox}")[0]
    assert "Tableur" in encadre and "Scratch" not in encadre
    assert "travail personnel" not in encadre.lower()


def test_t1_hors_materiel_seulement_pour_les_tp():
    assert mq.hors_materiel("TP") and mq.hors_materiel("", "TP03")
    for s in ("F", "A", "E", "AE", "AC", "AT", "EV", "R", "EA"):
        assert not mq.hors_materiel(s, f"{s}01")


def test_t1_plan_du_cycle_4_ne_liste_aucun_tp_donc_rien_a_exclure():
    src = (APPLI / "services" / "livret_plans_de_travail.py").read_text(encoding="utf-8")
    assert "_noter_marques" in src and "'TP'" not in src and '"TP"' not in src


def _referentiel(c):
    c.execute("INSERT INTO referentiel_sequences (referentiel_id, code, numero, nom) "
              "VALUES ('R09', 'S01', 1, 'Nombres')")
    c.execute("INSERT INTO referentiel_parties (referentiel_id, seq_code, numero) "
              "VALUES ('R09', 'S01', 1)")


def test_t1_publication_et_tableau_de_bord_sans_les_tp(app_6e, tmp_path):
    from services import format_referentiel as fmt
    from services import import_publication as ip
    with app_6e.json_store._conn() as c:
        _referentiel(c)
        c.execute("UPDATE exercices SET ordinateur='geogebra' WHERE id='tp1'")
        seul_tp = fmt.construire(c, "R09")
        c.execute("UPDATE exercices SET ordinateur='tableur' WHERE id='ac2'")
        doc = fmt.construire(c, "R09")
    # Un TP seul marqué : rien à publier (format 1.2, comme sans marqueur).
    assert all("materiel" not in p for s in seul_tp["sequences"] for p in s["parties"])
    materiel = [m for s in doc["sequences"] for p in s["parties"] for m in p.get("materiel", [])]
    assert materiel and all(m["serie"] != "TP" for m in materiel)
    # Publication de la v0.52.7 qui contenait le TP : pas stocké côté classe.
    p0 = doc["sequences"][0]["parties"][0]
    p0.setdefault("materiel", []).append(
        {"objectif": "02", "serie": "TP", "exercice": "TP01", "sequence": "S01",
         "titre": "Travail personnel n°1", "ordinateur": "geogebra", "calculatrice": ""})
    d = tmp_path / "classe"
    d.mkdir()
    classe = create_app(data_dir=d, profil="classe")
    with classe.json_store._conn() as c:
        ip._appliquer(c, tmp_path, "R09", doc, None, {}, "2026-10-20")
        stockes = [dict(r) for r in c.execute("SELECT * FROM referentiel_materiel_publie")]
        assert stockes and all(r["serie"] != "TP" for r in stockes)
        # Lignes TP déjà stockées par la v0.52.7 : filtrées à la lecture.
        c.execute("INSERT INTO referentiel_materiel_publie (referentiel_id, seq_code, "
                  "partie_numero, objectif_code, serie, exercice, exercice_seq, titre, "
                  "ordinateur, calculatrice, ordre) VALUES ('R09','S01',1,'02','TP','TP01',"
                  "'S01','TP','geogebra','',99)")
        lus = ip.materiel_publie(c, "R09")
    assert lus and all(r["exercice"] != "TP01" for r in lus)


# ── A1 : astuce ──────────────────────────────────────────────────────────────

def test_a1_module_v0_8_documente_l_astuce():
    from services import style6e
    dtx = (APPLI / "paquet" / "seqenseigne-style6e.dtx").read_text(encoding="utf-8")
    sty = (APPLI / "paquet" / "seqenseigne-style6e.sty").read_text(encoding="utf-8")
    assert "v0.8 seqenseigne" in dtx and "v0.8 seqenseigne" in sty
    for m in ("seqAstuceSix", "seqPictoAstuceSix"):
        assert m in style6e.MACROS
        assert rf"\DescribeMacro{{\{m}}}" in dtx
        assert re.search(r"\\changes\{v0\.8\}\{[^}]*\}\{\\cs\{" + m + r"\}", dtx), m
        assert re.search(r"\\newcommand\{\\" + m + r"\}", sty), m


def test_a1_astuce_sans_dependance_a_la_version_donc_visible_eleve_et_corrige():
    sty = (APPLI / "paquet" / "seqenseigne-style6e.sty").read_text(encoding="utf-8")
    debut = sty.index(r"\newcommand{\seqAstuceSix}")
    corps = sty[debut:sty.index("\n\\", debut + 30)]
    assert "Corrige" not in corps and "seq@corr" not in corps and r"\small" in corps
    assert "tcolorbox" not in corps                                   # sans cadre lourd


def test_a1_livret_eleve_et_corrige_portent_l_astuce_et_chargent_le_module(app_6e):
    from services import livret_sequence_6e as l6
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE exercices SET enonce = enonce || ? WHERE id='f1'", ("\n" + ASTUCE,))
        for version in ("eleve", "corrigee"):
            tex = l6.generer_livret_sequence_6e(c, "N09", "S01", {"version": version})
            assert ASTUCE in tex and r"\usepackage{seqenseigne-style6e}" in tex, version


def test_a1_import_accepte_l_astuce_sans_marquer_l_exercice_ordinateur(base, tmp_path):
    lots = _lot_s01(tmp_path / "lots")
    f = lots / "S01" / "S01.json"
    lot = json.loads(f.read_text(encoding="utf-8"))
    lot["objectifs"][0]["exercices"][1]["enonce"] += "\n" + ASTUCE
    f.write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")
    r = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                          base.parent / "images")
    assert not any("macros absentes" in a or "seqAstuceSix" in a for a in r.anomalies)
    assert any(r"1 astuce(s) \seqAstuceSix" in i for i in r.infos)
    _appliquer(base, lots)
    c = _conn(base)
    row = c.execute("SELECT enonce, ordinateur FROM exercices WHERE niveau='N09' AND "
                    "sequence='S01' AND serie_code='F' AND num=2").fetchone()
    assert ASTUCE in row["enonce"] and row["ordinateur"] == ""


def test_i2_macro_six_absente_du_module_signalee(base, tmp_path):
    lots = _lot_s01(tmp_path / "lots")
    f = lots / "S01" / "S01.json"
    lot = json.loads(f.read_text(encoding="utf-8"))
    lot["objectifs"][0]["exercices"][1]["enonce"] += r" \seqAstuce{faute de frappe} \seqConseilSix{x}"
    f.write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")
    r = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                          base.parent / "images")
    assert any("seqConseilSix" in a for a in r.anomalies)


# ── O1 : critères d'un objectif existant ─────────────────────────────────────

def test_o1_criteres_s05_12_du_20_octobre_dans_objectifs_6e():
    ref = imp.charger_referentiel()
    o = next(o for p in ref["parties"]["S05"] for o in p["objectifs"] if o["code"] == "12")
    assert o["critere_F"] == ("Construit la médiatrice d'un segment, à la règle graduée et à "
                              "l'équerre ou au compas.")
    assert o["critere_A"].startswith("Construit la médiatrice par les deux méthodes")


def test_o1_criteres_d_un_objectif_existant_mis_a_jour_et_signales_des_l_essai(base, tmp_path):
    lots = _lot_s01(tmp_path / "lots")
    _appliquer(base, lots)
    c = _conn(base)
    oid = c.execute("SELECT o.id FROM objectifs o JOIN sequence_parties p ON p.id=o.partie_id "
                    "JOIN sequences_par_niveau s ON s.id=p.sequence_par_niveau_id "
                    "WHERE s.niveau='N09' AND s.sequence_code='S01' AND o.code='02'"
                    ).fetchone()[0]
    c.execute("UPDATE objectifs SET critere_A='ancien critère' WHERE id=?", (oid,))
    c.commit()
    c.close()
    r = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                          base.parent / "images")
    assert "S01-02 : objectif mis à jour d'après objectifs_6e.json (critère A)" in r.infos
    _appliquer(base, lots)
    c = _conn(base)
    assert c.execute("SELECT critere_A FROM objectifs WHERE id=?", (oid,)).fetchone()[0] != \
        "ancien critère"
    c.close()
    r = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                          base.parent / "images")
    assert not any("objectif mis à jour" in i for i in r.infos)          # idempotent


def test_o1_sequence_validee_jamais_modifiee(base, tmp_path):
    lots = _lot_s01(tmp_path / "lots")
    _appliquer(base, lots)
    c = _conn(base)
    c.execute("UPDATE objectifs SET critere_A='critère de l''enseignant' WHERE id IN ("
              "SELECT o.id FROM objectifs o JOIN sequence_parties p ON p.id=o.partie_id "
              "JOIN sequences_par_niveau s ON s.id=p.sequence_par_niveau_id "
              "WHERE s.niveau='N09' AND s.sequence_code='S01')")
    c.execute("UPDATE sequences_par_niveau SET etat_code='valide' WHERE niveau='N09' AND "
              "sequence_code='S01'")
    c.commit()
    c.close()
    _appliquer(base, lots)
    c = _conn(base)
    assert {r[0] for r in c.execute(
        "SELECT o.critere_A FROM objectifs o JOIN sequence_parties p ON p.id=o.partie_id "
        "JOIN sequences_par_niveau s ON s.id=p.sequence_par_niveau_id "
        "WHERE s.niveau='N09' AND s.sequence_code='S01'")} == {"critère de l'enseignant"}


# ── B2 : bonus ───────────────────────────────────────────────────────────────

def test_b2_titre_avec_la_regle_du_bonus_toujours_reconnu_comme_bonus():
    assert imp._est_bonus({"titre": "Bonus (compté seulement si toutes les autres questions "
                                    "sont traitées) : Qui suis-je ?"})


def test_b2_bonus_hors_total_et_plafonne_au_total_du_bareme(app_6e):
    """L'appli ne calcule aucune note : le sujet affiche le barème (bonus
    hors total) et la règle « dans la limite du total »."""
    tex = _tex_e6(app_6e)
    assert r"\seqBaremeCompetences{S01-02/{5},S01-03/{3},Bonus/{2}}{8}" in tex
    assert "Le bonus s'ajoute dans la limite de 8." in tex
