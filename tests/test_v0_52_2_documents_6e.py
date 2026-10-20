"""tests/test_v0_52_2_documents_6e.py — v0.52.2

Documents de 6e hors livret, dans les ateliers existants : séries EV, TP,
AC, AT de l'atelier d'exercices, évaluations au gabarit de l'équipe de 6e,
travaux personnels / activités complémentaires / séances d'atelier, import
6e en base. Chaque test nomme la décision qu'il protège
(doc/redemarrage_v0_52_2.md).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app  # noqa: E402
from services import gabarits_documents as gd  # noqa: E402
from tests.test_v0_52_1_gabarits_documents import (  # noqa: E402
    DONNEES as DONNEES_0521, GOLDEN, SQL_CYCLE4, SQL_SIXIEME, peupler_cycle4, tex_cycle4)

DONNEES = Path(__file__).parent / "donnees_v0_52_2"

# Documents du cycle 4 aux options les plus larges (plan de travail en tête,
# corrigés de toutes les séries, remédiations…) : .tex figés produits par le
# code de la v0.52.1 (b22206a) sur les données SQL_CYCLE4.
GOLDEN_2 = (
    ("livret_sequence", "N11/S01", {"actif": True, "inclure_plan_travail_en_tete": True,
                                    "inclure_fiches_resume_en_fin": "completes",
                                    "inclure_corriges_serie_a": True,
                                    "inclure_corriges_serie_e": True,
                                    "inclure_corriges_remediation": True}),
    ("livret_exercices", "unique", {"actif": True, "corriges_a": True, "corriges_e": True,
                                    "corriges_remediation": True}),
    ("livret_corriges", "unique", {"actif": True, "inclure_serie_a": True,
                                   "inclure_serie_e": True}),
    ("livret_cours", "unique", {"actif": True}),
)

# Atomes « documents » reliés à un objectif du cycle 4 (ob_02, N11/S01) : ce
# que l'atelier permet désormais. Aucun document du cycle 4 ne doit les voir.
SQL_PARASITES = r"""
INSERT INTO exercices (id, serie, titre, niveau, sequence, num, serie_code, fichier, enonce,
                       corrige, remed_enonce, remed_corrige) VALUES
    ('p_ev', 'évaluation', 'PARASITE EV', 'N11', 'S01', 1, 'EV', '', 'PARASITE EV', 'PARASITE', 'PARASITE B', ''),
    ('p_tp', 'travail personnel', 'PARASITE TP', 'N11', 'S01', 1, 'TP', '', 'PARASITE TP', 'PARASITE', '', ''),
    ('p_ac', 'activité complémentaire', 'PARASITE AC', 'N11', 'S01', 1, 'AC', '', 'PARASITE AC', 'PARASITE', '', ''),
    ('p_at', 'séance d''atelier', 'PARASITE AT', 'N11', 'S01', 1, 'AT', '', 'PARASITE AT', 'PARASITE', '', '');
INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) VALUES
    ('ob_02', 'EV', 'p_ev', 1), ('ob_02', 'TP', 'p_tp', 1), ('ob_02', 'AC', 'p_ac', 1),
    ('ob_02', 'AT', 'p_at', 1);
