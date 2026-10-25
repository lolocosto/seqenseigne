"""tests/test_v0_53_0_mises_en_route.py — v0.53.0

1. Anomalie du 21 octobre (B1) : rendu par lot refusé en 6e (« niveau
   invalide : 'N09' ») ; fiche de résumé au modèle « Fiches » (B2).
2. Mises en route de 6e au modèle « Fiches » (décisions MR1 à MR7,
   doc/redemarrage_v0_53_0.md) : import des lots Mnn (I-MR1 à I-MR6),
   documents (fiche de cours, exercices de séance 2/3/4 par A4, test court,
   plan de séquence), validation, exclusivité avec le principal.

Base de test reconstruite à chaque test (jamais de base réelle) ; lot M01
de test : tests/donnees_v0_53_0/lot6e/M01/M01.json (8 séances).

v0.53.1 (changement voulu, décisions du 22 octobre 2026) : le format des lots
de mise en route passe en version 2 (une partie par objectif, codes M01-02,
M01-12…, une fiche de cours et un test court par partie) ; ces tests lisent le
même jeu de test, au format v2 : tests/donnees_v0_53_1/lot6e/M01/M01.json.
Nouvelles décisions : tests/test_v0_53_1_mer_parties.py.
"""

from __future__ import annotations

import copy
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from app import create_app
from outils import import_lot6e as imp
from outils import import_lot6e_mer as imp_mer
from services import mises_en_route_6e as mer
from services.cycle_import import importer_cycle

APPLI = Path(__file__).resolve().parent.parent
DATA = APPLI / "data"
LOT_M01 = Path(__file__).resolve().parent / "donnees_v0_53_1" / "lot6e" / "M01" / "M01.json"


# ── Base et lot ──────────────────────────────────────────────────────────────

# Index du paquet vide (les générateurs de .tex le lisent ; cf. v0.52.1).
SQL_PAQUET = r"""
CREATE TABLE IF NOT EXISTS paquet_definitions (
    nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT,
    corps TEXT, corps_fin TEXT, texte_complet TEXT,
    fichier_source TEXT, ligne_debut INTEGER,
    macros_appelees TEXT, environnements_utilises TEXT,
    statut_rendu_atome TEXT DEFAULT 'reutilise',
    contenu_atome TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS paquet_requirepackage (
    fichier_source TEXT NOT NULL, ordre INTEGER NOT NULL, nom TEXT NOT NULL,
    options TEXT NOT NULL DEFAULT '', PRIMARY KEY (fichier_source, ordre));
"""

@pytest.fixture
def base(tmp_path):
    d = tmp_path / "data_atelier"
    d.mkdir()
    for f in list(DATA.glob("C0*_*.csv")) + [DATA / "param_niveaux.csv"]:
        shutil.copy(f, d)
    create_app(d, profil="atelier")
    db = d / "seqenseigne.db"
    c = sqlite3.connect(db)
    for cy in ("C03", "C04"):
        importer_cycle(c, cy, "Cycle", d / f"{cy}_themes.csv", d / f"{cy}_sequences.csv")
    c.executescript(SQL_PAQUET)
    c.commit()
    c.close()
    return db


def _lot() -> dict:
    return json.loads(LOT_M01.read_text(encoding="utf-8"))


def _ecrire_lot(dossier: Path, lot: dict) -> Path:
    d = dossier / lot["sequence"]
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{lot['sequence']}.json").write_text(json.dumps(lot, ensure_ascii=False),
                                               encoding="utf-8")
    return dossier


@pytest.fixture
def lots(tmp_path):
    return _ecrire_lot(tmp_path / "lots", _lot())


def _appliquer(db, lots_dir):
    assert imp.main(["--db", str(db), "--lots", str(lots_dir), "--apply", "--yes"]) == 0


def _essai(db, lots_dir):
    return imp.essai_a_blanc(Path(db), imp.charger_lots(lots_dir), imp.charger_referentiel(),
                             Path(db).parent / "images")


