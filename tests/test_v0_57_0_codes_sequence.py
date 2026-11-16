"""tests/test_v0_57_0_codes_sequence.py — v0.57.0 (plan de migration des thèmes
et des codes, livraison 1 : code tolérant aux codes A1, aucune donnée migrée).

Chaque test nomme l'invariant qu'il protège. Décisions D1 à D8 :
`doc/redemarrage_v0_57_0.md`. Aucune base réelle : bases reconstruites dans
`tmp_path`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from services import codes_sequence as cs

APPLI = Path(__file__).resolve().parent.parent
PAQUET = APPLI / "paquet"


# ── D1 — services/codes_sequence.py : une seule source ─────────────────────

@pytest.mark.parametrize("code,famille", [
    ("A1", "theme"), ("F9", "theme"), ("S01", "ancien"), ("S15", "ancien"),
    ("M01", "mer"), ("X10", "archive"), ("G1", None), ("A0", None), ("A10", None),
    ("S1", None), ("DC1", None), ("", None), (None, None)])
def test_familles_de_codes_lettres_a_f_seulement_et_s_m_x_reserves(code, famille):
    assert cs.famille(code) == famille


def test_routes_acceptent_un_ancien_code_comme_avant_et_un_code_de_theme():
    # Avant v0.57.0, les routes acceptaient S + 1 à 3 chiffres : rien ne se resserre.
    for c in ("S1", "S01", "S101", "A1", "E1"):
        assert cs.est_code_sequence(c, ancien_large=True)
    for c in ("XYZ", "G1", "A10", "S1234", "M01", "X01"):
        assert not cs.est_code_sequence(c, ancien_large=True)
    assert cs.est_code_sequence("M01", mer=True)
    assert cs.est_code_sequence("X01", archive=True)


def test_chercher_code_dans_un_nom_de_fichier_ne_lit_pas_e2_dans_5e2():
    assert cs.chercher_code("5E2 S03_Livret.pdf") == "S03"
    assert cs.chercher_code("livret_sequence__N10__A1.pdf") == "A1"
    assert cs.chercher_code("livret_sequence__N10__S03.pdf") == "S03"
    assert cs.chercher_code("5E2 Livret.pdf") is None


def test_titre_sequence_a1_et_jamais_sequence_11_et_anciens_codes_inchanges():
    assert cs.libelle_numero("A1", 11, 2) == "A1"
    assert cs.libelle_numero("S03", 3, 2) == "03"
    assert cs.libelle_numero("S03", 3) == "3"
    assert cs.libelle_numero("S03", None) == ""


def test_tri_inchange_sans_code_de_theme_et_anciens_avant_nouveaux_quand_ils_coexistent():
    sans_theme = ["X02", "S10", "M01", "S02", "S01"]
    assert cs.trier(sans_theme) == sorted(sans_theme)          # ordre d'avant v0.57.0
    assert cs.trier(["B1", "S03", "A2", "X04", "A1", "S01"]) == ["S01", "S03", "A1", "A2",
                                                                   "B1", "X04"]


def test_convention_refuse_un_melange_d_anciens_codes_et_de_codes_de_theme():
    assert cs.convention_codes(["S01", "M01", "X01"]) == "ancien"
    assert cs.convention_codes(["A1", "M01"]) == "nouveau"
    assert cs.convention_codes(["M01", "X01"]) is None
    with pytest.raises(cs.CorrespondanceErreur):
        cs.convention_codes(["S01", "A1"])


# ── Table de correspondance outils/correspondance_codes_2027.json ──────────

def _table():
    return json.loads(cs.CHEMIN_CORRESPONDANCE.read_text(encoding="utf-8"))


def test_table_cycle3_couvre_les_treize_sequences_de_objectifs_6e_json_sans_perte():
    ref = json.loads((APPLI / "outils" / "objectifs_6e.json").read_text(encoding="utf-8"))
    c03 = _table()["cycles"]["C03"]
    par_ancien = {s["ancien"]: s for s in c03["sequences"]}
    assert sorted(par_ancien) == sorted(s["code"] for s in ref["sequences"])
    for s in ref["sequences"]:
        e = par_ancien[s["code"]]
        assert (e["nom"], e["theme_ancien"], e["numero_ancien"]) == (s["nom"], s["theme"],
                                                                      s["numero"])
    # Thèmes : permutation B → F, C → B, D → C, E → D, F → E ; noms et couleurs inchangés.
    perm = {t["ancien"]: t["nouveau"] for t in c03["themes"]}
    assert perm == {"A": "A", "B": "F", "C": "B", "D": "C", "E": "D", "F": "E"}
    couleurs = {t["code"]: t["code_couleur"] for t in ref["themes"]}
    assert all(couleurs[t["ancien"]] == t["code_couleur"] for t in c03["themes"])


def test_table_numero_vaut_dix_fois_le_rang_du_theme_plus_le_rang_dans_le_theme():
    for cycle, d in _table()["cycles"].items():
        ordre = {t["nouveau"]: t["ordre_nouveau"] for t in d["themes"]}
        for s in d["sequences"]:
            n = s["nouveau"]
            if n.startswith("X"):
                assert s["numero_nouveau"] == 100 + int(n[1:])
                continue
            assert cs.est_code_theme(n)
            assert s["theme_nouveau"] == n[0]
            assert s["numero_nouveau"] == 10 * ordre[n[0]] + int(n[1]), (cycle, n)
        nouveaux = [s["nouveau"] for s in d["sequences"]]
        assert len(nouveaux) == len(set(nouveaux)), cycle


def test_table_cycle4_suit_la_synthese_d1_fonctions_avant_d2_proportionnalite():
    c04 = {s["ancien"]: s["nouveau"] for s in _table()["cycles"]["C04"]["sequences"]}
    assert c04 == {"S03": "A1", "S15": "A2", "S01": "A3", "S05": "A4", "S11": "B1",
                   "S12": "B2", "S13": "B3", "S06": "C1", "S07": "C2", "S09": "D1",
                   "S08": "D2", "S14": "E1", "S02": "X02", "S04": "X04", "S10": "X10"}


def test_table_cycle3_cercles_b2_avant_angles_b3_et_grandeurs_en_f():
    t = _table()["cycles"]["C03"]
    seqs = {s["nom"]: s["nouveau"] for s in t["sequences"]}
    assert (seqs["Cercles"], seqs["Angles"]) == ("B2", "B3")
    assert {m["code"]: m["theme_nouveau"] for m in t["mises_en_route"]}["M03"] == "F"


def test_table_cycle4_anciens_codes_conformes_aux_donnees_de_depart():
    import csv
    with open(APPLI / "data" / "C04_sequences.csv", encoding="utf-8-sig", newline="") as f:
        csv_c04 = {r["Code"]: r for r in csv.DictReader(f)}
    for s in _table()["cycles"]["C04"]["sequences"]:
        if s.get("nouvelle"):
            assert s["ancien"] not in csv_c04
            continue
        assert csv_c04[s["ancien"]]["Theme"] == s["theme_ancien"], s["ancien"]
        assert int(csv_c04[s["ancien"]]["Numero"]) == s["numero_ancien"]


# ── Validations (endroits 1, 2, 3 et 15) ───────────────────────────────────

def test_compilation_par_lot_accepte_un_code_de_theme():
    from services.compilation_batch import sequence_valide
    assert sequence_valide("A1") and sequence_valide("S03") and sequence_valide("M01")
    assert not sequence_valide("G1") and not sequence_valide("A01")


def test_precedence_vers_une_sequence_a1_acceptee_et_format_absurde_refuse():
    from services.v2_edition import PrecedenceInvalide, _valider_precedence
    _valider_precedence("N09", "A1")
    _valider_precedence("N09", "S03")
    with pytest.raises(PrecedenceInvalide):
        _valider_precedence("N09", "G1")


@pytest.fixture
def client_vide(tmp_path):
    from app import create_app
    d = tmp_path / "data"
    d.mkdir()
    app = create_app(data_dir=d)
    app.config["TESTING"] = True
    return app.test_client()


def test_route_livret_sequence_ne_refuse_plus_un_code_a1_comme_invalide(client_vide):
    r = client_vide.get("/api/v2/livret-sequence/N10/A1/rendu-tex")
    assert r.status_code != 400 or "sequence invalide" not in (r.get_json() or {}).get("error", "")
    r = client_vide.get("/api/v2/livret-sequence/N10/G1/rendu-tex")
    assert r.status_code == 400 and "sequence invalide" in r.get_json()["error"]


def test_route_plan_de_travail_ne_refuse_plus_un_code_a1_comme_invalide():
    from flask import Flask
    from routes.plans_de_travail import _valider_niveau_sequence
    with Flask(__name__).app_context():
        assert _valider_niveau_sequence("N10", "A1") is None
        assert _valider_niveau_sequence("N10", "S03") is None
        assert _valider_niveau_sequence("N10", "G1")[1] == 400


# ── Scanner (endroits 4 et 5) et imports (6, 7, 8) ─────────────────────────

_EXO = "\\begin{seqExercice}[nom=Essai,obj=02]\nÉnoncé\n\\seqCorrige{Corrigé}\n\\end{seqExercice}\n"
_NOTION = "\\begin{seqNotion}{Titre}{Corps}\n\\end{seqNotion}\n"
_METHODE = "\\begin{seqMethode}{Méthode}{Corps}\n\\end{seqMethode}\n"


def test_scanner_lit_n10a1f01_et_n10s03f01_aucun_fichier_perdu(tmp_path):
    from scanner_latex import scanner_niveau
    base = tmp_path / "N10"
    for d in ("exercices", "notions", "methodes", "livrets_de_sequence"):
        (base / d).mkdir(parents=True)
    for seq in ("A1", "S03"):
        (base / "exercices" / f"N10{seq}F01.tex").write_text(_EXO, encoding="utf-8")
        (base / "exercices" / f"N10{seq}AE01.tex").write_text(_EXO, encoding="utf-8")
        (base / "exercices" / f"N10{seq}_param.tex").write_text("\\xintdefvar a := 2;",
                                                                 encoding="utf-8")
        (base / "notions" / f"N10_{seq}_Notion_01.tex").write_text(_NOTION, encoding="utf-8")
        (base / "methodes" / f"N10_{seq}_Methode_01.tex").write_text(_METHODE, encoding="utf-8")
        (base / "livrets_de_sequence" / f"N10_{seq}_Livret.tex").write_text(
            "\\begin{seqSerieExos}{1}\\input{../exercices/N10" + seq + "F01.tex}\\end{seqSerieExos}",
            encoding="utf-8")
    r = scanner_niveau(str(tmp_path), "N10")
    assert r["erreurs"] == []
    assert sorted((e["sequence"], e["serie_code"]) for e in r["exercices"]) == [
        ("A1", "AE"), ("A1", "F"), ("S03", "AE"), ("S03", "F")]
    assert all(e["variables"] for e in r["exercices"] if e["serie_code"] == "F")
    assert sorted(n["sequence"] for n in r["notions"]) == ["A1", "S03"]
    assert sorted(m["sequence"] for m in r["methodes"]) == ["A1", "S03"]
    assert {l["sequence"]: l["exercices"]["fondamental"] for l in r["livrets"]} == {
        "A1": [1], "S03": [1]}


def test_importer_arborescence_deduit_le_niveau_d_un_fichier_objectifs_en_a1(tmp_path):
    from importer_arborescence import deduire_niveau
    (tmp_path / "N10A1Objectifs.csv").write_text("x", encoding="utf-8")
    assert deduire_niveau(tmp_path) == "N10"
    (tmp_path / "N10S03Objectifs.csv").write_text("x", encoding="utf-8")
    assert deduire_niveau(tmp_path) == "N10"


def test_fiches_import_lit_seqsetcodesequence_a1_comme_s03():
    from services.fiches_import import _RE_SEQ
    assert _RE_SEQ.search(r"\seqSetCodeSequence{A1}").group(1) == "A1"
    assert _RE_SEQ.search(r"\seqSetCodeSequence{ S03 }").group(1) == "S03"
    assert _RE_SEQ.search(r"\seqSetCodeSequence{G1}") is None


@pytest.mark.parametrize("module", ["outils.verifier_referentiels",
                                    "importers.outils.verifier_referentiels"])
def test_verifier_referentiels_et_sa_copie_trouvent_le_code_a1_d_un_pdf_fige(module):
    import importlib
    m = importlib.import_module(module)
    assert m._chercher_code("livret_sequence__N10__A1.pdf") == "A1"
    assert m._chercher_code("5E2 S03_Livret.pdf") == "S03"


def test_verifier_referentiels_garde_les_creneaux_a1_et_ecarte_toujours_dc1():
    from outils.verifier_referentiels import _seq_valide
    assert _seq_valide("A1") and _seq_valide("S03")
    assert not _seq_valide("DC1") and not _seq_valide("Bilan")


def test_peuplement_14_lit_niveau_et_sequence_des_fichiers_a1():
    import importlib
    import sys
    sys.path.insert(0, str(APPLI / "scripts"))
    m = importlib.import_module("peuplement_14_verif_couverture")
    assert m._extraire_niveaux_sequences([("t", "N10A1F01.tex"), ("t", "N10_B2_Notion_01.tex"),
                                          ("t", "N11_S08_Methode_01.tex")]) == {
        ("N10", "A1"), ("N10", "B2"), ("N11", "S08")}


# ── Documents (endroits 11 et 16) ──────────────────────────────────────────

@pytest.fixture
def base_a1_b1(data_dir):
    """Deux séquences du cycle 4 en codes de thème, A1 (numéro 11) et B1
    (numéro 21), chacune avec son propre objectif ; B1 a A1 pour prérequis."""
    from app import create_app
    app = create_app(data_dir=data_dir)
    with app.json_store._conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS paquet_definitions (
                nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT, corps TEXT,
                corps_fin TEXT, texte_complet TEXT, fichier_source TEXT, ligne_debut INTEGER,
                macros_appelees TEXT, environnements_utilises TEXT,
                statut_rendu_atome TEXT DEFAULT 'reutilise', contenu_atome TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS paquet_requirepackage (
                fichier_source TEXT NOT NULL, ordre INTEGER NOT NULL, nom TEXT NOT NULL,
                options TEXT NOT NULL DEFAULT '', PRIMARY KEY (fichier_source, ordre));
            INSERT OR IGNORE INTO cycles (code, nom) VALUES ('C04', 'Cycle 4');
            INSERT OR IGNORE INTO themes (id, cycle_code, code, nom, code_couleur)
                VALUES ('th_A9', 'C04', 'Z', 'Nombres', 'nombres');
            INSERT INTO sequences_du_cycle (id, cycle_code, code, numero, nom, theme_id)
                VALUES ('sc_a1', 'C04', 'A1', 11, 'Calcul numérique', 'th_A9'),
                       ('sc_b1', 'C04', 'B1', 21, 'Transformations', 'th_A9');
            INSERT INTO sequences_par_niveau (id, niveau, sequence_code, parametres)
                VALUES ('sn_a1', 'N10', 'A1', ''), ('sn_b1', 'N10', 'B1', '');
            INSERT INTO sequence_parties (id, sequence_par_niveau_id, numero)
                VALUES ('pt_a1', 'sn_a1', 1), ('pt_b1', 'sn_b1', 1);
            INSERT INTO objectifs (id, partie_id, code, nom)
                VALUES ('ob_a1', 'pt_a1', '02', 'Objectif propre à A1'),
                       ('ob_b1', 'pt_b1', '02', 'Objectif propre à B1');
            INSERT INTO sequence_par_niveau_precedences
                (sequence_par_niveau_id, precedent_niveau, precedent_seq)
                VALUES ('sn_b1', 'N10', 'A1');
        """)
        conn.commit()
    return app


