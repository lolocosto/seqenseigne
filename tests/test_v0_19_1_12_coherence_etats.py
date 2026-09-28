"""tests/test_v0_19_1_12_coherence_etats.py — v0.19.1.12

`promouvoir_referentiels_utilises` : un référentiel `verrouille` lié à au moins
une progression passe à `utilise` ; idempotent ; ne promeut pas un référentiel
`en_cours`/`valide` ni un référentiel `verrouille` sans progression.
"""
import importlib.util
from pathlib import Path

import pytest

from persistence.sqlite_store import SqliteStore

_SPEC = importlib.util.spec_from_file_location(
    "coherence_etats_referentiels",
    Path(__file__).resolve().parent.parent / "outils"
    / "coherence_etats_referentiels.py")
ce = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ce)


@pytest.fixture
def db(tmp_path):
    return SqliteStore(tmp_path / "data")


def _ref(conn, rid, etat):
    conn.execute("""INSERT INTO referentiel_niveaux
        (id,niveau,version,date_debut,date_fin,description,etat)
        VALUES (?,?,?,?,?,?,?)""",
        (rid, "N10", rid, "2021-09-01", "2022-08-31", "T", etat))


def _prog(conn, pid, rid):
    conn.execute("""INSERT INTO etablissements (id,nom,academie)
        VALUES (?,?,?)""", (pid + "_e", "T", "Rennes"))
    conn.execute("""INSERT INTO progressions
        (id,niveau,annee,etablissement_id,referentiel_id,etat)
        VALUES (?,?,?,?,?,'en_cours')""",
        (pid, "N10", "2021-2022", pid + "_e", rid))


def test_promotion_verrouille_avec_progression(db):
    with db._conn() as conn:
        _ref(conn, "R_verrou", "verrouille")
        _prog(conn, "pg1", "R_verrou")
        promus = ce.promouvoir_referentiels_utilises(conn)
        etat = conn.execute("SELECT etat FROM referentiel_niveaux WHERE id=?",
                            ("R_verrou",)).fetchone()[0]
    assert promus == ["R_verrou"]
    assert etat == "utilise"


def test_pas_de_promotion_sans_progression(db):
    with db._conn() as conn:
        _ref(conn, "R_seul", "verrouille")  # aucune progression
        promus = ce.promouvoir_referentiels_utilises(conn)
        etat = conn.execute("SELECT etat FROM referentiel_niveaux WHERE id=?",
                            ("R_seul",)).fetchone()[0]
    assert promus == []
    assert etat == "verrouille"


def test_pas_de_promotion_si_valide(db):
    with db._conn() as conn:
        _ref(conn, "R_valide", "valide")
        _prog(conn, "pg2", "R_valide")
        promus = ce.promouvoir_referentiels_utilises(conn)
        etat = conn.execute("SELECT etat FROM referentiel_niveaux WHERE id=?",
                            ("R_valide",)).fetchone()[0]
    assert promus == []
    assert etat == "valide"


def test_idempotent(db):
    with db._conn() as conn:
        _ref(conn, "R_idem", "verrouille")
        _prog(conn, "pg3", "R_idem")
        ce.promouvoir_referentiels_utilises(conn)
        promus2 = ce.promouvoir_referentiels_utilises(conn)
    # Au 2e passage, le référentiel est déjà `utilise` → plus rien à promouvoir.
    assert promus2 == []
