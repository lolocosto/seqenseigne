"""tests/test_v0_58_2_scanner_apres_migration.py — v0.58.2

Le scanner et les données de départ après la migration des codes (v0.58.0).

Constat (v0.58.1) : le scanner résolvait les titres-macros des `.tex` avec les
seuls CSV de départ (`C0X_objectifs.csv`, `C0X_connaissances.csv`), restés en
codes S… : une nouvelle notion ou méthode de A1 dont le titre est
`\\seqObjectifGetNom{02}` était importée « [à saisir] ». L'audit a trouvé deux
autres effets du scan sur une base migrée : il recréait N11/S01…S14 depuis
l'instantané en S… d'un référentiel verrouillé, et sa réécriture complète des
notions et des méthodes détachait les méthodes reclassées de leur objectif
(et, avant comme après la migration, effaçait les liens objectif ↔ notion).

Invariants protégés (décisions P1 à P5, doc/redemarrage_v0_58_2.md) :
  P1 titres : tables vivantes d'abord ; CSV de départ en repli, rattachés au
     code vivant seulement si la séquence porte le même nom ; sinon
     « [à saisir] » avec incident. Les CSV ne sont jamais réécrits.
  P2 un scan ne crée rien pour une séquence absente des séquences du cycle.
  P3 un scan n'ajoute que les nouveaux atomes ; rien d'existant n'est touché.
  P4 libellés de parties de 6e lus sous l'ancien code d'`objectifs_6e.json`.
  P5 modèle « programme du cycle » : critères du CSV retrouvés après migration.

Base : celle des tests de l'outil de migration v0.58.0, migrée.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from outils import migrer_themes_codes_2027 as mig
from persistence.csv_store import CsvStore
from persistence.sqlite_store import SqliteStore
from tests.test_v0_52_0_import_lot6e import base as base_v052  # noqa: F401
from tests.test_v0_58_0_migration_themes_codes import (  # noqa: F401
    RECL,
    _ins,
    _migrer,
    _q,
    _tables,
    base,
)


@pytest.fixture(autouse=True)
def _table_reduite(tmp_path, monkeypatch):
    p = tmp_path / "reclassement_test.json"
    p.write_text(json.dumps(RECL), encoding="utf-8")
    monkeypatch.setattr(mig, "RECLASSEMENT", p)


def _preparer(db):
    """Avant migration : un référentiel verrouillé dont l'instantané est en
    S… (comme 2025_N11b), un lien objectif ↔ notion, une méthode liée par
    identifiant à son objectif (reclassée ensuite en A2), un objectif A1 avec
    méthode et critères."""
    c = sqlite3.connect(db)
    _ins(c, "referentiel_niveaux", id="2025_N10b", niveau="N10", version="2025b",
         etat="verrouille", source="interne", type_ref="principal")
    for code, nom in (("S03", "Calcul numérique"), ("S07", "Probabilités")):
        _ins(c, "referentiel_sequences", referentiel_id="2025_N10b", code=code, numero=3,
             nom=nom, theme_code="A")
        _ins(c, "referentiel_objectifs", referentiel_id="2025_N10b", seq_code=code,
             code="02", nom=f"Figé {code}", critere_f="f", critere_a="a", critere_e="e")
    _ins(c, "objectif_notions", objectif_id="ob_S10", notion_id="no_s10_2", ordre=0)
    c.execute("UPDATE objectifs SET methode_id='me_s02_1' WHERE id='ob_S02'")
    _ins(c, "methodes", id="me_s03_1", titre="Priorités", niveau="N10", sequence="S03",
         num_methode=1, num_objectif="02", fichier="N10_S03_Methode_01.tex",
         etat_code="valide")
    c.execute("UPDATE objectifs SET methode_id='me_s03_1', critere_F='cf', critere_A='ca', "
              "critere_E='ce' WHERE id='ob_S03'")
    c.commit()
    c.close()
    d = Path(db).parent
    (d / "referentiels" / "2025_N10b" / "_publication").mkdir(parents=True)
    (d / "referentiels" / "2025_N10b" / "_publication" / "referentiel.json").write_text(
        json.dumps({"exporte_par": "seqenseigne 0.58.1 (atelier)"}), encoding="utf-8")


@pytest.fixture
def migree(base):
    _preparer(base)
    r, _, _ = _migrer(base)
    assert not r.anomalies
    return base


def _ecrire(arbo: Path, rel: str, txt: str):
    p = arbo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")


def _methode(arbo, niv, seq, num, titre):
    _ecrire(arbo, f"{niv}/methodes/{niv}_{seq}_Methode_{num}.tex",
            "\\seqSetCodeSequence{%s}\n\\begin{seqMethode}{%s}{Corps.}\n"
            "\\underline{Exemples}: un exemple.\n\\end{seqMethode}\n" % (seq, titre))


def _notion(arbo, niv, seq, num, titre):
    _ecrire(arbo, f"{niv}/notions/{niv}_{seq}_Notion_{num}.tex",
            "\\seqSetCodeSequence{%s}\n\\begin{seqNotion}{%s}{Corps.}\n\\end{seqNotion}\n"
            % (seq, titre))


def _scanner(db, arbo, niveau="N10"):
    from scanner_latex import scanner_niveau
    from importers.scanner_latex import scanner_vers_bdd
    d = Path(db).parent
    data = scanner_niveau(str(arbo), niveau)
    return scanner_vers_bdd(data, SqliteStore(d), CsvStore(d))


def _titre(db, table, fichier):
    r = _q(db, f"SELECT titre FROM {table} WHERE fichier=?", (fichier,))
    assert len(r) == 1, f"{fichier} : {len(r)} ligne(s)"
    return r[0][0]


@pytest.fixture
def arbo(tmp_path):
    a = tmp_path / "sequences"
    _methode(a, "N10", "A1", "05", r"\seqObjectifGetNom{02}")
    _notion(a, "N10", "A1", "05", r"\seqConnaissanceGetNom{02}")
    _notion(a, "N10", "A1", "06", r"\seqConnaissanceGetNom{09}")
    _methode(a, "N10", "B1", "07", r"Séquence \seqSequenceGetNumero : \seqSequenceGetNom")
    return a


# ── P1 : titres-macros d'une séquence A1 ────────────────────────────────────

def test_nouvelle_methode_a1_dont_le_titre_est_une_macro_prend_le_nom_de_l_objectif_vivant(
        migree, arbo):
    """Le nom vivant (« Objectif propre à S03 ») l'emporte sur celui du CSV
    de départ (N10,S03,02 « Traduire un enchaînement… ») : c'est lui que
    rendent les atomes et les livrets."""
    rep = _scanner(migree, arbo)
    assert _titre(migree, "methodes", "N10_A1_Methode_05.tex") == "Objectif propre à S03"
    assert not [i for i in rep["incidents_macros"] if i["fichier"] == "N10_A1_Methode_05.tex"]


def test_nouvelle_notion_a1_prend_la_connaissance_du_csv_de_s03_rattache_par_le_nom(migree, arbo):
    """Aucune notion vivante 02 en A1 : le CSV (codes S…) est lu sous le code
    vivant parce que A1 et S03 portent le même nom « Calcul numérique »."""
    _scanner(migree, arbo)
    assert _titre(migree, "notions", "N10_A1_Notion_05.tex") == (
        "Opérandes des opérations arithmétiques: terme, facteur, dividende, diviseur.")


def test_connaissance_introuvable_partout_reste_a_saisir_avec_un_incident_explicite(migree, arbo):
    rep = _scanner(migree, arbo)
    assert _titre(migree, "notions", "N10_A1_Notion_06.tex") == "[à saisir]"
    inc = [i for i in rep["incidents_macros"] if i["fichier"] == "N10_A1_Notion_06.tex"]
    assert inc and "connaissance 09 introuvable pour N10/A1" in inc[0]["raison"]


def test_getters_de_sequence_lus_dans_les_tables_vivantes_numero_affiche_en_code_de_theme(
        migree, arbo):
    _scanner(migree, arbo)
    assert _titre(migree, "methodes", "N10_B1_Methode_07.tex") == (
        "Séquence B1 : Transformations géométriques")


def test_csv_du_cycle_3_jamais_rattache_a_une_sequence_vivante_d_un_autre_nom(migree):
    """C03_*.csv décrit l'ancien découpage : S07 « Proportionnalité » n'est pas
    la B3 « Angles » (S07 → B3 dans la table de correspondance)."""
    from services.resoudre_macros import completer_depuis_base, construire_contexte_global
    d = Path(migree).parent
    ctx = construire_contexte_global(CsvStore(d))
    assert ctx.connaissance_nom("N09", "S07", "01")
    c = sqlite3.connect(migree)
    completer_depuis_base(ctx, c)
    c.close()
    assert ctx.connaissance_nom("N09", "B3", "01") is None
    assert ctx.objectif_info("N09", "B3", "02") is None
    assert ctx.objectif_info("N10", "A1", "03")["nom"].startswith("Effectuer")    # C04 : rattaché


def test_les_csv_de_depart_ne_sont_jamais_reecrits(migree, arbo):
    d = Path(migree).parent
    avant = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in d.glob("*.csv")}
    _scanner(migree, arbo)
    assert avant and avant == {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in d.glob("*.csv")}


def test_base_d_avant_migration_connaissance_du_csv_comme_avant_objectif_au_nom_vivant(
        base, tmp_path):
    """Base non migrée : une connaissance absente de la base vient du CSV
    comme avant ; un objectif prend désormais son nom vivant (avant v0.58.2 :
    celui du CSV, « Traduire un enchaînement… », que l'atelier n'affiche
    plus)."""
    _preparer(base)
    a = tmp_path / "seq"
    _notion(a, "N10", "S03", "07", r"\seqConnaissanceGetNom{03}")
    _methode(a, "N10", "S03", "08", r"\seqObjectifGetNom{02}")
    _scanner(base, a)
    assert _titre(base, "notions", "N10_S03_Notion_07.tex") == (
        "Résultats des opérations arithmétiques: somme, différence, produit, quotient.")
    assert _titre(base, "methodes", "N10_S03_Methode_08.tex") == "Objectif propre à S03"


# ── Second scan, P2, P3 ─────────────────────────────────────────────────────

def test_second_scan_sans_doublon_et_base_identique_table_par_table(migree, arbo):
    r1 = _scanner(migree, arbo)
    assert r1["notions"]["nouvelles"] == 2 and r1["methodes"]["nouvelles"] == 2
    t1 = _tables(migree)
    r2 = _scanner(migree, arbo)
    assert r2["notions"]["nouvelles"] == 0 and r2["methodes"]["nouvelles"] == 0
    assert _tables(migree) == t1


def test_scan_apres_migration_ne_recree_pas_les_sequences_s_d_un_instantane_verrouille(
        migree, arbo):
    """2025_N10b (verrouillé, instantané S03/S07) : avant v0.58.2, chaque scan
    recréait N10/S03 et N10/S07 (séquences-niveaux, parties, objectifs) à côté
    de A1 et C2."""
    _scanner(migree, arbo)
    codes = {s for (s,) in _q(migree, "SELECT sequence_code FROM sequences_par_niveau")}
    assert not {c for c in codes if c.startswith("S")}
    assert not _q(migree, "SELECT 1 FROM objectifs WHERE nom LIKE 'Figé%'")


def test_reconstruction_des_objectifs_garde_effet_pour_les_sequences_du_cycle(base):
    """Base non migrée (S03 et S07 sont des séquences du cycle 4) : la
    réhydratation depuis l'instantané verrouillé fonctionne comme avant."""
    _preparer(base)
    rap = SqliteStore(Path(base).parent).ecrire_objectifs(seulement_sequences_du_cycle=True)
    assert rap["objectifs_ignores"] == 0 and rap["objectifs_maj"] + rap["objectifs_crees"] == 2


