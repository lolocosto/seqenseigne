"""tests/test_v0_52_0_import_lot6e.py — v0.52.0 (adapté en v0.52.2)

Outil `outils/import_lot6e.py` : import des séquences de 6e dans l'atelier
(N09), remplacement du découpage du cycle 3, archivage réversible de
l'ancien. Base de test reconstruite à chaque test (jamais de base réelle) :
appli atelier neuve + vrais CSV de cycle + anciens exercices de 6e aux codes
S01…S16 + un morceau de cycle 4 qui pointe vers eux.

v0.52.2 (doc/redemarrage_v0_52_2.md) : les documents hors base vont en base
(séries TP, AC, AT, EV ; décision O1 : plus de `.tex`, options --sortie et
--documents-seulement retirées) et les activités sont aussi reliées à leur
objectif (L1). Les tests qui figeaient l'ancien comportement sont adaptés ici ;
le nouveau est testé dans tests/test_v0_52_2_documents_6e.py.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app import create_app
from outils import import_lot6e as imp
from services.cycle_import import importer_cycle

APPLI = Path(__file__).resolve().parent.parent
DATA = APPLI / "data"


# ── Base et lots de test ─────────────────────────────────────────────────────

def _ins(c, table, **v):
    c.execute(f"INSERT INTO {table} ({', '.join(v)}) VALUES ({', '.join('?' * len(v))})",
              tuple(v.values()))


def _exo(c, eid, niveau, seq, sc, num, titre="ancien"):
    _ins(c, "exercices", id=eid, serie={"F": "fondamental", "A": "avancé", "E": "exploration",
                                        "AE": "approche"}[sc],
         titre=titre, enonce=f"énoncé {eid}", niveau=niveau, sequence=seq, num=num,
         serie_code=sc, etat_code="en_cours")


@pytest.fixture
def base(tmp_path):
    d = tmp_path / "data_atelier"
    d.mkdir()
    for f in list(DATA.glob("C0*_*.csv")) + [DATA / "param_niveaux.csv"]:
        shutil.copy(f, d)
    create_app(d, profil="atelier")
    db = d / "seqenseigne.db"
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    for cy in ("C03", "C04"):
        importer_cycle(c, cy, "Cycle", d / f"{cy}_themes.csv", d / f"{cy}_sequences.csv")
    # Anciens exercices de 6e (dont une clé N09/S01/F/1 qui entre en collision
    # avec le nouvel S01-F01) et un exercice de CM2.
    _exo(c, "ex_old_s01f1", "N09", "S01", "F", 1)
    _exo(c, "ex_old_s03a1", "N09", "S03", "A", 1)
    _exo(c, "ex_old_s16e1", "N09", "S16", "E", 1)
    _exo(c, "ex_old_n08", "N08", "S02", "F", 1)
    # Ancienne séquence-niveau N09/S03 avec un objectif et un lien.
    _ins(c, "sequences_par_niveau", id="sn_old_n09_s03", niveau="N09", sequence_code="S03")
    _ins(c, "sequence_parties", id="pt_old_n09", sequence_par_niveau_id="sn_old_n09_s03", numero=1)
    _ins(c, "objectifs", id="ob_old_n09", partie_id="pt_old_n09", code="02", nom="ancien")
    _ins(c, "objectif_exos", objectif_id="ob_old_n09", serie="A", exercice_id="ex_old_s03a1",
         ordre=1)
    _ins(c, "sequence_par_niveau_precedences", sequence_par_niveau_id="sn_old_n09_s03",
         precedent_niveau="N08", precedent_seq="S02")
    # Cycle 4 : N10/S01 a pour prérequis N09/S03 et une révision tirée de l'ancien exo.
    _ins(c, "sequences_par_niveau", id="sn_n10_s01", niveau="N10", sequence_code="S01")
    _ins(c, "sequence_parties", id="pt_n10", sequence_par_niveau_id="sn_n10_s01", numero=1)
    _ins(c, "objectifs", id="ob_n10", partie_id="pt_n10", code="02", nom="Objectif de 5e")
    _exo(c, "ex_n10_f1", "N10", "S01", "F", 1)
    _ins(c, "objectif_exos", objectif_id="ob_n10", serie="F", exercice_id="ex_n10_f1", ordre=1)
    _ins(c, "sequence_par_niveau_precedences", sequence_par_niveau_id="sn_n10_s01",
         precedent_niveau="N09", precedent_seq="S03")
    _ins(c, "partie_exos_revision_approche", partie_id="pt_n10", type="R",
         exercice_id="ex_old_s03a1", ordre=1, origin_niveau="N09", origin_seq="S03",
         origin_serie="A", origin_num=1)
    c.commit()
    c.close()
    return db


def _lot_s01(dossier: Path, avec_figure=True) -> Path:
    d = dossier / "S01"
    (d / "figures").mkdir(parents=True)
    if avec_figure:
        (d / "figures" / "fig-a.png").write_bytes(b"\x89PNG fausse image")
    lot = {
        "sequence": "S01", "titre": "Nombres", "theme": "A", "ancien_code": "S02",
        "macros_locales": "local.tex : \\seqLocBande",
        "objectifs": [
            {"code": "S01-02", "partie": 1, "intitule": "Utiliser la valeur des chiffres selon leur rang",
             "activites": [{"num": 1, "code": "AE01", "titre": "Un sudoku",
                            "latex": "Complète \\includegraphics{fig-a.png}", "figures": ["fig-a.png"],
                            "origine": "26S2liv#A2"},
                           {"num": 2, "code": "AE02", "titre": "Deuxième activité",
                            "latex": "Observe.", "figures": [], "origine": "création"}],
             "fiche_resume": {"titre": "La valeur d'un chiffre",
                              "latex": "\\seqSectionFicheSix{1. Chiffres}\nUn \\seqMotCle{entier}.\n"
                                       "\\seqSectionFicheSix{2. Rang}\nChaque rang vaut "
                                       "\\seqACompleter{dix} fois…"},
             "exercices": [
                 {"num": 1, "code": "F01", "serie": "F", "titre": "Former des nombres",
                  "enonce": "Forme \\seqACompleter{12}.", "corrige": "",
                  "remed_enonce": "Remédiation \\seqACompleter{3}.", "remed_corrige": "Explication.",
                  "origine": "26S2liv#1 | N09/S01/F01", "doublon_de": "", "figures": []},
                 {"num": 2, "code": "F02", "serie": "F", "titre": "Second F", "enonce": "F2",
                  "corrige": "", "remed_enonce": "", "remed_corrige": "", "origine": "création",
                  "figures": []},
                 {"num": 1, "code": "A01", "serie": "A", "titre": "Avancé", "enonce": "A1",
                  "corrige": "c", "remed_enonce": "", "remed_corrige": "", "origine": "création",
                  "figures": []},
                 {"num": 1, "code": "E01", "serie": "E", "titre": "Expert",
                  "enonce": "\\seqLocBande{x}", "corrige": "", "remed_enonce": "",
                  "remed_corrige": "", "origine": "création", "figures": []}]},
            {"code": "S01-12", "partie": 2, "intitule": "Interpréter une fraction comme le quotient de deux entiers",
             "activites": [{"num": 3, "code": "AE03", "titre": "Galettes", "latex": "Partage.",
                            "figures": [], "origine": "création"}],
             "fiche_resume": {"titre": "La fraction, un quotient", "latex": "Texte sans section."},
             "exercices": [
                 {"num": 3, "code": "F03", "serie": "F", "titre": "Division", "enonce": "F3",
                  "corrige": "", "remed_enonce": "", "remed_corrige": "", "origine": "création",
                  "figures": ["absente.png"]}]},
            {"code": "S01-99", "partie": 2, "intitule": "Objectif inventé", "activites": [],
             "exercices": [{"num": 9, "serie": "F", "titre": "x", "enonce": "x"}]},
        ],
        "pour_S02": {"destination": "S02", "objectifs": [
            {"code": "S02-02", "exercices": [{"num": 1, "serie": "F", "enonce": "ne pas importer"}]}]},
        "travaux_personnels": [{"titre": "Travail personnel n°1", "latex": "\\seqTitreTravailSix{TP}{x}{y}",
                                "delai_jours": 7, "bareme": "/20", "origine": "26S2tp1",
                                "objectifs": ["S01-02"], "figures": []}],
        "activites_complementaires": [{"titre": "Le mur", "latex": "Mur.", "origine": "création",
                                       "objectifs": ["S01-12"]}],
        "evaluations": [
            {"titre": "Évaluation --- Nombres", "sujet": "A", "bareme": [["S01-02", 20]],
             "total": 20, "latex": "\\seqIdentEleve Sujet A", "origine": "26S2evA"},
            {"titre": "Évaluation --- Nombres", "sujet": "B", "bareme": [["S01-02", 20]],
             "total": 20, "latex": "\\seqIdentEleve Sujet B", "origine": "26S2evB"}],
    }
    (d / "S01.json").write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")
    return dossier


@pytest.fixture
def lots(tmp_path):
    return _lot_s01(tmp_path / "lots")


def _conn(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


def _appliquer(db, lots_dir, sortie=None):
    # v0.52.2 (O1) : `sortie` n'est plus transmis (plus de .tex hors base).
    args = ["--db", str(db), "--lots", str(lots_dir), "--apply", "--yes"]
    assert imp.main(args) == 0


def _essai(db, lots_dir):
    ref = imp.charger_referentiel()
    return imp.essai_a_blanc(Path(db), imp.charger_lots(lots_dir), ref, Path(db).parent / "images")


def _md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def _dump(db, tables, where=None):
    c = _conn(db)
    out = {}
    for t in tables:
        rows = c.execute(f"SELECT * FROM {t}" + (f" WHERE {where[t]}" if where and t in where
                                                  else "")).fetchall()
        out[t] = sorted(tuple((k, r[k]) for k in r.keys() if k != "mtime") for r in rows)
    c.close()
    return out


TABLES_IMPORT = ("themes", "sequences_du_cycle", "sequences_par_niveau", "sequence_parties",
                 "objectifs", "exercices", "objectif_exos", "partie_exos_revision_approche",
                 "fiches_resume", "objectif_fiches", "atome_sections", "atome_section_items",
                 "sequence_par_niveau_precedences")


# ── Essai à blanc ────────────────────────────────────────────────────────────

def test_essai_a_blanc_n_ecrit_rien_car_il_travaille_sur_une_copie_en_memoire(base, lots, tmp_path,
                                                                               capsys):
    avant = _md5(base)
    assert imp.main(["--db", str(base), "--lots", str(lots)]) == 0
    out = capsys.readouterr().out
    assert "essai à blanc" in out and "S01-02" in out
    assert _md5(base) == avant
    assert not (base.parent / "images").exists() and not (lots / "documents_tex").exists()
    assert not (base.parent / "sauvegardes").exists()


def test_essai_a_blanc_annonce_exactement_ce_que_fait_l_application(base, lots):
    r1 = _essai(base, lots)
    _appliquer(base, lots)
    r2 = imp.Rapport()
    c = _conn(base)
    # Seconde passe sur la base appliquée : plus rien à créer.
    imp.executer(c, imp.charger_lots(lots), imp.charger_referentiel(), r2,
                 base.parent / "images", ecrire_fichiers=False)
    c.rollback()
    c.close()
    assert "créé" in r1.texte() and r1.archivage["exercices"] == 4
    assert not r2.archivage


# ── Application ──────────────────────────────────────────────────────────────

def test_application_cree_structure_n09_en_cours(base, lots):
    _appliquer(base, lots)
    c = _conn(base)
    sn = c.execute("SELECT * FROM sequences_par_niveau WHERE niveau='N09' AND sequence_code='S01'"
                   ).fetchone()
    assert sn["etat_code"] == "en_cours"
    codes = [r[0] for r in c.execute(
        "SELECT o.code FROM objectifs o JOIN sequence_parties p ON p.id=o.partie_id "
        "WHERE p.sequence_par_niveau_id=? ORDER BY o.code", (sn["id"],))]
    # Objectif « Cours » de chaque partie (01, 11) + objectifs du lot connus du référentiel.
    assert codes == ["01", "02", "11", "12"]
    o2 = c.execute("SELECT * FROM objectifs WHERE code='02' AND partie_id IN (SELECT id FROM "
                   "sequence_parties WHERE sequence_par_niveau_id=?)", (sn["id"],)).fetchone()
    assert o2["critere_F"].startswith("Donne le chiffre")
    assert o2["critere_E"] == "Utilise ce savoir-faire pour résoudre un problème."
    etats = {r[0] for r in c.execute("SELECT etat_code FROM exercices WHERE niveau='N09' AND "
                                     "sequence='S01'")}
    assert etats == {"en_cours"}
    assert {r[0] for r in c.execute("SELECT etat_code FROM fiches_resume WHERE niveau='N09' "
                                    "AND sequence='S01'")} == {"en_cours"}
    n = c.execute("SELECT COUNT(*) FROM exercices WHERE niveau='N09' AND sequence='S01' "
                  "AND serie_code IN ('F', 'A', 'E', 'AE')").fetchone()[0]
    assert n == 4 + 1 + 3          # F01 F02 A01 E01, F03, AE01-03 (v0.52.2 : + TP01, AC01)
    assert (base.parent / "images" / "fig-a.png").is_file()
    assert list((base.parent / "sauvegardes").glob("avant_import_lot6e_*.db"))
    assert list((base.parent / "sauvegardes").glob("journal_import_lot6e_*.json"))


def test_sauvegarde_avant_ecriture_contient_la_base_d_origine(base, lots):
    avant = _dump(base, ("exercices",))
    _appliquer(base, lots)
    sauvegarde = next((base.parent / "sauvegardes").glob("avant_import_lot6e_*.db"))
    assert _dump(sauvegarde, ("exercices",)) == avant


def test_deux_applications_donnent_le_meme_etat(base, lots, tmp_path):
    _appliquer(base, lots, tmp_path / "tex")
    etat1 = _dump(base, TABLES_IMPORT)
    _appliquer(base, lots, tmp_path / "tex")
    assert _dump(base, TABLES_IMPORT) == etat1


def test_contenu_modifie_dans_le_lot_est_mis_a_jour_sans_doublon(base, lots):
    _appliquer(base, lots)
    f = lots / "S01" / "S01.json"
    lot = json.loads(f.read_text(encoding="utf-8"))
    lot["objectifs"][0]["exercices"][1]["enonce"] = "F2 corrigé"
    f.write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")
    _appliquer(base, lots)
    c = _conn(base)
    rows = c.execute("SELECT enonce FROM exercices WHERE niveau='N09' AND sequence='S01' AND "
                     "serie_code='F' AND num=2").fetchall()
    assert [r[0] for r in rows] == ["F2 corrigé"]


def test_element_valide_dans_l_atelier_n_est_pas_ecrase(base, lots):
    _appliquer(base, lots)
    c = _conn(base)
    c.execute("UPDATE exercices SET etat_code='valide', enonce='revu par Laurent' WHERE "
              "niveau='N09' AND sequence='S01' AND serie_code='F' AND num=2")
    c.commit()
    r = _essai(base, lots)
    assert any("validé dans l'atelier" in a for a in r.anomalies)
    _appliquer(base, lots)
    assert c.execute("SELECT enonce FROM exercices WHERE niveau='N09' AND sequence='S01' AND "
                     "serie_code='F' AND num=2").fetchone()[0] == "revu par Laurent"


# ── Archivage ────────────────────────────────────────────────────────────────

def test_anciens_exercices_archives_en_codes_x_avant_import_sans_suppression(base, lots):
    c = _conn(base)
    ids_avant = {r[0] for r in c.execute("SELECT id FROM exercices")}
    c.close()
    _appliquer(base, lots)
    c = _conn(base)
    assert ids_avant <= {r[0] for r in c.execute("SELECT id FROM exercices")}
    old = {r["id"]: r["sequence"] for r in c.execute(
        "SELECT id, sequence FROM exercices WHERE id LIKE 'ex_old_%'")}
    assert old == {"ex_old_s01f1": "X01", "ex_old_s03a1": "X03", "ex_old_s16e1": "X16",
                   "ex_old_n08": "X02"}
    # L'ancienne séquence-niveau suit, avec ses objectifs et ses liens.
    sn = c.execute("SELECT * FROM sequences_par_niveau WHERE id='sn_old_n09_s03'").fetchone()
    assert sn["sequence_code"] == "X03"
    assert c.execute("SELECT 1 FROM objectif_exos WHERE objectif_id='ob_old_n09' AND "
                     "exercice_id='ex_old_s03a1'").fetchone()
    assert c.execute("SELECT precedent_seq FROM sequence_par_niveau_precedences WHERE "
                     "sequence_par_niveau_id='sn_old_n09_s03'").fetchone()[0] == "X02"


def test_aucune_collision_de_cle_entre_anciens_et_nouveaux_codes(base, lots):
    _appliquer(base, lots)
    c = _conn(base)
    doublons = c.execute("SELECT niveau, sequence, serie_code, num, COUNT(*) FROM exercices "
                         "GROUP BY 1, 2, 3, 4 HAVING COUNT(*) > 1").fetchall()
    assert doublons == []
    nouveau = c.execute("SELECT id, titre FROM exercices WHERE niveau='N09' AND sequence='S01' "
                        "AND serie_code='F' AND num=1").fetchone()
    assert nouveau["id"] != "ex_old_s01f1" and nouveau["titre"] == "Former des nombres"


def test_archivage_n_est_fait_qu_une_fois_sinon_les_nouveaux_s01_seraient_archives(base, lots):
    _appliquer(base, lots)
    _appliquer(base, lots)
    c = _conn(base)
    # v0.52.2 : séries du livret seulement (+ TP01 et AC01 en séries documents).
    assert c.execute("SELECT COUNT(*) FROM exercices WHERE niveau='N09' AND sequence='S01' "
                     "AND serie_code IN ('F', 'A', 'E', 'AE')").fetchone()[0] == 8
    assert c.execute("SELECT COUNT(*) FROM sequences_du_cycle WHERE cycle_code='C03' AND "
                     "code LIKE 'XX%'").fetchone()[0] == 0


def test_journal_permet_le_retour_arriere(base, lots):
    _appliquer(base, lots)
    j = json.loads(next((base.parent / "sauvegardes").glob("journal_import_lot6e_*.json"))
                   .read_text(encoding="utf-8"))
    ex = next(e for e in j["archivage"] if e.get("table") == "exercices")
    assert ex["ids"]["ex_old_s01f1"] == "S01"
    cle = {e["cle"]: e for e in j["import"]}
    assert cle["N09/S01/F01"]["origine"].startswith("26S2liv#1")


# ── Cycle 3 ──────────────────────────────────────────────────────────────────

def test_c03_remplace_sans_perte_anciennes_sequences_et_themes_archives(base, lots):
    c = _conn(base)
    anciennes = {r["id"]: r["nom"] for r in c.execute(
        "SELECT * FROM sequences_du_cycle WHERE cycle_code='C03'")}
    c.close()
    _appliquer(base, lots)
    c = _conn(base)
    rows = {r["id"]: r for r in c.execute("SELECT * FROM sequences_du_cycle WHERE cycle_code='C03'")}
    assert set(anciennes) <= set(rows)                       # rien de supprimé
    for sid, nom in anciennes.items():
        assert rows[sid]["code"].startswith("X") and rows[sid]["nom"] == nom + " (archive)"
        assert rows[sid]["numero"] > 100
    nouvelles = {r["code"]: r for r in rows.values() if r["code"].startswith("S")}
    assert sorted(nouvelles) == [f"S{i:02d}" for i in range(1, 11)]
    assert nouvelles["S09"]["nom"] == "Proportionnalité"
    themes = {r["code"]: r for r in c.execute("SELECT * FROM themes WHERE cycle_code='C03'")}
    assert {"A", "B", "C", "D", "E", "F", "XA", "XB", "XC"} == set(themes)
    assert themes["E"]["code_couleur"] == "proportionnalite"
    assert nouvelles["S09"]["theme_id"] == themes["E"]["id"]
    assert themes["XA"]["nom"] == "Nombres et Calculs (archive)"
    assert rows[next(i for i in anciennes if rows[i]["code"] == "X16")]["theme_id"] == themes["XC"]["id"]


def test_cycle4_n10_a_n12_intacts_et_references_signalees(base, lots):
    where = {"sequences_par_niveau": "niveau IN ('N10','N11','N12')",
             "exercices": "niveau IN ('N10','N11','N12')",
             "sequences_du_cycle": "cycle_code='C04'", "themes": "cycle_code='C04'",
             "partie_exos_revision_approche": "partie_id IN (SELECT p.id FROM sequence_parties p "
             "JOIN sequences_par_niveau sn ON sn.id = p.sequence_par_niveau_id "
             "WHERE sn.niveau IN ('N10','N11','N12'))"}
    tables = ("sequences_par_niveau", "exercices", "sequences_du_cycle", "themes",
              "sequence_par_niveau_precedences", "partie_exos_revision_approche",
              "referentiel_niveaux", "referentiel_sequences", "referentiel_objectifs")
    c = _conn(base)
    avant_n10 = _dump(base, tables, where)
    c.close()
    r = _essai(base, lots)
    assert any("N10/S01 a pour prérequis N09/S03" in a for a in r.anomalies)
    _appliquer(base, lots)
    apres = _dump(base, tables, where)
    # Précédences et révisions du cycle 4 : inchangées (seules celles du cycle 3 bougent).
    assert apres["sequence_par_niveau_precedences"] != avant_n10["sequence_par_niveau_precedences"]
    for t in tables:
        if t == "sequence_par_niveau_precedences":
            garde = lambda rows: [x for x in rows if ("sequence_par_niveau_id", "sn_n10_s01") in x]
            assert garde(apres[t]) == garde(avant_n10[t])
        else:
            assert apres[t] == avant_n10[t], t
    c = _conn(base)
    # La révision du cycle 4 pointe toujours vers le même exercice (archivé).
    assert c.execute("SELECT exercice_id FROM partie_exos_revision_approche WHERE "
                     "partie_id='pt_n10'").fetchone()[0] == "ex_old_s03a1"


# ── Contenu importé ──────────────────────────────────────────────────────────

def test_remediations_dans_remed_enonce_et_remed_corrige(base, lots):
    _appliquer(base, lots)
    c = _conn(base)
    e = c.execute("SELECT * FROM exercices WHERE niveau='N09' AND sequence='S01' AND "
                  "serie_code='F' AND num=1").fetchone()
    assert e["remed_enonce"] == "Remédiation \\seqACompleter{3}."
    assert e["remed_corrige"] == "Explication."
    assert e["serie"] == "fondamental" and e["enonce"] == "Forme \\seqACompleter{12}."


def test_liens_objectif_exercice_par_serie_dans_l_ordre_du_lot(base, lots):
    _appliquer(base, lots)
    c = _conn(base)
    rows = c.execute(
        "SELECT oe.serie, oe.ordre, e.serie_code, e.num FROM objectif_exos oe "
        "JOIN exercices e ON e.id = oe.exercice_id JOIN objectifs o ON o.id = oe.objectif_id "
        "WHERE e.niveau='N09' AND e.sequence='S01' AND o.code='02' "
        "AND oe.serie IN ('F', 'A', 'E') ORDER BY oe.serie, oe.ordre"   # v0.52.2 : + AE (L1)
    ).fetchall()
    assert [tuple(r) for r in rows] == [("A", 1, "A", 1), ("E", 1, "E", 1),
                                        ("F", 1, "F", 1), ("F", 2, "F", 2)]


def test_activites_en_approche_rattachees_a_la_partie_car_le_livret_ignore_ae_d_objectif(base, lots):
    """L'atelier rattache l'approche à la partie (rôle EA) : c'est ce que
    lisent le livret et le plan de travail (numerotation_livret).
    v0.52.2 (L1) : le lien à la partie est gardé ; l'activité est en plus
    reliée à son objectif (série AE), que la numérotation ignore."""
    _appliquer(base, lots)
    c = _conn(base)
    rows = c.execute(
        "SELECT p.numero, pe.ordre, e.serie_code, e.num, e.serie FROM "
        "partie_exos_revision_approche pe JOIN exercices e ON e.id = pe.exercice_id "
        "JOIN sequence_parties p ON p.id = pe.partie_id WHERE pe.type='EA' AND e.niveau='N09' "
        "AND e.sequence='S01' ORDER BY p.numero, pe.ordre").fetchall()
    assert [tuple(r) for r in rows] == [(1, 1, "AE", 1, "approche"), (1, 2, "AE", 2, "approche"),
                                        (2, 1, "AE", 3, "approche")]
    assert c.execute("SELECT COUNT(*) FROM objectif_exos WHERE serie='AE'").fetchone()[0] == 3
    from services.numerotation_livret import numeroter_sequence
    sn = c.execute("SELECT id FROM sequences_par_niveau WHERE niveau='N09' AND "
                   "sequence_code='S01'").fetchone()[0]
    n = numeroter_sequence(c, sn)
    assert len(n.ordre["R"]) == 3 and len(n.ordre["F"]) == 3


def test_fiche_liee_a_son_objectif_et_attachee_au_cours_de_la_partie(base, lots):
    _appliquer(base, lots)
    c = _conn(base)
    f = c.execute("SELECT f.*, o.code FROM fiches_resume f JOIN objectifs o ON o.id=f.objectif_id "
                  "WHERE f.niveau='N09' AND f.sequence='S01' ORDER BY f.num_fiche").fetchall()
    assert [(r["code"], r["titre"]) for r in f] == [("02", "La valeur d'un chiffre"),
                                                    ("12", "La fraction, un quotient")]
    attache = c.execute("SELECT o.code FROM objectif_fiches of JOIN objectifs o ON "
                        "o.id = of.objectif_id WHERE of.fiche_id=?", (f[0]["id"],)).fetchone()[0]
    assert attache == "01"
    from services.fiches_resume import lire_fiche
    secs = lire_fiche(c, f[0]["id"])["sections"]
    assert [s["titre"] for s in secs] == ["1. Chiffres", "2. Rang"]
    assert secs[1]["items"] == ["Chaque rang vaut \\seqACompleter{dix} fois…"]


def test_sections_de_fiche_texte_avant_la_premiere_section_garde():
    s = imp.sections_fiche("Intro {a}\n\\seqSectionFicheSix{T {1}}\nCorps \\seqACompleter{x}")
    assert s == [{"titre": "", "items": ["Intro {a}"]},
                 {"titre": "T {1}", "items": ["Corps \\seqACompleter{x}"]}]


def test_bloc_pour_s02_n_est_pas_importe_depuis_s01(base, lots):
    _appliquer(base, lots)
    c = _conn(base)
    assert c.execute("SELECT COUNT(*) FROM exercices WHERE enonce='ne pas importer'"
                     ).fetchone()[0] == 0
    assert c.execute("SELECT 1 FROM sequences_par_niveau WHERE niveau='N09' AND "
                     "sequence_code='S02'").fetchone() is None


def test_anomalies_objectif_inconnu_et_figure_manquante(base, lots):
    r = _essai(base, lots)
    assert any("objectif inconnu 'S01-99'" in a for a in r.anomalies)
    assert any("figure manquante absente.png" in a for a in r.anomalies)
    assert "== Anomalies" in r.texte()


def test_rapport_par_sequence_et_par_objectif(base, lots):
    r = _essai(base, lots)
    o = r.sequences["S01"]["objectifs"]["S01-02"]
    assert o["objectif"] == "créé"
    assert o["c"]["exercices F"] == {"créé": 2} and o["c"]["activités AE"] == {"créé": 2}
    assert o["c"]["remédiations"] == {"présentes": 1} and o["c"]["fiche"] == {"créée": 1}


# ── Documents hors base (v0.52.2 : en base, plus de .tex) ────────────────────

def test_plus_de_tex_hors_base_car_les_documents_vont_en_base(base, lots, tmp_path):
    """O1 (v0.52.2) : travaux personnels, activités complémentaires et
    évaluations vont dans l'atelier (séries TP, AC, AT, EV), plus en `.tex`.
    Une évaluation dont le découpage échoue (ici, pas de \\seqExoEval)
    n'est pas importée et est signalée."""
    r = _essai(base, lots)
    _appliquer(base, lots)
    assert not (lots / "documents_tex").exists()
    c = _conn(base)
    series = dict(c.execute("SELECT serie_code, COUNT(*) FROM exercices WHERE niveau='N09' "
                            "AND serie_code IN ('TP','AC','AT','EV') GROUP BY 1").fetchall())
    assert series == {"TP": 1, "AC": 1}
    assert c.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 0
    assert any("non importée : découpage impossible" in a for a in r.anomalies)