def test_livret_a1_titre_sequence_a1_jamais_sequence_11_et_ses_propres_objectifs(base_a1_b1):
    from services.livret_sequence import generer_livret_sequence
    with base_a1_b1.json_store._conn() as conn:
        tex_a1 = generer_livret_sequence(conn, "N10", "A1")
        tex_b1 = generer_livret_sequence(conn, "N10", "B1")
    assert "\\begin{boiteTitreGen}{Séquence A1}" in tex_a1
    assert "\\begin{boiteTitreGen}{Séquence B1}" in tex_b1
    assert "Séquence 11" not in tex_a1 and "Séquence 21" not in tex_b1
    assert "Objectif propre à A1" in tex_a1 and "Objectif propre à B1" not in tex_a1
    assert "Objectif propre à B1" in tex_b1
    # Prérequis de B1 : « Séquence A1 — Calcul numérique ».
    assert "Séquence A1 — Calcul numérique" in tex_b1


def test_plan_de_travail_6e_sous_titre_sequence_a1():
    from services.plan_travail_6e import corps_plan

    class N:
        exercices: dict = {}
    L = corps_plan({"code": "A1", "numero": 11, "nom": "Nombres", "parties": []}, N(), [], [],
                   0, {})
    assert any("Séquence A1" in x for x in L) and not any("Séquence 11" in x for x in L)
    L = corps_plan({"code": "S01", "numero": 1, "nom": "Nombres", "parties": []}, N(), [], [],
                   0, {})
    assert any("Séquence 1" in x for x in L)