def test_scan_garde_les_liens_objectif_notion_et_methode_objectif_des_contenus_reclasses(
        migree, arbo):
    avant_on = _q(migree, "SELECT * FROM objectif_notions ORDER BY 1, 2")
    avant_om = _q(migree, "SELECT id, methode_id, critere_F, critere_A, critere_E FROM objectifs "
                          "ORDER BY id")
    assert avant_on and ("ob_S02", "me_s02_1", "", "", "") in avant_om
    _scanner(migree, arbo)
    assert _q(migree, "SELECT * FROM objectif_notions ORDER BY 1, 2") == avant_on
    assert _q(migree, "SELECT id, methode_id, critere_F, critere_A, critere_E FROM objectifs "
                      "ORDER BY id") == avant_om


def test_nouvelle_methode_ne_prend_pas_l_objectif_deja_lie_et_n_efface_pas_ses_criteres(
        migree, arbo):
    """N10_A1_Methode_05 vise l'objectif 02 de A1, déjà lié à me_s03_1 avec
    des critères : rien ne change pour lui."""
    _scanner(migree, arbo)
    assert _q(migree, "SELECT methode_id, critere_F, critere_A, critere_E FROM objectifs "
                      "WHERE id='ob_S03'") == [("me_s03_1", "cf", "ca", "ce")]


