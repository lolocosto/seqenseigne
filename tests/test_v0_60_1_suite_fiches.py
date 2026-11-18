"""tests/test_v0_60_1_suite_fiches.py — v0.60.1

Suite de la version 2 du modèle Fiches et décisions du 18 novembre
(`doc/redemarrage_v0_60_1.md`, brief `col4/BRIEF_V0601.md`). Chaque test nomme
la décision qu'il protège :

  D15  10 min par objectif aussi en 6e (référentiels non figés), sans toucher
       aux publications figées ;
  D16  bonus : 1 pt sur tout le cycle 4 (absent compris), rien pour la 6e ;
  D17a document « Tests courts » (option cartes) : cartes évaluées dans le
       corrigé ; D17b tests courts placés dans les séances seulement si
       l'enseignant le choisit ;
  D-SE document « séance d'évaluation » : refus au-delà de 50 min / 5 objectifs ;
  D18  mode de mise en route du principal (déduction sûre, saisie, figé en
       lecture seule, format d'échange 1.7 sans changer l'empreinte si absent) ;
  E9   cartes de la partie dans le plan de travail Fiches ;
  F4   propriété « sans carte » de l'objectif, avertissement à la validation ;
  TC   titre court saisi dans l'atelier ; C11, C12 petits manques et traces S….
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from outils import import_lot6e as imp
from services import cartes_partie as cp
from services import documents_evaluation_v2 as dev
from services import evaluations_v2 as ev2
from services import mise_en_route_referentiel as mer
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
from tests.test_v0_60_0_version2_fiches import (  # noqa: F401
    _conn,
    _imp,
    _lot,
    _paire,
    b4,
    b4_rituels,
)


@pytest.fixture(autouse=True)
def _document_sans_paquet(monkeypatch):
    """Les définitions du paquet LaTeX ne sont pas dans la base de test : le
    document complet est remplacé par son corps (la compilation est vérifiée
    à part, sur la base rejouée : journal de la v0.60.1)."""
    def corps(conn, niveau, titre, lignes, corrigee, *a, **k):
        return "\\begin{document}\n" + "\n".join(lignes) + "\n\\end{document}"
    import services.livret_sequence_6e as l6
    import services.plan_travail_6e as pt
    monkeypatch.setattr(l6, "document", corps)
    monkeypatch.setattr(pt, "document", corps)


def _client(db):
    from app import create_app
    return create_app(db.parent, profil="atelier").test_client()


def _sn(c, code="A1"):
    return c.execute("SELECT id FROM sequences_par_niveau WHERE niveau='N11' AND "
                     "sequence_code=?", (code,)).fetchone()[0]


# ── D15 — 10 min par objectif en 6e ──────────────────────────────────────────

def test_d15_six_eme_dix_minutes_par_objectif_et_partie_sans_calculatrice_au_prorata(tmp_path):
    """La règle de la v0.60 n'a pas de cas particulier de niveau : une
    évaluation de 6e à 4 objectifs dure 40 min ; sa partie sans calculatrice
    (3 objectifs sur 4) dure 30 min, et non plus 55 min × points / total."""
    c = sqlite3.connect(tmp_path / "e.db")
    c.execute("CREATE TABLE evaluations (id TEXT PRIMARY KEY, niveau TEXT, numero INT, "
              "titre TEXT, mtime TEXT)")
    c.execute("CREATE TABLE evaluation_objectifs (evaluation_id TEXT, objectif_id TEXT)")
    c.execute("INSERT INTO evaluations VALUES ('e6', 'N09', 1, 'Évaluation --- A3', '')")
    c.executemany("INSERT INTO evaluation_objectifs VALUES ('e6', ?)",
                  [("o1",), ("o2",), ("o3",), ("o4",)])
    ev2.migrer(c)
    assert ev2.duree_auto(c, "e6") == 40
    p1 = [{"objectif": o, "points": 4} for o in ("A3-02", "A3-03", "A3-04")]
    assert ev2.duree_partie1_par_objectifs([p1, [{"objectif": "A3-05", "points": 4}]], 40) == 30


def test_d15_publication_figee_resservie_sans_recalcul(tmp_path):
    """Un référentiel verrouillé garde sa première publication : rien de la
    v0.60.1 (durées, mise en route) ne la réécrit."""
    from services import format_referentiel as fr
    chemin = tmp_path / "referentiels" / "R" / "_publication" / "referentiel.json"
    chemin.parent.mkdir(parents=True)
    doc = {"format": fr.FORMAT, "format_version": "1.2", "exporte_par": "seqenseigne 0.59",
           "referentiel": {"id": "R", "etat": "verrouille"}, "empreinte": "sha256:x"}
    chemin.write_text(json.dumps(doc), encoding="utf-8")
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE referentiel_niveaux (id TEXT, niveau TEXT, version TEXT, "
              "etat TEXT, source TEXT, type_ref TEXT, cartes_automatisme INT DEFAULT 0)")
    c.execute("INSERT INTO referentiel_niveaux VALUES ('R','N09','2026','verrouille',"
              "'interne','principal',0)")
    mer.migrer(c)
    out = fr.exporter(c, "R", tmp_path)
    assert out["format_version"] == "1.2" and "mise_en_route" not in out["referentiel"]


# ── D16 — bonus ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("niveau,bonus,attendu", [
    ("N09", 2, []), ("N09", 0, []),
    ("N10", 0, ["S évaluation « E » : pas de bonus (règle : 1 pt)"]),
    ("N11", 2, ["S évaluation « E » : bonus de 2 pts (règle : 1 pt)"]),
    ("N11", 1, []),
])
def test_d16_bonus_un_point_sur_tout_le_cycle_4_absent_compris_rien_en_6e(niveau, bonus,
                                                                           attendu):
    exos = [{"points": 20, "bonus": False}] + ([{"points": bonus, "bonus": True}] if bonus else [])
    with imp.niveau_actif(niveau):
        r = imp.Rapport()
        imp.controler_evaluation("S", "E", "evaluation", exos, r)
    assert r.avertissements == attendu


# ── F4 — propriété « sans carte » et avertissement de validation ─────────────

def test_f4_objectif_sans_carte_signale_a_la_validation_sauf_propriete_du_lot(b4_rituels,
                                                                             tmp_path, capsys):
    from services.v2_edition import avertissements_validation
    c = _conn(b4_rituels)
    sn = _sn(c)
    c.execute("DELETE FROM objectif_cartes WHERE objectif_id IN (SELECT o.id FROM objectifs o "
              "JOIN sequence_parties p ON p.id = o.partie_id WHERE p.sequence_par_niveau_id=? "
              "AND o.code = '03')", (sn,))
    c.commit()
    msgs = avertissements_validation(c, sn)
    assert any("L'objectif A1-03 n'a pas de carte d'automatisme" in m for m in msgs)
    assert not any("A1-02" in m or "A1-01" in m for m in msgs)      # « Cours » exclu
    c.close()

    def modif(lot):
        for o in lot["objectifs"]:
            if o["code"] == "A1-03":
                o["sans_carte"] = True
    out = _imp(b4_rituels, _lot(tmp_path, modif), capsys)
    assert "A1-03 : sans carte voulue" in out
    c = _conn(b4_rituels)
    assert not any("A1-03" in m for m in avertissements_validation(c, _sn(c)))
    # Clé absente au réimport : la propriété est gardée (comme `seances`).
    c.close()
    _imp(b4_rituels, _lot(tmp_path), capsys)
    c = _conn(b4_rituels)
    assert cp.objectifs_sans_carte(c, _sn(c)) == []


def test_f4_rien_sans_l_option_cartes_ni_en_6e(b4_rituels):
    c = _conn(b4_rituels)
    c.execute("UPDATE referentiel_niveaux SET cartes_automatisme = 0 WHERE id = '2027_N11'")
    c.execute("DELETE FROM objectif_cartes")
    assert cp.avertissements_validation(c, _sn(c), "N11") == []


def test_f4_valeur_invalide_signalee_et_ignoree(b4, tmp_path, capsys):
    def modif(lot):
        lot["objectifs"][0]["sans_carte"] = "oui"
    out = _imp(b4, _lot(tmp_path, modif), capsys)
    assert "sans_carte 'oui' invalide" in out


# ── E9 — cartes de la partie dans le plan de travail ─────────────────────────

def test_e9_plan_de_travail_liste_les_cartes_validees_de_la_partie(b4_rituels):
    from services.plan_travail_6e import generer_plan_travail_6e
    c = _conn(b4_rituels)
    tex = generer_plan_travail_6e(c, "N11", "A1")
    assert "Cartes d'automatisme (2)" in tex and "planche à distribuer au début" in tex
    assert r"\textbf{A1-CA01}" in tex
    c.execute("UPDATE cartes_automatisme SET etat_code='en_cours' WHERE num=2 AND niveau='N11'")
    assert "Cartes d'automatisme (1)" in generer_plan_travail_6e(c, "N11", "A1")
    # Sans l'option cartes : plan identique à celui de la v0.60.0 (aucune rubrique).
    c.execute("UPDATE referentiel_niveaux SET cartes_automatisme = 0 WHERE id = '2027_N11'")
    assert "Cartes d'automatisme" not in generer_plan_travail_6e(c, "N11", "A1")


# ── D17 — tests courts associés aux cartes ───────────────────────────────────

@pytest.fixture
def b4_tests(b4_rituels, tmp_path, capsys):
    def modif(lot):
        lot["seances_cours"] = {"1": 0}
        for o in lot["objectifs"]:
            o["seances"] = 3
        lot["evaluations"] = _paire("Évaluation --- Produits", pts=(10, 10))
        lot["tests_courts"] = _paire("Test court --- Produits", bonus=1, pts=(5, 4))
    _imp(b4_rituels, _lot(tmp_path, modif), capsys)
    return b4_rituels


def test_d17a_document_tests_courts_au_catalogue_avec_l_option_cartes_seulement(b4_tests):
    from services import gabarits_documents as gd
    c = _conn(b4_tests)
    assert "tests_courts_6e" in gd.types_du_referentiel(c, "2027_N11")
    c.execute("UPDATE referentiel_niveaux SET cartes_automatisme = 0 WHERE id = '2027_N11'")
    assert "tests_courts_6e" not in gd.types_du_referentiel(c, "2027_N11")
    c.execute("UPDATE referentiel_niveaux SET cartes_automatisme = 1 WHERE id = '2027_N11'")
    cibles = dev.cibles_tests_courts(c, "N11")
    assert [(x["cible_id"], x["sequence"], x["partie"]) for x in cibles] == \
        [("TC/N11/A1/p1", "A1", 1)]
    # Le document « Évaluations » garde ses cibles (le test court y reste).
    from services.referentiel_documents_compilation import _cibles_evaluations_6e
    assert len(_cibles_evaluations_6e(c, "N11")) == 2


def test_d17a_corrige_du_test_court_liste_les_cartes_evaluees_pas_le_sujet_eleve(b4_tests):
    c = _conn(b4_tests)
    eid = dev.cibles_tests_courts(c, "N11")[0]["eval_id"]
    corrige = dev.generer_test_court(c, eid, {"version": "corrigee"})
    eleve = dev.generer_test_court(c, eid, {"version": "eleve"})
    assert "Cartes d'automatisme évaluées (partie 1, 2 cartes)" in corrige
    assert "Cartes d'automatisme évaluées" not in eleve
    # Le sujet élève est celui du document « Évaluations » au caractère près.
    from services.render_evaluation import generer_tex_evaluation_6e
    assert eleve.split(r"\begin{document}")[1] == \
        generer_tex_evaluation_6e(c, eid, {"version": "eleve"}).split(r"\begin{document}")[1]


def test_d17b_tests_courts_non_places_par_defaut_places_si_choisis(b4_tests):
    c = _conn(b4_tests)
    pr.enregistrer(c, "2027_N11", texte="A1-P1",
                   parametres={"derniere_sequence_non_evaluee": False})
    places = lambda cal: [(s["numero"], [e["titre"] for e in s["evaluations"]])  # noqa: E731
                          for s in cal["semaines"] if s["evaluations"]]
    assert places(pr.calendrier(c, "2027_N11")) == [(4, ["Évaluation --- Produits"])]
    cal = pr.calendrier(c, "2027_N11", parametres={"tests_courts": "seances"})
    # Partie finie semaine 2, cartes au rituel semaine 3, 2 semaines pour les
    # connaître : test court à la séance de la semaine 6 ; 10 min, 0 objectif.
    assert places(cal) == [(4, ["Évaluation --- Produits"]), (6, ["Test court --- Produits"])]
    assert cal["semaines"][5]["charge_evaluation"] == {"minutes": 10, "objectifs": 0}
    with pytest.raises(pr.ProgressionErreur):
        pr.calendrier(c, "2027_N11", parametres={"tests_courts": "partout"})


def test_dse_seance_d_evaluation_en_tete_sujets_et_refus_au_dela_de_50_minutes(b4_tests):
    c = _conn(b4_tests)
    pr.enregistrer(c, "2027_N11", texte="A1-P1",
                   parametres={"derniere_sequence_non_evaluee": False,
                               "tests_courts": "seances", "delai_test_court": 1})
    se = dev.seance(c, "2027_N11", 4)
    assert [e["titre"] for e in se["evaluations"]] == ["Évaluation --- Produits",
                                                       "Test court --- Produits"]
    assert (se["minutes"], se["objectifs"]) == (30, 2) and dev.controler_seance(se) == []
    tex = dev.generer_seance_evaluation(c, "2027_N11", 4, {"version": "corrigee"})
    assert "Durée totale : 30 min" in tex and tex.count(r"\seqTitreEvalSix") == 2
    assert "Cartes d'automatisme évaluées" in tex
    with pytest.raises(dev.DocumentEvaluationErreur):
        dev.seance(c, "2027_N11", 3)                      # pas de séance en semaine impaire
    trop = {**se, "minutes": 60}
    assert dev.controler_seance(trop) == ["60 min pour une séance de 50 min"]
    assert dev.controler_seance({**trop, "evaluations": se["evaluations"][:1]}) == []


def test_dse_routes_de_la_seance(b4_tests):
    cl = _client(b4_tests)
    cl.put("/api/progression-rituels/2027_N11", json={
        "texte": "A1-P1", "parametres": {"derniere_sequence_non_evaluee": False}})
    r = cl.get("/api/progression-rituels/2027_N11/seance/4")
    assert r.status_code == 200 and r.get_json()["minutes"] == 20
    assert cl.get("/api/progression-rituels/2027_N11/seance/5").status_code == 400
    tex = cl.get("/api/progression-rituels/2027_N11/seance/4/tex?sujet=B").get_data(as_text=True)
    assert "Séance d'évaluation --- semaine 4" in tex and "sujet B" in tex


# ── D18 — mode de mise en route ──────────────────────────────────────────────

def _refs(tmp_path, lignes):
    c = sqlite3.connect(tmp_path / "r.db")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE referentiel_niveaux (id TEXT PRIMARY KEY, niveau TEXT, version TEXT,"
              " etat TEXT, source TEXT, type_ref TEXT, cartes_automatisme INT DEFAULT 0, "
              "instantane TEXT DEFAULT '')")
    c.executemany("INSERT INTO referentiel_niveaux VALUES (?,?,?,?,?,?,?,?)", lignes)
    return c


def test_d18a_deduction_sure_une_seule_fois_sans_toucher_aux_instantanes(tmp_path):
    c = _refs(tmp_path, [
        ("2027_N11", "N11", "2027", "valide", "interne", "principal", 1, ""),
        ("2026_N09", "N09", "2026", "verrouille", "interne", "principal", 0, "{fige}"),
        ("2026_N09b", "N09", "2026b", "valide", "interne", "mer", 0, ""),
        ("M2026_N09", "N09", "M2026", "en_cours", "externe", "mer", 0, ""),
        ("X2026_N09", "N09", "X2026", "utilise", "externe", "principal", 0, ""),
        ("2025_N10", "N10", "2025", "en_cours", "interne", "principal", 0, "")])
    faits = mer.migrer(c)
    assert "modes de mise en route déduits : 2" in faits
    modes = {r[0]: (r[1], r[2]) for r in c.execute(
        "SELECT id, mise_en_route, mer_referentiel FROM referentiel_niveaux")}
    assert modes["2027_N11"] == ("cartes", "")
    assert modes["2026_N09"] == ("progression", "2026_N09b")
    assert modes["X2026_N09"] == ("", "") and modes["2025_N10"] == ("", "")
    assert c.execute("SELECT instantane FROM referentiel_niveaux WHERE id='2026_N09'"
                     ).fetchone()[0] == "{fige}"
    # Une saisie (même « non renseigné ») n'est jamais reprise par la migration suivante.
    c.execute("UPDATE referentiel_niveaux SET mise_en_route='' WHERE id='2027_N11'")
    assert mer.migrer(c) == []
    assert mer.lire(c, "2027_N11")["mode"] == ""


def test_d18a_mer_candidate_ambigue_ou_d_un_autre_niveau_rien_n_est_deduit(tmp_path):
    c = _refs(tmp_path, [
        ("P9", "N09", "2026", "valide", "interne", "principal", 0, ""),
        ("A", "N09", "2026b", "valide", "interne", "mer", 0, ""),
        ("B", "N09", "2026b", "en_cours", "interne", "mer", 0, ""),
        ("P10", "N10", "2026", "valide", "interne", "principal", 0, ""),
        ("C", "N12", "2026b", "valide", "interne", "mer", 0, "")])
    mer.migrer(c)
    assert mer.lire(c, "P9")["mode"] == "" and mer.lire(c, "P10")["mode"] == ""


def test_d18b_saisie_controlee_et_lecture_seule_quand_fige(tmp_path):
    c = _refs(tmp_path, [
        ("P", "N09", "2027", "en_cours", "interne", "principal", 0, ""),
        ("F", "N09", "2026", "verrouille", "interne", "principal", 0, ""),
        ("M", "N09", "2027b", "en_cours", "interne", "mer", 0, ""),
        ("M10", "N10", "2027b", "en_cours", "interne", "mer", 0, "")])
    mer.migrer(c)
    assert mer.poser(c, "P", "progression", "M")["libelle"] == \
        "progression de mise en route (M)"
    for mode, ref in (("progression", ""), ("progression", "M10"), ("leitner", "")):
        with pytest.raises(mer.MiseEnRouteErreur):
            mer.poser(c, "P", mode, ref)
    with pytest.raises(mer.MiseEnRouteErreur) as e:
        mer.poser(c, "F", "aucune")
    assert e.value.statut == 409
    with pytest.raises(mer.MiseEnRouteErreur):
        mer.poser(c, "M", "cartes")                         # pas un principal
    assert mer.poser(c, "P", "cartes", "M")["mer"] == ""    # MER ignorée hors progression


def test_d18_routes_creation_onglet_et_liste(b4_rituels):
    cl = _client(b4_rituels)
    r = cl.post("/api/referentiels/coquille", json={"niveau": "N11", "gabarit": "sixieme",
                                                     "mise_en_route": "aucune"})
    assert r.status_code == 201 and r.get_json()["ref"]["mise_en_route"] == "aucune"
    rid = r.get_json()["ref"]["id"]
    with sqlite3.connect(b4_rituels) as c:
        n = c.execute("SELECT COUNT(*) FROM referentiel_niveaux").fetchone()[0]
    assert cl.post("/api/referentiels/coquille", json={
        "niveau": "N11", "mise_en_route": "progression"}).status_code == 400
    with sqlite3.connect(b4_rituels) as c:          # refus : rien de créé à moitié
        assert c.execute("SELECT COUNT(*) FROM referentiel_niveaux").fetchone()[0] == n
    d = cl.get(f"/api/referentiels/{rid}/mise-en-route").get_json()
    assert (d["mode"], d["modifiable"], d["type_ref"]) == ("aucune", True, "principal")
    r = cl.put(f"/api/referentiels/{rid}/mise-en-route", json={"mode": "cartes"})
    assert r.status_code == 200 and r.get_json()["libelle"] == "cartes d'automatisme"
    liste = cl.get("/api/referentiels?niveau=N11").get_json()["referentiels"]
    assert [x.get("mise_en_route") for x in liste if x["id"] == rid] == ["cartes"]
    with sqlite3.connect(b4_rituels) as c:
        c.execute("UPDATE referentiel_niveaux SET etat='verrouille' WHERE id=?", (rid,))
    assert cl.put(f"/api/referentiels/{rid}/mise-en-route",
                  json={"mode": "aucune"}).status_code == 409
    assert cl.get(f"/api/referentiels/{rid}/mise-en-route").get_json()["modifiable"] is False


def test_d18d_format_d_echange_1_7_seulement_si_renseigne_empreinte_inchangee_sinon(b4_rituels):
    from services import format_referentiel as fr
    c = _conn(b4_rituels)
    mer.poser(c, "2027_N11", "")
    sans = fr.construire(c, "2027_N11", None)
    assert "mise_en_route" not in sans["referentiel"] and sans["format_version"] != "1.7"
    mer.poser(c, "2027_N11", "cartes")
    avec = fr.construire(c, "2027_N11", None)
    assert avec["format_version"] == fr.FORMAT_VERSION == "1.7"
    assert avec["referentiel"]["mise_en_route"] == {"mode": "cartes"}
    assert fr.valider(avec) == []
    mer.poser(c, "2027_N11", "")
    assert fr.construire(c, "2027_N11", None)["empreinte"] == sans["empreinte"]


def test_d18c_vue_d_ensemble_ligne_mise_en_route_seulement_si_renseignee(b4_rituels):
    from services.vue_ensemble_referentiel import generer_vue_ensemble
    c = _conn(b4_rituels)
    mer.poser(c, "2027_N11", "")
    assert "Mise en route &" not in generer_vue_ensemble(c, "2027_N11")
    mer.poser(c, "2027_N11", "cartes")
    assert r"Mise en route & cartes d'automatisme \\" in generer_vue_ensemble(c, "2027_N11")
    pr.enregistrer(c, "2027_N11", texte="A1-P1")
    assert "Mise en route : cartes d'automatisme" in pr.generer_tex(c, "2027_N11")


# ── TC — titre court ─────────────────────────────────────────────────────────

def test_tc_titre_court_saisi_dans_l_atelier_lecture_seule_si_validee(b4_rituels):
    cl = _client(b4_rituels)
    with sqlite3.connect(b4_rituels) as c:
        sn = _sn(c)
    url = f"/api/v2/sequences-par-niveau/{sn}/titre-court"
    r = cl.put(url, json={"titre_court": "  Nombres   relatifs "})
    assert r.status_code == 200 and r.get_json()["titre_court"] == "Nombres relatifs"
    from services.fiches_cycle4 import titre_court
    with sqlite3.connect(b4_rituels) as c:
        assert titre_court(c, "N11", "A1") == "Nombres relatifs"
        c.execute("UPDATE sequences_par_niveau SET etat_code='valide' WHERE id=?", (sn,))
    assert cl.put(url, json={"titre_court": "x"}).status_code == 409
    assert cl.put(url, json={"titre_court": "x" * 121}).status_code == 400
    assert cl.put("/api/v2/sequences-par-niveau/inconnu/titre-court",
                  json={"titre_court": "x"}).status_code == 404


# ── C11, C12 ─────────────────────────────────────────────────────────────────

def test_c11_rendu_par_lot_recense_les_cartes_mentales_avec_leur_partie(b4_rituels):
    from persistence.sqlite_store import SqliteStore
    from services.compilation_batch import Filtre, recenser_atomes
    st = SqliteStore(b4_rituels.parent)
    with st._conn() as c:
        if c.execute("SELECT COUNT(*) FROM cartes_mentales").fetchone()[0] == 0:
            pid = c.execute("SELECT p.id FROM sequence_parties p JOIN sequences_par_niveau sn "
                            "ON sn.id = p.sequence_par_niveau_id WHERE sn.niveau='N11' AND "
                            "sn.sequence_code='A1'").fetchone()[0]
            _ins(c, "cartes_mentales", id="cm1", partie_id=pid, titre="T",
                 latex="\\begin{seqCarteMentaleSix}{T}\\end{seqCarteMentaleSix}")
    a = recenser_atomes(st, Filtre(type="carte_mentale", niveau="N11"))
    assert [(x.id, x.sequence, x.identifiant) for x in a] == [("1", "A1", "N11/A1/CM partie 1")]


def test_c11_sans_cache_transmis_a_la_compilation(monkeypatch, tmp_path):
    from services import compilation_batch as cb
    vus = {}

    class R:
        ok, depuis_cache, duree_ms, erreurs, log_complet = True, False, 1, [], ""

    def faux(**k):
        vus.update(k)
        return R()
    monkeypatch.setattr(cb, "compiler_atome", faux)
    monkeypatch.setattr(cb, "generer_tex_par_type", lambda *a, **k: "tex")
    at = cb.Atome(type="fiche", id="f", niveau="N11", sequence="A1", identifiant="i", titre="t")
    cb.compiler_un_atome(None, at, None, None, tmp_path, None, None, 30, ignorer_cache=True)
    assert vus["ignorer_cache"] is True
    vus.clear()
    cb.compiler_un_atome(None, at, None, None, tmp_path, None, None, 30)
    assert "ignorer_cache" not in vus


def test_c12c_import_de_cycle_refuse_sur_un_cycle_migre_en_codes_a1(b4_rituels):
    from routes.cycle import cycle_migre_codes_theme
    cl = _client(b4_rituels)
    with sqlite3.connect(b4_rituels) as c:
        assert cycle_migre_codes_theme(c, "C04") is True
        avant = c.execute("SELECT code, nom FROM sequences_du_cycle ORDER BY code").fetchall()
    r = cl.post("/api/admin/cycle/importer", json={"cycle_code": "C04"})
    assert r.status_code == 409 and r.get_json()["code"] == "cycle_migre"
    with sqlite3.connect(b4_rituels) as c:
        assert c.execute("SELECT code, nom FROM sequences_du_cycle ORDER BY code").fetchall() \
            == avant


# ── Réimport des tests courts de 4e (coordinateur, 18 novembre) ──────────────

def _paire_courte(titre):
    """Test court refait : un exercice de moins (le bonus seul reste), autre texte."""
    latex = ("\\seqExoEval{Produits}{10 pts --- A1-02}\nQuestion refaite.\n"
             "\\seqExoEval{Bonus}{1 pt --- A1-02}\nBonus refait.\n")
    return [{"titre": titre, "sujet": s, "latex": latex,
             "bareme": [["A1-02", 10], ["Bonus", 1]]} for s in ("A", "B")]


@pytest.fixture
def b4_valide(b4, tmp_path, capsys):
    """État de Laurent : le test court importé comme évaluation (3 exercices),
    séquence, évaluation et exercices EV validés."""
    def modif(lot):
        lot["evaluations"] = _paire("Test court --- Produits", pts=(6, 4))
    _imp(b4, _lot(tmp_path, modif), capsys)
    c = sqlite3.connect(b4)
    c.execute("UPDATE evaluations SET etat_code='valide' WHERE niveau='N11'")
    c.execute("UPDATE exercices SET etat_code='valide' WHERE niveau='N11' AND serie_code='EV'")
    c.execute("UPDATE sequences_par_niveau SET etat_code='valide' WHERE niveau='N11' AND "
              "sequence_code='A1'")
    c.commit()
    c.close()
    return b4


def _nouveau_lot(tmp_path):
    def modif(lot):
        lot.pop("evaluations", None)
        lot["tests_courts"] = _paire_courte("Test court --- Produits")
    return _lot(tmp_path, modif)


def test_r7_essai_a_blanc_dit_quoi_repasser_en_cours_et_comment(b4_valide, tmp_path, capsys):
    capsys.readouterr()
    assert _importer(b4_valide, _nouveau_lot(tmp_path)) == 0
    out = capsys.readouterr().out
    i = out.index("== À repasser en cours avant l'import")
    section = out[i:out.index("== Anomalies")]
    assert "Séquences validées (lot non importé) : A1" in section
    assert "A1 « Test court --- Produits »" in section
    assert "portée Niveau › Évaluation" in section and "⟲ En cours" in section


def test_r5_repasser_une_evaluation_en_cours_repasse_ses_exercices_ev_propres(b4_valide):
    cl = _client(b4_valide)
    with sqlite3.connect(b4_valide) as c:
        eid = c.execute("SELECT id FROM evaluations WHERE niveau='N11'").fetchone()[0]
    r = cl.patch(f"/api/evaluations/{eid}/etat", json={"etat_code": "en_cours"})
    assert r.status_code == 200 and r.get_json()["evaluation"]["etat_code"] == "en_cours"
    with sqlite3.connect(b4_valide) as c:
        assert c.execute("SELECT DISTINCT etat_code FROM exercices WHERE niveau='N11' AND "
                         "serie_code='EV'").fetchall() == [("en_cours",)]
    assert cl.patch(f"/api/evaluations/{eid}/etat",
                    json={"etat_code": "en_cours"}).status_code == 200      # déjà : rien
    assert cl.patch(f"/api/evaluations/{eid}/etat", json={"etat_code": "x"}).status_code == 400
    assert cl.patch(f"/api/evaluations/{eid}/etat",
                    json={"etat_code": "valide"}).status_code == 200
    with sqlite3.connect(b4_valide) as c:
        assert c.execute("SELECT DISTINCT etat_code FROM exercices WHERE niveau='N11' AND "
                         "serie_code='EV'").fetchall() == [("valide",)]


def test_r6_reimport_remplace_le_contenu_et_devient_test_court_sans_doublon(b4_valide, tmp_path,
                                                                           capsys):
    cl = _client(b4_valide)
    with sqlite3.connect(b4_valide) as c:
        sn = _sn(c)
        eid = c.execute("SELECT id FROM evaluations WHERE niveau='N11'").fetchone()[0]
    cl.patch(f"/api/v2/sequences-par-niveau/{sn}/etat", json={"etat_code": "en_cours"})
    cl.patch(f"/api/evaluations/{eid}/etat", json={"etat_code": "en_cours"})
    out = _imp(b4_valide, _nouveau_lot(tmp_path), capsys)
    assert "== À repasser en cours" not in out
    assert "1 ancien(s) exercice(s) EV retiré(s) de l'évaluation" in out
    c = _conn(b4_valide)
    evs = c.execute("SELECT id, type_evaluation FROM evaluations WHERE niveau='N11'").fetchall()
    assert [(e[0], e[1]) for e in evs] == [(eid, "test_court")]            # même ligne
    pts = c.execute("SELECT SUM(bareme_points), COUNT(*) FROM evaluation_exercices WHERE "
                    "evaluation_id=?", (eid,)).fetchone()
    assert tuple(pts) == (11.0, 2)                                         # 10 + bonus 1
    assert c.execute("SELECT COUNT(*) FROM exercices x WHERE niveau='N11' AND serie_code='EV' "
                     "AND NOT EXISTS (SELECT 1 FROM evaluation_exercices ee WHERE "
                     "ee.exercice_id = x.id)").fetchone()[0] == 0          # orphelin retiré
    assert [r[0] for r in c.execute("SELECT o.code FROM evaluation_objectifs eo JOIN objectifs o "
                                    "ON o.id = eo.objectif_id WHERE eo.evaluation_id=?",
                                    (eid,))] == ["02"]                     # A1-03 n'est plus évalué
    c.close()
    out = _imp(b4_valide, _nouveau_lot(tmp_path), capsys)                  # idempotent
    assert "« Test court --- Produits » : inchangée" in out


def test_accord_du_mot_point_dans_les_sujets():
    from services.render_evaluation import libelle_points
    assert [libelle_points(p) for p in (1, 0.5, 1.5, 2, 10)] == \
        ["1 pt", "0,5 pt", "1,5 pt", "2 pts", "10 pts"]