def test_sujet_d_evaluation_6e_titre_par_libelle_numero():
    src = (APPLI / "services" / "render_evaluation.py").read_text(encoding="utf-8")
    assert "Séquence {libelle_numero(st['sequence'], numero)}" in src


# ── Paquet LaTeX (endroit 12) ──────────────────────────────────────────────

def test_dtx_sans_borne_ni_base_nommee_par_le_numero():
    dtx = (PAQUET / "seqenseigne-data.dtx").read_text(encoding="utf-8")
    code = "\n".join(l for l in dtx.splitlines() if not l.lstrip().startswith("%"))
    assert "\\seq@maxsequences" not in code
    assert "seq@objectifs@s\\" not in code
    assert "\\changes{v1.1}{2026/11/15}" in dtx


@pytest.mark.skipif(shutil.which("tex") is None, reason="tex absent")
def test_sty_livre_est_celui_que_docstrip_produit_du_dtx(tmp_path):
    for f in ("seqenseigne-data.dtx", "seqenseigne.ins"):
        shutil.copy(PAQUET / f, tmp_path)
    ins = (tmp_path / "seqenseigne.ins").read_text(encoding="utf-8")
    ins = re.sub(r"\\file\{(?!seqenseigne-data\.sty)[^}]*\}\{\\from\{[^}]*\}\{package\}\}\n", "",
                 ins)
    (tmp_path / "seqenseigne.ins").write_text(ins, encoding="utf-8")
    subprocess.run(["tex", "-8bit", "-interaction=batchmode", "seqenseigne.ins"], cwd=tmp_path,
                   capture_output=True, timeout=120)
    assert (tmp_path / "seqenseigne-data.sty").read_bytes() == \
        (PAQUET / "seqenseigne-data.sty").read_bytes()