def test_referentiels_figes_et_leurs_pdf_intacts_apres_scan(migree, arbo):
    d = Path(migree).parent
    fige = {t: v for t, v in _tables(migree).items() if t.startswith("referentiel")}
    pdf = d / "referentiels" / "N11_v2025" / "_verrouille" / "pdfs" / "livret_sequence__N11__S03.pdf"
    _scanner(migree, arbo)
    _scanner(migree, arbo)
    assert {t: v for t, v in _tables(migree).items() if t.startswith("referentiel")} == fige
    assert pdf.read_bytes() == b"%PDF fige"


# ── P4, P5 ──────────────────────────────────────────────────────────────────

def test_libelles_des_parties_de_6e_lus_sous_l_ancien_code_apres_migration():
    from services.livret_sequence_6e import libelles_parties
    assert libelles_parties("N09", "B1") == libelles_parties("N09", "S05")
    assert libelles_parties("N09", "B1")[2] == "Médiatrice"
    assert libelles_parties("N09", "B4")[2] == "Droites remarquables"   # S08
    assert libelles_parties("N10", "B1") == {}                           # autre niveau


def test_modele_programme_du_cycle_retrouve_les_criteres_du_csv_apres_migration(base):
    """L'objectif 02 de N10/S03 n'a pas de critères en base : le modèle les
    prend dans C04_objectifs.csv, avant comme après la migration (A1)."""
    from services import modeles_referentiel as mr
    d = Path(base).parent

    def parties(nom):
        c = sqlite3.connect(base)
        c.row_factory = sqlite3.Row
        try:
            seqs = mr._cycle(c, d, "N10")["sequences"]
        finally:
            c.close()
        return next(s["parties"] for s in seqs if s["nom"] == nom)

    avant = parties("Calcul numérique")
    assert avant[0]["objectifs"][0]["criteres"]["f"]
    _migrer(base)
    assert parties("Calcul numérique") == avant


