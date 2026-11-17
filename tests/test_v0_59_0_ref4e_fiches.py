"""tests/test_v0_59_0_ref4e_fiches.py — v0.59.0

Référentiel de 4e au modèle « Fiches », version 1 (avant le premier lot de 4e ;
`doc/redemarrage_v0_59_0.md`, décisions D1 à D7 ; décisions de Laurent du
16 novembre 2026, point 10 : réponses par défaut des 20 points, sauf les cartes
d'automatisme, rattachées aux objectifs et absentes du livret).

Invariants protégés :
  D1 archivage de la structure de 2025 d'un niveau du cycle 4 : essai à blanc
     sans écriture, idempotent, réversible ; séquence-niveau, parties,
     objectifs, liens et atomes passent sous l'archive « X + ancien numéro »
     (identifiants inchangés, `fichier` inchangé) ; référentiels figés (tables
     `referentiel_*`, fichiers `referentiels\\`), autres niveaux et X02/X04/X10
     intacts ;
  D2 l'import d'un lot de 4e REFUSE de s'appliquer tant que la structure de 2025
     n'est pas archivée (sinon il réécrirait A1-02 et F01 de 2025) ; hors 6e il
     n'écrit jamais dans les thèmes et séquences du cycle ; libellés de parties
     et titre court en base ; second passage nul ; la 6e garde ses globaux ;
  D3 cartes d'automatisme des lots : rattachées à leur objectif, niveau de
     création gardé, carte validée jamais réécrite ;
  D4 référentiel interne : année choisie à la création (2027-2028 créé en
     novembre 2026), option « cartes d'automatisme » du modèle Fiches, qui fait
     compter dans la validation les cartes rattachées (et elles seules) ;
  D5/D6 livret Fiches de 4e : titre court et libellés de parties en base ;
  transcription : `outils/objectifs_4e.json` = `outils/ref4e_v1.md`.
"""

from __future__ import annotations

import datetime
import json
import re
import shutil
import sqlite3
from pathlib import Path

import pytest

from outils import archiver_structure_niveau as arch
from outils import import_lot6e as imp
from outils import migrer_themes_codes_2027 as mig
from services import fiches_cycle4 as fc4
from tests.test_v0_52_0_import_lot6e import base as base_v052  # noqa: F401
from tests.test_v0_58_0_migration_themes_codes import (  # noqa: F401
    RECL,
    _ins,
    _migrer,
    _q,
    _tables,
    base,
)

APPLI = Path(__file__).resolve().parent.parent
LOT_ESSAI = APPLI / "tests" / "donnees" / "lot4e_essai"


@pytest.fixture(autouse=True)
def _table_reduite(tmp_path, monkeypatch):
    p = tmp_path / "reclassement_test.json"
    p.write_text(json.dumps(RECL), encoding="utf-8")
    monkeypatch.setattr(mig, "RECLASSEMENT", p)