_DOC_A1_B1 = r"""\documentclass{article}
\usepackage[T1]{fontenc}\usepackage[utf8]{inputenc}
\usepackage{seqenseigne-data}
\makeatletter
\DTLnewdb{param_niveaux}\DTLnewrow{param_niveaux}%
\DTLnewdbentry{param_niveaux}{Code}{N10}\DTLnewdbentry{param_niveaux}{AnneeDansCycle}{anneeun}%
\newcommand\ajout[3]{\DTLnewrow{seq@objectifs@anneeun}%
 \DTLnewdbentry{seq@objectifs@anneeun}{CodeSequence}{#1}%
 \DTLnewdbentry{seq@objectifs@anneeun}{CodeObjectif}{#2}%
 \DTLnewdbentry{seq@objectifs@anneeun}{Nom}{#3}%
 \DTLnewdbentry{seq@objectifs@anneeun}{MaitriseTB}{tb}%
 \DTLnewdbentry{seq@objectifs@anneeun}{MaitriseS}{s}%
 \DTLnewdbentry{seq@objectifs@anneeun}{MaitriseF}{f}}
\ajout{A1}{02}{Objectif de A1}\ajout{B1}{02}{Objectif de B1}\ajout{B1}{03}{Second de B1}
\ajout{S03}{02}{Objectif de S03}
\newcommand\lister[1]{\seq@seqcode@tobasename{\nb}{#1}%
 \DTLforeach*{\nb}{\c=CodeObjectif,\n=Nom}{\typeout{OBJ #1 \c\space \n}}}
\begin{document}
\seq@basesobjectifs@filter@niveau{N10}
\lister{A1}\lister{B1}\lister{S03}\lister{C1}
x
\end{document}
"""


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex absent")
def test_un_code_a1_et_un_code_b1_ne_partagent_pas_leurs_objectifs(tmp_path):
    """Avant v1.1 du module data, A1 et B1 donnaient la même base
    (`seq@objectifs@s1`) : les objectifs d'une séquence auraient été lus dans
    une autre. Chaque code a désormais sa base ; S03 garde la sienne ; une
    séquence sans objectif (C1) donne une base vide, sans erreur."""
    (tmp_path / "t.tex").write_text(_DOC_A1_B1, encoding="utf-8")
    env = dict(os.environ, TEXINPUTS=f".:{PAQUET}//:")
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "t.tex"], cwd=tmp_path,
                   capture_output=True, env=env, timeout=300)
    log = (tmp_path / "t.log").read_text(encoding="latin-1")
    assert not re.search(r"^! ", log, re.M), log[-3000:]
    lignes = re.findall(r"^OBJ (\S+) (\d\d) (.+)$", log, re.M)
    assert lignes == [("A1", "02", "Objectif de A1"), ("B1", "02", "Objectif de B1"),
                      ("B1", "03", "Second de B1"), ("S03", "02", "Objectif de S03")]