"""


def _golden2(conn):
    """Documents GOLDEN_2 dans un second référentiel N11 (une ligne par type
    et par référentiel)."""
    conn.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat) "
                 "VALUES ('R11B', 'N11', '2027', 'en_cours')")
    for i, (t, _, o) in enumerate(GOLDEN_2, start=1):
        conn.execute("INSERT INTO referentiel_documents (id, referentiel_id, type_document, "
                     "options, ordre) VALUES (?, 'R11B', ?, ?, ?)",
                     (f"rg{i}", t, json.dumps(o), i))
    conn.commit()


def _tex(conn, ref_id: str, type_doc: str, cible_id: str) -> str:
    """Comme tex_cycle4 (v0.52.1), pour un référentiel donné."""
    if ref_id == "R11":
        return tex_cycle4(conn, type_doc, cible_id)
    from services import orchestrateur_compilation as orch
    from services.referentiel_documents_compilation import lister_cibles_document
    doc_id, opts = conn.execute("SELECT id, options FROM referentiel_documents WHERE "
                                "referentiel_id=? AND type_document=?",
                                (ref_id, type_doc)).fetchone()
    cible = next(c for c in lister_cibles_document(conn, doc_id, ref_id, type_doc)
                 if c["cible_id"] == cible_id)
    cible = {**cible, "referentiel_id": ref_id, "gabarit": gd.gabarit_du_referentiel(conn, ref_id)}
    return orch.REGISTRE[type_doc](conn, cible, json.loads(opts), [], ["booktabs", "varwidth"])


@pytest.fixture
def app_c4p(data_dir):
    """Cycle 4 des tests v0.52.1 + atomes EV/TP/AC/AT reliés à ob_02."""
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as c:
        peupler_cycle4(c)
        _golden2(c)
        c.executescript(SQL_PARASITES)
        c.commit()
    return app


# Évaluation de 6e (deux exercices EV reliés à leur objectif, un bonus sans
# objectif), un travail personnel, une activité complémentaire n°2, une
# séance d'atelier, une archive X.
SQL_SIXIEME_DOCS = SQL_SIXIEME + r"""
INSERT INTO exercices (id, serie, titre, niveau, sequence, num, serie_code, fichier, enonce,
                       corrige, remed_enonce, remed_corrige) VALUES
    ('ev1', 'évaluation', 'Valeur des chiffres', 'N09', 'S01', 1, 'EV', '',
     'Sujet A1 \seqACompleter{3}.', '', '% titre B : Valeur des chiffres de 73
Sujet B1 \seqACompleter{7}.', ''),
    ('ev2', 'évaluation', 'Grands nombres', 'N09', 'S01', 2, 'EV', '', 'Sujet A2.',
     'Explication A2.', 'Sujet B2.', ''),
    ('ev3', 'évaluation', 'Bonus : Qui suis-je ?', 'N09', 'S01', 3, 'EV', '', 'Bonus A.', '',
     'Bonus B.', ''),
    ('tp1', 'travail personnel', 'Travail personnel n°1', 'N09', 'S01', 1, 'TP', '',
     '\seqTitreTravailSix{Travail personnel n°1}{Titre}{Séquence 1} Contenu TP \seqACompleter{x}.',
     '', '', ''),
    ('ac2', 'activité complémentaire', 'Le mur', 'N09', 'S01', 2, 'AC', '',
     '\seqTitreComplementSix{Le mur}{S01} Mur.', 'Explication AC.', '', ''),
    ('at1', 'séance d''atelier', 'Zooms', 'N09', 'S01', 1, 'AT', '', 'Séance.', '', '', ''),
    ('tpx', 'travail personnel', 'Archive', 'N09', 'X02', 1, 'TP', '', 'Vieux.', '', '', '');
INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) VALUES
    ('o602', 'EV', 'ev1', 1), ('o603', 'EV', 'ev2', 1),
    ('o602', 'TP', 'tp1', 1), ('o603', 'TP', 'tp1', 1), ('o603', 'AC', 'ac2', 1),
    ('o602', 'AT', 'at1', 1);
INSERT INTO evaluations (id, niveau, numero, ordre, titre, mode_notation)
    VALUES ('E6', 'N09', 1, 1, 'Évaluation --- Nombres', 'note_criteres');
INSERT INTO evaluation_exercices (evaluation_id, exercice_id, ordre, bareme_points) VALUES
    ('E6', 'ev1', 1, 5.0), ('E6', 'ev2', 2, 3.0), ('E6', 'ev3', 3, 2.0);