@pytest.fixture
def base4e(base):
    """Base migrée (codes A1) + une 4e de 2025 en N11 (A1 : partie, objectif
    A1-02 « ancien » lié à l'exercice F01 et à une carte ; B1 : un exercice),
    un référentiel verrouillé avec instantané (comme 2025_N11b), une
    précédence de 3e qui vise N11/A1."""
    r, _, _ = _migrer(base)
    assert not r.anomalies
    c = sqlite3.connect(base)
    _ins(c, "sequences_par_niveau", id="sn_n11_a1", niveau="N11", sequence_code="A1",
         parametres="")
    _ins(c, "sequence_parties", id="pt_n11_a1", sequence_par_niveau_id="sn_n11_a1", numero=1)
    _ins(c, "objectifs", id="ob_n11_a1_02", partie_id="pt_n11_a1", code="02",
         nom="Ancien objectif de 2025")
    _ins(c, "exercices", id="ex_n11_a1_f1", serie="fondamental", titre="ancien F01",
         enonce="ancien énoncé", niveau="N11", sequence="A1", num=1, serie_code="F",
         fichier="N11A1F01.tex", variables="", etat_code="valide")
    _ins(c, "objectif_exos", objectif_id="ob_n11_a1_02", serie="F", exercice_id="ex_n11_a1_f1",
         ordre=1)
    _ins(c, "cartes_automatisme", id="crt_n11_a1", niveau="N11", sequence="A1", num=1,
         titre="ancienne carte", recto="r", verso="v", ordre=1)
    _ins(c, "objectif_cartes", objectif_id="ob_n11_a1_02", carte_id="crt_n11_a1", ordre=1)
    _ins(c, "exercices", id="ex_n11_b1_f1", serie="fondamental", titre="rotation",
         enonce="rotation", niveau="N11", sequence="B1", num=1, serie_code="F",
         fichier="N11B1F01.tex", variables="", etat_code="en_cours")
    _ins(c, "sequences_par_niveau", id="sn_n12_b1", niveau="N12", sequence_code="B1",
         parametres="")
    _ins(c, "sequence_par_niveau_precedences", sequence_par_niveau_id="sn_n12_b1",
         precedent_niveau="N11", precedent_seq="A1", ordre=1)
    _ins(c, "referentiel_niveaux", id="2025_N11b", niveau="N11", version="2025b",
         etat="verrouille", source="interne", type_ref="principal")
    _ins(c, "referentiel_sequences", referentiel_id="2025_N11b", code="S03", numero=3,
         nom="Calcul numérique", theme_code=None)
    _ins(c, "referentiel_objectifs", referentiel_id="2025_N11b", seq_code="S03", code="02",
         nom="Figé", critere_f="f", critere_a="a", critere_e="e")
    c.commit()
    c.close()
    return base


def _referentiels(db) -> dict:
    t = _tables(db)
    return {k: v for k, v in t.items() if k.startswith("referentiel_")}


def _fichiers(d: Path) -> dict:
    r = d / "referentiels"
    return {str(p.relative_to(r)): p.read_bytes() for p in sorted(r.rglob("*")) if p.is_file()}


def _archiver(db, *extra) -> int:
    return arch.main(["--niveau", "N11", "--db", str(db), *extra])


def _lots(tmp_path) -> Path:
    d = tmp_path / "lot4e"
    shutil.copytree(LOT_ESSAI, d)
    return d


def _importer(db, lots, *extra) -> int:
    return imp.main(["--niveau", "N11", "--db", str(db), "--lots", str(lots), *extra])


# ── D1 Archivage ─────────────────────────────────────────────────────────────

def test_archivage_essai_a_blanc_par_defaut_n_ecrit_rien(base4e, capsys):
    avant = base4e.read_bytes()
    assert _archiver(base4e) == 0
    assert base4e.read_bytes() == avant
    out = capsys.readouterr().out
    assert "N11/A1 → N11/X03" in out and "essai à blanc" in out