# ── Lots de 6e (endroit 13, décision D6) ───────────────────────────────────

from tests.test_v0_52_0_import_lot6e import (  # noqa: E402
    TABLES_IMPORT, _dump, _lot_s01, base, imp)


def _migrer_c03_pour_le_test(db: Path) -> None:
    """Migration minimale du cycle 3 (ce que fera la v0.58.0) : thèmes
    permutés, séquences recodées, N09 recodé. Sert à vérifier qu'un lot S…
    est lu en A1 après la migration."""
    t = cs.charger_correspondance()
    c = sqlite3.connect(db)
    for e in t.doc["cycles"]["C03"]["themes"]:
        c.execute("UPDATE themes SET code='tmp'||code WHERE cycle_code='C03' AND code=?",
                  (e["ancien"],))
    for e in t.doc["cycles"]["C03"]["themes"]:
        c.execute("UPDATE themes SET code=?, ordre=? WHERE cycle_code='C03' AND code=?",
                  (e["nouveau"], e["ordre_nouveau"], "tmp" + e["ancien"]))
    for e in t.doc["cycles"]["C03"]["sequences"]:
        c.execute("UPDATE sequences_du_cycle SET numero=numero+1000 WHERE cycle_code='C03' "
                  "AND code=?", (e["ancien"],))
    for e in t.doc["cycles"]["C03"]["sequences"]:
        c.execute("UPDATE sequences_du_cycle SET code=?, numero=? WHERE cycle_code='C03' "
                  "AND code=?", (e["nouveau"], e["numero_nouveau"], e["ancien"]))
        for table, col in (("sequences_par_niveau", "sequence_code"), ("exercices", "sequence"),
                           ("notions", "sequence"), ("methodes", "sequence"),
                           ("fiches_resume", "sequence"), ("cartes_automatisme", "sequence")):
            c.execute(f"UPDATE {table} SET {col}=? WHERE niveau='N09' AND {col}=?",
                      (e["nouveau"], e["ancien"]))
    c.commit()
    c.close()