# ── Lancement, base, référentiel ─────────────────────────────────────────────

def test_outil_se_lance_par_chemin_comme_sous_windows():
    r = subprocess.run([sys.executable, str(APPLI / "outils" / "import_lot6e.py"), "--help"],
                       cwd=str(APPLI), capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "--apply" in r.stdout


def test_base_par_defaut_celle_du_profil_atelier_et_base_classe_refusee(tmp_path, lots):
    from services import repartition
    racine = tmp_path / "appli"
    (racine / "data").mkdir(parents=True)
    assert imp.resoudre_base(None, racine) == racine / "data" / "seqenseigne.db"
    da = racine / "data_atelier"
    da.mkdir()
    for f in list(DATA.glob("*.csv")):
        shutil.copy(f, da)
    create_app(da, profil="atelier")
    c = _conn(da / "seqenseigne.db")
    repartition.definir_role(c, "atelier")
    c.commit()
    c.close()
    assert imp.resoudre_base(None, racine) == da / "seqenseigne.db"
    c = sqlite3.connect(da / "seqenseigne.db")
    c.execute("UPDATE instance_locale SET role='classe'")
    c.commit()
    c.close()
    assert imp.main(["--db", str(da / "seqenseigne.db"), "--lots", str(lots)]) == 2


def test_objectifs_6e_json_coherent_avec_le_referentiel():
    ref = imp.charger_referentiel()
    assert [s["code"] for s in ref["sequences"]] == [f"S{i:02d}" for i in range(1, 11)]
    assert [t["code"] for t in ref["themes"]] == list("ABCDEF")
    assert {s["code"]: s["theme"] for s in ref["sequences"]}["S10"] == "F"
    objs = [(seq, p["numero"], o["code"]) for seq, ps in ref["parties"].items() for p in ps
            for o in p["objectifs"]]
    assert len(objs) == 22
    assert all(int(code[0]) + 1 == num for _, num, code in objs)    # 02 en partie 1, 12 en 2…


def test_couleur_proportionnalite_connue_de_l_appli():
    from services.couleurs_themes import slugs_valides
    from services.latex_rendu_atome import THEMES_VALIDES
    from services.referentiel_principal_externe import COULEURS_THEMES
    assert "proportionnalite" in slugs_valides()
    assert "proportionnalite" in THEMES_VALIDES
    assert "proportionnalite" in dict(COULEURS_THEMES)


def test_modele_programme_du_cycle_sans_archives_ni_objectifs_csv_d_une_autre_sequence(base, lots):
    from services import modeles_referentiel as mdl
    _appliquer(base, lots)
    c = _conn(base)
    m = mdl.lister(c, base.parent, "N09", "principal")[0]["modele"]
    assert [t["code"] for t in m["themes"]] == list("ABCDEF")
    # Seule S01 a des objectifs N09 dans l'atelier ; S04 « Pré-algèbre » ne
    # reçoit pas les objectifs CSV de l'ancienne S04 ; aucune archive.
    assert [s["nom"] for s in m["sequences"]] == ["Nombres entiers et décimaux, fractions"]


# ── Bases d'avant v0.14.7 : clés étrangères restées sur objectifs_v2 ─────────
# Cas réel (base atelier de Laurent, 18 octobre) : le renommage
# objectifs_v2 → objectifs de v0.14.7 n'avait pas réécrit les références des
# tables de liens. L'import plantait sur « FOREIGN KEY constraint failed »
# dès le premier lien objectif ↔ exercice d'un objectif nouvellement créé.

TABLES_V2 = ("objectif_exos", "objectif_notions", "objectif_fiches", "objectif_cartes",
             "fiches_resume", "evaluation_objectifs", "ui_etat_atelier_sequence")


def _vieillir(db, orphelin=False):
    """Remet la base dans l'état des bases anciennes : une table objectifs_v2
    (copie de objectifs) et les tables de liens qui pointent dessus."""
    c = sqlite3.connect(db)
    ddl = c.execute("SELECT sql FROM sqlite_master WHERE name='objectifs'").fetchone()[0]
    c.execute(ddl.replace("CREATE TABLE objectifs", "CREATE TABLE objectifs_v2", 1))
    c.execute("INSERT INTO objectifs_v2 SELECT * FROM objectifs")
    if orphelin:
        # Lien vers un objectif qui n'existe que dans objectifs_v2 (supprimé
        # depuis de objectifs) : invisible pour l'appli, mais il violerait la
        # contrainte une fois redirigée.
        c.execute("INSERT INTO objectifs_v2 (id, partie_id, code, nom) "
                  "VALUES ('ob_fantome', 'pt_n10', '99', 'fantôme')")
        c.execute("INSERT INTO objectif_exos (objectif_id, serie, exercice_id, ordre) "
                  "VALUES ('ob_fantome', 'F', 'ex_n10_f1', 1)")
        c.commit()
    v = c.execute("PRAGMA schema_version").fetchone()[0]
    c.execute("PRAGMA writable_schema = ON")
    for t in TABLES_V2:
        sql = c.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()[0]
        c.execute("UPDATE sqlite_master SET sql=? WHERE name=?",
                  (sql.replace("REFERENCES objectifs(", "REFERENCES objectifs_v2("), t))
    c.execute(f"PRAGMA schema_version = {v + 1}")
    c.commit()
    c.execute("PRAGMA writable_schema = OFF")
    c.close()


def _cibles_fk(db, cible):
    c = sqlite3.connect(db)
    try:
        return sorted(t for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                      if any(r[2] == cible for r in c.execute(f'PRAGMA foreign_key_list("{t}")')))
    finally:
        c.close()


def test_base_ancienne_reproduit_l_echec_de_lien_vers_un_objectif_neuf(base):
    _vieillir(base)
    c = sqlite3.connect(base)
    c.execute("PRAGMA foreign_keys = ON")
    _ins(c, "objectifs", id="ob_neuf", partie_id="pt_n10", code="03", nom="neuf")
    with pytest.raises(sqlite3.IntegrityError):
        _ins(c, "objectif_exos", objectif_id="ob_neuf", serie="F", exercice_id="ex_n10_f1",
             ordre=2)
    c.close()


def test_import_sur_base_ancienne_redirige_les_cles_puis_importe(base, lots):
    _vieillir(base)
    r = _essai(base, lots)
    assert any("objectifs_v2" in i for i in r.infos)
    assert len(_cibles_fk(base, "objectifs_v2")) == len(TABLES_V2)   # essai : base intacte
    _appliquer(base, lots)
    assert _cibles_fk(base, "objectifs_v2") == []
    assert set(TABLES_V2) <= set(_cibles_fk(base, "objectifs"))
    c = _conn(base)
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert c.execute("SELECT COUNT(*) FROM objectif_exos WHERE objectif_id='ob_n10'").fetchone()[0] == 1
    c.close()
    _appliquer(base, lots)                                               # idempotent


def test_redirection_sauvegarde_puis_retire_les_liens_orphelins(base, tmp_path):
    from services import retraits
    _vieillir(base, orphelin=True)
    c = _conn(base)
    res = retraits.rediriger_objectifs_v2(c, tmp_path)
    assert res["orphelins"] == {"objectif_exos.objectif_id": 1}
    sauve = json.loads(Path(res["sauvegarde"]).read_text(encoding="utf-8"))
    assert sauve["orphelins"]["objectif_exos.objectif_id"][0]["objectif_id"] == "ob_fantome"
    assert c.execute("SELECT COUNT(*) FROM objectif_exos WHERE objectif_id='ob_fantome'"
                     ).fetchone()[0] == 0
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    assert retraits.rediriger_objectifs_v2(c, tmp_path) is None          # idempotent
    c.close()


def test_demarrage_de_l_appli_repare_puis_retire_objectifs_v2(base):
    _vieillir(base)
    create_app(base.parent, profil="atelier")
    c = sqlite3.connect(base)
    assert c.execute("SELECT name FROM sqlite_master WHERE name='objectifs_v2'").fetchone() is None
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    c.close()
    assert _cibles_fk(base, "objectifs_v2") == []