# ── Q1 : séquence-niveau A2 des contenus reclassés ──────────────────────────
#
# La v0.58.0 range des contenus en A2 (N10 et, par copie, N11 dans la base de
# test) sans créer la séquence-niveau A2 ; l'atelier n'a aucun moyen de la
# créer : l'atelier Séquence répondait « introuvable » (ni partie, ni objectif,
# ni lien). L'outil de migration la crée (en cours, vide), même sur une base
# déjà migrée.

def _sn(db, code="A2"):
    return _q(db, "SELECT niveau, etat_code, parametres FROM sequences_par_niveau "
                  "WHERE sequence_code=? ORDER BY niveau", (code,))


def _comme_v0580(db):
    """Base migrée par la v0.58.0 : contenus en A2, aucune séquence-niveau A2."""
    c = sqlite3.connect(db)
    c.execute("DELETE FROM sequences_par_niveau WHERE sequence_code='A2' AND niveau LIKE 'N1%'")
    c.commit()
    c.close()


def test_migration_cree_la_sequence_niveau_a2_de_chaque_niveau_qui_a_des_contenus_a2(migree):
    assert _q(migree, "SELECT DISTINCT niveau FROM methodes WHERE sequence='A2' ORDER BY 1") == [
        ("N10",), ("N11",)]
    assert _sn(migree) == [("N10", "en_cours", ""), ("N11", "en_cours", "")]
    assert not _q(migree, "SELECT 1 FROM sequence_parties p JOIN sequences_par_niveau sn "
                          "ON sn.id=p.sequence_par_niveau_id WHERE sn.sequence_code='A2'")
    # Archive : seules les anciennes séquences-niveaux S02, S10 recodées.
    assert _q(migree, "SELECT id FROM sequences_par_niveau WHERE sequence_code LIKE 'X%' "
                      "AND niveau LIKE 'N1%' ORDER BY id") == [
        ("sn_s02",), ("sn_s10",)]