def test_archivage_range_la_4e_de_2025_sous_l_ancien_numero_sans_changer_les_identifiants(
        base4e):
    """Sinon l'import du lot A1 réécrirait l'objectif A1-02 de 2025 (et ses
    liens) et l'exercice F01 : l'archive garde la 4e de 2025 entière."""
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _q(base4e, "SELECT sequence_code FROM sequences_par_niveau WHERE id='sn_n11_a1'") \
        == [("X03",)]
    # Partie, objectif et liens suivent par identifiant.
    assert _q(base4e, "SELECT exercice_id FROM objectif_exos WHERE objectif_id='ob_n11_a1_02'") \
        == [("ex_n11_a1_f1",)]
    assert _q(base4e, "SELECT carte_id FROM objectif_cartes WHERE objectif_id='ob_n11_a1_02'") \
        == [("crt_n11_a1",)]
    # Atomes : séquence d'archive, `fichier` inchangé (un scan ne recrée rien).
    assert _q(base4e, "SELECT sequence, fichier FROM exercices WHERE id='ex_n11_a1_f1'") \
        == [("X03", "N11A1F01.tex")]
    assert _q(base4e, "SELECT sequence FROM exercices WHERE id='ex_n11_b1_f1'") == [("X11",)]
    assert _q(base4e, "SELECT sequence FROM cartes_automatisme WHERE id='crt_n11_a1'") \
        == [("X03",)]
    # Séquence du cycle d'archive : n° 100 + ancien numéro, thème de A1.
    x03 = _q(base4e, "SELECT numero, nom, theme_id FROM sequences_du_cycle WHERE "
                     "cycle_code='C04' AND code='X03'")
    a1 = _q(base4e, "SELECT theme_id FROM sequences_du_cycle WHERE cycle_code='C04' AND "
                    "code='A1'")
    assert x03 == [(103, "Calcul numérique (archive)", a1[0][0])]
    # La précédence de 3e vise le contenu de 2025.
    assert _q(base4e, "SELECT precedent_seq FROM sequence_par_niveau_precedences WHERE "
                      "sequence_par_niveau_id='sn_n12_b1'") == [("X03",)]
    # Plus aucune séquence-niveau vivante en N11 ; la marque est posée.
    assert _q(base4e, "SELECT COUNT(*) FROM sequences_par_niveau WHERE niveau='N11' AND "
                      "sequence_code NOT LIKE 'X%'") == [(0,)]
    c = sqlite3.connect(base4e)
    # A2 : copies en 4e du reclassement de la migration (table réduite des tests).
    assert fc4.archivage(c, "N11")["resume"] == "A1→X03, A2→X15, B1→X11"
    c.close()


def test_archivage_ne_touche_ni_aux_referentiels_figes_ni_aux_autres_niveaux(base4e):
    """N11_v2025 « utilisé » et 2025_N11b « verrouillé » : instantanés et PDF
    identiques ; N10 et les archives X02/X04/X10 de la migration non plus."""
    refs, fichiers = _referentiels(base4e), _fichiers(base4e.parent)
    n10 = _q(base4e, "SELECT * FROM exercices WHERE niveau='N10' ORDER BY id")
    x = _q(base4e, "SELECT * FROM sequences_du_cycle WHERE code IN ('X02','X04','X10') "
                   "ORDER BY code")
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _referentiels(base4e) == refs
    assert _fichiers(base4e.parent) == fichiers
    assert b"%PDF fige" in fichiers.values()
    assert _q(base4e, "SELECT * FROM exercices WHERE niveau='N10' ORDER BY id") == n10
    assert _q(base4e, "SELECT * FROM sequences_du_cycle WHERE code IN ('X02','X04','X10') "
                      "ORDER BY code") == x


def test_archivage_idempotent_le_second_passage_dit_rien_a_faire(base4e, capsys):
    assert _archiver(base4e, "--apply", "--yes") == 0
    apres = _tables(base4e)
    capsys.readouterr()
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert "rien à faire" in capsys.readouterr().out
    assert _tables(base4e) == apres


def test_archivage_annuler_rend_la_base_d_origine_table_par_table(base4e):
    avant = _tables(base4e)
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _archiver(base4e, "--annuler", "--yes") == 0
    assert _tables(base4e) == avant


def test_archivage_annuler_refuse_apres_import_d_un_lot(base4e, tmp_path, capsys):
    """Le lot a recréé N11/A1 : l'annulation mêlerait 2025 et 2027 (restaurer
    plutôt la sauvegarde, que le message nomme)."""
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _importer(base4e, _lots(tmp_path), "--apply", "--yes") == 0
    apres = _tables(base4e)
    capsys.readouterr()
    assert _archiver(base4e, "--annuler", "--yes") == 2
    out = capsys.readouterr().out
    assert "N11/A1 : une séquence-niveau a été créée depuis l'archivage" in out
    assert "sauvegarde" in out
    assert _tables(base4e) == apres


def test_archivage_refuse_un_niveau_hors_cycle_4(base4e, capsys):
    assert arch.main(["--niveau", "N09", "--db", str(base4e)]) == 2
    assert "seuls les niveaux du cycle 4" in capsys.readouterr().out


