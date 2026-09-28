"""tests/test_v0_19_1_11_audit_ignore_dc.py — v0.19.1.11

L'audit de structure de `verifier_referentiels.auditer_structure` doit ignorer
les pseudo-séquences de planning (devoirs communs DC1/DC2/DC3, bilans…) qui
occupent un créneau sans être de vraies séquences du référentiel. Sinon il
signale de faux écarts pour toute progression de 3e (qui contient des DC).
"""
import importlib.util
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore

# Charger l'outil (hors package outils standard pour le test).
_SPEC = importlib.util.spec_from_file_location(
    "verifier_referentiels",
    Path(__file__).resolve().parent.parent / "outils" / "verifier_referentiels.py")
vr = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(vr)


@pytest.fixture
def db(tmp_path):
    return SqliteStore(tmp_path / "data")


def _setup(db):
    """Référentiel N12 minimal (S01 1 partie) + progression avec un créneau
    S01 et trois créneaux DC1/DC2/DC3."""
    rid, pid, eid = "N12_vTEST", "pg_test", "et_test"
    with db._conn() as conn:
        conn.execute("""INSERT INTO referentiel_niveaux
            (id,niveau,version,date_debut,date_fin,description,etat)
            VALUES (?,?,'T','2022-09-01','2023-08-31','T','verrouille')""",
            (rid, "N12"))
        conn.execute("""INSERT INTO referentiel_themes
            (referentiel_id,code,nom,couleur) VALUES (?,'A','Nb','calcul')""", (rid,))
        conn.execute("""INSERT INTO referentiel_sequences
            (referentiel_id,code,numero,nom,theme_code)
            VALUES (?,'S01',1,'Repr','A')""", (rid,))
        conn.execute("""INSERT INTO referentiel_objectifs
            (referentiel_id,seq_code,code,nom,fin_cycle,critere_f,critere_a,
             critere_e,partie_numero,nb_seances)
            VALUES (?,'S01','01','cours',0,'','','',1,0)""", (rid,))
        conn.execute("""INSERT INTO referentiel_parties
            (referentiel_id,seq_code,numero,nb_seances_R_AE)
            VALUES (?,'S01',1,0)""", (rid,))
        conn.execute("""INSERT INTO etablissements (id,nom,academie)
            VALUES (?,?,?)""", (eid, "Test", "Rennes"))
        conn.execute("""INSERT INTO progressions
            (id,niveau,annee,etablissement_id,referentiel_id,etat)
            VALUES (?,?,?,?,?,'en_cours')""",
            (pid, "N12", "2022-2023", eid, rid))
        for cid, seq, per in [("cr_s01", "S01", "T1"), ("cr_dc1", "DC1", "T1"),
                              ("cr_dc2", "DC2", "T2"), ("cr_dc3", "DC3", "T3")]:
            conn.execute("""INSERT INTO creneaux
                (id,progression_id,seq_code,partie_debut,partie_fin,partie,
                 periode,date_debut,date_fin,revisions,ordre)
                VALUES (?,?,?,1,1,'',?,NULL,NULL,'',0)""", (cid, pid, seq, per))
    return rid


def test_audit_structure_ignore_les_dc(db):
    rid = _setup(db)
    with db._conn() as conn:
        ecarts = vr.auditer_structure(conn, rid)
    # Aucun écart : S01 est aligné, DC1/DC2/DC3 sont ignorés (pas de faux
    # « séquence DC absente du référentiel »).
    assert ecarts == [], f"écarts inattendus : {ecarts}"


def test_re_seq_valide_distingue_dc(db):
    assert vr._RE_SEQ_VALIDE.match("S01")
    assert vr._RE_SEQ_VALIDE.match("S14")
    assert not vr._RE_SEQ_VALIDE.match("DC1")
    assert not vr._RE_SEQ_VALIDE.match("Bilan T1")