def test_base_deja_migree_l_outil_relance_cree_a2_puis_ne_fait_plus_rien(migree, capsys):
    _comme_v0580(migree)
    assert _sn(migree) == []
    assert mig.main(["--db", str(migree), "--sans-fichiers"]) == 0          # essai à blanc
    assert _sn(migree) == []
    assert "N10/A2 (en cours, sans partie ni objectif)" in capsys.readouterr().out
    assert mig.main(["--db", str(migree), "--sans-fichiers", "--apply", "--yes"]) == 0
    assert [r[0] for r in _sn(migree)] == ["N10", "N11"]
    t = _tables(migree)
    assert mig.main(["--db", str(migree), "--sans-fichiers", "--apply", "--yes"]) == 0
    assert "Rien à faire" in capsys.readouterr().out
    assert _tables(migree) == t


def test_annuler_retire_a2_mais_refuse_si_une_partie_y_a_ete_creee(migree, capsys):
    _comme_v0580(migree)
    assert mig.main(["--db", str(migree), "--sans-fichiers", "--apply", "--yes"]) == 0
    sid = _q(migree, "SELECT id FROM sequences_par_niveau WHERE niveau='N10' AND "
                     "sequence_code='A2'")[0][0]
    c = sqlite3.connect(migree)
    _ins(c, "sequence_parties", id="pt_a2", sequence_par_niveau_id=sid, numero=1)
    c.commit()
    c.close()
    assert mig.main(["--db", str(migree), "--annuler", "--yes"]) != 0
    assert "des parties y ont été créées" in capsys.readouterr().out
    assert len(_sn(migree)) == 2                                   # rien retiré
    c = sqlite3.connect(migree)
    c.execute("DELETE FROM sequence_parties WHERE id='pt_a2'")
    c.commit()
    c.close()
    assert mig.main(["--db", str(migree), "--annuler", "--yes"]) == 0
    assert _sn(migree) == []


def test_atelier_sequence_a2_ouverte_et_modifiable_ses_contenus_listes(migree):
    from app import create_app
    cl = create_app(Path(migree).parent, profil="atelier").test_client()
    assert [m["titre"] for m in cl.get("/api/methodes?niveau=N10&sequence=A2").get_json()] == [
        "Comparer"]
    r = cl.get("/api/v2/sequences-par-niveau/N10/A2")
    assert r.status_code == 200
    j = r.get_json()
    sid = (j.get("sequence_par_niveau") or j)["id"]
    assert cl.post(f"/api/v2/sequences-par-niveau/{sid}/parties", json={}).status_code == 201
    _comme_v0580(migree)
    assert cl.get("/api/v2/sequences-par-niveau/N10/A2").status_code == 404   # cas v0.58.0