# ── D2 Import des lots de 4e ─────────────────────────────────────────────────

def test_import_4e_refuse_sans_archivage_avec_un_message_clair(base4e, tmp_path, capsys):
    avant = base4e.read_bytes()
    lots = _lots(tmp_path)
    assert _importer(base4e, lots) == 2
    assert _importer(base4e, lots, "--apply", "--yes") == 2
    out = capsys.readouterr().out
    assert "structure de 2025 de N11 non archivée" in out
    assert "archiver_structure_niveau.py --niveau N11 --apply" in out
    assert base4e.read_bytes() == avant
    # Appel direct (outils, tests) : même refus.
    c = sqlite3.connect(base4e)
    with pytest.raises(imp.ImportErreur, match="non archivée"):
        imp.executer(c, imp.charger_lots(lots), json.loads(
            (APPLI / "outils" / "objectifs_4e.json").read_text(encoding="utf-8")),
            imp.Rapport(), base4e.parent / "images", ecrire_fichiers=False, niveau="N11")
    c.close()


def test_import_4e_apres_archivage_cree_la_sequence_sans_toucher_au_cycle_ni_a_l_archive(
        base4e, tmp_path):
    lots = _lots(tmp_path)
    assert _archiver(base4e, "--apply", "--yes") == 0
    cycle = _q(base4e, "SELECT * FROM sequences_du_cycle ORDER BY id")
    themes = _q(base4e, "SELECT * FROM themes ORDER BY id")
    archive = _q(base4e, "SELECT id, titre, enonce, sequence FROM exercices WHERE "
                         "sequence LIKE 'X%' AND niveau='N11' ORDER BY id")
    refs = _referentiels(base4e)
    assert _importer(base4e, lots, "--apply", "--yes") == 0
    assert _q(base4e, "SELECT * FROM sequences_du_cycle ORDER BY id") == cycle
    assert _q(base4e, "SELECT * FROM themes ORDER BY id") == themes
    assert _q(base4e, "SELECT id, titre, enonce, sequence FROM exercices WHERE "
                      "sequence LIKE 'X%' AND niveau='N11' ORDER BY id") == archive
    assert _referentiels(base4e) == refs
    sn = _q(base4e, "SELECT id, titre_court FROM sequences_par_niveau WHERE niveau='N11' AND "
                    "sequence_code='A1'")
    assert sn[0][1] == "Nombres relatifs : produits et quotients"
    assert _q(base4e, "SELECT numero, libelle FROM sequence_parties WHERE "
                      "sequence_par_niveau_id=?", (sn[0][0],)) \
        == [(1, "Produits et quotients de relatifs")]
    objs = _q(base4e, "SELECT o.code, o.nom FROM objectifs o JOIN sequence_parties p ON "
                      "p.id=o.partie_id WHERE p.sequence_par_niveau_id=? ORDER BY o.code",
              (sn[0][0],))
    assert objs == [("01", "Connaître le cours"), ("02", "Multiplier deux nombres relatifs"),
                    ("03", "Diviser deux nombres relatifs")]
    # Nouvel exercice F01 distinct de l'ancien (archivé en X03).
    assert _q(base4e, "SELECT titre FROM exercices WHERE niveau='N11' AND sequence='A1' AND "
                      "serie_code='F' AND num=1") == [("Le signe d'abord",)]


def test_import_4e_second_passage_nul(base4e, tmp_path):
    lots = _lots(tmp_path)
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _importer(base4e, lots, "--apply", "--yes") == 0
    apres = _tables(base4e)
    assert _importer(base4e, lots, "--apply", "--yes") == 0
    assert _tables(base4e) == apres