def _codes_c03(db):
    c = sqlite3.connect(db)
    try:
        return sorted(r[0] for r in c.execute(
            "SELECT code FROM sequences_du_cycle WHERE cycle_code='C03'"))
    finally:
        c.close()


def _lot_en_a1(dossier: Path) -> Path:
    """Le lot S01 de test réécrit en codes de thème (dossier A1, clés A1-nn)."""
    src = _lot_s01(dossier / "tmp")
    lot = json.loads((src / "S01" / "S01.json").read_text(encoding="utf-8"))
    texte = json.dumps(lot, ensure_ascii=False).replace('"S01', '"A1')
    d = dossier / "A1"
    shutil.copytree(src / "S01" / "figures", d / "figures")
    (d / "A1.json").write_text(texte, encoding="utf-8")
    shutil.rmtree(dossier / "tmp")
    return dossier


def test_apres_migration_un_lot_s01_est_importe_en_a1_sans_jamais_recreer_s01(base, tmp_path):
    lots = _lot_s01(tmp_path / "lots")
    assert imp.main(["--db", str(base), "--lots", str(lots), "--apply", "--yes"]) == 0
    _migrer_c03_pour_le_test(base)
    avant = _dump(base, TABLES_IMPORT)
    rapport = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                                base.parent / "images")
    assert any("lot S01 lu en A1" in x for x in rapport.infos)
    assert all(("inchang" in l) for l in rapport.cycle), rapport.cycle
    assert imp.main(["--db", str(base), "--lots", str(lots), "--apply", "--yes"]) == 0
    assert not [c for c in _codes_c03(base) if cs.est_code_ancien(c)]
    assert _dump(base, TABLES_IMPORT) == avant           # rien de créé, rien de renommé


