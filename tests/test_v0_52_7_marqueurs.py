"""tests/test_v0_52_7_marqueurs.py — v0.52.7

Marqueurs « ordinateur » et « calculatrice » des exercices (besoin de
Laurent, 20 octobre 2026). Chaque test nomme la décision qu'il protège
(doc/redemarrage_v0_52_7.md) :

- M1 le marquage porte sur l'énoncé principal ; remédiation et sujet B
  suivent ;
- M2 valeurs fermées (refusées par l'atelier, signalées par l'import) ;
- M3 liste de l'atelier : clé `marqueurs` seulement pour un exercice marqué ;
- M4 cycle 4 : mention dans `nom=`, seulement si l'exercice est marqué ;
- M5 format d'échange 1.3 : `partie.materiel` facultatif, version et
  empreinte inchangées sans marqueur ; côté classe, table
  `referentiel_materiel_publie` ;
- M6 trace de figeage : clés seulement si l'exercice est marqué ;
- M7 import : clé absente = non marqué, idempotent, exercice validé non
  touché, marqueurs hors comparaison R2 ;
- M8 plans de travail : mention dans la ligne et encadré « Matériel à
  prévoir », seulement si un exercice est marqué.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app  # noqa: E402
from services import marqueurs_exercices as mq  # noqa: E402
from tests.test_v0_52_0_import_lot6e import (  # noqa: E402,F401
    _conn, _dump, _lot_s01, base, imp)
from tests.test_v0_52_1_gabarits_documents import SQL_SIXIEME  # noqa: E402
from tests.test_v0_52_6_retrait_evaluations import _evaluation  # noqa: E402

APPLI = Path(__file__).resolve().parent.parent


@pytest.fixture
def app_6e(data_dir):
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as c:
        c.executescript(SQL_SIXIEME)
        c.execute("INSERT INTO referentiel_niveaux (id, niveau, version, etat, gabarit_documents) "
                  "VALUES ('R09', 'N09', '2026', 'en_cours', 'sixieme')")
        c.commit()
    return app


# ── Données ──────────────────────────────────────────────────────────────────

def test_migration_idempotente_ajoute_deux_colonnes_vides_car_rien_n_est_marque_par_defaut():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE exercices (id TEXT PRIMARY KEY, titre TEXT)")
    c.execute("INSERT INTO exercices VALUES ('x', 't')")
    mq.migrer(c)
    mq.migrer(c)
    cols = {r[1]: r for r in c.execute("PRAGMA table_info(exercices)")}
    assert cols["ordinateur"][3] == 1 and cols["calculatrice"][3] == 1        # NOT NULL
    assert c.execute("SELECT ordinateur, calculatrice FROM exercices").fetchone() == ("", "")


def test_base_de_l_appli_migree_au_demarrage(app_6e):
    with app_6e.json_store._conn() as c:
        assert mq.colonnes_presentes(c)


def test_m2_valeurs_fermees():
    assert mq.ORDINATEUR == ("", "scratch", "geogebra", "tableur", "autre")
    assert mq.CALCULATRICE == ("", "autorisee", "interdite")
    assert mq.valider("ordinateur", None) == ""
    with pytest.raises(mq.MarqueurInvalide):
        mq.valider("calculatrice", "oui")


# ── Atelier : services et routes ─────────────────────────────────────────────

def test_m2_atelier_enregistre_relit_et_refuse_une_valeur_inconnue(app_6e):
    cl = app_6e.test_client()
    eid = cl.post("/api/exercices", json={"serie": "fondamental", "niveau": "N09",
                                          "sequence": "S01"}).get_json()["id"]
    r = cl.patch(f"/api/exercices/{eid}", json={"ordinateur": "scratch",
                                                 "calculatrice": "interdite"})
    assert r.status_code == 200
    d = cl.get(f"/api/exercices/{eid}").get_json()
    assert (d["ordinateur"], d["calculatrice"]) == ("scratch", "interdite")
    r = cl.patch(f"/api/exercices/{eid}", json={"ordinateur": "python"})
    assert r.status_code == 400
    assert cl.get(f"/api/exercices/{eid}").get_json()["ordinateur"] == "scratch"
    r = cl.post("/api/exercices", json={"serie": "fondamental", "calculatrice": "peut-être"})
    assert r.status_code == 400


def test_enregistrement_sans_les_cles_garde_les_marqueurs_car_le_scanner_ne_les_connait_pas(app_6e):
    st = app_6e.json_store
    with st._conn() as c:
        c.execute("UPDATE exercices SET ordinateur='geogebra' WHERE id='f1'")
        c.commit()
    liste = st.lire_exercices()
    for e in liste:
        e.pop("ordinateur", None)
        e.pop("calculatrice", None)
    st.ecrire_exercices(liste)
    with st._conn() as c:
        assert c.execute("SELECT ordinateur FROM exercices WHERE id='f1'").fetchone()[0] == "geogebra"


def test_m3_liste_atelier_cle_marqueurs_seulement_pour_un_exercice_marque(app_6e):
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE exercices SET calculatrice='autorisee' WHERE id='f2'")
        c.commit()
    data = app_6e.test_client().get("/api/exercices?niveau=N09&sequence=S01").get_json()
    par_id = {a["id"]: a for a in data}
    assert par_id["f2"]["marqueurs"] == {"ordinateur": "", "calculatrice": "autorisee"}
    assert set(par_id["f1"]) == {"id", "titre", "num", "code", "etat_code", "liens", "sequence"}


def test_interface_atelier_listes_ordinateur_et_calculatrice():
    html = (APPLI / "templates" / "index.html").read_text(encoding="utf-8")
    for v in ("scratch", "geogebra", "tableur", "autre", "autorisee", "interdite"):
        assert f'<option value="{v}">' in html
    assert 'id="atl-exercice-ordinateur"' in html and 'id="atl-exercice-calculatrice"' in html


# ── Rendus 6e ────────────────────────────────────────────────────────────────

def test_titre_6e_inchange_sans_marqueur_et_pictogrammes_sinon():
    from services.livret_sequence_6e import _titre_exo
    ex = {"titre": "Les rosaces", "code": "F01"}
    assert _titre_exo(ex) == (r"Les rosaces\hfill{\footnotesize\color{seqSixGrisTexte}F01}")
    ex.update(ordinateur="scratch", calculatrice="interdite")
    assert _titre_exo(ex) == (r"Les rosaces\hfill\seqMaterielSix{Scratch}{interdite}\quad"
                              r"{\footnotesize\color{seqSixGrisTexte}F01}")
    assert mq.latex_6e({"ordinateur": "autre"}) == r"\seqMaterielSix{autre logiciel}{}"


def test_m1_la_remediation_suit_le_marquage_de_l_exercice(app_6e):
    from services import livret_sequence_6e as l6
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE exercices SET ordinateur='tableur' WHERE id='f1'")
        tex = l6.generer_livret_sequence_6e(c, "N09", "S01", {"version": "eleve"})
    lignes = [x for x in tex.splitlines() if "Former des nombres" in x and "seqExoSix" in x]
    assert len(lignes) >= 2 and all(r"\seqMaterielSix{Tableur}{}" in x for x in lignes)
    assert any("Remédiation" in x for x in lignes)


def test_module_style6e_v0_7_documente_les_marqueurs():
    import re
    from services import style6e
    dtx = (APPLI / "paquet" / "seqenseigne-style6e.dtx").read_text(encoding="utf-8")
    sty = (APPLI / "paquet" / "seqenseigne-style6e.sty").read_text(encoding="utf-8")
    # v0.52.8 : le module est passé en v0.8 ; les marqueurs v0.7 restent.
    # v0.53.0 : module v0.9 (\seqLocItemCM, lot M01), qui garde tout ce qui précède.
    assert "v0.11 seqenseigne" in dtx and "v0.11 seqenseigne" in sty   # v0.53.1 : v0.10 ; v0.53.3 : v0.11
    for m in ("seqMaterielSix", "seqOrdinateurSix", "seqCalculatriceSix"):
        assert m in style6e.MACROS
        assert rf"\DescribeMacro{{\{m}}}" in dtx
        assert re.search(r"\\changes\{v0\.7\}\{[^}]*\}\{\\cs\{" + m + r"\}", dtx), m
        assert re.search(r"\\(newcommand|NewDocumentCommand)\{\\" + m + r"\}", sty), m


# ── Cycle 4 ──────────────────────────────────────────────────────────────────

def test_m4_cycle4_nom_inchange_sans_marqueur_et_mention_sinon():
    from services.latex_rendu_atome import Atome, generer_corps_exercice
    a = Atome(id="x", type_atome="exercice", niveau="N10", sequence="S01", fichier="",
              titre="Fractions", corps="Énoncé", corrige="c", num=1, serie="fondamental")
    assert "nom={Fractions}" in generer_corps_exercice(a)
    a.ordinateur, a.calculatrice = "geogebra", "autorisee"
    assert (r"nom={Fractions\hfill{\small\upshape (ordinateur~: GeoGebra ; "
            r"calculatrice autorisée)}}") in generer_corps_exercice(a)
    assert mq.nom_cycle4("T", {}) == "T"


# ── Plans de travail ─────────────────────────────────────────────────────────

def test_m8_plan_6e_mention_dans_la_ligne_et_encadre_materiel(app_6e):
    from services.plan_travail_6e import generer_plan_travail_6e, ligne_exercices
    assert ligne_exercices([("O", 1), ("O", 2), ("A", 3)]) == "1 - 2 - ( 3 )"
    with app_6e.json_store._conn() as c:
        sans = generer_plan_travail_6e(c, "N09", "S01")
        assert "Matériel à prévoir" not in sans
        c.execute("UPDATE exercices SET ordinateur='scratch' WHERE id='f2'")
        c.execute("UPDATE exercices SET calculatrice='autorisee' WHERE id='a2'")
        avec = generer_plan_travail_6e(c, "N09", "S01")
    assert "Matériel à prévoir" in avec
    assert r"\textbf{Ordinateur --- Scratch} : exercice" in avec
    assert r"\textbf{Calculatrice (autorisée)} : activité" in avec
    assert r"{\small (ordinateur~: Scratch)}" in avec


def test_m8_plan_cycle4_liste_inchangee_sans_marqueur():
    from services.livret_plans_de_travail import _emettre_materiel, _fmt_liste_exos
    assert _fmt_liste_exos([1, 2, 3]) == "1,2,3"
    assert _fmt_liste_exos([1, 2], {2: "calculatrice interdite"}) == \
        r"1,2 {\small (calculatrice interdite)}"
    assert _emettre_materiel({"numero": 1}, [{"code": "02"}]) == []


# ── Format d'échange, classe, figeage ────────────────────────────────────────

def _referentiel(c):
    c.execute("INSERT INTO referentiel_sequences (referentiel_id, code, numero, nom) "
              "VALUES ('R09', 'S01', 1, 'Nombres')")
    c.execute("INSERT INTO referentiel_parties (referentiel_id, seq_code, numero) "
              "VALUES ('R09', 'S01', 1)")


def test_m5_format_inchange_sans_marqueur_et_1_3_avec(app_6e, tmp_path):
    from services import format_referentiel as fmt
    from services import import_publication as ip
    with app_6e.json_store._conn() as c:
        _referentiel(c)
        sans = fmt.construire(c, "R09")
        c.execute("UPDATE exercices SET ordinateur='scratch', calculatrice='interdite' "
                  "WHERE id='f2'")
        c.execute("UPDATE exercices SET calculatrice='autorisee' WHERE id='a1'")
        avec = fmt.construire(c, "R09")
    # Sans marqueur : document de la v0.52.6 (version 1.2, pas de clé
    # `materiel`, même vide), donc même empreinte.
    assert sans["format_version"] == "1.2"
    assert "materiel" not in sans["sequences"][0]["parties"][0]
    with app_6e.json_store._conn() as c:
        c.execute("UPDATE exercices SET ordinateur='', calculatrice=''")
        assert fmt.construire(c, "R09")["empreinte"] == sans["empreinte"]
    assert avec["format_version"] == "1.3" and fmt.valider(avec) == []
    m = avec["sequences"][0]["parties"][0]["materiel"]
    assert [(x["objectif"], x["serie"], x["exercice"]) for x in m] == [
        ("", "EA", "AE01"), ("03", "F", "F02")]
    assert m[1]["ordinateur"] == "scratch" and m[1]["calculatrice"] == "interdite"
    # Côté classe : stocké pour le futur tableau de bord.
    classe = create_app(data_dir=_dossier(tmp_path), profil="classe")
    with classe.json_store._conn() as c:
        ip._appliquer(c, tmp_path, "R09", avec, None, {}, "2026-10-20")
        rows = ip.materiel_publie(c, "R09", "S01", 1)
    assert [(r["exercice"], r["ordinateur"]) for r in rows] == [("AE01", ""), ("F02", "scratch")]


def _dossier(tmp_path):
    d = tmp_path / "classe"
    d.mkdir()
    return d


def test_m5_table_classe_rangee_cote_classe():
    from services import repartition
    assert "referentiel_materiel_publie" in repartition.TABLES_CLASSE


def test_m6_trace_de_figeage_cles_seulement_si_marque(app_6e):
    from services.referentiel_figeage import _trace_exos_de_objectif
    with app_6e.json_store._conn() as c:
        assert all("ordinateur" not in e for e in _trace_exos_de_objectif(c, "o602"))
        c.execute("UPDATE exercices SET ordinateur='tableur' WHERE id='f1'")
        t = _trace_exos_de_objectif(c, "o602")
    assert [e.get("ordinateur") for e in t if e["titre"] == "Former des nombres"] == ["tableur"]
    assert all("calculatrice" not in e for e in t)


# ── Import des lots ──────────────────────────────────────────────────────────

def _marquer(lots, **cles):
    f = lots / "S01" / "S01.json"
    lot = json.loads(f.read_text(encoding="utf-8"))
    for (obj, liste, num), m in cles.get("exos", {}).items():
        x = next(e for o in lot["objectifs"] if o["code"] == obj for e in o[liste]
                 if e["num"] == num)
        x.clear() if m is None else None
        x.update(m)
    for cle, k, m in cles.get("docs", []):
        lot[cle][k].update(m)
    if "evaluations" in cles:
        lot["evaluations"] = cles["evaluations"]
    f.write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")


def _marques(db):
    c = _conn(db)
    return {f"{r['serie_code']}{r['num']:02d}": (r["ordinateur"], r["calculatrice"])
            for r in c.execute("SELECT * FROM exercices WHERE niveau='N09' AND sequence='S01'")
            if r["ordinateur"] or r["calculatrice"]}


def _appliquer(db, lots):
    assert imp.main(["--db", str(db), "--lots", str(lots), "--apply", "--yes"]) == 0


def test_m7_import_ecrit_les_marqueurs_de_tous_les_types_et_reste_idempotent(base, tmp_path):
    lots = _lot_s01(tmp_path / "lots")
    ev = _evaluation("Évaluation --- Nombres", [("Valeur", 10, "S01-02", "Énoncé V."),
                                                ("Rang", 10, "S01-02", "Énoncé R.")])
    ev[0]["calculatrice"] = "interdite"
    _marquer(lots, exos={("S01-02", "exercices", 1): {"ordinateur": "scratch"},
                         ("S01-02", "activites", 2): {"calculatrice": "autorisee"}},
             docs=[("travaux_personnels", 0, {"ordinateur": "geogebra"}),
                   ("activites_complementaires", 0, {"ordinateur": "tableur",
                                                     "calculatrice": "autorisee"})],
             evaluations=ev)
    _appliquer(base, lots)
    m = _marques(base)
    assert m == {"F01": ("scratch", ""), "AE02": ("", "autorisee"), "TP01": ("geogebra", ""),
                 "AC01": ("tableur", "autorisee"), "EV01": ("", "interdite"),
                 "EV02": ("", "interdite")}
    etat = _dump(base, ("exercices",))
    _appliquer(base, lots)
    assert _dump(base, ("exercices",)) == etat
    rapport = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                                base.parent / "images").texte()
    assert "marqueurs : ordinateur Scratch 1" in rapport


def test_m7_cle_retiree_du_lot_demarque_car_le_lot_fait_foi(base, tmp_path):
    lots = _lot_s01(tmp_path / "lots")
    _marquer(lots, exos={("S01-02", "exercices", 2): {"calculatrice": "interdite"}})
    _appliquer(base, lots)
    assert _marques(base) == {"F02": ("", "interdite")}
    _marquer(lots, exos={("S01-02", "exercices", 2): {"calculatrice": ""}})
    _appliquer(base, lots)
    assert _marques(base) == {}


def test_m7_exercice_valide_non_touche_et_valeur_inconnue_signalee(base, tmp_path):
    lots = _lot_s01(tmp_path / "lots")
    _appliquer(base, lots)
    c = _conn(base)
    c.execute("UPDATE exercices SET etat_code='valide' WHERE niveau='N09' AND sequence='S01' "
              "AND serie_code='F' AND num=1")
    c.commit()
    c.close()
    _marquer(lots, exos={("S01-02", "exercices", 1): {"ordinateur": "scratch"},
                         ("S01-02", "exercices", 2): {"ordinateur": "python"}})
    r = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                          base.parent / "images")
    assert any("F01 validé dans l'atelier" in a for a in r.anomalies)
    assert any("ordinateur 'python' inconnu" in a for a in r.anomalies)
    _appliquer(base, lots)
    assert _marques(base) == {}


def test_m7_marqueurs_hors_comparaison_r2_un_ev_valide_garde_son_numero(base, tmp_path):
    """Marquer une évaluation ne doit pas faire passer un exercice EV validé
    (même contenu) pour « occupé » : il garde son numéro (R2 inchangée)."""
    lots = _lot_s01(tmp_path / "lots")
    exos = [("Valeur", 10, "S01-02", "Énoncé V."), ("Rang", 10, "S01-02", "Énoncé R.")]
    _marquer(lots, evaluations=_evaluation("Évaluation --- Nombres", exos))
    _appliquer(base, lots)
    c = _conn(base)
    c.execute("UPDATE exercices SET etat_code='valide' WHERE niveau='N09' AND sequence='S01' "
              "AND serie_code='EV' AND num=1")
    c.commit()
    c.close()
    ev = _evaluation("Évaluation --- Nombres", exos)
    ev[0]["calculatrice"] = "autorisee"
    _marquer(lots, evaluations=ev)
    _appliquer(base, lots)
    c = _conn(base)
    nums = sorted(r[0] for r in c.execute("SELECT num FROM exercices WHERE niveau='N09' AND "
                                          "sequence='S01' AND serie_code='EV'"))
    assert nums == [1, 2]
    assert _marques(base) == {"EV02": ("", "autorisee")}             # EV01 validé : non touché


def test_m7_import_ajoute_les_colonnes_d_une_base_pas_encore_migree(base, tmp_path):
    """Laurent peut lancer l'import avant le premier démarrage de la v0.52.7."""
    c = _conn(base)
    c.execute("ALTER TABLE exercices DROP COLUMN ordinateur")
    c.execute("ALTER TABLE exercices DROP COLUMN calculatrice")
    c.commit()
    assert not mq.colonnes_presentes(c)
    c.close()
    lots = _lot_s01(tmp_path / "lots")
    _marquer(lots, exos={("S01-02", "exercices", 1): {"ordinateur": "scratch"}})
    _appliquer(base, lots)
    assert _marques(base) == {"F01": ("scratch", "")}