def test_import_4e_rend_les_globaux_de_la_6e(base4e, tmp_path):
    """Les fonctions de l'outil lisent NIVEAU, CYCLE, REFERENTIEL : un import
    de 4e ne doit pas laisser l'outil réglé sur N11 (la 6e réimporterait en 4e)."""
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _importer(base4e, _lots(tmp_path), "--apply", "--yes") == 0
    assert (imp.NIVEAU, imp.CYCLE, imp.REFERENTIEL.name) == ("N09", "C03", "objectifs_6e.json")


def test_import_4e_ignore_un_lot_de_mise_en_route(base4e, tmp_path):
    lots = _lots(tmp_path)
    (lots / "M01").mkdir()
    (lots / "M01" / "M01.json").write_text(json.dumps({"sequence": "M01", "objectifs": []}),
                                           encoding="utf-8")
    assert _archiver(base4e, "--apply", "--yes") == 0
    c = sqlite3.connect(base4e)
    r = imp.Rapport()
    ref = json.loads((APPLI / "outils" / "objectifs_4e.json").read_text(encoding="utf-8"))
    imp.executer(c, imp.charger_lots(lots), ref, r, base4e.parent / "images",
                 ecrire_fichiers=False, niveau="N11")
    c.rollback()
    c.close()
    assert any("M01 : mise en route hors 6e" in a for a in r.anomalies)


# ── D3 Cartes d'automatisme des lots ─────────────────────────────────────────

def test_cartes_du_lot_rattachees_a_leur_objectif_avec_le_niveau_de_creation(base4e, tmp_path):
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _importer(base4e, _lots(tmp_path), "--apply", "--yes") == 0
    rows = _q(base4e, "SELECT c.num, c.niveau_creation, c.type_tech, c.etat_code, o.code "
                      "FROM cartes_automatisme c JOIN objectif_cartes oc ON oc.carte_id=c.id "
                      "JOIN objectifs o ON o.id=oc.objectif_id WHERE c.niveau='N11' AND "
                      "c.sequence='A1' ORDER BY c.num")
    assert rows == [(1, "N11", "fixe", "en_cours", "02"), (2, "N10", "parametree", "en_cours", "03")]
    c = sqlite3.connect(base4e)
    cartes = fc4.cartes_rattachees(c, "N11")
    c.close()
    # L'ancienne carte archivée (X03) n'est pas du périmètre.
    assert [(x["num"], x["objectifs"]) for x in cartes] == [(1, ["A1-02"]), (2, ["A1-03"])]


def test_carte_validee_dans_l_atelier_jamais_reecrite(base4e, tmp_path):
    lots = _lots(tmp_path)
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _importer(base4e, lots, "--apply", "--yes") == 0
    c = sqlite3.connect(base4e)
    c.execute("UPDATE cartes_automatisme SET etat_code='valide', verso='verso de Laurent' "
              "WHERE niveau='N11' AND sequence='A1' AND num=1")
    c.commit()
    c.close()
    assert _importer(base4e, lots, "--apply", "--yes") == 0
    assert _q(base4e, "SELECT verso FROM cartes_automatisme WHERE niveau='N11' AND "
                      "sequence='A1' AND num=1") == [("verso de Laurent",)]


def test_carte_de_type_inconnu_refusee_et_signalee(base4e, tmp_path):
    lots = _lots(tmp_path)
    p = lots / "A1" / "A1.json"
    lot = json.loads(p.read_text(encoding="utf-8"))
    lot["objectifs"][0]["cartes_automatisme"][0]["type_pedago"] = "inconnu"
    p.write_text(json.dumps(lot, ensure_ascii=False), encoding="utf-8")
    assert _archiver(base4e, "--apply", "--yes") == 0
    c = sqlite3.connect(base4e)
    r = imp.Rapport()
    imp.executer(c, imp.charger_lots(lots), json.loads(
        (APPLI / "outils" / "objectifs_4e.json").read_text(encoding="utf-8")), r,
        base4e.parent / "images", ecrire_fichiers=False, niveau="N11")
    n = c.execute("SELECT COUNT(*) FROM cartes_automatisme WHERE niveau='N11' AND "
                  "sequence='A1'").fetchone()[0]
    c.rollback()
    c.close()
    assert n == 1
    assert any("type pédagogique 'inconnu' inconnu" in a for a in r.anomalies)