INSERT INTO evaluation_objectifs (evaluation_id, objectif_id) VALUES ('E6', 'o602'), ('E6', 'o603');
"""


@pytest.fixture
def app_6e(data_dir):
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as c:
        c.executescript(SQL_SIXIEME_DOCS)
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, gabarit_documents) "
                  "VALUES ('R09', 'N09', '2026', 'en_cours', 'sixieme')")
        c.commit()
    return app


# ── 1. Cycle 4 : exactement le même .tex qu'avant ────────────────────────────

@pytest.mark.parametrize("dossier,type_doc,cible_id", (
    [(DONNEES_0521, f"cycle4_{t}.tex", ("R11", t, cid)) for t, cid, _ in GOLDEN]
    + [(DONNEES, f"cycle4b_{t}.tex", ("R11B", t, cid)) for t, cid, _ in GOLDEN_2]))
def test_cycle4_meme_tex_qu_avant_meme_avec_des_documents_relies_au_cycle4_car_les_listes_de_series_sont_fermees(
        app_c4p, dossier, type_doc, cible_id):
    """Liste fermée de séries : livret de séquence (plan de travail et
    numérotation compris), recueil d'exercices, corrigés, livret de cours,
    livret de fiches et évaluation du cycle 4 produisent au caractère près
    le .tex de la v0.52.1, même quand des atomes EV, TP, AC, AT sont reliés
    à un objectif du cycle 4."""
    ref_id, t, cid = cible_id
    attendu = (dossier / type_doc).read_text(encoding="utf-8")
    with app_c4p.json_store._conn() as c:
        tex = _tex(c, ref_id, t, cid)
    assert "PARASITE" not in tex
    assert tex == attendu


def test_numerotation_et_plan_de_travail_ignorent_les_series_documents(app_c4p):
    from services.livret_plans_de_travail import _lire_objectifs_de_partie
    from services.numerotation_livret import numeroter_sequence
    with app_c4p.json_store._conn() as c:
        n = numeroter_sequence(c, "sn_n11_s01")
        tous = {i for lst in n.ordre.values() for i in lst}
        assert not tous & {"p_ev", "p_tp", "p_ac", "p_at"}
        o = [x for x in _lire_objectifs_de_partie(c, "pt_p1") if x["code"] == "02"][0]
        assert (o["exos_F"], o["exos_A"], o["exos_E"]) == ([1], [1], [1])


def test_figeage_et_revision_ignorent_les_series_documents(app_c4p):
    """La trace de figeage (format d'échange) ne liste que les exercices du
    livret ; on ne pioche pas un document en révision."""
    from services.referentiel_figeage import _trace_exos_de_objectif
    from services.v2_edition import lister_exos_disponibles_pour_revision
    with app_c4p.json_store._conn() as c:
        assert {x["titre"] for x in _trace_exos_de_objectif(c, "ob_02")} == {"F1", "A1", "E1"}
        assert {x["serie_code"] for x in lister_exos_disponibles_pour_revision(c, "N11", "S01")} \
            == {"F", "A", "E", "AE"}


def test_tableau_de_bord_le_bonus_d_evaluation_n_est_pas_a_rattacher(app_6e):
    """Un exercice EV appartient à son évaluation : le bonus (sans objectif)
    n'est pas compté « non rattaché »."""
    from services.tableau_bord import atomes_non_rattaches_par_niveau
    with app_6e.json_store._conn() as c:
        n09 = [x for x in atomes_non_rattaches_par_niveau(c) if x["niveau"] == "N09"][0]
    # Seul l'ancien TP d'archive (X02, sans lien) reste « à rattacher ».
    assert n09["par_type"]["exercice"] == 1


def test_livret_6e_ne_reprend_aucune_serie_document(app_6e):
    from services.livret_sequence_6e import generer_livret_sequence_6e
    with app_6e.json_store._conn() as c:
        tex = generer_livret_sequence_6e(c, "N09", "S01")
    for x in ("Sujet A1", "Contenu TP", "Mur.", "Séance."):
        assert x not in tex


# ── 2. Série EV : sujet B dans la remédiation, validation ────────────────────

def test_series_documents_creees_par_l_atelier_avec_leur_code(app_6e):
    from services import atomes
    liste, ex, err = atomes.creer_exercice([], {"serie": "évaluation", "niveau": "N09",
                                               "sequence": "S01"})
    assert err is None and ex["serie_code"] == "EV" and ex["num"] == 1
    for lib, code in (("travail personnel", "TP"), ("activité complémentaire", "AC"),
                      ("séance d'atelier", "AT")):
        assert atomes.creer_exercice([], {"serie": lib})[1]["serie_code"] == code


def test_validation_document_sans_corrige_car_les_reponses_sont_dans_l_enonce(app_6e):
    """V1 : EV, TP, AC, AT se corrigent par \\seqVersionCorrigee ; le
    corrigé est facultatif, mais une évaluation exige son sujet B. Les
    autres séries gardent la règle d'or (corrigé obligatoire)."""
    from services.atomes import _valider_exercice_hook
    from services.etats_edition import ValidationPedagogiqueErreur
    with app_6e.json_store._conn() as c:
        _valider_exercice_hook(c, "ev1")
        _valider_exercice_hook(c, "tp1")
        c.execute("UPDATE exercices SET remed_enonce='' WHERE id='ev3'")
        with pytest.raises(ValidationPedagogiqueErreur):
            _valider_exercice_hook(c, "ev3")
        with pytest.raises(ValidationPedagogiqueErreur):
            _valider_exercice_hook(c, "f2")            # F sans corrigé : refusé


def test_api_lien_objectif_accepte_les_series_documents(app_6e):
    from services.v2_edition import SerieInvalide, ajouter_exo_a_objectif
    with app_6e.json_store._conn() as c:
        r = ajouter_exo_a_objectif(c, "o603", "AT", "at1")
        assert [e["exercice_id"] for e in r["exos"]] == ["at1"]
        with pytest.raises(SerieInvalide):
            ajouter_exo_a_objectif(c, "o603", "R", "at1")


# ── 3. Évaluation au gabarit 6e ──────────────────────────────────────────────

def _eval6e(app, **opts):
    from services.render_evaluation import generer_tex_evaluation
    with app.json_store._conn() as c:
        return generer_tex_evaluation(c, "E6", gabarit="sixieme", options=opts)


def test_evaluation_6e_bareme_par_competence_somme_des_points_par_objectif(app_6e):
    """E1 : chaque exercice vise l'objectif de l'évaluation auquel il est
    relié ; barème par compétence = somme par objectif. B1 : le bonus (sans
    objectif) a sa colonne et ne compte pas dans le total."""
    tex = _eval6e(app_6e)
    assert r"\seqBaremeCompetences{S01-02/{5},S01-03/{3},Bonus/{2}}{8}" in tex
    assert r"\seqExoEval{Valeur des chiffres}{5 pts --- S01-02}" in tex
    assert r"\seqExoEval{Grands nombres}{3 pts --- S01-03}" in tex
    assert r"\seqExoEval{Bonus : Qui suis-je ?}{2 pts --- bonus}" in tex
    assert "Le bonus s'ajoute dans la limite de 8." in tex
    assert r"\seqTitreEvalSix{Évaluation --- Nombres}{Séquence 1 --- Sujet A --- " \
           r"calculatrice interdite}" in tex
    assert r"\seqIdentEleve" in tex and r"\seqVersionCorrigee" not in tex
    assert "Sujet A1" in tex and "Sujet B1" not in tex


def test_evaluation_6e_sujet_b_vient_de_la_remediation_avec_son_titre(app_6e):
    """E3 : sujet B = remed_enonce ; la ligne « % titre B : … » donne le
    titre propre au sujet B (S01 : nombre différent dans le titre)."""
    tex = _eval6e(app_6e, sujet="B", version="corrigee")
    assert r"\seqExoEval{Valeur des chiffres de 73}{5 pts --- S01-02}" in tex
    assert "Sujet B1" in tex and "Sujet A1" not in tex and "% titre B" not in tex
    assert "Sujet B" in tex and r"\seqVersionCorrigee" in tex


def test_evaluation_6e_explication_et_mention_calculatrice(app_6e):
    tex = _eval6e(app_6e, calculatrice="autorisee")
    assert r"\seqLocExplication{Explication A2.}" in tex
    assert "calculatrice autorisée" in tex
    assert "calculatrice" not in _eval6e(app_6e, calculatrice="non_precisee").split(
        r"\begin{document}")[1].split(r"\seqBaremeCompetences")[0]


def test_evaluation_6e_une_seule_geometrie_celle_du_module_6e(app_6e):
    tex = _eval6e(app_6e)
    preambule = tex.split(r"\begin{document}")[0]
    assert preambule.count(r"\geometry{") == 1 and "left=35pt,right=35pt,top=50pt" in preambule
    assert r"\usepackage{seqenseigne-style6e}" in preambule


def test_evaluation_6e_option_invalide_refusee(app_6e):
    from services.render_evaluation import Evaluation6eErreur
    with pytest.raises(Evaluation6eErreur):
        _eval6e(app_6e, sujet="C")


def test_route_module_evaluations_n09_au_gabarit_6e(app_6e):
    """R1 partagé : N09 → gabarit 6e (sujet et version en paramètres)."""
    cl = app_6e.test_client()
    r = cl.get("/api/evaluations/E6/rendu-tex?sujet=B&version=corrigee")
    assert r.status_code == 200 and r"\seqTitreEvalSix" in r.get_data(as_text=True)
    assert "Sujet B" in r.get_data(as_text=True)
    assert cl.get("/api/evaluations/E6/rendu-tex?sujet=Z").status_code == 400


def test_route_module_evaluations_cycle4_meme_tex_qu_avant(app_c4p):
    """Une évaluation du cycle 4 garde son rendu : la route produit
    exactement l'appel historique (gabarit cycle 4, mêmes bibliothèques)."""
    from routes.evaluations import _configuration
    from services.render_evaluation import generer_tex_evaluation
    r4 = app_c4p.test_client().get("/api/evaluations/ev1/rendu-tex")
    with app_c4p.app_context():
        config = _configuration()
        with app_c4p.json_store._conn() as c:
            attendu = generer_tex_evaluation(c, "ev1", tikz_libraries=config.tikz_libraries(),
                                             tblr_libraries=config.tblr_libraries())
    assert r4.status_code == 200 and r4.get_data(as_text=True) == attendu
    assert r"\seqTitreEval[" in attendu


def test_module_evaluations_propose_les_ev_dont_le_bonus_sans_objectif(app_6e):
    cl = app_6e.test_client()
    d = cl.get("/api/evaluations/niveau/N09/exos-disponibles").get_json()
    ids = {e["id"] for lst in d["par_sequence"].values() for e in lst}
    assert {"ev1", "ev2", "ev3"} <= ids                 # ev3 : bonus, sans lien
    assert not ids & {"tp1", "ac2", "at1"}             # pas des exercices d'évaluation


# ── 4. Catalogue, cibles, documents TP / AC / AT ─────────────────────────────

def test_catalogue_sixieme_types_et_options_du_cadrage():
    t = gd.type_document("evaluation_6e")
    # v0.52.8 (C2) : « selon l'évaluation » remplace « interdite » par défaut.
    assert t.options == {"actif": False, "sujet": "A", "version": "eleve",
                         "calculatrice": "selon_evaluation"}
    for cle in ("travaux_personnels_6e", "activites_complementaires_6e", "seances_atelier_6e"):
        assert gd.type_document(cle).options == {"actif": False, "version": "eleve"}
        assert gd.gabarit_du_type(cle) == "sixieme"
    assert not set(gd.types("cycle4")) & {"evaluation_6e", "travaux_personnels_6e"}


def test_cibles_une_par_evaluation_et_par_document_terminees_par_la_sequence(app_6e):
    """Les cibles se terminent par « /S01 » (comme les livrets) pour être
    proposées côté classe avec la séquence ; les archives X ne sont jamais
    des cibles."""
    from services import referentiel_documents_compilation as rdc
    with app_6e.json_store._conn() as c:
        ev = rdc._cibles_evaluations_6e(c, "N09")
        assert [x["cible_id"] for x in ev] == ["EV01/N09/S01"]
        assert ev[0]["eval_id"] == "E6" and ev[0]["titre_doc"] == "Évaluation --- Nombres"
        tp = rdc._cibles_documents_6e(c, "N09", "travaux_personnels_6e")
        assert [x["cible_id"] for x in tp] == ["TP01/N09/S01"]
        assert [x["cible_id"] for x in rdc._cibles_documents_6e(
            c, "N09", "activites_complementaires_6e")] == ["AC02/N09/S01"]


def test_producteurs_6e_enregistres(app_6e):
    from services import orchestrateur_compilation as orch
    with app_6e.json_store._conn() as c:
        tex = orch.REGISTRE["evaluation_6e"](c, {"eval_id": "E6"}, {"sujet": "B"}, [], [])
        assert "Sujet B" in tex
        tex = orch.REGISTRE["travaux_personnels_6e"](c, {"exercice_id": "tp1"},
                                                     {"version": "corrigee"}, [], [])
        assert r"\seqTitreTravailSix" in tex and r"\seqVersionCorrigee" in tex


def test_activite_complementaire_garde_son_numero_dans_le_titre(app_6e):
    """D2 : \\seqTitreComplementSix numérote par compteur ; AC02 isolé doit
    afficher « Activité complémentaire 2 »."""
    from services.documents_6e import generer_document_6e
    with app_6e.json_store._conn() as c:
        tex = generer_document_6e(c, "ac2")
    corps = tex.split(r"\begin{document}")[1]
    assert corps.index(r"\setcounter{seqComplSix}{1}") < corps.index(r"\seqTitreComplementSix")
    assert r"\seqLocExplication{Explication AC.}" in corps


def test_document_6e_refuse_une_archive_et_une_serie_du_livret(app_6e):
    from services.documents_6e import Document6eErreur, generer_document_6e
    with app_6e.json_store._conn() as c:
        for i in ("tpx", "f1"):
            with pytest.raises(Document6eErreur):
                generer_document_6e(c, i)


def test_peremption_connait_les_types_6e():
    from services.peremption_atomes import ATOMES_PAR_TYPE_DOCUMENT
    for t in gd.types("sixieme"):
        assert t in ATOMES_PAR_TYPE_DOCUMENT


# ── 5. Côté classe : proposés avec la séquence, délai réglable ──────────────

def test_classe_propose_tp_et_evaluations_et_leur_donne_un_delai(app_6e):
    """Pas de nouvelle table : le délai (≈ 7 jours) se règle sur
    l'association (retour « à rendre », délai en jours)."""
    from services import progression_doc as pgd
    with app_6e.json_store._conn() as c:
        for i, t in enumerate(("travaux_personnels_6e", "evaluation_6e"), start=1):
            c.execute("INSERT INTO referentiel_documents (id, referentiel_id, type_document, "
                      "options, ordre) VALUES (?, 'R09', ?, '{\"actif\": true}', ?)",
                      (f"d{i}", t, i))
        c.execute("INSERT INTO etablissements (id, nom) VALUES ('et', 'Collège')")
        c.execute("INSERT INTO progressions (id, niveau, annee, etablissement_id, referentiel_id) "
                  "VALUES ('pg6', 'N09', '2026-2027', 'et', 'R09')")
        d = pgd.documents_disponibles(c, "N09", "2026-2027", "S01", prog_ref="pg6")
        refs = {x["doc_ref"]: x["libelle"] for x in d["sequence"] if x["source"] == "interne"}
        assert refs["travaux_personnels_6e|TP01/N09/S01"] == \
            "Travaux personnels — S01 : Travail personnel n°1"     # v0.52.4 (M1)
        assert "evaluation_6e|EV01/N09/S01" in refs
        a = pgd.ajouter(c, prog_kind="principale", prog_ref="pg6", creneau_ref="cr", rang_seance=2,
                        doc_source="interne", doc_ref="travaux_personnels_6e|TP01/N09/S01",
                        doc_libelle="TP1", retour="rendre", delai_type="jours", delai_n=7)
        assert (a["retour"], a["delai_type"], a["delai_n"]) == ("rendre", "jours", 7)
        assert pgd.delai_en_jours("jours", 7) == 7


# ── 6. Livret 6e : activité sous son objectif, une seule fois (L1) ──────────

def test_livret_6e_activite_reliee_a_son_objectif_affichee_une_fois_sous_son_bandeau(app_6e):
    """L1 : l'import garde le lien à la partie et ajoute le lien à
    l'objectif ; le livret ne montre l'activité que sous le bandeau."""
    from services.livret_sequence_6e import generer_livret_sequence_6e
    with app_6e.json_store._conn() as c:
        c.execute("INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) "
                  "VALUES ('o602', 'AE', 'a1', 1)")
        tex = generer_livret_sequence_6e(c, "N09", "S01")
    assert tex.count("Un sudoku") == 1
    assert tex.index(r"\seqBandeauCapacite{S01-02}") < tex.index("Un sudoku")


# ── 7. Import 6e en base ─────────────────────────────────────────────────────

from tests.test_v0_52_0_import_lot6e import (  # noqa: E402,F401
    _conn, _lot_s01, base, imp)

EVAL_A = (r"\setcounter{seqExoEval}{0}" "\n" r"\seqIdentEleve" "\n"
          r"\seqTitreEvalSix{Évaluation --- Nombres}{Séquence 1 --- Sujet A}" "\n"
          r"\seqBaremeCompetences{S01-02/5,S01-12/3,Bonus/2}{8}" "\n"
          r"\seqExoEval{Valeur des chiffres dans 45}{5 pts --- S01-02}" "\nÉnoncé A1.\n\n"
          r"\seqExoEval{Un quotient}{3 pts --- S01-12}" "\nÉnoncé A2.\n\n"
          r"\seqExoEval{Bonus : Qui suis-je ?}{2 pts --- S01-02}" "\nBonus A.")
EVAL_B = (EVAL_A.replace("Sujet A", "Sujet B").replace("dans 45", "dans 73")
          .replace("Énoncé A", "Énoncé B").replace("Bonus A.", "Bonus B."))


def _lot_eval(tmp_path, eval_b=EVAL_B, valide_tp=False):
    d = _lot_s01(tmp_path / "lots")
    f = d / "S01" / "S01.json"
    lot = json.loads(f.read_text(encoding="utf-8"))
    bareme = [["S01-02", 5], ["S01-12", 3], ["Bonus", 2]]
    lot["evaluations"] = [
        {"titre": "Évaluation --- Nombres", "sujet": "A", "bareme": bareme, "total": 8,
         "latex": EVAL_A, "origine": "26S2evA"},
        {"titre": "Évaluation --- Nombres", "sujet": "B", "bareme": bareme, "total": 8,
         "latex": eval_b, "origine": "26S2evB"}]
    lot["travaux_personnels"].append({"titre": "Travail personnel n°2", "latex": "TP2",
                                      "objectifs": ["S01-12", "S01-02"]})
    lot["seances_atelier"] = [{"titre": "Atelier", "latex": "AT1", "objectifs": ["S01-12"],
                               "apres_objectif": "S01-12"}]
    f.write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")
    return d


def _appliquer(db, lots):
    assert imp.main(["--db", str(db), "--lots", str(lots), "--apply", "--yes"]) == 0


def test_import_documents_tp_ac_at_un_atome_par_document_relie_a_ses_objectifs(base, tmp_path):
    lots = _lot_eval(tmp_path)
    _appliquer(base, lots)
    c = _conn(base)
    docs = c.execute("SELECT serie_code, num, serie, titre, enonce, etat_code FROM exercices "
                     "WHERE niveau='N09' AND sequence='S01' AND serie_code IN ('TP','AC','AT') "
                     "ORDER BY serie_code, num").fetchall()
    assert [(r[0], r[1], r[2]) for r in docs] == [
        ("AC", 1, "activité complémentaire"), ("AT", 1, "séance d'atelier"),
        ("TP", 1, "travail personnel"), ("TP", 2, "travail personnel")]
    assert {r[5] for r in docs} == {"en_cours"}
    liens = c.execute("SELECT o.code, oe.serie, e.num FROM objectif_exos oe JOIN exercices e ON "
                      "e.id=oe.exercice_id JOIN objectifs o ON o.id=oe.objectif_id WHERE "
                      "oe.serie='TP' ORDER BY o.code, oe.ordre").fetchall()
    assert [tuple(r) for r in liens] == [("02", "TP", 1), ("02", "TP", 2), ("12", "TP", 2)]


def test_import_evaluation_sujet_a_dans_l_enonce_sujet_b_dans_la_remediation(base, tmp_path):
    """Évaluation « note et critères » : barème par exercice, objectifs
    évalués ; EV reliés à leur objectif sauf le bonus (B1) ; titre propre
    au sujet B gardé (E3)."""
    lots = _lot_eval(tmp_path)
    _appliquer(base, lots)
    c = _conn(base)
    ev = c.execute("SELECT * FROM evaluations WHERE niveau='N09'").fetchall()
    assert len(ev) == 1 and ev[0]["mode_notation"] == "note_criteres"
    assert ev[0]["etat_code"] == "en_cours"
    exos = c.execute("SELECT e.num, e.titre, e.enonce, e.corrige, e.remed_enonce, ee.bareme_points "
                     "FROM evaluation_exercices ee JOIN exercices e ON e.id=ee.exercice_id "
                     "WHERE ee.evaluation_id=? ORDER BY ee.ordre", (ev[0]["id"],)).fetchall()
    assert [(r[0], r[5]) for r in exos] == [(1, 5.0), (2, 3.0), (3, 2.0)]
    assert exos[0]["enonce"] == "Énoncé A1." and exos[0]["corrige"] == ""
    assert exos[0]["remed_enonce"] == "% titre B : Valeur des chiffres dans 73\nÉnoncé B1."
    assert exos[1]["remed_enonce"] == "Énoncé B2."
    objs = {r[0] for r in c.execute("SELECT o.code FROM evaluation_objectifs eo JOIN objectifs o "
                                    "ON o.id=eo.objectif_id WHERE eo.evaluation_id=?",
                                    (ev[0]["id"],))}
    assert objs == {"02", "12"}
    liens = c.execute("SELECT e.num, o.code FROM objectif_exos oe JOIN exercices e ON "
                      "e.id=oe.exercice_id JOIN objectifs o ON o.id=oe.objectif_id WHERE "
                      "oe.serie='EV' ORDER BY e.num").fetchall()
    assert [tuple(r) for r in liens] == [(1, "02"), (2, "12")]      # bonus : aucun lien
    from services.render_evaluation import (corps_evaluation_6e, options_evaluation_6e,
                                            structure_evaluation_6e)
    tex = "\n".join(corps_evaluation_6e(c, structure_evaluation_6e(c, ev[0]["id"]),
                                         options_evaluation_6e({"sujet": "B"})))
    assert r"\seqBaremeCompetences{S01-02/{5},S01-12/{3},Bonus/{2}}{8}" in tex
    assert r"\seqExoEval{Valeur des chiffres dans 73}{5 pts --- S01-02}" in tex


def test_import_evaluation_idempotent_et_evaluation_validee_intouchee(base, tmp_path):
    lots = _lot_eval(tmp_path)
    _appliquer(base, lots)
    tables = ("exercices", "objectif_exos", "evaluations", "evaluation_exercices",
              "evaluation_objectifs")
    from tests.test_v0_52_0_import_lot6e import _dump
    etat = _dump(base, tables)
    _appliquer(base, lots)
    assert _dump(base, tables) == etat
    c = _conn(base)
    c.execute("UPDATE evaluations SET etat_code='valide'")
    c.execute("DELETE FROM evaluation_objectifs")
    c.commit()
    c.close()
    r = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                          base.parent / "images")
    assert any("validée dans le module Évaluations" in a for a in r.anomalies)
    _appliquer(base, lots)
    assert _conn(base).execute("SELECT COUNT(*) FROM evaluation_objectifs").fetchone()[0] == 0


