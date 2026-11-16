"""tests/test_v0_58_0_migration_themes_codes.py — v0.58.0

Outil `outils/migrer_themes_codes_2027.py` : migration des thèmes et des codes
A1 (cycles 3 et 4), livraison 2 du plan de migration. Chaque test porte le nom
de l'invariant qu'il protège. Base de test reconstruite à chaque test : appli
atelier neuve + vrais CSV de cycle (cycle 4 en S01…S14) + cycle 3 de la v0.52
(import_lot6e : S01…S13, M, archives X01…X16) + contenus de 5e, un référentiel
figé (instantané, `_verrouille\\`, `_publication\\`) et un référentiel externe.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from outils import migrer_themes_codes_2027 as mig
from outils import import_lot6e as imp
from services import codes_sequence as cs
from tests.test_v0_52_0_import_lot6e import base as base_v052, _lot_s01, TABLES_IMPORT, _dump  # noqa: F401

CORR = mig.charger_json(mig.CORRESPONDANCE)

# Reclassement réduit (la table réelle vise les contenus de la base de Laurent).
RECL = {"sequences": {
    "N10/S02": {"archive": "X02", "destinations": [
        {"vers": "N10/A2", "objectif_vise": "S15-12", "methodes": [1], "exercices": ["F01"]},
        {"vers": "N11/A2", "objectif_vise": "copie en 4e", "copie": True, "methodes": [1],
         "exercices": ["F01"]}]},
    "N10/S04": {"archive": "X04", "destinations": []},
    "N10/S10": {"archive": "X10", "destinations": [
        {"vers": "N10/B1", "objectif_vise": "S11-15", "notions": ["01"], "cartes": [1]}]},
}}


def _ins(c, table, **v):
    c.execute(f"INSERT INTO {table} ({', '.join(v)}) VALUES ({', '.join('?' * len(v))})",
              tuple(v.values()))


def _exo(c, eid, niv, seq, sc, num, fichier="", variables=""):
    _ins(c, "exercices", id=eid, serie={"F": "fondamental", "A": "avancé", "E": "exploration"}[sc],
         titre="t", enonce=f"énoncé {eid} \\xintiieval{{{niv}{seq}{sc}{num:02d}_x}}",
         niveau=niv, sequence=seq, num=num, serie_code=sc, fichier=fichier,
         variables=variables, etat_code="en_cours")


@pytest.fixture
def base(base_v052):
    db = base_v052
    c = sqlite3.connect(db)
    r = imp.Rapport()
    imp.executer(c, [], imp.charger_referentiel(), r, db.parent / "images", ecrire_fichiers=False)
    c.commit()
    # Cycle 3 : un exercice de 6e en S01, une fiche ; précédence de 5e vers N09/S01.
    _exo(c, "ex_n09_s01", "N09", "S01", "F", 7)
    # Cycle 4 : N10/S03 (A1), S11 (B1), S02, S10 avec contenus.
    for sid, seq in (("sn_s03", "S03"), ("sn_s11", "S11"), ("sn_s02", "S02"), ("sn_s10", "S10")):
        _ins(c, "sequences_par_niveau", id=sid, niveau="N10", sequence_code=seq, parametres="")
        _ins(c, "sequence_parties", id="pt_" + seq, sequence_par_niveau_id=sid, numero=1)
        _ins(c, "objectifs", id="ob_" + seq, partie_id="pt_" + seq, code="02",
             nom=f"Objectif propre à {seq}")
    _ins(c, "sequence_par_niveau_precedences", sequence_par_niveau_id="sn_s11",
         precedent_niveau="N10", precedent_seq="S03", ordre=1)
    _ins(c, "sequence_par_niveau_precedences", sequence_par_niveau_id="sn_s03",
         precedent_niveau="N09", precedent_seq="S01", ordre=1)
    _exo(c, "ex_s03_f1", "N10", "S03", "F", 1, "N10S03F01.tex",
         variables="\\xintdefiivar N10S03F01_x := 3;")
    _exo(c, "ex_s02_f1", "N10", "S02", "F", 1, "N10S02F01.tex")
    _exo(c, "ex_s02_f2", "N10", "S02", "F", 2, "N10S02F02.tex")
    _exo(c, "ex_a2_f1", "N10", "S11", "F", 1, "N10S11F01.tex")
    _ins(c, "objectif_exos", objectif_id="ob_S02", serie="F", exercice_id="ex_s02_f1", ordre=1)
    _ins(c, "partie_exos_revision_approche", partie_id="pt_S11", type="R", exercice_id="ex_s02_f1",
         ordre=1, origin_niveau="N10", origin_seq="S02", origin_serie="F", origin_num=1)
    _ins(c, "methodes", id="me_s02_1", titre="Comparer", niveau="N10", sequence="S02",
         num_methode=1, num_objectif="02", fichier="N10_S02_Methode_01.tex", etat_code="valide")
    _ins(c, "atome_sections", id="sec_1", entite_type="methode", entite_id="me_s02_1",
         titre="Méthode", ordre=1)
    _ins(c, "atome_section_items", id="it_1", section_id="sec_1", ordre=1, corps="corps")
    _ins(c, "notions", id="no_s10_1", titre="Aire", niveau="N10", sequence="S10",
         num_connaissance="01", fichier="N10_S10_Notion_01.tex", etat_code="en_cours")
    _ins(c, "notions", id="no_s10_2", titre="Durée", niveau="N10", sequence="S10",
         num_connaissance="02", fichier="N10_S10_Notion_02.tex", etat_code="en_cours")
    _ins(c, "cartes_automatisme", id="crt_1", niveau="N10", sequence="S10", num=1, titre="Aire",
         ordre=1)
    _ins(c, "cartes_automatisme", id="crt_b1", niveau="N10", sequence="S11", num=1, titre="Sym",
         ordre=1)
    # Référentiel interne figé (instantané en S…) et référentiel externe.
    _ins(c, "referentiel_niveaux", id="N11_v2025", niveau="N11", version="2025", etat="utilise",
         source="interne", type_ref="principal")
    _ins(c, "referentiel_themes", referentiel_id="N11_v2025", code="A", nom="Nombres et Calculs",
         couleur="nombres", ordre=1)
    _ins(c, "referentiel_sequences", referentiel_id="N11_v2025", code="S03", numero=3,
         nom="Calcul numérique", theme_code="A")
    _ins(c, "referentiel_niveaux", id="X2026_N09", niveau="N09", version="X2026", etat="utilise",
         source="externe", type_ref="principal")
    _ins(c, "referentiel_themes", referentiel_id="X2026_N09", code="A", nom="Géométrie",
         couleur="geometrie", ordre=1)
    _ins(c, "referentiel_sequences", referentiel_id="X2026_N09", code="S01", numero=1,
         nom="Géométrie", theme_code="A")
    c.commit()
    c.close()
    d = db.parent
    (d / "referentiels" / "N11_v2025" / "_publication").mkdir(parents=True)
    (d / "referentiels" / "N11_v2025" / "_publication" / "referentiel.json").write_text(
        json.dumps({"exporte_par": "seqenseigne 0.57.0 (atelier)"}), encoding="utf-8")
    (d / "referentiels" / "N11_v2025" / "_verrouille" / "pdfs").mkdir(parents=True)
    (d / "referentiels" / "N11_v2025" / "_verrouille" / "pdfs" /
     "livret_sequence__N11__S03.pdf").write_bytes(b"%PDF fige")
    return db


@pytest.fixture(autouse=True)
def _table_reduite(tmp_path, monkeypatch):
    """main() lit la table de reclassement réduite (la réelle vise la base de Laurent)."""
    p = tmp_path / "reclassement_test.json"
    p.write_text(json.dumps(RECL), encoding="utf-8")
    monkeypatch.setattr(mig, "RECLASSEMENT", p)


def _arbo(tmp_path) -> Path:
    r = tmp_path / "reference" / "sequences"
    for rel, txt in {
        "N10/exercices/N10S03F01.tex": "\\seqSetCodeSequence{S03}\n% N10S03F01_x\n",
        "N10/exercices/N10S03F01_enonce.tex": "énoncé",
        "N10/exercices/N10S03_param.tex": "\\xintdefiivar N10S03F01_x := 3;",
        "N10/exercices/N10S02F01.tex": "\\seqSetCodeSequence{S02}",
        "N10/exercices/N10S02F02.tex": "\\seqSetCodeSequence{S02}",
        "N10/exercices/N10S11F01.tex": "x",
        "N10/methodes/N10_S02_Methode_01.tex": "méthode",
        "N10/notions/N10_S10_Notion_01.tex": "aire",
        "N10/notions/N10_S10_Notion_02.tex": "durée",
        "N10/livrets_de_sequence/N10_S03_Livret.tex":
            "\\seqSetCodeSequence{S03}\n\\input{../exercices/N10S03_param.tex}\n"
            "\\input{../exercices/N10S03F01.tex}\n\\input{../exercices/N10S03F01}\n"
            "\\input{../../N10/exercices/N10S02F01.tex}\n\\includegraphics{N10S03F01_fig.png}\n",
        "N10/N10S03Objectifs.csv": "x",
    }.items():
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8")
    (r / "N10" / "images").mkdir()
    (r / "N10" / "images" / "N10S03F01_fig.png").write_bytes(b"PNG")
    return r


def _arbre(d: Path) -> dict:
    return {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(d.rglob("*")) if p.is_file()}


def _tables(db) -> dict:
    c = sqlite3.connect(db)
    out = {}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' "
                          "AND name NOT LIKE 'sqlite_%'").fetchall():
        cols = ", ".join(f'"{r[1]}"' for r in c.execute(f'PRAGMA table_info("{t}")'))
        out[t] = c.execute(f'SELECT {cols} FROM "{t}" ORDER BY {cols}').fetchall()
    c.close()
    return out


def _migrer(db, cycles=("C03", "C04"), racines=(), recl=RECL):
    c = sqlite3.connect(db)
    r, j = mig.Rapport(), mig.Journal()
    res = mig.executer(c, list(cycles), CORR, recl, r, db.parent, list(racines), j)
    c.commit()
    c.close()
    if res["plan"]:
        mig.appliquer_fichiers(res["plan"], j, db.parent / "sauvegardes" / "tex")
    return r, j, res


def _q(db, sql, params=()):
    c = sqlite3.connect(db)
    try:
        return c.execute(sql, params).fetchall()
    finally:
        c.close()


# ── Essai à blanc, idempotence, retour arrière ──────────────────────────────

def test_essai_a_blanc_par_defaut_n_ecrit_rien_dans_la_base(base, capsys):
    avant = base.read_bytes()
    assert mig.main(["--db", str(base), "--sans-fichiers"]) == 0
    assert base.read_bytes() == avant
    out = capsys.readouterr().out
    assert "S03 → A1" in out and "essai à blanc" in out


def test_migration_idempotente_la_deuxieme_execution_ne_change_rien_et_le_dit(base, capsys):
    assert mig.main(["--db", str(base), "--sans-fichiers", "--apply", "--yes"]) == 0
    apres = _tables(base)
    capsys.readouterr()
    assert mig.main(["--db", str(base), "--sans-fichiers", "--apply", "--yes"]) == 0
    out = capsys.readouterr().out
    assert out.count("rien à faire") == 2 and "Rien à faire" in out
    assert _tables(base) == apres


def test_annuler_rend_la_base_d_origine_table_par_table_et_les_fichiers(base, tmp_path):
    arbo = _arbo(tmp_path)
    avant, arbre = _tables(base), _arbre(arbo)
    assert mig.main(["--db", str(base), "--latex", str(arbo), "--apply", "--yes"]) == 0
    assert _tables(base) != avant and _arbre(arbo) != arbre
    assert mig.main(["--db", str(base), "--annuler", "--yes"]) == 0
    assert _tables(base) == avant
    assert _arbre(arbo) == arbre
    # Le journal annulé ne s'annule pas deux fois.
    assert mig.main(["--db", str(base), "--annuler", "--yes"]) == 2


def test_annuler_refuse_si_une_donnee_migree_a_ete_modifiee_depuis(base, capsys):
    assert mig.main(["--db", str(base), "--sans-fichiers", "--apply", "--yes"]) == 0
    c = sqlite3.connect(base)
    c.execute("UPDATE exercices SET sequence='A3' WHERE id='ex_s03_f1'")
    c.commit()
    c.close()
    modifiee = _tables(base)
    assert mig.main(["--db", str(base), "--annuler", "--yes"]) == 2
    assert "modifié depuis la migration" in capsys.readouterr().out
    assert _tables(base) == modifiee                 # rien n'a été fait


def test_sauvegarde_et_journal_ecrits_avant_tout_changement(base):
    assert mig.main(["--db", str(base), "--sans-fichiers", "--apply", "--yes"]) == 0
    d = base.parent / "sauvegardes"
    sauvegarde = next(d.glob("avant_migration_2027_*.db"))
    assert _q(sauvegarde, "SELECT code FROM sequences_du_cycle WHERE code='S03'")
    journal = json.loads(next(d.glob("journal_migration_2027_*.json")).read_text(encoding="utf-8"))
    assert journal["sauvegarde"] == str(sauvegarde) and journal["ops"]


def test_cycle_3_et_cycle_4_migres_separement(base):
    _migrer(base, ["C03"])
    assert _q(base, "SELECT code FROM sequences_du_cycle WHERE cycle_code='C03' AND numero=11") == [("A1",)]
    assert _q(base, "SELECT code FROM sequences_du_cycle WHERE cycle_code='C04' AND code='S03'")
    _migrer(base, ["C04"])
    assert _q(base, "SELECT code FROM sequences_du_cycle WHERE cycle_code='C04' AND numero=11") == [("A1",)]


# ── Ce qui n'est jamais touché ──────────────────────────────────────────────

def test_instantanes_figes_verrouille_publication_identiques_octet_pour_octet(base):
    tables = ("referentiel_niveaux", "referentiel_themes", "referentiel_sequences",
              "referentiel_parties", "referentiel_objectifs", "referentiel_obj_exos",
              "referentiel_parties_seances", "referentiel_fichiers")
    avant = {t: v for t, v in _tables(base).items() if t in tables}
    arbre = _arbre(base.parent / "referentiels")
    _migrer(base)
    assert {t: v for t, v in _tables(base).items() if t in tables} == avant
    assert _arbre(base.parent / "referentiels") == arbre
    # N11_v2025 garde ses codes S… et ses anciens thèmes.
    assert _q(base, "SELECT code, theme_code FROM referentiel_sequences "
                    "WHERE referentiel_id='N11_v2025'") == [("S03", "A")]


def test_referentiels_externes_inchanges_leurs_codes_ne_dependent_pas_du_cycle(base):
    _migrer(base)
    assert _q(base, "SELECT code FROM referentiel_sequences WHERE referentiel_id='X2026_N09'") == [("S01",)]


def test_archives_x01_a_x16_du_cycle_3_et_leurs_contenus_ne_bougent_pas(base):
    avant = _q(base, "SELECT * FROM sequences_du_cycle WHERE cycle_code='C03' AND code LIKE 'X%' "
                     "ORDER BY code")
    exos = _q(base, "SELECT * FROM exercices WHERE niveau='N09' AND sequence LIKE 'X%' ORDER BY id")
    assert len(avant) == 16 and exos
    _migrer(base)
    assert _q(base, "SELECT * FROM sequences_du_cycle WHERE cycle_code='C03' AND code LIKE 'X%' "
                    "ORDER BY code") == avant
    assert _q(base, "SELECT * FROM exercices WHERE niveau='N09' AND sequence LIKE 'X%' "
                    "ORDER BY id") == exos


def test_une_ecriture_hors_tables_vivantes_annule_toute_la_transaction(base, monkeypatch):
    original = mig.recoder_tables_vivantes

    def fautif(conn, cycle, carte, j, rapport):
        original(conn, cycle, carte, j, rapport)
        conn.execute("UPDATE referentiel_sequences SET nom='abîmé' WHERE referentiel_id='N11_v2025'")
    monkeypatch.setattr(mig, "recoder_tables_vivantes", fautif)
    avant = base.read_bytes()
    assert mig.main(["--db", str(base), "--sans-fichiers", "--apply", "--yes"]) == 2
    assert base.read_bytes() == avant


def test_base_de_classe_refusee(base):
    c = sqlite3.connect(base)
    c.execute("CREATE TABLE IF NOT EXISTS instance_locale (id TEXT, nom TEXT, cree_le TEXT, role TEXT)")
    c.execute("DELETE FROM instance_locale")
    c.execute("INSERT INTO instance_locale VALUES ('i', 'classe', '', 'classe')")
    c.commit()
    c.close()
    avant = base.read_bytes()
    assert mig.main(["--db", str(base), "--apply", "--yes"]) == 2
    assert base.read_bytes() == avant


def test_referentiel_fige_sans_premiere_publication_refuse_sauf_option_explicite(base):
    (base.parent / "referentiels" / "N11_v2025" / "_publication" / "referentiel.json").unlink()
    assert mig.main(["--db", str(base), "--sans-fichiers"]) == 2
    assert mig.main(["--db", str(base), "--sans-fichiers", "--sans-publication"]) == 0


def test_base_aux_codes_meles_refusee(base):
    c = sqlite3.connect(base)
    c.execute("UPDATE sequences_du_cycle SET code='A1', numero=99 WHERE cycle_code='C04' AND code='S03'")
    c.commit()
    c.close()
    assert mig.main(["--db", str(base), "--sans-fichiers"]) == 2


# ── Thèmes, séquences, tables vivantes ──────────────────────────────────────

def test_themes_du_cycle_4_suivent_les_domaines_et_gardent_leur_identifiant(base):
    ids = dict(_q(base, "SELECT code, id FROM themes WHERE cycle_code='C04'"))
    _migrer(base)
    apres = {r[0]: r[1:] for r in _q(base, "SELECT code, id, nom, code_couleur, ordre FROM themes "
                                           "WHERE cycle_code='C04'")}
    assert apres["B"][0] == ids["D"] and apres["C"][0] == ids["B"] and apres["F"][0] == ids["C"]
    assert apres["D"][1:] == ("Proportionnalité, fonctions", "proportionnalite", 4)
    assert apres["C"][1] == "Organisation et gestion de données et probabilités"
    assert [k for k, _ in sorted(apres.items(), key=lambda x: x[1][3])] == list("ABCDEF")


def test_themes_du_cycle_3_permutes_noms_et_couleurs_inchanges(base):
    avant = {r[0]: r[1:] for r in _q(base, "SELECT id, code, nom, code_couleur FROM themes "
                                           "WHERE cycle_code='C03' AND code NOT LIKE 'X%'")}
    _migrer(base)
    apres = {r[0]: r[1:] for r in _q(base, "SELECT id, code, nom, code_couleur FROM themes "
                                           "WHERE cycle_code='C03' AND code NOT LIKE 'X%'")}
    perm = {"A": "A", "B": "F", "C": "B", "D": "C", "E": "D", "F": "E"}
    for tid, (code, nom, coul) in avant.items():
        assert apres[tid] == (perm[code], nom, coul)


def test_couleurs_des_sequences_s11_geometrie_s08_s09_proportionnalite(base):
    _migrer(base)
    coul = dict(_q(base, "SELECT s.code, t.code_couleur FROM sequences_du_cycle s JOIN themes t "
                         "ON t.id=s.theme_id WHERE s.cycle_code='C04'"))
    assert coul["B1"] == "geometrie"                                    # ex-S11 (grandeurs)
    assert coul["D1"] == coul["D2"] == "proportionnalite"               # ex-S09, ex-S08 (donnees)
    assert coul["A1"] == "nombres" and coul["C1"] == "donnees" and coul["X10"] == "grandeurs"


def test_numero_dix_fois_le_rang_du_theme_et_tri_par_code_egal_tri_par_numero(base):
    _migrer(base)
    rows = _q(base, "SELECT code, numero FROM sequences_du_cycle WHERE cycle_code='C04' "
                    "AND code NOT LIKE 'X%' ORDER BY numero")
    assert [c for c, _ in rows] == sorted(c for c, _ in rows)
    assert dict(rows)["A2"] == 12 and dict(rows)["E1"] == 51


def test_archives_x02_x04_x10_hors_du_referentiel_principal(base):
    from services.mises_en_route_6e import hors_principal
    from services.referentiels_internes import dans_perimetre
    _migrer(base)
    rows = dict(_q(base, "SELECT code, nom FROM sequences_du_cycle WHERE cycle_code='C04' "
                         "AND code LIKE 'X%'"))
    assert rows == {"X02": "Comparaison de nombres (archive)",
                    "X04": "Divisibilité et nombres premiers (archive)",
                    "X10": "Calcul de grandeurs (archive)"}
    assert all(hors_principal(c) for c in rows)
    assert not dans_perimetre("X02", "principal") and dans_perimetre("A2", "principal")
    assert _q(base, "SELECT sequence_code FROM sequences_par_niveau WHERE id='sn_s02'") == [("X02",)]


def test_tables_vivantes_recodees_identifiants_et_liens_inchanges(base):
    _migrer(base)
    assert _q(base, "SELECT sequence, fichier FROM exercices WHERE id='ex_s03_f1'") == [
        ("A1", "N10A1F01.tex")]
    assert _q(base, "SELECT sequence_code FROM sequences_par_niveau WHERE id='sn_s03'") == [("A1",)]
    assert _q(base, "SELECT sequence FROM exercices WHERE id='ex_n09_s01'") == [("A1",)]
    # Liens objectif ↔ exercice : par identifiant, inchangés.
    assert _q(base, "SELECT objectif_id FROM objectif_exos WHERE exercice_id='ex_s02_f1'") == [("ob_S02",)]


def test_precedence_de_5e_vers_la_6e_recodee_avec_le_cycle_3(base):
    _migrer(base)
    rows = _q(base, "SELECT sequence_par_niveau_id, precedent_niveau, precedent_seq FROM "
                    "sequence_par_niveau_precedences WHERE sequence_par_niveau_id IN ('sn_s03','sn_s11')")
    assert sorted(rows) == [("sn_s03", "N09", "A1"), ("sn_s11", "N10", "A1")]


def test_contenus_jamais_reecrits_variables_xint_et_enonces_gardent_l_ancien_nom(base):
    avant = _q(base, "SELECT enonce, variables FROM exercices WHERE id='ex_s03_f1'")
    _migrer(base)
    assert _q(base, "SELECT enonce, variables FROM exercices WHERE id='ex_s03_f1'") == avant
    assert "N10S03F01_x" in avant[0][1]


def test_lots_de_6e_reimportes_apres_migration_en_a1_sans_rien_creer(base, tmp_path):
    lots = _lot_s01(tmp_path / "lots")
    assert imp.main(["--db", str(base), "--lots", str(lots), "--apply", "--yes"]) == 0
    _migrer(base)
    avant = _dump(base, TABLES_IMPORT)
    rapport = imp.essai_a_blanc(base, imp.charger_lots(lots), imp.charger_referentiel(),
                                base.parent / "images")
    assert any("lot S01 lu en A1" in x for x in rapport.infos)
    assert all("inchang" in l for l in rapport.cycle), rapport.cycle
    assert imp.main(["--db", str(base), "--lots", str(lots), "--apply", "--yes"]) == 0
    assert _dump(base, TABLES_IMPORT) == avant
    assert not [c for (c,) in _q(base, "SELECT code FROM sequences_du_cycle WHERE cycle_code='C03'")
                if cs.est_code_ancien(c)]


# ── Reclassement de S02, S04, S10 ───────────────────────────────────────────

def test_reclassement_contenus_repris_renumerotes_a_la_suite_le_reste_en_archive(base):
    _migrer(base)
    # N10/S02 F01 → N10/A2 (première de A2), F02 reste dans X02.
    assert _q(base, "SELECT niveau, sequence, num, fichier FROM exercices WHERE id='ex_s02_f1'") == [
        ("N10", "A2", 1, "N10A2F01.tex")]
    assert _q(base, "SELECT sequence, fichier FROM exercices WHERE id='ex_s02_f2'") == [
        ("X02", "N10X02F02.tex")]
    # N10/S10 carte 1 → B1, à la suite de la carte déjà présente (num 2, ordre 2).
    assert _q(base, "SELECT sequence, num, ordre FROM cartes_automatisme WHERE id='crt_1'") == [
        ("B1", 2, 2)]
    assert _q(base, "SELECT sequence, num_connaissance, fichier FROM notions WHERE id='no_s10_1'") == [
        ("B1", "01", "N10_B1_Notion_01.tex")]
    assert _q(base, "SELECT sequence FROM notions WHERE id='no_s10_2'") == [("X10",)]
    # L'origine notée dans les révisions suit l'exercice.
    assert _q(base, "SELECT origin_niveau, origin_seq, origin_num FROM partie_exos_revision_approche "
                    "WHERE exercice_id='ex_s02_f1'") == [("N10", "A2", 1)]


def test_copie_au_niveau_d_arrivee_nouvel_identifiant_sections_comprises_original_deplace(base):
    _migrer(base)
    copies = _q(base, "SELECT id, niveau, sequence, num_methode, fichier FROM methodes "
                      "WHERE niveau='N11' AND sequence='A2'")
    assert len(copies) == 1 and copies[0][0] != "me_s02_1"
    assert copies[0][1:] == ("N11", "A2", 1, "N11_A2_Methode_01.tex")
    assert _q(base, "SELECT niveau, sequence FROM methodes WHERE id='me_s02_1'") == [("N10", "A2")]
    assert _q(base, "SELECT i.corps FROM atome_sections s JOIN atome_section_items i ON "
                    "i.section_id=s.id WHERE s.entite_id=?", (copies[0][0],)) == [("corps",)]


def test_reclassement_refuse_un_contenu_introuvable_rien_n_est_ecrit(base):
    recl = copy.deepcopy(RECL)
    recl["sequences"]["N10/S02"]["destinations"][0]["exercices"].append("A09")
    c = sqlite3.connect(base)
    avant = _tables(base)
    with pytest.raises(mig.MigrationErreur, match="introuvable"):
        mig.executer(c, ["C03", "C04"], CORR, recl, mig.Rapport(), base.parent, [], mig.Journal())
    c.rollback()
    c.close()
    assert _tables(base) == avant


def test_table_de_reclassement_reelle_coherente_avec_la_correspondance():
    recl = mig.charger_json(Path(mig.__file__).parent / "reclassement_2027.json")
    archives = {s["ancien"]: s["nouveau"] for s in CORR["cycles"]["C04"]["sequences"] if s.get("archive")}
    codes = {s["nouveau"] for s in CORR["cycles"]["C04"]["sequences"]}
    for cle, d in recl["sequences"].items():
        niv, anc = cle.split("/")
        assert archives[anc] == d["archive"]
        for dest in d["destinations"]:
            vniv, vcode = dest["vers"].split("/")
            assert vniv in ("N10", "N11", "N12") and cs.est_code_theme(vcode) and vcode in codes
    # S02, S04, S10 aux trois niveaux.
    assert sorted(recl["sequences"]) == sorted(f"{n}/{s}" for n in ("N10", "N11", "N12")
                                               for s in ("S02", "S04", "S10"))


# ── Fichiers LaTeX ──────────────────────────────────────────────────────────

def test_fichiers_latex_renommes_input_et_code_reecrits_images_jamais_renommees(base, tmp_path):
    arbo = _arbo(tmp_path)
    _migrer(base, racines=[arbo])
    n10 = arbo / "N10"
    assert (n10 / "exercices" / "N10A1F01.tex").read_text(encoding="utf-8").startswith(
        "\\seqSetCodeSequence{A1}")
    assert (n10 / "exercices" / "N10A1F01_enonce.tex").is_file()
    assert (n10 / "exercices" / "N10A1_param.tex").is_file()
    assert (n10 / "N10A1Objectifs.csv").is_file()
    livret = (n10 / "livrets_de_sequence" / "N10_A1_Livret.tex").read_text(encoding="utf-8")
    assert "\\input{../exercices/N10A1_param.tex}" in livret
    assert "\\input{../exercices/N10A1F01.tex}" in livret and "\\input{../exercices/N10A1F01}" in livret
    assert "\\input{../../N10/exercices/N10A2F01.tex}" in livret      # reclassé (S02 → A2)
    assert "\\includegraphics{N10S03F01_fig.png}" in livret            # images : jamais renommées
    assert (n10 / "images" / "N10S03F01_fig.png").is_file()
    assert (n10 / "exercices" / "N10X02F02.tex").read_text(encoding="utf-8") == \
        "\\seqSetCodeSequence{X02}"
    # Contenu reclassé copié en 4e : fichier copié dans le dossier N11.
    assert (arbo / "N11" / "exercices" / "N11A2F01.tex").is_file()


def test_apres_migration_le_scanner_reconnait_les_fichiers_sans_rien_creer_en_double(base, tmp_path):
    from scanner_latex import scanner_niveau
    arbo = _arbo(tmp_path)
    for f in ("N10S03F01.tex",):
        (arbo / "N10" / "exercices" / f).write_text(
            "\\begin{seqExercice}[nom={Ex}]\\seqEnonce{x}\\end{seqExercice}", encoding="utf-8")
    _migrer(base, racines=[arbo])
    en_base = {f for (f,) in _q(base, "SELECT fichier FROM exercices")}
    import re
    motif = re.compile(r"(N\d+)(" + cs.MOTIF_FICHIER + r")(AE|[FAE])(\d+)\.tex$")
    reconnus = [p.name for p in (arbo / "N10" / "exercices").glob("*.tex")
                if motif.match(p.name) and "_param" not in p.name]
    assert reconnus and set(reconnus) <= en_base                  # aucun doublon au scan
    assert "N10X02F02.tex" not in reconnus                        # archives : ignorées
    data = scanner_niveau(str(arbo), "N10")
    assert not data["erreurs"]


def test_conflit_de_fichier_refuse_avant_toute_ecriture(base, tmp_path, capsys):
    arbo = _arbo(tmp_path)
    (arbo / "N10" / "exercices" / "N10A1F01.tex").write_text("déjà là", encoding="utf-8")
    avant, arbre = base.read_bytes(), _arbre(arbo)
    assert mig.main(["--db", str(base), "--latex", str(arbo), "--apply", "--yes"]) == 2
    assert base.read_bytes() == avant and _arbre(arbo) == arbre
    assert "existe déjà" in capsys.readouterr().out


def test_arborescence_trouvee_d_apres_la_configuration_chemin_reference_sequences(base, tmp_path):
    arbo = _arbo(tmp_path)
    (base.parent / "configuration.json").write_text(json.dumps(
        {"chemin_racine_seqenseigne": str(tmp_path)}), encoding="utf-8")
    assert arbo.resolve() in mig.racines_latex(base, None)


def test_lancement_par_chemin_sous_windows_le_module_trouve_l_appli():
    # Lancé par chemin (..\outils\python\python.exe .\outils\migrer_themes_codes_2027.py),
    # le dossier de l'appli est ajouté à sys.path par l'outil lui-même.
    import subprocess
    import sys
    p = subprocess.run([sys.executable, str(Path(mig.__file__)), "--help"], capture_output=True,
                       text=True, cwd=str(Path(mig.__file__).parent.parent))
    assert p.returncode == 0 and "--annuler" in p.stdout


# ── Livrets A1 et B1 après migration ────────────────────────────────────────

def test_apres_migration_livrets_a1_et_b1_avec_leurs_propres_objectifs(base):
    from services.livret_sequence import generer_livret_sequence
    _migrer(base)
    c = sqlite3.connect(base)
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE IF NOT EXISTS paquet_definitions (
            nom TEXT PRIMARY KEY, type_latex TEXT, args_spec TEXT, corps TEXT,
            corps_fin TEXT, texte_complet TEXT, fichier_source TEXT, ligne_debut INTEGER,
            macros_appelees TEXT, environnements_utilises TEXT,
            statut_rendu_atome TEXT DEFAULT 'reutilise', contenu_atome TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS paquet_requirepackage (
            fichier_source TEXT NOT NULL, ordre INTEGER NOT NULL, nom TEXT NOT NULL,
            options TEXT NOT NULL DEFAULT '', PRIMARY KEY (fichier_source, ordre));""")
    tex_a1 = generer_livret_sequence(c, "N10", "A1")
    tex_b1 = generer_livret_sequence(c, "N10", "B1")
    c.close()
    assert "Séquence A1" in tex_a1 and "Séquence B1" in tex_b1
    assert "Objectif propre à S03" in tex_a1 and "Objectif propre à S11" not in tex_a1
    assert "Objectif propre à S11" in tex_b1
    assert "Séquence A1 — Calcul numérique" in tex_b1            # prérequis recodé