# ── D4 Référentiel interne de 4e ─────────────────────────────────────────────

def test_annee_choisie_a_la_creation_donne_le_referentiel_2027_2028(base4e):
    from services import referentiels as svc
    from services.referentiel_principal_externe import nom_calcule
    nov = datetime.date(2026, 11, 16)
    assert svc.annees_proposees(nov) == ["2026-2027", "2027-2028"]
    assert svc.normaliser_annee_choisie("2027-2028", nov) == "2027"
    for refus in ("2025-2026", "2028", "2027-2029", "deux mille"):
        with pytest.raises(ValueError):
            svc.normaliser_annee_choisie(refus, nov)
    c = sqlite3.connect(base4e)
    c.row_factory = sqlite3.Row
    ref = svc.creer_coquille(c, "N11", maintenant=nov, annee="2027-2028")
    assert ref["id"] == "2027_N11"
    r = dict(c.execute("SELECT * FROM referentiel_niveaux WHERE id='2027_N11'").fetchone())
    assert nom_calcule(r) == "4e — 2027-2028 — Principal"
    # Sans année : l'année en cours, comme avant.
    assert svc.creer_coquille(c, "N11", maintenant=nov)["id"] == "2026_N11"
    c.close()


def _client(db):
    from app import create_app
    return create_app(db.parent, profil="atelier").test_client()


def test_route_creation_annee_et_option_cartes(base4e):
    cl = _client(base4e)
    r = cl.post("/api/referentiels/coquille", json={"niveau": "N11", "gabarit": "cycle4",
                                                     "cartes_automatisme": True})
    assert r.status_code == 400 and "modèle « Fiches" in r.get_json()["error"]
    r = cl.post("/api/referentiels/coquille", json={"niveau": "N11", "gabarit": "sixieme",
                                                     "annee": "1999-2000"})
    assert r.status_code == 400
    assert _q(base4e, "SELECT COUNT(*) FROM referentiel_niveaux WHERE niveau='N11' AND "
                      "etat='en_cours'") == [(0,)]
    an = datetime.date.today().year + (1 if datetime.date.today().month >= 8 else 0)
    r = cl.post("/api/referentiels/coquille", json={"niveau": "N11", "gabarit": "sixieme",
                                                     "annee": f"{an}-{an + 1}",
                                                     "cartes_automatisme": True})
    assert r.status_code == 201, r.get_json()
    ref = r.get_json()["ref"]
    assert ref["id"] == f"{an}_N11" and ref["cartes_automatisme"] is True
    liste = cl.get("/api/referentiels?niveau=N11").get_json()["referentiels"]
    assert [x.get("cartes_automatisme") for x in liste if x["id"] == ref["id"]] == [True]
    # Les autres référentiels de la liste n'ont pas la clé (listes inchangées).
    assert all("cartes_automatisme" not in x for x in liste if x["id"] != ref["id"])


def test_validation_avec_option_compte_les_cartes_rattachees_et_elles_seules(base4e, tmp_path):
    """Au modèle Fiches sans option, les cartes ne comptent pas (6e) ; avec
    l'option, une carte rattachée non validée bloque, une carte d'archive
    (2025) ou sans objectif ne compte pas."""
    from services.referentiel_validation import evaluer_eligibilite_validation
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _importer(base4e, _lots(tmp_path), "--apply", "--yes") == 0
    c = sqlite3.connect(base4e)
    c.row_factory = sqlite3.Row
    _ins(c, "cartes_automatisme", id="crt_libre", niveau="N11", sequence="A1", num=50,
         titre="sans objectif", ordre=50)
    for rid, version, opt in (("2027_N11", "2027", 1), ("2027_N11b", "2027b", 0)):
        _ins(c, "referentiel_niveaux", id=rid, niveau="N11", version=version,
             etat="en_cours", source="interne",
             type_ref="principal", gabarit_documents="sixieme", cartes_automatisme=opt)
    c.commit()
    avec = evaluer_eligibilite_validation(c, "2027_N11")
    sans = evaluer_eligibilite_validation(c, "2027_N11b")
    c.close()
    assert avec["cartes_automatisme"] is True
    assert avec["details"]["atomes_non_valides"]["cartes_automatisme"] == 2
    assert "2 cartes d'automatisme non validé(e)s" in avec["raisons"]
    assert sans["details"]["atomes_non_valides"]["cartes_automatisme"] == 0