def test_import_evaluation_au_decoupage_impossible_signalee_et_non_importee(base, tmp_path):
    """Sujets A et B de structures différentes : anomalie, rien d'importé."""
    lots = _lot_eval(tmp_path, eval_b=EVAL_B.replace("3 pts --- S01-12", "4 pts --- S01-12"))
    r = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                          base.parent / "images")
    assert any("non importée : découpage impossible" in a and "exercice 2" in a
               for a in r.anomalies)
    _appliquer(base, lots)
    c = _conn(base)
    assert c.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM exercices WHERE serie_code='EV'").fetchone()[0] == 0


def test_import_bareme_du_lot_controle_contre_les_exercices():
    lot_a = {"latex": EVAL_A, "bareme": [["S01-02", 6], ["S01-12", 2], ["Bonus", 2]]}
    with pytest.raises(imp.ImportErreur):
        imp.preparer_evaluation("x", {"A": lot_a, "B": {"latex": EVAL_B}})
    ok = imp.preparer_evaluation("x", {"A": {"latex": EVAL_A, "bareme": [
        ["S01-02", 5], ["S01-12", 3], ["Bonus", 2]]}, "B": {"latex": EVAL_B}})
    assert [x["bonus"] for x in ok] == [False, False, True]


def test_import_activites_reliees_a_leur_objectif_et_a_la_partie(base, tmp_path):
    """L1 : lien objectif (série AE) ajouté, lien partie (EA) gardé pour la
    numérotation et le plan de travail."""
    lots = _lot_eval(tmp_path)
    _appliquer(base, lots)
    c = _conn(base)
    ae = c.execute("SELECT o.code, e.num FROM objectif_exos oe JOIN exercices e ON "
                   "e.id=oe.exercice_id JOIN objectifs o ON o.id=oe.objectif_id WHERE "
                   "oe.serie='AE' ORDER BY e.num").fetchall()
    assert [tuple(r) for r in ae] == [("02", 1), ("02", 2), ("12", 3)]
    assert c.execute("SELECT COUNT(*) FROM partie_exos_revision_approche WHERE type='EA'"
                     ).fetchone()[0] == 3


def test_import_options_tex_retirees_proprement():
    """O1 : plus de --sortie ni --documents-seulement (les documents vont en
    base) ; l'aide ne les propose plus."""
    import subprocess
    r = subprocess.run([sys.executable, str(Path(imp.__file__)), "--help"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0
    assert "--documents-seulement" not in r.stdout and "--sortie" not in r.stdout