def test_avant_migration_un_lot_ecrit_en_a1_equivaut_au_lot_s01(base, tmp_path):
    lots_s = _lot_s01(tmp_path / "lots_s")
    lots_a = _lot_en_a1(tmp_path / "lots_a")
    assert imp.main(["--db", str(base), "--lots", str(lots_s), "--apply", "--yes"]) == 0
    avant = _dump(base, TABLES_IMPORT)
    assert imp.main(["--db", str(base), "--lots", str(lots_a), "--apply", "--yes"]) == 0
    assert _dump(base, TABLES_IMPORT) == avant
    assert "A1" not in _codes_c03(base)


def test_lot_de_code_inconnu_n_est_pas_importe_et_ne_cree_aucune_sequence(base, tmp_path):
    lots = _lot_s01(tmp_path / "lots")
    assert imp.main(["--db", str(base), "--lots", str(lots), "--apply", "--yes"]) == 0
    _migrer_c03_pour_le_test(base)
    d = tmp_path / "inconnu" / "S14"
    d.mkdir(parents=True)
    (d / "S14.json").write_text(json.dumps({"sequence": "S14", "titre": "?", "objectifs": []}),
                                encoding="utf-8")
    rapport = imp.essai_a_blanc(base, imp.charger_lots(d.parent), imp.charger_referentiel(),
                                base.parent / "images")
    assert any("S14" in a and "non importé" in a for a in rapport.anomalies)
    assert "S14" not in _codes_c03(base)