def test_apercu_avant_creation_annonce_les_cartes_rattachees(base4e, tmp_path):
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _importer(base4e, _lots(tmp_path), "--apply", "--yes") == 0
    cl = _client(base4e)
    a = cl.get("/api/referentiels/apercu-creation?niveau=N11&type_ref=principal&gabarit=sixieme"
               "&cartes=1").get_json()["apercu"]
    assert (a["cartes_automatisme"], a["nb_cartes"], a["cartes_non_valides"]) == (True, 2, 2)
    assert a["nb_sequences"] == 1 and a["nb_objectifs"] == 2
    b = cl.get("/api/referentiels/apercu-creation?niveau=N11&type_ref=principal&gabarit=sixieme"
               ).get_json()["apercu"]
    assert (b["cartes_automatisme"], b["nb_cartes"]) == (False, 0)


def test_atelier_n11_suit_le_modele_du_referentiel_2027(base4e):
    from services import gabarits_documents as gd
    c = sqlite3.connect(base4e)
    _ins(c, "referentiel_niveaux", id="2027_N11", niveau="N11", version="2027", etat="en_cours",
         source="interne", type_ref="principal", gabarit_documents="sixieme")
    assert gd.referentiel_atelier_du_niveau(c, "N11") == "2027_N11"
    assert gd.gabarit_atelier_du_niveau(c, "N11") == "sixieme"
    c.close()


def test_referentiel_fige_de_2025_ni_deverrouillable_ni_recompilable_apres_archivage(base4e):
    """Point 16 : 2025_N11b recalculerait son instantané sur l'atelier (devenu
    la nouvelle 4e) ; ses documents se recompileraient depuis les archives. Un
    référentiel 2027 garde le déverrouillage ; la 5e n'est pas concernée."""
    c = sqlite3.connect(base4e)
    _ins(c, "referentiel_documents", id="rd_n11b", referentiel_id="2025_N11b",
         type_document="livret_sequence", options='{"actif": true}')
    _ins(c, "referentiel_niveaux", id="2027_N11", niveau="N11", version="2027",
         etat="verrouille", source="interne", type_ref="principal")
    _ins(c, "referentiel_niveaux", id="2025_N10z", niveau="N10", version="2025z",
         etat="verrouille", source="interne", type_ref="principal")
    c.commit()
    c.close()
    cl = _client(base4e)
    assert _archiver(base4e, "--apply", "--yes") == 0
    r = cl.post("/api/referentiels/2025_N11b/deverrouiller")
    assert r.status_code == 409 and "structure de 2025 de N11 est archivée" in r.get_json()["error"]
    assert _q(base4e, "SELECT etat FROM referentiel_niveaux WHERE id='2025_N11b'") \
        == [("verrouille",)]
    r = cl.post("/api/referentiels/2025_N11b/documents/rd_n11b/compiler")
    assert r.status_code == 409 and r.get_json()["error"] == "structure_archivee"
    assert cl.post("/api/referentiels/2027_N11/deverrouiller").status_code == 200
    assert cl.post("/api/referentiels/2025_N10z/deverrouiller").status_code == 200


# ── D5/D6 Livret Fiches de 4e ────────────────────────────────────────────────