def _conn(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


def _dump(db) -> list:
    c = sqlite3.connect(db)
    out = []
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        out.append((t, sorted(map(repr, c.execute(f'SELECT * FROM "{t}"')))))
    c.close()
    return out


# ── 1. Rendu par lot (B1) et fiche au modèle « Fiches » (B2) ────────────────

@pytest.fixture
def client(base):
    app = create_app(base.parent, profil="atelier")
    return app.test_client()


def test_rendu_par_lot_accepte_N09_car_le_filtre_refusait_la_6e_le_21_octobre(client):
    r = client.get("/api/admin/compilation-atomes/preview?niveau=N09")
    assert r.status_code == 200, r.get_json()
    assert "total" in r.get_json()


def test_rendu_par_lot_accepte_les_sequences_de_mise_en_route_et_d_archive(client):
    for seq in ("S01", "M01", "X03"):
        r = client.get(f"/api/admin/compilation-atomes/preview?niveau=N09&sequence={seq}")
        assert r.status_code == 200, (seq, r.get_json())


def test_rendu_par_lot_refuse_toujours_un_niveau_ou_une_sequence_inconnus(client):
    assert client.get("/api/admin/compilation-atomes/preview?niveau=N99").status_code == 400
    assert client.get("/api/admin/compilation-atomes/preview?sequence=S1").status_code == 400
    assert client.get("/api/admin/compilation-atomes/preview?sequence=Z01").status_code == 400


def test_niveaux_valides_viennent_aussi_de_param_niveaux_pour_ne_plus_coder_la_liste_en_dur(base):
    from services.compilation_batch import niveaux_valides, sequence_valide
    c = sqlite3.connect(base)
    assert {"N09", "N10", "N11", "N12", "N08"} <= set(niveaux_valides(c))
    assert niveaux_valides(None) == ("N09", "N10", "N11", "N12")
    assert sequence_valide("M07") and sequence_valide("S14") and not sequence_valide("M7")


def test_fiche_de_resume_N09_rendue_au_modele_fiches_comme_les_fiches_de_cours(base, lots):
    _appliquer(base, lots)
    from services.latex_rendu_atome import generer_tex_par_type
    c = _conn(base)
    fid = c.execute("SELECT id FROM fiches_resume WHERE sequence='M01'").fetchone()[0]
    tex = generer_tex_par_type(c, "fiche", fid)
    assert r"\begin{seqFicheResumeSix}" in tex and r"\seqVersionComplete" in tex
    assert "Mise en route 1 --- Calcul mental" in tex
    tex_e = generer_tex_par_type(c, "fiche", fid, options={"version": "eleve"})
    assert r"\seqVersionComplete" not in tex_e


def test_fiche_du_cycle4_rendue_comme_avant_car_le_crochet_B2_est_reserve_au_modele_fiches(base):
    from services import fiches_resume as svc
    from services.latex_rendu_atome import generer_tex_atome, generer_tex_par_type
    c = _conn(base)
    c.execute("INSERT INTO sequences_par_niveau (id, niveau, sequence_code) VALUES "
              "('sn10', 'N10', 'S01')")
    c.execute("INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero) VALUES "
              "('pt10', 'sn10', 1)")
    c.execute("INSERT INTO objectifs (id, partie_id, code, nom) VALUES ('ob10', 'pt10', '02', 'x')")
    f = svc.creer_fiche(c, objectif_id="ob10", titre="Fiche 5e",
                        sections=[{"titre": "A", "items": ["texte"]}])
    assert generer_tex_par_type(c, "fiche", f["id"]) == generer_tex_atome(c, "fiche", f["id"])


# ── 2. Référentiel et import des mises en route ─────────────────────────────

def test_referentiel_mer_transcrit_ref6e_v2_7_sequences_25_objectifs_131_seances():
    ref = imp_mer.referentiel_mer()
    assert sorted(ref) == [f"M0{i}" for i in range(1, 8)]
    objs = [o for s in ref.values() for o in s["objectifs"]]
    assert len(objs) == 25
    assert sum(o["seances"] for o in objs) == 131
    assert sum(s["exercices"] for s in ref.values()) == 131
    assert ref["M01"]["nom"] == "Calcul mental" and ref["M01"]["theme"] == "A"
    assert ref["M05"]["objectifs"][0]["seances"] == 6           # suite après « (6 séances) ; »


def test_import_mer_essai_a_blanc_n_ecrit_rien(base, lots):
    avant = _dump(base)
    r = _essai(base, lots)
    assert "M01" in r.sequences
    assert _dump(base) == avant


def test_import_mer_idempotent_car_le_second_apply_ne_change_rien(base, lots):
    _appliquer(base, lots)
    une = _dump(base)
    _appliquer(base, lots)
    assert _dump(base) == une


def test_import_mer_cree_une_sequence_Mnn_sans_objectif_cours_car_la_fiche_est_de_sequence(base,
                                                                                         lots):
    _appliquer(base, lots)
    c = _conn(base)
    sc = c.execute("SELECT numero, nom FROM sequences_du_cycle WHERE cycle_code='C03' AND "
                   "code='M01'").fetchone()
    assert tuple(sc) == (201, "Calcul mental")
    objs = c.execute("SELECT o.code, o.nom, o.nb_seances, o.critere_F, p.numero FROM objectifs o "
                     "JOIN sequence_parties p ON p.id=o.partie_id JOIN sequences_par_niveau s "
                     "ON s.id=p.sequence_par_niveau_id WHERE s.niveau='N09' AND "
                     "s.sequence_code='M01' ORDER BY o.code").fetchall()
    assert [o["code"] for o in objs] == ["02", "12", "22", "32"]          # v0.53.1
    assert [o["numero"] for o in objs] == [1, 2, 3, 4]
    assert all(o["nb_seances"] == 6 for o in objs)
    assert objs[0]["nom"] == "Utiliser les tables de multiplication jusqu'à la table de 12"
    assert objs[0]["critere_F"].startswith("Donne 4 produits")
    fiches = c.execute("SELECT objectif_id, titre FROM fiches_resume WHERE sequence='M01' "
                       "ORDER BY num_fiche").fetchall()
    assert [(f[0], f[1]) for f in fiches] == [(None, "Tables de multiplication"),
                                              (None, "Compléments entiers"),
                                              (None, "Complément décimal à 1"),
                                              (None, "Arrondis")]                # v0.53.1


def test_import_mer_exercices_de_seance_serie_MR_numerotes_par_seance_et_relies_a_l_objectif(base,
                                                                                            lots):
    _appliquer(base, lots)
    c = _conn(base)
    rows = c.execute("SELECT e.num, e.serie, e.calculatrice, o.code FROM exercices e JOIN "
                     "objectif_exos oe ON oe.exercice_id=e.id AND oe.serie='MR' JOIN objectifs o "
                     "ON o.id=oe.objectif_id WHERE e.sequence='M01' AND e.serie_code='MR' "
                     "ORDER BY e.num").fetchall()
    assert [r[0] for r in rows] == list(range(1, 9))
    assert {r[1] for r in rows} == {"mise en route"} and {r[2] for r in rows} == {"interdite"}
    assert [r[3] for r in rows] == ["02", "02", "12", "12", "22", "22", "32", "32"]


def test_import_mer_test_court_dans_le_module_evaluations_avec_sujets_A_et_B(base, lots):
    _appliquer(base, lots)
    c = _conn(base)
    ev = c.execute("SELECT id, titre, calculatrice FROM evaluations WHERE niveau='N09'").fetchall()
    assert len(ev) == 4 and ev[0]["titre"] == "Test court --- Tables de multiplication"
    exos = c.execute("SELECT e.serie_code, e.sequence, e.remed_enonce <> '' FROM "
                     "evaluation_exercices ee JOIN exercices e ON e.id=ee.exercice_id "
                     "WHERE ee.evaluation_id=?", (ev[0]["id"],)).fetchall()
    assert [tuple(x) for x in exos] == [("EV", "M01", 1), ("EV", "M01", 1)]


def test_import_mer_ne_reecrit_jamais_un_exercice_valide(base, lots, tmp_path):
    _appliquer(base, lots)
    c = _conn(base)
    c.execute("UPDATE exercices SET etat_code='valide' WHERE sequence='M01' AND serie_code='MR' "
              "AND num=1")
    c.commit()
    lot = _lot()
    lot["exercices_seance"][0]["titre"] = "Titre changé"
    r = _essai(base, _ecrire_lot(tmp_path / "l2", lot))
    assert any("MR01 validé" in a for a in r.anomalies)
    _appliquer(base, tmp_path / "l2")
    assert c.execute("SELECT titre FROM exercices WHERE sequence='M01' AND serie_code='MR' AND "
                     "num=1").fetchone()[0] == "Tables de 2 à 5"


def test_import_mer_seance_qui_change_d_objectif_perd_son_ancien_lien(base, lots, tmp_path):
    _appliquer(base, lots)
    lot = _lot()
    lot["exercices_seance"][0]["objectif"] = "M01-12"
    _appliquer(base, _ecrire_lot(tmp_path / "l2", lot))
    c = _conn(base)
    codes = [r[0] for r in c.execute(
        "SELECT o.code FROM objectif_exos oe JOIN objectifs o ON o.id=oe.objectif_id JOIN "
        "exercices e ON e.id=oe.exercice_id WHERE e.sequence='M01' AND e.num=1 AND "
        "e.serie_code='MR' AND oe.serie='MR'")]
    assert codes == ["12"]


def test_import_mer_version_complete_redigee_a_part_puis_retiree_si_le_lot_n_en_a_plus(base, lots,
                                                                                       tmp_path):
    lot = _lot()
    fc = lot["parties"][0]["fiche_cours"]
    fc["latex_corrige"] = fc["latex"].replace(r"\seqACompleter{56}", "56")
    _appliquer(base, _ecrire_lot(tmp_path / "l2", lot))
    c = _conn(base)
    s = mer.lire_sequence_mer(c, "N09", "M01")
    assert s["fiche"]["titre"] == "Tables de multiplication"
    assert s["fiche_complete"]["titre"] == "Tables de multiplication" + mer.SUFFIXE_COMPLETE
    tex = mer.generer_document_mer(c, "N09", "M01", {"document": "fiche_cours",
                                                      "version": "corrigee", "partie": 1})
    assert r"\seqACompleter{56}" not in tex and "{Tables de multiplication}" in tex
    c.close()
    _appliquer(base, lots)
    c = _conn(base)
    assert mer.lire_sequence_mer(c, "N09", "M01")["fiche_complete"] is None


def test_import_mer_note_de_corrige_dans_la_fiche_visible_en_version_complete_seulement(base,
                                                                                        tmp_path):
    lot = _lot()
    lot["parties"][0]["fiche_cours"]["latex_corrige"] = "Mots à compléter : 56 ; 63 ; 4."
    _appliquer(base, _ecrire_lot(tmp_path / "l2", lot))
    c = _conn(base)
    s = mer.lire_sequence_mer(c, "N09", "M01")
    assert s["fiche_complete"] is None
    assert s["fiche"]["sections"][-1] == {
        **s["fiche"]["sections"][-1], "titre": "",
        "items": [r"\seqLocExplication{Mots à compléter : 56 ; 63 ; 4.}"]}
    tex = mer.generer_document_mer(c, "N09", "M01", {"document": "fiche_cours", "partie": 1})
    assert r"\seqLocExplication{Mots à compléter" in tex and r"\seqVersionComplete" not in tex


def test_import_mer_signale_format_macros_locales_objectif_inconnu_et_total(base, tmp_path):
    lot = _lot()
    lot["macros_locales"] = r"\newcommand{\seqLocX}{x}"
    lot["exercices_seance"][1]["objectif"] = "M01-09"
    for ev in lot["evaluations"]:
        ev["total"] = 20
    r = _essai(base, _ecrire_lot(tmp_path / "l", lot))
    txt = "\n".join(r.anomalies)
    assert "seqLocX, absente(s) du module" in txt
    assert "objectif 'M01-09' inconnu" in txt
    assert "un test court est sur 10" in txt
    mauvais = {"sequence": "M02", "titre": "x"}
    r = _essai(base, _ecrire_lot(tmp_path / "l3", mauvais))
    assert any("non conforme" in a for a in r.anomalies)


def test_import_mer_reconnait_les_etiquettes_Mnn_des_tests_courts():
    assert imp.RE_ETIQUETTE_EVAL.match("5 pts --- M01-02")
    assert imp.RE_ETIQUETTE_EVAL.match("5 pts --- S01-02")


def test_charger_lots_range_les_mises_en_route_apres_les_sequences(tmp_path):
    for code in ("M01", "S02", "S01"):
        _ecrire_lot(tmp_path, {"sequence": code})
    assert [l["sequence"] for l in imp.charger_lots(tmp_path)] == ["S01", "S02", "M01"]


# ── 3. Validation (MR6) ─────────────────────────────────────────────────────

def test_validation_mer_complete_avec_avertissement_seulement_sur_le_nombre_de_seances(base, lots):
    _appliquer(base, lots)
    v = mer.valider_sequence_mer(_conn(base), "N09", "M01")
    assert v["valide"] and v["erreurs"] == []
    assert v["avertissements"][0] == "8 exercice(s) de séance pour 24 séance(s) prévue(s)"


def test_validation_mer_exige_la_fiche_et_un_exercice_par_objectif(base, lots):
    _appliquer(base, lots)
    c = _conn(base)
    c.execute("DELETE FROM fiches_resume WHERE sequence='M01'")
    oe = c.execute("SELECT oe.exercice_id FROM objectif_exos oe JOIN objectifs o ON "
                   "o.id=oe.objectif_id WHERE o.code='32' AND oe.serie='MR'").fetchall()
    for (eid,) in oe:
        c.execute("DELETE FROM objectif_exos WHERE exercice_id=?", (eid,))
    v = mer.valider_sequence_mer(c, "N09", "M01")
    assert not v["valide"]
    assert "partie 1 : pas de fiche de cours" in v["erreurs"]          # v0.53.1 : par partie
    assert "M01-32 sans exercice de séance" in v["erreurs"]
    assert "MR07 relié à aucun objectif de la séquence" in v["erreurs"]


# ── 4. Documents (MR5) ──────────────────────────────────────────────────────

@pytest.fixture
def conn_m01(base, lots):
    _appliquer(base, lots)
    return _conn(base)


@pytest.mark.parametrize("par_page", [2, 3, 4])
def test_planche_des_exercices_de_seance_n_par_A4_dans_l_ordre_des_seances(conn_m01, par_page):
    tex = mer.generer_document_mer(conn_m01, "N09", "M01", {"document": "planche",
                                                             "par_page": par_page})
    assert r"\begin{seqPlancheFiches}{%d}" % par_page in tex
    assert tex.count(r"\begin{seqBande}") == 8
    assert tex.index("séance 1 ---") < tex.index("séance 2 ---") < tex.index("séance 8 ---")
    assert r"\seqVersionCorrigee" not in tex
    assert tex.count(r"\setcounter{seqItemCM}{0}") == 8


def test_planche_corrigee_garde_la_mise_en_page_eleve_et_met_les_corriges_rediges_apres(conn_m01):
    # Un corrigé rédigé ne tient pas dans un quart de A4 (essai du lot M01) :
    # les bandes restent celles de l'élève, les corrigés suivent la planche.
    e = mer.generer_document_mer(conn_m01, "N09", "M01", {"document": "planche"})
    tex = mer.generer_document_mer(conn_m01, "N09", "M01", {"document": "planche",
                                                             "version": "corrigee"})
    assert r"\seqVersionCorrigee" in tex and r"\seqLocExplication{" not in e
    debut, fin = tex.index(r"\begin{seqPlancheFiches}"), tex.index(r"\end{seqPlancheFiches}")
    assert r"\seqLocExplication" not in tex[debut:fin]
    assert tex[debut:fin] == e[e.index(r"\begin{seqPlancheFiches}"):e.index(r"\end{seqPlancheFiches}")]
    assert tex.count(r"\seqLocExplication{On utilise") == 8
    assert r"\seqPartieSix{Séance 1 --- Tables de 2 à 5 --- MR01}" in tex[fin:]


def test_bande_sans_titre_en_double_quand_l_enonce_a_son_bandeau_calcul_mental(conn_m01):
    s = mer.lire_sequence_mer(conn_m01, "N09", "M01")
    L: list = []
    mer.emettre_bande(L, s, s["exercices"][0])
    assert not any(x.startswith(r"{\bfseries\color{seqSixBleu}Tables") for x in L)
    L = []
    mer.emettre_bande(L, s, dict(s["exercices"][0], enonce="Calcule."))
    assert any(x.startswith(r"{\bfseries\color{seqSixBleu}Tables de 2 à 5") for x in L)


def test_fiche_de_cours_eleve_a_completer_et_complete_en_version_corrigee(conn_m01):
    e = mer.generer_document_mer(conn_m01, "N09", "M01", {"document": "fiche_cours"})
    k = mer.generer_document_mer(conn_m01, "N09", "M01", {"document": "fiche_cours",
                                                          "version": "corrigee"})
    assert r"\seqVersionComplete" not in e and r"\seqVersionComplete" in k
    assert r"\seqTitreFicheSix{Mise en route 1 --- Calcul mental --- partie 1}" in e
    assert r"\begin{seqFicheResumeSix}{Tables de multiplication}" in e
    assert e.count(r"\begin{seqFicheResumeSix}") == 4       # v0.53.1 : toute la séquence
    x2 = mer.generer_document_mer(conn_m01, "N09", "M01", {"document": "fiche_cours",
                                                           "exemplaires": 2})
    assert r"\begin{seqCopies}{2}" in x2


def test_test_court_au_rendu_6e_avec_la_mention_mise_en_route_et_non_sequence_201(conn_m01):
    tex = mer.generer_document_mer(conn_m01, "N09", "M01", {"document": "test_court"})
    assert "Mise en route 1, partie 1 --- Sujet A --- calculatrice interdite" in tex
    assert "Séquence 201" not in tex
    assert r"\seqBaremeCompetences{M01-02/{10},Bonus/{1}}" in tex
    b = mer.generer_document_mer(conn_m01, "N09", "M01", {"document": "test_court",
                                                          "sujet": "B", "exemplaires": 2})
    assert r"\begin{seqCopies}{2}" in b and r"$5\times4" in b


def test_plan_de_sequence_liste_les_seances_les_tests_et_le_controle(conn_m01):
    tex = mer.generer_document_mer(conn_m01, "N09", "M01", {"document": "plan"})
    assert r"\begin{longtable}" in tex and r"\usepackage{longtable}" in tex
    assert "8 & M01-32 & Arrondir au dixième & MR08" in tex
    assert "Test court --- Tables de multiplication" in tex
    assert "Attention : 8 exercice(s) de séance pour 24 séance(s) prévue(s)" in tex


@pytest.mark.parametrize("options", [{"document": "livret"}, {"par_page": 5},
                                     {"exemplaires": 3}, {"version": "x"}, {"test": 5,
                                                                           "document": "test_court"},
                                     {"partie": 9}, {"partie": "x"}])
def test_options_mer_invalides_refusees(conn_m01, options):
    with pytest.raises(mer.MiseEnRouteErreur):
        mer.generer_document_mer(conn_m01, "N09", "M01", options)


def test_route_du_livret_produit_les_documents_d_une_mise_en_route(base, lots):
    _appliquer(base, lots)
    c = create_app(base.parent, profil="atelier").test_client()
    r = c.post("/api/v2/livret-sequence/N09/M01/rendu-tex",
               json={"options": {"mer": {"document": "planche", "par_page": 2}}})
    assert r.status_code == 200 and r"\begin{seqPlancheFiches}{2}" in r.get_data(as_text=True)
    r = c.get("/api/v2/livret-sequence/N09/M01/rendu-tex?document=plan")
    assert r.status_code == 200 and "Plan de séquence" in r.get_data(as_text=True)
    r = c.get("/api/v2/livret-sequence/N09/M01/rendu-tex?par_page=9")
    assert r.status_code == 400 and r.get_json()["error"] == "options_invalides"


def test_atome_MR_rendu_seul_a_sa_taille_reelle_de_quart_de_page(conn_m01):
    from services.latex_rendu_atome import generer_tex_par_type
    eid = conn_m01.execute("SELECT id FROM exercices WHERE sequence='M01' AND serie_code='MR' "
                           "AND num=3").fetchone()[0]
    tex = generer_tex_par_type(conn_m01, "exercice", eid)
    assert r"\begin{seqPlancheFiches}{4}" in tex and tex.count(r"\begin{seqBande}") == 1
    assert "séance 3 --- M01-12" in tex


# ── 5. Exclusivité avec le principal (MR7) et objectif Cours (MR1b) ─────────

def test_mise_en_route_hors_des_documents_du_principal(conn_m01):
    from services import livret_sequence_6e as l6
    from services.referentiel_documents_compilation import lister_cibles_document
    c = conn_m01
    assert "M01" not in l6.sequences_du_niveau(c, "N09")
    c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, gabarit_documents) "
              "VALUES ('R09', 'N09', '2026', 'en_cours', 'sixieme')")
    for t in ("livret_sequence_6e", "fiches_cours_6e", "evaluation_6e", "plans_travail_6e"):
        cibles = lister_cibles_document(c, None, "R09", t)
        assert not any("M01" in (x.get("cible_id") or "") for x in cibles), t