def test_titre_de_document_du_lot_jamais_traduit_seule_l_etiquette_d_evaluation_l_est():
    # Sans cette règle, après la migration, 12 documents AC/AT des lots de 6e
    # étaient « mis à jour » avec un titre à moitié traduit (« A1-02, S01-03 »).
    table = cs.charger_correspondance()
    lot = {"sequence": "S01", "activites_complementaires": [
        {"titre": "Sudokus", "objectifs": ["S01-02"],
         "latex": "\\seqTitreComplementSix{Sudokus}{Séquence 1 : Nombres --- S01-02, S01-03}"}],
        "evaluations": [{"titre": "Év", "latex": "\\seqExoEval{Rang}{5 pts --- S01-02}"}]}
    t = imp.traduire_lot(lot, table, "nouveau")
    ac = t["activites_complementaires"][0]
    assert ac["latex"] == lot["activites_complementaires"][0]["latex"]      # texte libre intact
    assert ac["objectifs"] == ["A1-02"]
    assert t["evaluations"][0]["latex"] == "\\seqExoEval{Rang}{5 pts --- A1-02}"


def test_ref6e_v2_table_de_correspondance_en_tete_sans_effet_sur_les_mises_en_route():
    from outils import import_lot6e_mer as mer
    texte = (Path(mer.REF6E_V2)).read_text(encoding="utf-8")
    assert texte.index("## Codes de la rentrée 2027") < texte.index("## Mises en route")
    ref = mer.referentiel_mer()
    assert sorted(ref) == [f"M{i:02d}" for i in range(1, 8)]


def test_fins_de_ligne_windows_gardees_seuls_les_codes_changent(base, tmp_path):
    arbo = _arbo(tmp_path)
    p = arbo / "N10" / "livrets_de_sequence" / "N10_S03_Livret.tex"
    p.write_bytes("\\seqSetCodeSequence{S03}\r\nÉnoncé accentué\r\n\\input{../exercices/N10S03F01.tex}\r\n"
                  .encode("utf-8"))
    _migrer(base, racines=[arbo])
    assert (p.with_name("N10_A1_Livret.tex")).read_bytes() == (
        "\\seqSetCodeSequence{A1}\r\nÉnoncé accentué\r\n\\input{../exercices/N10A1F01.tex}\r\n"
        .encode("utf-8"))