def test_livret_4e_titre_court_et_libelle_de_partie_sans_carte(base4e, tmp_path):
    from services import livret_sequence_6e as l6
    assert _archiver(base4e, "--apply", "--yes") == 0
    assert _importer(base4e, _lots(tmp_path), "--apply", "--yes") == 0
    c = sqlite3.connect(base4e)
    c.row_factory = sqlite3.Row
    seq = l6.lire_sequence_6e(c, "N11", "A1")
    # Couverture, en-tête et corps (le document complet demande les tables du
    # paquet, absentes de la base de test ; la compilation est vérifiée à part).
    tex = "\n".join([l6.entete(seq, False), l6.couverture(seq), *l6.corps_livret(
        seq, l6.normaliser_options(None)), *l6.macros_niveau(c, "N11")])
    c.close()
    assert seq["nom"] == "Nombres relatifs : produits et quotients"
    assert seq["nom_cycle"] == "Calcul numérique"
    assert r"\seqCouvertureLivretSix*{Nombres relatifs : produits et quotients}" in tex
    assert r"\fancyhead[R]{\small\bfseries Nombres relatifs : produits et quotients" in tex
    assert r"\seqPartieSuiviSix{Partie 1 --- Produits et quotients de relatifs}" in tex
    assert r"\renewcommand{\seqNiveauCourt}{4e}" in tex
    # Décision du 16 novembre : pas de cartes d'automatisme dans le livret.
    assert "Signe d'un produit de relatifs" not in tex


def test_livret_6e_garde_le_nom_du_cycle_et_les_libelles_du_json(base4e):
    """Sans titre court ni libellé en base (6e), rien ne change."""
    from services import livret_sequence_6e as l6
    c = sqlite3.connect(base4e)
    c.row_factory = sqlite3.Row
    assert fc4.titre_court(c, "N09", "A1") == ""
    assert l6.libelles_parties_base(c, "N11", "ZZ") == {}
    c.close()


# ── Transcription du référentiel ─────────────────────────────────────────────

def _lire_ref4e_md() -> dict:
    """Lecture indépendante de outils/ref4e_v1.md : {séquence: [(numéro,
    libellé, [(code, nom, F, A)])]} et titres courts."""
    texte = (APPLI / "outils" / "ref4e_v1.md").read_text(encoding="utf-8")
    debut, fin = texte.index("\n## A1 — "), texte.index("\n## Cartes d'automatisme")
    out = {}
    for bloc in re.split(r"\n(?=## [A-E]\d — )", texte[debut:fin])[1:]:
        seq = bloc[3:5]
        parties, cur = [], None
        lignes = bloc.splitlines()
        for i, l in enumerate(lignes):
            m = re.match(r"^### Partie (\d+) — (.+)$", l)
            if m:
                cur = (int(m.group(1)), m.group(2).strip(), [])
                parties.append(cur)
            m = re.match(rf"^\*\*{seq}-(\d\d) · (.+?)\*\*", l)
            if m:
                f, a = re.match(r"^- F : « (.+?) » · A : « (.+) »\s*$", lignes[i + 2]).groups()
                cur[2].append((m.group(1), m.group(2).strip(), f, a))
        out[seq] = parties
    courts = dict(re.findall(r"^\| S\d\d \| ([A-E]\d) \| \d+ \| .+? \| (.+?) \| [A-E] \|$", texte,
                             re.M))
    return out, courts


def test_objectifs_4e_json_transcrit_exactement_le_referentiel(tmp_path):
    md, courts = _lire_ref4e_md()
    ref = json.loads((APPLI / "outils" / "objectifs_4e.json").read_text(encoding="utf-8"))
    assert (ref["niveau"], ref["cycle"]) == ("N11", "C04")
    js = {seq: [(p["numero"], p["libelle"], [(o["code"], o["nom"], o["critere_F"],
                                              o["critere_A"]) for o in p["objectifs"]])
                for p in ps] for seq, ps in ref["parties"].items()}
    assert js == md
    assert {s["code"]: s["titre_court"] for s in ref["sequences"]} == courts
    assert sum(len(p["objectifs"]) for ps in ref["parties"].values() for p in ps) == 54
    assert sum(len(ps) for ps in ref["parties"].values()) == 16