def test_mise_en_route_hors_de_la_validation_et_du_programme_du_cycle(conn_m01):
    from services.referentiel_validation import _compter_atomes_non_valides
    n = _compter_atomes_non_valides(conn_m01, "N09", "sixieme")
    assert n["exercices"] == 0 and n["fiches_resume"] == 0
    from services import modeles_referentiel as mr
    import inspect
    assert "M[0-9][0-9]" in inspect.getsource(mr)


def test_objectif_01_d_une_mise_en_route_n_est_pas_le_cours(conn_m01):
    assert mer.est_objectif_cours("01", 1, "S01")
    assert not mer.est_objectif_cours("01", 1, "M01")
    from services.referentiels import arbre_du_niveau
    a = arbre_du_niveau(conn_m01, "N09")
    m01 = next(s for s in a["sequences"] if s["code"] == "M01")
    o1 = m01["parties"][0]["objectifs"][0]
    assert o1["code"] == "02" and not o1.get("est_cours")      # v0.53.1 : codes du principal
    assert not mer.est_objectif_cours("11", 2, "M01")


def test_serie_MR_est_une_serie_documents_hors_livret_creee_depuis_l_atelier():
    from services import atomes
    assert "MR" in atomes.SERIES_HORS_LIVRET
    assert atomes._SERIE_VERS_CODE["mise en route"] == "MR"
    assert "mise en route" in atomes.SERIES_VALIDES


def test_module_v0_9_fournit_seqLocItemCM_du_lot_M01_car_les_macros_locales_ne_sont_pas_importees():
    import re
    from services import style6e
    dtx = (APPLI / "paquet" / "seqenseigne-style6e.dtx").read_text(encoding="utf-8")
    sty = (APPLI / "paquet" / "seqenseigne-style6e.sty").read_text(encoding="utf-8")
    assert "v0.11 seqenseigne" in dtx and "v0.11 seqenseigne" in sty   # v0.53.1 : v0.10 ; v0.53.3 : v0.11
    assert "seqLocItemCM" in style6e.MACROS
    assert r"\DescribeMacro{\seqLocItemCM}" in dtx
    assert re.search(r"\\changes\{v0\.9\}\{[^}]*\}\{\\cs\{seqLocItemCM\}", dtx)
    assert r"\NewDocumentCommand{\seqLocItemCM}{m}" in sty
    assert imp_mer.macros_definies(r"\providecommand{\seqLocItemCM}[1]{x}") == ["seqLocItemCM"]