def test_base_aux_codes_meles_refusee_par_les_outils_de_lots(base):
    c = sqlite3.connect(base)
    c.execute("UPDATE sequences_du_cycle SET code='A1', numero=911 WHERE cycle_code='C03' "
              "AND code='S01'")
    c.commit()
    c.row_factory = sqlite3.Row
    with pytest.raises(imp.ImportErreur):
        imp.convention_base(c)
    c.close()


def test_lettre_de_theme_des_mises_en_route_traduite_par_code():
    t = cs.charger_correspondance()
    ref_mer = {"M03": {"code": "M03", "theme": "B"}, "M05": {"code": "M05", "theme": "C"},
               "M01": {"code": "M01", "theme": "A"}}
    nv = imp.traduire_ref_mer(ref_mer, t, "nouveau")
    assert {k: v["theme"] for k, v in nv.items()} == {"M03": "F", "M05": "B", "M01": "A"}
    assert imp.traduire_ref_mer(nv, t, "nouveau") == nv                 # idempotent
    assert {k: v["theme"] for k, v in imp.traduire_ref_mer(nv, t, "ancien").items()} == \
        {"M03": "B", "M05": "C", "M01": "A"}
    lot = imp.traduire_lot({"sequence": "M03", "theme": "B"}, t, "nouveau")
    assert (lot["sequence"], lot["theme"]) == ("M03", "F")


def test_referentiel_6e_traduit_en_codes_de_theme_numeros_et_ordre_des_themes():
    t = cs.charger_correspondance()
    ref = imp.charger_referentiel()
    nv = imp.traduire_referentiel(ref, t, "nouveau")
    seqs = {s["code"]: (s["numero"], s["theme"]) for s in nv["sequences"]}
    assert seqs["A1"] == (11, "A") and seqs["B2"] == (22, "B") and seqs["E1"] == (51, "E")
    assert sorted(nv["parties"]) == sorted(seqs)
    themes = {th["code"]: (th["nom"], th["ordre"]) for th in nv["themes"]}
    assert themes["F"] == ("Grandeurs et mesures", 6) and themes["B"][0] == "Espace et géométrie"
    assert imp.traduire_referentiel(ref, t, "ancien") is ref          # rien à traduire


def test_etiquettes_d_evaluation_et_objectifs_du_lot_traduits():
    t = cs.charger_correspondance()
    lot = {"sequence": "S01", "objectifs": [{"code": "S01-02", "exercices": [
               {"code": "F01", "serie": "F"}]}],
           "travaux_personnels": [{"objectifs": ["S01-02", "S01-12"]}],
           "ancien_code": "S02",
           "evaluations": [{"latex": "\\seqExoEval{Ex}{2 pts --- S01-02} Texte S01-02",
                            "bareme": [["S01-02", 20]]}]}
    nv = imp.traduire_lot(lot, t, "nouveau")
    assert nv["sequence"] == "A1" and nv["_sequence_lot"] == "S01"
    assert nv["objectifs"][0]["code"] == "A1-02"
    assert nv["objectifs"][0]["exercices"][0]["code"] == "F01"
    assert nv["travaux_personnels"][0]["objectifs"] == ["A1-02", "A1-12"]
    assert nv["ancien_code"] == "S02"                       # information, non traduite
    assert "{2 pts --- A1-02}" in nv["evaluations"][0]["latex"]
    assert nv["evaluations"][0]["latex"].endswith("Texte S01-02")   # texte libre intact
    assert imp.decouper_evaluation(nv["evaluations"][0]["latex"])[0]["objectif"] == "A1-02"
    assert imp.traduire_lot(nv, t, "nouveau") is nv
