"""tests/test_v0_60_0_version2_fiches.py — v0.60.0

« Version 2 » du modèle Fiches avec cartes et correctifs d'import
(`doc/redemarrage_v0_60_0.md`, brief `col4/BRIEF_V0600.md`). Chaque test
nomme la décision qu'il protège :

  T1 type d'évaluation : tests courts reconnus par leur titre une seule fois
     (sans toucher mtime : aucun document périmé), ensuite seul l'import ou
     le module écrit le type ;
  T2 durée : 10 min par objectif évalué, 10 min pour un test court ; réglable ;
  T3 (B8) partie sans calculatrice = part de la durée de l'évaluation qui
     revient à ses objectifs (40 + 10 sur 50 min, 20 + 10 sur 30 min) ;
  E6 clé `tests_courts` des lots, un test court par partie (avertissement) ;
  B6 activités de découverte sous l'objectif « Cours » (import et outil de
     migration, séquence validée jamais touchée, 6e exclue) ;
  B7 clé `variables` des exercices (absente : valeur en base gardée) ;
  B9 titre d'exercice échappé dans le livret Fiches ;
  B10 bonus de 1 point : avertissement seulement ;
  P0-P7 ordre des parties saisi, rituels et séances d'évaluation.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from outils import import_lot6e as imp
from outils import migrer_ae_cours as mac
from services import evaluations_v2 as ev2
from services import progression_rituels as pr
from tests.test_v0_52_0_import_lot6e import base as base_v052  # noqa: F401
from tests.test_v0_58_0_migration_themes_codes import _ins
from tests.test_v0_59_0_ref4e_fiches import (  # noqa: F401
    LOT_ESSAI,
    _archiver,
    _importer,
    _table_reduite,
    base,
    base4e,
)


def _conn(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


def _lot(tmp_path, modif=None) -> Path:
    d = tmp_path / "lot4e"
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(LOT_ESSAI, d)
    f = d / "A1" / "A1.json"
    lot = json.loads(f.read_text(encoding="utf-8"))
    if modif:
        modif(lot)
    f.write_text(json.dumps(lot, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def _sujet(bonus=1, pts=(6, 4)):
    return ("\\seqExoEval{Exercice 1}{%g pts --- A1-02}\nQuestion 1.\n"
            "\\seqExoEval{Exercice 2}{%g pts --- A1-03}\nQuestion 2.\n"
            "\\seqExoEval{Bonus}{%g pts --- A1-02}\nQuestion bonus.\n" % (pts[0], pts[1], bonus))


def _paire(titre, bonus=1, pts=(6, 4)):
    return [{"titre": titre, "sujet": s, "latex": _sujet(bonus, pts),
             "bareme": [["A1-02", pts[0]], ["A1-03", pts[1]], ["Bonus", bonus]]}
            for s in ("A", "B")]


@pytest.fixture
def b4(base4e):
    assert _archiver(base4e, "--apply", "--yes") == 0
    return base4e


def _imp(db, lots, capsys):
    capsys.readouterr()
    assert _importer(db, lots, "--apply", "--yes") == 0
    return capsys.readouterr().out


# ── T1 / T2 / T3 ─────────────────────────────────────────────────────────────

def _base_evals(tmp_path):
    db = tmp_path / "ev.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE evaluations (id TEXT PRIMARY KEY, niveau TEXT, numero INT, "
              "titre TEXT, mtime TEXT)")
    c.execute("CREATE TABLE evaluation_objectifs (evaluation_id TEXT, objectif_id TEXT)")
    c.executemany("INSERT INTO evaluations VALUES (?,?,?,?,?)", [
        ("e1", "N11", 1, "Test court --- Translation", "2026-11-01 10:00:00"),
        ("e2", "N11", 2, "  test   COURT --- Pythagore", "2026-11-01 10:00:00"),
        ("e3", "N11", 3, "Évaluation --- Translation", "2026-11-01 10:00:00")])
    c.executemany("INSERT INTO evaluation_objectifs VALUES (?,?)",
                  [("e3", "o1"), ("e3", "o2"), ("e3", "o3")])
    c.commit()
    return c


def test_t1_tests_courts_reconnus_par_leur_titre_une_seule_fois_sans_toucher_mtime(tmp_path):
    c = _base_evals(tmp_path)
    faits = ev2.migrer(c)
    assert "tests courts reconnus : 2" in faits
    types = dict(c.execute("SELECT id, type_evaluation FROM evaluations"))
    assert types == {"e1": "test_court", "e2": "test_court", "e3": "evaluation"}
    # mtime intact : aucun document ne devient « périmé » par la migration.
    assert {r[0] for r in c.execute("SELECT mtime FROM evaluations")} == {"2026-11-01 10:00:00"}
    # Un réglage de l'enseignant n'est jamais repris par une migration suivante.
    c.execute("UPDATE evaluations SET type_evaluation = 'evaluation' WHERE id = 'e2'")
    assert ev2.migrer(c) == []
    assert ev2.type_evaluation(c, "e2") == "evaluation"


def test_t2_duree_dix_minutes_par_objectif_test_court_dix_minutes_reglage_prioritaire(tmp_path):
    c = _base_evals(tmp_path)
    ev2.migrer(c)
    assert ev2.duree_auto(c, "e3") == 30
    assert ev2.duree_auto(c, "e1") == 10
    c.execute("UPDATE evaluations SET duree = 45 WHERE id = 'e3'")
    assert ev2.duree(c, "e3") == 45
    assert ev2.resume(c, "e3") == {"type_evaluation": "evaluation", "duree_auto": 30,
                                   "duree": 45, "duree_retenue": 45}
    with pytest.raises(ev2.DureeInvalide):
        ev2.valider_duree("12,5")
    assert ev2.valider_duree("") is None


def _ex(obj, pts):
    return {"objectif": obj, "points": pts}


def test_t3_b8_partie_sans_calculatrice_part_des_objectifs_et_non_plus_55_minutes():
    f = ev2.duree_partie1_par_objectifs
    # A3 de 4e : 4 objectifs sans calculatrice, 1 avec, 50 min → 40 + 10.
    p1 = [_ex(o, 4) for o in ("A3-02", "A3-03", "A3-05", "A3-06")]
    assert f([p1, [_ex("A3-04", 4)]], 50) == 40
    # A4 « Équations » : 30 min, 2 objectifs sur 3 en partie 1 → 20 + 10
    # (l'ancien calcul donnait 40 min de partie 1 pour 30 min d'évaluation).
    assert f([[_ex("A4-12", 7), _ex("A4-13", 7)], [_ex("A4-14", 6)]], 30) == 20
    # Objectif partagé : au prorata de ses points ; le bonus ne compte pas.
    assert f([[_ex("X-02", 5), _ex("X-03", 2), _ex("", 1)], [_ex("X-03", 8)]], 20) == 10
    # Au moins 10 min, au plus la durée.
    assert f([[_ex("X-02", 1)], [_ex("X-03", 9), _ex("X-04", 9), _ex("X-05", 9)]], 40) == 10
    assert f([[_ex("X-02", 1)], []], 10) == 10


# ── E6, B10 — tests courts et bonus à l'import ───────────────────────────────

def test_e6_cle_tests_courts_type_et_controles_du_bareme_avertissements_seulement(b4, tmp_path,
                                                                                   capsys):
    def modif(lot):
        lot["evaluations"] = _paire("Évaluation --- Produits", bonus=2, pts=(12, 8))
        lot["tests_courts"] = _paire("Contrôle flash --- Produits", bonus=1, pts=(5, 4))
    out = _imp(b4, _lot(tmp_path, modif), capsys)
    c = _conn(b4)
    types = dict(c.execute("SELECT titre, type_evaluation FROM evaluations WHERE niveau='N11'"))
    assert types["Évaluation --- Produits"] == "evaluation"
    assert types["Contrôle flash --- Produits"] == "test_court"      # clé tests_courts
    assert "== Avertissements" in out
    assert "évaluation « Évaluation --- Produits » : bonus de 2 pts (règle : 1 pt)" in out
    assert "test court « Contrôle flash --- Produits » : sur 9 (un test court est sur 10)" in out
    assert "partie 1 : pas de test court" not in out
    # Avertissements : l'import passe quand même (rien de bloquant).
    assert "anomalie" not in out.split("== Avertissements")[1].lower()


def test_e6_titre_test_court_dans_evaluations_et_deux_tests_pour_une_partie(b4, tmp_path, capsys):
    def modif(lot):
        lot["evaluations"] = (_paire("Test court --- Produits", pts=(6, 4))
                              + _paire("Test court --- Quotients", pts=(6, 4)))
    out = _imp(b4, _lot(tmp_path, modif), capsys)
    c = _conn(b4)
    assert {r[0] for r in c.execute("SELECT type_evaluation FROM evaluations WHERE "
                                    "niveau='N11'")} == {"test_court"}
    assert "A1 partie 1 : 2 tests courts (un par partie)" in out


# ── B6 — activités sous « Cours » ────────────────────────────────────────────

AE = {"num": 1, "code": "AE01", "titre": "Découverte", "latex": "Une activité."}


def _ae_lien(c):
    return {r[0] for r in c.execute(
        "SELECT o.code FROM objectif_exos oe JOIN objectifs o ON o.id = oe.objectif_id "
        "JOIN exercices e ON e.id = oe.exercice_id WHERE e.niveau='N11' AND e.sequence='A1' "
        "AND e.serie_code='AE' AND oe.serie='AE'")}


def test_b6_activite_sous_cours_ouvre_la_partie_et_quitte_le_premier_objectif(b4, tmp_path,
                                                                             capsys):
    def ancien(lot):
        lot["objectifs"][0]["activites"] = [dict(AE)]
    _imp(b4, _lot(tmp_path, ancien), capsys)
    c = _conn(b4)
    assert _ae_lien(c) == {"02"}
    mt = c.execute("SELECT mtime FROM exercices WHERE niveau='N11' AND serie_code='AE'"
                   ).fetchone()[0]
    c.execute("UPDATE exercices SET mtime='2000-01-01 00:00:00' WHERE serie_code='AE'")
    c.commit()

    def cours(lot):
        lot["objectifs"].insert(0, {"code": "A1-01", "activites": [dict(AE)]})
    out = _imp(b4, _lot(tmp_path, cours), capsys)
    assert _ae_lien(c) == {"01"}
    assert "objectif inconnu" not in out
    # Contenu inchangé mais mtime rafraîchi : livret et corrigés périmés.
    assert c.execute("SELECT mtime FROM exercices WHERE serie_code='AE'").fetchone()[0] \
        > "2000-01-01 00:00:00" and mt
    from services.livret_sequence_6e import lire_sequence_6e
    st = lire_sequence_6e(c, "N11", "A1")
    p1 = st["parties"][0]
    assert [a["titre"] for a in p1["activites"]] == ["Découverte"]
    assert all(not o["activites"] for o in p1["objectifs"])


def test_b6_cle_cours_avec_partie_et_contenus_refuses_sous_cours(b4, tmp_path, capsys):
    def cours(lot):
        lot["objectifs"].insert(0, {"code": "Cours", "partie": 1, "activites": [dict(AE)],
                                    "exercices": [{"serie": "F", "num": 9, "titre": "x"}]})
    out = _imp(b4, _lot(tmp_path, cours), capsys)
    assert _ae_lien(_conn(b4)) == {"01"}
    assert "A1-01 (Cours) : clé « exercices » ignorée" in out


def test_b6_outil_de_migration_seulement_hors_6e_jamais_sur_sequence_validee(b4, tmp_path,
                                                                             capsys):
    def ancien(lot):
        lot["objectifs"][0]["activites"] = [dict(AE)]
    _imp(b4, _lot(tmp_path, ancien), capsys)
    c = _conn(b4)
    c.execute("UPDATE sequences_par_niveau SET etat_code='valide' WHERE niveau='N11' AND "
              "sequence_code='A1'")
    c.commit()
    assert mac.main(["--db", str(b4), "--niveau", "N11", "--apply", "--yes"]) == 0
    assert _ae_lien(c) == {"02"}                                   # validée : intacte
    assert "séquence validée" in capsys.readouterr().out
    c.execute("UPDATE sequences_par_niveau SET etat_code='en_cours' WHERE niveau='N11' AND "
              "sequence_code='A1'")
    c.commit()
    assert mac.main(["--db", str(b4), "--niveau", "N11"]) == 0     # essai à blanc
    assert _ae_lien(c) == {"02"}
    assert mac.main(["--db", str(b4), "--niveau", "N11", "--apply", "--yes"]) == 0
    assert _ae_lien(c) == {"01"}
    assert mac.candidats(c, "N11") == []                           # idempotent
    assert mac.main(["--db", str(b4), "--niveau", "N09"]) == 2     # 6e exclue


# ── B7 — variables ───────────────────────────────────────────────────────────

def test_b7_variables_des_exercices_ecrites_si_presentes_gardees_si_absentes(b4, tmp_path,
                                                                             capsys):
    v = "\\xintdefiivar N11A1F01_a := randrange(2,9);"

    def avec(lot):
        lot["objectifs"][0]["exercices"][0]["variables"] = v
        lot["objectifs"][0]["exercices"][1]["variables"] = v           # même nom : signalé
    out = _imp(b4, _lot(tmp_path, avec), capsys)
    c = _conn(b4)
    lire = lambda n: c.execute("SELECT variables FROM exercices WHERE niveau='N11' AND "  # noqa
                               "sequence='A1' AND serie_code='F' AND num=?", (n,)).fetchone()[0]
    assert lire(1) == v
    assert "variable N11A1F01_a déjà déclarée par A1 F01" in out
    _imp(b4, _lot(tmp_path), capsys)                    # clé absente : base gardée
    assert lire(1) == v


# ── B9 — titre échappé ───────────────────────────────────────────────────────

def test_b9_titre_d_exercice_avec_pourcent_echappe_dans_le_livret_fiches():
    from services.livret_sequence_6e import _titre_exo
    t = _titre_exo({"titre": "Passer par 10 % ou 1 %", "code": "F01"})
    assert t.startswith(r"Passer par 10 \% ou 1 \%")
    assert _titre_exo({"titre": r"Déjà \% et $x_1$", "code": "F01"}).startswith(
        r"Déjà \% et $x_1$")


# ── P0 à P7 — ordre des parties et rituels ───────────────────────────────────

@pytest.fixture
def b4_rituels(b4, tmp_path, capsys):
    """Lot A1 importé (cartes CA01 sous A1-02, CA02 sous A1-03), 6 séances
    pour la partie, cartes validées (CA02 créée en 5e : réactivation), une
    évaluation sur A1-02 et A1-03, référentiel 2027_N11 au modèle Fiches."""
    def modif(lot):
        lot["seances_cours"] = {"1": 0}
        for o in lot["objectifs"]:
            o["seances"] = 3
        lot["evaluations"] = _paire("Évaluation --- Produits", pts=(10, 10))
    _imp(b4, _lot(tmp_path, modif), capsys)
    c = sqlite3.connect(b4)
    c.execute("UPDATE cartes_automatisme SET etat_code='valide' WHERE niveau='N11' AND "
              "sequence='A1'")
    c.execute("UPDATE cartes_automatisme SET niveau_creation='N10' WHERE niveau='N11' AND "
              "sequence='A1' AND num=2")
    _ins(c, "referentiel_niveaux", id="2027_N11", niveau="N11", version="2027",
         etat="en_cours", source="interne", type_ref="principal",
         gabarit_documents="sixieme", cartes_automatisme=1)
    c.commit()
    c.close()
    return b4


def test_p0_saisie_de_l_ordre_erreurs_nommees_rien_n_est_ecrit(b4_rituels):
    c = _conn(b4_rituels)
    parties = pr.parties_du_referentiel(c, "2027_N11")
    assert [p["code"] for p in parties] == ["A1-P1"]
    r = pr.analyser_saisie("# commentaire\nA1-P1 2\nZ9-P1\nA1-1\nn'importe quoi", parties)
    assert r["ordre"] == [{"partie": "A1-P1", "semaines": 2}]
    assert r["erreurs"] == ["ligne 3 : partie Z9-P1 absente du référentiel",
                            "ligne 4 : partie A1-P1 en double",
                            "ligne 5 : « n'importe quoi » illisible (attendu A1-P1, ou A1-P1 2)"]
    with pytest.raises(pr.ProgressionErreur):
        pr.enregistrer(c, "2027_N11", texte="Z9-P1")
    assert pr.lire(c, "2027_N11")["ordre"] == []


def test_p1_p2_p3_p4_semaines_cartes_nouvelles_rappels_et_reactivation(b4_rituels):
    c = _conn(b4_rituels)
    pr.enregistrer(c, "2027_N11", texte="A1-P1", parametres={"semaines_annee": 20})
    cal = pr.calendrier(c, "2027_N11")
    assert cal["parties"][0]["debut"] == 1 and cal["parties"][0]["fin"] == 2   # 6 séances / 3
    sem = {s["numero"]: s for s in cal["semaines"]}
    # P4 — carte de 5e : réactivée la 1re semaine de la partie, puis rappels.
    assert [x["num"] for x in sem[1]["reactivation"]] == [2]
    # P2 — carte de 4e : rituel la semaine qui suit la partie.
    assert [x["num"] for x in sem[3]["nouvelles"]] == [1]
    # P3 — rappels à +1 et +4 semaines, puis toutes les 6 semaines (20 semaines).
    rap1 = [w for w, s in sem.items() if any(x["num"] == 1 for x in s["rappels"])]
    assert rap1 == [4, 7, 13, 19]
    rap2 = [w for w, s in sem.items() if any(x["num"] == 2 for x in s["rappels"])]
    assert rap2 == [2, 5, 11, 17]


def test_p5_p6_seance_d_evaluation_une_semaine_apres_et_derniere_sequence_non_evaluee(b4_rituels):
    c = _conn(b4_rituels)
    pr.enregistrer(c, "2027_N11", texte="A1-P1")
    cal = pr.calendrier(c, "2027_N11")
    assert cal["non_evaluees"] == ["Évaluation --- Produits"]      # P6 : règle de progression
    assert all(not s["evaluations"] for s in cal["semaines"])
    cal = pr.calendrier(c, "2027_N11", parametres={"derniere_sequence_non_evaluee": False})
    places = [(s["numero"], [e["titre"] for e in s["evaluations"]]) for s in cal["semaines"]
              if s["evaluations"]]
    # Partie finie en semaine 2 : séance d'évaluation de la semaine 4 (paire, ≥ 2 + 1).
    assert places == [(4, ["Évaluation --- Produits"])]
    assert cal["semaines"][3]["charge_evaluation"] == {"minutes": 20, "objectifs": 2}


def test_p7_cartes_non_validees_absentes_et_comptees(b4_rituels):
    c = _conn(b4_rituels)
    c.execute("UPDATE cartes_automatisme SET etat_code='en_cours' WHERE num=1 AND "
              "sequence='A1' AND niveau='N11'")
    pr.enregistrer(c, "2027_N11", texte="A1-P1")
    cal = pr.calendrier(c, "2027_N11")
    assert not any(s["nouvelles"] for s in cal["semaines"])
    assert "1 carte(s) rattachée(s) non validée(s) : absentes du document" in \
        cal["avertissements"]


def test_document_et_routes_de_la_progression_des_rituels(b4_rituels):
    from app import create_app
    app = create_app(b4_rituels.parent, profil="atelier")
    cl = app.test_client()
    r = cl.put("/api/progression-rituels/2027_N11", json={"texte": "A1-P1",
                                                         "parametres": {"jour_evaluation": "jeudi"}})
    assert r.status_code == 200 and r.get_json()["parametres"]["jour_evaluation"] == "jeudi"
    assert cl.put("/api/progression-rituels/2027_N11",
                  json={"texte": "B9-P1"}).status_code == 400
    assert cl.get("/api/progression-rituels/inconnu").status_code == 404
    tex = cl.get("/api/progression-rituels/2027_N11/tex").get_data(as_text=True)
    assert r"\section*{Semaine 3 --- }" not in tex
    assert r"\section*{Semaine 1 --- A1-P1}" in tex and r"\begin{seqCarteRecap}" in tex
    assert "jeudi" in tex
    aucune = cl.get("/api/progression-rituels/2027_N11/tex?cartes=aucune").get_data(as_text=True)
    assert r"\begin{seqCarteRecap}" not in aucune
    # Hors catalogue : la liste des documents du référentiel ne change pas.
    from services import gabarits_documents as gd
    with app.json_store._conn() as conn:
        assert "rituels_progression" not in gd.types_du_referentiel(conn, "2027_N11")


def test_module_evaluations_type_et_duree_par_la_route(b4_rituels):
    from app import create_app
    app = create_app(b4_rituels.parent, profil="atelier")
    cl = app.test_client()
    with app.json_store._conn() as conn:
        eid = conn.execute("SELECT id FROM evaluations WHERE niveau='N11'").fetchone()[0]
    ev = cl.get(f"/api/evaluations/{eid}").get_json()["evaluation"]
    assert (ev["type_evaluation"], ev["duree_auto"], ev["duree"]) == ("evaluation", 20, None)
    ev = cl.patch(f"/api/evaluations/{eid}", json={"type_evaluation": "test_court",
                                                  "duree": "15"}).get_json()["evaluation"]
    assert (ev["type_evaluation"], ev["duree_auto"], ev["duree"]) == ("test_court", 10, 15)
    r = cl.patch(f"/api/evaluations/{eid}", json={"type_evaluation": "quiz"})
    assert r.status_code == 400 and r.get_json()["code"] == "type_evaluation_invalide"


def test_b10b_bonus_de_2_points_des_lots_de_6e_non_signale_hors_4e():
    exos = [{"points": 10, "bonus": False}, {"points": 2, "bonus": True}]
    for niveau, attendu in (("N09", []), ("N11", ["S évaluation « E » : bonus de 2 pts "
                                                  "(règle : 1 pt)"])):
        with imp.niveau_actif(niveau):
            r = imp.Rapport()
            imp.controler_evaluation("S", "E", "evaluation", exos, r)
            assert r.avertissements == attendu


# ── Points de l'étape 3 de la 5e (coordinateur, 18 novembre) ────────────────

def test_f1_import_des_lots_de_5e_niveau_n10_et_referentiel_transcrit():
    with imp.niveau_actif("N10"):
        ref = imp.charger_referentiel()
        assert (imp.CYCLE, ref["niveau"]) == ("C04", "N10")
        assert imp.LOTS_DEFAUT.name == "lot5e"
        assert [s["code"] for s in ref["sequences"]][:2] == ["A1", "A2"]


def test_f2_archivage_signale_les_referentiels_non_figes_qui_lisent_la_structure(b4, capsys):
    from outils import archiver_structure_niveau as arch
    c = sqlite3.connect(b4)
    for rid, etat in (("2025_N10", "en_cours"), ("N10_v2024", "utilise"), ("2026_N10", "verrouille")):
        _ins(c, "referentiel_niveaux", id=rid, niveau="N10", version=rid[:4], etat=etat,
             source="interne", type_ref="principal")
    c.commit()
    assert arch.referentiels_non_figes(c, "N10") == [("2025_N10", "en_cours")]
    r = arch.Rapport("N10")
    arch.avertir_referentiels_non_figes(c, "N10", r)
    assert len(r.avertissements) == 1 and "2025_N10" in r.texte()
    assert "verrouiller avant" in r.texte()


def test_f3_niveau_de_creation_corrige_par_l_import_meme_sur_carte_validee(b4, tmp_path, capsys):
    _imp(b4, _lot(tmp_path), capsys)
    c = _conn(b4)
    c.execute("UPDATE cartes_automatisme SET etat_code='valide', mtime='2000-01-01 00:00:00' "
              "WHERE niveau='N11' AND sequence='A1'")
    c.commit()

    def nc(lot):
        lot["objectifs"][0]["cartes_automatisme"][0]["niveau_creation"] = "N10"
    out = _imp(b4, _lot(tmp_path, nc), capsys)
    r = c.execute("SELECT niveau_creation, mtime FROM cartes_automatisme WHERE niveau='N11' "
                  "AND sequence='A1' AND num=1").fetchone()
    assert tuple(r) == ("N10", "2000-01-01 00:00:00")          # rendu inchangé : mtime gardé
    assert "CA1 (validée) : niveau de création corrigé N11 → N10" in out
    assert "validée dans l'atelier : contenu du lot non appliqué" not in out

    def nc_et_recto(lot):
        nc(lot)
        lot["objectifs"][0]["cartes_automatisme"][0]["recto"] = "Autre recto"
    out = _imp(b4, _lot(tmp_path, nc_et_recto), capsys)
    assert "validée dans l'atelier : contenu du lot non appliqué" in out


def test_f3_niveau_de_creation_modifiable_dans_l_atelier_meme_carte_validee(b4, tmp_path, capsys):
    from app import create_app
    _imp(b4, _lot(tmp_path), capsys)
    c = sqlite3.connect(b4)
    cid = c.execute("SELECT id FROM cartes_automatisme WHERE niveau='N11' AND num=1").fetchone()[0]
    c.execute("UPDATE cartes_automatisme SET etat_code='valide' WHERE id=?", (cid,))
    c.commit()
    cl = create_app(b4.parent, profil="atelier").test_client()
    assert cl.get(f"/api/cartes/{cid}").get_json()["niveau_creation"] == "N11"
    r = cl.put(f"/api/cartes/{cid}/niveau-creation", json={"niveau_creation": "n09"})
    assert r.status_code == 200 and r.get_json()["niveau_creation"] == "N09"
    assert cl.put(f"/api/cartes/{cid}/niveau-creation",
                  json={"niveau_creation": "N13"}).status_code == 400


def test_point5_carte_de_6e_ecrite_en_5e_rappelee_jamais_nouvelle():
    assert pr._rang_niveau("N09") < pr._rang_niveau("N10") < pr._rang_niveau("N11")


def test_point5_carte_de_6e_dans_les_rituels_de_4e_est_reactivee(b4_rituels):
    c = _conn(b4_rituels)
    c.execute("UPDATE cartes_automatisme SET niveau_creation='N09' WHERE niveau='N11' AND "
              "sequence='A1' AND num=1")
    pr.enregistrer(c, "2027_N11", texte="A1-P1")
    cal = pr.calendrier(c, "2027_N11")
    assert sorted(x["num"] for x in cal["semaines"][0]["reactivation"]) == [1, 2]
    assert not any(s["nouvelles"] for s in cal["semaines"])
